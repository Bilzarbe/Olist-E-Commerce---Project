-- =====================================================================
-- Project B - Olist | queries.sql
-- 10 consultas SELECT + 1 transacción con INSERT/UPDATE/DELETE
-- Autores: Beñat Ilzarbe Daza (B) y Nora Cepas Zapico (N)
-- Cada bloque: pregunta, SQL, y una frase de por qué es relevante.
-- =====================================================================


-- ---------------------------------------------------------------------
-- Q1 | Autor: Beñat | Nivel: básico | JOIN de 4 tablas + GROUP BY
-- Pregunta: ¿Qué 15 categorías de producto generan más ingresos en
--           pedidos entregados, y cuántos pedidos tiene cada una?
-- Relevante: identifica las categorías que sostienen el negocio.
-- ---------------------------------------------------------------------
SELECT COALESCE(pc.category_name_english, p.category_name, 'unknown') AS category,
       COUNT(DISTINCT o.order_id) AS orders,
       ROUND(SUM(oi.price), 2)    AS revenue
FROM order_item oi
JOIN orders o  ON o.order_id   = oi.order_id
JOIN product p ON p.product_id = oi.product_id
LEFT JOIN product_category pc ON pc.category_name = p.category_name
WHERE o.order_status = 'delivered'
GROUP BY 1
ORDER BY revenue DESC
LIMIT 15;


-- ---------------------------------------------------------------------
-- Q2 | Autor: Nora | Nivel: avanzado | CTE + JOIN + GROUP BY + HAVING
-- Pregunta: ¿Qué categorías con al menos 100 reseñas tienen una
--           puntuación media inferior a 4?
-- Relevante: señala categorías con problemas de satisfacción, ignorando
--            las que tienen muy pocas reseñas para ser fiables.
-- (La CTE usa pares pedido-categoría únicos para no contar dos veces la
--  misma reseña cuando un pedido tiene varios productos de la categoría.)
-- ---------------------------------------------------------------------
WITH order_category AS (
    SELECT DISTINCT oi.order_id,
           COALESCE(pc.category_name_english, p.category_name) AS category
    FROM order_item oi
    JOIN product p ON p.product_id = oi.product_id
    LEFT JOIN product_category pc ON pc.category_name = p.category_name
    WHERE p.category_name IS NOT NULL
)
SELECT oc.category,
       COUNT(*)                       AS reviews,
       ROUND(AVG(r.review_score), 2)  AS avg_score
FROM order_category oc
JOIN order_review r ON r.order_id = oc.order_id
GROUP BY oc.category
HAVING COUNT(*) >= 100 AND AVG(r.review_score) < 4.0
ORDER BY avg_score;


-- ---------------------------------------------------------------------
-- Q3 | Autor: Beñat | Nivel: avanzado | SUBQUERY (en HAVING + tabla derivada)
-- Pregunta: ¿Qué 20 vendedores facturan más que el vendedor medio?
-- Relevante: separa a los vendedores grandes del resto, que son la mayoría.
-- ---------------------------------------------------------------------
SELECT s.seller_id,
       s.state,
       COUNT(DISTINCT oi.order_id) AS orders,
       ROUND(SUM(oi.price), 2)     AS revenue
FROM seller s
JOIN order_item oi ON oi.seller_id = s.seller_id
GROUP BY s.seller_id, s.state
HAVING SUM(oi.price) > (
        SELECT AVG(t.total)
        FROM (SELECT SUM(price) AS total
              FROM order_item
              GROUP BY seller_id) t)
ORDER BY revenue DESC
LIMIT 20;


-- ---------------------------------------------------------------------
-- Q4 | Autor: Nora | Nivel: avanzado | WINDOW RANK() + CTE
-- Pregunta: ¿Quiénes son los 3 vendedores que más facturan en cada uno
--           de los principales estados?
-- Relevante: muestra cuánto se concentra el negocio dentro de cada estado.
-- (Parámetro de la app: lista de estados / un estado concreto.)
-- ---------------------------------------------------------------------
WITH seller_rev AS (
    SELECT s.seller_id, s.state, SUM(oi.price) AS revenue
    FROM seller s
    JOIN order_item oi ON oi.seller_id = s.seller_id
    GROUP BY s.seller_id, s.state
), ranked AS (
    SELECT seller_id, state, revenue,
           RANK() OVER (PARTITION BY state ORDER BY revenue DESC) AS rnk
    FROM seller_rev
)
SELECT state, rnk, seller_id, ROUND(revenue, 2) AS revenue
FROM ranked
WHERE rnk <= 3
  AND state IN ('SP', 'RJ', 'MG', 'PR', 'RS')
