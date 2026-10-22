"""밥때 손님 페이지. st.set_page_config는 여기서 부르지 않는다 (병합 규칙)."""

from __future__ import annotations

import streamlit as st

from . import cards, storage
from .config import BREED_BY_ID, BREEDS, SLOT_LABELS, SLOTS
from .logic import compute_streak, day_count, loyalty_of, recent_days, today_kst
from .models import CollectionCard, GuestVisit
from .service import process_pending_events


def render() -> None:
    for v in process_pending_events():
        st.toast(f"똑똑, {SLOT_LABELS[v.slot]} 손님이 찾아왔어요!", icon="🐾")

    visits = storage.get_visits()
    collection = storage.get_cards()
    today = today_kst()

    st.title("밥때 손님")
    streak, best = compute_streak(visits, today)
    st.html(cards.day_board(day_count(visits, today), streak, best, recent_days(visits, today), today))
    st.progress(len(collection) / len(BREEDS), text=f"📖 도감 {len(collection)} / {len(BREEDS)}장 모음")

    today_tab, dex_tab = st.tabs(["오늘의 손님", "도감"])
    with today_tab:
        _today(visits, collection)
    with dex_tab:
        _dex(collection)


def _today(visits: list[GuestVisit], collection: dict[str, CollectionCard]) -> None:
    unseen = sorted((v for v in visits if not v.seen), key=lambda v: (v.date, SLOTS.index(v.slot)))
    if unseen:
        _arrival(unseen[0], collection[unseen[0].breed_id])
        if len(unseen) > 1:
            st.caption(f"문 앞에 손님이 {len(unseen) - 1}명 더 기다리고 있어요.")

    today = today_kst().isoformat()
    slots = {
        v.slot: (BREED_BY_ID[v.breed_id], v.image_url, v.meal_photo)
        for v in visits
        if v.date == today and v.seen
    }
    st.markdown("#### 오늘의 3칸")
    st.html(cards.today_slots(slots))


def _arrival(visit: GuestVisit, card: CollectionCard) -> None:
    """손님 방문 연출: 카드가 뒤집히며 나오고, 버튼을 누르면 도감에 붙는다."""
    breed = BREED_BY_ID[visit.breed_id]
    is_new = card.first_met_at == visit.visited_at
    with st.container(border=True):
        st.markdown(f"### 🔔 똑똑, {SLOT_LABELS[visit.slot]} 손님이 찾아왔어요!")
        guest_card = cards.reveal(cards.card(breed, card, image_url=visit.image_url, is_new=is_new))
        if visit.meal_photo:
            meal_col, card_col = st.columns(2, vertical_alignment="center")
            meal_col.image(visit.meal_photo, caption=f"내 {SLOT_LABELS[visit.slot]} 밥상 냄새를 맡고 왔어요", use_container_width=True)
            with card_col:
                st.html(guest_card)
        else:
            st.html(guest_card)
        lv = loyalty_of(card.met_count)
        if is_new:
            st.success(f"새 카드 획득! {breed.name} 카드를 도감에 붙일 수 있어요.")
        elif lv.remaining is not None:
            st.info(f"{breed.name}와(과) 다시 만났어요. 다음 단골 레벨까지 {lv.remaining}번 남았어요.")
        if not visit.image_url:
            st.caption("사진을 불러오지 못해 그림으로 대신했어요.")
        if st.button("📖 도감에 붙이기", key=f"guest_seen_{visit.id}", type="primary", use_container_width=True):
            storage.mark_seen(visit.id)
            st.rerun()


def _dex(collection: dict[str, CollectionCard]) -> None:
    choice = st.radio(
        "손님 종류", ["전체", "강아지", "고양이"], horizontal=True, key="guest_dex_filter", label_visibility="collapsed"
    )
    species = {"강아지": "dog", "고양이": "cat"}.get(choice)
    shown = [b for b in BREEDS if species is None or b.species == species]
    collected = [b for b in shown if b.id in collection]
    st.caption(f"{choice} {len(collected)} / {len(shown)}장")

    if not collection:
        st.info("아직 모은 카드가 없어요. 끼니를 기록하면 첫 손님 카드가 생겨요.")
    st.html(cards.grid([cards.card(b, collection.get(b.id)) for b in shown]))

    if collected:
        pick = st.selectbox(
            "카드 자세히 보기",
            collected,
            index=None,
            format_func=lambda b: b.name,
            placeholder="모은 카드를 골라 자세히 보기",
            key="guest_dex_detail",
        )
        if pick:
            _detail(pick.id, collection[pick.id])


def _detail(breed_id: str, card: CollectionCard) -> None:
    breed = BREED_BY_ID[breed_id]
    lv = loyalty_of(card.met_count)
    with st.container(border=True):
        left, right = st.columns([1, 1.3])
        with left:
            st.html(cards.CSS + cards.card(breed, card))
        with right:
            st.subheader(breed.name)
            st.write(breed.description)
            st.markdown(
                f"- 처음 만난 날: {card.first_met_at[:10].replace('-', '.')}\n"
                f"- 만난 횟수: {card.met_count}번\n"
                f"- 단골 레벨: {cards.LEVEL_BADGES.get(lv.level, '')} Lv.{lv.level} {lv.title}"
                + (f" (다음 레벨까지 {lv.remaining}번)" if lv.remaining is not None else " (최고 레벨!)")
            )
