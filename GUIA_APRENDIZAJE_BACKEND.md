# Guía para aprender y mantener el backend de Ferretería

Esta guía no busca que memorices archivos ni que copies código a ciegas. Busca que puedas explicar por qué existe cada pieza, qué condiciones debe cumplir una operación y cómo comprobar que un cambio funciona y no abrió un agujero de seguridad.

Úsala junto con el cronograma de sprints y el código fuente. El código es la implementación actual; esta guía también marca límites que hay que corregir antes de considerar el sistema listo para producción.

## 1. Cómo pensar antes de programar

Ante cada requisito, responde estas preguntas antes de abrir el editor:

1. **¿Quién usa la función?** Cliente, empleado o propietario.
2. **¿Qué recurso modifica o consulta?** Producto, pedido, venta, etc.
3. **¿Qué puede hacer cada rol?** Define permisos para cada operación y para cada registro, no solo para cada ruta.
4. **¿Qué reglas de negocio deben cumplirse?** Por ejemplo, una venta no puede dejar stock negativo.
5. **¿Qué datos son confiables?** El cliente puede alterar cualquier valor que envíe; el servidor debe calcular precios, totales, rol y propietario del registro.
6. **¿Qué pasa si falla?** Decide qué respuesta HTTP dar y cómo evitar escrituras parciales.
7. **¿Cómo voy a demostrar que funciona?** Escribe casos válidos, inválidos, no autenticados y sin permisos.

Una ruta que “responde 200” no demuestra que esté bien. También hay que probar que rechaza entradas inválidas y que un usuario no puede ver o modificar datos ajenos.

## 2. Mapa mental de una petición

Una petición típica sigue este recorrido:

```text
Cliente / Flutter / Swagger
        │ método HTTP, ruta, JSON y token
        ▼
FastAPI registra la ruta desde main.py
        ▼
Router valida el body y aplica autorización
        ├── Token_Dependencia → verifica JWT e identidad
        └── SessionDeDependencia → abre sesión de base de datos
        ▼
SQLModel consulta o modifica el modelo
        ▼
MySQL aplica tipos, índices y llaves foráneas
        ▼
FastAPI serializa la respuesta y devuelve el status HTTP
```

Cuando algo falla, sigue el recorrido de abajo hacia arriba. Por ejemplo:

- `ERR_CONNECTION_REFUSED`: no hay servidor escuchando en esa dirección/puerto.
- Error durante startup: el proceso de arranque (por ejemplo, conexión a MySQL) falla antes de registrar peticiones.
- `401`: falta el token o no es válido.
- `403`: el usuario está autenticado, pero no tiene permiso.
- `404`: el recurso pedido no existe o se decidió no revelar su existencia.
- `422`: el body, los parámetros o sus tipos no cumplen el esquema.
- `500`: error no manejado; revisa la excepción completa del servidor, no solo la respuesta del navegador.
- Error MySQL de llave foránea: se envió una referencia a una fila inexistente o las tablas/modelos no están alineados.

## 3. Dónde vive cada responsabilidad

| Ubicación | Responsabilidad | Pregunta que debes hacerte |
|---|---|---|
| `main.py` | Crea FastAPI, importa modelos y registra routers | ¿La app incluyó la ruta y cargó la metadata de todos los modelos? |
| `config/db.py` | Configura el engine y la conexión MySQL | ¿La aplicación apunta a la base, host, puerto y credenciales correctos? |
| `config/session_Dependencia.py` | Proporciona una sesión SQLModel por petición | ¿Se abre y se cierra la sesión correctamente? |
| `config/segurity.py` | Crea/decodifica JWT y obtiene identidad desde el token | ¿Se valida expiración, firma y estructura de claims? |
| `config/segurity_Dependencia.py` | Expone dependencias para formularios OAuth2 y tokens | ¿La ruta que requiere identidad incluye la dependencia? |
| `models/` | Representa tablas SQL y esquemas de entrada/salida | ¿Nombres, tipos, longitudes, nulabilidad y FKs coinciden con SQL? |
| `routers/` | Define rutas HTTP, permisos, reglas de negocio y persistencia | ¿La operación valida autorización y no confía en datos manipulables? |
| `lib/pwd.py` | Hash y verificación de contraseñas | ¿Se guarda solo el hash, nunca la contraseña original? |
| `.env` | Configuración local sensible | ¿Está fuera del control de versiones y no contiene secretos publicados? |

