import asyncio
import os
import unittest
from decimal import Decimal
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import main
from models.categoria import Categoria
from models.datos_facturacion import DatosFacturacion
from models.detalle_venta import DetalleVenta
from models.producto import Producto, ProductoBusquedaEmpleado
from models.pedido import PedidoCreate, PedidoItemCreate, PedidoUpdate
from models.rol import Rol
from models.ubicacion import Ubicacion
from models.usuario import Usuario
from models.venta import (
    FacturaDatosCreate,
    VentaItemCreate,
    VentaPOSCreate,
)
from routers.producto_router import buscar_catalogo_publico, buscar_productos_empleado
from routers.detalle_pedido_router import listar_detalles_pedido
from routers.pedido_router import (
    actualizar_estado_pedido,
    crear_pedido,
    listar_pedidos,
    obtener_pedido,
)
from routers.venta_router import obtener_factura, procesar_venta
from config.segurity import create_access_token, get_current_user, validate_token_config


class SprintThreeFourTests(unittest.TestCase):
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
        self.session.add(
            Rol(id_rol=2, nombre="Empleado", descripcion="Empleado de prueba")
        )
        self.session.add(
            Rol(id_rol=3, nombre="Cliente", descripcion="Cliente de prueba")
        )
        self.session.commit()
        self.session.add(
            Usuario(
                id_usuario=11,
                Nombres="Empleado",
                apellidos="Prueba",
                correo="empleado@example.com",
                password_hash="not-used-in-this-test",
                rol_id=2,
            )
        )
        self.session.add(
            Usuario(
                id_usuario=12,
                Nombres="Cliente",
                apellidos="Uno",
                correo="cliente@example.com",
                password_hash="not-used-in-this-test",
                rol_id=3,
            )
        )
        self.session.add(
            Usuario(
                id_usuario=13,
                Nombres="Cliente",
                apellidos="Dos",
                correo="otro@example.com",
                password_hash="not-used-in-this-test",
                rol_id=3,
            )
        )
        categoria = Categoria(nombre="Herramientas")
        ubicacion = Ubicacion(pasillo="A", estante="2", nivel="1")
        self.session.add(categoria)
        self.session.add(ubicacion)
        self.session.flush()
        self.producto = Producto(
            codigo="MART-01",
            nombre="Martillo",
            marca="FerreMax",
            medida_presentacion="Unidad",
            precio_compra=Decimal("50.00"),
            precio_venta=Decimal("100.00"),
            stock_actual=5,
            stock_minimo=2,
            categoria_id=categoria.id_categoria,
            ubicacion_id=ubicacion.id_ubicacion,
        )
        self.session.add(self.producto)
        self.session.commit()
        self.producto_id = self.producto.id_producto

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_catalogue_search_filters_and_hides_internal_stock(self):
        result = asyncio.run(
            buscar_catalogo_publico(
                self.session,
                codigo="MART",
                nombre="mart",
                marca="ferre",
                categoria="herram",
                medida="unidad",
                offset=0,
                limit=20,
            )
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].codigo, "MART-01")
        self.assertFalse(hasattr(result[0], "stock_actual"))

    def test_employee_search_includes_exact_location_and_stock(self):
        result = asyncio.run(
            buscar_productos_empleado(
                self.session,
                {"id_rol": 2},
                codigo="MART",
                nombre=None,
                marca=None,
                categoria=None,
                medida=None,
                offset=0,
                limit=20,
            )
        )
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], ProductoBusquedaEmpleado)
        self.assertEqual(result[0].stock_actual, 5)
        self.assertEqual((result[0].pasillo, result[0].estante, result[0].nivel), ("A", "2", "1"))

    def test_customer_cannot_use_employee_inventory_search(self):
        with self.assertRaises(HTTPException) as error:
            asyncio.run(
                buscar_productos_empleado(
                    self.session,
                    {"id_rol": 3},
                    codigo=None,
                    nombre=None,
                    marca=None,
                    categoria=None,
                    medida=None,
                    offset=0,
                    limit=20,
                )
            )
        self.assertEqual(error.exception.status_code, 403)

    def test_pos_calculates_tax_and_decrements_stock(self):
        payload = VentaPOSCreate(
            items=[VentaItemCreate(producto_id=self.producto_id, cantidad=2)],
            datos_facturacion=FacturaDatosCreate(
                tipo_cliente="Natural",
                nombre_razon_social="Ana López",
                numero_documento="DOC-123",
            ),
        )
        result = asyncio.run(
            procesar_venta(payload, self.session, {"id": 11, "id_rol": 2})
        )

        self.assertEqual(result.subtotal, Decimal("200.00"))
        self.assertEqual(result.iva, Decimal("26.00"))
        self.assertEqual(result.total_pagar, Decimal("226.00"))
        self.assertEqual(result.detalles[0].cantidad, 2)
        self.session.refresh(self.producto)
        self.assertEqual(self.producto.stock_actual, 3)
        self.assertEqual(len(self.session.exec(select(DetalleVenta)).all()), 1)
        self.assertEqual(len(self.session.exec(select(DatosFacturacion)).all()), 1)
        with patch.dict(
            os.environ,
            {
                "FACTURA_RAZON_SOCIAL": "Ferretería Ejemplo",
                "FACTURA_IDENTIFICACION": "TAX-EMPRESA",
                "FACTURA_DIRECCION": "Dirección de prueba",
                "FACTURA_TELEFONO": "555-0100",
            },
        ):
            factura = asyncio.run(
                obtener_factura(
                    result.id_venta,
                    self.session,
                    {"id": 11, "id_rol": 2},
                )
            )
        self.assertEqual(factura.emisor.nombre, "Ferretería Ejemplo")
        self.assertEqual(factura.tipo_cliente, "Natural")
        self.assertEqual(factura.iva_porcentaje, Decimal("0.13"))

    def test_pos_rejects_insufficient_stock_without_partial_writes(self):
        payload = VentaPOSCreate(
            items=[VentaItemCreate(producto_id=self.producto_id, cantidad=6)],
            datos_facturacion=FacturaDatosCreate(
                tipo_cliente="Juridico",
                nombre_razon_social="Comercial Ejemplo S.A.",
                numero_documento="TAX-123",
            ),
        )
        with self.assertRaises(HTTPException) as error:
            asyncio.run(
                procesar_venta(payload, self.session, {"id": 11, "id_rol": 2})
            )

        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(len(self.session.exec(select(DetalleVenta)).all()), 0)
        self.assertEqual(len(self.session.exec(select(DatosFacturacion)).all()), 0)
        self.session.refresh(self.producto)
        self.assertEqual(self.producto.stock_actual, 5)

    def test_invoice_fails_explicitly_when_issuer_configuration_is_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HTTPException) as error:
                asyncio.run(
                    obtener_factura(
                        1,
                        self.session,
                        {"id": 11, "id_rol": 2},
                    )
                )
        self.assertEqual(error.exception.status_code, 503)

    def test_customer_orders_are_scoped_and_owner_is_taken_from_token(self):
        order_session = Session(self.engine, expire_on_commit=False)
        order_one = asyncio.run(
            crear_pedido(
                PedidoCreate(
                    items=[PedidoItemCreate(producto_id=self.producto_id, cantidad=2)]
                ),
                order_session,
                {"id": 12, "id_rol": 3},
            )
        )
        order_session.close()

        order_session = Session(self.engine, expire_on_commit=False)
        order_two = asyncio.run(
            crear_pedido(
                PedidoCreate(
                    items=[PedidoItemCreate(producto_id=self.producto_id, cantidad=1)]
                ),
                order_session,
                {"id": 13, "id_rol": 3},
            )
        )
        order_session.close()

        self.assertEqual(order_one.usuario_id, 12)
        self.assertEqual(order_one.total_pedido, Decimal("200.00"))
        self.assertEqual(order_two.usuario_id, 13)

        order_session = Session(self.engine, expire_on_commit=False)
        customer_orders = asyncio.run(
            listar_pedidos(order_session, {"id": 12, "id_rol": 3})
        )
        order_session.close()
        self.assertEqual([order.id_pedido for order in customer_orders], [order_one.id_pedido])

        order_session = Session(self.engine, expire_on_commit=False)
        with self.assertRaises(HTTPException) as error:
            asyncio.run(
                obtener_pedido(order_two.id_pedido, order_session, {"id": 12, "id_rol": 3})
            )
        order_session.close()
        self.assertEqual(error.exception.status_code, 404)

        order_session = Session(self.engine, expire_on_commit=False)
        with self.assertRaises(HTTPException) as error:
            asyncio.run(
                listar_detalles_pedido(
                    order_two.id_pedido,
                    order_session,
                    {"id": 12, "id_rol": 3},
                )
            )
        order_session.close()
        self.assertEqual(error.exception.status_code, 404)

    def test_customer_cannot_supply_order_owner_total_or_status(self):
        with self.assertRaises(ValueError):
            PedidoCreate.model_validate(
                {
                    "usuario_id": 13,
                    "estado": "Entregado",
                    "total_pedido": 0,
                    "items": [{"producto_id": self.producto_id, "cantidad": 1}],
                }
            )
        with self.assertRaises(ValueError):
            PedidoUpdate.model_validate({"estado": "Entregado", "total_pedido": 0})

    def test_only_staff_can_advance_order_state(self):
        pedido = asyncio.run(
            crear_pedido(
                PedidoCreate(
                    items=[PedidoItemCreate(producto_id=self.producto_id, cantidad=1)]
                ),
                self.session,
                {"id": 12, "id_rol": 3},
            )
        )
        with self.assertRaises(HTTPException) as error:
            asyncio.run(
                actualizar_estado_pedido(
                    pedido.id_pedido,
                    PedidoUpdate(estado="En preparacion"),
                    self.session,
                    {"id": 12, "id_rol": 3},
                )
            )
        self.assertEqual(error.exception.status_code, 403)

        updated = asyncio.run(
            actualizar_estado_pedido(
                pedido.id_pedido,
                PedidoUpdate(estado="En preparacion"),
                self.session,
                {"id": 11, "id_rol": 2},
            )
        )
        self.assertEqual(updated.estado, "En preparacion")

    def test_customer_token_uses_current_database_role_not_stale_claim(self):
        with patch.dict(os.environ, {"SECRET_KEY_TOKEN": "a" * 48}):
            token = create_access_token({"id": 11, "id_rol": 1})
            auth_session = Session(self.engine, expire_on_commit=False)
            with patch("config.segurity.Session", return_value=auth_session):
                identity = get_current_user(token)
        self.assertEqual(identity["id_rol"], 2)
        self.assertEqual(identity["username"], "empleado@example.com")

    def test_jwt_secret_must_be_configured_and_strong_enough(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                validate_token_config()
        with patch.dict(os.environ, {"SECRET_KEY_TOKEN": "short"}):
            with self.assertRaises(RuntimeError):
                validate_token_config()


if __name__ == "__main__":
    unittest.main()
