from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal, Optional

from pydantic import ConfigDict
from sqlmodel import Field, SQLModel


class Venta(SQLModel, table=True):
    __tablename__ = "venta"
    id_venta: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(nullable=False, foreign_key="Usuario.id_usuario")
    fecha_hora: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
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


class VentaItemCreate(SQLModel):
    model_config = ConfigDict(extra="forbid")

    producto_id: int = Field(gt=0)
    cantidad: int = Field(gt=0)


class FacturaDatosCreate(SQLModel):
    model_config = ConfigDict(extra="forbid")

    tipo_cliente: Literal["Natural", "Juridico"]
    nombre_razon_social: str = Field(min_length=1, max_length=150)
    numero_documento: str = Field(min_length=1, max_length=50)


class VentaPOSCreate(SQLModel):
    model_config = ConfigDict(extra="forbid")

    items: list[VentaItemCreate] = Field(min_length=1, max_length=100)
    datos_facturacion: FacturaDatosCreate


class VentaDetalleResponse(SQLModel):
    producto_id: int
    codigo: str
    nombre: str
    cantidad: int
    precio_unitario: Decimal
    descuento: Decimal
    subtotal: Decimal


class VentaPOSResponse(SQLModel):
    id_venta: int
    usuario_id: int
    fecha_hora: datetime
    subtotal: Decimal
    iva: Decimal
    total_pagar: Decimal
    detalles: list[VentaDetalleResponse]


class FacturaEmisor(SQLModel):
    nombre: str
    identificacion: str
    direccion: str
    telefono: Optional[str] = None


class FacturaResponse(SQLModel):
    emisor: FacturaEmisor
    id_factura: int
    fecha_hora: datetime
    tipo_cliente: Literal["Natural", "Juridico"]
    nombre_razon_social: str
    numero_documento: str
    detalles: list[VentaDetalleResponse]
    subtotal: Decimal
    iva_porcentaje: Decimal
    iva: Decimal
    total_pagar: Decimal
