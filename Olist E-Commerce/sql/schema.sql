-- =====================================================================
-- Project B - Olist Brazilian E-Commerce
-- schema.sql : crea TODAS las tablas con sus constraints.
-- El script de carga (ETL) solo inserta filas; no crea ni modifica tablas.
-- Ejecutar sobre una base de datos vacía (olist).
-- =====================================================================

DROP TABLE IF EXISTS order_review, order_payment, order_item, orders,
                     customer, customer_person, seller, product,
                     product_category, geolocation CASCADE;

-- ---------------------------------------------------------------------
-- Categorías de producto (+ traducción al inglés)
-- Las 2 categorías sin traducción en el CSV se insertan con english = NULL.
-- ---------------------------------------------------------------------
CREATE TABLE product_category (
    category_name          VARCHAR(60) PRIMARY KEY,
    category_name_english  VARCHAR(60) UNIQUE          -- NULL permitido
);

-- ---------------------------------------------------------------------
-- Productos
-- (columnas *_lenght del CSV renombradas a *_length)
-- Categoría y atributos de catálogo son NULL en 610 productos.
-- ---------------------------------------------------------------------
CREATE TABLE product (
    product_id                CHAR(32) PRIMARY KEY,
    category_name             VARCHAR(60) REFERENCES product_category(category_name),
    product_name_length       SMALLINT CHECK (product_name_length > 0),
    product_description_length SMALLINT CHECK (product_description_length > 0),
    product_photos_qty        SMALLINT CHECK (product_photos_qty > 0),
    product_weight_g          INTEGER  CHECK (product_weight_g >= 0),   -- hay pesos = 0 en los datos
    product_length_cm         SMALLINT CHECK (product_length_cm > 0),
    product_height_cm         SMALLINT CHECK (product_height_cm > 0),
    product_width_cm          SMALLINT CHECK (product_width_cm > 0)
);

-- ---------------------------------------------------------------------
-- Vendedores
-- zip_code_prefix NO tiene FK a geolocation (excepción justificada:
-- en geolocation el zip se repite y 7 zips de vendedores no existen allí).
-- ---------------------------------------------------------------------
CREATE TABLE seller (
    seller_id        CHAR(32) PRIMARY KEY,
    zip_code_prefix  CHAR(5)     NOT NULL,
    city             VARCHAR(50) NOT NULL,
    state            CHAR(2)     NOT NULL
);

-- ---------------------------------------------------------------------
-- Clientes: customer_id es POR PEDIDO; customer_unique_id identifica
-- a la persona (99.441 customer_id vs 96.096 customer_unique_id).
-- ---------------------------------------------------------------------
CREATE TABLE customer_person (
    customer_unique_id CHAR(32) PRIMARY KEY
);

CREATE TABLE customer (
    customer_id         CHAR(32) PRIMARY KEY,
    customer_unique_id  CHAR(32)    NOT NULL REFERENCES customer_person(customer_unique_id),
    zip_code_prefix     CHAR(5)     NOT NULL,   -- sin FK a geolocation (ver seller)
    city                VARCHAR(50) NOT NULL,
    state               CHAR(2)     NOT NULL
);

-- ---------------------------------------------------------------------
-- Pedidos
-- Los timestamps de entrega pueden ser NULL (pedidos cancelados, en curso
-- y 8 'delivered' sin fecha). No se imponen CHECK de orden sobre
-- carrier/customer porque los datos los incumplen (166 y 23 filas).
-- ---------------------------------------------------------------------
CREATE TABLE orders (
    order_id                       CHAR(32) PRIMARY KEY,
    customer_id                    CHAR(32)  NOT NULL REFERENCES customer(customer_id),
    order_status                   VARCHAR(12) NOT NULL
        CHECK (order_status IN ('delivered','shipped','canceled','unavailable',
                                'invoiced','processing','created','approved')),
    order_purchase_timestamp       TIMESTAMP NOT NULL,
    order_approved_at              TIMESTAMP,
    order_delivered_carrier_date   TIMESTAMP,
    order_delivered_customer_date  TIMESTAMP,
    order_estimated_delivery_date  TIMESTAMP NOT NULL,
    CHECK (order_approved_at IS NULL OR order_approved_at >= order_purchase_timestamp),
    CHECK (order_delivered_customer_date IS NULL
           OR order_delivered_customer_date >= order_purchase_timestamp)
);

