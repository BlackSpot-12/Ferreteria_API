from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import select

from config.segurity_Dependencia import Token_Dependencia
from config.session_Dependencia import SessionDeDependencia
from models.categoria import Categoria
from models.producto import (
    Producto,
    ProductoBusquedaEmpleado,
    ProductoCatalogo,
    ProductoCreate,
    ProductoUpdate,
)
from models.ubicacion import Ubicacion

router = APIRouter()


def _consulta_busqueda(codigo, nombre, marca, categoria, medida):
    consulta = (
        select(Producto, Categoria, Ubicacion)
        .join(Categoria, Producto.categoria_id == Categoria.id_categoria)
        .join(Ubicacion, Producto.ubicacion_id == Ubicacion.id_ubicacion)
        .where(Producto.estado.is_(True))
    )
    if codigo:
        consulta = consulta.where(Producto.codigo.ilike(f"%{codigo.strip()}%"))
    if nombre:
        consulta = consulta.where(Producto.nombre.ilike(f"%{nombre.strip()}%"))
    if marca:
        consulta = consulta.where(Producto.marca.ilike(f"%{marca.strip()}%"))
    if categoria:
        consulta = consulta.where(Categoria.nombre.ilike(f"%{categoria.strip()}%"))
    if medida:
        consulta = consulta.where(
            Producto.medida_presentacion.ilike(f"%{medida.strip()}%")
        )
    return consulta.order_by(Producto.nombre, Producto.id_producto)


def _producto_empleado(producto, categoria, ubicacion):
    return ProductoBusquedaEmpleado(
        id_producto=producto.id_producto,
        codigo=producto.codigo,
        nombre=producto.nombre,
        marca=producto.marca,
        medida_presentacion=producto.medida_presentacion,
        precio_venta=producto.precio_venta,
        fotografia_url=producto.fotografia_url,
        stock_actual=producto.stock_actual,
        stock_minimo=producto.stock_minimo,
        categoria=categoria.nombre,
        pasillo=ubicacion.pasillo,
        estante=ubicacion.estante,
        nivel=ubicacion.nivel,
    )


@router.get(
    "/catalogo/productos",
    response_model=list[ProductoCatalogo],
    status_code=status.HTTP_200_OK,
)
async def buscar_catalogo_publico(
    session: SessionDeDependencia,
    codigo: str | None = Query(default=None, min_length=1, max_length=50),
    nombre: str | None = Query(default=None, min_length=1, max_length=100),
    marca: str | None = Query(default=None, min_length=1, max_length=50),
    categoria: str | None = Query(default=None, min_length=1, max_length=100),
    medida: str | None = Query(default=None, min_length=1, max_length=50),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    rows = session.exec(
        _consulta_busqueda(codigo, nombre, marca, categoria, medida)
        .offset(offset)
        .limit(limit)
    ).all()
    return [ProductoCatalogo.model_validate(row[0]) for row in rows]


@router.get(
    "/productos/buscar",
    response_model=list[ProductoBusquedaEmpleado],
    status_code=status.HTTP_200_OK,
)
async def buscar_productos_empleado(
    session: SessionDeDependencia,
    token: Token_Dependencia,
    codigo: str | None = Query(default=None, min_length=1, max_length=50),
    nombre: str | None = Query(default=None, min_length=1, max_length=100),
    marca: str | None = Query(default=None, min_length=1, max_length=50),
    categoria: str | None = Query(default=None, min_length=1, max_length=100),
    medida: str | None = Query(default=None, min_length=1, max_length=50),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo empleados y propietarios pueden consultar existencias y ubicaciones",
        )
    rows = session.exec(
        _consulta_busqueda(codigo, nombre, marca, categoria, medida)
        .offset(offset)
        .limit(limit)
    ).all()
    return [_producto_empleado(*row) for row in rows]


@router.get("/productos", response_model=list[Producto], status_code=status.HTTP_200_OK)
async def listar_productos(session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para consultar productos")
    return session.exec(select(Producto).order_by(Producto.id_producto)).all()

@router.get("/productos/{producto_id}", response_model=Producto, status_code=status.HTTP_200_OK)
async def obtener_producto(producto_id: int, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para consultar productos")
    producto = session.get(Producto, producto_id)
    if not producto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    return producto

@router.post("/productos", response_model=Producto, status_code=status.HTTP_201_CREATED)
async def crear_producto(payload: ProductoCreate, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para crear productos")
    if session.get(Categoria, payload.categoria_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La categor?a indicada no existe")
    if session.get(Ubicacion, payload.ubicacion_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La ubicaci?n indicada no existe")
    if session.exec(select(Producto).where(Producto.codigo == payload.codigo)).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El c?digo del producto ya existe")
    producto = Producto(**payload.model_dump())
    session.add(producto)
    session.commit()
    session.refresh(producto)
    return producto

@router.put("/productos/{producto_id}", response_model=Producto, status_code=status.HTTP_200_OK)
async def actualizar_producto(producto_id: int, payload: ProductoUpdate, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para editar productos")
    producto = session.get(Producto, producto_id)
    if not producto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    if payload.categoria_id is not None and session.get(Categoria, payload.categoria_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La categor?a indicada no existe")
    if payload.ubicacion_id is not None and session.get(Ubicacion, payload.ubicacion_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La ubicaci?n indicada no existe")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(producto, key, value)
    session.add(producto)
    session.commit()
    session.refresh(producto)
    return producto

@router.delete("/productos/{producto_id}", status_code=status.HTTP_200_OK)
async def eliminar_producto(producto_id: int, session: SessionDeDependencia, token: Token_Dependencia):
    if token["id_rol"] not in (1, 2):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para eliminar productos")
    producto = session.get(Producto, producto_id)
    if not producto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    session.delete(producto)
    session.commit()
    return {"detail": "Producto eliminado"}
