"""주유 기록과 일별 평균가 스냅샷 저장 (SQLite)."""

import os
import sqlite3
from contextlib import closing
from pathlib import Path

DB_PATH = Path(os.environ.get("FUEL_DB_PATH", Path(__file__).resolve().parent / ".data" / "fuel.db"))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS fuel_records (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    date         TEXT NOT NULL,          -- YYYY-MM-DD
    station_name TEXT NOT NULL,
    station_id   TEXT,                   -- 오피넷 UNI_ID (목록에서 골랐을 때)
    prodcd       TEXT NOT NULL,
    price_per_l  REAL NOT NULL,
    liters       REAL NOT NULL,
    sido_cd      TEXT NOT NULL,
    sigun_cd     TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS fuel_avg_snapshots (
    date       TEXT NOT NULL,
    area_level TEXT NOT NULL,            -- 'sido' | 'sigun'
    area_cd    TEXT NOT NULL,
    area_nm    TEXT NOT NULL,
    prodcd     TEXT NOT NULL,
    price      REAL NOT NULL,
    PRIMARY KEY (date, area_level, area_cd, prodcd)
);
"""

_RECORD_FIELDS = ("date", "station_name", "station_id", "prodcd", "price_per_l", "liters", "sido_cd", "sigun_cd")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def total_price(record: dict) -> int:
    return round(record["price_per_l"] * record["liters"])


def add_record(**fields) -> int:
    values = [fields.get(f) for f in _RECORD_FIELDS]
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            f"INSERT INTO fuel_records ({', '.join(_RECORD_FIELDS)}) VALUES ({', '.join('?' * len(_RECORD_FIELDS))})",
            values,
        )
        return cur.lastrowid


def update_record(record_id: int, **fields) -> None:
    cols = [f for f in _RECORD_FIELDS if f in fields]
    if not cols:
        return
    with closing(_connect()) as conn, conn:
        conn.execute(
            f"UPDATE fuel_records SET {', '.join(f'{c} = ?' for c in cols)} WHERE id = ?",
            [fields[c] for c in cols] + [record_id],
        )


def delete_record(record_id: int) -> None:
    with closing(_connect()) as conn, conn:
        conn.execute("DELETE FROM fuel_records WHERE id = ?", (record_id,))


def list_records() -> list[dict]:
    """최근 날짜 순."""
    with closing(_connect()) as conn:
        rows = conn.execute("SELECT * FROM fuel_records ORDER BY date DESC, id DESC").fetchall()
    return [dict(r) for r in rows]


def monthly_totals(records: list[dict]) -> list[dict]:
    months: dict[str, dict] = {}
    for r in records:
        m = months.setdefault(r["date"][:7], {"month": r["date"][:7], "count": 0, "liters": 0.0, "total": 0})
        m["count"] += 1
        m["liters"] += r["liters"]
        m["total"] += total_price(r)
    return sorted(months.values(), key=lambda m: m["month"], reverse=True)


def save_snapshots(date: str, area_level: str, rows: list[dict]) -> None:
    """같은 날·지역·유종은 마지막 값으로 덮어쓴다."""
    with closing(_connect()) as conn, conn:
        conn.executemany(
            "INSERT OR REPLACE INTO fuel_avg_snapshots VALUES (?, ?, ?, ?, ?, ?)",
            [(date, area_level, r["area_cd"], r["area_nm"], r["prodcd"], r["price"]) for r in rows],
        )


def get_avg(date: str, area_level: str, area_cd: str, prodcd: str) -> dict | None:
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT * FROM fuel_avg_snapshots WHERE date = ? AND area_level = ? AND area_cd = ? AND prodcd = ?",
            (date, area_level, area_cd, prodcd),
        ).fetchone()
    return dict(row) if row else None