Mantén una sola fuente de verdad para cada concepto. No dupliques el modelo de una tabla en varios módulos. Si hay que moverlo, actualiza imports y pruebas en el mismo cambio.

## 4. Base de datos y ORM

La base SQL define la estructura persistente. SQLModel describe esa estructura a Python; no sustituye una migración.

### Al cambiar una tabla

Compara sistemáticamente:

- nombre de tabla y de columnas (incluida capitalización cuando el servidor sea sensible a ella);
- tipos SQL y tipos Python (`DECIMAL` ↔ `Decimal`, `DATETIME` ↔ `datetime`);
- `NULL` / `NOT NULL`, valores por defecto y longitudes;
- claves primarias, `UNIQUE`, índices y claves foráneas;
- acciones `ON DELETE` y `ON UPDATE`.

`SQLModel.metadata.create_all(engine)` crea tablas faltantes; **no modifica las tablas existentes para que coincidan con modelos nuevos**. Para cambiar una base ya creada se necesita una migración o un procedimiento explícito y respaldado. Nunca asumas que reiniciar FastAPI actualizó MySQL.

Las tablas base tienen dependencias: primero roles, categorías y ubicaciones; después usuarios y productos; finalmente ventas/pedidos y sus detalles. Una FK como `Usuario.rol_id → rol.id_rol` requiere que exista el rol antes del usuario.

No mezcles las antiguas tablas `usuarios`/`roles` con las del script `Usuario`/`rol`. Antes de una migración, inspecciona qué tablas existen y respalda los datos. No ejecutes `DROP TABLE` en una base que contenga información que debas conservar.

### Dinero e inventario

- Usa `Decimal` para importes; los `float` pueden introducir errores de redondeo.
- Valida rangos y valores positivos en la entrada.
- La base protege integridad estructural; el servidor debe proteger reglas de negocio.
- No aceptes del cliente el total calculado de una compra como fuente confiable.
- Una operación que descuenta existencias y crea venta/detalles debe ser una sola transacción. Si falla una parte, se revierte todo.

## 5. Autenticación y autorización no son lo mismo

- **Autenticación:** ¿quién eres? En este proyecto, login verifica correo y contraseña y devuelve un JWT.
- **Autorización:** ¿qué puedes hacer? La ruta comprueba rol y, cuando corresponda, que el recurso pertenezca al usuario.

El token es firmado, no cifrado: no guardes secretos dentro de sus claims. La contraseña se almacena como hash con `lib/pwd.py`. OAuth2PasswordBearer espera un token `Bearer`; Swagger permite obtenerlo con el endpoint de login.

Para cada ruta protegida revisa:

1. ¿Exige token?
2. ¿Qué roles permite esta acción?
3. ¿El usuario solo puede acceder a sus propios datos?
4. ¿Puede modificar campos que no debería, como `rol_id`, `usuario_id`, estado o totales?
5. ¿Qué ocurre con un token expirado, alterado o emitido antes de un cambio de rol?

### Límites de seguridad conocidos del código actual

Los endpoints son una base didáctica y **no deben tratarse como una implementación de producción**. Los pedidos ahora filtran los datos del cliente por propietario, crean sus detalles con precios calculados desde producto y permiten cambios de estado solo al personal en secuencia. Aun así:

- El registro asigna el rol cliente usando el ID `3`. Debe garantizarse mediante datos semilla/migración que ese ID corresponde al rol cliente; es más robusto buscarlo por nombre o tener una configuración estable. El registro público nunca debe aceptar un rol arbitrario.
- `SECRET_KEY_TOKEN` ya no usa una clave de respaldo; el arranque falla si falta o tiene menos de 32 caracteres. Genera el valor localmente con `python -c "import secrets; print(secrets.token_urlsafe(48))"` y no lo publiques. Las rutas protegidas consultan el usuario y rol actuales desde la base; esto agrega una lectura de BD por petición autenticada.
- El pedido en línea no reserva ni descuenta stock; eso debe decidirse e implementarse como parte de la política de cumplimiento del sprint 5 antes de aceptar pedidos para producción.
- La factura devuelta sigue siendo JSON de presentación, no un PDF ni una factura fiscal certificada. El nombre/código de producto histórico tampoco se conserva como snapshot en el esquema SQL.
- Las transacciones convierten errores de integridad en respuestas controladas; las excepciones operativas inesperadas deben seguir visibles en logs del servidor y no exponerse al cliente.

