"""
ETL Olist -> PostgreSQL

* NO crea tablas: el esquema lo crea sql/schema.sql ANTES de ejecutar esto.
* Toda la carga se hace en UNA transacción: si algo falla, no queda nada cargado.
* Python solo LEE y LIMPIA FORMATOS. No agrega, une ni analiza datos
  (todo el análisis se hace en SQL).
* Los valores que faltan se quedan en NULL; nunca se inventa nada.

Uso:
    python etl/load.py                     # carga real
    python etl/load.py --simulate-error    # demo de rollback (provoca un error al final)

Conexión: variables PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD
(o un archivo .env en la raíz del proyecto, que NO se sube a Git).
"""
import argparse
import csv
import io
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Acepta los CSV en data/raw/ o directamente en data/
DEFAULT_DATA = ROOT / "data" / "raw"
if not (DEFAULT_DATA / "olist_orders_dataset.csv").exists() and \
        (ROOT / "data" / "olist_orders_dataset.csv").exists():
    DEFAULT_DATA = ROOT / "data"
LOG_FILE = ROOT / "docs" / "cleaning_log.md"

csv.field_size_limit(10**9)

# (tabla destino, archivo, [(columna CSV, columna BD), ...])
# Las columnas '*_lenght' del CSV se renombran a '*_length' (regla R4).
SPECS = {
    "product": ("olist_products_dataset.csv", [
        ("product_id", "product_id"),
        ("product_category_name", "category_name"),
        ("product_name_lenght", "product_name_length"),
        ("product_description_lenght", "product_description_length"),
        ("product_photos_qty", "product_photos_qty"),
        ("product_weight_g", "product_weight_g"),
        ("product_length_cm", "product_length_cm"),
        ("product_height_cm", "product_height_cm"),
        ("product_width_cm", "product_width_cm"),
    ]),
    "seller": ("olist_sellers_dataset.csv", [
        ("seller_id", "seller_id"),
        ("seller_zip_code_prefix", "zip_code_prefix"),
        ("seller_city", "city"),
        ("seller_state", "state"),
    ]),
    "geolocation": ("olist_geolocation_dataset.csv", [
        ("geolocation_zip_code_prefix", "zip_code_prefix"),
        ("geolocation_lat", "lat"),
        ("geolocation_lng", "lng"),
        ("geolocation_city", "city"),
        ("geolocation_state", "state"),
    ]),
    "customer": ("olist_customers_dataset.csv", [
        ("customer_id", "customer_id"),
        ("customer_unique_id", "customer_unique_id"),
        ("customer_zip_code_prefix", "zip_code_prefix"),
        ("customer_city", "city"),
        ("customer_state", "state"),
    ]),
    "orders": ("olist_orders_dataset.csv", [
        ("order_id", "order_id"),
        ("customer_id", "customer_id"),
        ("order_status", "order_status"),
        ("order_purchase_timestamp", "order_purchase_timestamp"),
        ("order_approved_at", "order_approved_at"),
        ("order_delivered_carrier_date", "order_delivered_carrier_date"),
        ("order_delivered_customer_date", "order_delivered_customer_date"),
        ("order_estimated_delivery_date", "order_estimated_delivery_date"),
    ]),
    "order_item": ("olist_order_items_dataset.csv", [
        ("order_id", "order_id"),
        ("order_item_id", "order_item_id"),
        ("product_id", "product_id"),
        ("seller_id", "seller_id"),
        ("shipping_limit_date", "shipping_limit_date"),
        ("price", "price"),
        ("freight_value", "freight_value"),
    ]),
    "order_payment": ("olist_order_payments_dataset.csv", [
        ("order_id", "order_id"),
        ("payment_sequential", "payment_sequential"),
        ("payment_type", "payment_type"),
        ("payment_installments", "payment_installments"),
        ("payment_value", "payment_value"),
    ]),
    "order_review": ("olist_order_reviews_dataset.csv", [
        ("review_id", "review_id"),
        ("order_id", "order_id"),
        ("review_score", "review_score"),
        ("review_comment_title", "review_comment_title"),
        ("review_comment_message", "review_comment_message"),
        ("review_creation_date", "review_creation_date"),
        ("review_answer_timestamp", "review_answer_timestamp"),
    ]),
}
TRANSLATION_FILE = "product_category_name_translation.csv"

