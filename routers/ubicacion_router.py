from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from config.segurity_Dependencia import Token_Dependencia
from config.session_Dependencia import SessionDeDependencia
from models.ubicacion import Ubicacion, UbicacionCreate, UbicacionUpdate

router = APIRouter()

@router.get("/ubicaciones", response_model=list[Ubicacion], status_code=status.HTTP_200_OK)
async def listar_ubicaciones(session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para ver ubicaciones")
    return session.exec(select(Ubicacion).order_by(Ubicacion.id_ubicacion)).all()

@router.get("/ubicaciones/{ubicacion_id}", response_model=Ubicacion, status_code=status.HTTP_200_OK)
async def obtener_ubicacion(ubicacion_id: int, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para ver ubicaciones")
    ubicacion = session.get(Ubicacion, ubicacion_id)
    if not ubicacion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ubicaci?n no encontrada")
    return ubicacion

@router.post("/ubicaciones", response_model=Ubicacion, status_code=status.HTTP_201_CREATED)
async def crear_ubicacion(payload: UbicacionCreate, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para crear ubicaciones")
    ubicacion = Ubicacion(**payload.model_dump())
    session.add(ubicacion)
    session.commit()
    session.refresh(ubicacion)
    return ubicacion

@router.put("/ubicaciones/{ubicacion_id}", response_model=Ubicacion, status_code=status.HTTP_200_OK)
async def actualizar_ubicacion(ubicacion_id: int, payload: UbicacionUpdate, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para editar ubicaciones")
    ubicacion = session.get(Ubicacion, ubicacion_id)
    if not ubicacion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ubicaci?n no encontrada")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(ubicacion, key, value)
    session.add(ubicacion)
    session.commit()
    session.refresh(ubicacion)
    return ubicacion

@router.delete("/ubicaciones/{ubicacion_id}", status_code=status.HTTP_200_OK)
async def eliminar_ubicacion(ubicacion_id: int, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para eliminar ubicaciones")
    ubicacion = session.get(Ubicacion, ubicacion_id)
    if not ubicacion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ubicaci?n no encontrada")
    session.delete(ubicacion)
    session.commit()
    return {"detail": "Ubicaci?n eliminada"}
