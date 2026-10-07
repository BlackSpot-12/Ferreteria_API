from typing import Optional

from sqlmodel import Field, SQLModel


class Rol(SQLModel, table=True):
    __tablename__ = "rol"
    id_rol: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(nullable=False, max_length=50, unique=True)
    descripcion: Optional[str] = Field(default=None, max_length=255)


class RolCreate(SQLModel):
    nombre: str = Field(nullable=False, max_length=50)
    descripcion: Optional[str] = Field(default=None, max_length=255)


class RolUpdate(SQLModel):
    nombre: Optional[str] = Field(default=None, max_length=50)
    descripcion: Optional[str] = Field(default=None, max_length=255)
