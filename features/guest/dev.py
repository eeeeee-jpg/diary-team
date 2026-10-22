"""밥때 손님 단독 실행: streamlit run features/guest/dev.py

한 끼 서비스 대신 화면 맨 위의 "끼니 기록하기"(밥상 사진 선택)로 손님 방문을 검증한다.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 저장소 루트에서 features.guest를 찾도록

from features.guest import get_today_summary, page  # noqa: E402
from features.guest.config import SLOT_LABELS, SLOTS  # noqa: E402
from features.guest.events import MEAL_EVENTS_KEY, emit_mock_meal_logged  # noqa: E402
from features.guest.logic import now_kst, today_kst  # noqa: E402
from features.guest.storage import clear_all, has_visit  # noqa: E402

st.set_page_config(page_title="밥때 손님 (단독 실행)", page_icon="🐾", layout="centered")

SLOT_ICONS = {"breakfast": "🌅", "lunch": "☀️", "dinner": "🌙"}


def _logged(day: str, slot: str) -> bool:
    """이미 손님이 왔거나, 방금 눌러서 처리 대기 중인 끼니"""
    pending = st.session_state.get(MEAL_EVENTS_KEY, [])
    return has_visit(day, slot) or any(e["date"] == day and e["slot"] == slot for e in pending)


def _slot_now() -> str:
    hour = now_kst().hour
    return "breakfast" if hour < 11 else "lunch" if hour < 16 else "dinner"


def _log_meal(day: str, slot: str, photo: bytes | None) -> None:
    emit_mock_meal_logged({"meal_log_id": f"mock-{uuid.uuid4().hex}", "slot": slot, "date": day, "photo": photo})
    st.session_state["guest_dev_upload_n"] = st.session_state.get("guest_dev_upload_n", 0) + 1  # 사진 칸 비우기
    nxt = next((s for s in SLOTS if s != slot and not _logged(day, s)), None)
    if nxt:
        st.session_state["guest_dev_slot"] = nxt  # 다음 끼니로 넘겨 두기


with st.container(border=True):
    st.markdown("**🍚 끼니 기록하기** · 개발용 (병합하면 '오늘의 한 끼' 페이지의 기록으로 바뀌어요)")
    day = st.date_input("끼니 날짜", value=today_kst(), key="guest_dev_date").isoformat()
    st.session_state.setdefault("guest_dev_slot", _slot_now())  # 처음엔 지금 시간의 끼니
    slot = st.radio(
        "어떤 끼니인가요?",
        SLOTS,
        format_func=lambda s: f"{SLOT_ICONS[s]} {SLOT_LABELS[s]}" + (" ✓" if _logged(day, s) else ""),
        horizontal=True,
        key="guest_dev_slot",
    )
    if _logged(day, slot):
        st.info(f"{SLOT_LABELS[slot]}은 이미 기록했어요. 손님은 끼니마다 한 번만 와요.")
    else:
        upload = st.file_uploader(
            "📷 밥상 사진 (선택) · 휴대폰에서는 바로 찍을 수도 있어요",
            type=["jpg", "jpeg", "png", "webp"],
            key=f"guest_dev_photo_{st.session_state.get('guest_dev_upload_n', 0)}",
        )
        photo = upload.getvalue() if upload else None
        if photo:
            st.image(photo, width=220, caption="이 사진으로 기록해요")
        st.button(
            f"🍚 {SLOT_LABELS[slot]} 기록하기",
            key="guest_dev_log",
            type="primary",
            use_container_width=True,
            on_click=_log_meal,
            args=(day, slot, photo),
        )

page()

with st.expander("🧪 개발 도구"):
    st.code(f"get_today_summary()\n{get_today_summary()}", language=None)
    if st.button("손님 기록 모두 지우기", key="guest_dev_reset"):
        clear_all()
        st.session_state[MEAL_EVENTS_KEY] = []
        st.rerun()
