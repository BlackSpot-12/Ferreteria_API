from decimal import Decimal
from typing import Optional

from sqlmodel import Field, SQLModel


class ConfiguracionNegocio(SQLModel, table=True):
    __tablename__ = "configuracion_negocio"
    id_configuracion: Optional[int] = Field(default=None, primary_key=True)
    umbral_mayorista: Optional[Decimal] = Field(
        default=None,
        nullable=True,
        max_digits=12,
        decimal_places=2,
    )


class ConfiguracionMayoristaUpdate(SQLModel):
    umbral_mayorista: Optional[Decimal] = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
    )
