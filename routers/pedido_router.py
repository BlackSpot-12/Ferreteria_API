from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from config.segurity_Dependencia import Token_Dependencia
from config.session_Dependencia import SessionDeDependencia
from models.pedido import Pedido, PedidoCreate, PedidoUpdate

router = APIRouter()

@router.get("/pedidos", response_model=list[Pedido], status_code=status.HTTP_200_OK)
async def listar_pedidos(session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2, 3):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para consultar pedidos")
    return session.exec(select(Pedido).order_by(Pedido.id_pedido)).all()

@router.get("/pedidos/{pedido_id}", response_model=Pedido, status_code=status.HTTP_200_OK)
async def obtener_pedido(pedido_id: int, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2, 3):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para consultar pedidos")
    pedido = session.get(Pedido, pedido_id)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")
    return pedido

@router.post("/pedidos", response_model=Pedido, status_code=status.HTTP_201_CREATED)
async def crear_pedido(payload: PedidoCreate, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2, 3):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para crear pedidos")
    pedido = Pedido(**payload.model_dump())
    session.add(pedido)
    session.commit()
    session.refresh(pedido)
    return pedido

@router.put("/pedidos/{pedido_id}", response_model=Pedido, status_code=status.HTTP_200_OK)
async def actualizar_pedido(pedido_id: int, payload: PedidoUpdate, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para editar pedidos")
    pedido = session.get(Pedido, pedido_id)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(pedido, key, value)
    session.add(pedido)
    session.commit()
    session.refresh(pedido)
    return pedido

@router.delete("/pedidos/{pedido_id}", status_code=status.HTTP_200_OK)
async def eliminar_pedido(pedido_id: int, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para eliminar pedidos")
    pedido = session.get(Pedido, pedido_id)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")
    session.delete(pedido)
    session.commit()
    return {"detail": "Pedido eliminado"}
