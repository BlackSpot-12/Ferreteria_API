from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal, Optional

from pydantic import ConfigDict, EmailStr, model_validator
from sqlmodel import Field, SQLModel


class Venta(SQLModel, table=True):
    __tablename__ = "venta"
    id_venta: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(nullable=False, foreign_key="Usuario.id_usuario")
    cliente_usuario_id: Optional[int] = Field(
        default=None,
        foreign_key="Usuario.id_usuario",
    )
    fecha_hora: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    canal: str = Field(default="POS", max_length=20)
    pedido_id: Optional[int] = Field(
        default=None,
        foreign_key="pedido.id_pedido",
        unique=True,
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
    correo: EmailStr
    telefono: str = Field(min_length=7, max_length=30)
    direccion: str = Field(min_length=1, max_length=255)
    metodo_pago: Literal["Efectivo", "Tarjeta", "Transferencia"]
    referencia_pago: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def validar_referencia(self):
        if self.referencia_pago is not None:
            self.referencia_pago = self.referencia_pago.strip()
            if not self.referencia_pago:
                raise ValueError("referencia_pago no puede estar vacía")
            if self.metodo_pago == "Efectivo":
                raise ValueError("referencia_pago solo aplica a pagos no monetarios")
        return self


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
    correo: str
    telefono: str
    direccion: str
    metodo_pago: str
    detalles: list[VentaDetalleResponse]
    subtotal: Decimal
    iva_porcentaje: Decimal
    iva: Decimal
    total_pagar: Decimal
