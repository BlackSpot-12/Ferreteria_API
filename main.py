from fastapi import FastAPI
from contextlib import asynccontextmanager
from config.db import crear_db_y_tablas
from routers.auth_router import router as auth_router
from routers.usuario_router import router as usuario_router
import models.usuario
import models.categoria
import models.ubicacion
import models.producto
import models.venta
import models.pedido


@asynccontextmanager
async def lifespan(app: FastAPI):
    crear_db_y_tablas()
    yield

app = FastAPI(title="API Ferretería", lifespan=lifespan)

app.include_router(auth_router, tags=["Autenticación"])
app.include_router(usuario_router, tags=["Usuarios"])
