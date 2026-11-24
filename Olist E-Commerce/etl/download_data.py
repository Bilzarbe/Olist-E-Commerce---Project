"""
Prepara los datos crudos en data/raw/ (esa carpeta NO se sube a Git).

Uso:
    python etl/download_data.py --zip "C:\\ruta\\al\\archive.zip"   # desde un zip local
    python etl/download_data.py                                    # intenta bajarlo de Kaggle (kagglehub)

Dataset: Brazilian E-Commerce Public Dataset by Olist (Kaggle: olistbr/brazilian-ecommerce)
"""
import argparse
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"


def extract_zip(zip_path: Path) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if name.lower().endswith(".csv"):
                target = RAW / Path(name).name          # aplanamos rutas internas
                with zf.open(name) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                print(f"  extraído: {target.name}")


def download_kaggle() -> None:
    try:
        import kagglehub                                # pip install kagglehub
    except ImportError:
        sys.exit("kagglehub no está instalado. Usa: pip install kagglehub  (o pasa --zip)")
    path = Path(kagglehub.dataset_download("olistbr/brazilian-ecommerce"))
    RAW.mkdir(parents=True, exist_ok=True)
    for f in path.glob("*.csv"):
        shutil.copyfile(f, RAW / f.name)
        print(f"  copiado: {f.name}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", type=Path, help="zip descargado manualmente de Kaggle")
    a = ap.parse_args()
    if a.zip:
        extract_zip(a.zip)
    else:
        download_kaggle()
    print(f"Listo. Datos crudos en {RAW}")
