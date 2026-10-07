from decimal import Decimal
from typing import Optional

from sqlmodel import Field, SQLModel


class DetalleVenta(SQLModel, table=True):
    __tablename__ = "detalle_venta"
    id_detalle_venta: Optional[int] = Field(default=None, primary_key=True)
    venta_id: int = Field(nullable=False, foreign_key="venta.id_venta")
    producto_id: int = Field(nullable=False, foreign_key="Producto.id_producto")
    cantidad_id: int = Field(nullable=False)
    precio_unitario: Decimal = Field(nullable=False, max_digits=10, decimal_places=2)
    descuento: Decimal = Field(default=0.00, nullable=False, max_digits=10, decimal_places=2)
    subtotal: Decimal = Field(nullable=False, max_digits=10, decimal_places=2)


class DetalleVentaCreate(SQLModel):
    venta_id: int = Field(nullable=False)
    producto_id: int = Field(nullable=False)
    cantidad_id: int = Field(nullable=False)
    precio_unitario: Decimal = Field(nullable=False, max_digits=10, decimal_places=2)
    descuento: Decimal = Field(default=0.00, nullable=False, max_digits=10, decimal_places=2)
    subtotal: Decimal = Field(nullable=False, max_digits=10, decimal_places=2)


class DetalleVentaUpdate(SQLModel):
    venta_id: Optional[int] = Field(default=None)
    producto_id: Optional[int] = Field(default=None)
    cantidad_id: Optional[int] = Field(default=None)
    precio_unitario: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=2)
    descuento: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=2)
    subtotal: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=2)
