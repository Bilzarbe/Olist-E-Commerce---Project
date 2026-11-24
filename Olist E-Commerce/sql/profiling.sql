-- =====================================================================
-- profiling.sql : perfilado de los datos CRUDOS (esquema raw), solo SQL
-- Requiere: sql/raw_schema.sql + python etl/load_raw.py
-- Ejecutar cada bloque P1..P10 por separado y capturar el resultado.
-- =====================================================================


-- P1 | Filas de cada archivo
SELECT 'olist_customers_dataset.csv'      AS file, COUNT(*) AS row_count FROM raw.customers
UNION ALL SELECT 'olist_geolocation_dataset.csv',     COUNT(*) FROM raw.geolocation
UNION ALL SELECT 'olist_order_items_dataset.csv',     COUNT(*) FROM raw.order_items
UNION ALL SELECT 'olist_order_payments_dataset.csv',  COUNT(*) FROM raw.order_payments
UNION ALL SELECT 'olist_order_reviews_dataset.csv',   COUNT(*) FROM raw.order_reviews
UNION ALL SELECT 'olist_orders_dataset.csv',          COUNT(*) FROM raw.orders
UNION ALL SELECT 'olist_products_dataset.csv',        COUNT(*) FROM raw.products
UNION ALL SELECT 'olist_sellers_dataset.csv',         COUNT(*) FROM raw.sellers
UNION ALL SELECT 'product_category_name_translation.csv', COUNT(*) FROM raw.category_translation
ORDER BY row_count DESC;


-- P2 | Claves candidatas: ¿son realmente únicas?
SELECT tbl, candidate_key, total_rows, distinct_values,
       CASE WHEN total_rows = distinct_values THEN 'YES' ELSE 'NO' END AS is_unique
FROM (
    SELECT 'customers' AS tbl, 'customer_id' AS candidate_key, COUNT(*) AS total_rows, COUNT(DISTINCT customer_id) AS distinct_values FROM raw.customers
    UNION ALL SELECT 'customers', 'customer_unique_id', COUNT(*), COUNT(DISTINCT customer_unique_id) FROM raw.customers
    UNION ALL SELECT 'orders', 'order_id', COUNT(*), COUNT(DISTINCT order_id) FROM raw.orders
    UNION ALL SELECT 'order_items', '(order_id, order_item_id)', COUNT(*), COUNT(DISTINCT order_id || '|' || order_item_id) FROM raw.order_items
    UNION ALL SELECT 'order_payments', '(order_id, payment_sequential)', COUNT(*), COUNT(DISTINCT order_id || '|' || payment_sequential) FROM raw.order_payments
    UNION ALL SELECT 'order_reviews', 'review_id', COUNT(*), COUNT(DISTINCT review_id) FROM raw.order_reviews
    UNION ALL SELECT 'order_reviews', '(review_id, order_id)', COUNT(*), COUNT(DISTINCT review_id || '|' || order_id) FROM raw.order_reviews
    UNION ALL SELECT 'products', 'product_id', COUNT(*), COUNT(DISTINCT product_id) FROM raw.products
    UNION ALL SELECT 'sellers', 'seller_id', COUNT(*), COUNT(DISTINCT seller_id) FROM raw.sellers
    UNION ALL SELECT 'geolocation', 'geolocation_zip_code_prefix', COUNT(*), COUNT(DISTINCT geolocation_zip_code_prefix) FROM raw.geolocation
    UNION ALL SELECT 'category_translation', 'product_category_name', COUNT(*), COUNT(DISTINCT product_category_name) FROM raw.category_translation
) k
ORDER BY tbl, candidate_key;


