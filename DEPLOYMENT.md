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
- La prioridad mayorista queda apagada hasta que el propietario configure el umbral en el dashboard. Solo se usa historial de ventas asociado a una cuenta de cliente; los pedidos de invitado no cuentan mientras no exista una verificación de identidad.
- Ejecuta las pruebas con `python -m unittest discover -s tests` antes de publicar.

Este documento deja el proceso preparado, pero no implica que la API o el sitio estén desplegados: publicar requiere una cuenta de hosting, dominio, configuración de secretos y autorización de acceso al proveedor.
