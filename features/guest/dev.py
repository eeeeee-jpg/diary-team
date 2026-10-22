"""밥때 손님 단독 실행: streamlit run features/guest/dev.py

한 끼 서비스 대신 화면 맨 위의 "오늘 뭐 먹었어?" 메모지(끼니·메뉴 글·밥상 사진 선택)로 손님 방문을 검증한다.
"""

from __future__ import annotations

import html
import sys
import uuid
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 저장소 루트에서 features.guest를 찾도록

from features.guest import get_today_summary, page  # noqa: E402
from features.guest.config import SLOT_LABELS, SLOTS  # noqa: E402
from features.guest.events import MEAL_EVENTS_KEY, emit_mock_meal_logged  # noqa: E402
from features.guest.logic import MENU_MAX_LEN, now_kst, today_kst  # noqa: E402
from features.guest.storage import clear_all, get_visits, has_visit  # noqa: E402

st.set_page_config(page_title="밥때 손님 (단독 실행)", page_icon="🐾", layout="centered")

SLOT_ICONS = {"breakfast": "🌅", "lunch": "☀️", "dinner": "🌙"}


def _logged(day: str, slot: str) -> bool:
    """이미 손님이 왔거나, 방금 눌러서 처리 대기 중인 끼니"""
    pending = st.session_state.get(MEAL_EVENTS_KEY, [])
    return has_visit(day, slot) or any(e["date"] == day and e["slot"] == slot for e in pending)


def _slot_now() -> str:
    hour = now_kst().hour
    return "breakfast" if hour < 11 else "lunch" if hour < 16 else "dinner"


def _logged_menu(day: str, slot: str) -> str | None:
    pending = st.session_state.get(MEAL_EVENTS_KEY, [])
    for e in pending:
        if e["date"] == day and e["slot"] == slot:
            return e.get("menu")
    return next((v.menu for v in get_visits() if v.date == day and v.slot == slot), None)


def _log_meal(day: str, slot: str, photo: bytes | None, menu_key: str) -> None:
    emit_mock_meal_logged({
        "meal_log_id": f"mock-{uuid.uuid4().hex}", "slot": slot, "date": day, "photo": photo,
        "menu": st.session_state.get(menu_key),
    })
    st.session_state["guest_dev_upload_n"] = st.session_state.get("guest_dev_upload_n", 0) + 1  # 사진·메뉴 칸 비우기
    nxt = next((s for s in SLOTS if s != slot and not _logged(day, s)), None)
    if nxt:
        st.session_state["guest_dev_slot"] = nxt  # 다음 끼니로 넘겨 두기


