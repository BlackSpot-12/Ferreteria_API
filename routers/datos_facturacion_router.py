from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from config.segurity_Dependencia import Token_Dependencia
from config.session_Dependencia import SessionDeDependencia
from models.datos_facturacion import DatosFacturacion, DatosFacturacionCreate, DatosFacturacionUpdate

router = APIRouter()

@router.get("/datos-facturacion", response_model=list[DatosFacturacion], status_code=status.HTTP_200_OK)
async def listar_datos_facturacion(session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para consultar datos de facturaci?n")
    return session.exec(select(DatosFacturacion).order_by(DatosFacturacion.id_facturacion)).all()

@router.post("/datos-facturacion", response_model=DatosFacturacion, status_code=status.HTTP_201_CREATED)
async def crear_datos_facturacion(payload: DatosFacturacionCreate, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para crear datos de facturaci?n")
    dato = DatosFacturacion(**payload.model_dump())
    session.add(dato)
    session.commit()
    session.refresh(dato)
    return dato

@router.put("/datos-facturacion/{dato_id}", response_model=DatosFacturacion, status_code=status.HTTP_200_OK)
async def actualizar_datos_facturacion(dato_id: int, payload: DatosFacturacionUpdate, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para editar datos de facturaci?n")
    dato = session.get(DatosFacturacion, dato_id)
    if not dato:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dato de facturaci?n no encontrado")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(dato, key, value)
    session.add(dato)
    session.commit()
    session.refresh(dato)
    return dato

@router.delete("/datos-facturacion/{dato_id}", status_code=status.HTTP_200_OK)
async def eliminar_datos_facturacion(dato_id: int, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para eliminar datos de facturaci?n")
    dato = session.get(DatosFacturacion, dato_id)
    if not dato:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dato de facturaci?n no encontrado")
    session.delete(dato)
    session.commit()
    return {"detail": "Dato de facturaci?n eliminado"}
