from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from config.segurity_Dependencia import Token_Dependencia
from config.session_Dependencia import SessionDeDependencia
from models.categoria import Categoria, CategoriaCreate, CategoriaUpdate

router = APIRouter()

@router.get("/categorias", response_model=list[Categoria], status_code=status.HTTP_200_OK)
async def listar_categorias(session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para consultar categor?as")
    return session.exec(select(Categoria).order_by(Categoria.id_categoria)).all()

@router.get("/categorias/{categoria_id}", response_model=Categoria, status_code=status.HTTP_200_OK)
async def obtener_categoria(categoria_id: int, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para ver categor?as")
    categoria = session.get(Categoria, categoria_id)
    if not categoria:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categor?a no encontrada")
    return categoria

@router.post("/categorias", response_model=Categoria, status_code=status.HTTP_201_CREATED)
async def crear_categoria(payload: CategoriaCreate, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para crear categor?as")
    if session.exec(select(Categoria).where(Categoria.nombre == payload.nombre)).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La categor?a ya existe")
    categoria = Categoria(**payload.model_dump())
    session.add(categoria)
    session.commit()
    session.refresh(categoria)
    return categoria

@router.put("/categorias/{categoria_id}", response_model=Categoria, status_code=status.HTTP_200_OK)
async def actualizar_categoria(categoria_id: int, payload: CategoriaUpdate, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para editar categor?as")
    categoria = session.get(Categoria, categoria_id)
    if not categoria:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categor?a no encontrada")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(categoria, key, value)
    session.add(categoria)
    session.commit()
    session.refresh(categoria)
    return categoria

@router.delete("/categorias/{categoria_id}", status_code=status.HTTP_200_OK)
async def eliminar_categoria(categoria_id: int, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para eliminar categor?as")
    categoria = session.get(Categoria, categoria_id)
    if not categoria:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categor?a no encontrada")
    session.delete(categoria)
    session.commit()
    return {"detail": "Categor?a eliminada"}