-- P3 | Nulos por columna (todas las tablas; recorre las columnas con to_jsonb)
SELECT tbl, col, total_rows, nulls, ROUND(100.0 * nulls / total_rows, 2) AS pct_null
FROM (
    SELECT 'customers' AS tbl, e.key AS col, COUNT(*) AS total_rows, COUNT(*) FILTER (WHERE e.value IS NULL) AS nulls
      FROM raw.customers t, LATERAL jsonb_each_text(to_jsonb(t)) AS e(key, value) GROUP BY e.key
    UNION ALL SELECT 'geolocation', e.key, COUNT(*), COUNT(*) FILTER (WHERE e.value IS NULL)
      FROM raw.geolocation t, LATERAL jsonb_each_text(to_jsonb(t)) AS e(key, value) GROUP BY e.key
    UNION ALL SELECT 'order_items', e.key, COUNT(*), COUNT(*) FILTER (WHERE e.value IS NULL)
      FROM raw.order_items t, LATERAL jsonb_each_text(to_jsonb(t)) AS e(key, value) GROUP BY e.key
    UNION ALL SELECT 'order_payments', e.key, COUNT(*), COUNT(*) FILTER (WHERE e.value IS NULL)
      FROM raw.order_payments t, LATERAL jsonb_each_text(to_jsonb(t)) AS e(key, value) GROUP BY e.key
    UNION ALL SELECT 'order_reviews', e.key, COUNT(*), COUNT(*) FILTER (WHERE e.value IS NULL)
      FROM raw.order_reviews t, LATERAL jsonb_each_text(to_jsonb(t)) AS e(key, value) GROUP BY e.key
    UNION ALL SELECT 'orders', e.key, COUNT(*), COUNT(*) FILTER (WHERE e.value IS NULL)
      FROM raw.orders t, LATERAL jsonb_each_text(to_jsonb(t)) AS e(key, value) GROUP BY e.key
    UNION ALL SELECT 'products', e.key, COUNT(*), COUNT(*) FILTER (WHERE e.value IS NULL)
      FROM raw.products t, LATERAL jsonb_each_text(to_jsonb(t)) AS e(key, value) GROUP BY e.key
    UNION ALL SELECT 'sellers', e.key, COUNT(*), COUNT(*) FILTER (WHERE e.value IS NULL)
      FROM raw.sellers t, LATERAL jsonb_each_text(to_jsonb(t)) AS e(key, value) GROUP BY e.key
    UNION ALL SELECT 'category_translation', e.key, COUNT(*), COUNT(*) FILTER (WHERE e.value IS NULL)
      FROM raw.category_translation t, LATERAL jsonb_each_text(to_jsonb(t)) AS e(key, value) GROUP BY e.key
) n
ORDER BY tbl, nulls DESC, col;


-- P4 | Fechas: rango y formato (esperado YYYY-MM-DD HH:MI:SS)
SELECT col, MIN(v) AS min_value, MAX(v) AS max_value,
       COUNT(v) AS non_null,
       COUNT(*) FILTER (WHERE v IS NOT NULL AND v !~ '^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$') AS bad_format
FROM (
    SELECT 'orders.order_purchase_timestamp' AS col, order_purchase_timestamp AS v FROM raw.orders
    UNION ALL SELECT 'orders.order_approved_at', order_approved_at FROM raw.orders
    UNION ALL SELECT 'orders.order_delivered_carrier_date', order_delivered_carrier_date FROM raw.orders
    UNION ALL SELECT 'orders.order_delivered_customer_date', order_delivered_customer_date FROM raw.orders
    UNION ALL SELECT 'orders.order_estimated_delivery_date', order_estimated_delivery_date FROM raw.orders
    UNION ALL SELECT 'order_items.shipping_limit_date', shipping_limit_date FROM raw.order_items
    UNION ALL SELECT 'order_reviews.review_creation_date', review_creation_date FROM raw.order_reviews
    UNION ALL SELECT 'order_reviews.review_answer_timestamp', review_answer_timestamp FROM raw.order_reviews
) d
GROUP BY col
ORDER BY col;


-- P5 | Números: rango y valores que no son numéricos
SELECT col, MIN(v::numeric) AS min_value, MAX(v::numeric) AS max_value,
       COUNT(v) AS non_null,
       COUNT(*) FILTER (WHERE v !~ '^-?\d+(\.\d+)?$') AS not_numeric
