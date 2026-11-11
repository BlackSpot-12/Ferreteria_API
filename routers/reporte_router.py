from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlmodel import select

from config.segurity_Dependencia import Token_Dependencia
from config.session_Dependencia import SessionDeDependencia
from models.categoria import Categoria
from models.detalle_venta import DetalleVenta
from models.producto import Producto
from models.venta import Venta

router = APIRouter(prefix="/reportes", tags=["Reportes"])


def _require_owner(token: dict) -> None:
    if token.get("id_rol") != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el propietario puede consultar reportes administrativos",
        )


def _range_bounds(
    fecha_inicio: date | None,
    fecha_fin: date | None,
) -> tuple[date, date, datetime, datetime]:
    fin = fecha_fin or datetime.now(timezone.utc).date()
    inicio = fecha_inicio or fin - timedelta(days=29)
    if inicio > fin:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="fecha_inicio no puede ser posterior a fecha_fin",
        )
    inicio_dt = datetime.combine(inicio, time.min, tzinfo=timezone.utc)
    fin_exclusivo = datetime.combine(
        fin + timedelta(days=1),
        time.min,
        tzinfo=timezone.utc,
    )
    return inicio, fin, inicio_dt, fin_exclusivo


@router.get("/ventas")
async def reporte_ventas(
    session: SessionDeDependencia,
    token: Token_Dependencia,
    fecha_inicio: date | None = Query(default=None),
    fecha_fin: date | None = Query(default=None),
    productos_limit: int = Query(default=10, ge=1, le=50),
):
    _require_owner(token)
    inicio, fin, inicio_dt, fin_exclusivo = _range_bounds(
        fecha_inicio,
        fecha_fin,
    )

    totales = session.exec(
        select(
            func.count(Venta.id_venta),
            func.coalesce(func.sum(Venta.subtotal), 0),
            func.coalesce(func.sum(Venta.iva), 0),
            func.coalesce(func.sum(Venta.total_pagar), 0),
        ).where(
            Venta.fecha_hora >= inicio_dt,
            Venta.fecha_hora < fin_exclusivo,
        )
    ).one()

    ventas_por_dia = session.exec(
        select(
            func.date(Venta.fecha_hora),
            func.count(Venta.id_venta),
            func.coalesce(func.sum(Venta.total_pagar), 0),
        )
        .where(
            Venta.fecha_hora >= inicio_dt,
            Venta.fecha_hora < fin_exclusivo,
        )
        .group_by(func.date(Venta.fecha_hora))
        .order_by(func.date(Venta.fecha_hora))
    ).all()

    productos_mas_vendidos = session.exec(
        select(
            Producto.id_producto,
            Producto.codigo,
            Producto.nombre,
            func.coalesce(func.sum(DetalleVenta.cantidad_id), 0),
            func.coalesce(func.sum(DetalleVenta.subtotal), 0),
        )
        .join(DetalleVenta, DetalleVenta.producto_id == Producto.id_producto)
        .join(Venta, Venta.id_venta == DetalleVenta.venta_id)
        .where(
            Venta.fecha_hora >= inicio_dt,
            Venta.fecha_hora < fin_exclusivo,
        )
        .group_by(
            Producto.id_producto,
            Producto.codigo,
            Producto.nombre,
        )
        .order_by(func.sum(DetalleVenta.cantidad_id).desc(), Producto.nombre)
        .limit(productos_limit)
    ).all()

    return {
        "fecha_inicio": inicio,
        "fecha_fin": fin,
        "total_ventas": int(totales[0] or 0),
        "subtotal": Decimal(str(totales[1] or 0)),
        "iva": Decimal(str(totales[2] or 0)),
        "ingresos": Decimal(str(totales[3] or 0)),
        "ventas_por_dia": [
            {
                "fecha": row[0],
                "cantidad_ventas": int(row[1]),
                "ingresos": Decimal(str(row[2] or 0)),
            }
            for row in ventas_por_dia
        ],
        "productos_mas_vendidos": [
            {
                "producto_id": int(row[0]),
                "codigo": row[1],
                "nombre": row[2],
                "cantidad_vendida": int(row[3]),
                "ingresos": Decimal(str(row[4] or 0)),
            }
            for row in productos_mas_vendidos
        ],
    }


