from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlmodel import Field, SQLModel


class UserAccess(SQLModel, table=True):
    __tablename__ = "user_access"

    usuario_id: int = Field(
        primary_key=True,
        foreign_key="Usuario.id_usuario",
    )
    activo: bool = Field(default=True, nullable=False)
    token_version: int = Field(default=0, nullable=False)


class PaymentRecord(SQLModel, table=True):
    __tablename__ = "payment_record"

    id_pago: Optional[int] = Field(default=None, primary_key=True)
    venta_id: int = Field(
        nullable=False,
        unique=True,
        foreign_key="venta.id_venta",
    )
    usuario_id: int = Field(nullable=False, foreign_key="Usuario.id_usuario")
    metodo_pago: str = Field(nullable=False, max_length=20)
    referencia: Optional[str] = Field(default=None, max_length=100)
    monto: Decimal = Field(nullable=False, max_digits=10, decimal_places=2)
    fecha_hora: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class GuestOrderLookupLimit(SQLModel, table=True):
    __tablename__ = "guest_order_lookup_limit"

    ip_hash: str = Field(primary_key=True, max_length=64)
    window_started_at: datetime = Field(nullable=False)
    attempts: int = Field(default=0, nullable=False)