FROM (
    SELECT 'order_items.price' AS col, price AS v FROM raw.order_items
    UNION ALL SELECT 'order_items.freight_value', freight_value FROM raw.order_items
    UNION ALL SELECT 'order_items.order_item_id', order_item_id FROM raw.order_items
    UNION ALL SELECT 'order_payments.payment_value', payment_value FROM raw.order_payments
    UNION ALL SELECT 'order_payments.payment_installments', payment_installments FROM raw.order_payments
    UNION ALL SELECT 'order_payments.payment_sequential', payment_sequential FROM raw.order_payments
    UNION ALL SELECT 'order_reviews.review_score', review_score FROM raw.order_reviews
    UNION ALL SELECT 'products.product_weight_g', product_weight_g FROM raw.products
    UNION ALL SELECT 'products.product_length_cm', product_length_cm FROM raw.products
    UNION ALL SELECT 'products.product_height_cm', product_height_cm FROM raw.products
    UNION ALL SELECT 'products.product_width_cm', product_width_cm FROM raw.products
    UNION ALL SELECT 'products.product_photos_qty', product_photos_qty FROM raw.products
    UNION ALL SELECT 'geolocation.lat', geolocation_lat FROM raw.geolocation
    UNION ALL SELECT 'geolocation.lng', geolocation_lng FROM raw.geolocation
) x
WHERE v IS NOT NULL
GROUP BY col
ORDER BY col;


-- P6 | Códigos de longitud fija: ids, códigos postales y estados
SELECT col, MIN(LENGTH(v)) AS min_len, MAX(LENGTH(v)) AS max_len, COUNT(DISTINCT v) AS distinct_values
FROM (
    SELECT 'customers.customer_zip_code_prefix' AS col, customer_zip_code_prefix AS v FROM raw.customers
    UNION ALL SELECT 'sellers.seller_zip_code_prefix', seller_zip_code_prefix FROM raw.sellers
    UNION ALL SELECT 'geolocation.zip_code_prefix', geolocation_zip_code_prefix FROM raw.geolocation
    UNION ALL SELECT 'customers.customer_state', customer_state FROM raw.customers
    UNION ALL SELECT 'sellers.seller_state', seller_state FROM raw.sellers
    UNION ALL SELECT 'geolocation.state', geolocation_state FROM raw.geolocation
    UNION ALL SELECT 'orders.order_id', order_id FROM raw.orders
    UNION ALL SELECT 'customers.customer_id', customer_id FROM raw.customers
    UNION ALL SELECT 'products.product_id', product_id FROM raw.products
    UNION ALL SELECT 'sellers.seller_id', seller_id FROM raw.sellers
    UNION ALL SELECT 'order_reviews.review_id', review_id FROM raw.order_reviews
) c
GROUP BY col
ORDER BY col;


-- P7 | Códigos categóricos: valores distintos y frecuencia
SELECT field, value, COUNT(*) AS n
FROM (
    SELECT 'orders.order_status' AS field, order_status AS value FROM raw.orders
    UNION ALL SELECT 'order_payments.payment_type', payment_type FROM raw.order_payments
    UNION ALL SELECT 'order_reviews.review_score', review_score FROM raw.order_reviews
) c
GROUP BY field, value
ORDER BY field, n DESC;


-- P8 | Duplicados
SELECT 'geolocation: filas duplicadas exactas (sobran)' AS finding,
       (SELECT COUNT(*) FROM raw.geolocation) - (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM raw.geolocation) d) AS n
UNION ALL SELECT 'order_reviews: review_id que aparece en más de una fila',
       (SELECT COUNT(*) FROM (SELECT review_id FROM raw.order_reviews GROUP BY review_id HAVING COUNT(*) > 1) x)
UNION ALL SELECT 'order_reviews: pedidos con más de una review',
       (SELECT COUNT(*) FROM (SELECT order_id FROM raw.order_reviews GROUP BY order_id HAVING COUNT(*) > 1) x)
UNION ALL SELECT 'customers: customer_unique_id con más de un customer_id',
       (SELECT COUNT(*) FROM (SELECT customer_unique_id FROM raw.customers GROUP BY customer_unique_id HAVING COUNT(*) > 1) x);


-- P9 | Integridad referencial: filas "huérfanas" y relaciones sin hijos
SELECT 'order_items.order_id -> orders' AS relation, COUNT(*) AS rows_without_match
  FROM raw.order_items oi WHERE NOT EXISTS (SELECT 1 FROM raw.orders o WHERE o.order_id = oi.order_id)
UNION ALL SELECT 'order_items.product_id -> products', COUNT(*)
  FROM raw.order_items oi WHERE NOT EXISTS (SELECT 1 FROM raw.products p WHERE p.product_id = oi.product_id)
UNION ALL SELECT 'order_items.seller_id -> sellers', COUNT(*)
  FROM raw.order_items oi WHERE NOT EXISTS (SELECT 1 FROM raw.sellers s WHERE s.seller_id = oi.seller_id)
