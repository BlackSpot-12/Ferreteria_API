import asyncio
import hashlib
import hmac
import os
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import main  # noqa: F401
from config.segurity import create_access_token, get_current_user
from config.session_Dependencia import get_session
from models.categoria import Categoria
from models.detalle_venta import DetalleVenta
from models.pedido import (
    DatosPedidoCreate,
    PagoPedidoCreate,
    Pedido,
    PedidoInvitadoCreate,
    PedidoItemCreate,
    PedidoUpdate,
)
from models.producto import Producto, ProductoUpdate
from models.rol import Rol
from models.security import PaymentRecord, UserAccess
from models.security import GuestOrderLookupLimit
from models.ubicacion import Ubicacion
from models.usuario import Usuario, UsuarioEstadoUpdate
from models.venta import FacturaDatosCreate, VentaItemCreate, VentaPOSCreate
from routers.pedido_router import (
    actualizar_estado_pedido,
    consultar_pedido_invitado,
    crear_pedido_invitado,
    listar_pedidos,
    pagar_y_entregar_pedido,
    router as pedido_router,
)
from routers.auth_router import cerrar_todas_las_sesiones
from routers.pago_router import listar_registros_pago
from routers.producto_router import actualizar_producto, eliminar_producto
from routers.reporte_router import reporte_inventario
from routers.usuario_router import (
    actualizar_estado_usuario,
    listar_usuarios,
    revocar_sesiones_usuario,
)
from routers.venta_router import procesar_venta


