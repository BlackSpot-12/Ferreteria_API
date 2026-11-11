import os
from datetime import datetime, timezone

from sqlmodel import Session, select

import main  # noqa: F401 - registra todos los modelos en SQLModel.metadata
from config.db import engine
from lib.pwd import get_password_hash
from models.categoria import Categoria
from models.email import UserEmailVerification
from models.producto import Producto
from models.rol import Rol
from models.ubicacion import Ubicacion
from models.usuario import Usuario

ROLES = (
    (1, "Propietario", "Administrador del negocio"),
    (2, "Empleado", "Personal de ventas e inventario"),
    (3, "Cliente", "Cliente de la ferretería"),
)

CATEGORIAS = (
    "Plomería",
    "Electricidad",
    "Herramientas",
    "Pinturas",
    "Construcción",
)

UBICACIONES = (
    ("A", "1", "1"),
    ("A", "2", "1"),
    ("B", "1", "2"),
    ("B", "2", "2"),
    ("C", "1", "1"),
)

PRODUCTOS = (
    ("PLO-001", "Tubo PVC 1/2 pulgada", "HidroMax", "3 m", "3.25", "5.50", 35, 8, "Plomería", 0),
    ("PLO-002", "Codo PVC 1/2 pulgada", "HidroMax", "Unidad", "0.35", "0.75", 80, 15, "Plomería", 0),
    ("PLO-003", "Llave de paso 1/2 pulgada", "AquaPro", "Unidad", "4.20", "7.90", 18, 5, "Plomería", 1),
    ("PLO-004", "Cinta de teflón", "Sellaflex", "Rollo", "0.45", "1.00", 55, 12, "Plomería", 1),
    ("ELE-001", "Cable eléctrico calibre 12", "Voltix", "Metro", "0.65", "1.20", 120, 25, "Electricidad", 2),
    ("ELE-002", "Tomacorriente doble", "Voltix", "Unidad", "2.10", "4.00", 30, 8, "Electricidad", 2),
    ("ELE-003", "Interruptor sencillo", "Lumen", "Unidad", "1.40", "2.75", 24, 6, "Electricidad", 2),
    ("ELE-004", "Bombillo LED 9 W", "Lumen", "Unidad", "1.75", "3.50", 40, 10, "Electricidad", 3),
    ("HER-001", "Martillo de uña 16 oz", "Fuerza", "Unidad", "5.50", "9.90", 16, 4, "Herramientas", 3),
    ("HER-002", "Destornillador plano mediano", "Fuerza", "Unidad", "1.80", "3.50", 22, 5, "Herramientas", 3),
    ("HER-003", "Alicate universal 8 pulgadas", "Fuerza", "Unidad", "4.75", "8.50", 14, 4, "Herramientas", 3),
    ("HER-004", "Cinta métrica 5 metros", "Meditek", "Unidad", "2.80", "5.25", 19, 5, "Herramientas", 4),
    ("PIN-001", "Pintura blanca interior", "ColorCasa", "Galón", "14.00", "22.50", 12, 3, "Pinturas", 4),
    ("PIN-002", "Brocha 2 pulgadas", "ColorCasa", "Unidad", "1.25", "2.50", 28, 7, "Pinturas", 4),
    ("PIN-003", "Rodillo para pintar 9 pulgadas", "ColorCasa", "Unidad", "3.40", "6.25", 17, 4, "Pinturas", 4),
    ("CON-001", "Cemento gris", "Firme", "Bolsa 42.5 kg", "8.75", "12.50", 50, 12, "Construcción", 0),
    ("CON-002", "Clavo para madera 2 pulgadas", "MetalForte", "Libra", "1.10", "2.00", 32, 8, "Construcción", 0),
    ("CON-003", "Tornillo para madera 1 pulgada", "MetalForte", "Caja 100", "2.20", "4.25", 21, 5, "Construcción", 1),
    ("CON-004", "Lija para madera grano 120", "Abrasivos", "Hoja", "0.30", "0.75", 65, 15, "Construcción", 1),
    ("PLO-005", "Manguera reforzada 1/2 pulgada", "AquaPro", "Metro", "1.60", "3.00", 26, 6, "Plomería", 1),
)

