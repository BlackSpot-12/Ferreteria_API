from datetime import datetime, timezone
from typing import Optional

from pydantic import EmailStr
from sqlmodel import Field, SQLModel


class UserEmailVerification(SQLModel, table=True):
    __tablename__ = "user_email_verification"

    usuario_id: int = Field(primary_key=True, foreign_key="Usuario.id_usuario")
    verificado: bool = Field(default=False, nullable=False)
    verified_at: Optional[datetime] = Field(default=None)
    last_sent_at: Optional[datetime] = Field(default=None)


class EmailToken(SQLModel, table=True):
    __tablename__ = "email_token"

    id: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(nullable=False, foreign_key="Usuario.id_usuario")
    purpose: str = Field(nullable=False, max_length=32, index=True)
    token_hash: str = Field(nullable=False, max_length=64, unique=True, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    expires_at: datetime = Field(nullable=False)
    used_at: Optional[datetime] = Field(default=None)


class InvoiceEmailState(SQLModel, table=True):
    __tablename__ = "invoice_email_state"

    venta_id: int = Field(primary_key=True, foreign_key="venta.id_venta")
    automatic_attempted_at: Optional[datetime] = Field(default=None)
    automatic_sent_at: Optional[datetime] = Field(default=None)
    manual_resend_count: int = Field(default=0, nullable=False)
    manual_last_requested_at: Optional[datetime] = Field(default=None)
    last_delivery_succeeded: Optional[bool] = Field(default=None)


class InvoiceEmailAudit(SQLModel, table=True):
    __tablename__ = "invoice_email_audit"

    id: Optional[int] = Field(default=None, primary_key=True)
    venta_id: int = Field(nullable=False, foreign_key="venta.id_venta", index=True)
    requested_by: Optional[int] = Field(
        default=None,
        foreign_key="Usuario.id_usuario",
    )
    requested_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Optional[datetime] = Field(default=None)
    delivery_succeeded: Optional[bool] = Field(default=None)


class PasswordResetRequest(SQLModel):
    correo: EmailStr


class PasswordResetApply(SQLModel):
    token: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=255)


class EmailVerificationApply(SQLModel):
    token: str = Field(min_length=1, max_length=255)
