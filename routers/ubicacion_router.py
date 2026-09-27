from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from models.ubicacion import Ubicacion
from config.db import get_session

router = APIRouter(prefix="/ubicaciones", tags=["Ubicaciones"])


@router.post("/", response_model=Ubicacion)
def crear_ubicacion(ubicacion: Ubicacion, db: Session = Depends(get_session)):
    db.add(ubicacion)
    db.commit()
    db.refresh(ubicacion)
    return ubicacion


@router.get("/", response_model=list[Ubicacion])
def obtener_ubicaciones(db: Session = Depends(get_session)):
    ubicaciones = db.exec(select(Ubicacion)).all()
    return ubicaciones


@router.put("/{id}", response_model=Ubicacion)
def actualizar_ubicacion(id: int, ubicacion_actualizada: Ubicacion, db: Session = Depends(get_session)):
    ubicacion_db = db.get(Ubicacion, id)
    if not ubicacion_db:
        raise HTTPException(status_code=404, detail="Ubicación no encontrada")

    ubicacion_db.pasillo = ubicacion_actualizada.pasillo
    ubicacion_db.estanteria = ubicacion_actualizada.estanteria

    db.add(ubicacion_db)
    db.commit()
    db.refresh(ubicacion_db)
    return ubicacion_db


@router.delete("/{id}")
def eliminar_ubicacion(id: int, db: Session = Depends(get_session)):
    ubicacion_db = db.get(Ubicacion, id)
    if not ubicacion_db:
        raise HTTPException(status_code=404, detail="Ubicación no encontrada")

    db.delete(ubicacion_db)
    db.commit()
    return {"mensaje": "Ubicación eliminada exitosamente"}
