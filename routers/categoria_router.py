from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from models.categoria import Categoria

from config.db import get_session

router = APIRouter(prefix="/categorias", tags=["Categorías"])


@router.post("/", response_model=Categoria)
def crear_categoria(categoria: Categoria, db: Session = Depends(get_session)):

    categoria_existente = db.exec(select(Categoria).where(
        Categoria.nombre == categoria.nombre)).first()
    if categoria_existente:
        raise HTTPException(status_code=400, detail="La categoría ya existe")

    db.add(categoria)
    db.commit()
    db.refresh(categoria)
    return categoria


@router.get("/", response_model=list[Categoria])
def obtener_categorias(db: Session = Depends(get_session)):
    categorias = db.exec(select(Categoria)).all()
    return categorias


@router.put("/{id}", response_model=Categoria)
def actualizar_categoria(id: int, categoria_actualizada: Categoria, db: Session = Depends(get_session)):
    categoria_db = db.get(Categoria, id)
    if not categoria_db:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")

    categoria_db.nombre = categoria_actualizada.nombre
    db.add(categoria_db)
    db.commit()
    db.refresh(categoria_db)
    return categoria_db


@router.delete("/{id}")
def eliminar_categoria(id: int, db: Session = Depends(get_session)):
    categoria_db = db.get(Categoria, id)
    if not categoria_db:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")

    db.delete(categoria_db)
    db.commit()
    return {"mensaje": "Categoría eliminada exitosamente"}
