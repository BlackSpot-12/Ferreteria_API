from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlmodel import Field, SQLModel


class Venta(SQLModel, table=True):
    __tablename__ = "venta"
    id_venta: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(nullable=False, foreign_key="Usuario.id_usuario")
    fecha_hora: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    subtotal: Decimal = Field(nullable=False, max_digits=10, decimal_places=2)
    iva: Decimal = Field(nullable=False, max_digits=10, decimal_places=2)
    total_pagar: Decimal = Field(nullable=False, max_digits=10, decimal_places=2)


class VentaCreate(SQLModel):
    usuario_id: int = Field(nullable=False)
    subtotal: Decimal = Field(nullable=False, max_digits=10, decimal_places=2)
    iva: Decimal = Field(nullable=False, max_digits=10, decimal_places=2)
    total_pagar: Decimal = Field(nullable=False, max_digits=10, decimal_places=2)


class VentaUpdate(SQLModel):
    usuario_id: Optional[int] = Field(default=None)
    subtotal: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=2)
    iva: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=2)
    total_pagar: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=2)
