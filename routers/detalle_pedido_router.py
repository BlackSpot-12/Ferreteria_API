from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from config.segurity_Dependencia import Token_Dependencia
from config.session_Dependencia import SessionDeDependencia
from models.detalle_pedido import DetallePedido
from models.pedido import Pedido, PedidoDetalleResponse

router = APIRouter()
ROLES_GESTION_PEDIDOS = (1, 2)


@router.get(
    "/detalles-pedido/{pedido_id}",
    response_model=list[PedidoDetalleResponse],
    status_code=status.HTTP_200_OK,
)
async def listar_detalles_pedido(
    pedido_id: int,
    session: SessionDeDependencia,
    token: Token_Dependencia,
):
    pedido = session.get(Pedido, pedido_id)
    if pedido is None or (
        token["id_rol"] == 3 and pedido.usuario_id != token["id"]
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido no encontrado",
        )
    if token["id_rol"] not in (*ROLES_GESTION_PEDIDOS, 3):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para consultar detalles de pedidos",
        )
    return session.exec(
        select(DetallePedido)
        .where(DetallePedido.pedido_id == pedido_id)
        .order_by(DetallePedido.id_detalle_pedido)
    ).all()
