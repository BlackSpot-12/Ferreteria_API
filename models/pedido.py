from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
from decimal import Decimal
import enum


class EstadoPedido(str, enum.Enum):
    PENDIENTE = "Pendiente"
    EN_PREPARACION = "En preparacion"
    LISTO = "Listo"
    ENTREGADO = "Entregado"


class Pedido(SQLModel, table=True):
    __tablename__ = "pedidos"
    id_pedido: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(nullable=False, foreign_key="usuarios.id")
    fecha_hora: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))
    estado: EstadoPedido = Field(default=EstadoPedido.PENDIENTE)
    total_pedido: Decimal = Field(default=0, max_digits=10, decimal_places=2)


class DetallePedido(SQLModel, table=True):
    __tablename__ = "detalles_pedidos"
    id_detalle_pedido: Optional[int] = Field(default=None, primary_key=True)
    pedido_id: int = Field(nullable=False, foreign_key="pedidos.id_pedido")
    producto_id: int = Field(
        nullable=False, foreign_key="productos.id_producto")
    cantidad: int = Field(nullable=False)
    precio_unitario: Decimal = Field(
        nullable=False, max_digits=10, decimal_places=2)
    subtotal: Decimal = Field(nullable=False, max_digits=10, decimal_places=2)
