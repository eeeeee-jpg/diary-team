"""순수 로직. Streamlit 없이 테스트한다."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

from .config import LOYALTY_LEVELS, RARITY_WEIGHTS, SLOTS
from .models import Breed, CollectionCard, GuestVisit, Rarity, TodaySummary

# 대한민국 기준 날짜. 배포 서버(UTC)에서도 오늘이 하루 밀리지 않게 한다. (한국은 서머타임 없음)
KST = timezone(timedelta(hours=9))


def now_kst() -> datetime:
    return datetime.now(KST)


def today_kst() -> date:
    return now_kst().date()


def pick_breed(
    breeds: list[Breed],
    weights: dict[Rarity, int] = RARITY_WEIGHTS,
    rng: random.Random | None = None,
) -> Breed:
    """희귀도를 가중치로 뽑은 뒤, 그 희귀도의 품종 중에서 균등하게 뽑는다."""
    rng = rng or random.Random()
    rarities = [r for r, w in weights.items() if w > 0 and any(b.rarity == r for b in breeds)]
    if not rarities:
        raise ValueError("뽑을 수 있는 품종이 없습니다")
    rarity = rng.choices(rarities, [weights[r] for r in rarities])[0]
    return rng.choice([b for b in breeds if b.rarity == rarity])


@dataclass(frozen=True)
class Loyalty:
    level: int
    title: str
    remaining: int | None  # 다음 레벨까지 남은 만남 횟수. 최고 레벨이면 None


def loyalty_of(met_count: int) -> Loyalty:
    current = None
    for lv in LOYALTY_LEVELS:
        if met_count >= lv["min_count"]:
            current = lv
    nxt = next((lv for lv in LOYALTY_LEVELS if lv["min_count"] > met_count), None)
    return Loyalty(
        level=current["level"] if current else 0,
        title=current["title"] if current else "",
        remaining=nxt["min_count"] - met_count if nxt else None,
    )


def apply_visit(
    prev: CollectionCard | None, breed_id: str, visited_at: str, image_url: str | None = None
) -> tuple[CollectionCard, bool, bool]:
    """방문 1건을 도감 카드에 반영한다. (카드, 첫 만남인지, 레벨이 올랐는지)

    사진은 가장 최근에 받은 것으로 바꾸고, 이번에 못 받았으면 예전 사진을 둔다.
    """
    met_count = (prev.met_count if prev else 0) + 1
    level = loyalty_of(met_count).level
    card = CollectionCard(
        breed_id=breed_id,
        first_met_at=prev.first_met_at if prev else visited_at,
        met_count=met_count,
        loyalty_level=level,
        image_url=image_url or (prev.image_url if prev else None),
    )
    return card, prev is None, prev is not None and level > prev.loyalty_level


def compute_streak(visits: Iterable[GuestVisit], today: date) -> tuple[int, int]:
    """연속 일수 (D-3): 하루 3칸을 모두 채운 날이 이어진 수와 최고 기록.

    오늘이 아직 다 안 찼으면 어제까지를 센다.
    """
    slots_by_date: dict[date, set[str]] = {}
    for v in visits:
        slots_by_date.setdefault(date.fromisoformat(v.date), set()).add(v.slot)
    full = {d for d, s in slots_by_date.items() if s >= set(SLOTS)}

    cur = today if today in full else today - timedelta(days=1)
    current = 0
    while cur in full:
        current += 1
        cur -= timedelta(days=1)

    best = 0
    for d in full:
        if d - timedelta(days=1) in full:
            continue  # 연속 구간의 시작에서만 센다
        n = 0
        while d + timedelta(days=n) in full:
            n += 1
        best = max(best, n)
    return current, best


def day_count(visits: Iterable[GuestVisit], today: date) -> int:
    """첫 손님을 만난 날을 1일째로 센 오늘의 일차. 아직 손님이 없으면 0."""
    days = [date.fromisoformat(v.date) for v in visits]
    days = [d for d in days if d <= today]
    return (today - min(days)).days + 1 if days else 0


def recent_days(visits: Iterable[GuestVisit], today: date, n: int = 7) -> list[tuple[date, set[str]]]:
    """최근 n일(오늘 포함, 오래된 날부터)과 그날 채운 끼니 칸."""
    slots_by_date: dict[str, set[str]] = {}
    for v in visits:
        slots_by_date.setdefault(v.date, set()).add(v.slot)
    days = [today - timedelta(days=i) for i in range(n - 1, -1, -1)]
    return [(d, slots_by_date.get(d.isoformat(), set())) for d in days]


def build_summary(visits_today: int, collected: int, total_breeds: int) -> TodaySummary:
    if visits_today == 0:
        status = "empty"
    elif visits_today >= len(SLOTS):
        status = "done"
    else:
        status = "in_progress"
    return {
        "title": "밥때 손님",
        "value": f"오늘 손님 {visits_today}/{len(SLOTS)} · 도감 {collected}/{total_breeds}",
        "status": status,
    }


MENU_MAX_LEN = 30  # 폴라로이드 한 줄에 들어가는 길이


def clean_menu(text: str | None) -> str | None:
    """먹은 메뉴 글: 공백·줄바꿈을 한 칸으로 줄이고 MENU_MAX_LEN자까지만. 비어 있으면 None."""
    if not text:
        return None
    cleaned = " ".join(text.split())[:MENU_MAX_LEN]
    return cleaned or None
