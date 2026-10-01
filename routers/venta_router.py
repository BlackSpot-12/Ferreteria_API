from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from config.segurity_Dependencia import Token_Dependencia
from config.session_Dependencia import SessionDeDependencia
from models.venta import Venta, VentaCreate, VentaUpdate

router = APIRouter()

@router.get("/ventas", response_model=list[Venta], status_code=status.HTTP_200_OK)
async def listar_ventas(session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para consultar ventas")
    return session.exec(select(Venta).order_by(Venta.id_venta)).all()

@router.get("/ventas/{venta_id}", response_model=Venta, status_code=status.HTTP_200_OK)
async def obtener_venta(venta_id: int, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para consultar ventas")
    venta = session.get(Venta, venta_id)
    if not venta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada")
    return venta

@router.post("/ventas", response_model=Venta, status_code=status.HTTP_201_CREATED)
async def crear_venta(payload: VentaCreate, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para crear ventas")
    venta = Venta(**payload.model_dump())
    session.add(venta)
    session.commit()
    session.refresh(venta)
    return venta

@router.put("/ventas/{venta_id}", response_model=Venta, status_code=status.HTTP_200_OK)
async def actualizar_venta(venta_id: int, payload: VentaUpdate, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para editar ventas")
    venta = session.get(Venta, venta_id)
    if not venta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(venta, key, value)
    session.add(venta)
    session.commit()
    session.refresh(venta)
    return venta

@router.delete("/ventas/{venta_id}", status_code=status.HTTP_200_OK)
async def eliminar_venta(venta_id: int, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para eliminar ventas")
    venta = session.get(Venta, venta_id)
    if not venta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada")
    session.delete(venta)
    session.commit()
    return {"detail": "Venta eliminada"}
