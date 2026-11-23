"""Caminhos centralizados do projeto."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "camposync_demo.db"
CSV_DIR = DATA_DIR / "csv"
DOCS_DIR = DATA_DIR / "documentos"
CHROMA_DIR = DATA_DIR / "chroma_db"
