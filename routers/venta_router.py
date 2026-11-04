import hashlib
import os
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from config.segurity_Dependencia import Token_Dependencia
from config.session_Dependencia import SessionDeDependencia
from models.datos_facturacion import DatosFacturacion
from models.detalle_venta import DetalleVenta
from models.pedido import Pedido
from models.producto import Producto
from models.usuario import Usuario
from models.venta import (
    FacturaEmisor,
    FacturaResponse,
    Venta,
    VentaDetalleResponse,
    VentaPOSCreate,
    VentaPOSResponse,
)

router = APIRouter()

IVA_PORCENTAJE = Decimal("0.13")
CENTAVO = Decimal("0.01")
ROLES_POS = (1, 2)


def _detalle_respuesta(detalle, producto):
    return VentaDetalleResponse(
        producto_id=producto.id_producto,
        codigo=producto.codigo,
        nombre=producto.nombre,
        cantidad=detalle.cantidad_id,
        precio_unitario=detalle.precio_unitario,
        descuento=detalle.descuento,
        subtotal=detalle.subtotal,
    )


def _authorize_sale(venta: Venta | None, token: dict) -> Venta:
    if venta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Venta no encontrada",
        )
    if token.get("id_rol") == 2 and venta.usuario_id != token.get("id"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Venta no encontrada",
        )
    if token.get("id_rol") == 3 and venta.cliente_usuario_id != token.get("id"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Venta no encontrada",
        )
    return venta


@router.get("/ventas", response_model=list[Venta], status_code=status.HTTP_200_OK)
async def listar_ventas(
    session: SessionDeDependencia,
    token: Token_Dependencia,
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
    canal: Literal["POS", "WEB"] | None = None,
):
    if token["id_rol"] not in ROLES_POS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo empleados y propietarios pueden consultar ventas",
        )
    query = select(Venta)
    if token["id_rol"] == 2:
        query = query.where(Venta.usuario_id == token["id"])
    if fecha_inicio is not None and fecha_fin is not None and fecha_inicio > fecha_fin:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="fecha_inicio no puede ser posterior a fecha_fin",
        )
    if fecha_inicio is not None:
        query = query.where(
            Venta.fecha_hora >= datetime.combine(
                fecha_inicio,
                time.min,
                tzinfo=timezone.utc,
            )
        )
    if fecha_fin is not None:
        query = query.where(
            Venta.fecha_hora < datetime.combine(
                fecha_fin + timedelta(days=1),
                time.min,
                tzinfo=timezone.utc,
            )
        )
    if canal is not None:
        query = query.where(Venta.canal == canal)
    return session.exec(query.order_by(Venta.fecha_hora.desc())).all()


@router.get("/ventas/{venta_id}", response_model=VentaPOSResponse)
async def obtener_venta(
    venta_id: int,
    session: SessionDeDependencia,
    token: Token_Dependencia,
):
    if token["id_rol"] not in (*ROLES_POS, 3):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo empleados y propietarios pueden consultar ventas",
        )
    venta = _authorize_sale(session.get(Venta, venta_id), token)
    lineas = session.exec(
        select(DetalleVenta, Producto)
        .join(Producto, DetalleVenta.producto_id == Producto.id_producto)
        .where(DetalleVenta.venta_id == venta_id)
        .order_by(DetalleVenta.id_detalle_venta)
    ).all()
    return VentaPOSResponse(
        id_venta=venta.id_venta,
        usuario_id=venta.usuario_id,
        fecha_hora=venta.fecha_hora,
        subtotal=venta.subtotal,
        iva=venta.iva,
        total_pagar=venta.total_pagar,
        detalles=[_detalle_respuesta(detalle, producto) for detalle, producto in lineas],
    )


