from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal, Optional

from pydantic import EmailStr
from pydantic import ConfigDict
from sqlmodel import Field, SQLModel


EstadoPedido = Literal["Pendiente", "En preparacion", "Listo", "Entregado"]


class Pedido(SQLModel, table=True):
    __tablename__ = "pedido"
    id_pedido: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: Optional[int] = Field(
        default=None,
        nullable=True,
        foreign_key="Usuario.id_usuario",
    )
    fecha_hora: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    estado: str = Field(default="Pendiente", max_length=30)
    total_pedido: Decimal = Field(nullable=False, max_digits=10, decimal_places=2)
    nombre_cliente: str = Field(nullable=False, max_length=150)
    correo_cliente: str = Field(nullable=False, max_length=150)
    telefono_cliente: str = Field(nullable=False, max_length=30)
    tipo_cliente: str = Field(default="Natural", max_length=20)
    numero_documento: str = Field(nullable=False, max_length=50)
    direccion_cliente: str = Field(nullable=False, max_length=255)
    codigo_acceso_hash: Optional[str] = Field(default=None, max_length=64)
    venta_id: Optional[int] = Field(default=None)


class PedidoItemCreate(SQLModel):
    model_config = ConfigDict(extra="forbid")

    producto_id: int = Field(gt=0)
    cantidad: int = Field(gt=0)


class PedidoCreate(SQLModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PedidoItemCreate] = Field(min_length=1, max_length=100)
    datos_cliente: DatosPedidoCreate


class DatosPedidoCreate(SQLModel):
    tipo_cliente: Literal["Natural", "Juridico"]
    nombre_razon_social: str = Field(min_length=1, max_length=150)
    correo: EmailStr
    telefono: str = Field(min_length=7, max_length=30)
    numero_documento: str = Field(min_length=1, max_length=50)
    direccion: str = Field(min_length=1, max_length=255)


class PedidoInvitadoCreate(SQLModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PedidoItemCreate] = Field(min_length=1, max_length=100)
    datos_cliente: DatosPedidoCreate


class PedidoUpdate(SQLModel):
    model_config = ConfigDict(extra="forbid")

    estado: EstadoPedido


class PedidoResponse(SQLModel):
    id_pedido: int
    usuario_id: Optional[int]
    fecha_hora: datetime
    estado: str
    total_pedido: Decimal
    nombre_cliente: str
    correo_cliente: str
    telefono_cliente: str
    tipo_cliente: str
    numero_documento: str
    direccion_cliente: str
    venta_id: Optional[int] = None
    prioridad_mayorista: bool = False
    compras_12_meses: Decimal = Decimal("0.00")
    detalles: Optional[list["PedidoDetalleResponse"]] = None


class PedidoInvitadoResponse(SQLModel):
    pedido: PedidoResponse
    codigo_acceso: str
    instrucciones: str
    detalles: list["PedidoDetalleResponse"]


class PedidoConsultaResponse(SQLModel):
    pedido: PedidoResponse
    detalles: list["PedidoDetalleResponse"]
    iva_estimado: Decimal
    total_estimado: Decimal
    venta_id: Optional[int] = None


class PagoPedidoCreate(SQLModel):
    model_config = ConfigDict(extra="forbid")

    metodo_pago: Literal["Efectivo", "Tarjeta", "Transferencia"]


class PedidoDetalleResponse(SQLModel):
    id_detalle_pedido: int
    pedido_id: int
    producto_id: int
    producto_nombre: str
    producto_codigo: str
    cantidad: int
    precio_unitario: Decimal
    subtotal: Decimal
