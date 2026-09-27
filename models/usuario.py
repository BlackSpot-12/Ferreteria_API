from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
from pydantic import EmailStr


class RolBase(SQLModel):
    nombre: str = Field(nullable=False, max_length=50, unique=True)


class Rol(RolBase, table=True):
    __tablename__ = "roles"
    id: Optional[int] = Field(default=None, primary_key=True)


class UsuarioBase(SQLModel):
    username: str = Field(nullable=False, max_length=50, unique=True)
    nombre: str = Field(nullable=False, max_length=255)
    apellido: str = Field(nullable=False, max_length=255)
    telefono: str = Field(nullable=False, max_length=15)
    correo: EmailStr = Field(nullable=False, unique=True, max_length=255)
    id_rol: int = Field(nullable=False, foreign_key="roles.id")


class Usuario(UsuarioBase, table=True):
    __tablename__ = "usuarios"
    id: Optional[int] = Field(default=None, primary_key=True)
    password: str = Field(nullable=False, max_length=255)
    # Aquí aplicamos la corrección de la zona horaria
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc))
    estado: bool = Field(default=True)


class UsuarioCreate(UsuarioBase):
    password: str


class UsuarioRegistroCliente(SQLModel):
    username: str
    password: str
    nombre: str
    apellido: str
    telefono: str
    correo: EmailStr


class UsuarioResponse(UsuarioBase):
    id: int
    estado: bool
