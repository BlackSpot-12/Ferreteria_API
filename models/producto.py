from sqlmodel import SQLModel, Field
from typing import Optional
from decimal import Decimal


class Producto(SQLModel, table=True):
    __tablename__ = "productos"
    id_producto: Optional[int] = Field(default=None, primary_key=True)
    codigo: str = Field(nullable=False, max_length=50, unique=True)
    nombre: str = Field(nullable=False, max_length=150)
    marca: str = Field(nullable=False, max_length=100)
    descripcion: str = Field(nullable=False)
    medida_presentacion: str = Field(nullable=False, max_length=100)
    precio_compra: Decimal = Field(default=0, max_digits=10, decimal_places=2)
    precio_venta: Decimal = Field(default=0, max_digits=10, decimal_places=2)
    stock_actual: int = Field(default=0)
    stock_minimo: int = Field(default=0)
    estado: bool = Field(default=True)
    fotografia_url: Optional[str] = Field(default=None)

    categoria_id: int = Field(nullable=False, foreign_key="categorias.id")
    ubicacion_id: int = Field(nullable=False, foreign_key="ubicaciones.id")
