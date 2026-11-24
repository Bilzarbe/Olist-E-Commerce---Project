# Cleaning log (generado por etl/load.py)

| Regla | Tabla | Descripción | Filas afectadas |
|---|---|---|---|
| R3 | product_category | categorías de productos sin traducción añadidas con english=NULL: ['pc_gamer', 'portateis_cozinha_e_preparadores_de_alimentos'] | 2 |
| R1 | product | celda vacía en 'category_name' -> NULL | 610 |
| R1 | product | celda vacía en 'product_name_length' -> NULL | 610 |
| R1 | product | celda vacía en 'product_description_length' -> NULL | 610 |
| R1 | product | celda vacía en 'product_photos_qty' -> NULL | 610 |
| R1 | product | celda vacía en 'product_weight_g' -> NULL | 2 |
| R1 | product | celda vacía en 'product_length_cm' -> NULL | 2 |
| R1 | product | celda vacía en 'product_height_cm' -> NULL | 2 |
| R1 | product | celda vacía en 'product_width_cm' -> NULL | 2 |
| R2 | geolocation | filas duplicadas exactas eliminadas | 261,831 |
| R5 | customer_person | 99,441 customer_id colapsan en customer_unique_id distintos | 96,096 |
| R1 | orders | celda vacía en 'order_delivered_carrier_date' -> NULL | 1,783 |
| R1 | orders | celda vacía en 'order_delivered_customer_date' -> NULL | 2,965 |
| R1 | orders | celda vacía en 'order_approved_at' -> NULL | 160 |
| R1 | order_review | celda vacía en 'review_comment_title' -> NULL | 87,656 |
| R1 | order_review | celda vacía en 'review_comment_message' -> NULL | 58,247 |

| Tabla | Filas insertadas |
|---|---|
| product_category | 73 |
| product | 32,951 |
| seller | 3,095 |
| geolocation | 738,332 |
| customer_person | 96,096 |
| customer | 99,441 |
| orders | 99,441 |
| order_item | 112,650 |
| order_payment | 103,886 |
| order_review | 99,224 |

R4 (estático): columnas `product_name_lenght` y `product_description_lenght` renombradas a `*_length`.