USUARIOS = (
    ("propietario@ferreteria.local", "Propietario", "Demostración", 1, "SEED_OWNER_PASSWORD"),
    ("empleado@ferreteria.local", "Empleado", "Demostración", 2, "SEED_EMPLOYEE_PASSWORD"),
    ("cliente@ferreteria.local", "Cliente", "Demostración", 3, "SEED_CUSTOMER_PASSWORD"),
)


def poblar_datos(session: Session, passwords: dict[str, str]) -> dict[str, int]:
    required_passwords = {env_name for *_, env_name in USUARIOS}
    missing = sorted(name for name in required_passwords if not passwords.get(name))
    if missing:
        raise ValueError(
            "Define contraseñas de demostración en estas variables de entorno: "
            + ", ".join(missing)
        )

    counts = {"roles": 0, "categorias": 0, "ubicaciones": 0, "productos": 0, "usuarios": 0}
    for role_id, name, description in ROLES:
        role = session.get(Rol, role_id)
        if role is not None and role.nombre != name:
            raise RuntimeError(
                f"El rol con id {role_id} ya existe con otro nombre; "
                "no se modificó la base de datos."
            )
        if role is None:
            existing = session.exec(select(Rol).where(Rol.nombre == name)).first()
            if existing is not None:
                raise RuntimeError(
                    f"El rol '{name}' existe con id {existing.id_rol}; "
                    f"se esperaba id {role_id}."
                )
            session.add(
                Rol(id_rol=role_id, nombre=name, descripcion=description)
            )
            counts["roles"] += 1
    session.flush()

    categories = {}
    for name in CATEGORIAS:
        category = session.exec(
            select(Categoria).where(Categoria.nombre == name)
        ).first()
        if category is None:
            category = Categoria(nombre=name)
            session.add(category)
            session.flush()
            counts["categorias"] += 1
        categories[name] = category

    locations = []
    for aisle, shelf, level in UBICACIONES:
        location = session.exec(
            select(Ubicacion).where(
                Ubicacion.pasillo == aisle,
                Ubicacion.estante == shelf,
                Ubicacion.nivel == level,
            )
        ).first()
        if location is None:
            location = Ubicacion(pasillo=aisle, estante=shelf, nivel=level)
            session.add(location)
            session.flush()
            counts["ubicaciones"] += 1
        locations.append(location)

    for row in PRODUCTOS:
        (
            code,
            name,
            brand,
            measure,
            purchase_price,
            sale_price,
            stock,
            minimum,
            category_name,
            location_index,
        ) = row
        exists = session.exec(
            select(Producto).where(Producto.codigo == code)
        ).first()
        if exists is not None:
            continue
        session.add(
            Producto(
                codigo=code,
                nombre=name,
                marca=brand,
                medida_presentacion=measure,
                precio_compra=purchase_price,
                precio_venta=sale_price,
                stock_actual=stock,
                stock_minimo=minimum,
                estado=True,
                categoria_id=categories[category_name].id_categoria,
                ubicacion_id=locations[location_index].id_ubicacion,
            )
        )
        counts["productos"] += 1

    for email, first_name, last_name, role_id, password_env in USUARIOS:
        existing = session.exec(
            select(Usuario).where(Usuario.correo == email)
        ).first()
        if existing is not None:
            continue
        user = Usuario(
            Nombres=first_name,
            apellidos=last_name,
            correo=email,
            password_hash=get_password_hash(passwords[password_env]),
            rol_id=role_id,
        )
        session.add(user)
        session.flush()
        session.add(
            UserEmailVerification(
                usuario_id=user.id_usuario,
                verificado=True,
                verified_at=datetime.now(timezone.utc),
            )
        )
        counts["usuarios"] += 1

    session.commit()
    return counts


def main_cli() -> None:
    # Importing main registers every SQLModel table before create_all.
    from config.db import crear_db_y_tablas

    crear_db_y_tablas()
    passwords = {
        key: os.getenv(key, "")
        for key in (
            "SEED_OWNER_PASSWORD",
            "SEED_EMPLOYEE_PASSWORD",
            "SEED_CUSTOMER_PASSWORD",
        )
    }
    with Session(engine) as session:
        counts = poblar_datos(session, passwords)
    print("Seeder completado (los registros existentes se conservaron):")
    for name, count in counts.items():
        print(f"- {name}: {count} creados")
    print("Cuentas de prueba: propietario@ferreteria.local, "
          "empleado@ferreteria.local, cliente@ferreteria.local")


if __name__ == "__main__":
    main_cli()