En los permisos de ejemplo se usan los IDs 1/2/3 para propietario/empleado/cliente. Los números de auto-incremento no son una política segura: primero garantiza los roles y evita que un seed accidental cambie su significado.

## 6. Cómo diseñar una función nueva: ejemplo de producto

Requisito: “un propietario o empleado puede registrar un producto y el producto debe tener categoría y ubicación existentes”.

Piensa así:

1. **Modelo:** identifica las columnas del SQL (`codigo`, precios, stock, `categoria_id`, `ubicacion_id`).
2. **Entrada:** crea un esquema de escritura que excluya el ID autogenerado. Valida longitudes, precios y stock.
3. **Autorización:** exige JWT y permite solo los roles definidos por el negocio.
4. **Integridad:** verifica categoría y ubicación; la FK en MySQL sigue siendo la última barrera.
5. **Duplicados:** valida el código, pero conserva también la restricción `UNIQUE` para carreras entre solicitudes.
6. **Persistencia:** agrega, hace commit y refresca el objeto.
7. **Respuesta:** devuelve un esquema que no exponga campos internos.
8. **Pruebas:** caso válido, código repetido, categoría/ubicación inexistente, token ausente, rol cliente y error de BD.

El `GET /productos` actual está orientado al mantenimiento. Para el catálogo público del cronograma, define una ruta pública separada que exponga únicamente productos activos y campos aptos para clientes. No quites controles del endpoint administrativo solo para que Flutter pueda cargar el catálogo.

## 7. Lectura del código que se trabajó

El código actual reúne:

- login por correo y contraseña y emisión de JWT en `routers/auth_router.py`;
- registro de cliente, creación administrativa y perfil en `routers/usuario_router.py`;
- modelos alineados al script SQL en `models/`;
- CRUD base de categorías, ubicaciones y productos en sus routers;
- endpoints CRUD básicos para ventas, pedidos, detalles y datos de facturación;
- registro de esos routers en `main.py`.

La diferencia entre “CRUD básico” y “función de negocio” es fundamental. Por ejemplo, un `POST /ventas` que inserta importes recibidos no implementa todavía el POS: el POS necesita calcular importes en el servidor, validar existencias, insertar encabezado y detalles, actualizar stock y emitir factura atómicamente.

## 8. Cronograma de 7 sprints visto desde el backend

El cronograma también incluye tareas Flutter. La lista aquí separa lo que corresponde al backend y marca lo que falta, en vez de confundir archivos creados con criterios de aceptación terminados.

| Sprint | Backend según el cronograma | Estado formativo del código actual |
|---|---|---|
| 1. Arquitectura y autenticación | Esquema, usuarios, login JWT y roles | Hay configuración, modelos y rutas base. Falta cerrar autorización por registro, roles iniciales, pruebas automatizadas y comprobar despliegue integrado. Flutter no forma parte del backend. |
| 2. Inventario | CRUD categoría/ubicación/producto y alertas de stock | Hay CRUD base para las tres entidades. Falta endpoint de stock bajo/agotar y pruebas/validaciones de negocio completas. |
| 3. Catálogos y búsqueda | Filtros por código, nombre, marca, categoría y medida | Pendiente. Diseñar filtros opcionales, paginación, orden y límites; evitar concatenar SQL manualmente. |
| 4. POS y facturación | Venta + detalles, cálculo, stock transaccional y factura | Solo hay CRUD básico de tablas relacionadas. Falta el caso de uso transaccional y la generación/formato de factura. |
| 5. Pedidos en línea | Pedidos del cliente, detalles, estados y gestión | Se implementó parcialmente junto con la revisión: el cliente ve solo sus pedidos; su identidad, precios, total, estado inicial y detalles se controlan en servidor; solo personal puede avanzar estados. El flujo frontend y pruebas MySQL/concurrencia siguen pendientes. |
| 6. Reportes | Ventas por periodo, productos vendidos, ingresos e inventario valorizado | Pendiente. Define zona horaria, intervalos inclusivos/exclusivos, moneda y permisos antes de agrupar datos. |
| 7. Calidad y despliegue | Seeders, pruebas, errores HTTP, carga y despliegue | Pendiente. Compilar/importar no sustituye pruebas automatizadas, prueba de carga, configuración de producción o despliegue. |

Para declarar un sprint terminado, traduce cada criterio del cronograma a pruebas reproducibles y guarda evidencia. No lo marques completo solo porque Swagger muestra una ruta.

