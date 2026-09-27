from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import Optional
from models.producto import Producto
from config.db import get_session

router = APIRouter(prefix="/productos", tags=["Productos"])


@router.get("/alertas/bajo-stock", response_model=list[Producto])
def alertas_stock(db: Session = Depends(get_session)):
    query = select(Producto).where(
        Producto.stock_actual <= Producto.stock_minimo)
    return db.exec(query).all()


@router.get("/buscar", response_model=list[Producto])
def buscar_productos(
    codigo: Optional[str] = None,
    nombre: Optional[str] = None,
    marca: Optional[str] = None,
    categoria_id: Optional[int] = None,
    medida: Optional[str] = None,
    db: Session = Depends(get_session)
):
    query = select(Producto)

    if codigo:
        query = query.where(Producto.codigo.contains(codigo))
    if nombre:
        query = query.where(Producto.nombre.contains(nombre))
    if marca:
        query = query.where(Producto.marca.contains(marca))
    if categoria_id:
        query = query.where(Producto.categoria_id == categoria_id)
    if medida:
        query = query.where(Producto.medida_presentacion.contains(medida))

    resultados = db.exec(query).all()
    return resultados


@router.post("/", response_model=Producto)
def crear_producto(producto: Producto, db: Session = Depends(get_session)):
    db.add(producto)
    db.commit()
    db.refresh(producto)
    return producto


@router.get("/", response_model=list[Producto])
def obtener_productos(db: Session = Depends(get_session)):
    productos = db.exec(select(Producto)).all()
    return productos


@router.put("/{id}", response_model=Producto)
def actualizar_producto(id: int, producto_actualizado: Producto, db: Session = Depends(get_session)):
    producto_db = db.get(Producto, id)
    if not producto_db:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    producto_db.codigo = producto_actualizado.codigo
    producto_db.nombre = producto_actualizado.nombre
    producto_db.marca = producto_actualizado.marca
    producto_db.descripcion = producto_actualizado.descripcion
    producto_db.medida_presentacion = producto_actualizado.medida_presentacion
    producto_db.precio_compra = producto_actualizado.precio_compra
    producto_db.precio_venta = producto_actualizado.precio_venta
    producto_db.stock_actual = producto_actualizado.stock_actual
    producto_db.stock_minimo = producto_actualizado.stock_minimo
    producto_db.estado = producto_actualizado.estado
    producto_db.fotografia_url = producto_actualizado.fotografia_url
    producto_db.categoria_id = producto_actualizado.categoria_id
    producto_db.ubicacion_id = producto_actualizado.ubicacion_id

    db.add(producto_db)
    db.commit()
    db.refresh(producto_db)
    return producto_db


@router.delete("/{id}")
def eliminar_producto(id: int, db: Session = Depends(get_session)):
    producto_db = db.get(Producto, id)
    if not producto_db:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    db.delete(producto_db)
    db.commit()
    return {"mensaje": "Producto eliminado exitosamente"}