ORDER BY state, rnk;


-- ---------------------------------------------------------------------
-- Q5 | Autor: Beñat | Nivel: avanzado | CTE + WINDOW LAG()
-- Pregunta: ¿Cuánto facturamos cada mes y cuánto crece respecto al mes
--           anterior (ene-2017 a ago-2018)?
-- Relevante: muestra la evolución y la estacionalidad (p. ej. Black Friday).
-- ---------------------------------------------------------------------
WITH monthly AS (
    SELECT date_trunc('month', o.order_purchase_timestamp) AS month,
           SUM(oi.price) AS revenue
    FROM orders o
    JOIN order_item oi ON oi.order_id = o.order_id
    WHERE o.order_status <> 'canceled'
      AND o.order_purchase_timestamp >= '2017-01-01'
      AND o.order_purchase_timestamp <  '2018-09-01'
    GROUP BY 1
)
SELECT month,
       ROUND(revenue, 2) AS revenue,
       ROUND(LAG(revenue) OVER (ORDER BY month), 2) AS prev_revenue,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month))
                   / LAG(revenue) OVER (ORDER BY month), 1) AS growth_pct
FROM monthly
ORDER BY month;


-- ---------------------------------------------------------------------
-- Q6 | Autor: Nora | Nivel: intermedio | JOIN + GROUP BY + HAVING + fechas
-- Pregunta: ¿Cuántos días tarda de media en llegar un pedido en cada
--           estado, y con cuántos días de adelanto sobre lo prometido?
-- Relevante: revela qué regiones sufren más logística y si la promesa de
--            entrega es realista.
-- ---------------------------------------------------------------------
SELECT c.state,
       COUNT(*) AS delivered_orders,
       ROUND(AVG(EXTRACT(EPOCH FROM (o.order_delivered_customer_date - o.order_purchase_timestamp)) / 86400)::numeric, 1) AS avg_days_to_deliver,
       ROUND(AVG(EXTRACT(EPOCH FROM (o.order_estimated_delivery_date - o.order_delivered_customer_date)) / 86400)::numeric, 1) AS avg_days_early
FROM orders o
JOIN customer c ON c.customer_id = o.customer_id
WHERE o.order_status = 'delivered'
  AND o.order_delivered_customer_date IS NOT NULL
GROUP BY c.state
HAVING COUNT(*) >= 100
ORDER BY avg_days_to_deliver DESC;


-- ---------------------------------------------------------------------
-- Q7 | Autor: Beñat | Nivel: avanzado | CTE + WINDOW SUM() OVER ()
-- Pregunta: ¿Qué porcentaje de clientes (personas reales) ha comprado
--           1, 2, 3 o 4+ veces?
-- Relevante: mide la fidelidad; usa customer_unique_id porque customer_id
--            cambia en cada pedido.
-- ---------------------------------------------------------------------
WITH per_person AS (
    SELECT c.customer_unique_id, COUNT(*) AS n_orders
    FROM orders o
    JOIN customer c ON c.customer_id = o.customer_id
    WHERE o.order_status <> 'canceled'
    GROUP BY c.customer_unique_id
)
SELECT CASE WHEN n_orders >= 4 THEN '4+' ELSE CAST(n_orders AS TEXT) END AS orders_per_customer,
       COUNT(*) AS customers,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
FROM per_person
GROUP BY 1
ORDER BY 1;


-- ---------------------------------------------------------------------
-- Q8 | Autor: Nora | Nivel: avanzado | WINDOW SUM() OVER () + GROUP BY
-- Pregunta: ¿Qué peso tiene cada método de pago sobre el importe total y
--           cuántas cuotas se usan de media?
-- Relevante: muestra la dependencia de la tarjeta y del boleto, clave
--            para decisiones de financiación.
-- ---------------------------------------------------------------------
SELECT payment_type,
       COUNT(*)                          AS payments,
       ROUND(SUM(payment_value), 2)      AS total_value,
       ROUND(AVG(payment_installments), 2) AS avg_installments,
       ROUND(100.0 * SUM(payment_value) / SUM(SUM(payment_value)) OVER (), 2) AS pct_of_value
FROM order_payment
GROUP BY payment_type
ORDER BY total_value DESC;


