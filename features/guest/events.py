"""한 끼 서비스(팀원 A)와의 연결 지점.

한 끼가 끼니를 기록하면 st.session_state[MEAL_EVENTS_KEY] 목록에 이벤트를 넣고,
손님은 페이지나 홈 요약이 실행될 때 이 목록을 읽어 처리한다.
키 이름과 형태는 팀원 A와 확정해야 한다. 바뀌면 이 파일만 고친다.
"""

from __future__ import annotations

import streamlit as st

from .models import MealLoggedEvent

MEAL_EVENTS_KEY = "meal_logged_events"


def pending_meal_events() -> list[MealLoggedEvent]:
    return list(st.session_state.get(MEAL_EVENTS_KEY, []))


def emit_mock_meal_logged(event: MealLoggedEvent) -> None:
    """개발용 테스트 버튼에서 쓰는 목 발행"""
    st.session_state.setdefault(MEAL_EVENTS_KEY, []).append(event)
