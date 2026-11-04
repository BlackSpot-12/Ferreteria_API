import asyncio
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import main  # noqa: F401
from config.segurity import get_current_user
from config.session_Dependencia import get_session
from models.categoria import Categoria
from models.configuracion import (
    ConfiguracionMayoristaUpdate,
    ConfiguracionNegocio,
)
from models.detalle_venta import DetalleVenta
from models.pedido import DatosPedidoCreate, Pedido, PedidoCreate, PedidoItemCreate
from models.producto import Producto
from models.rol import Rol
from models.ubicacion import Ubicacion
from models.usuario import Usuario
from models.venta import Venta
from routers.configuracion_router import (
    actualizar_configuracion_mayorista,
    obtener_configuracion_mayorista,
)
from routers.pedido_router import (
    crear_pedido,
    listar_pedidos,
    router as pedido_router,
)
from routers.reporte_router import (
    reporte_inventario,
    reporte_ventas,
    router as reporte_router,
)
from seed import PRODUCTOS, poblar_datos
from routers.venta_router import listar_ventas


class SprintSixSevenTests(unittest.TestCase):
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

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def _add_catalogue(self):
        self.session.add(Rol(id_rol=1, nombre="Propietario"))
        self.session.add(
            Usuario(
                id_usuario=1,
                Nombres="Dueño",
                apellidos="Prueba",
                correo="owner@example.com",
                password_hash="not-used",
                rol_id=1,
            )
        )
        category = Categoria(nombre="Herramientas")
        location = Ubicacion(pasillo="A", estante="1", nivel="1")
        self.session.add(category)
        self.session.add(location)
        self.session.flush()
        product = Producto(
            codigo="HER-001",
            nombre="Martillo",
            marca="Bimetálica",
            medida_presentacion="Unidad",
            precio_compra=Decimal("5.00"),
            precio_venta=Decimal("10.00"),
            stock_actual=4,
            stock_minimo=1,
            categoria_id=category.id_categoria,
            ubicacion_id=location.id_ubicacion,
        )
        self.session.add(product)
        self.session.commit()
        return product

    def test_sales_report_aggregates_date_range_and_best_sellers(self):
        product = self._add_catalogue()
        self.session.add_all(
            [
                Venta(
                    id_venta=1,
                    usuario_id=1,
                    fecha_hora=datetime(2026, 10, 10, 12, tzinfo=timezone.utc),
                    subtotal=Decimal("20.00"),
                    iva=Decimal("2.60"),
                    total_pagar=Decimal("22.60"),
                ),
                Venta(
                    id_venta=2,
                    usuario_id=1,
                    fecha_hora=datetime(2026, 10, 11, 12, tzinfo=timezone.utc),
                    subtotal=Decimal("10.00"),
                    iva=Decimal("1.30"),
                    total_pagar=Decimal("11.30"),
                ),
            ]
        )
        self.session.flush()
        self.session.add_all(
            [
                DetalleVenta(
                    venta_id=1,
                    producto_id=product.id_producto,
                    cantidad_id=2,
                    precio_unitario=Decimal("10.00"),
                    subtotal=Decimal("20.00"),
                ),
                DetalleVenta(
                    venta_id=2,
                    producto_id=product.id_producto,
                    cantidad_id=1,
                    precio_unitario=Decimal("10.00"),
                    subtotal=Decimal("10.00"),
                ),
            ]
        )
        self.session.commit()

        report = asyncio.run(
            reporte_ventas(
                self.session,
                {"id_rol": 1},
                date(2026, 10, 10),
                date(2026, 10, 11),
                10,
            )
        )

        self.assertEqual(report["total_ventas"], 2)
        self.assertEqual(report["subtotal"], Decimal("30"))
        self.assertEqual(report["iva"], Decimal("3.9"))
        self.assertEqual(report["ingresos"], Decimal("33.9"))
        self.assertEqual(len(report["ventas_por_dia"]), 2)
        self.assertEqual(report["productos_mas_vendidos"][0]["cantidad_vendida"], 3)

    def test_sales_report_rejects_reversed_range_and_non_owner(self):
        with self.assertRaises(HTTPException) as error:
            asyncio.run(
                reporte_ventas(
                    self.session,
                    {"id_rol": 1},
                    date(2026, 10, 12),
                    date(2026, 10, 11),
                    10,
                )
            )
        self.assertEqual(error.exception.status_code, 422)

        with self.assertRaises(HTTPException) as error:
            asyncio.run(
                reporte_ventas(
                    self.session,
                    {"id_rol": 2},
                    None,
                    None,
                    10,
                )
            )
        self.assertEqual(error.exception.status_code, 403)

    def test_inventory_report_calculates_cost_and_sale_value(self):
        product = self._add_catalogue()
        report = asyncio.run(
            reporte_inventario(self.session, {"id_rol": 1})
        )
        self.assertEqual(report["total_productos"], 1)
        self.assertEqual(report["unidades_disponibles"], 4)
        self.assertEqual(report["valor_inventario_compra"], Decimal("20"))
        self.assertEqual(report["valor_inventario_venta"], Decimal("40"))
        self.assertEqual(report["por_categoria"][0]["categoria"], "Herramientas")

        with self.assertRaises(HTTPException) as error:
            asyncio.run(reporte_inventario(self.session, {"id_rol": 2}))
        self.assertEqual(error.exception.status_code, 403)

        product.estado = False
        self.session.add(product)
        self.session.commit()
        empty_report = asyncio.run(
            reporte_inventario(self.session, {"id_rol": 1})
        )
        self.assertEqual(empty_report["total_productos"], 0)
        self.assertEqual(empty_report["unidades_disponibles"], 0)

    def test_seed_creates_demo_data_once_and_requires_passwords(self):
        passwords = {
            "SEED_OWNER_PASSWORD": "owner-test-password",
            "SEED_EMPLOYEE_PASSWORD": "employee-test-password",
            "SEED_CUSTOMER_PASSWORD": "customer-test-password",
        }
        with patch("seed.get_password_hash", side_effect=lambda value: f"hash:{value}"):
            first = poblar_datos(self.session, passwords)
            second = poblar_datos(self.session, passwords)

        self.assertEqual(first["roles"], 3)
        self.assertEqual(first["categorias"], 5)
        self.assertEqual(first["ubicaciones"], 5)
        self.assertEqual(first["productos"], len(PRODUCTOS))
        self.assertEqual(first["usuarios"], 3)
        self.assertTrue(all(count == 0 for count in second.values()))
        self.assertEqual(len(self.session.exec(select(Producto)).all()), 20)
        self.assertEqual(len(self.session.exec(select(Usuario)).all()), 3)

        with self.assertRaises(ValueError):
            poblar_datos(self.session, {})

    def test_http_report_routes_validate_inputs_and_enforce_roles(self):
        self._add_catalogue()
        app = FastAPI()
        app.include_router(reporte_router)

        def session_override():
            with Session(self.engine, expire_on_commit=False) as session:
                yield session

        app.dependency_overrides[get_session] = session_override
        app.dependency_overrides[get_current_user] = lambda: {"id_rol": 1}
        with TestClient(app) as client:
            inventory_response = client.get("/reportes/inventario")
            invalid_date_response = client.get(
                "/reportes/ventas?fecha_inicio=no-es-fecha"
            )
            reversed_range_response = client.get(
                "/reportes/ventas"
                "?fecha_inicio=2026-10-12&fecha_fin=2026-10-11"
            )

        self.assertEqual(inventory_response.status_code, 200)
        self.assertEqual(
            inventory_response.json()["valor_inventario_venta"],
            40.0,
        )
        self.assertEqual(invalid_date_response.status_code, 422)
        self.assertEqual(reversed_range_response.status_code, 422)

        app.dependency_overrides[get_current_user] = lambda: {"id_rol": 2}
        with TestClient(app) as client:
            forbidden_response = client.get("/reportes/inventario")
        self.assertEqual(forbidden_response.status_code, 403)

    def test_owner_configures_wholesale_threshold_and_staff_sees_priority(self):
        product = self._add_catalogue()
        self.session.add_all(
            [
                Rol(id_rol=2, nombre="Empleado"),
                Rol(id_rol=3, nombre="Cliente"),
                Usuario(
                    id_usuario=2,
                    Nombres="Empleado",
                    apellidos="Prueba",
                    correo="staff@example.com",
                    password_hash="not-used",
                    rol_id=2,
                ),
                Usuario(
                    id_usuario=3,
                    Nombres="Cliente",
                    apellidos="Mayorista",
                    correo="buyer@example.com",
                    password_hash="not-used",
                    rol_id=3,
                ),
            ]
        )
        self.session.add(
            Venta(
                usuario_id=2,
                cliente_usuario_id=3,
                subtotal=Decimal("300.00"),
                iva=Decimal("39.00"),
                total_pagar=Decimal("339.00"),
            )
        )
        self.session.commit()
        asyncio.run(
            actualizar_configuracion_mayorista(
                ConfiguracionMayoristaUpdate(umbral_mayorista=Decimal("250")),
                self.session,
                {"id_rol": 1},
            )
        )
        self.session.commit()
        pedido = asyncio.run(
            crear_pedido(
                PedidoCreate(
                    items=[PedidoItemCreate(producto_id=product.id_producto, cantidad=1)],
                    datos_cliente=DatosPedidoCreate(
                        tipo_cliente="Natural",
                        nombre_razon_social="Cliente Mayorista",
                        correo="buyer@example.com",
                        telefono="555-0401",
                        numero_documento="ID-WHOLESALE",
                        direccion="Dirección cliente",
                    ),
                ),
                self.session,
                {"id": 3, "id_rol": 3},
            )
        )

        staff_orders = asyncio.run(
            listar_pedidos(self.session, {"id": 2, "id_rol": 2})
        )
        prioritized = next(
            order for order in staff_orders if order.id_pedido == pedido.id_pedido
        )
        self.assertTrue(prioritized.prioridad_mayorista)
        self.assertEqual(prioritized.compras_12_meses, Decimal("339.00"))

        asyncio.run(
            actualizar_configuracion_mayorista(
                ConfiguracionMayoristaUpdate(umbral_mayorista=None),
                self.session,
                {"id_rol": 1},
            )
        )
        settings = asyncio.run(
            obtener_configuracion_mayorista(self.session, {"id_rol": 1})
        )
        self.assertIsNone(settings["umbral_mayorista"])
        self.assertFalse(settings["prioridad_activa"])

        with self.assertRaises(HTTPException) as error:
            asyncio.run(
                actualizar_configuracion_mayorista(
                    ConfiguracionMayoristaUpdate(umbral_mayorista=Decimal("250")),
                    self.session,
                    {"id_rol": 2},
                )
            )
        self.assertEqual(error.exception.status_code, 403)

    def test_employee_sales_history_is_limited_to_own_sales(self):
        self._add_catalogue()
        self.session.add_all(
            [
                Rol(id_rol=2, nombre="Empleado"),
                Rol(id_rol=3, nombre="Cliente"),
                Usuario(
                    id_usuario=2,
                    Nombres="Empleado",
                    apellidos="Uno",
                    correo="employee-one@example.com",
                    password_hash="not-used",
                    rol_id=2,
                ),
                Usuario(
                    id_usuario=3,
                    Nombres="Empleado",
                    apellidos="Dos",
                    correo="employee-two@example.com",
                    password_hash="not-used",
                    rol_id=2,
                ),
            ]
        )
        self.session.flush()
        self.session.add_all(
            [
                Venta(
                    usuario_id=2,
                    subtotal=Decimal("10"),
                    iva=Decimal("1.3"),
                    total_pagar=Decimal("11.3"),
                ),
                Venta(
                    usuario_id=3,
                    subtotal=Decimal("20"),
                    iva=Decimal("2.6"),
                    total_pagar=Decimal("22.6"),
                ),
            ]
        )
        self.session.commit()
        employee_sales = asyncio.run(
            listar_ventas(self.session, {"id": 2, "id_rol": 2})
        )
        owner_sales = asyncio.run(
            listar_ventas(self.session, {"id": 1, "id_rol": 1})
        )
        self.assertEqual(len(employee_sales), 1)
        self.assertEqual(employee_sales[0].usuario_id, 2)
        self.assertEqual(len(owner_sales), 2)

    def test_guest_checkout_is_public_and_receipt_code_is_sent_in_header(self):
        product = self._add_catalogue()
        app = FastAPI()
        app.include_router(pedido_router)

        def session_override():
            with Session(self.engine, expire_on_commit=False) as session:
                yield session

        app.dependency_overrides[get_session] = session_override
        with TestClient(app) as client:
            response = client.post(
                "/pedidos/invitado",
                json={
                    "items": [
                        {"producto_id": product.id_producto, "cantidad": 1}
                    ],
                    "datos_cliente": {
                        "tipo_cliente": "Natural",
                        "nombre_razon_social": "Compra Invitado",
                        "correo": "guest@example.com",
                        "telefono": "555-0501",
                        "numero_documento": "ID-501",
                        "direccion": "Dirección invitado",
                    },
                },
            )
            self.assertEqual(response.status_code, 201)
            body = response.json()
            code = body["codigo_acceso"]
            self.assertNotIn("codigo_acceso_hash", body["pedido"])
            lookup = client.get(
                "/pedidos/consulta",
                headers={"X-Order-Access-Code": code},
            )
            self.assertEqual(lookup.status_code, 200)
            self.assertEqual(
                lookup.json()["pedido"]["correo_cliente"],
                "guest@example.com",
            )



if __name__ == "__main__":
    unittest.main()
