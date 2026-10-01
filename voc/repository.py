import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pandas as pd

from voc.config import db_path


@contextmanager
def connection():
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=20)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS datasets (id TEXT PRIMARY KEY, name TEXT NOT NULL, "
            "created_at TEXT NOT NULL, metadata TEXT NOT NULL, records TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS analyses (id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL, "
            "created_at TEXT NOT NULL, result TEXT NOT NULL)"
        )
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def now() -> str:
    return datetime.now(UTC).isoformat()


def save_dataset(frame: pd.DataFrame, name: str, ingestion: dict) -> dict:
    records = frame.to_json(orient="records", force_ascii=False)
    identifier = "ds_" + hashlib.sha256(records.encode()).hexdigest()[:20]
    metadata = {
        "id": identifier,
        "name": name[:120],
        "synthetic": True,
        "provenance": "Synthetic demo or uploader-attested synthetic data",
        "rows": len(frame),
        "created_at": now(),
        "ingestion": ingestion,
        "options": {
            field: sorted(frame[field].unique().tolist())
            for field in ["source", "customer_type", "product", "market"]
        },
        "date_from": str(frame.date.min()),
        "date_to": str(frame.date.max()),
    }
    with connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO datasets VALUES (?, ?, ?, ?, ?)",
            (identifier, metadata["name"], metadata["created_at"], json.dumps(metadata), records),
        )
    return get_dataset(identifier)[0]


def get_dataset(identifier: str) -> tuple[dict, pd.DataFrame]:
    with connection() as conn:
        row = conn.execute("SELECT metadata, records FROM datasets WHERE id = ?", (identifier,)).fetchone()
    if row is None:
        raise KeyError("Dataset not found")
    return json.loads(row["metadata"]), pd.DataFrame(json.loads(row["records"]))


def list_datasets() -> list[dict]:
    with connection() as conn:
        rows = conn.execute("SELECT metadata FROM datasets ORDER BY created_at DESC").fetchall()
    return [json.loads(r["metadata"]) for r in rows]


def save_analysis(dataset_id: str, result: dict) -> dict:
    identifier = "run_" + uuid4().hex
    result = {**result, "id": identifier, "dataset_id": dataset_id, "created_at": now()}
    with connection() as conn:
        conn.execute(
            "INSERT INTO analyses VALUES (?, ?, ?, ?)",
            (identifier, dataset_id, result["created_at"], json.dumps(result)),
        )
    return result


def get_analysis(identifier: str) -> dict:
    with connection() as conn:
        row = conn.execute("SELECT result FROM analyses WHERE id = ?", (identifier,)).fetchone()
    if row is None:
        raise KeyError("Analysis not found")
    return json.loads(row["result"])


def list_analyses(dataset_id: str) -> list[dict]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT id, dataset_id, created_at FROM analyses WHERE dataset_id = ? "
            "ORDER BY created_at DESC LIMIT 20",
            (dataset_id,),
        ).fetchall()
    return [dict(r) for r in rows]
