from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlmodel import Field, SQLModel


class Pedido(SQLModel, table=True):
    __tablename__ = "pedido"
    id_pedido: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(nullable=False, foreign_key="Usuario.id_usuario")
    fecha_hora: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    estado: str = Field(default="Pendiente", max_length=30)
    total_pedido: Decimal = Field(nullable=False, max_digits=10, decimal_places=2)


class PedidoCreate(SQLModel):
    usuario_id: int = Field(nullable=False)
    estado: str = Field(default="Pendiente", max_length=30)
    total_pedido: Decimal = Field(nullable=False, max_digits=10, decimal_places=2)


class PedidoUpdate(SQLModel):
    usuario_id: Optional[int] = Field(default=None)
    estado: Optional[str] = Field(default=None, max_length=30)
    total_pedido: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=2)
