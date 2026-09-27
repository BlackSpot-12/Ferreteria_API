from sqlmodel import SQLModel, Field
from typing import Optional


class Ubicacion(SQLModel, table=True):
    __tablename__ = "ubicaciones"
    id: Optional[int] = Field(default=None, primary_key=True)
    pasillo: str = Field(nullable=False, max_length=50)
    estanteria: str = Field(nullable=False, max_length=50)
