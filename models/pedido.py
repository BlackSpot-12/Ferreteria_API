from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal, Optional

from pydantic import ConfigDict
from sqlmodel import Field, SQLModel


EstadoPedido = Literal["Pendiente", "En preparacion", "Listo", "Entregado"]


class Pedido(SQLModel, table=True):
    __tablename__ = "pedido"
    id_pedido: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(nullable=False, foreign_key="Usuario.id_usuario")
    fecha_hora: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    estado: str = Field(default="Pendiente", max_length=30)
    total_pedido: Decimal = Field(nullable=False, max_digits=10, decimal_places=2)


class PedidoItemCreate(SQLModel):
    model_config = ConfigDict(extra="forbid")

    producto_id: int = Field(gt=0)
    cantidad: int = Field(gt=0)


class PedidoCreate(SQLModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PedidoItemCreate] = Field(min_length=1, max_length=100)


class PedidoUpdate(SQLModel):
    model_config = ConfigDict(extra="forbid")

    estado: EstadoPedido


class PedidoDetalleResponse(SQLModel):
    id_detalle_pedido: int
    pedido_id: int
    producto_id: int
    cantidad: int
    precio_unitario: Decimal
    subtotal: Decimal