# Orden de carga: respeta las claves foráneas.
LOAD_ORDER = ["product_category", "product", "seller", "geolocation",
              "customer_person", "customer", "orders",
              "order_item", "order_payment", "order_review"]


class Log:
    """Recoge cada regla de limpieza con el nº de filas afectadas."""
    def __init__(self):
        self.rules = []      # (id, tabla, descripción, filas)
        self.loaded = {}     # tabla -> filas insertadas

    def rule(self, rid, table, text, n):
        self.rules.append((rid, table, text, n))
        print(f"   [{rid}] {table}: {text} -> {n:,} filas")


def read_csv(data_dir: Path, filename: str):
    with open(data_dir / filename, newline="", encoding="utf-8-sig") as fh:
        yield from csv.DictReader(fh)


def mapped_rows(data_dir, table, log):
    """R1: celdas vacías -> NULL (se cuentan por columna). R4: renombrado de columnas."""
    filename, mapping = SPECS[table]
    empties = defaultdict(int)
    for rec in read_csv(data_dir, filename):
        row = []
        for src, dst in mapping:
            v = rec[src]
            if v == "":
                empties[dst] += 1
                v = None
            row.append(v)
        yield row
    for col, n in empties.items():
        log.rule("R1", table, f"celda vacía en '{col}' -> NULL", n)


def category_rows(data_dir, log):
    """Traducciones del CSV + categorías usadas por productos que no tienen traducción
    (se insertan con english = NULL: no se inventa la traducción) -> R3."""
    translated = set()
    for rec in read_csv(data_dir, TRANSLATION_FILE):
        name = rec["product_category_name"]
        translated.add(name)
        yield [name, rec["product_category_name_english"]]
    used = {rec["product_category_name"] for rec in read_csv(data_dir, SPECS["product"][0])
            if rec["product_category_name"] != ""}
    missing = sorted(used - translated)
    for name in missing:
        yield [name, None]
    log.rule("R3", "product_category",
             f"categorías de productos sin traducción añadidas con english=NULL: {missing}",
             len(missing))


def geolocation_rows(data_dir, log):
    """R2: se eliminan filas duplicadas exactas (las 5 columnas iguales)."""
    seen, dup = set(), 0
    for row in mapped_rows(data_dir, "geolocation", log):
        key = tuple(row)
        if key in seen:
            dup += 1
            continue
        seen.add(key)
        yield row
    log.rule("R2", "geolocation", "filas duplicadas exactas eliminadas", dup)


def customer_person_rows(data_dir, log):
    """R5: customer_unique_id distintos (la tabla customer_person normaliza 'persona')."""
    seen = set()
    total = 0
    for rec in read_csv(data_dir, SPECS["customer"][0]):
        total += 1
        uid = rec["customer_unique_id"]
        if uid not in seen:
            seen.add(uid)
            yield [uid]
    log.rule("R5", "customer_person",
             f"{total:,} customer_id colapsan en customer_unique_id distintos", len(seen))


def row_source(table, data_dir, log):
    if table == "product_category":
        return category_rows(data_dir, log)
    if table == "geolocation":
        return geolocation_rows(data_dir, log)
    if table == "customer_person":
        return customer_person_rows(data_dir, log)
    return mapped_rows(data_dir, table, log)


def columns_of(table):
    if table == "product_category":
        return ["category_name", "category_name_english"]
    if table == "customer_person":
        return ["customer_unique_id"]
    return [dst for _, dst in SPECS[table][1]]


