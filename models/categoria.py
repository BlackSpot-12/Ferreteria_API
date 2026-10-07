from typing import Optional

from sqlmodel import Field, SQLModel


class Categoria(SQLModel, table=True):
    __tablename__ = "Categoria"
    id_categoria: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(nullable=False, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=255)


class CategoriaCreate(SQLModel):
    nombre: str = Field(nullable=False, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=255)


class CategoriaUpdate(SQLModel):
    nombre: Optional[str] = Field(default=None, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=255)
