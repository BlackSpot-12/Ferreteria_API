# Preparar y desplegar Ferretería Bimetálica

## Desarrollo local con XAMPP

1. Inicia MySQL desde XAMPP y crea la base `ferreteria`.
2. Para una base existente, realiza un respaldo y aplica una sola vez `migrations/20261027_checkout_facturacion_mayoristas.sql` antes de iniciar la nueva versión de la API. El script amplía tablas existentes y no debe ejecutarse dos veces.
3. Copia `.env.example` a `.env`; conserva las contraseñas reales solo en `.env`.
4. Genera un valor aleatorio para `SECRET_KEY_TOKEN` y configura las variables de conexión.
5. En PowerShell, desde esta carpeta:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   uvicorn main:app --reload
   ```

6. Si se necesitan datos de demostración, completa las tres variables `SEED_*_PASSWORD` y ejecuta `python seed.py`. El seeder no sobrescribe cuentas ni productos existentes.
7. La documentación interactiva de la API queda disponible en `http://127.0.0.1:8000/docs`.

## Compilar Flutter Web

Desde `C:\Bimetalica\ferreteriaBimetalica`, configura `API_BASE_URL` con una URL que la aplicación pueda alcanzar y ejecuta:

```powershell
flutter pub get
flutter analyze
flutter build web --release --dart-define=API_BASE_URL=https://api.example.com
```

Publica el contenido de `build\web` en un hosting estático con HTTPS. No uses `localhost` como URL de API en el navegador de los clientes; debe ser la dirección HTTPS pública de la API.

## Lista previa a producción

- Usa MySQL administrado o un servidor de base de datos con acceso privado; no expongas el puerto de base de datos a Internet.
- Configura `DATABASE_*`, `SECRET_KEY_TOKEN` (mínimo 32 caracteres aleatorios), `CORS_ORIGINS` y los datos fiscales como variables protegidas del proveedor.
- `CORS_ORIGINS` debe contener el origen exacto del hosting Flutter, incluyendo esquema y puerto cuando aplique. No habilites `*` junto con credenciales.
- Ejecuta la API detrás de un servidor ASGI/proxy con HTTPS y define comprobaciones de salud y reinicio del proceso en el proveedor.
- No subas `.env`, claves JWT ni contraseñas del seeder al repositorio.
- El esquema actual se inicializa con `SQLModel.metadata.create_all`; planifica migraciones versionadas antes de cambios de esquema en producción.
- Los pedidos de invitado guardan datos de contacto y un hash del código privado de consulta. Los pedidos WEB solo se convierten en venta/factura cuando el empleado registra el pago en tienda y marca la entrega.
- La versión de API agrega las tablas `user_access`, `payment_record` y `guest_order_lookup_limit`; no requiere modificar columnas de las tablas existentes. `create_all` las crea al iniciar.
- `POST /auth/logout-all` revoca todas las sesiones del usuario autenticado. `GET /usuarios` está disponible para propietario/empleado sin incluir contraseñas; `PUT /usuarios/{usuario_id}/estado` y `POST /usuarios/{usuario_id}/logout-all` son exclusivos del propietario.
- Las operaciones de escritura y administración de `/productos` son exclusivas del propietario. `DELETE /productos/{producto_id}` inactiva el producto y `PUT` con `{"estado": true}` lo reactiva; el catálogo público omite productos inactivos.
- `GET /pedidos` acepta filtros `estado`, `fecha_inicio`, `fecha_fin` y `cliente` (nombre, correo o documento); los pedidos de clientes autenticados siguen limitados a su cuenta y la cola de empleados es compartida.
- Los códigos de consulta de pedidos invitados tienen 12 caracteres y permiten hasta 10 consultas por IP cada 15 minutos. El cobro acepta `referencia_pago` opcional para tarjeta/transferencia; `GET /pagos` (solo propietario) expone el registro de auditoría.
- `GET /reportes/inventario` incluye conteos y lista de reposición, valores por categoría y los productos con mayor valor de venta en inventario (`productos_limit`, de 1 a 50).
- La prioridad mayorista queda apagada hasta que el propietario configure el umbral en el dashboard. Solo se usa historial de ventas asociado a una cuenta de cliente; los pedidos de invitado no cuentan mientras no exista una verificación de identidad.
- Ejecuta las pruebas con `python -m unittest discover -s tests` antes de publicar.
- `SQL_ECHO=0` desactiva el eco SQL por defecto. Habilítalo solo temporalmente en desarrollo; los parámetros SQL pueden contener datos personales.
- El correo usa `MAIL_ENABLED=0` por defecto. Para habilitarlo, configura `SMTP_HOST`, `SMTP_PORT=587`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM` (opcional; por defecto usa `SMTP_USER`) y `WEB_PUBLIC_URL` mediante variables protegidas. La API inicia SMTP con STARTTLS y un timeout de 15 segundos. No guardes credenciales SMTP en el repositorio.
- `REQUIRE_EMAIL_VERIFICATION=0` conserva el acceso actual; al activarlo, únicamente bloquea pedidos de clientes autenticados que no hayan verificado su correo. El checkout de invitado permanece habilitado.
- La cuenta de cliente creada en `/usuarios/registro` recibe un enlace de verificación con vigencia de 24 horas. Las cuentas antiguas sin registro de verificación se consideran verificadas. El restablecimiento de contraseña usa tokens de un solo uso con vigencia de una hora y revoca las sesiones existentes.
- Los recibos de pedido y las facturas se envían en tareas en segundo plano. Las facturas automáticas se deduplican por venta; `POST /ventas/{venta_id}/factura/email` solicita un reenvío manual (propietario o cualquier empleado). `python enviar_prueba.py destinatario@example.com` envía un correo de prueba usando exclusivamente la configuración del entorno.
- El esquema añade únicamente `user_email_verification`, `email_token`, `invoice_email_state` e `invoice_email_audit` para esta función; `SQLModel.metadata.create_all` las crea sin alterar columnas existentes.

### Contratos de correo

- `POST /auth/olvide-password` recibe `{"correo":"cliente@example.com"}`. Siempre responde `200` con `{"detail":"Si el correo está registrado, recibirás instrucciones para restablecer la contraseña"}`; solo se programa el envío cuando existe una cuenta.
- `POST /auth/restablecer-password` recibe `{"token":"...","password":"..."}`. La contraseña debe tener entre 8 y 255 caracteres; los tokens vencidos, usados o inválidos responden `400`.
- `POST /usuarios/verificar-correo` recibe `{"token":"..."}`. `GET /usuarios/me/verificacion` requiere autenticación y devuelve `{"verificado":true|false,"verificado_en":timestamp|null}`. `POST /usuarios/me/reenviar-verificacion` también requiere autenticación y responde `429` si no han pasado dos minutos desde el último envío.
- `POST /ventas/{venta_id}/factura/email` requiere un token de propietario o empleado; responde `202` al registrar y programar un reenvío. Cada solicitud manual queda auditada aunque falle SMTP.

Este documento deja el proceso preparado, pero no implica que la API o el sitio estén desplegados: publicar requiere una cuenta de hosting, dominio, configuración de secretos y autorización de acceso al proveedor.
