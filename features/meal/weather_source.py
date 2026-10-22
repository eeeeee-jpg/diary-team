"""날씨 읽기 어댑터. 병합 시 이 파일의 `get_weather`만 팀원 E의 것으로 바꾼다.

반환: {"temp", "feels_like", "precip", "min", "max", "hourly"} 또는 실패 시 None.
임시로 Open-Meteo(키 불필요)를 직접 호출한다. 개발 중에는 목 시나리오로 바꿔 볼 수 있다.
"""

from typing import Any

import requests
import streamlit as st

MOCK_SCENARIO_KEY = "meal_mock_weather"
REAL_WEATHER = "실제 날씨"

MOCK_SCENARIOS: dict[str, dict[str, Any] | None] = {
    "맑음": {"temp": 20, "feels_like": 20, "precip": 0, "min": 14, "max": 24, "hourly": []},
    "비": {"temp": 16, "feels_like": 15, "precip": 4.0, "min": 13, "max": 18, "hourly": []},
    "눈": {"temp": -1, "feels_like": -5, "precip": 2.0, "min": -4, "max": 1, "hourly": []},
    "한파": {"temp": -8, "feels_like": -14, "precip": 0, "min": -11, "max": -3, "hourly": []},
    "폭염": {"temp": 35, "feels_like": 38, "precip": 0, "min": 27, "max": 36, "hourly": []},
    "날씨 실패": None,
}

_URL = "https://api.open-meteo.com/v1/forecast"


@st.cache_data(ttl=600, show_spinner=False)
def meal_fetch_open_meteo(lat: float, lng: float) -> dict[str, Any]:
    """Open-Meteo 현재 날씨. 실패하면 예외를 던진다(캐시되지 않음)."""
    res = requests.get(
        _URL,
        params={
            "latitude": lat,
            "longitude": lng,
            "current": "temperature_2m,apparent_temperature,precipitation",
            "hourly": "temperature_2m,precipitation",
            "daily": "temperature_2m_max,temperature_2m_min",
            "timezone": "Asia/Seoul",
            "forecast_days": 1,
        },
        timeout=5,
    )
    res.raise_for_status()
    data = res.json()
    cur, daily, hourly = data["current"], data["daily"], data["hourly"]
    return {
        "temp": cur["temperature_2m"],
        "feels_like": cur["apparent_temperature"],
        "precip": cur["precipitation"],
        "min": daily["temperature_2m_min"][0],
        "max": daily["temperature_2m_max"][0],
        "hourly": [
            {"time": t, "temp": temp, "precip": p}
            for t, temp, p in zip(hourly["time"], hourly["temperature_2m"], hourly["precipitation"])
        ],
    }


def get_weather(lat: float, lng: float) -> dict[str, Any] | None:
    scenario = st.session_state.get(MOCK_SCENARIO_KEY, REAL_WEATHER)
    if scenario != REAL_WEATHER:
        return MOCK_SCENARIOS.get(scenario)
    try:
        return meal_fetch_open_meteo(lat, lng)
    except (requests.RequestException, KeyError, ValueError, IndexError):
        return None
