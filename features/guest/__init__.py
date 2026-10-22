"""밥때 손님 (팀원 C). 병합 단위: page(), ROUTE, get_today_summary()만 내보낸다."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import TodaySummary

__all__ = ["page", "ROUTE", "get_today_summary"]

ROUTE = "guest"


# Streamlit은 함수 안에서 불러와, 순수 로직(logic.py) 테스트가 Streamlit 없이 돌게 한다.
def page() -> None:
    from .ui import render

    render()


def get_today_summary() -> "TodaySummary":
    from .service import get_today_summary as summary

    return summary()
