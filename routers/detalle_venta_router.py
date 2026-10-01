from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from config.segurity_Dependencia import Token_Dependencia
from config.session_Dependencia import SessionDeDependencia
from models.detalle_venta import DetalleVenta, DetalleVentaCreate, DetalleVentaUpdate

router = APIRouter()

@router.get("/detalles-venta", response_model=list[DetalleVenta], status_code=status.HTTP_200_OK)
async def listar_detalles_venta(session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para consultar detalles de venta")
    return session.exec(select(DetalleVenta).order_by(DetalleVenta.id_detalle_venta)).all()

@router.post("/detalles-venta", response_model=DetalleVenta, status_code=status.HTTP_201_CREATED)
async def crear_detalle_venta(payload: DetalleVentaCreate, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para crear detalle de venta")
    detalle = DetalleVenta(**payload.model_dump())
    session.add(detalle)
    session.commit()
    session.refresh(detalle)
    return detalle

@router.put("/detalles-venta/{detalle_id}", response_model=DetalleVenta, status_code=status.HTTP_200_OK)
async def actualizar_detalle_venta(detalle_id: int, payload: DetalleVentaUpdate, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para editar detalle de venta")
    detalle = session.get(DetalleVenta, detalle_id)
    if not detalle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detalle de venta no encontrado")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(detalle, key, value)
    session.add(detalle)
    session.commit()
    session.refresh(detalle)
    return detalle

@router.delete("/detalles-venta/{detalle_id}", status_code=status.HTTP_200_OK)
async def eliminar_detalle_venta(detalle_id: int, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para eliminar detalle de venta")
    detalle = session.get(DetalleVenta, detalle_id)
    if not detalle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detalle de venta no encontrado")
    session.delete(detalle)
    session.commit()
    return {"detail": "Detalle de venta eliminado"}