UNION ALL SELECT 'order_payments.order_id -> orders', COUNT(*)
  FROM raw.order_payments op WHERE NOT EXISTS (SELECT 1 FROM raw.orders o WHERE o.order_id = op.order_id)
UNION ALL SELECT 'order_reviews.order_id -> orders', COUNT(*)
  FROM raw.order_reviews r WHERE NOT EXISTS (SELECT 1 FROM raw.orders o WHERE o.order_id = r.order_id)
UNION ALL SELECT 'orders.customer_id -> customers', COUNT(*)
  FROM raw.orders o WHERE NOT EXISTS (SELECT 1 FROM raw.customers c WHERE c.customer_id = o.customer_id)
UNION ALL SELECT 'products: categorías distintas sin traducción', COUNT(DISTINCT p.product_category_name)
  FROM raw.products p WHERE p.product_category_name IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM raw.category_translation t WHERE t.product_category_name = p.product_category_name)
UNION ALL SELECT 'customers: códigos postales distintos sin geolocation', COUNT(DISTINCT c.customer_zip_code_prefix)
  FROM raw.customers c WHERE NOT EXISTS (SELECT 1 FROM raw.geolocation g WHERE g.geolocation_zip_code_prefix = c.customer_zip_code_prefix)
UNION ALL SELECT 'sellers: códigos postales distintos sin geolocation', COUNT(DISTINCT s.seller_zip_code_prefix)
  FROM raw.sellers s WHERE NOT EXISTS (SELECT 1 FROM raw.geolocation g WHERE g.geolocation_zip_code_prefix = s.seller_zip_code_prefix)
UNION ALL SELECT 'orders sin ningún order_item', COUNT(*)
  FROM raw.orders o WHERE NOT EXISTS (SELECT 1 FROM raw.order_items oi WHERE oi.order_id = o.order_id)
UNION ALL SELECT 'orders sin ningún pago', COUNT(*)
  FROM raw.orders o WHERE NOT EXISTS (SELECT 1 FROM raw.order_payments op WHERE op.order_id = o.order_id);


-- P10 | Valores inesperados e incoherencias
SELECT 'orders: estado delivered sin fecha de entrega al cliente' AS finding, COUNT(*) AS n
  FROM raw.orders WHERE order_status = 'delivered' AND order_delivered_customer_date IS NULL
UNION ALL SELECT 'orders: entrega al transportista ANTERIOR a la compra', COUNT(*)
  FROM raw.orders WHERE order_delivered_carrier_date < order_purchase_timestamp
UNION ALL SELECT 'orders: entrega al cliente ANTERIOR a la entrega al transportista', COUNT(*)
  FROM raw.orders WHERE order_delivered_customer_date < order_delivered_carrier_date
UNION ALL SELECT 'orders: aprobación ANTERIOR a la compra', COUNT(*)
  FROM raw.orders WHERE order_approved_at < order_purchase_timestamp
UNION ALL SELECT 'order_reviews: respuesta ANTERIOR a la creación', COUNT(*)
  FROM raw.order_reviews WHERE review_answer_timestamp < review_creation_date
UNION ALL SELECT 'order_payments: payment_value = 0', COUNT(*)
  FROM raw.order_payments WHERE payment_value::numeric = 0
UNION ALL SELECT 'order_payments: payment_installments = 0', COUNT(*)
  FROM raw.order_payments WHERE payment_installments::numeric = 0
UNION ALL SELECT 'order_payments: payment_type = not_defined (código sin significado)', COUNT(*)
  FROM raw.order_payments WHERE payment_type = 'not_defined'
UNION ALL SELECT 'order_items: price <= 0', COUNT(*)
  FROM raw.order_items WHERE price::numeric <= 0
UNION ALL SELECT 'products: product_weight_g = 0', COUNT(*)
  FROM raw.products WHERE product_weight_g::numeric = 0
UNION ALL SELECT 'products: sin categoría', COUNT(*)
  FROM raw.products WHERE product_category_name IS NULL
UNION ALL SELECT 'geolocation: coordenadas fuera de Brasil (filas)', COUNT(*)
  FROM raw.geolocation
  WHERE geolocation_lat::numeric NOT BETWEEN -34 AND 6 OR geolocation_lng::numeric NOT BETWEEN -74 AND -34;
