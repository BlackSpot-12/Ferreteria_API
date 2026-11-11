from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import select

from config.segurity_Dependencia import Token_Dependencia
from config.session_Dependencia import SessionDeDependencia
from models.security import PaymentRecord

router = APIRouter(prefix="/pagos", tags=["Pagos"])


@router.get("", status_code=status.HTTP_200_OK)
async def listar_registros_pago(
    session: SessionDeDependencia,
    token: Token_Dependencia,
    fecha_inicio: date | None = Query(default=None),
    fecha_fin: date | None = Query(default=None),
    metodo_pago: Literal["Efectivo", "Tarjeta", "Transferencia"] | None = Query(
        default=None
    ),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
):
    if token.get("id_rol") != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el propietario puede consultar registros de pago",
        )
    if fecha_inicio is not None and fecha_fin is not None and fecha_inicio > fecha_fin:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="fecha_inicio no puede ser posterior a fecha_fin",
        )
    query = select(PaymentRecord)
    if fecha_inicio is not None:
        query = query.where(
            PaymentRecord.fecha_hora
            >= datetime.combine(fecha_inicio, time.min, tzinfo=timezone.utc)
        )
    if fecha_fin is not None:
        query = query.where(
            PaymentRecord.fecha_hora
            < datetime.combine(
                fecha_fin + timedelta(days=1),
                time.min,
                tzinfo=timezone.utc,
            )
        )
    if metodo_pago is not None:
        query = query.where(PaymentRecord.metodo_pago == metodo_pago)
    return session.exec(
        query.order_by(PaymentRecord.fecha_hora.desc())
        .offset(offset)
        .limit(limit)
    ).all()
