"""끼니 기록 저장. 저장 방식은 미정(PRD 13장)이라 이 파일에만 둔다.

임시 구현: 서버 로컬 SQLite 파일. 사용자 구분이 없어 모든 방문자가 같은 기록을 공유하고,
Community Cloud에서 재시작 후 남는지도 확인되지 않았다. 개발·시연용으로만 쓴다.
"""

import sqlite3
import uuid
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path

from .models import LOG_SLOTS, MealLog

DB_PATH = Path(__file__).parent / ".data" / "meal.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meal_logs (
    id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    slot TEXT NOT NULL,
    menu_name TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (date, slot)
)
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    return conn


def _to_log(row: sqlite3.Row) -> MealLog:
    return MealLog(**dict(row))


def get_logs(day: date) -> dict[str, MealLog]:
    """해당 날짜의 기록을 slot -> MealLog로 돌려준다."""
    with closing(_connect()) as conn:
        rows = conn.execute("SELECT * FROM meal_logs WHERE date = ?", (day.isoformat(),)).fetchall()
    return {r["slot"]: _to_log(r) for r in rows}


def recent_menu_names(today: date, days: int) -> list[str]:
    """today를 포함해 최근 days일 동안 기록한 메뉴 이름."""
    since = (today - timedelta(days=days - 1)).isoformat()
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT menu_name FROM meal_logs WHERE date >= ? AND date <= ?",
            (since, today.isoformat()),
        ).fetchall()
    return [r["menu_name"] for r in rows]


def save_log(day: date, slot: str, menu_name: str, source: str) -> tuple[MealLog, bool]:
    """기록을 저장한다. 같은 날 같은 slot이 있으면 덮어쓰고 id는 유지한다.

    반환: (기록, 새로 만들었는지)
    """
    if slot not in LOG_SLOTS:
        raise ValueError(f"기록할 수 없는 끼니예요: {slot}")
    menu_name = menu_name.strip()
    if not menu_name:
        raise ValueError("메뉴 이름이 비어 있어요")
    with closing(_connect()) as conn, conn:
        row = conn.execute(
            "SELECT * FROM meal_logs WHERE date = ? AND slot = ?", (day.isoformat(), slot)
        ).fetchone()
        if row is not None:
            conn.execute(
                "UPDATE meal_logs SET menu_name = ?, source = ? WHERE id = ?",
                (menu_name, source, row["id"]),
            )
            created = False
            log_id = row["id"]
            created_at = row["created_at"]
        else:
            created = True
            log_id = uuid.uuid4().hex
            created_at = datetime.now().isoformat(timespec="seconds")
            conn.execute(
                "INSERT INTO meal_logs (id, date, slot, menu_name, source, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (log_id, day.isoformat(), slot, menu_name, source, created_at),
            )
    return MealLog(log_id, day.isoformat(), slot, menu_name, source, created_at), created


def delete_log(day: date, slot: str) -> None:
    with closing(_connect()) as conn, conn:
        conn.execute("DELETE FROM meal_logs WHERE date = ? AND slot = ?", (day.isoformat(), slot))
