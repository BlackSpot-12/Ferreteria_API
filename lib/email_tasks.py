import hashlib
import html
import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from sqlmodel import Session, select

from config.db import engine
from lib.correo import WEB_PUBLIC_URL, enviar_correo
from models.detalle_pedido import DetallePedido
from models.email import (
    EmailToken,
    InvoiceEmailAudit,
    InvoiceEmailState,
    UserEmailVerification,
)
from models.pedido import Pedido
from models.producto import Producto
from models.usuario import Usuario
from models.venta import Venta

logger = logging.getLogger(__name__)

PASSWORD_RESET = "password_reset"
EMAIL_VERIFICATION = "email_verification"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _escape(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _invalidate_previous_tokens(session: Session, user_id: int, purpose: str) -> None:
    now = _utcnow()
    tokens = session.exec(
        select(EmailToken).where(
            EmailToken.usuario_id == user_id,
            EmailToken.purpose == purpose,
            EmailToken.used_at.is_(None),
        )
    ).all()
    for token in tokens:
        token.used_at = now
        session.add(token)


def enviar_token_restablecimiento(usuario_id: int) -> None:
    try:
        with Session(engine) as session:
            user = session.get(Usuario, usuario_id)
            if user is None:
                return
            recipient = str(user.correo)
            token = secrets.token_urlsafe(32)
            now = _utcnow()
            _invalidate_previous_tokens(session, usuario_id, PASSWORD_RESET)
            session.add(
                EmailToken(
                    usuario_id=usuario_id,
                    purpose=PASSWORD_RESET,
                    token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
                    created_at=now,
                    expires_at=now + timedelta(hours=1),
                )
            )
            session.commit()

        link = f"{WEB_PUBLIC_URL}/restablecer-password?token={quote(token, safe='')}"
        safe_link = _escape(link)
        enviar_correo(
            recipient,
            "Restablece tu contraseña",
            (
                "<p>Recibimos una solicitud para restablecer tu contraseña.</p>"
                f'<p><a href="{safe_link}">Restablecer contraseña</a></p>'
                "<p>El enlace vence en una hora. Si no solicitaste el cambio, "
                "ignora este mensaje.</p>"
            ),
            f"Restablece tu contraseña en {link}. El enlace vence en una hora.",
        )
    except Exception:
        logger.warning("Notificación omitida: category=password_reset")


def enviar_token_verificacion(usuario_id: int) -> None:
    try:
        with Session(engine) as session:
            user = session.get(Usuario, usuario_id)
            verification = session.get(UserEmailVerification, usuario_id)
            if user is None or verification is None or verification.verificado:
                return
            token = secrets.token_urlsafe(32)
            now = _utcnow()
            _invalidate_previous_tokens(session, usuario_id, EMAIL_VERIFICATION)
            session.add(
                EmailToken(
                    usuario_id=usuario_id,
                    purpose=EMAIL_VERIFICATION,
                    token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
                    created_at=now,
                    expires_at=now + timedelta(hours=24),
                )
            )
            session.commit()
            recipient = str(user.correo)
            name = user.Nombres

        link = f"{WEB_PUBLIC_URL}/verificar-correo?token={quote(token, safe='')}"
        safe_link = _escape(link)
        enviar_correo(
            recipient,
            "Verifica tu correo",
            (
                f"<p>Hola {_escape(name)},</p>"
                '<p><a href="' + safe_link + '">Verificar correo</a></p>'
                "<p>El enlace vence en 24 horas.</p>"
            ),
            f"Verifica tu correo en {link}. El enlace vence en 24 horas.",
        )
    except Exception:
        logger.warning("Notificación omitida: category=email_verification")


def enviar_recibo_pedido(pedido_id: int, codigo_acceso: str | None = None) -> None:
    try:
        with Session(engine) as session:
            pedido = session.get(Pedido, pedido_id)
            if pedido is None:
                return
            recipient = pedido.correo_cliente
            if pedido.usuario_id is not None:
                user = session.get(Usuario, pedido.usuario_id)
                if user is None:
                    return
                recipient = str(user.correo)
            lines = session.exec(
                select(DetallePedido, Producto)
                .join(Producto, Producto.id_producto == DetallePedido.producto_id)
                .where(DetallePedido.pedido_id == pedido_id)
                .order_by(DetallePedido.id_detalle_pedido)
            ).all()
            snapshot = {
                "name": pedido.nombre_cliente,
                "status": pedido.estado,
                "total": pedido.total_pedido,
                "date": pedido.fecha_hora,
                "lines": [
                    (
                        product.nombre,
                        detail.cantidad,
                        detail.precio_unitario,
                        detail.subtotal,
                    )
                    for detail, product in lines
                ],
            }

        rows = "".join(
            "<tr><td>"
            + _escape(name)
            + "</td><td>"
            + _escape(quantity)
            + "</td><td>"
            + _escape(price)
            + "</td><td>"
            + _escape(subtotal)
            + "</td></tr>"
            for name, quantity, price, subtotal in snapshot["lines"]
        )
        code_section = ""
        plain_code = ""
        if codigo_acceso is not None:
            lookup_url = (
                f"{WEB_PUBLIC_URL}/pedido/consulta/"
                f"?codigo_acceso={quote(codigo_acceso, safe='')}"
            )
            code_section = (
                f"<p>Código privado de consulta: <strong>{_escape(codigo_acceso)}</strong></p>"
                f'<p><a href="{_escape(lookup_url)}">Consultar pedido</a></p>'
            )
            plain_code = (
                f"\nCódigo privado: {codigo_acceso}\nConsulta: {lookup_url}"
            )
        subject = f"Recibo del pedido #{pedido_id}"
        body = (
            f"<h2>Recibo del pedido #{pedido_id}</h2>"
            f"<p>Hola {_escape(snapshot['name'])}.</p>"
            f"<p>Fecha: {_escape(snapshot['date'])}<br>"
            f"Estado: {_escape(snapshot['status'])}</p>"
            "<table><thead><tr><th>Producto</th><th>Cantidad</th>"
            "<th>Precio</th><th>Subtotal</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
            f"<p>Total: {_escape(snapshot['total'])}</p>{code_section}"
        )
        text_lines = "\n".join(
            f"{name}: {quantity} x {price} = {subtotal}"
            for name, quantity, price, subtotal in snapshot["lines"]
        )
        enviar_correo(
            recipient,
            subject,
            body,
            (
                f"Recibo del pedido #{pedido_id}\n"
                f"Fecha: {snapshot['date']}\nEstado: {snapshot['status']}\n"
                f"{text_lines}\nTotal: {snapshot['total']}{plain_code}"
            ),
        )
    except Exception:
        logger.warning("Notificación omitida: category=order_receipt")


def enviar_factura_por_correo(
    venta_id: int,
    manual: bool = False,
    audit_id: int | None = None,
) -> None:
    try:
        from routers.venta_router import _factura_de_venta

        with Session(engine) as session:
            sale = session.get(Venta, venta_id)
            if sale is None:
                logger.warning("Notificación omitida: category=invoice_missing")
                return
            invoice = _factura_de_venta(sale, session)

        with Session(engine) as session:
            state = session.exec(
                select(InvoiceEmailState)
                .where(InvoiceEmailState.venta_id == venta_id)
                .with_for_update()
            ).first()
            if state is None:
                state = InvoiceEmailState(venta_id=venta_id)
                session.add(state)
                session.flush()
            if not manual and state.automatic_attempted_at is not None:
                return
            now = _utcnow()
            if manual:
                state.manual_resend_count += 1
                state.manual_last_requested_at = now
                if audit_id is None:
                    audit = InvoiceEmailAudit(
                        venta_id=venta_id,
                        requested_at=now,
                    )
                    session.add(audit)
                    session.flush()
                    audit_id = audit.id
            else:
                state.automatic_attempted_at = now
            session.add(state)
            session.commit()

        detail_rows = "".join(
            "<tr>"
            f'<td style="padding:10px 8px;border:1px solid #d6dde4;color:#24415c;">{_escape(line.codigo)}</td>'
            f'<td style="padding:10px 8px;border:1px solid #d6dde4;font-weight:600;">{_escape(line.nombre)}</td>'
            f'<td style="padding:10px 8px;border:1px solid #d6dde4;text-align:center;">{_escape(line.cantidad)}</td>'
            f'<td style="padding:10px 8px;border:1px solid #d6dde4;text-align:right;">${_escape(line.precio_unitario)}</td>'
            f'<td style="padding:10px 8px;border:1px solid #d6dde4;text-align:right;font-weight:700;">${_escape(line.subtotal)}</td>'
            "</tr>"
            for line in invoice.detalles
        )
        logo_url = (
            _escape(f"{WEB_PUBLIC_URL}/static/tienda/logo.png")
            if WEB_PUBLIC_URL
            else ""
        )
        logo = (
            f'<img src="{logo_url}" alt="BIMETÁLICA" width="185" '
            'style="display:block;width:185px;max-width:100%;height:auto;border:0;">'
            if logo_url
            else '<span style="font-size:22px;font-weight:700;letter-spacing:1px;">BIMETÁLICA</span>'
        )
        body = (
            '<!doctype html><html lang="es"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Factura</title></head>'
            '<body style="margin:0;padding:24px 10px;background-color:#f4f3ef;'
            'font-family:Arial,Helvetica,sans-serif;color:#14283c;">'
            '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
            'style="border-collapse:collapse;"><tr><td align="center">'
            '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
            'style="width:100%;max-width:1000px;border-collapse:collapse;background:#fff;'
            'border:1px solid #e4e6e8;border-radius:8px;overflow:hidden;">'
            '<tr><td style="padding:22px 24px;background:#14283c;color:#fff;">'
            '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
            'style="border-collapse:collapse;"><tr>'
            f'<td valign="middle">{logo}'
            f'<div style="padding-top:10px;font-size:13px;">{_escape(invoice.emisor.nombre)}</div></td>'
            '<td align="right" valign="top" style="padding-left:12px;">'
            '<span style="display:inline-block;padding:4px 10px;border-radius:6px;'
            'background:#ffc107;color:#14283c;font-size:12px;font-weight:700;">Factura</span>'
            f'<div style="padding-top:6px;font-size:22px;font-weight:700;">#{_escape(invoice.id_factura)}</div>'
            f'<div style="font-size:12px;color:#e4ebf2;">{_escape(invoice.fecha_hora)}</div>'
            '</td></tr></table></td></tr>'
            '<tr><td style="padding:22px 24px;">'
            f'<div style="font-size:16px;font-weight:700;">{_escape(invoice.nombre_razon_social)}</div>'
            f'<div style="padding-top:5px;font-size:13px;color:#536b80;">{_escape(invoice.numero_documento)} · {_escape(invoice.correo)}</div>'
            f'<div style="padding-top:4px;font-size:13px;color:#536b80;">{_escape(invoice.telefono)} · {_escape(invoice.direccion)}</div>'
            f'<div style="padding-top:4px;font-size:13px;color:#536b80;">{_escape(invoice.tipo_cliente)} · {_escape(invoice.metodo_pago)}</div>'
            '<table width="100%" cellspacing="0" cellpadding="0" '
            'style="margin-top:22px;border-collapse:collapse;font-size:14px;">'
            '<thead><tr style="background:#f5f6f7;">'
            '<th align="left" style="padding:10px 8px;border:1px solid #cbd2d8;">Código</th>'
            '<th align="left" style="padding:10px 8px;border:1px solid #cbd2d8;">Producto</th>'
            '<th align="center" style="padding:10px 8px;border:1px solid #cbd2d8;">Cantidad</th>'
            '<th align="right" style="padding:10px 8px;border:1px solid #cbd2d8;">Precio unitario</th>'
            '<th align="right" style="padding:10px 8px;border:1px solid #cbd2d8;">Subtotal</th>'
            f'</tr></thead><tbody>{detail_rows}</tbody></table>'
            '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
            'style="margin-top:28px;border-collapse:collapse;"><tr><td></td>'
            '<td width="330" style="width:330px;font-size:14px;">'
            f'<div style="padding:5px 0;text-align:right;">Subtotal: <span style="display:inline-block;min-width:100px;">${_escape(invoice.subtotal)}</span></div>'
            f'<div style="padding:5px 0;text-align:right;">IVA ({_escape(invoice.iva_porcentaje)}): <span style="display:inline-block;min-width:100px;">${_escape(invoice.iva)}</span></div>'
            '<div style="margin-top:4px;padding-top:10px;border-top:1px solid #d6dde4;'
            'text-align:right;font-size:19px;font-weight:700;">'
            f'Total: <span style="display:inline-block;min-width:100px;color:#16865a;">${_escape(invoice.total_pagar)}</span>'
            '</div></td></tr></table>'
            '<div style="padding-top:24px;font-size:12px;color:#718096;">'
            f'{_escape(invoice.emisor.identificacion)} · {_escape(invoice.emisor.direccion)}'
            '</div></td></tr></table></td></tr></table></body></html>'
        )
        text_body = (
            f"Factura #{invoice.id_factura}\n"
            f"Emisor: {invoice.emisor.nombre} | {invoice.emisor.identificacion}\n"
            f"Fecha: {invoice.fecha_hora}\n"
            f"Cliente: {invoice.nombre_razon_social} | {invoice.numero_documento}\n"
            f"Contacto: {invoice.correo} | {invoice.telefono}\n"
            f"Dirección: {invoice.direccion}\n"
            f"Método de pago: {invoice.metodo_pago}\n"
            + "\n".join(
                f"{line.producto_id} {line.codigo} {line.nombre}: {line.cantidad} x "
                f"{line.precio_unitario} - {line.descuento} = {line.subtotal}"
                for line in invoice.detalles
            )
            + "\n"
            f"Subtotal: {invoice.subtotal}\nIVA: {invoice.iva}\n"
            f"Total: {invoice.total_pagar}"
        )
        delivered = enviar_correo(
            invoice.correo,
            f"Factura #{invoice.id_factura}",
            body,
            text_body,
        )
        with Session(engine) as session:
            state = session.get(InvoiceEmailState, venta_id)
            if state is not None:
                state.last_delivery_succeeded = delivered
                if delivered and not manual:
                    state.automatic_sent_at = _utcnow()
                session.add(state)
            if manual and audit_id is not None:
                audit = session.get(InvoiceEmailAudit, audit_id)
                if audit is not None:
                    audit.completed_at = _utcnow()
                    audit.delivery_succeeded = delivered
                    session.add(audit)
            session.commit()
    except Exception:
        logger.warning("Notificación omitida: category=invoice")


def enviar_correo_prueba(destinatario: str) -> bool:
    return enviar_correo(
        destinatario,
        "Prueba de correo - Ferretería Bimetálica",
        "<p>El envío de correo está configurado correctamente.</p>",
        "El envío de correo está configurado correctamente.",
    )
