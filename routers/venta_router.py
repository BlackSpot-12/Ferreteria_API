from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from pydantic import BaseModel
from typing import List
from datetime import datetime, timezone

from models.venta import Venta, DetalleVenta
from models.producto import Producto
from config.db import get_session

router = APIRouter(prefix="/ventas", tags=["Ventas y Facturación"])


class DetalleVentaRequest(BaseModel):
    producto_id: int
    cantidad: int
    precio_unitario: float
    descuento: float = 0.0
    subtotal: float


class VentaRequest(BaseModel):
    usuario_id: int
    subtotal: float
    iva: float
    total_pagar: float
    detalles: List[DetalleVentaRequest]


@router.post("/", response_model=Venta)
def crear_venta(venta_req: VentaRequest, db: Session = Depends(get_session)):
    try:

        nueva_venta = Venta(
            usuario_id=venta_req.usuario_id,
            fecha_hora=datetime.now(timezone.utc),
            subtotal=venta_req.subtotal,
            iva=venta_req.iva,
            total_pagar=venta_req.total_pagar
        )
        db.add(nueva_venta)
        db.flush()

        for item in venta_req.detalles:
            producto_db = db.get(Producto, item.producto_id)

            if not producto_db:
                raise HTTPException(
                    status_code=404, detail=f"El producto con ID {item.producto_id} no existe")

            if producto_db.stock_actual < item.cantidad:
                raise HTTPException(
                    status_code=400,
                    detail=f"Stock insuficiente para {producto_db.nombre}. Disponibles: {producto_db.stock_actual}"
                )

            producto_db.stock_actual -= item.cantidad
            db.add(producto_db)

            nuevo_detalle = DetalleVenta(
                venta_id=nueva_venta.id_venta,
                producto_id=item.producto_id,
                cantidad=item.cantidad,
                precio_unitario=item.precio_unitario,
                descuento=item.descuento,
                subtotal=item.subtotal
            )
            db.add(nuevo_detalle)

        db.commit()
        db.refresh(nueva_venta)
        return nueva_venta

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
