"""밥때 손님 페이지 (다이어리 모양). st.set_page_config는 여기서 부르지 않는다 (병합 규칙)."""

from __future__ import annotations

import streamlit as st

from . import cards, diary, storage
from .config import BREED_BY_ID, BREEDS, SLOT_LABELS, SLOTS
from .logic import compute_streak, day_count, loyalty_of, recent_days, today_kst
from .models import CollectionCard, GuestVisit
from .service import process_pending_events


def _html(html: str) -> None:
    """카드 기울기·홀로그램 스크립트(cards.TILT_JS)가 돌도록 JavaScript를 허용한다.
    넣는 값은 config.toml과 API 사진 주소, 줄인 밥상 사진뿐이고, 글자는 모두 escape()를 거친다."""
    st.html(html, unsafe_allow_javascript=True)


def render() -> None:
    for v in process_pending_events():
        st.toast(f"똑똑, {SLOT_LABELS[v.slot]} 손님이 찾아왔어요!", icon="🐾")

    visits = storage.get_visits()
    collection = storage.get_cards()
    today = today_kst()

    streak, best = compute_streak(visits, today)
    _html(diary.header(
        today, day_count(visits, today), streak, best, recent_days(visits, today), len(collection), len(BREEDS)
    ))

    today_tab, album_tab = st.tabs(["📔 오늘의 일기", "📒 카드 앨범"])
    with today_tab:
        _today(visits, collection)
    with album_tab:
        _album(collection)


def _today(visits: list[GuestVisit], collection: dict[str, CollectionCard]) -> None:
    unseen = sorted((v for v in visits if not v.seen), key=lambda v: (v.date, SLOTS.index(v.slot)))
    if unseen:
        _arrival(unseen[0], collection[unseen[0].breed_id])

    today = today_kst().isoformat()
    slots = {
        v.slot: (BREED_BY_ID[v.breed_id], v.image_url, v.meal_photo)
        for v in visits
        if v.date == today and v.seen
    }
    _html(diary.today_page(slots, waiting=max(0, len(unseen) - 1)))


def _arrival(visit: GuestVisit, card: CollectionCard) -> None:
    """손님 방문 일기: 카드가 뒤집히며 나오고, 버튼을 누르면 앨범에 붙는다."""
    breed = BREED_BY_ID[visit.breed_id]
    is_new = card.first_met_at == visit.visited_at
    card_html = cards.card(breed, card, image_url=visit.image_url, is_new=is_new)
    _html(diary.arrival(
        visit.slot, breed, card_html, visit.meal_photo, is_new, loyalty_of(card.met_count), photo_ok=bool(visit.image_url)
    ))
    if st.button("📒 카드 앨범에 붙이기", key=f"guest_seen_{visit.id}", type="primary", use_container_width=True):
        storage.mark_seen(visit.id)
        st.rerun()


def _album(collection: dict[str, CollectionCard]) -> None:
    choice = st.radio(
        "손님 종류", ["전체", "강아지", "고양이"], horizontal=True, key="guest_dex_filter", label_visibility="collapsed"
    )
    species = {"강아지": "dog", "고양이": "cat"}.get(choice)
    shown = [b for b in BREEDS if species is None or b.species == species]
    collected = [b for b in shown if b.id in collection]
    _html(diary.album(
        choice, len(collected), len(shown), [cards.card(b, collection.get(b.id)) for b in shown], empty=not collection
    ))

    if collected:
        pick = st.selectbox(
            "카드 꺼내 보기",
            collected,
            index=None,
            format_func=lambda b: b.name,
            placeholder="모은 카드를 골라 자세히 보기",
            key="guest_dex_detail",
        )
        if pick:
            card = collection[pick.id]
            _html(diary.detail(pick, card, cards.card(pick, card), loyalty_of(card.met_count)))
