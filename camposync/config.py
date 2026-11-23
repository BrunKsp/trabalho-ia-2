"""Caminhos centralizados do projeto."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
# CAMPOSYNC_DB permite apontar para outra base (ex.: testes) sem tocar na versionada
DB_PATH = Path(os.environ.get("CAMPOSYNC_DB", DATA_DIR / "camposync_demo.db"))
CSV_DIR = DATA_DIR / "csv"
DOCS_DIR = DATA_DIR / "documentos"
CHROMA_DIR = DATA_DIR / "chroma_db"
