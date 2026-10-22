"""밥때 손님 저장 계층. 저장 방식이 정해지면 이 파일만 바꾼다.

지금은 st.session_state에만 저장한다 (개발용). 새로고침하거나 세션이 끝나면 사라진다.
"""

from __future__ import annotations

from typing import Callable

import streamlit as st

from .models import CollectionCard, GuestVisit, Slot

_VISITS = "guest_visits"
_CARDS = "guest_cards"


def _visits() -> list[GuestVisit]:
    return st.session_state.setdefault(_VISITS, [])


def _cards() -> dict[str, CollectionCard]:
    return st.session_state.setdefault(_CARDS, {})


def get_visits() -> list[GuestVisit]:
    return list(_visits())


def get_cards() -> dict[str, CollectionCard]:
    return dict(_cards())


def has_visit(date: str, slot: Slot) -> bool:
    return any(v.date == date and v.slot == slot for v in _visits())


def save_visit(
    visit: GuestVisit,
    update_card: Callable[[CollectionCard | None], CollectionCard],
) -> CollectionCard | None:
    """방문 저장과 도감 카드 갱신. 같은 날 같은 끼니 방문이 이미 있으면 저장하지 않고 None."""
    if has_visit(visit.date, visit.slot):
        return None
    card = update_card(_cards().get(visit.breed_id))
    _visits().append(visit)
    _cards()[visit.breed_id] = card
    return card


def mark_seen(visit_id: str) -> None:
    for v in _visits():
        if v.id == visit_id:
            v.seen = True


def clear_all() -> None:
    """개발용: 손님 기록 전체 삭제"""
    st.session_state[_VISITS] = []
    st.session_state[_CARDS] = {}