### Implementación backend añadida para los sprints 3 y 4

El código ahora ofrece:

- `GET /catalogo/productos`: catálogo público de productos activos; acepta filtros opcionales `codigo`, `nombre`, `marca`, `categoria`, `medida`, `offset` y `limit`. La respuesta no incluye stock, costo de compra ni ubicación interna.
- `GET /productos/buscar`: misma búsqueda para propietario/empleado, con existencias, categoría y ubicación exacta. El cliente recibe `403`.
- `POST /ventas`: flujo POS para propietario/empleado. El body lleva productos y cantidades, y datos de facturación. El servidor lee precios vigentes de la base, calcula subtotal e IVA al 13% (indicado por el usuario), registra venta/detalles/facturación y descuenta inventario en una sola transacción. Una venta rechazada por stock insuficiente no deja filas ni descuenta existencias.
- `GET /ventas/{venta_id}/factura`: retorna una representación JSON formateada para mostrar/imprimir. Requiere configurar `FACTURA_RAZON_SOCIAL`, `FACTURA_IDENTIFICACION` y `FACTURA_DIRECCION`; `FACTURA_TELEFONO` es opcional. `.env.example` muestra los nombres esperados.

Ejemplo del body de `POST /ventas`:

```json
{
  "items": [
    {"producto_id": 8, "cantidad": 2},
    {"producto_id": 15, "cantidad": 1}
  ],
  "datos_facturacion": {
    "tipo_cliente": "Natural",
    "nombre_razon_social": "Nombre del cliente",
    "numero_documento": "IDENTIFICACION"
  }
}
```

No se manda `usuario_id`, precio ni total: el usuario que atiende se deriva del JWT y el precio se consulta en la base. `tipo_cliente` admite exactamente `Natural` o `Juridico`, como el `ENUM` del SQL. Las rutas independientes de escritura de detalles de venta y datos de facturación se retiraron para impedir saltarse el flujo transaccional del POS.

La respuesta de factura es un documento JSON básico; no genera PDF ni acredita por sí mismo cumplimiento fiscal/legal. Hay que validar los requisitos del país e integrar un proveedor/autorización fiscal si el negocio lo necesita. Los nombres de producto en una factura se consultan desde el producto actual; el SQL existente no conserva una copia histórica del nombre/código. Para preservar esos datos a lo largo del tiempo sería necesaria una migración que agregue snapshots en `detalle_venta`.

Las pruebas focalizadas se ejecutan con la biblioteca estándar:

```powershell
python -m unittest discover -s tests -v
```

Cubren filtros combinados, ocultamiento de stock al público, permiso de empleado, cálculo del 13%, descuento de inventario, factura JSON y rollback lógico cuando no hay existencias suficientes. Se ejecutan en SQLite aislado; también hace falta una prueba de integración contra MySQL antes del despliegue, especialmente para el bloqueo de filas `FOR UPDATE`.

## 9. Cómo probar sin depender de la memoria

### Arranque local

En PowerShell, desde la raíz del proyecto que realmente quieres ejecutar:

```powershell
python -m compileall .
python -c "import main; print('import correcto')"
python -m uvicorn main:app --reload
```

Después abre `http://127.0.0.1:8000/docs`. Confirma en la terminal el directorio/proceso que arrancó; si ves columnas antiguas como `username` cuando el SQL nuevo usa `Nombres`, estás ejecutando otra copia o un modelo viejo.

No imprimas la URL completa de conexión si incluye credenciales. Mantén `.env` privado y comprueba que Git lo ignore.

### Probar una ruta de forma disciplinada

Para cada operación registra:

- método + URL;
- body y headers;
- resultado esperado (status y forma de JSON);
- resultado observado;
- qué cambió en MySQL.

Matriz mínima para una ruta protegida:

| Caso | Resultado esperado |
|---|---|
| Sin token | `401 Unauthorized` |
| Token inválido/expirado | `401 Unauthorized` |
| Rol válido para acción | Éxito y efecto esperado |
| Rol sin permiso | `403 Forbidden`, sin cambios en BD |
| ID inexistente | `404 Not Found` |
| Body inválido | `422 Unprocessable Entity`, sin cambios en BD |
| Restricción de BD/duplicado | Error HTTP controlado, transacción sin cambios parciales |

Usa datos nuevos o una base de prueba. Nunca uses pruebas destructivas en una base que contenga datos valiosos.

## 10. Método de depuración

Cuando aparezca un error:

1. Lee la primera excepción causal del traceback; las últimas líneas suelen indicar dónde se propagó.
2. Distingue capa de origen: red, startup, validación, autorización, ORM, MySQL o regla de negocio.
3. Comprueba desde qué carpeta y entorno se ejecuta Python.
4. Inspecciona el SQL generado y compáralo con `SHOW CREATE TABLE` de la base correcta.
5. Reduce el caso a una petición y datos concretos.
6. Corrige la causa raíz; no tapes el error con un `try/except` general ni retornes éxito falso.
7. Repite la prueba que fallaba y pruebas de regresión relacionadas.

Ejemplo: `Unknown column 'Usuario.username'` no se arregla creando una columna a ciegas. Primero determina si el ORM viejo se importó, si el proceso corre desde otra copia o si la base no recibió la migración esperada.

## 11. Seguridad que debes recordar en cada módulo

- Valida autorización tanto en la ruta como sobre el **registro concreto**.
- Deriva `usuario_id` del token cuando el recurso es propiedad del usuario.
- No confíes en rol, precios, descuentos, stock, totales ni estado enviados por el cliente.
- Usa consultas parametrizadas/SQLModel y restricciones de BD; nunca construyas SQL con texto del usuario.
- Aplica el mínimo privilegio: una ruta pública no debe exponer costo de compra, datos personales o datos internos.
- Responde con `401`, `403`, `404`, `409`/`400` y `422` coherentes, sin incluir stack traces ni secretos al cliente.
- Evita que errores de `commit()` dejen transacciones abiertas o cambios parciales.
- Agrega pruebas negativas de seguridad; un endpoint que funciona para el propietario puede filtrar datos a un cliente.
- Para despliegue: HTTPS, secretos fuertes, cuenta MySQL de privilegios mínimos, CORS limitado y logs sin contraseñas/tokens.

## 12. Git y hábitos de trabajo

Antes de modificar:

```powershell
git status --short --branch
git diff --check
```

Haz cambios pequeños por requisito, revisa el diff completo y verifica que no hayas agregado `.env`, cachés o archivos ajenos. Después ejecuta pruebas y revisa otra vez `git status`/`git diff`.

Si trabajas con una carpeta worktree, confirma la raíz Git antes de mover o copiar archivos. No copies archivos sobre otra instalación para “sincronizar” código sin entender qué rama y base estás usando. Mantén una fuente de verdad, y usa migraciones versionadas para cambios de esquema.

## 13. Cómo aprender cada cambio por tu cuenta

Para cada tarea del cronograma, completa una ficha breve en tus propias notas:

```text
Requisito:
Actor y permisos:
Datos que entran:
Reglas que el servidor debe imponer:
Tablas/relaciones afectadas:
Rutas y status HTTP:
Casos válidos:
Casos que deben rechazarse:
Pruebas y resultado:
Riesgos o decisiones pendientes:
```

Luego sigue este ciclo:

1. Lee la ruta/modelo más parecido que ya exista.
2. Dibuja la relación con tablas y roles.
3. Implementa primero el comportamiento mínimo y explícito.
4. Escribe pruebas de éxito y rechazo.
5. Ejecuta, inspecciona los datos y revisa el diff.
6. Explica en voz alta por qué cada validación está en el servidor.
7. Solo entonces integra el siguiente requisito.

Si pides ayuda a una persona o a una IA, úsala como revisión: presenta tu hipótesis, el error reproducible, los archivos que investigaste y las pruebas que harás. Pide que cuestione tus supuestos; no aceptes código que no puedas explicar.

## 14. Próximos pasos recomendados

1. Confirmar que solo se usa el esquema SQL nuevo y planear migración segura para cualquier base existente.
2. Crear datos semilla idempotentes para los tres roles y cuentas de demostración no productivas.
3. Añadir pruebas de autenticación/autorización y corregir acceso a pedidos por propietario.
4. Completar alertas de stock y búsqueda (sprints 2–3).
5. Implementar el POS como transacción (sprint 4), no como varios CRUD sin coordinación.
6. Completar estados y propiedad de pedidos (sprint 5).
7. Añadir consultas analíticas y pruebas de límites de fechas (sprint 6).
8. Preparar pruebas integrales, configuración segura y despliegue (sprint 7).

Una señal de dominio real no es recordar todos los nombres: es poder justificar las reglas, detectar qué capa debe imponer cada una y probar también los caminos que deben fallar.
