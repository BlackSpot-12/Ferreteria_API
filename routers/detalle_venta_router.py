from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from config.segurity_Dependencia import Token_Dependencia
from config.session_Dependencia import SessionDeDependencia
from models.detalle_venta import DetalleVenta
from models.producto import Producto
from models.venta import Venta, VentaDetalleResponse

router = APIRouter()


@router.get(
    "/ventas/{venta_id}/detalles",
    response_model=list[VentaDetalleResponse],
    status_code=status.HTTP_200_OK,
)
async def listar_detalles_venta(
    venta_id: int,
    session: SessionDeDependencia,
    token: Token_Dependencia,
):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo empleados y propietarios pueden consultar detalles de venta",
        )
    if session.get(Venta, venta_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Venta no encontrada",
        )

    lineas = session.exec(
        select(DetalleVenta, Producto)
        .join(Producto, DetalleVenta.producto_id == Producto.id_producto)
        .where(DetalleVenta.venta_id == venta_id)
        .order_by(DetalleVenta.id_detalle_venta)
    ).all()
    return [
        VentaDetalleResponse(
            producto_id=producto.id_producto,
            codigo=producto.codigo,
            nombre=producto.nombre,
            cantidad=detalle.cantidad_id,
            precio_unitario=detalle.precio_unitario,
            descuento=detalle.descuento,
            subtotal=detalle.subtotal,
        )
        for detalle, producto in lineas
    ]
