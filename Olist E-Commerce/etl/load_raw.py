"""
Carga los 9 CSV TAL CUAL en el esquema raw (sin limpiar ni transformar) para poder
perfilarlos en SQL. Requiere haber ejecutado antes sql/raw_schema.sql.
Una sola transacción: si algo falla, no queda nada cargado.

Uso:  python etl/load_raw.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from load import DEFAULT_DATA, connect          # reutiliza conexión y ruta de datos

FILES = {
    "customers": "olist_customers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

conn = connect()
try:
    with conn.cursor() as cur:
        for table, fname in FILES.items():
            with open(DEFAULT_DATA / fname, encoding="utf-8-sig", newline="") as fh:
                # HEADER salta la 1ª línea; NULL '' deja los campos vacíos como NULL
                cur.copy_expert(f"COPY raw.{table} FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')", fh)
            print(f"raw.{table:22s} {cur.rowcount:>10,} filas")
    conn.commit()
    print("COMMIT correcto.")
except Exception as e:
    conn.rollback()
    sys.exit(f"ERROR ({type(e).__name__}): {e}\n¿Ejecutaste antes sql/raw_schema.sql? ROLLBACK hecho.")
finally:
    conn.close()
