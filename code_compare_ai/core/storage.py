import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

from config import HISTORY_DB_PATH


def _connect() -> sqlite3.Connection:
    HISTORY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(HISTORY_DB_PATH)



def init_history_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS review_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                file_a_name TEXT NOT NULL,
                file_b_name TEXT NOT NULL,
                provider_name TEXT NOT NULL,
                model_name TEXT NOT NULL,
                score REAL NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        conn.commit()



def save_history_entry(entry: Dict[str, Any]) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO review_history (
                created_at,
                file_a_name,
                file_b_name,
                provider_name,
                model_name,
                score,
                payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry["created_at"],
                entry["file_a_name"],
                entry["file_b_name"],
                entry["provider_name"],
                entry["model_name"],
                float(entry.get("score", 0)),
                json.dumps(entry, ensure_ascii=False),
            ),
        )
        conn.commit()



def list_history_entries(limit: int = 20) -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT payload_json
            FROM review_history
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    result = []
    for row in rows:
        try:
            result.append(json.loads(row[0]))
        except json.JSONDecodeError:
            continue
    return result
