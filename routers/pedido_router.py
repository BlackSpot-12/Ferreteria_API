from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from config.segurity_Dependencia import Token_Dependencia
from config.session_Dependencia import SessionDeDependencia
from models.detalle_pedido import DetallePedido
from models.pedido import (
    EstadoPedido,
    Pedido,
    PedidoCreate,
    PedidoDetalleResponse,
    PedidoUpdate,
)
from models.producto import Producto

router = APIRouter()
ROLES_GESTION_PEDIDOS = (1, 2)
ESTADOS_PEDIDO: tuple[EstadoPedido, ...] = (
    "Pendiente",
    "En preparacion",
    "Listo",
    "Entregado",
)
TRANSICIONES_PEDIDO = {
    "Pendiente": "En preparacion",
    "En preparacion": "Listo",
    "Listo": "Entregado",
}


@router.get("/pedidos", response_model=list[Pedido], status_code=status.HTTP_200_OK)
async def listar_pedidos(session: SessionDeDependencia, token: Token_Dependencia):
    consulta = select(Pedido).order_by(Pedido.id_pedido)
    if token["id_rol"] == 3:
        consulta = consulta.where(Pedido.usuario_id == token["id"])
    elif token["id_rol"] not in ROLES_GESTION_PEDIDOS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para consultar pedidos",
        )
    return session.exec(consulta).all()


@router.get("/pedidos/{pedido_id}", response_model=Pedido)
async def obtener_pedido(
    pedido_id: int,
    session: SessionDeDependencia,
    token: Token_Dependencia,
):
    pedido = session.get(Pedido, pedido_id)
    if pedido is None or (
        token["id_rol"] == 3 and pedido.usuario_id != token["id"]
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido no encontrado",
        )
    if token["id_rol"] not in (*ROLES_GESTION_PEDIDOS, 3):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para consultar pedidos",
        )
    return pedido


@router.post(
    "/pedidos",
    response_model=Pedido,
    status_code=status.HTTP_201_CREATED,
)
async def crear_pedido(
    payload: PedidoCreate,
    session: SessionDeDependencia,
    token: Token_Dependencia,
):
    usuario_id = token.get("id")
    if (
        not isinstance(usuario_id, int)
        or token["id_rol"] not in (*ROLES_GESTION_PEDIDOS, 3)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para crear pedidos",
        )

    cantidades = {}
    for item in payload.items:
        cantidades[item.producto_id] = cantidades.get(item.producto_id, 0) + item.cantidad

    try:
        with session.begin():
            productos = session.exec(
                select(Producto)
                .where(Producto.id_producto.in_(sorted(cantidades)))
                .order_by(Producto.id_producto)
                .with_for_update()
            ).all()
            productos_por_id = {producto.id_producto: producto for producto in productos}
            faltantes = set(cantidades) - productos_por_id.keys()
            if faltantes:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No se encontraron productos: {sorted(faltantes)}",
                )

            total = Decimal("0.00")
            lineas = []
            for producto_id in sorted(cantidades):
                producto = productos_por_id[producto_id]
                cantidad = cantidades[producto_id]
                if not producto.estado:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"El producto {producto.codigo} está inactivo",
                    )
                if producto.precio_venta < 0:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"El producto {producto.codigo} tiene un precio inválido",
                    )
                subtotal_linea = (producto.precio_venta * cantidad).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP,
                )
                total += subtotal_linea
                lineas.append(
                    DetallePedido(
                        producto_id=producto_id,
                        cantidad=cantidad,
                        precio_unitario=producto.precio_venta,
                        subtotal=subtotal_linea,
                    )
                )

            pedido = Pedido(
                usuario_id=usuario_id,
                estado="Pendiente",
                total_pedido=total.quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP,
                ),
            )
            session.add(pedido)
            session.flush()
            for linea in lineas:
                linea.pedido_id = pedido.id_pedido
                session.add(linea)
            session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se pudo registrar el pedido por una restricción de integridad",
        ) from exc

    session.refresh(pedido)
    return pedido


@router.put("/pedidos/{pedido_id}", response_model=Pedido)
async def actualizar_estado_pedido(
    pedido_id: int,
    payload: PedidoUpdate,
    session: SessionDeDependencia,
    token: Token_Dependencia,
):
    if token["id_rol"] not in ROLES_GESTION_PEDIDOS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo empleados y propietarios pueden actualizar pedidos",
        )
    pedido = session.get(Pedido, pedido_id)
    if pedido is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido no encontrado",
        )
    if payload.estado not in ESTADOS_PEDIDO:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Estado de pedido no válido",
        )
    if TRANSICIONES_PEDIDO.get(pedido.estado) != payload.estado:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se permite cambiar el pedido de '{pedido.estado}' a '{payload.estado}'",
        )

    pedido.estado = payload.estado
    session.add(pedido)
    session.commit()
    session.refresh(pedido)
    return pedido


@router.get(
    "/pedidos/{pedido_id}/detalles",
    response_model=list[PedidoDetalleResponse],
)
async def listar_detalles_pedido(
    pedido_id: int,
    session: SessionDeDependencia,
    token: Token_Dependencia,
):
    pedido = session.get(Pedido, pedido_id)
    if pedido is None or (
        token["id_rol"] == 3 and pedido.usuario_id != token["id"]
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido no encontrado",
        )
    if token["id_rol"] not in (*ROLES_GESTION_PEDIDOS, 3):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para consultar detalles de pedidos",
        )
    detalles = session.exec(
        select(DetallePedido)
        .where(DetallePedido.pedido_id == pedido_id)
        .order_by(DetallePedido.id_detalle_pedido)
    ).all()
    return detalles
