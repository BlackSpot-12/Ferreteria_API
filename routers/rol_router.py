from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from config.segurity_Dependencia import Token_Dependencia
from config.session_Dependencia import SessionDeDependencia
from models.rol import Rol, RolCreate, RolUpdate

router = APIRouter()

@router.get("/roles", response_model=list[Rol], status_code=status.HTTP_200_OK)
async def listar_roles(session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] != 1:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el propietario puede consultar roles")
    return session.exec(select(Rol).order_by(Rol.id_rol)).all()

@router.get("/roles/{rol_id}", response_model=Rol, status_code=status.HTTP_200_OK)
async def obtener_rol(rol_id: int, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] != 1:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el propietario puede consultar roles")
    rol = session.get(Rol, rol_id)
    if not rol:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rol no encontrado")
    return rol

@router.post("/roles", response_model=Rol, status_code=status.HTTP_201_CREATED)
async def crear_rol(payload: RolCreate, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] != 1:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el propietario puede crear roles")
    if session.exec(select(Rol).where(Rol.nombre == payload.nombre)).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El rol ya existe")
    rol = Rol(**payload.model_dump())
    session.add(rol)
    session.commit()
    session.refresh(rol)
    return rol

@router.put("/roles/{rol_id}", response_model=Rol, status_code=status.HTTP_200_OK)
async def actualizar_rol(rol_id: int, payload: RolUpdate, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] != 1:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el propietario puede actualizar roles")
    rol = session.get(Rol, rol_id)
    if not rol:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rol no encontrado")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(rol, key, value)
    session.add(rol)
    session.commit()
    session.refresh(rol)
    return rol

@router.delete("/roles/{rol_id}", status_code=status.HTTP_200_OK)
async def eliminar_rol(rol_id: int, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] != 1:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el propietario puede eliminar roles")
    rol = session.get(Rol, rol_id)
    if not rol:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rol no encontrado")
    session.delete(rol)
    session.commit()
    return {"detail": "Rol eliminado"}
