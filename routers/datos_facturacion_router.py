from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from config.segurity_Dependencia import Token_Dependencia
from config.session_Dependencia import SessionDeDependencia
from models.datos_facturacion import DatosFacturacion
from models.venta import Venta

router = APIRouter()


@router.get(
    "/ventas/{venta_id}/datos-facturacion",
    response_model=DatosFacturacion,
    status_code=status.HTTP_200_OK,
)
async def obtener_datos_facturacion(
    venta_id: int,
    session: SessionDeDependencia,
    token: Token_Dependencia,
):
    if token["id_rol"] not in (1, 2, 3):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo empleados y propietarios pueden consultar datos de facturación",
        )
    venta = session.get(Venta, venta_id)
    if venta is None or (
        (token["id_rol"] == 2 and venta.usuario_id != token["id"])
        or (
            token["id_rol"] == 3
            and venta.cliente_usuario_id != token["id"]
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Venta no encontrada",
        )
    datos = session.exec(
        select(DatosFacturacion).where(DatosFacturacion.venta_id == venta_id)
    ).first()
    if datos is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay datos de facturación para esta venta",
        )
    return datos
