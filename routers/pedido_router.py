import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from config.segurity_Dependencia import Token_Dependencia
from config.session_Dependencia import SessionDeDependencia
from models.configuracion import ConfiguracionNegocio
from models.datos_facturacion import DatosFacturacion
from models.detalle_pedido import DetallePedido
from models.detalle_venta import DetalleVenta
from models.pedido import (
    DatosPedidoCreate,
    EstadoPedido,
    PagoPedidoCreate,
    Pedido,
    PedidoConsultaResponse,
    PedidoCreate,
    PedidoDetalleResponse,
    PedidoInvitadoCreate,
    PedidoInvitadoResponse,
    PedidoItemCreate,
    PedidoResponse,
    PedidoUpdate,
)
from models.producto import Producto
from models.venta import Venta, VentaDetalleResponse, VentaPOSResponse

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
IVA_PORCENTAJE = Decimal("0.13")
CENTAVO = Decimal("0.01")


def _pedido_response(
    pedido: Pedido,
    spending: Decimal = Decimal("0"),
    threshold: Decimal | None = None,
    details: list[PedidoDetalleResponse] | None = None,
):
    is_wholesale = (
        pedido.usuario_id is not None
        and threshold is not None
        and spending >= threshold
    )
    return PedidoResponse.model_validate(
        {
            **pedido.model_dump(exclude={"codigo_acceso_hash"}),
            "prioridad_mayorista": is_wholesale,
            "compras_12_meses": spending,
            "detalles": details,
        }
    )


def _pedido_detalles(session, pedido_id: int) -> list[PedidoDetalleResponse]:
    rows = session.exec(
        select(DetallePedido, Producto)
        .join(Producto, Producto.id_producto == DetallePedido.producto_id)
        .where(DetallePedido.pedido_id == pedido_id)
        .order_by(DetallePedido.id_detalle_pedido)
    ).all()
    return [
        PedidoDetalleResponse.model_validate(
            {
                **detalle.model_dump(),
                "producto_nombre": producto.nombre,
                "producto_codigo": producto.codigo,
            }
        )
        for detalle, producto in rows
    ]


def _authorize_order_access(pedido: Pedido | None, token: dict) -> Pedido:
    if pedido is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido no encontrado",
        )
    if token.get("id_rol") == 3:
        if pedido.usuario_id != token.get("id"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pedido no encontrado",
            )
    elif token.get("id_rol") not in ROLES_GESTION_PEDIDOS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para consultar pedidos",
        )
    return pedido


def _create_order(
    items: list[PedidoItemCreate],
    customer: DatosPedidoCreate,
    user_id: int | None,
    session,
) -> tuple[Pedido, str | None]:
    quantities: dict[int, int] = {}
    for item in items:
        quantities[item.producto_id] = (
            quantities.get(item.producto_id, 0) + item.cantidad
        )
    access_code = secrets.token_urlsafe(24) if user_id is None else None
    try:
        with session.begin():
            products = session.exec(
                select(Producto)
                .where(Producto.id_producto.in_(sorted(quantities)))
                .order_by(Producto.id_producto)
                .with_for_update()
            ).all()
            products_by_id = {product.id_producto: product for product in products}
            missing = set(quantities) - products_by_id.keys()
            if missing:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No se encontraron productos: {sorted(missing)}",
                )

            total = Decimal("0.00")
            lines = []
            for product_id in sorted(quantities):
                product = products_by_id[product_id]
                quantity = quantities[product_id]
                if not product.estado:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"El producto {product.codigo} está inactivo",
                    )
                if product.precio_venta < 0:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"El producto {product.codigo} tiene un precio inválido",
                    )
                line_total = (product.precio_venta * quantity).quantize(
                    CENTAVO,
                    rounding=ROUND_HALF_UP,
                )
                total += line_total
                lines.append(
                    DetallePedido(
                        producto_id=product_id,
                        cantidad=quantity,
                        precio_unitario=product.precio_venta,
                        subtotal=line_total,
                    )
                )

            pedido = Pedido(
                usuario_id=user_id,
                estado="Pendiente",
                total_pedido=total.quantize(CENTAVO, rounding=ROUND_HALF_UP),
                nombre_cliente=customer.nombre_razon_social,
                correo_cliente=str(customer.correo).lower(),
                telefono_cliente=customer.telefono,
                tipo_cliente=customer.tipo_cliente,
                numero_documento=customer.numero_documento,
                direccion_cliente=customer.direccion,
                codigo_acceso_hash=(
                    hashlib.sha256(access_code.encode("utf-8")).hexdigest()
                    if access_code
                    else None
                ),
            )
            session.add(pedido)
            session.flush()
            for line in lines:
                line.pedido_id = pedido.id_pedido
                session.add(line)
            session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se pudo registrar el pedido por una restricción de integridad",
        ) from exc

    session.refresh(pedido)
    return pedido, access_code