def copy_table(cur, table, rows):
    """Vuelca las filas ya limpias con COPY (rápido) dentro de la transacción abierta.
    Los nombres de tabla/columna salen de constantes de este archivo, no de entrada externa."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    n = 0
    for r in rows:
        writer.writerow(r)          # None -> campo vacío -> NULL en COPY
        n += 1
    buf.seek(0)
    cols = ", ".join(columns_of(table))
    cur.copy_expert(f"COPY {table} ({cols}) FROM STDIN WITH (FORMAT csv, NULL '')", buf)
    if cur.rowcount != n:
        raise RuntimeError(f"{table}: enviadas {n} filas pero PostgreSQL insertó {cur.rowcount}")
    return n


def table_counts(conn):
    with conn.cursor() as cur:
        out = {}
        for t in LOAD_ORDER:
            cur.execute(f"SELECT count(*) FROM {t}")
            out[t] = cur.fetchone()[0]
    return out


def run_load(conn, data_dir: Path, simulate_error=False, log=None):
    log = log or Log()
    with conn.cursor() as cur:
        for t in LOAD_ORDER:
            t0 = time.time()
            print(f"-> cargando {t} ...")
            n = copy_table(cur, t, row_source(t, data_dir, log))
            log.loaded[t] = n
            print(f"   {n:,} filas insertadas ({time.time() - t0:.1f}s)")

        if simulate_error:
            print("-> SIMULACIÓN: insertando una review con score=9 (viola el CHECK)")
            cur.execute("""
                INSERT INTO order_review (review_id, order_id, review_score,
                                          review_creation_date, review_answer_timestamp)
                SELECT 'x' || repeat('0', 31), order_id, 9, now(), now()
                FROM orders LIMIT 1""")
    return log


def write_log(log: Log):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("# Cleaning log (generado por etl/load.py)\n\n")
        f.write("| Regla | Tabla | Descripción | Filas afectadas |\n|---|---|---|---|\n")
        for rid, t, text, n in log.rules:
            f.write(f"| {rid} | {t} | {text} | {n:,} |\n")
        f.write("\n| Tabla | Filas insertadas |\n|---|---|\n")
        for t, n in log.loaded.items():
            f.write(f"| {t} | {n:,} |\n")
        f.write("\nR4 (estático): columnas `product_name_lenght` y `product_description_lenght` "
                "renombradas a `*_length`.\n")


def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def connect():
    import psycopg2                                 # import tardío
    load_env()
    return psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ.get("PGDATABASE", "olist"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", ""),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--simulate-error", action="store_true",
                    help="provoca un error al final para demostrar el rollback")
    a = ap.parse_args()

    needed = [f for f, _ in SPECS.values()] + [TRANSLATION_FILE]
    absent = [f for f in needed if not (a.data_dir / f).exists()]
    if absent:
        sys.exit(f"Faltan CSV en {a.data_dir}: {absent}\nEjecuta antes: python etl/download_data.py --zip <archivo.zip>")

    conn = connect()                # autocommit=False por defecto -> una sola transacción
    try:
        before = table_counts(conn)
    except Exception as e:
        conn.rollback()
        sys.exit(f"No se pudo leer el esquema ({e}).\nEjecuta primero sql/schema.sql en la base de datos.")
    conn.rollback()
    if any(before.values()):
        sys.exit(f"Las tablas ya contienen datos: {before}\nVuelve a ejecutar sql/schema.sql para empezar limpio.")

    try:
        log = run_load(conn, a.data_dir, a.simulate_error)
        conn.commit()                                       # <- único COMMIT
    except Exception as e:
        conn.rollback()                                     # <- si algo falla, nada se guarda
        print(f"\n!! ERROR: {type(e).__name__}: {str(e).strip()}")
        print("!! ROLLBACK ejecutado. Filas por tabla ahora mismo:")
        for t, n in table_counts(conn).items():
            print(f"   {t:18s} {n:>10,}")
        conn.rollback()
        sys.exit(1)

    write_log(log)
    print("\nCOMMIT correcto. Filas por tabla en la BD:")
    for t, n in table_counts(conn).items():
        print(f"   {t:18s} {n:>10,}")
    print(f"\nLog de limpieza escrito en {LOG_FILE}")
    conn.close()


if __name__ == "__main__":
    main()