-- ---------------------------------------------------------------------
-- Líneas de pedido
-- ---------------------------------------------------------------------
CREATE TABLE order_item (
    order_id             CHAR(32)      NOT NULL REFERENCES orders(order_id),
    order_item_id        SMALLINT      NOT NULL CHECK (order_item_id >= 1),
    product_id           CHAR(32)      NOT NULL REFERENCES product(product_id),
    seller_id            CHAR(32)      NOT NULL REFERENCES seller(seller_id),
    shipping_limit_date  TIMESTAMP     NOT NULL,
    price                NUMERIC(10,2) NOT NULL CHECK (price >= 0),
    freight_value        NUMERIC(10,2) NOT NULL CHECK (freight_value >= 0),
    PRIMARY KEY (order_id, order_item_id)
);

-- ---------------------------------------------------------------------
-- Pagos (un pedido puede tener varios pagos; 1 pedido no tiene ninguno)
-- 'not_defined' existe en los datos (3 filas): se conserva tal cual.
-- ---------------------------------------------------------------------
CREATE TABLE order_payment (
    order_id              CHAR(32)      NOT NULL REFERENCES orders(order_id),
    payment_sequential    SMALLINT      NOT NULL CHECK (payment_sequential >= 1),
    payment_type          VARCHAR(12)   NOT NULL
        CHECK (payment_type IN ('credit_card','boleto','voucher','debit_card','not_defined')),
    payment_installments  SMALLINT      NOT NULL CHECK (payment_installments >= 0),
    payment_value         NUMERIC(10,2) NOT NULL CHECK (payment_value >= 0),
    PRIMARY KEY (order_id, payment_sequential)
);

-- ---------------------------------------------------------------------
-- Reviews
-- review_id NO es único en los datos (789 ids repetidos, asociados a
-- pedidos distintos) -> PK compuesta (review_id, order_id).
-- ---------------------------------------------------------------------
CREATE TABLE order_review (
    review_id                CHAR(32)     NOT NULL,
    order_id                 CHAR(32)     NOT NULL REFERENCES orders(order_id),
    review_score             SMALLINT     NOT NULL CHECK (review_score BETWEEN 1 AND 5),
    review_comment_title     VARCHAR(100),
    review_comment_message   TEXT,
    review_creation_date     TIMESTAMP    NOT NULL,
    review_answer_timestamp  TIMESTAMP    NOT NULL,
    PRIMARY KEY (review_id, order_id),
    CHECK (review_answer_timestamp >= review_creation_date)
);

-- ---------------------------------------------------------------------
-- Geolocalización (tabla grande, ~740.000 filas tras quitar duplicados exactos)
-- zip_code_prefix se repite -> PK sustituta. Se guardan lat/lng tal cual:
-- hay coordenadas fuera de Brasil en el CSV, así que solo se comprueba
-- el rango geográfico mundial, no el de Brasil.
-- ---------------------------------------------------------------------
CREATE TABLE geolocation (
    geolocation_id   SERIAL PRIMARY KEY,
    zip_code_prefix  CHAR(5)           NOT NULL,
    lat              DOUBLE PRECISION  NOT NULL CHECK (lat BETWEEN -90  AND 90),
    lng              DOUBLE PRECISION  NOT NULL CHECK (lng BETWEEN -180 AND 180),
    city             VARCHAR(50)       NOT NULL,
    state            CHAR(2)           NOT NULL
);
