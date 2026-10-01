from decimal import Decimal
from typing import Optional

from sqlmodel import Field, SQLModel


class DetallePedido(SQLModel, table=True):
    __tablename__ = "detalle_pedido"
    id_detalle_pedido: Optional[int] = Field(default=None, primary_key=True)
    pedido_id: int = Field(nullable=False, foreign_key="pedido.id_pedido")
    producto_id: int = Field(nullable=False, foreign_key="Producto.id_producto")
    cantidad: int = Field(nullable=False)
    precio_unitario: Decimal = Field(nullable=False, max_digits=10, decimal_places=2)
    subtotal: Decimal = Field(nullable=False, max_digits=10, decimal_places=2)


class DetallePedidoCreate(SQLModel):
    pedido_id: int = Field(nullable=False)
    producto_id: int = Field(nullable=False)
    cantidad: int = Field(nullable=False)
    precio_unitario: Decimal = Field(nullable=False, max_digits=10, decimal_places=2)
    subtotal: Decimal = Field(nullable=False, max_digits=10, decimal_places=2)


class DetallePedidoUpdate(SQLModel):
    pedido_id: Optional[int] = Field(default=None)
    producto_id: Optional[int] = Field(default=None)
    cantidad: Optional[int] = Field(default=None)
    precio_unitario: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=2)
    subtotal: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=2)
