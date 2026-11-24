"""
Consultas de la app. Son las de sql/queries.sql con los filtros convertidos en
parámetros enlazados (%(nombre)s). Todo el cálculo ocurre en PostgreSQL.
"""

# ---- apoyo a los filtros (listas y límites) -------------------------------
BOUNDS = "SELECT MIN(order_purchase_timestamp)::date, MAX(order_purchase_timestamp)::date FROM orders"
CUSTOMER_STATES = "SELECT DISTINCT state FROM customer ORDER BY 1"
SELLER_STATES = "SELECT DISTINCT state FROM seller ORDER BY 1"
ORDER_STATUSES = "SELECT DISTINCT order_status FROM orders ORDER BY 1"

# Fragmento común de filtros (se repite literal en cada consulta para que cada SQL se lea completo):
#   AND o.order_purchase_timestamp >= %(d_from)s
#   AND o.order_purchase_timestamp <  %(d_to)s::date + 1
#   AND (%(state)s::text IS NULL OR c.state = %(state)s)

Q1_REVENUE_BY_CATEGORY = """
SELECT COALESCE(pc.category_name_english, p.category_name, 'unknown') AS category,
       COUNT(DISTINCT o.order_id) AS orders,
       ROUND(SUM(oi.price), 2)    AS revenue
FROM order_item oi
JOIN orders o   ON o.order_id    = oi.order_id
JOIN customer c ON c.customer_id = o.customer_id
JOIN product p  ON p.product_id  = oi.product_id
LEFT JOIN product_category pc ON pc.category_name = p.category_name
WHERE o.order_status = ANY(%(statuses)s)
  AND o.order_purchase_timestamp >= %(d_from)s
  AND o.order_purchase_timestamp <  %(d_to)s::date + 1
  AND (%(state)s::text IS NULL OR c.state = %(state)s)
GROUP BY 1
ORDER BY revenue DESC
LIMIT %(top_n)s
"""

Q4_TOP_SELLERS_BY_STATE = """
WITH seller_rev AS (
    SELECT s.seller_id, s.state, SUM(oi.price) AS revenue
    FROM seller s
    JOIN order_item oi ON oi.seller_id = s.seller_id
    JOIN orders o      ON o.order_id   = oi.order_id
    WHERE o.order_purchase_timestamp >= %(d_from)s
      AND o.order_purchase_timestamp <  %(d_to)s::date + 1
    GROUP BY s.seller_id, s.state
), ranked AS (
    SELECT seller_id, state, revenue,
           RANK() OVER (PARTITION BY state ORDER BY revenue DESC) AS rnk
    FROM seller_rev
)
SELECT state, rnk, seller_id, ROUND(revenue, 2) AS revenue
FROM ranked
WHERE rnk <= %(top_k)s
  AND state = %(seller_state)s
ORDER BY rnk, seller_id
"""

Q5_MONTHLY_REVENUE = """
WITH monthly AS (
    SELECT date_trunc('month', o.order_purchase_timestamp) AS month,
           SUM(oi.price) AS revenue
    FROM orders o
    JOIN order_item oi ON oi.order_id    = o.order_id
    JOIN customer c    ON c.customer_id  = o.customer_id
    WHERE o.order_status <> 'canceled'
      AND o.order_purchase_timestamp >= %(d_from)s
      AND o.order_purchase_timestamp <  %(d_to)s::date + 1
      AND (%(state)s::text IS NULL OR c.state = %(state)s)
    GROUP BY 1
)
SELECT month,
       ROUND(revenue, 2) AS revenue,
       ROUND(LAG(revenue) OVER (ORDER BY month), 2) AS prev_revenue,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month))
                   / LAG(revenue) OVER (ORDER BY month), 1) AS growth_pct
FROM monthly
ORDER BY month
"""

Q6_DELIVERY_BY_STATE = """
SELECT c.state,
       COUNT(*) AS delivered_orders,
       ROUND(AVG(EXTRACT(EPOCH FROM (o.order_delivered_customer_date - o.order_purchase_timestamp)) / 86400)::numeric, 1) AS avg_days_to_deliver,
       ROUND(AVG(EXTRACT(EPOCH FROM (o.order_estimated_delivery_date - o.order_delivered_customer_date)) / 86400)::numeric, 1) AS avg_days_early
FROM orders o
JOIN customer c ON c.customer_id = o.customer_id
WHERE o.order_status = 'delivered'
  AND o.order_delivered_customer_date IS NOT NULL
  AND o.order_purchase_timestamp >= %(d_from)s
  AND o.order_purchase_timestamp <  %(d_to)s::date + 1
GROUP BY c.state
HAVING COUNT(*) >= %(min_orders)s
ORDER BY avg_days_to_deliver DESC
"""

Q7_REPEAT_CUSTOMERS = """
WITH per_person AS (
    SELECT c.customer_unique_id, COUNT(*) AS n_orders
    FROM orders o
    JOIN customer c ON c.customer_id = o.customer_id
    WHERE o.order_status <> 'canceled'
      AND o.order_purchase_timestamp >= %(d_from)s
      AND o.order_purchase_timestamp <  %(d_to)s::date + 1
      AND (%(state)s::text IS NULL OR c.state = %(state)s)
    GROUP BY c.customer_unique_id
)
SELECT CASE WHEN n_orders >= 4 THEN '4+' ELSE CAST(n_orders AS TEXT) END AS orders_per_customer,
       COUNT(*) AS customers,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
FROM per_person
GROUP BY 1
ORDER BY 1
"""

Q8_PAYMENT_METHODS = """
SELECT op.payment_type,
       COUNT(*)                            AS payments,
       ROUND(SUM(op.payment_value), 2)     AS total_value,
       ROUND(AVG(op.payment_installments), 2) AS avg_installments,
       ROUND(100.0 * SUM(op.payment_value) / SUM(SUM(op.payment_value)) OVER (), 2) AS pct_of_value
FROM order_payment op
JOIN orders o   ON o.order_id    = op.order_id
JOIN customer c ON c.customer_id = o.customer_id
WHERE o.order_purchase_timestamp >= %(d_from)s
  AND o.order_purchase_timestamp <  %(d_to)s::date + 1
  AND (%(state)s::text IS NULL OR c.state = %(state)s)
GROUP BY op.payment_type
ORDER BY total_value DESC
"""

Q9_SCORE_VS_DELAY = """
WITH order_delay AS (
    SELECT o.order_id,
           EXTRACT(EPOCH FROM (o.order_delivered_customer_date - o.order_estimated_delivery_date)) / 86400 AS delay_days
    FROM orders o
    JOIN customer c ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
      AND o.order_delivered_customer_date IS NOT NULL
      AND o.order_purchase_timestamp >= %(d_from)s
      AND o.order_purchase_timestamp <  %(d_to)s::date + 1
      AND (%(state)s::text IS NULL OR c.state = %(state)s)
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
ORDER BY 1
"""

Q10_DISTANCE_VS_FREIGHT = """
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
    WHERE o.order_purchase_timestamp >= %(d_from)s
      AND o.order_purchase_timestamp <  %(d_to)s::date + 1
)
SELECT customer_state,
       COUNT(*)                     AS items,
       ROUND(AVG(km)::numeric, 0)   AS avg_km,
       ROUND(AVG(freight_value), 2) AS avg_freight
FROM item_dist
GROUP BY customer_state
HAVING COUNT(*) >= %(min_items)s
ORDER BY avg_km DESC
"""