-- ---------------------------------------------------------------------
-- Q9 | Autor: Beñat | Nivel: avanzado | CTE + CASE + JOIN
-- Pregunta: ¿Cómo cambia la puntuación de las reseñas según el retraso
--           de la entrega respecto a la fecha prometida?
-- Relevante: cuantifica el coste en satisfacción de entregar tarde.
-- ---------------------------------------------------------------------
WITH order_delay AS (
    SELECT o.order_id,
           EXTRACT(EPOCH FROM (o.order_delivered_customer_date - o.order_estimated_delivery_date)) / 86400 AS delay_days
    FROM orders o
    WHERE o.order_status = 'delivered'
      AND o.order_delivered_customer_date IS NOT NULL
)
SELECT CASE WHEN d.delay_days <= 0 THEN '1. On time or early'
            WHEN d.delay_days <= 3 THEN '2. Up to 3 days late'
            WHEN d.delay_days <= 7 THEN '3. 4-7 days late'
            ELSE '4. More than 7 days late' END AS delivery,
       COUNT(*)                      AS reviews,
       ROUND(AVG(r.review_score), 2) AS avg_score
FROM order_delay d
JOIN order_review r ON r.order_id = d.order_id
GROUP BY 1
ORDER BY 1;


-- ---------------------------------------------------------------------
-- Q10 | Autor: Nora | Nivel: avanzado | 2 CTE + 6 JOIN + fórmula de Haversine
-- Pregunta: ¿Qué distancia media (km) recorre un artículo entre vendedor
--           y cliente en cada estado, y cuánto se paga de envío?
-- Relevante: relaciona geografía y coste logístico usando la tabla grande
--            de geolocalización.
-- (Se ignoran coordenadas fuera de Brasil: anomalía detectada en el
--  profiling. zip_geo promedia las filas repetidas de cada código postal.)
-- ---------------------------------------------------------------------
WITH zip_geo AS (
    SELECT zip_code_prefix, AVG(lat) AS lat, AVG(lng) AS lng
    FROM geolocation
    WHERE lat BETWEEN -34 AND 6
      AND lng BETWEEN -74 AND -34
    GROUP BY zip_code_prefix
), item_dist AS (
    SELECT c.state AS customer_state,
           oi.freight_value,
           2 * 6371 * ASIN(SQRT(
               POWER(SIN(RADIANS(gc.lat - gs.lat) / 2), 2) +
               COS(RADIANS(gs.lat)) * COS(RADIANS(gc.lat)) *
               POWER(SIN(RADIANS(gc.lng - gs.lng) / 2), 2)
           )) AS km
    FROM order_item oi
    JOIN orders   o  ON o.order_id    = oi.order_id
    JOIN customer c  ON c.customer_id = o.customer_id
    JOIN seller   s  ON s.seller_id   = oi.seller_id
    JOIN zip_geo  gc ON gc.zip_code_prefix = c.zip_code_prefix
    JOIN zip_geo  gs ON gs.zip_code_prefix = s.zip_code_prefix
)
SELECT customer_state,
       COUNT(*)                              AS items,
       ROUND(AVG(km)::numeric, 0)            AS avg_km,
       ROUND(AVG(freight_value), 2)          AS avg_freight
FROM item_dist
GROUP BY customer_state
HAVING COUNT(*) >= 200
ORDER BY avg_km DESC;


-- ---------------------------------------------------------------------
-- Q11 | Autor: Beñat | INSERT + UPDATE + DELETE dentro de una TRANSACCIÓN
-- Pregunta: ¿Qué pasaría con el reparto de estados si reclasificáramos
--           como 'unavailable' los pedidos marcados 'delivered' que no
--           tienen fecha de entrega? (sin cambiar los datos de verdad)
-- Relevante: demuestra DML transaccional: se puede probar un cambio,
--            comprobarlo y deshacerlo con ROLLBACK sin dejar rastro.
-- En pgAdmin ejecuta las sentencias de una en una (F5 con el texto
-- seleccionado) para ver el resultado de cada SELECT.
-- ---------------------------------------------------------------------
BEGIN;

INSERT INTO product_category (category_name, category_name_english)
VALUES ('categoria_prueba', 'test_category');

UPDATE orders
SET order_status = 'unavailable'
WHERE order_status = 'delivered'
  AND order_delivered_customer_date IS NULL;

SELECT order_status, COUNT(*) AS orders
FROM orders
GROUP BY order_status
ORDER BY orders DESC;

DELETE FROM product_category
WHERE category_name = 'categoria_prueba';

ROLLBACK;

-- Comprobación tras el ROLLBACK: 'delivered' vuelve a tener 96.478 pedidos
SELECT order_status, COUNT(*) AS orders
FROM orders
GROUP BY order_status
ORDER BY orders DESC;
