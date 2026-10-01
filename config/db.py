import os

from dotenv import load_dotenv
from sqlmodel import SQLModel, create_engine

load_dotenv()

DATABASE_USER = os.getenv("DATABASE_USER", "root")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD", "")
DATABASE_HOST = os.getenv("DATABASE_HOST", "localhost")
DATABASE_PORT = os.getenv("DATABASE_PORT", "3306")
DATABASE_NAME = os.getenv("DATABASE_NAME", "ferreteria")

DATABASE_URL = (
    f"mysql+pymysql://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"
)

engine = create_engine(DATABASE_URL, echo=True, pool_pre_ping=True)


def crear_db_y_tablas():
    try:
        SQLModel.metadata.create_all(engine)
    except Exception as exc:
        raise RuntimeError(
            "No se pudo conectar a MySQL. Verifica que el servicio de MySQL esté activo, "
            "que la base 'ferreteria' exista y que los datos de .env sean correctos: "
            "DATABASE_HOST, DATABASE_PORT, DATABASE_USER, DATABASE_PASSWORD, DATABASE_NAME."
        ) from exc
