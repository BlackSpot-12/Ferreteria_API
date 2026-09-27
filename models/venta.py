from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
from decimal import Decimal
import enum


class TipoCliente(str, enum.Enum):
    NATURAL = "Natural"
    JURIDICO = "Juridico"


class Venta(SQLModel, table=True):
    __tablename__ = "ventas"
    id_venta: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(nullable=False, foreign_key="usuarios.id")
    fecha_hora: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))
    subtotal: Decimal = Field(default=0, max_digits=10, decimal_places=2)
    iva: Decimal = Field(default=0, max_digits=10, decimal_places=2)
    total_pagar: Decimal = Field(default=0, max_digits=10, decimal_places=2)


class DetalleVenta(SQLModel, table=True):
    __tablename__ = "detalles_ventas"
    id_detalle_venta: Optional[int] = Field(default=None, primary_key=True)
    venta_id: int = Field(nullable=False, foreign_key="ventas.id_venta")
    producto_id: int = Field(
        nullable=False, foreign_key="productos.id_producto")
    cantidad: int = Field(nullable=False)
    precio_unitario: Decimal = Field(
        nullable=False, max_digits=10, decimal_places=2)
    descuento: Decimal = Field(default=0, max_digits=10, decimal_places=2)
    subtotal: Decimal = Field(nullable=False, max_digits=10, decimal_places=2)


class DatosFacturacion(SQLModel, table=True):
    __tablename__ = "datos_facturacion"
    id_facturacion: Optional[int] = Field(default=None, primary_key=True)
    venta_id: int = Field(nullable=False, foreign_key="ventas.id_venta")
    tipo_cliente: TipoCliente = Field(nullable=False)
    nombre_razon_social: str = Field(nullable=False, max_length=150)
    numero_documento: str = Field(nullable=False, max_length=50)
