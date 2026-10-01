from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from config.segurity_Dependencia import Token_Dependencia
from config.session_Dependencia import SessionDeDependencia
from models.detalle_pedido import DetallePedido, DetallePedidoCreate, DetallePedidoUpdate

router = APIRouter()

@router.get("/detalles-pedido", response_model=list[DetallePedido], status_code=status.HTTP_200_OK)
async def listar_detalles_pedido(session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2, 3):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para consultar detalles de pedido")
    return session.exec(select(DetallePedido).order_by(DetallePedido.id_detalle_pedido)).all()

@router.post("/detalles-pedido", response_model=DetallePedido, status_code=status.HTTP_201_CREATED)
async def crear_detalle_pedido(payload: DetallePedidoCreate, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2, 3):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para crear detalles de pedido")
    detalle = DetallePedido(**payload.model_dump())
    session.add(detalle)
    session.commit()
    session.refresh(detalle)
    return detalle

@router.put("/detalles-pedido/{detalle_id}", response_model=DetallePedido, status_code=status.HTTP_200_OK)
async def actualizar_detalle_pedido(detalle_id: int, payload: DetallePedidoUpdate, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para editar detalle de pedido")
    detalle = session.get(DetallePedido, detalle_id)
    if not detalle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detalle de pedido no encontrado")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(detalle, key, value)
    session.add(detalle)
    session.commit()
    session.refresh(detalle)
    return detalle

@router.delete("/detalles-pedido/{detalle_id}", status_code=status.HTTP_200_OK)
async def eliminar_detalle_pedido(detalle_id: int, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para eliminar detalle de pedido")
    detalle = session.get(DetallePedido, detalle_id)
    if not detalle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detalle de pedido no encontrado")
    session.delete(detalle)
    session.commit()
    return {"detail": "Detalle de pedido eliminado"}
