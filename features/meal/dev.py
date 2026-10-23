"""단독 실행: streamlit run features/meal/dev.py (목 날씨 사용)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

st.set_page_config(page_title="오늘의 한 끼 (dev)", page_icon="🍚", layout="centered")

from features.meal import page  # noqa: E402
from features.meal.weather_source import MOCK_SCENARIO_KEY, MOCK_SCENARIOS, REAL_WEATHER  # noqa: E402

with st.sidebar:
    st.caption("개발용 날씨 (실제 날씨 = Open-Meteo)")
    st.selectbox("날씨 시나리오", [REAL_WEATHER, *MOCK_SCENARIOS], key=MOCK_SCENARIO_KEY)

page()
