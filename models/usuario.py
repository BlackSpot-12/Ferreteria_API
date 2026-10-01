from typing import Optional

from pydantic import EmailStr
from sqlmodel import Field, SQLModel


class Usuario(SQLModel, table=True):
    __tablename__ = "Usuario"
    id_usuario: Optional[int] = Field(default=None, primary_key=True)
    Nombres: str = Field(nullable=False, max_length=100)
    apellidos: str = Field(nullable=False, max_length=100)
    correo: EmailStr = Field(nullable=False, unique=True, max_length=150)
    password_hash: str = Field(nullable=False, max_length=255)
    rol_id: int = Field(nullable=False, foreign_key="rol.id_rol")


class UsuarioCreate(SQLModel):
    Nombres: str = Field(nullable=False, max_length=100)
    apellidos: str = Field(nullable=False, max_length=100)
    correo: EmailStr = Field(nullable=False, max_length=150)
    password: str = Field(nullable=False, max_length=255)
    rol_id: int = Field(nullable=False)


class UsuarioRegistroCliente(SQLModel):
    Nombres: str = Field(nullable=False, max_length=100)
    apellidos: str = Field(nullable=False, max_length=100)
    correo: EmailStr = Field(nullable=False, max_length=150)
    password: str = Field(nullable=False, max_length=255)


class UsuarioResponse(SQLModel):
    id_usuario: int
    Nombres: str
    apellidos: str
    correo: EmailStr
    rol_id: int
