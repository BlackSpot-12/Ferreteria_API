from contextlib import asynccontextmanager

from fastapi import FastAPI

from config.db import crear_db_y_tablas
from config.segurity import validate_token_config
from routers.auth_router import router as auth_router
from routers.categoria_router import router as categoria_router
from routers.datos_facturacion_router import router as datos_facturacion_router
from routers.detalle_pedido_router import router as detalle_pedido_router
from routers.detalle_venta_router import router as detalle_venta_router
from routers.pedido_router import router as pedido_router
from routers.producto_router import router as producto_router
from routers.rol_router import router as rol_router
from routers.ubicacion_router import router as ubicacion_router
from routers.usuario_router import router as usuario_router
from routers.venta_router import router as venta_router

import models.categoria
import models.datos_facturacion
import models.detalle_pedido
import models.detalle_venta
import models.pedido
import models.producto
import models.rol
import models.ubicacion
import models.usuario
import models.venta


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_token_config()
    crear_db_y_tablas()
    yield


app = FastAPI(title="API Ferretería", lifespan=lifespan)

app.include_router(auth_router, tags=["Autenticación"])
app.include_router(usuario_router, tags=["Usuarios"])
app.include_router(categoria_router, tags=["Categorías"])
app.include_router(ubicacion_router, tags=["Ubicaciones"])
app.include_router(producto_router, tags=["Productos"])
app.include_router(rol_router, tags=["Roles"])
app.include_router(venta_router, tags=["Ventas"])
app.include_router(detalle_venta_router, tags=["Detalle Venta"])
app.include_router(datos_facturacion_router, tags=["Datos de Facturación"])
app.include_router(pedido_router, tags=["Pedidos"])
app.include_router(detalle_pedido_router, tags=["Detalle Pedido"])
