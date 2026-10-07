from typing import Optional

from sqlmodel import Field, SQLModel


class DatosFacturacion(SQLModel, table=True):
    __tablename__ = "datos_facturacion"
    id_facturacion: Optional[int] = Field(default=None, primary_key=True)
    venta_id: int = Field(nullable=False, foreign_key="venta.id_venta")
    tipo_cliente: str = Field(nullable=False, max_length=20)
    nombre_razon_social: str = Field(nullable=False, max_length=150)
    numero_documento: str = Field(nullable=False, max_length=50)


class DatosFacturacionCreate(SQLModel):
    venta_id: int = Field(nullable=False)
    tipo_cliente: str = Field(nullable=False, max_length=20)
    nombre_razon_social: str = Field(nullable=False, max_length=150)
    numero_documento: str = Field(nullable=False, max_length=50)


class DatosFacturacionUpdate(SQLModel):
    venta_id: Optional[int] = Field(default=None)
    tipo_cliente: Optional[str] = Field(default=None, max_length=20)
    nombre_razon_social: Optional[str] = Field(default=None, max_length=150)
    numero_documento: Optional[str] = Field(default=None, max_length=50)
