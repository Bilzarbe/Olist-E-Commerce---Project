"""Acceso a PostgreSQL: SOLO envía SQL + parámetros y devuelve las filas tal cual."""
import os
from pathlib import Path
import psycopg2

ROOT = Path(__file__).resolve().parent.parent


def _load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def run_query(sql, params=None):
    """Ejecuta una consulta de SOLO LECTURA con parámetros enlazados (%(nombre)s).
    Los valores NUNCA se concatenan en el texto SQL -> sin inyección SQL."""
    _load_env()
    conn = psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ.get("PGDATABASE", "olist"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", ""),
        connect_timeout=5,
        options="-c statement_timeout=30000",      # corta consultas de más de 30 s
    )
    try:
        conn.set_session(readonly=True, autocommit=True)   # la app no puede modificar datos
        with conn.cursor() as cur:
            cur.execute(sql, params or {})
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
        return cols, rows
    finally:
        conn.close()
