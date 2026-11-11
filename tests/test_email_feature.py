import asyncio
import hashlib
import os
import re
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import main  # noqa: F401
from config.segurity import create_access_token, get_current_user
from lib.correo import enviar_correo
from lib.email_tasks import (
    EMAIL_VERIFICATION,
    PASSWORD_RESET,
    enviar_factura_por_correo,
    enviar_recibo_pedido,
    enviar_token_restablecimiento,
    enviar_token_verificacion,
)
from lib.pwd import get_password_hash, verify_password
from models.categoria import Categoria
from models.datos_facturacion import DatosFacturacion
from models.detalle_pedido import DetallePedido
from models.detalle_venta import DetalleVenta
from models.email import (
    EmailToken,
    EmailVerificationApply,
    InvoiceEmailAudit,
    InvoiceEmailState,
    PasswordResetApply,
    PasswordResetRequest,
    UserEmailVerification,
)
from models.pedido import (
    DatosPedidoCreate,
    PagoPedidoCreate,
    Pedido,
    PedidoCreate,
    PedidoInvitadoCreate,
    PedidoItemCreate,
)
from models.producto import Producto
from models.rol import Rol
from models.security import UserAccess
from models.ubicacion import Ubicacion
from models.usuario import Usuario, UsuarioCreate, UsuarioRegistroCliente
from models.venta import FacturaDatosCreate, Venta, VentaItemCreate, VentaPOSCreate
from routers.auth_router import (
    restablecer_password,
    solicitar_restauracion_password,
)
from routers.pedido_router import (
    crear_pedido,
    crear_pedido_invitado,
    pagar_y_entregar_pedido,
)
from routers.usuario_router import (
    estado_verificacion_correo,
    reenviar_verificacion_correo,
    crear_empleado_admin,
    registrar_cliente,
    verificar_correo,
)
from routers.venta_router import (
    procesar_venta,
    reenviar_factura_por_correo,
)
from seed import poblar_datos


class EmailFeatureTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        event.listen(
            self.engine,
            "connect",
            lambda connection, record: connection.execute("PRAGMA foreign_keys=ON"),
        )
        SQLModel.metadata.create_all(self.engine)
        self.session = Session(self.engine, expire_on_commit=False)
        self.session.add_all(
            [
                Rol(id_rol=1, nombre="Propietario"),
                Rol(id_rol=2, nombre="Empleado"),
                Rol(id_rol=3, nombre="Cliente"),
            ]
        )
        self.owner = Usuario(
            id_usuario=1,
            Nombres="Dueño",
            apellidos="Prueba",
            correo="owner@example.com",
            password_hash=get_password_hash("old-password"),
            rol_id=1,
        )
        self.employee = Usuario(
            id_usuario=2,
            Nombres="Empleado",
            apellidos="Prueba",
            correo="employee@example.com",
            password_hash=get_password_hash("employee-pass"),
            rol_id=2,
        )
        self.customer = Usuario(
            id_usuario=3,
            Nombres="Cliente <script>alert(1)</script>",
            apellidos="Prueba",
            correo="account@example.com",
            password_hash=get_password_hash("customer-pass"),
            rol_id=3,
        )
        self.session.add_all([self.owner, self.employee, self.customer])
        category = Categoria(nombre="Herramientas")
        location = Ubicacion(pasillo="A", estante="1", nivel="1")
        self.session.add_all([category, location])
        self.session.flush()
        self.product = Producto(
            codigo="HAM-01",
            nombre="<script>alert('x')</script>",
            precio_compra=Decimal("5.00"),
            precio_venta=Decimal("10.00"),
            stock_actual=10,
            stock_minimo=1,
            categoria_id=category.id_categoria,
            ubicacion_id=location.id_ubicacion,
        )
        self.session.add(self.product)
        self.session.commit()
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.session.close)
        self.engine_patch = patch("lib.email_tasks.engine", self.engine)
        self.engine_patch.start()
        self.addCleanup(self.engine_patch.stop)

    def _email_token(self, purpose, token, expires=None):
        row = EmailToken(
            usuario_id=self.customer.id_usuario,
            purpose=purpose,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            created_at=datetime.now(timezone.utc),
            expires_at=expires or datetime.now(timezone.utc) + timedelta(hours=1),
        )
        self.session.add(row)
        self.session.commit()
        return row

    def _sale_with_invoice(self):
        sale = Venta(
            usuario_id=self.employee.id_usuario,
            subtotal=Decimal("10.00"),
            iva=Decimal("1.30"),
            total_pagar=Decimal("11.30"),
        )
        self.session.add(sale)
        self.session.flush()
        self.session.add(
            DetalleVenta(
                venta_id=sale.id_venta,
                producto_id=self.product.id_producto,
                cantidad_id=1,
                precio_unitario=Decimal("10.00"),
                descuento=Decimal("0.00"),
                subtotal=Decimal("10.00"),
            )
        )
        self.session.add(
            DatosFacturacion(
                venta_id=sale.id_venta,
                tipo_cliente="Natural",
                nombre_razon_social="<img src=x onerror=alert(1)>",
                numero_documento="123",
                correo="invoice@example.com",
                telefono="12345678",
                direccion="Dirección",
                metodo_pago="Efectivo",
            )
        )
        self.session.commit()
        return sale

    def test_smtp_is_multipart_and_uses_starttls(self):
        with patch("lib.correo.MAIL_ENABLED", True), patch(
            "lib.correo.SMTP_HOST", "smtp.gmail.com"
        ), patch("lib.correo.SMTP_PORT", 587), patch(
            "lib.correo.smtplib.SMTP"
        ) as smtp_class:
            smtp = smtp_class.return_value.__enter__.return_value
            sent = enviar_correo(
                "person@example.com",
                "Test subject",
                "<p>HTML</p>",
                "Plain text",
            )
        self.assertTrue(sent)
        smtp_class.assert_called_once_with("smtp.gmail.com", 587, timeout=15)
        smtp.starttls.assert_called_once()
        message = smtp.send_message.call_args.args[0]
        self.assertEqual(message.get_body(preferencelist=("plain",)).get_content().strip(), "Plain text")
        self.assertEqual(message.get_body(preferencelist=("html",)).get_content().strip(), "<p>HTML</p>")

    def test_smtp_rejects_header_injection_and_disabled_is_quiet(self):
        with patch("lib.correo.MAIL_ENABLED", True), patch(
            "lib.correo.smtplib.SMTP"
        ) as smtp:
            self.assertFalse(
                enviar_correo("person@example.com\r\nBcc:x", "Subject", "<p/>", "text")
            )
            self.assertFalse(
                enviar_correo("person@example.com", "Subject\r\nBcc:x", "<p/>", "text")
            )
            smtp.assert_not_called()
        with patch("lib.correo.MAIL_ENABLED", False), patch(
            "lib.correo.smtplib.SMTP"
        ) as smtp:
            self.assertFalse(
                enviar_correo("private@example.com", "Hello", "<p/>", "text")
            )
            smtp.assert_not_called()

    def test_smtp_exceptions_do_not_propagate_or_log_sensitive_values(self):
        with self.assertLogs("lib.correo", level="WARNING") as captured:
            with patch("lib.correo.MAIL_ENABLED", True), patch(
                "lib.correo.smtplib.SMTP", side_effect=RuntimeError("secret-password")
            ):
                self.assertFalse(
                    enviar_correo(
                        "private@example.com",
                        "Private subject",
                        "<p>private-token</p>",
                        "private",
                    )
                )
        output = "\n".join(captured.output)
        self.assertNotIn("private@example.com", output)
        self.assertNotIn("secret-password", output)
        self.assertNotIn("private-token", output)

    def test_password_reset_tokens_expire_are_single_use_and_revoke_sessions(self):
        expired = self._email_token(
            PASSWORD_RESET,
            "expired-token",
            datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        with self.assertRaises(HTTPException) as error:
            asyncio.run(
                restablecer_password(
                    PasswordResetApply(token="expired-token", password="new-password"),
                    self.session,
                )
            )
        self.assertEqual(error.exception.status_code, 400)
        self.session.delete(expired)
        self.session.add(UserAccess(usuario_id=3, token_version=4))
        self.session.commit()
        with patch.dict(os.environ, {"SECRET_KEY_TOKEN": "s" * 48}):
            old_access_token = create_access_token({"id": 3, "token_version": 4})
        self._email_token(PASSWORD_RESET, "valid-reset-token")

        asyncio.run(
            restablecer_password(
                PasswordResetApply(
                    token="valid-reset-token",
                    password="new-password",
                ),
                self.session,
            )
        )
        self.session.refresh(self.customer)
        self.assertTrue(verify_password("new-password", self.customer.password_hash))
        self.assertEqual(self.session.get(UserAccess, 3).token_version, 5)
        with patch("config.segurity.engine", self.engine), patch.dict(
            os.environ, {"SECRET_KEY_TOKEN": "s" * 48}
        ):
            with self.assertRaises(HTTPException):
                get_current_user(old_access_token)
        with self.assertRaises(HTTPException) as error:
            asyncio.run(
                restablecer_password(
                    PasswordResetApply(
                        token="valid-reset-token",
                        password="another-password",
                    ),
                    self.session,
                )
            )
        self.assertEqual(error.exception.status_code, 400)

    def test_forgot_password_response_does_not_disclose_account_existence(self):
        known_tasks = BackgroundTasks()
        unknown_tasks = BackgroundTasks()
        known = asyncio.run(
            solicitar_restauracion_password(
                PasswordResetRequest(correo="account@example.com"),
                self.session,
                known_tasks,
            )
        )
        unknown = asyncio.run(
            solicitar_restauracion_password(
                PasswordResetRequest(correo="missing@example.com"),
                self.session,
                unknown_tasks,
            )
        )
        self.assertEqual(known, unknown)
        self.assertEqual(len(known_tasks.tasks), 1)
        self.assertEqual(len(unknown_tasks.tasks), 0)

    def test_seed_created_users_are_explicitly_verified(self):
        poblar_datos(
            self.session,
            {
                "SEED_OWNER_PASSWORD": "owner-password",
                "SEED_EMPLOYEE_PASSWORD": "employee-password",
                "SEED_CUSTOMER_PASSWORD": "customer-password",
            },
        )
        for email in (
            "propietario@ferreteria.local",
            "empleado@ferreteria.local",
            "cliente@ferreteria.local",
        ):
            user = self.session.exec(
                select(Usuario).where(Usuario.correo == email)
            ).first()
            verification = self.session.get(
                UserEmailVerification,
                user.id_usuario,
            )
            self.assertTrue(verification.verificado)
            self.assertIsNotNone(verification.verified_at)

    def test_reset_email_token_is_hashed_short_lived_and_older_tokens_invalidated(self):
        sent = []
        with patch("lib.email_tasks.enviar_correo", side_effect=lambda *args: sent.append(args) or True):
            enviar_token_restablecimiento(self.customer.id_usuario)
            enviar_token_restablecimiento(self.customer.id_usuario)
        rows = self.session.exec(
            select(EmailToken).where(
                EmailToken.usuario_id == self.customer.id_usuario,
                EmailToken.purpose == PASSWORD_RESET,
            )
        ).all()
        self.assertEqual(len(rows), 2)
        self.assertEqual(sum(row.used_at is None for row in rows), 1)
        match = re.search(r"token=([^\"&]+)", sent[-1][2])
        self.assertIsNotNone(match)
        raw_token = match.group(1)
        active = next(row for row in rows if row.used_at is None)
        self.assertEqual(active.token_hash, hashlib.sha256(raw_token.encode()).hexdigest())
        self.assertNotEqual(active.token_hash, raw_token)
        self.assertLessEqual(active.expires_at - active.created_at, timedelta(hours=1))

    def test_email_verification_expiry_one_use_legacy_and_throttle(self):
        verification = UserEmailVerification(
            usuario_id=3,
            verificado=False,
            last_sent_at=datetime.now(timezone.utc) - timedelta(minutes=3),
        )
        self.session.add(verification)
        self.session.commit()
        background = BackgroundTasks()
        response = asyncio.run(
            reenviar_verificacion_correo(
                self.session,
                {"id": 3},
                background,
            )
        )
        self.assertIn("recibirás", response["detail"])
        self.assertEqual(len(background.tasks), 1)
        with self.assertRaises(HTTPException) as error:
            asyncio.run(
                reenviar_verificacion_correo(
                    self.session,
                    {"id": 3},
                    BackgroundTasks(),
                )
            )
        self.assertEqual(error.exception.status_code, 429)

        sent = []
        with patch("lib.email_tasks.enviar_correo", side_effect=lambda *args: sent.append(args) or True):
            enviar_token_verificacion(3)
        token = re.search(r"token=([^\"&]+)", sent[0][2]).group(1)
        row = self.session.exec(
            select(EmailToken).where(EmailToken.purpose == EMAIL_VERIFICATION)
        ).first()
        self.assertEqual(row.token_hash, hashlib.sha256(token.encode()).hexdigest())
        self.assertLessEqual(row.expires_at - row.created_at, timedelta(hours=24))
        result = asyncio.run(
            verificar_correo(
                EmailVerificationApply(token=token),
                self.session,
            )
        )
        self.assertEqual(result["detail"], "Correo verificado")
        with self.assertRaises(HTTPException):
            asyncio.run(
                verificar_correo(
                    EmailVerificationApply(token=token),
                    self.session,
                )
            )

        legacy = asyncio.run(
            estado_verificacion_correo(self.session, {"id": 1})
        )
        self.assertTrue(legacy["verificado"])
        expired_token = self._email_token(
            EMAIL_VERIFICATION,
            "expired-verification",
            datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        with self.assertRaises(HTTPException):
            asyncio.run(
                verificar_correo(
                    EmailVerificationApply(token="expired-verification"),
                    self.session,
                )
            )
        self.session.delete(expired_token)
        self.session.commit()

    def test_registration_password_constraints_and_unverified_state(self):
        with self.assertRaises(ValueError):
            UsuarioRegistroCliente(
                Nombres="New",
                apellidos="User",
                correo="new@example.com",
                password="short",
            )
        background = BackgroundTasks()
        response = asyncio.run(
            registrar_cliente(
                UsuarioRegistroCliente(
                    Nombres="New",
                    apellidos="User",
                    correo="new@example.com",
                    password="new-password",
                ),
                self.session,
                background,
            )
        )
        self.assertEqual(response.correo, "new@example.com")
        verification = self.session.get(UserEmailVerification, response.id_usuario)
        self.assertFalse(verification.verificado)
        self.assertEqual(len(background.tasks), 1)

    def test_password_limits_and_employee_accounts_are_verified(self):
        with self.assertRaises(ValueError):
            UsuarioCreate(
                Nombres="Employee",
                apellidos="Test",
                correo="new-employee@example.com",
                password="short",
                rol_id=2,
            )
        with self.assertRaises(ValueError):
            PasswordResetApply(token="token", password="p" * 256)
        employee = asyncio.run(
            crear_empleado_admin(
                UsuarioCreate(
                    Nombres="Employee",
                    apellidos="Test",
                    correo="new-employee@example.com",
                    password="employee-password",
                    rol_id=2,
                ),
                self.session,
                {"id_rol": 1},
            )
        )
        verification = self.session.get(UserEmailVerification, employee.id_usuario)
        self.assertTrue(verification.verificado)
        self.assertIsNotNone(verification.verified_at)
        with self.assertRaises(ValueError):
            UsuarioCreate(
                Nombres="Employee",
                apellidos="Test",
                correo="long-password@example.com",
                password="p" * 256,
                rol_id=2,
            )

    def test_registered_customer_policy_and_guest_exemption(self):
        self.session.add(UserEmailVerification(usuario_id=3, verificado=False))
        self.session.commit()
        payload = PedidoCreate(
            items=[PedidoItemCreate(producto_id=self.product.id_producto, cantidad=1)],
            datos_cliente=DatosPedidoCreate(
                tipo_cliente="Natural",
                nombre_razon_social="Contact Name",
                correo="checkout@example.com",
                telefono="12345678",
                numero_documento="123",
                direccion="Street",
            ),
        )
        with patch.dict(os.environ, {"REQUIRE_EMAIL_VERIFICATION": "1"}):
            with self.assertRaises(HTTPException) as error:
                asyncio.run(crear_pedido(payload, self.session, {"id": 3, "id_rol": 3}))
            self.assertEqual(error.exception.status_code, 403)
            self.session.rollback()
            guest_background = BackgroundTasks()
            guest_payload = PedidoInvitadoCreate(
                items=payload.items,
                datos_cliente=payload.datos_cliente,
            )
            guest = asyncio.run(
                crear_pedido_invitado(guest_payload, self.session, guest_background)
            )
        self.assertTrue(guest.codigo_acceso)
        self.assertEqual(len(guest_background.tasks), 1)

    def test_order_receipts_use_persisted_content_and_escape_html(self):
        order = Pedido(
            usuario_id=3,
            estado="Pendiente",
            total_pedido=Decimal("10.00"),
            nombre_cliente="<b>Customer</b>",
            correo_cliente="checkout@example.com",
            telefono_cliente="12345678",
            tipo_cliente="Natural",
            numero_documento="123",
            direccion_cliente="Street",
        )
        self.session.add(order)
        self.session.flush()
        self.session.add(
            DetallePedido(
                pedido_id=order.id_pedido,
                producto_id=self.product.id_producto,
                cantidad=1,
                precio_unitario=Decimal("10.00"),
                subtotal=Decimal("10.00"),
            )
        )
        self.session.commit()
        messages = []
        with patch("lib.email_tasks.enviar_correo", side_effect=lambda *args: messages.append(args) or True):
            enviar_recibo_pedido(order.id_pedido)
            guest_order = Pedido(
                usuario_id=None,
                estado="Pendiente",
                total_pedido=Decimal("10.00"),
                nombre_cliente="Guest",
                correo_cliente="guest@example.com",
                telefono_cliente="12345678",
                tipo_cliente="Natural",
                numero_documento="123",
                direccion_cliente="Street",
            )
            self.session.add(guest_order)
            self.session.flush()
            self.session.add(
                DetallePedido(
                    pedido_id=guest_order.id_pedido,
                    producto_id=self.product.id_producto,
                    cantidad=1,
                    precio_unitario=Decimal("10.00"),
                    subtotal=Decimal("10.00"),
                )
            )
            self.session.commit()
            with patch("lib.email_tasks.WEB_PUBLIC_URL", "https://shop.example"):
                enviar_recibo_pedido(guest_order.id_pedido, "abc&<secret")
        self.assertEqual(messages[0][0], "account@example.com")
        self.assertIn("&lt;script&gt;", messages[0][2])
        self.assertNotIn("<script>", messages[0][2])
        self.assertEqual(messages[1][0], "guest@example.com")
        self.assertIn("https://shop.example/pedido/consulta/", messages[1][2])
        self.assertIn("abc%26%3Csecret", messages[1][2])
        self.assertIn("abc&<secret", messages[1][3])

    def test_pos_and_delivery_schedule_invoice_email(self):
        pos_payload = VentaPOSCreate(
            items=[VentaItemCreate(producto_id=self.product.id_producto, cantidad=1)],
            datos_facturacion=FacturaDatosCreate(
                tipo_cliente="Natural",
                nombre_razon_social="Customer",
                numero_documento="123",
                correo="invoice@example.com",
                telefono="12345678",
                direccion="Street",
                metodo_pago="Efectivo",
            ),
        )
        pos_tasks = BackgroundTasks()
        asyncio.run(
            procesar_venta(pos_payload, self.session, {"id": 2, "id_rol": 2}, pos_tasks)
        )
        self.assertEqual(pos_tasks.tasks[0].func, enviar_factura_por_correo)

        order = Pedido(
            usuario_id=None,
            estado="Listo",
            total_pedido=Decimal("10.00"),
            nombre_cliente="Guest",
            correo_cliente="guest@example.com",
            telefono_cliente="12345678",
            tipo_cliente="Natural",
            numero_documento="123",
            direccion_cliente="Street",
        )
        self.session.add(order)
        self.session.flush()
        self.session.add(
            DetallePedido(
                pedido_id=order.id_pedido,
                producto_id=self.product.id_producto,
                cantidad=1,
                precio_unitario=Decimal("10.00"),
                subtotal=Decimal("10.00"),
            )
        )
        self.session.commit()
        delivery_tasks = BackgroundTasks()
        asyncio.run(
            pagar_y_entregar_pedido(
                order.id_pedido,
                PagoPedidoCreate(metodo_pago="Efectivo"),
                self.session,
                {"id": 2, "id_rol": 2},
                delivery_tasks,
            )
        )
        self.assertEqual(delivery_tasks.tasks[0].func, enviar_factura_por_correo)

    def test_invoice_automatic_dedup_failure_and_manual_audit_retry(self):
        sale = self._sale_with_invoice()
        messages = []

        def fake_send(*args):
            messages.append(args)
            return len(messages) > 1

        with patch.dict(
            os.environ,
            {
                "FACTURA_RAZON_SOCIAL": "Tienda",
                "FACTURA_IDENTIFICACION": "123",
                "FACTURA_DIRECCION": "Address",
            },
        ), patch("lib.email_tasks.enviar_correo", side_effect=fake_send):
            enviar_factura_por_correo(sale.id_venta)
            enviar_factura_por_correo(sale.id_venta)
            self.assertEqual(len(messages), 1)
            audit = InvoiceEmailAudit(
                venta_id=sale.id_venta,
                requested_by=2,
            )
            self.session.add(audit)
            self.session.commit()
            self.session.refresh(audit)
            enviar_factura_por_correo(sale.id_venta, True, audit.id)
        self.assertEqual(len(messages), 2)
        self.assertIn("&lt;img", messages[0][2])
        self.assertNotIn("<img src=x", messages[0][2])
        self.assertIn('background:#14283c;color:#fff', messages[0][2])
        self.assertIn(">Código</th>", messages[0][2])
        self.assertIn(">Producto</th>", messages[0][2])
        self.assertIn(">Precio unitario</th>", messages[0][2])
        self.assertIn("$10.00", messages[0][2])
        self.assertIn("$1.30", messages[0][2])
        self.assertIn("$11.30", messages[0][2])
        state = self.session.get(InvoiceEmailState, sale.id_venta)
        self.assertIsNotNone(state.automatic_attempted_at)
        self.assertIsNone(state.automatic_sent_at)
        self.assertEqual(state.manual_resend_count, 1)
        self.assertTrue(state.last_delivery_succeeded)
        self.session.refresh(audit)
        self.assertTrue(audit.delivery_succeeded)

    def test_manual_invoice_resend_is_available_to_employee_and_audited(self):
        sale = self._sale_with_invoice()
        tasks = BackgroundTasks()
        response = asyncio.run(
            reenviar_factura_por_correo(
                sale.id_venta,
                tasks,
                self.session,
                {"id": 2, "id_rol": 2},
            )
        )
        self.assertIn("reenvío", response["detail"])
        audit = self.session.exec(
            select(InvoiceEmailAudit).where(InvoiceEmailAudit.venta_id == sale.id_venta)
        ).first()
        self.assertEqual(audit.requested_by, 2)
        self.assertEqual(len(tasks.tasks), 1)
