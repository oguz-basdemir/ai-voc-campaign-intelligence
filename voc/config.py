import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 10000
MAX_TEXT_LENGTH = 5000


def db_path() -> Path:
    return Path(os.getenv("VOC_DB_PATH", str(ROOT / "data" / "voc.db")))
