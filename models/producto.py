from decimal import Decimal
from typing import Optional

from sqlmodel import Field, SQLModel


class Producto(SQLModel, table=True):
    __tablename__ = "Producto"
    id_producto: Optional[int] = Field(default=None, primary_key=True)
    codigo: str = Field(nullable=False, max_length=50, unique=True)
    nombre: str = Field(nullable=False, max_length=100)
    marca: Optional[str] = Field(default=None, max_length=50)
    descripcion: Optional[str] = Field(default=None)
    medida_presentacion: Optional[str] = Field(default=None, max_length=50)
    precio_compra: Decimal = Field(nullable=False, max_digits=10, decimal_places=2)
    precio_venta: Decimal = Field(nullable=False, max_digits=10, decimal_places=2)
    stock_actual: int = Field(default=0, nullable=False)
    stock_minimo: int = Field(default=0, nullable=False)
    estado: bool = Field(default=True, nullable=False)
    fotografia_url: Optional[str] = Field(default=None, max_length=255)
    categoria_id: int = Field(nullable=False, foreign_key="Categoria.id_categoria")
    ubicacion_id: int = Field(nullable=False, foreign_key="Ubicacion.id_ubicacion")


class ProductoCreate(SQLModel):
    codigo: str = Field(nullable=False, max_length=50)
    nombre: str = Field(nullable=False, max_length=100)
    marca: Optional[str] = Field(default=None, max_length=50)
    descripcion: Optional[str] = Field(default=None)
    medida_presentacion: Optional[str] = Field(default=None, max_length=50)
    precio_compra: Decimal = Field(nullable=False, max_digits=10, decimal_places=2)
    precio_venta: Decimal = Field(nullable=False, max_digits=10, decimal_places=2)
    stock_actual: int = Field(default=0, nullable=False)
    stock_minimo: int = Field(default=0, nullable=False)
    estado: bool = Field(default=True, nullable=False)
    fotografia_url: Optional[str] = Field(default=None, max_length=255)
    categoria_id: int = Field(nullable=False)
    ubicacion_id: int = Field(nullable=False)


class ProductoUpdate(SQLModel):
    codigo: Optional[str] = Field(default=None, max_length=50)
    nombre: Optional[str] = Field(default=None, max_length=100)
    marca: Optional[str] = Field(default=None, max_length=50)
    descripcion: Optional[str] = Field(default=None)
    medida_presentacion: Optional[str] = Field(default=None, max_length=50)
    precio_compra: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=2)
    precio_venta: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=2)
    stock_actual: Optional[int] = Field(default=None)
    stock_minimo: Optional[int] = Field(default=None)
    estado: Optional[bool] = Field(default=None)
    fotografia_url: Optional[str] = Field(default=None, max_length=255)
    categoria_id: Optional[int] = Field(default=None)
    ubicacion_id: Optional[int] = Field(default=None)