def _sales_by_customer(session, user_ids: set[int]) -> dict[int, Decimal]:
    if not user_ids:
        return {}
    since = datetime.now(timezone.utc) - timedelta(days=365)
    rows = session.exec(
        select(
            Venta.cliente_usuario_id,
            func.coalesce(func.sum(Venta.total_pagar), 0),
        )
        .where(
            Venta.cliente_usuario_id.in_(user_ids),
            Venta.fecha_hora >= since,
        )
        .group_by(Venta.cliente_usuario_id)
    ).all()
    return {
        int(user_id): Decimal(str(total or 0))
        for user_id, total in rows
        if user_id is not None
    }


@router.get(
    "/pedidos",
    response_model=list[PedidoResponse],
    status_code=status.HTTP_200_OK,
)
async def listar_pedidos(session: SessionDeDependencia, token: Token_Dependencia):
    orders = session.exec(select(Pedido)).all()
    if token["id_rol"] == 3:
        orders = [order for order in orders if order.usuario_id == token["id"]]
    elif token["id_rol"] not in ROLES_GESTION_PEDIDOS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para consultar pedidos",
        )

    user_ids = {order.usuario_id for order in orders if order.usuario_id is not None}
    spendings = _sales_by_customer(session, user_ids)
    setting = session.get(ConfiguracionNegocio, 1)
    threshold = setting.umbral_mayorista if setting is not None else None
    if token["id_rol"] in ROLES_GESTION_PEDIDOS and threshold is not None:
        orders.sort(
            key=lambda order: (
                order.estado == "Entregado",
                -int(
                    spendings.get(order.usuario_id, Decimal("0")) >= threshold
                    if order.usuario_id is not None
                    else False
                ),
                -spendings.get(order.usuario_id, Decimal("0")),
                order.id_pedido,
            )
        )
    else:
        orders.sort(key=lambda order: order.id_pedido or 0)
    return [
        _pedido_response(
            order,
            spendings.get(order.usuario_id, Decimal("0"))
            if order.usuario_id is not None
            else Decimal("0"),
            threshold,
        )
        for order in orders
    ]


@router.get("/pedidos/{pedido_id:int}", response_model=PedidoResponse)
async def obtener_pedido(
    pedido_id: int,
    session: SessionDeDependencia,
    token: Token_Dependencia,
):
    pedido = _authorize_order_access(session.get(Pedido, pedido_id), token)
    return _pedido_response(pedido)


@router.post(
    "/pedidos",
    response_model=PedidoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def crear_pedido(
    payload: PedidoCreate,
    session: SessionDeDependencia,
    token: Token_Dependencia,
):
    user_id = token.get("id")
    if (
        not isinstance(user_id, int)
        or token["id_rol"] not in (*ROLES_GESTION_PEDIDOS, 3)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para crear pedidos",
        )
    pedido, _ = _create_order(
        payload.items,
        payload.datos_cliente,
        user_id,
        session,
    )
    return _pedido_response(
        pedido,
        details=_pedido_detalles(session, pedido.id_pedido),
    )


@router.post(
    "/pedidos/invitado",
    response_model=PedidoInvitadoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def crear_pedido_invitado(
    payload: PedidoInvitadoCreate,
    session: SessionDeDependencia,
):
    pedido, access_code = _create_order(
        payload.items,
        payload.datos_cliente,
        None,
        session,
    )
    if access_code is None:
        raise RuntimeError("No se generó un código de acceso para el pedido invitado")
    return PedidoInvitadoResponse(
        pedido=_pedido_response(pedido),
        codigo_acceso=access_code,
        instrucciones=(
            "Presenta este comprobante en la ferretería para pagar y retirar "
            "tu pedido. El código permite consultar su estado; guárdalo y no "
            "lo compartas."
        ),
        detalles=_pedido_detalles(session, pedido.id_pedido),
    )


@router.get("/pedidos/consulta", response_model=PedidoConsultaResponse)
async def consultar_pedido_invitado(
    session: SessionDeDependencia,
    codigo_acceso: str = Header(alias="X-Order-Access-Code"),
):
    if len(codigo_acceso) < 24 or len(codigo_acceso) > 128:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comprobante no encontrado",
        )
    digest = hashlib.sha256(codigo_acceso.encode("utf-8")).hexdigest()
    pedido = session.exec(
        select(Pedido).where(
            Pedido.usuario_id.is_(None),
            Pedido.codigo_acceso_hash == digest,
        )
    ).first()
    if pedido is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comprobante no encontrado",
        )
    tax = (pedido.total_pedido * IVA_PORCENTAJE).quantize(
        CENTAVO,
        rounding=ROUND_HALF_UP,
    )
    return PedidoConsultaResponse(
        pedido=_pedido_response(pedido),
        detalles=_pedido_detalles(session, pedido.id_pedido),
        iva_estimado=tax,
        total_estimado=pedido.total_pedido + tax,
        venta_id=pedido.venta_id,
    )