@router.get("/inventario")
async def reporte_inventario(
    session: SessionDeDependencia,
    token: Token_Dependencia,
    productos_limit: int = 10,
):
    _require_owner(token)
    if not 1 <= productos_limit <= 50:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="productos_limit debe estar entre 1 y 50",
        )

    totales = session.exec(
        select(
            func.count(Producto.id_producto),
            func.coalesce(func.sum(Producto.stock_actual), 0),
            func.coalesce(
                func.sum(Producto.stock_actual * Producto.precio_compra),
                0,
            ),
            func.coalesce(
                func.sum(Producto.stock_actual * Producto.precio_venta),
                0,
            ),
        ).where(Producto.estado.is_(True))
    ).one()

    por_categoria = session.exec(
        select(
            Categoria.nombre,
            func.count(Producto.id_producto),
            func.coalesce(func.sum(Producto.stock_actual), 0),
            func.coalesce(
                func.sum(Producto.stock_actual * Producto.precio_compra),
                0,
            ),
            func.coalesce(
                func.sum(Producto.stock_actual * Producto.precio_venta),
                0,
            ),
        )
        .join(Producto, Producto.categoria_id == Categoria.id_categoria)
        .where(Producto.estado.is_(True))
        .group_by(Categoria.id_categoria, Categoria.nombre)
        .order_by(Categoria.nombre)
    ).all()

    reponer = session.exec(
        select(
            Producto.id_producto,
            Producto.codigo,
            Producto.nombre,
            Categoria.nombre,
            Producto.stock_actual,
            Producto.stock_minimo,
            Producto.stock_actual * Producto.precio_compra,
            Producto.stock_actual * Producto.precio_venta,
        )
        .join(Categoria, Categoria.id_categoria == Producto.categoria_id)
        .where(
            Producto.estado.is_(True),
            or_(
                Producto.stock_actual <= Producto.stock_minimo,
                Producto.stock_actual <= 0,
            ),
        )
        .order_by(Producto.stock_actual, Producto.nombre)
    ).all()

    alto_valor = session.exec(
        select(
            Producto.id_producto,
            Producto.codigo,
            Producto.nombre,
            Categoria.nombre,
            Producto.stock_actual,
            Producto.stock_minimo,
            Producto.stock_actual * Producto.precio_compra,
            Producto.stock_actual * Producto.precio_venta,
        )
        .join(Categoria, Categoria.id_categoria == Producto.categoria_id)
        .where(Producto.estado.is_(True))
        .order_by(
            (Producto.stock_actual * Producto.precio_venta).desc(),
            Producto.nombre,
        )
        .limit(productos_limit)
    ).all()

    productos_reponer = [
        {
            "producto_id": int(row[0]),
            "codigo": row[1],
            "nombre": row[2],
            "categoria": row[3],
            "stock_actual": int(row[4]),
            "stock_minimo": int(row[5]),
            "valor_compra": Decimal(str(row[6] or 0)),
            "valor_venta": Decimal(str(row[7] or 0)),
        }
        for row in reponer
    ]

    return {
        "total_productos": int(totales[0] or 0),
        "unidades_disponibles": int(totales[1] or 0),
        "valor_inventario_compra": Decimal(str(totales[2] or 0)),
        "valor_inventario_venta": Decimal(str(totales[3] or 0)),
        "productos_bajo_stock": sum(
            1 for row in reponer if int(row[4]) > 0
        ),
        "productos_sin_stock": sum(1 for row in reponer if int(row[4]) <= 0),
        "productos_reponer": productos_reponer,
        "productos_mayor_valor": [
            {
                "producto_id": int(row[0]),
                "codigo": row[1],
                "nombre": row[2],
                "categoria": row[3],
                "stock_actual": int(row[4]),
                "stock_minimo": int(row[5]),
                "valor_compra": Decimal(str(row[6] or 0)),
                "valor_venta": Decimal(str(row[7] or 0)),
            }
            for row in alto_valor
        ],
        "por_categoria": [
            {
                "categoria": row[0],
                "productos": int(row[1]),
                "unidades": int(row[2]),
                "valor_compra": Decimal(str(row[3] or 0)),
                "valor_venta": Decimal(str(row[4] or 0)),
            }
            for row in por_categoria
        ],
    }
