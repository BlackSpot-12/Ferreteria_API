-- Backup the ferreteria database before applying this migration.
-- Apply once to an existing MySQL/MariaDB database before starting the new API.

ALTER TABLE pedido
    MODIFY COLUMN usuario_id INT NULL,
    ADD COLUMN nombre_cliente VARCHAR(150) NOT NULL DEFAULT '',
    ADD COLUMN correo_cliente VARCHAR(150) NOT NULL DEFAULT '',
    ADD COLUMN telefono_cliente VARCHAR(30) NOT NULL DEFAULT '',
    ADD COLUMN tipo_cliente VARCHAR(20) NOT NULL DEFAULT 'Natural',
    ADD COLUMN numero_documento VARCHAR(50) NOT NULL DEFAULT '',
    ADD COLUMN direccion_cliente VARCHAR(255) NOT NULL DEFAULT '',
    ADD COLUMN venta_id INT NULL,
    ADD COLUMN codigo_acceso_hash CHAR(64) NULL;

ALTER TABLE venta
    ADD COLUMN cliente_usuario_id INT NULL,
    ADD COLUMN canal VARCHAR(20) NOT NULL DEFAULT 'POS',
    ADD COLUMN pedido_id INT NULL,
    ADD CONSTRAINT fk_venta_cliente_usuario
        FOREIGN KEY (cliente_usuario_id) REFERENCES Usuario (id_usuario),
    ADD CONSTRAINT fk_venta_pedido
        FOREIGN KEY (pedido_id) REFERENCES pedido (id_pedido),
    ADD CONSTRAINT uq_venta_pedido UNIQUE (pedido_id);

ALTER TABLE datos_facturacion
    ADD COLUMN correo VARCHAR(150) NOT NULL DEFAULT '',
    ADD COLUMN telefono VARCHAR(30) NOT NULL DEFAULT '',
    ADD COLUMN direccion VARCHAR(255) NOT NULL DEFAULT '',
    ADD COLUMN metodo_pago VARCHAR(20) NOT NULL DEFAULT 'Efectivo';

CREATE TABLE configuracion_negocio (
    id_configuracion INT NOT NULL PRIMARY KEY,
    umbral_mayorista DECIMAL(12, 2) NULL
);