@router.put("/pedidos/{pedido_id}", response_model=PedidoResponse)
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
    if payload.estado == "Entregado":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Para entregar el pedido debe registrarse su pago y generar la venta",
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
    return _pedido_response(pedido)


@router.post(
    "/pedidos/{pedido_id}/entregar",
    response_model=VentaPOSResponse,
)
async def pagar_y_entregar_pedido(
    pedido_id: int,
    payload: PagoPedidoCreate,
    session: SessionDeDependencia,
    token: Token_Dependencia,
):
    if token.get("id_rol") not in ROLES_GESTION_PEDIDOS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo empleados y propietarios pueden registrar el pago",
        )
    try:
        with session.begin():
            pedido = session.exec(
                select(Pedido)
                .where(Pedido.id_pedido == pedido_id)
                .with_for_update()
            ).first()
            if pedido is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Pedido no encontrado",
                )
            if pedido.estado != "Listo":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Solo se puede cobrar y entregar un pedido marcado como listo",
                )
            if session.exec(
                select(Venta).where(Venta.pedido_id == pedido_id)
            ).first() is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="El pedido ya tiene una venta registrada",
                )

            rows = session.exec(
                select(DetallePedido, Producto)
                .join(Producto, Producto.id_producto == DetallePedido.producto_id)
                .where(DetallePedido.pedido_id == pedido_id)
                .order_by(Producto.id_producto)
                .with_for_update()
            ).all()
            if not rows:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="El pedido no contiene productos",
                )
            subtotal = sum(
                (detail.subtotal for detail, _ in rows),
                Decimal("0.00"),
            ).quantize(CENTAVO, rounding=ROUND_HALF_UP)
            tax = (subtotal * IVA_PORCENTAJE).quantize(
                CENTAVO,
                rounding=ROUND_HALF_UP,
            )
            sale = Venta(
                usuario_id=token["id"],
                cliente_usuario_id=pedido.usuario_id,
                canal="WEB",
                pedido_id=pedido_id,
                subtotal=subtotal,
                iva=tax,
                total_pagar=subtotal + tax,
            )
            session.add(sale)
            session.flush()
            pedido.venta_id = sale.id_venta
            session.add(pedido)
            sale_lines = []
            response_lines = []
            for order_line, product in rows:
                if not product.estado or product.stock_actual < order_line.cantidad:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            f"Existencia insuficiente para {product.nombre}; "
                            "actualiza el pedido antes de cobrar."
                        ),
                    )
                product.stock_actual -= order_line.cantidad
                session.add(product)
                sale_line = DetalleVenta(
                    venta_id=sale.id_venta,
                    producto_id=product.id_producto,
                    cantidad_id=order_line.cantidad,
                    precio_unitario=order_line.precio_unitario,
                    descuento=Decimal("0.00"),
                    subtotal=order_line.subtotal,
                )
                sale_lines.append(sale_line)
                response_lines.append(
                    VentaDetalleResponse(
                        producto_id=product.id_producto,
                        codigo=product.codigo,
                        nombre=product.nombre,
                        cantidad=order_line.cantidad,
                        precio_unitario=order_line.precio_unitario,
                        descuento=Decimal("0.00"),
                        subtotal=order_line.subtotal,
                    )
                )
            session.add_all(sale_lines)
            session.add(
                DatosFacturacion(
                    venta_id=sale.id_venta,
                    tipo_cliente=pedido.tipo_cliente,
                    nombre_razon_social=pedido.nombre_cliente,
                    numero_documento=pedido.numero_documento,
                    correo=pedido.correo_cliente,
                    telefono=pedido.telefono_cliente,
                    direccion=pedido.direccion_cliente,
                    metodo_pago=payload.metodo_pago,
                )
            )
            pedido.estado = "Entregado"
            session.add(pedido)
            session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se pudo cobrar el pedido por una restricción de integridad",
        ) from exc

    return VentaPOSResponse(
        id_venta=sale.id_venta,
        usuario_id=sale.usuario_id,
        fecha_hora=sale.fecha_hora,
        subtotal=sale.subtotal,
        iva=sale.iva,
        total_pagar=sale.total_pagar,
        detalles=response_lines,
    )


@router.get(
    "/pedidos/{pedido_id}/detalles",
    response_model=list[PedidoDetalleResponse],
)
async def listar_detalles_pedido(
    pedido_id: int,
    session: SessionDeDependencia,
    token: Token_Dependencia,
):
    pedido = _authorize_order_access(session.get(Pedido, pedido_id), token)
    return _pedido_detalles(session, pedido.id_pedido)