@router.post(
    "/ventas",
    response_model=VentaPOSResponse,
    status_code=status.HTTP_201_CREATED,
)
async def procesar_venta(
    payload: VentaPOSCreate,
    session: SessionDeDependencia,
    token: Token_Dependencia,
):
    usuario_id = token.get("id")
    if not isinstance(usuario_id, int):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token no contiene un usuario válido",
            headers={"WWW-Authenticate": "Bearer"},
        )

    cantidades = {}
    for item in payload.items:
        cantidades[item.producto_id] = cantidades.get(item.producto_id, 0) + item.cantidad

    try:
        with session.begin():
            usuario = session.exec(
                select(Usuario)
                .where(Usuario.id_usuario == usuario_id)
                .with_for_update()
            ).first()
            if usuario is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="El usuario del token ya no existe",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            if usuario.rol_id not in ROLES_POS:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Solo empleados y propietarios pueden procesar ventas",
                )

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

            subtotal = Decimal("0.00")
            lineas_creadas = []
            productos_linea = []
            for producto_id in sorted(cantidades):
                producto = productos_por_id[producto_id]
                cantidad = cantidades[producto_id]
                if not producto.estado:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"El producto {producto.codigo} está inactivo",
                    )
                if producto.stock_actual < cantidad:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            f"Existencia insuficiente para {producto.nombre}. "
                            f"Disponible: {producto.stock_actual}; solicitada: {cantidad}."
                        ),
                    )
                if producto.precio_venta < 0:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"El producto {producto.codigo} tiene un precio inválido",
                    )

                precio = producto.precio_venta
                importe_linea = (precio * cantidad).quantize(
                    CENTAVO, rounding=ROUND_HALF_UP
                )
                subtotal += importe_linea
                productos_linea.append(producto)
                lineas_creadas.append(
                    DetalleVenta(
                        producto_id=producto_id,
                        cantidad_id=cantidad,
                        precio_unitario=precio,
                        descuento=Decimal("0.00"),
                        subtotal=importe_linea,
                    )
                )

            subtotal = subtotal.quantize(CENTAVO, rounding=ROUND_HALF_UP)
            iva = (subtotal * IVA_PORCENTAJE).quantize(
                CENTAVO, rounding=ROUND_HALF_UP
            )
            total = subtotal + iva
            venta = Venta(
                usuario_id=usuario_id,
                cliente_usuario_id=session.exec(
                    select(Usuario.id_usuario).where(
                        func.lower(Usuario.correo)
                        == payload.datos_facturacion.correo.lower(),
                        Usuario.rol_id == 3,
                    )
                ).first(),
                canal="POS",
                subtotal=subtotal,
                iva=iva,
                total_pagar=total,
            )
            session.add(venta)
            session.flush()

            for producto in productos_linea:
                producto.stock_actual -= cantidades[producto.id_producto]
                session.add(producto)
            for detalle in lineas_creadas:
                detalle.venta_id = venta.id_venta
                session.add(detalle)

            facturacion = DatosFacturacion(
                venta_id=venta.id_venta,
                tipo_cliente=payload.datos_facturacion.tipo_cliente,
                nombre_razon_social=payload.datos_facturacion.nombre_razon_social,
                numero_documento=payload.datos_facturacion.numero_documento,
                correo=payload.datos_facturacion.correo.lower(),
                telefono=payload.datos_facturacion.telefono,
                direccion=payload.datos_facturacion.direccion,
                metodo_pago=payload.datos_facturacion.metodo_pago,
            )
            session.add(facturacion)
            session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se pudo registrar la venta por una restricción de integridad",
        ) from exc

    session.refresh(venta)
    return VentaPOSResponse(
        id_venta=venta.id_venta,
        usuario_id=venta.usuario_id,
        fecha_hora=venta.fecha_hora,
        subtotal=venta.subtotal,
        iva=venta.iva,
        total_pagar=venta.total_pagar,
        detalles=[
            _detalle_respuesta(detalle, producto)
            for detalle, producto in zip(lineas_creadas, productos_linea)
        ],
    )


@router.get("/ventas/{venta_id}/factura", response_model=FacturaResponse)
async def obtener_factura(
    venta_id: int,
    session: SessionDeDependencia,
    token: Token_Dependencia,
):
    if token["id_rol"] not in (*ROLES_POS, 3):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo empleados y propietarios pueden consultar facturas",
        )

    _issuer_data()
    venta = _authorize_sale(session.get(Venta, venta_id), token)
    return _factura_de_venta(venta, session)


def _issuer_data() -> dict[str, str]:
    required_issuer_data = {
        "FACTURA_RAZON_SOCIAL": os.getenv("FACTURA_RAZON_SOCIAL", "").strip(),
        "FACTURA_IDENTIFICACION": os.getenv("FACTURA_IDENTIFICACION", "").strip(),
        "FACTURA_DIRECCION": os.getenv("FACTURA_DIRECCION", "").strip(),
    }
    missing = [key for key, value in required_issuer_data.items() if not value]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Falta configurar los datos del emisor para generar la factura: "
                + ", ".join(missing)
            ),
        )
    return required_issuer_data


def _factura_de_venta(venta: Venta, session) -> FacturaResponse:
    required_issuer_data = _issuer_data()

    facturacion = session.exec(
        select(DatosFacturacion).where(DatosFacturacion.venta_id == venta.id_venta)
    ).first()
    if not facturacion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay datos de facturación para esta venta",
        )

    lineas = session.exec(
        select(DetalleVenta, Producto)
        .join(Producto, DetalleVenta.producto_id == Producto.id_producto)
        .where(DetalleVenta.venta_id == venta.id_venta)
        .order_by(DetalleVenta.id_detalle_venta)
    ).all()

    return FacturaResponse(
        emisor=FacturaEmisor(
            nombre=required_issuer_data["FACTURA_RAZON_SOCIAL"],
            identificacion=required_issuer_data["FACTURA_IDENTIFICACION"],
            direccion=required_issuer_data["FACTURA_DIRECCION"],
            telefono=os.getenv("FACTURA_TELEFONO"),
        ),
        id_factura=venta.id_venta,
        fecha_hora=venta.fecha_hora,
        tipo_cliente=facturacion.tipo_cliente,
        nombre_razon_social=facturacion.nombre_razon_social,
        numero_documento=facturacion.numero_documento,
        correo=facturacion.correo,
        telefono=facturacion.telefono,
        direccion=facturacion.direccion,
        metodo_pago=facturacion.metodo_pago,
        detalles=[_detalle_respuesta(detalle, producto) for detalle, producto in lineas],
        subtotal=venta.subtotal,
        iva_porcentaje=IVA_PORCENTAJE,
        iva=venta.iva,
        total_pagar=venta.total_pagar,
    )


@router.get(
    "/pedidos/consulta/factura",
    response_model=FacturaResponse,
)
async def obtener_factura_invitado(
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
    if pedido.venta_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La factura se generará cuando el pedido se pague y retire",
        )
    venta = session.get(Venta, pedido.venta_id)
    if venta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Venta asociada al pedido no encontrada",
        )
    return _factura_de_venta(venta, session)