class ManagementApiTests(unittest.TestCase):
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
        self.session.add_all(
            [
                Usuario(
                    id_usuario=1,
                    Nombres="Dueño",
                    apellidos="Prueba",
                    correo="owner@example.com",
                    password_hash="not-used",
                    rol_id=1,
                ),
                Usuario(
                    id_usuario=2,
                    Nombres="Empleado",
                    apellidos="Prueba",
                    correo="employee@example.com",
                    password_hash="not-used",
                    rol_id=2,
                ),
                Usuario(
                    id_usuario=3,
                    Nombres="Cliente",
                    apellidos="Prueba",
                    correo="customer@example.com",
                    password_hash="not-used",
                    rol_id=3,
                ),
            ]
        )
        self.category = Categoria(nombre="Herramientas")
        self.location = Ubicacion(pasillo="A", estante="1", nivel="1")
        self.session.add_all([self.category, self.location])
        self.session.flush()
        self.product = Producto(
            codigo="HAM-01",
            nombre="Martillo",
            precio_compra=Decimal("5.00"),
            precio_venta=Decimal("10.00"),
            stock_actual=2,
            stock_minimo=2,
            categoria_id=self.category.id_categoria,
            ubicacion_id=self.location.id_ubicacion,
        )
        self.session.add(self.product)
        self.session.commit()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_product_delete_is_owner_only_soft_delete_and_reactivatable(self):
        with self.assertRaises(HTTPException) as error:
            asyncio.run(
                eliminar_producto(
                    self.product.id_producto,
                    self.session,
                    {"id": 2, "id_rol": 2},
                )
            )
        self.assertEqual(error.exception.status_code, 403)

        result = asyncio.run(
            eliminar_producto(
                self.product.id_producto,
                self.session,
                {"id": 1, "id_rol": 1},
            )
        )
        self.assertFalse(result["estado"])
        self.assertIsNotNone(self.session.get(Producto, self.product.id_producto))
        restored = asyncio.run(
            actualizar_producto(
                self.product.id_producto,
                ProductoUpdate(estado=True),
                self.session,
                {"id": 1, "id_rol": 1},
            )
        )
        self.assertTrue(restored.estado)

    def test_user_listing_is_limited_to_staff_and_status_revokes_tokens(self):
        listed = asyncio.run(listar_usuarios(self.session, {"id_rol": 2}))
        self.assertEqual(len(listed), 3)
        self.assertTrue(all(not hasattr(user, "password_hash") for user in listed))
        with self.assertRaises(HTTPException) as error:
            asyncio.run(
                actualizar_estado_usuario(
                    3,
                    UsuarioEstadoUpdate(activo=False),
                    self.session,
                    {"id": 2, "id_rol": 2},
                )
            )
        self.assertEqual(error.exception.status_code, 403)

        with patch.dict(os.environ, {"SECRET_KEY_TOKEN": "s" * 48}):
            token = create_access_token(
                {"id": 2, "id_rol": 2, "token_version": 0}
            )
            access = UserAccess(usuario_id=2, token_version=0)
            self.session.add(access)
            self.session.commit()
            updated = asyncio.run(
                actualizar_estado_usuario(
                    2,
                    UsuarioEstadoUpdate(activo=False),
                    self.session,
                    {"id": 1, "id_rol": 1},
                )
            )
            self.assertFalse(updated.activo)
            with patch(
                "config.segurity.Session",
                side_effect=lambda *args, **kwargs: Session(
                    self.engine,
                    expire_on_commit=False,
                ),
            ):
                with self.assertRaises(HTTPException) as error:
                    get_current_user(token)
            self.assertEqual(error.exception.status_code, 401)

            restored = asyncio.run(
                actualizar_estado_usuario(
                    2,
                    UsuarioEstadoUpdate(activo=True),
                    self.session,
                    {"id": 1, "id_rol": 1},
                )
            )
            self.assertTrue(restored.activo)
            with self.assertRaises(HTTPException):
                with patch(
                    "config.segurity.Session",
                    side_effect=lambda *args, **kwargs: Session(
                        self.engine,
                        expire_on_commit=False,
                    ),
                ):
                    get_current_user(token)

    def test_updating_user_status_returns_user_with_default_session_expiration(self):
        self.session.close()
        with Session(self.engine) as session:
            updated = asyncio.run(
                actualizar_estado_usuario(
                    2,
                    UsuarioEstadoUpdate(activo=False),
                    session,
                    {"id": 1, "id_rol": 1},
                )
            )

        self.assertEqual(updated.id_usuario, 2)
        self.assertEqual(updated.Nombres, "Empleado")
        self.assertEqual(updated.correo, "employee@example.com")
        self.assertFalse(updated.activo)

    def test_owner_accounts_cannot_be_deactivated_by_another_owner(self):
        self.session.add(
            Usuario(
                id_usuario=4,
                Nombres="Segundo propietario",
                apellidos="Prueba",
                correo="owner2@example.com",
                password_hash="not-used",
                rol_id=1,
            )
        )
        self.session.commit()

        with self.assertRaises(HTTPException) as error:
            asyncio.run(
                actualizar_estado_usuario(
                    4,
                    UsuarioEstadoUpdate(activo=False),
                    self.session,
                    {"id": 1, "id_rol": 1},
                )
            )

        self.assertEqual(error.exception.status_code, 409)
        self.assertIsNone(self.session.get(UserAccess, 4))

    def test_owner_can_revoke_another_users_sessions(self):
        self.session.add(UserAccess(usuario_id=2, token_version=0))
        self.session.commit()
        result = asyncio.run(
            revocar_sesiones_usuario(
                2,
                self.session,
                {"id": 1, "id_rol": 1},
            )
        )
        self.assertIn("revocaron", result["detail"])
        self.assertEqual(self.session.get(UserAccess, 2).token_version, 1)
        asyncio.run(cerrar_todas_las_sesiones(self.session, {"id": 2}))
        self.assertEqual(self.session.get(UserAccess, 2).token_version, 2)

    def test_order_filters_keep_employee_queue_shared(self):
        self.session.add_all(
            [
                Pedido(
                    usuario_id=3,
                    fecha_hora=datetime(2026, 11, 1, tzinfo=timezone.utc),
                    estado="Pendiente",
                    total_pedido=Decimal("10.00"),
                    nombre_cliente="Ana Ejemplo",
                    correo_cliente="ana@example.com",
                    telefono_cliente="5550101",
                    tipo_cliente="Natural",
                    numero_documento="ID-1",
                    direccion_cliente="Calle 1",
                ),
                Pedido(
                    usuario_id=3,
                    fecha_hora=datetime(2026, 11, 2, tzinfo=timezone.utc),
                    estado="En preparacion",
                    total_pedido=Decimal("10.00"),
                    nombre_cliente="Beto Ejemplo",
                    correo_cliente="beto@example.com",
                    telefono_cliente="5550102",
                    tipo_cliente="Natural",
                    numero_documento="ID-2",
                    direccion_cliente="Calle 2",
                ),
            ]
        )
        self.session.commit()

        orders = asyncio.run(
            listar_pedidos(
                self.session,
                {"id": 2, "id_rol": 2},
                "Pendiente",
                datetime(2026, 11, 1).date(),
                datetime(2026, 11, 1).date(),
                "Ana",
            )
        )
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].nombre_cliente, "Ana Ejemplo")
        customer_orders = asyncio.run(
            listar_pedidos(
                self.session,
                {"id": 3, "id_rol": 3},
                "En preparacion",
            )
        )
        self.assertEqual(len(customer_orders), 1)

    def test_inventory_report_includes_replenishment_and_high_value_items(self):
        empty_product = Producto(
            codigo="SAW-01",
            nombre="Sierra",
            precio_compra=Decimal("15.00"),
            precio_venta=Decimal("30.00"),
            stock_actual=0,
            stock_minimo=3,
            categoria_id=self.category.id_categoria,
            ubicacion_id=self.location.id_ubicacion,
        )
        self.session.add(empty_product)
        self.session.commit()
        report = asyncio.run(reporte_inventario(self.session, {"id_rol": 1}))
        self.assertEqual(report["productos_bajo_stock"], 1)
        self.assertEqual(report["productos_sin_stock"], 1)
        self.assertEqual(len(report["productos_reponer"]), 2)
        self.assertEqual(report["productos_mayor_valor"][0]["codigo"], "HAM-01")

    def test_pos_persists_audited_payment_and_optional_reference(self):
        payload = VentaPOSCreate(
            items=[VentaItemCreate(producto_id=self.product.id_producto, cantidad=1)],
            datos_facturacion=FacturaDatosCreate(
                tipo_cliente="Natural",
                nombre_razon_social="Ana Ejemplo",
                numero_documento="ID-10",
                correo="ana@example.com",
                telefono="5550100",
                direccion="Calle 1",
                metodo_pago="Transferencia",
                referencia_pago=" TRANS-55 ",
            ),
        )
        sale = asyncio.run(
            procesar_venta(payload, self.session, {"id": 2, "id_rol": 2})
        )
        record = self.session.exec(
            select(PaymentRecord).where(PaymentRecord.venta_id == sale.id_venta)
        ).one()
        self.assertEqual(record.metodo_pago, "Transferencia")
        self.assertEqual(record.referencia, "TRANS-55")
        self.assertEqual(record.monto, sale.total_pagar)
        audited = asyncio.run(
            listar_registros_pago(
                self.session,
                {"id_rol": 1},
                None,
                None,
                "Transferencia",
                0,
                100,
            )
        )
        self.assertEqual(audited[0].referencia, "TRANS-55")
        with self.assertRaises(HTTPException) as error:
            asyncio.run(
                listar_registros_pago(
                    self.session,
                    {"id_rol": 2},
                    None,
                    None,
                    None,
                    0,
                    100,
                )
            )
        self.assertEqual(error.exception.status_code, 403)

        with self.assertRaises(ValueError):
            FacturaDatosCreate(
                tipo_cliente="Natural",
                nombre_razon_social="Ana Ejemplo",
                numero_documento="ID-10",
                correo="ana@example.com",
                telefono="5550100",
                direccion="Calle 1",
                metodo_pago="Efectivo",
                referencia_pago="REF",
            )

    def test_guest_code_is_short_and_lookup_attempts_are_bounded(self):
        with patch.dict(os.environ, {"SECRET_KEY_TOKEN": "g" * 48}):
            receipt = asyncio.run(
                crear_pedido_invitado(
                    PedidoInvitadoCreate(
                        items=[
                            PedidoItemCreate(
                                producto_id=self.product.id_producto,
                                cantidad=1,
                            )
                        ],
                        datos_cliente=DatosPedidoCreate(
                            tipo_cliente="Natural",
                            nombre_razon_social="Invitado",
                            correo="guest@example.com",
                            telefono="5550100",
                            numero_documento="ID-G",
                            direccion="Calle 1",
                        ),
                    ),
                    self.session,
                )
            )
            self.assertEqual(len(receipt.codigo_acceso), 12)
            found = asyncio.run(
                consultar_pedido_invitado(self.session, receipt.codigo_acceso)
            )
            self.assertEqual(found.pedido.id_pedido, receipt.pedido.id_pedido)

            for _ in range(9):
                with self.assertRaises(HTTPException) as error:
                    asyncio.run(consultar_pedido_invitado(self.session, "x" * 12))
                self.assertEqual(error.exception.status_code, 404)
            with self.assertRaises(HTTPException) as error:
                asyncio.run(consultar_pedido_invitado(self.session, "x" * 12))
            self.assertEqual(error.exception.status_code, 429)

    def test_guest_lookup_route_accepts_short_code_and_enforces_ip_limit(self):
        app = FastAPI()
        app.include_router(pedido_router)

        def session_override():
            with Session(self.engine, expire_on_commit=False) as session:
                yield session

        app.dependency_overrides[get_session] = session_override
        with patch.dict(os.environ, {"SECRET_KEY_TOKEN": "h" * 48}):
            receipt = asyncio.run(
                crear_pedido_invitado(
                    PedidoInvitadoCreate(
                        items=[
                            PedidoItemCreate(
                                producto_id=self.product.id_producto,
                                cantidad=1,
                            )
                        ],
                        datos_cliente=DatosPedidoCreate(
                            tipo_cliente="Natural",
                            nombre_razon_social="Invitado",
                            correo="guest@example.com",
                            telefono="5550100",
                            numero_documento="ID-G",
                            direccion="Calle 1",
                        ),
                    ),
                    self.session,
                )
            )
            with TestClient(app) as client:
                response = client.get(
                    "/pedidos/consulta",
                    headers={"X-Order-Access-Code": receipt.codigo_acceso},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.json()["pedido"]["id_pedido"],
                    receipt.pedido.id_pedido,
                )
                for _ in range(9):
                    response = client.get(
                        "/pedidos/consulta",
                        headers={"X-Order-Access-Code": "z" * 12},
                    )
                    self.assertEqual(response.status_code, 404)
                limited = client.get(
                    "/pedidos/consulta",
                    headers={"X-Order-Access-Code": "z" * 12},
                )
                self.assertEqual(limited.status_code, 429)
                self.assertEqual(limited.headers["retry-after"], "900")

    def test_guest_lookup_rate_limit_uses_real_ip_and_safe_peer_fallback(self):
        app = FastAPI()
        app.include_router(pedido_router)

        def session_override():
            with Session(self.engine, expire_on_commit=False) as session:
                yield session

        app.dependency_overrides[get_session] = session_override
        secret = "r" * 48
        with patch.dict(os.environ, {"SECRET_KEY_TOKEN": secret}):
            with TestClient(app) as client:
                for proxy_ip in ("203.0.113.10", "203.0.113.11"):
                    response = client.get(
                        "/pedidos/consulta",
                        headers={
                            "X-Order-Access-Code": "x" * 12,
                            "X-Real-IP": proxy_ip,
                            "X-Forwarded-For": "198.51.100.77",
                        },
                    )
                    self.assertEqual(response.status_code, 404)

                peer = client.get(
                    "/pedidos/consulta",
                    headers={
                        "X-Order-Access-Code": "x" * 12,
                        "X-Forwarded-For": "192.0.2.10",
                    },
                )
                self.assertEqual(peer.status_code, 404)
                fallback_peer = client.get(
                    "/pedidos/consulta",
                    headers={
                        "X-Order-Access-Code": "x" * 12,
                        "X-Forwarded-For": "192.0.2.11",
                        "X-Real-IP": "not-an-ip",
                    },
                )
                self.assertEqual(fallback_peer.status_code, 404)

        def fingerprint(ip):
            return hmac.new(
                secret.encode("utf-8"),
                ip.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

        with Session(self.engine) as session:
            counters = {
                row.ip_hash: row.attempts
                for row in session.exec(select(GuestOrderLookupLimit)).all()
            }
        self.assertEqual(counters[fingerprint("203.0.113.10")], 1)
        self.assertEqual(counters[fingerprint("203.0.113.11")], 1)
        self.assertEqual(counters[fingerprint("testclient")], 2)
        self.assertEqual(len(counters), 3)

    def test_order_payment_is_audited(self):
        with patch.dict(os.environ, {"SECRET_KEY_TOKEN": "p" * 48}):
            receipt = asyncio.run(
                crear_pedido_invitado(
                    PedidoInvitadoCreate(
                        items=[
                            PedidoItemCreate(
                                producto_id=self.product.id_producto,
                                cantidad=1,
                            )
                        ],
                        datos_cliente=DatosPedidoCreate(
                            tipo_cliente="Natural",
                            nombre_razon_social="Invitado",
                            correo="guest@example.com",
                            telefono="5550100",
                            numero_documento="ID-G",
                            direccion="Calle 1",
                        ),
                    ),
                    self.session,
                )
            )
        asyncio.run(
            actualizar_estado_pedido(
                receipt.pedido.id_pedido,
                PedidoUpdate(estado="En preparacion"),
                self.session,
                {"id": 2, "id_rol": 2},
            )
        )
        asyncio.run(
            actualizar_estado_pedido(
                receipt.pedido.id_pedido,
                PedidoUpdate(estado="Listo"),
                self.session,
                {"id": 2, "id_rol": 2},
            )
        )
        self.session.commit()
        asyncio.run(
            pagar_y_entregar_pedido(
                receipt.pedido.id_pedido,
                PagoPedidoCreate(
                    metodo_pago="Tarjeta",
                    referencia_pago="CARD-88",
                ),
                self.session,
                {"id": 2, "id_rol": 2},
            )
        )
        record = self.session.exec(select(PaymentRecord)).one()
        self.assertEqual(record.referencia, "CARD-88")
        self.assertEqual(record.metodo_pago, "Tarjeta")


if __name__ == "__main__":
    unittest.main()
