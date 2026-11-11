import hashlib
import hmac
import ipaddress
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, status
from sqlalchemy.exc import IntegrityError

from config.segurity import _secret_key
from models.security import GuestOrderLookupLimit

CODIGO_ACCESO_LONGITUD = 12
INTENTOS_CONSULTA_MAXIMOS = 10
VENTANA_CONSULTA = timedelta(minutes=15)


def consumir_intento_consulta(session, request: Request | None) -> None:
    client_ip = (
        request.client.host
        if request is not None and request.client is not None
        else "direct-api-call"
    )
    if request is not None:
        trusted_real_ip = request.headers.get("x-real-ip")
        if trusted_real_ip:
            try:
                client_ip = str(ipaddress.ip_address(trusted_real_ip.strip()))
            except ValueError:
                pass
    fingerprint = hmac.new(
        _secret_key().encode("utf-8"),
        client_ip.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    now = datetime.now(timezone.utc)
    limit = session.get(GuestOrderLookupLimit, fingerprint, with_for_update=True)
    if limit is None:
        limit = GuestOrderLookupLimit(
            ip_hash=fingerprint,
            window_started_at=now,
            attempts=0,
        )
        try:
            session.add(limit)
            session.flush()
        except IntegrityError:
            session.rollback()
            limit = session.get(
                GuestOrderLookupLimit,
                fingerprint,
                with_for_update=True,
            )
    window_start = limit.window_started_at
    if window_start.tzinfo is None:
        window_start = window_start.replace(tzinfo=timezone.utc)
    if now - window_start >= VENTANA_CONSULTA:
        limit.window_started_at = now
        limit.attempts = 0
    if limit.attempts >= INTENTOS_CONSULTA_MAXIMOS:
        session.add(limit)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Se alcanzó el límite de consultas; inténtalo más tarde",
            headers={"Retry-After": str(int(VENTANA_CONSULTA.total_seconds()))},
        )
    limit.attempts += 1
    session.add(limit)
    session.commit()