# 개발용 기록 영역을 작은 다이어리 메모지처럼 꾸민다. 이 컨테이너(st-key-guest_dev_logger) 안에만 적용된다.
# dev.py 전용이라 병합 앱에는 들어가지 않는다.
LOGGER_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Jua&family=Poor+Story&family=Gowun+Dodum&display=swap');
.st-key-guest_dev_logger {
  position:relative; margin-top:14px; padding:18px 14px 10px 44px; border-radius:4px 16px 16px 4px; gap:.45rem;
  background-color:#fffaf0;
  background-image:linear-gradient(90deg, transparent 30px, rgba(242,155,184,.55) 30px 32px, transparent 32px);
  box-shadow:0 1px 0 #efe3d5, 0 8px 18px rgba(40,20,40,.18); color:#4a3640;
  font-family:'Gowun Dodum', 'Malgun Gothic', sans-serif;
}
.st-key-guest_dev_logger::before {  /* 스프링 구멍 */
  content:""; position:absolute; left:9px; top:12px; bottom:12px; width:12px;
  background:radial-gradient(circle, #ddd2da 0 4px, transparent 5px) 0 0 / 12px 26px repeat-y;
}
.st-key-guest_dev_logger::after {  /* 마스킹 테이프 */
  content:""; position:absolute; top:-10px; left:50%; width:96px; height:20px; transform:translateX(-50%) rotate(-2deg);
  background:repeating-linear-gradient(45deg, rgba(255,214,140,.9) 0 7px, rgba(255,232,186,.9) 7px 14px);
  box-shadow:0 1px 3px rgba(0,0,0,.15);
}
.st-key-guest_dev_logger .guest-log-title { font-family:'Jua', 'Gowun Dodum', sans-serif; font-weight:400; font-size:20px; line-height:1.2; color:#3d2b38; }
.st-key-guest_dev_logger .guest-log-title small { font-family:'Gowun Dodum', sans-serif; font-weight:400; font-size:12px; color:#9a8494; margin-left:6px; }
.st-key-guest_dev_logger .guest-log-done { font-family:'Poor Story', 'Gowun Dodum', cursive; font-size:16px; color:#8a6a7c; padding:2px 0 4px; }
.st-key-guest_dev_logger button[data-variant="segmented_control"] {
  background:#fff; color:#5a4250; border:1.5px solid #e9d6e0; font-family:'Jua', 'Gowun Dodum', sans-serif; font-size:15px; min-height:40px;
}
.st-key-guest_dev_logger button[data-variant="segmented_control"][aria-checked="true"] { background:#ffd9e6; border-color:#f29bb8; color:#c23d6a; }
.st-key-guest_dev_logger [data-testid="stTextInputRootElement"], .st-key-guest_dev_logger [data-testid="stDateInputField"] {
  background:#fff; border:1.5px solid #e9d6e0; border-radius:12px;
}
.st-key-guest_dev_logger [data-testid="stDateInputField"] * { color:#4a3640; }
.st-key-guest_dev_logger input { color:#4a3640; -webkit-text-fill-color:#4a3640; font-family:'Gowun Dodum', sans-serif; }
.st-key-guest_dev_logger input::placeholder { color:#b8a2ae; -webkit-text-fill-color:#b8a2ae; }
.st-key-guest_dev_logger button[kind="secondary"] { background:#fff; color:#5a4250; border:1.5px solid #e9d6e0; border-radius:12px; min-height:40px; }
.st-key-guest_dev_logger button[kind="primary"] {
  background:linear-gradient(180deg, #f7a8c3, #e9799f); border:none; color:#fff; border-radius:12px; min-height:40px;
  font-family:'Jua', 'Gowun Dodum', sans-serif; font-weight:400; font-size:16px; box-shadow:0 3px 0 #d0628a;
}
</style>
"""

with st.container(key="guest_dev_logger"):
    st.html(LOGGER_CSS + '<div class="guest-log-title">🍚 오늘 뭐 먹었어?<small>개발용 기록</small></div>')
    st.session_state.setdefault("guest_dev_slot", _slot_now())  # 처음엔 지금 시간의 끼니
    # 가로 컨테이너는 st.columns와 달리 좁은 화면에서도 세로로 다 쌓이지 않고, 자리가 모자랄 때만 줄을 바꾼다.
    top = st.container(horizontal=True, vertical_alignment="center", gap="small")
    slot_box, day_box = top.container(width="content"), top.container(width=150)
    day = day_box.date_input(
        "끼니 날짜", value=today_kst(), key="guest_dev_date", label_visibility="collapsed", format="YYYY.MM.DD"
    ).isoformat()
    slot = slot_box.segmented_control(
        "어떤 끼니인가요?",
        SLOTS,
        format_func=lambda s: f"{SLOT_ICONS[s]} {SLOT_LABELS[s]}" + (" ✓" if _logged(day, s) else ""),
        required=True,
        key="guest_dev_slot",
        label_visibility="collapsed",
    )
    if _logged(day, slot):
        menu = _logged_menu(day, slot)
        eaten = f" — 🍴 {html.escape(menu)}" if menu else ""
        st.html(f'<div class="guest-log-done">✓ {SLOT_LABELS[slot]}은 기록했어요{eaten} · 손님은 끼니마다 한 번만 와요</div>')
    else:
        n = st.session_state.get("guest_dev_upload_n", 0)
        menu_key = f"guest_dev_menu_{n}"
        row = st.container(horizontal=True, vertical_alignment="bottom", gap="small")
        row.text_input(
            "먹은 메뉴",
            key=menu_key,
            max_chars=MENU_MAX_LEN,
            placeholder=f"{SLOT_LABELS[slot]} 메뉴 (예: 김치찌개)",
            label_visibility="collapsed",
            width="stretch",
        )
        photo_key = f"guest_dev_photo_{n}"
        has_photo = st.session_state.get(photo_key) is not None
        with row.popover("📷 ✓" if has_photo else "📷", help="밥상 사진 올리기 (선택)"):
            upload = st.file_uploader(
                "밥상 사진 (선택) · 휴대폰에서는 바로 찍을 수도 있어요", type=["jpg", "jpeg", "png", "webp"], key=photo_key
            )
            photo = upload.getvalue() if upload else None
            if photo:
                st.image(photo, width=180, caption="이 사진으로 기록해요")
        row.button(
            "기록하기",
            key="guest_dev_log",
            type="primary",
            on_click=_log_meal,
            args=(day, slot, photo, menu_key),
        )

page()

with st.expander("🧪 개발 도구"):
    st.code(f"get_today_summary()\n{get_today_summary()}", language=None)
    if st.button("손님 기록 모두 지우기", key="guest_dev_reset"):
        clear_all()
        st.session_state[MEAL_EVENTS_KEY] = []
        st.rerun()
