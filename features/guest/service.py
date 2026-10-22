"""끼니 기록 이벤트 → 손님 방문 처리."""

from __future__ import annotations

import logging
import uuid

import streamlit as st

from . import storage
from .clients.photos import fetch_photo
from .config import BREEDS
from .events import pending_meal_events
from .logic import apply_visit, build_summary, now_kst, pick_breed, today_kst
from .meal_photo import shrink
from .models import GuestVisit, MealLoggedEvent, TodaySummary

log = logging.getLogger("guest")

_PROCESSED = "guest_processed_meal_log_ids"


def track(name: str, **props: str | int) -> None:
    """PRD 9장 분석 이벤트. 공통 분석 모듈이 정해지면 이 함수만 바꾼다. 개인 식별 정보는 넣지 않는다."""
    log.info("analytics %s %s", name, props)


def handle_meal_logged(event: MealLoggedEvent) -> GuestVisit | None:
    """D-1: 끼니 기록 1건에 손님 1마리. 같은 날 같은 끼니에 이미 왔으면 아무것도 하지 않는다."""
    if storage.has_visit(event["date"], event["slot"]):
        return None

    breed = pick_breed(BREEDS)
    visit = GuestVisit(
        id=uuid.uuid4().hex,
        meal_log_id=event["meal_log_id"],
        breed_id=breed.id,
        date=event["date"],
        slot=event["slot"],
        visited_at=now_kst().isoformat(timespec="seconds"),
        image_url=fetch_photo(breed),  # 실패하면 None → 화면에서 SVG 일러스트로 대신
        meal_photo=shrink(event.get("photo")),
    )
    result: dict[str, bool] = {}

    def update(prev):
        card, result["unlocked"], result["leveled_up"] = apply_visit(
            prev, breed.id, visit.visited_at, visit.image_url
        )
        return card

    card = storage.save_visit(visit, update)
    if card is None:
        return None

    track("guest_visit", breed_id=breed.id, rarity=breed.rarity)
    if result["unlocked"]:
        track("card_unlocked", breed_id=breed.id)
    if result["leveled_up"]:
        track("loyalty_level_up", breed_id=breed.id, level=card.loyalty_level)
    return visit


def process_pending_events() -> list[GuestVisit]:
    """대기 중인 끼니 이벤트 중 아직 처리하지 않은 것을 처리한다."""
    processed: set[str] = st.session_state.setdefault(_PROCESSED, set())
    arrived = []
    for event in pending_meal_events():
        if event["meal_log_id"] in processed:
            continue
        processed.add(event["meal_log_id"])
        visit = handle_meal_logged(event)
        if visit:
            arrived.append(visit)
    return arrived


def get_today_summary() -> TodaySummary:
    process_pending_events()
    today = today_kst().isoformat()
    visits_today = sum(1 for v in storage.get_visits() if v.date == today)
    return build_summary(visits_today, len(storage.get_cards()), len(BREEDS))
