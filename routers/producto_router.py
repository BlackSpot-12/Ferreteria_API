from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from config.segurity_Dependencia import Token_Dependencia
from config.session_Dependencia import SessionDeDependencia
from models.categoria import Categoria
from models.producto import Producto, ProductoCreate, ProductoUpdate
from models.ubicacion import Ubicacion

router = APIRouter()

@router.get("/productos", response_model=list[Producto], status_code=status.HTTP_200_OK)
async def listar_productos(session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para consultar productos")
    return session.exec(select(Producto).order_by(Producto.id_producto)).all()

@router.get("/productos/{producto_id}", response_model=Producto, status_code=status.HTTP_200_OK)
async def obtener_producto(producto_id: int, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para consultar productos")
    producto = session.get(Producto, producto_id)
    if not producto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    return producto

@router.post("/productos", response_model=Producto, status_code=status.HTTP_201_CREATED)
async def crear_producto(payload: ProductoCreate, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para crear productos")
    if session.get(Categoria, payload.categoria_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La categor?a indicada no existe")
    if session.get(Ubicacion, payload.ubicacion_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La ubicaci?n indicada no existe")
    if session.exec(select(Producto).where(Producto.codigo == payload.codigo)).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El c?digo del producto ya existe")
    producto = Producto(**payload.model_dump())
    session.add(producto)
    session.commit()
    session.refresh(producto)
    return producto

@router.put("/productos/{producto_id}", response_model=Producto, status_code=status.HTTP_200_OK)
async def actualizar_producto(producto_id: int, payload: ProductoUpdate, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para editar productos")
    producto = session.get(Producto, producto_id)
    if not producto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    if payload.categoria_id is not None and session.get(Categoria, payload.categoria_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La categor?a indicada no existe")
    if payload.ubicacion_id is not None and session.get(Ubicacion, payload.ubicacion_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La ubicaci?n indicada no existe")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(producto, key, value)
    session.add(producto)
    session.commit()
    session.refresh(producto)
    return producto

@router.delete("/productos/{producto_id}", status_code=status.HTTP_200_OK)
async def eliminar_producto(producto_id: int, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para eliminar productos")
    producto = session.get(Producto, producto_id)
    if not producto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    session.delete(producto)
    session.commit()
    return {"detail": "Producto eliminado"}
