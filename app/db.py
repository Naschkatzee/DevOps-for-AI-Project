import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

DB_PATH = Path("data") / "vacation_agent.db"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")  # better reliability
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS plans (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                query_preview TEXT NOT NULL,
                parsed_json TEXT NOT NULL,
                decision_json TEXT NOT NULL,
                weather_json TEXT,
                attractions_json TEXT,
                itinerary_json TEXT NOT NULL,
                status TEXT NOT NULL,
                duration_ms INTEGER NOT NULL
            );
            """
        )
        conn.commit()


def insert_plan(
    *,
    plan_id: str,
    created_at: str,
    query_preview: str,
    parsed: dict[str, Any],
    decision: dict[str, Any],
    weather: Optional[dict[str, Any]],
    attractions: Optional[dict[str, Any]],
    itinerary: list[str],
    status: str,
    duration_ms: int,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO plans (
                id, created_at, query_preview,
                parsed_json, decision_json, weather_json,
                attractions_json,
                itinerary_json, status, duration_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan_id,
                created_at,
                query_preview,
                json.dumps(parsed, ensure_ascii=False),
                json.dumps(decision, ensure_ascii=False),
                json.dumps(weather, ensure_ascii=False) if weather is not None else None,
                json.dumps(attractions, ensure_ascii=False) if attractions is not None else None,
                json.dumps(itinerary, ensure_ascii=False),
                status,
                duration_ms,
            ),
        )
        conn.commit()
