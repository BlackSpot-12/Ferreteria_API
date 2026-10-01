from typing import Optional

from sqlmodel import Field, SQLModel


class Ubicacion(SQLModel, table=True):
    __tablename__ = "Ubicacion"
    id_ubicacion: Optional[int] = Field(default=None, primary_key=True)
    pasillo: str = Field(nullable=False, max_length=50)
    estante: str = Field(nullable=False, max_length=50)
    nivel: str = Field(nullable=False, max_length=50)


class UbicacionCreate(SQLModel):
    pasillo: str = Field(nullable=False, max_length=50)
    estante: str = Field(nullable=False, max_length=50)
    nivel: str = Field(nullable=False, max_length=50)


class UbicacionUpdate(SQLModel):
    pasillo: Optional[str] = Field(default=None, max_length=50)
    estante: Optional[str] = Field(default=None, max_length=50)
    nivel: Optional[str] = Field(default=None, max_length=50)
