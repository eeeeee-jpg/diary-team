"""MOIPJI — 오늘 날씨에, 모입지?

OpenWeatherMap 날씨와 사용자가 고른 스타일을 조합해 오늘의 옷차림을 추천한다.
단독 실행: streamlit run features/weather/weather.py

규칙(체감온도 구간, 시간대, 문구, 기준값)은 data/rules.json,
코디·아이템·이미지 경로는 data/outfits.json, 지역 목록은 data/cities.json에서 관리한다.
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

API_BASE = "https://api.openweathermap.org/data/2.5"
API_KEY_NAMES = ("OPENWEATHER_API_KEY", "WEATHER_KEY")  # WEATHER_KEY는 팀 공통 규칙의 이름
TIMEOUT_SECONDS = 5
CACHE_TTL_SECONDS = 600

DEFAULT_CITY = "서울"
DEFAULT_STYLE = "simple"
NO_OUTER_LABEL = "아우터 없이도 좋아요"
NO_OUTER_REASON = "이 기온엔 겉옷 없이 다녀도 충분해요."

load_dotenv(BASE_DIR / ".env")


class WeatherError(Exception):
    """사용자에게 그대로 보여줄 수 있는 날씨 조회 오류. 키나 요청 URL을 메시지에 넣지 않는다."""


# ---------------------------------------------------------------------------
# 데이터 구조
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Snapshot:
    """한 시점의 날씨. 현재 관측 또는 3시간 예보 한 칸."""

    time: datetime  # 선택 지역 현지 시각
    temp: float
    feels_like: float
    humidity: float | None
    wind_speed: float | None
    pop: float | None  # 강수확률 0~1. 현재 관측에는 가장 가까운 예보 값을 채운다
    description: str
    icon: str | None
    condition_id: int | None
    is_current: bool


@dataclass(frozen=True)
class WeatherData:
    current: Snapshot
    forecast: list[Snapshot]
    tz: tzinfo
    fetched_at: datetime  # OpenWeather에서 실제로 불러온 시각 (캐시 10분 동안 그대로)
    forecast_error: str | None = None


@dataclass(frozen=True)
class Sky:
    """화면에 보여줄 날씨 상태. OpenWeather 코드 → 한글 이름과 Material 아이콘."""

    label: str
    icon: str


@dataclass(frozen=True)
class Item:
    item_id: str
    category: str
    name: str
    reason: str
    image_path: str


@dataclass(frozen=True)
class Outfit:
    outfit_id: str
    style: str
    temperature_code: str
    top: Item
    bottom: Item
    outer: Item | None
    accessories: list[str]
    description: str
    image_path: str


@dataclass(frozen=True)
class Condition:
    id: str
    headline: str
    tip: str


@dataclass(frozen=True)
class Recommendation:
    outfit: Outfit
    temperature_range: dict[str, Any]
    headline: str
    conditions: list[Condition]  # 우선순위 순서. 첫 번째가 핵심 안내


# ---------------------------------------------------------------------------
# 데이터 파일
# ---------------------------------------------------------------------------


def load_json(name: str) -> Any:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def load_outfits(catalog: dict[str, Any]) -> list[Outfit]:
    items = catalog["items"]

    def to_item(ref: dict[str, str] | None) -> Item | None:
        if ref is None:
            return None
        info = items[ref["item_id"]]
        return Item(
            item_id=ref["item_id"],
            category=info["category"],
            name=info["name"],
            reason=ref["reason"],
            image_path=info["image_path"],
        )

    return [
        Outfit(
            outfit_id=o["outfit_id"],
            style=o["style"],
            temperature_code=o["temperature_code"],
            top=to_item(o["top"]),
            bottom=to_item(o["bottom"]),
            outer=to_item(o["outer"]),
            accessories=list(o.get("accessories", [])),
            description=o["description"],
            image_path=o["image_path"],
        )
        for o in catalog["outfits"]
    ]


def image_file(path: str | None) -> Path | None:
    """이미지 파일이 실제로 있을 때만 경로를 돌려준다. 없으면 None (플레이스홀더 표시)."""
    if not path:
        return None
    full = BASE_DIR / path
    return full if full.is_file() else None


# ---------------------------------------------------------------------------
# 날씨 조회
# ---------------------------------------------------------------------------


def _api_key() -> str | None:
    for name in API_KEY_NAMES:
        try:
            value = st.secrets.get(name)
        except Exception:  # secrets.toml이 없으면 예외가 난다
            value = None
        value = value or os.environ.get(name)
        if value:
            return str(value)
    return None


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def weather_fetch(endpoint: str, lat: float, lon: float) -> dict[str, Any]:
    """OpenWeatherMap 호출. 성공한 응답만 10분 캐시된다(예외는 캐시되지 않음)."""
    key = _api_key()
    if not key:
        raise WeatherError("날씨 API 키가 설정되지 않았어요. .env의 OPENWEATHER_API_KEY를 확인해 주세요.")
    try:
        res = requests.get(
            f"{API_BASE}/{endpoint}",
            params={"lat": lat, "lon": lon, "appid": key, "units": "metric", "lang": "kr"},
            timeout=TIMEOUT_SECONDS,
        )
    except requests.Timeout:
        raise WeatherError("날씨 서버가 응답하지 않아요. 잠시 후 다시 시도해 주세요.") from None
    except requests.RequestException:
        raise WeatherError("날씨 서버에 연결하지 못했어요. 인터넷 연결을 확인해 주세요.") from None

    if res.status_code == 401:
        raise WeatherError("날씨 API 키가 올바르지 않거나 아직 활성화되지 않았어요.")
    if res.status_code == 429:
        raise WeatherError("날씨 조회 요청이 많아요. 잠시 후 다시 시도해 주세요.")
    if not res.ok:
        raise WeatherError(f"날씨를 불러오지 못했어요. (오류 {res.status_code})")
    try:
        body = res.json()
    except ValueError:
        raise WeatherError("날씨 응답을 읽지 못했어요.") from None
    if isinstance(body, dict):
        body["_fetched_at"] = time.time()  # 캐시된 응답이 언제 받아온 것인지 화면에 보여주기 위함
    return body


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def parse_snapshot(raw: dict[str, Any], tz: tzinfo, is_current: bool) -> Snapshot | None:
    """필수 값(시각·기온·체감온도)이 없으면 None. 임의 값으로 채우지 않는다."""
    main = raw.get("main") or {}
    dt = _num(raw.get("dt"))
    temp = _num(main.get("temp"))
    feels_like = _num(main.get("feels_like"))
    if dt is None or temp is None or feels_like is None:
        return None
    weather = (raw.get("weather") or [{}])[0] or {}
    condition_id = _num(weather.get("id"))
    return Snapshot(
        time=datetime.fromtimestamp(dt, tz),
        temp=temp,
        feels_like=feels_like,
        humidity=_num(main.get("humidity")),
        wind_speed=_num((raw.get("wind") or {}).get("speed")),
        pop=_num(raw.get("pop")),
        description=str(weather.get("description") or ""),
        icon=weather.get("icon"),
        condition_id=int(condition_id) if condition_id is not None else None,
        is_current=is_current,
    )


def parse_weather(
    current_raw: dict[str, Any],
    forecast_raw: dict[str, Any] | None,
    forecast_error: str | None = None,
) -> WeatherData:
    offset = (forecast_raw or {}).get("city", {}).get("timezone", current_raw.get("timezone", 0))
    tz = timezone(timedelta(seconds=int(offset or 0)))

    current = parse_snapshot(current_raw, tz, is_current=True)
    if current is None:
        raise WeatherError("현재 날씨 데이터가 비어 있어요. 잠시 후 다시 시도해 주세요.")

    forecast = [
        s
        for s in (parse_snapshot(item, tz, is_current=False) for item in (forecast_raw or {}).get("list", []))
        if s is not None
    ]
    forecast.sort(key=lambda s: s.time)

    # 현재 관측에는 강수확률이 없으므로 3시간 이내의 가장 가까운 예보 값을 쓴다
    nearby = [s for s in forecast if abs(s.time - current.time) <= timedelta(hours=3) and s.pop is not None]
    if nearby:
        nearest = min(nearby, key=lambda s: abs(s.time - current.time))
        current = replace(current, pop=nearest.pop)

    fetched = _num(current_raw.get("_fetched_at"))
    fetched_at = datetime.fromtimestamp(fetched, tz) if fetched is not None else current.time
    return WeatherData(
        current=current, forecast=forecast, tz=tz, fetched_at=fetched_at, forecast_error=forecast_error
    )


def load_weather(lat: float, lon: float) -> WeatherData:
    """현재 날씨는 필수, 예보는 실패해도 현재 날씨만으로 화면을 그린다."""
    current_raw = weather_fetch("weather", lat, lon)
    try:
        forecast_raw = weather_fetch("forecast", lat, lon)
        forecast_error = None
    except WeatherError as e:
        forecast_raw, forecast_error = None, str(e)
    return parse_weather(current_raw, forecast_raw, forecast_error)


# ---------------------------------------------------------------------------
# 데이터 가공: 시간대·일교차
# ---------------------------------------------------------------------------


def current_slot_id(now: datetime, slots: list[dict[str, Any]]) -> str:
    return slot_for_hour(now.hour, slots)["id"]


def slot_for_hour(hour: int, slots: list[dict[str, Any]]) -> dict[str, Any]:
    """시각이 속한 시간대(오전·오후·저녁). 문구와 질문을 고를 때 쓴다."""
    for slot in slots:
        if hour < slot["until_hour"]:
            return slot
    return slots[-1]


@dataclass(frozen=True)
class HourCell:
    """시간별 날씨 한 칸. 무료 예보가 3시간 간격이라 하루 8칸(0·3·…·21시)."""

    time: datetime
    snapshot: Snapshot | None  # 데이터가 없으면 None
    is_now: bool
    is_past: bool


def day_timeline(
    data: WeatherData, now: datetime, day_offset: int = 0, step_hours: int = 3, max_minutes: int = 90
) -> list[HourCell]:
    """그날 0시부터 하루 끝까지. 지금 칸은 현재 관측, 지난 칸은 데이터 없음(무료 API는 과거를 주지 않음)."""
    day = (now + timedelta(days=day_offset)).date()
    start = datetime(day.year, day.month, day.day, tzinfo=now.tzinfo)
    step = timedelta(hours=step_hours)
    cells = []
    for k in range(24 // step_hours):
        t = start + step * k
        is_now = day_offset == 0 and t <= now < t + step
        is_past = day_offset == 0 and t + step <= now
        snapshot = None
        if is_now:
            snapshot = data.current
        elif not is_past and data.forecast:
            nearest = min(data.forecast, key=lambda s: abs(s.time - t))
            if abs(nearest.time - t) <= timedelta(minutes=max_minutes):
                snapshot = nearest
        cells.append(HourCell(time=t, snapshot=snapshot, is_now=is_now, is_past=is_past))
    return cells


def default_cell_index(cells: list[HourCell]) -> int:
    """처음 선택할 칸: 오늘은 지금, 내일은 오전 8시 이후 첫 칸."""
    for i, cell in enumerate(cells):
        if cell.is_now:
            return i
    for i, cell in enumerate(cells):
        if cell.time.hour >= 8 and cell.snapshot is not None:
            return i
    return 0


def day_extremes(data: WeatherData, now: datetime, day_offset: int = 0) -> tuple[float, float] | None:
    """그날(현지 날짜)의 최저·최고 기온. 오늘은 현재 기온도 포함. 데이터가 없으면 None."""
    day = (now + timedelta(days=day_offset)).date()
    temps = [s.temp for s in data.forecast if s.time.date() == day]
    if day_offset == 0:
        temps.append(data.current.temp)
    return (min(temps), max(temps)) if temps else None


def daily_range(data: WeatherData, now: datetime, min_points: int, day_offset: int = 0) -> float | None:
    """그날 예보의 최고-최저. 예보가 min_points개보다 적으면 None (일교차 안내 생략)."""
    day = (now + timedelta(days=day_offset)).date()
    if sum(1 for s in data.forecast if s.time.date() == day) < min_points:
        return None
    low, high = day_extremes(data, now, day_offset)
    return high - low


def sky_of(snapshot: Snapshot, sky_rules: list[dict[str, Any]]) -> Sky:
    """날씨 상태 코드를 한글 이름과 아이콘으로. 밤에는 맑음·구름 아이콘을 밤용으로 바꾼다."""
    night = bool(snapshot.icon and snapshot.icon.endswith("n"))
    if snapshot.condition_id is not None:
        for rule in sky_rules:
            if rule["min"] <= snapshot.condition_id <= rule["max"]:
                icon = rule.get("icon_night", rule["icon"]) if night else rule["icon"]
                return Sky(label=rule["label"], icon=icon)
    return Sky(label=snapshot.description or "날씨 정보 없음", icon="thermostat")


# ---------------------------------------------------------------------------
# 코디 추천·문구 선택
# ---------------------------------------------------------------------------


def round_half_up(value: float) -> int:
    """사사오입. 화면 표시와 구간 판정에 같은 규칙을 써서 '16°C인데 17~22°C 구간' 같은 모순을 막는다.
    (파이썬 round()와 f"{x:.0f}"는 16.5 → 16으로 짝수 쪽 반올림을 한다)"""
    return math.floor(value + 0.5)


def find_temperature_range(feels_like: float, ranges: list[dict[str, Any]]) -> dict[str, Any]:
    """체감온도를 정수로 반올림해 구간을 찾는다. 구간 하한이 연속이라 경계에서 빠지는 값이 없다.
    (예: 5.4°C → 5 → '5°C 이하', 5.5°C → 6 → '6~11°C')"""
    rounded = round_half_up(feels_like)
    for r in ranges:
        if r["min"] is None or rounded >= r["min"]:
            return r
    return ranges[-1]


def find_outfit(outfits: list[Outfit], style: str, temperature_code: str) -> Outfit:
    for outfit in outfits:
        if outfit.style == style and outfit.temperature_code == temperature_code:
            return outfit
    raise KeyError(f"outfit not found: {style} {temperature_code}")


def detect_conditions(
    snapshot: Snapshot, day_range: float | None, rules: dict[str, Any]
) -> list[Condition]:
    th = rules["thresholds"]
    values: dict[str, str | None] = {
        "rain": f"{round(snapshot.pop * 100)}" if snapshot.pop is not None and snapshot.pop >= th["rain_pop"] else None,
        "daily_range": f"{round_half_up(day_range)}" if day_range is not None and day_range >= th["daily_range"] else None,
        "wind": f"{snapshot.wind_speed:.1f}"
        if snapshot.wind_speed is not None and snapshot.wind_speed >= th["wind_speed"]
        else None,
    }
    return [
        Condition(id=c["id"], headline=c["headline"], tip=c["tip"].format(value=values[c["id"]]))
        for c in rules["conditions"]  # rules.json 순서 = 우선순위
        if values.get(c["id"]) is not None
    ]


def recommend(
    snapshot: Snapshot,
    slot_id: str,
    style: str,
    day_range: float | None,
    rules: dict[str, Any],
    outfits: list[Outfit],
    day_label: str = "오늘",
) -> Recommendation:
    temperature_range = find_temperature_range(snapshot.feels_like, rules["temperature_ranges"])
    return Recommendation(
        outfit=find_outfit(outfits, style, temperature_range["code"]),
        temperature_range=temperature_range,
        headline=headline_for(rules, temperature_range["code"], slot_id, day_label),
        conditions=detect_conditions(snapshot, day_range, rules),
    )


def headline_for(rules: dict[str, Any], temperature_code: str, slot_id: str, day_label: str) -> str:
    """문구의 {day}를 '오늘'/'내일'로 바꾼다. 내일 탭에서 '오늘은 ~'이 나오지 않게 하기 위함."""
    return rules["messages"][temperature_code][slot_id].replace("{day}", day_label)


# ---------------------------------------------------------------------------
# 다른 서비스용 (홈·오늘의 한 끼)
# ---------------------------------------------------------------------------


def _precip_type(condition_id: int | None) -> str:
    # 2xx 뇌우, 3xx 이슬비, 5xx 비, 6xx 눈 — https://openweathermap.org/weather-conditions
    if condition_id is None:
        return "none"
    group = condition_id // 100
    if group == 6:
        return "snow"
    if group in (2, 3, 5):
        return "rain"
    return "none"


def get_weather(lat: float, lng: float) -> dict[str, Any]:
    """팀 공통 날씨 함수. 반환 형태를 바꿀 때는 팀원 A와 먼저 합의한다.
    실패하면 WeatherError를 던진다(호출하는 쪽에서 카드 단위 폴백)."""
    data = load_weather(round(lat, 2), round(lng, 2))
    now = datetime.now(data.tz)
    today = [s for s in data.forecast if s.time.date() == now.date()]
    temps = [data.current.temp, *(s.temp for s in today)]
    pops = [s.pop for s in today if s.pop is not None]
    return {
        "temp": data.current.temp,
        "feels_like": data.current.feels_like,
        "precip": {
            "type": _precip_type(data.current.condition_id),
            "probability": max(pops) if pops else None,
        },
        "min": min(temps),
        "max": max(temps),
        "hourly": [
            {"time": s.time.isoformat(), "temp": s.temp, "feels_like": s.feels_like, "pop": s.pop}
            for s in data.forecast[:8]  # 3시간 간격 × 8 = 24시간
        ],
    }


def get_today_summary() -> dict[str, str]:
    """홈 카드용 한 줄 요약."""
    cities = {c["name"]: c for c in load_json("cities.json")}
    city = cities.get(st.session_state.get("weather_city", DEFAULT_CITY), cities[DEFAULT_CITY])
    try:
        data = load_weather(city["lat"], city["lon"])
    except WeatherError:
        return {"title": "MOIPJI", "value": "날씨를 불러오지 못했어요", "status": "error"}
    rules = load_json("rules.json")
    temperature_range = find_temperature_range(data.current.feels_like, rules["temperature_ranges"])
    slot_id = current_slot_id(datetime.now(data.tz), rules["time_slots"])
    message = headline_for(rules, temperature_range["code"], slot_id, "오늘")
    return {"title": "MOIPJI", "value": f"{round_half_up(data.current.temp)}°C · {message}", "status": "ok"}


# ---------------------------------------------------------------------------
# 화면 — 디자인 시스템 "Atmospheric Glass"
# ---------------------------------------------------------------------------

KST = timezone(timedelta(hours=9))
WEEKDAYS = ("월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일")

# 날씨 상태별 배경 그라데이션과 글자색 (디자인 시스템 2.1)
# shadow: 흰 글자가 밝은 그라데이션 끝(민트 등)에서 대비가 낮아 옅은 글자 그림자로 보완한다
THEMES = {
    "clear_day": {"start": "#4A90E2", "end": "#50E3C2", "text": "#FFFFFF", "shadow": "0 1px 2px rgba(0, 0, 0, 0.28)"},
    "clear_night": {"start": "#1F1C2C", "end": "#928DAB", "text": "#FFFFFF", "shadow": "0 1px 2px rgba(0, 0, 0, 0.28)"},
    "cloudy": {"start": "#4CA1AF", "end": "#C4E0E5", "text": "#2C3E50", "shadow": "none"},
}
DEFAULT_THEME = "clear_day"

# 모든 선택자는 MOIPJI 페이지(.st-key-weather_root)가 있을 때만 적용된다. 병합 후 다른 페이지에 새지 않게 하기 위함.
PAGE_CSS = """
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css');

.stApp:has(.st-key-weather_root) {
  --mj-glass: rgba(255, 255, 255, 0.2);
  --mj-glass-strong: rgba(255, 255, 255, 0.42);
  --mj-glass-border: rgba(255, 255, 255, 0.4);
  --mj-blur: blur(20px);
  --mj-radius: 24px;
  --mj-pad: 24px;
  --mj-unit: 8px;
  background: linear-gradient(165deg, var(--mj-start) 0%, var(--mj-end) 100%) fixed;
}
.stApp:has(.st-key-weather_root) [data-testid="stHeader"] {
  background: transparent;
}

/* 로딩: 스켈레톤 없이 배경만 물결치듯 은은하게 (디자인 시스템 4) */
.stApp:has(.st-key-weather_root)::before {
  content: "";
  position: fixed;
  inset: -20%;
  pointer-events: none;
  background: radial-gradient(circle at 30% 30%, rgba(255, 255, 255, 0.22), transparent 55%);
  opacity: 0;
  z-index: 0;
}
.stApp[data-test-script-state="running"]:has(.st-key-weather_root)::before {
  animation: mj-pulse 2.4s ease-in-out infinite;
}
@keyframes mj-pulse {
  0%, 100% { opacity: 0; transform: translate(0, 0); }
  50% { opacity: 1; transform: translate(6%, 4%); }
}
@media (prefers-reduced-motion: reduce) {
  .stApp[data-test-script-state="running"]:has(.st-key-weather_root)::before {
    animation: none;
    opacity: 0.6;
  }
}

/* 글자: Pretendard, 상태별 글자색 */
.st-key-weather_root {
  color: var(--mj-text);
  text-shadow: var(--mj-shadow);
}
.st-key-weather_root :where(p, li, label, h1, h2, h3, button, input, [data-baseweb="select"] div) {
  font-family: 'Pretendard Variable', Pretendard, -apple-system, BlinkMacSystemFont, sans-serif;
  color: var(--mj-text);
}
.st-key-weather_root p,
.st-key-weather_root li {
  font-size: 16px;
}
.st-key-weather_root [data-testid="stCaptionContainer"],
.st-key-weather_root [data-testid="stCaptionContainer"] p {
  opacity: 1;
  font-size: 12px;
  font-weight: 300;
  color: var(--mj-text);
}
.st-key-weather_root [data-testid="stWidgetLabel"] p {
  font-size: 12px;
  font-weight: 300;
}
.st-key-weather_root span[role="img"] {
  color: var(--mj-text);
}

/* 유리 카드: 그림자 없이 테두리로만 구분 (디자인 시스템 3.1) */
.st-key-weather_card,
.st-key-weather_hero,
.st-key-weather_tips,
.st-key-weather_notice,
.st-key-weather_error,
.st-key-weather_look_placeholder,
[class*="st-key-weather_item_"],
.st-key-weather_root [data-testid="stExpander"] details {
  background: var(--mj-glass);
  border: 1px solid var(--mj-glass-border);
  border-radius: var(--mj-radius);
  -webkit-backdrop-filter: var(--mj-blur);
  backdrop-filter: var(--mj-blur);
  box-shadow: none;
}
.st-key-weather_card,
.st-key-weather_hero,
.st-key-weather_tips,
.st-key-weather_notice,
.st-key-weather_error,
[class*="st-key-weather_item_"] {
  padding: var(--mj-pad);
}
[class*="st-key-weather_item_"] {
  gap: calc(var(--mj-unit) / 2);
}

/* 입력 요소도 유리처럼 */
.st-key-weather_root [data-baseweb="select"] > div,
.st-key-weather_root [data-testid="stButtonGroup"] button,
.st-key-weather_root button[data-testid^="stBaseButton"] {
  background: var(--mj-glass);
  border: 1px solid var(--mj-glass-border);
  -webkit-backdrop-filter: var(--mj-blur);
  backdrop-filter: var(--mj-blur);
  color: var(--mj-text);
}
.st-key-weather_root [data-baseweb="select"] > div {
  border-radius: 16px;
}
.st-key-weather_root [data-testid="stButtonGroup"] button[aria-checked="true"] {
  background: var(--mj-glass-strong);
  border-color: rgba(255, 255, 255, 0.9);
}
.st-key-weather_root [data-testid="stButtonGroup"] button[aria-checked="true"] p {
  font-weight: 600;
}
.st-key-weather_root :focus-visible {
  outline: 2px solid var(--mj-text);
  outline-offset: 2px;
}

/* 머리글 */
.st-key-weather_brand p {
  font-size: 24px;
  font-weight: 700;
  margin: 0;
}

/* 메인 날씨 카드 */
.st-key-weather_card_top p {
  font-weight: 600;
  margin: 0;
}
.st-key-weather_card_icon span[role="img"] {
  font-size: 56px;
}
.st-key-weather_temp p {
  font-size: 72px;
  font-weight: 700;
  letter-spacing: -0.05em;
  line-height: 1;
  margin: 0;
  font-variant-numeric: tabular-nums;
}
.st-key-weather_card_sky p {
  font-size: 24px;
  font-weight: 600;
  margin: 0;
  text-align: center;
}
.st-key-weather_card_range p {
  margin: 0;
  font-variant-numeric: tabular-nums;
}

/* 시간별 예보: 가로 스크롤, 같은 너비 (디자인 시스템 3.2) */
[class*="st-key-weather_hour_"] [role="radiogroup"],
[class*="st-key-weather_hour_"] [data-testid="stButtonGroup"] > div:last-child {
  flex-wrap: nowrap;
  overflow-x: auto;
  scrollbar-width: thin;
  padding-bottom: var(--mj-unit);
}
[class*="st-key-weather_hour_"] button {
  flex: 0 0 76px;
  width: 76px;
  min-height: 104px;
  border-radius: 20px;
  padding: var(--mj-unit) 0;
}
[class*="st-key-weather_hour_"] button p {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-variant-numeric: tabular-nums;
}
[class*="st-key-weather_hour_"] button span[role="img"] {
  font-size: 26px;
}

/* 한 줄 추천 */
.st-key-weather_headline p {
  font-size: 24px;
  font-weight: 600;
  line-height: 1.35;
  margin: 0;
  word-break: keep-all;
}
.st-key-weather_alert p {
  font-weight: 600;
  margin: 0;
}
.st-key-weather_look_style p {
  font-weight: 600;
  margin: 0;
}

/* 완성 룩 자리: 3:4 */
.st-key-weather_look_placeholder {
  aspect-ratio: 3 / 4;
  justify-content: center;
  align-items: center;
}
.st-key-weather_look_placeholder [data-testid="stCaptionContainer"] p {
  text-align: center;
}

/* 오류: 흐린 유리창에 빗방울 (디자인 시스템 4) */
.st-key-weather_error {
  min-height: 320px;
  justify-content: center;
  align-items: center;
  text-align: center;
  background-color: rgba(255, 255, 255, 0.18);
  background-image:
    radial-gradient(circle at 12% 18%, rgba(255, 255, 255, 0.55) 0 3px, transparent 4px),
    radial-gradient(circle at 78% 26%, rgba(255, 255, 255, 0.45) 0 5px, transparent 6px),
    radial-gradient(circle at 34% 72%, rgba(255, 255, 255, 0.5) 0 4px, transparent 5px),
    radial-gradient(circle at 88% 80%, rgba(255, 255, 255, 0.4) 0 2px, transparent 3px),
    radial-gradient(ellipse 2px 10px at 58% 48%, rgba(255, 255, 255, 0.45), transparent),
    radial-gradient(ellipse 2px 14px at 22% 44%, rgba(255, 255, 255, 0.4), transparent);
}
.st-key-weather_error p {
  text-align: center;
}
"""


def page_css(theme: str) -> str:
    t = THEMES[theme]
    tokens = (
        ".stApp:has(.st-key-weather_root) {"
        f" --mj-start: {t['start']}; --mj-end: {t['end']}; --mj-text: {t['text']}; --mj-shadow: {t['shadow']}; }}"
    )
    return f"<style>{PAGE_CSS}\n{tokens}</style>"


def theme_of(snapshot: Snapshot | None) -> str:
    """맑음·구름 조금(800~801)은 낮/밤 테마, 흐림·비·눈·안개 등은 흐림/비 테마."""
    if snapshot is None or snapshot.condition_id is None:
        return "cloudy"
    if snapshot.condition_id in (800, 801):
        return "clear_night" if snapshot.icon and snapshot.icon.endswith("n") else "clear_day"
    return "cloudy"


def _fmt(value: float | None, unit: str, digits: int = 0) -> str:
    if value is None:
        return "—"
    return f"{round_half_up(value)}{unit}" if digits == 0 else f"{value:.{digits}f}{unit}"


def format_date(moment: datetime) -> str:
    return f"{moment.month}월 {moment.day}일 {WEEKDAYS[moment.weekday()]}"


def format_short_date(moment: datetime) -> str:
    return f"{moment.month}/{moment.day}({WEEKDAYS[moment.weekday()][0]})"


def basis_text(snapshot: Snapshot) -> str:
    """추천이 어느 시점의 데이터로 만들어졌는지. 예: '10월 23일 금요일 09:00 예보 기준'"""
    source = "현재 관측" if snapshot.is_current else "예보"
    return f"{format_date(snapshot.time)} {snapshot.time:%H:%M} {source} 기준"


def cell_label(cell: HourCell, sky_rules: list[dict[str, Any]]) -> str:
    hour = "지금" if cell.is_now else f"{cell.time.hour}시"
    if cell.snapshot is None:
        return f"{hour} :material/remove: —"
    sky = sky_of(cell.snapshot, sky_rules)
    return f"{hour} :material/{sky.icon}: {round_half_up(cell.snapshot.temp)}°"


def _render_header(cities: list[dict[str, Any]]) -> dict[str, Any]:
    with st.container(key="weather_brand"):
        st.markdown("MOIPJI")
        st.caption("오늘 날씨에, 모입지?")
    names = [c["name"] for c in cities]
    name = st.selectbox("지역", names, index=names.index(DEFAULT_CITY), key="weather_city")
    return next(c for c in cities if c["name"] == name)


def _render_main_card(data: WeatherData, city_name: str, sky: Sky, now: datetime) -> None:
    """도시·날짜 → 아이콘과 대형 기온 → 최고/최저 (디자인 시스템 3.1)"""
    current = data.current
    extremes = day_extremes(data, now)
    with st.container(key="weather_card", gap="small"):
        with st.container(key="weather_card_top", horizontal=True, horizontal_alignment="distribute"):
            st.markdown(city_name)
            st.markdown(format_date(now))
        with st.container(horizontal=True, horizontal_alignment="center", vertical_alignment="center", gap="medium"):
            with st.container(key="weather_card_icon", width="content"):
                st.markdown(f":material/{sky.icon}:")
            with st.container(key="weather_temp", width="content"):
                st.markdown(f"{round_half_up(current.temp)}°")
        with st.container(key="weather_card_sky"):
            st.markdown(sky.label)
        with st.container(key="weather_card_range", horizontal=True, horizontal_alignment="center", gap="medium"):
            if extremes:
                st.markdown(f"최고 {round_half_up(extremes[1])}°")
                st.markdown(f"최저 {round_half_up(extremes[0])}°")
        with st.container(horizontal=True, horizontal_alignment="center", gap="medium"):
            st.caption(f"체감 {_fmt(current.feels_like, '°')}")
            st.caption(f"습도 {_fmt(current.humidity, '%')}")
            st.caption(f"바람 {_fmt(current.wind_speed, 'm/s', 1)}")
            st.caption(f"{current.time:%H:%M} 관측")


def _render_hours(cells: list[HourCell], day_id: str, sky_rules: list[dict[str, Any]]) -> HourCell:
    """0시부터 하루 끝까지 가로 스크롤. 고른 칸의 날씨로 코디를 추천한다."""
    key = f"weather_hour_{day_id}"
    index = st.pills(
        "시간별 날씨 (3시간 간격)",
        list(range(len(cells))),
        default=default_cell_index(cells),
        required=True,
        format_func=lambda i: cell_label(cells[i], sky_rules),
        key=key,
        wrap=False,
        width="stretch",
    )
    # 지난 칸은 흐리게, 지금 칸은 뒤에 은은한 빛 (디자인 시스템 3.2)
    rules = []
    past = sum(1 for c in cells if c.is_past)
    if past:
        rules.append(f".st-key-{key} button:nth-of-type(-n+{past}) {{ opacity: 0.5; }}")
    now_index = next((i for i, c in enumerate(cells) if c.is_now), None)
    if now_index is not None:
        rules.append(
            f".st-key-{key} button:nth-of-type({now_index + 1}) {{"
            " box-shadow: 0 0 24px 6px rgba(255, 255, 255, 0.35); }"
        )
    # 처음 보일 때 고른 칸이 화면 가운데 오도록 가로 스크롤을 옮긴다
    script = f"""
<script>
setTimeout(() => {{
  const root = document.querySelector('.st-key-{key}');
  const btn = root && root.querySelector('button[aria-checked="true"]');
  const strip = btn && btn.parentElement;
  if (strip) strip.scrollLeft = btn.offsetLeft - strip.clientWidth / 2 + btn.clientWidth / 2;
}}, 150);
</script>"""
    st.html(f"<style>{''.join(rules)}</style>{script}", unsafe_allow_javascript=True)
    return cells[index]


def _render_notice(message: str, detail: str | None = None) -> None:
    with st.container(key="weather_notice"):
        st.markdown(f"**{message}**")
        if detail:
            st.caption(detail)


def _render_hero(snapshot: Snapshot, question: str, rec: Recommendation, sky: Sky) -> None:
    with st.container(key="weather_hero", gap="small"):
        st.caption(question)
        with st.container(key="weather_headline"):
            st.markdown(rec.headline)
        if rec.conditions:
            with st.container(key="weather_alert"):
                st.markdown(f":material/priority_high: {rec.conditions[0].headline}")
        st.markdown(
            f":material/{sky.icon}: {sky.label}, 체감 {round_half_up(snapshot.feels_like)}°C"
            f" ({rec.temperature_range['label']} 구간)"
        )
        st.caption(basis_text(snapshot))


def _render_look(outfit: Outfit, style_name: str) -> None:
    image = image_file(outfit.image_path)
    if image:
        st.image(str(image), width="stretch", alt=f"{style_name} 완성 룩")
    else:
        with st.container(key="weather_look_placeholder"):
            st.caption(f"완성 룩 이미지 준비 중\n\n{outfit.outfit_id}")
    with st.container(key="weather_look_style"):
        st.markdown(style_name)
    outer = outfit.outer.name if outfit.outer else NO_OUTER_LABEL
    st.markdown(f"{outfit.top.name} + {outfit.bottom.name} + {outer}")
    st.caption(outfit.description)


def _render_item(key: str, label: str, item: Item | None) -> None:
    with st.container(key=f"weather_item_{key}"):
        # 아이템 이미지는 있을 때만 보여주고, 없으면 이름만 표시한다
        image = image_file(item.image_path) if item else None
        if image:
            st.image(str(image), width=96, alt=item.name)
        st.caption(label)
        st.markdown(f"**{item.name if item else NO_OUTER_LABEL}**")
        st.caption(item.reason if item else NO_OUTER_REASON)


def _render_basis(snapshot: Snapshot, rec: Recommendation, day_range: float | None, sky: Sky) -> None:
    pop = _fmt(None if snapshot.pop is None else snapshot.pop * 100, "%")
    with st.expander("날씨 및 추천 근거"):
        st.markdown(
            f"- **{basis_text(snapshot)}** ({sky.label})\n"
            f"- 기온 {round_half_up(snapshot.temp)}°C, 체감 {snapshot.feels_like:.1f}°C → "
            f"**{rec.temperature_range['label']}** 구간\n"
            f"- 강수확률 {pop}, 풍속 {_fmt(snapshot.wind_speed, 'm/s', 1)}, 일교차 {_fmt(day_range, '°C')}"
        )


def _render_tips(rec: Recommendation) -> None:
    tips = [c.tip for c in rec.conditions]
    if rec.outfit.accessories:
        tips.append(", ".join(rec.outfit.accessories))
    with st.container(key="weather_tips"):
        st.markdown("**챙길 것**")
        if tips:
            st.markdown("\n".join(f"- {t}" for t in tips))
        else:
            st.caption("따로 챙길 준비물은 없어요.")


def _render_footer(data: WeatherData | None, city_name: str) -> None:
    updated = (
        f" {format_date(data.fetched_at)} {data.fetched_at:%H:%M}에 불러온 데이터예요"
        f"({city_name} 현지 시각, 10분마다 새로 불러와요)."
        if data
        else ""
    )
    st.caption(f"날씨 정보는 [OpenWeather](https://openweathermap.org/)에서 가져와요.{updated}")


def page() -> None:
    """MOIPJI 페이지. st.set_page_config는 여기서 부르지 않는다(병합 시 app.py가 부름)."""
    # 날씨를 불러오는 동안에도 배경이 보이도록 직전 테마로 먼저 그린다
    st.html(page_css(st.session_state.get("weather_theme", DEFAULT_THEME)))
    with st.container(key="weather_root"):
        _render_page()


def _set_theme(theme: str) -> None:
    if st.session_state.get("weather_theme", DEFAULT_THEME) != theme:
        st.html(page_css(theme))
    st.session_state["weather_theme"] = theme


def _render_page() -> None:
    rules = load_json("rules.json")
    catalog = load_json("outfits.json")
    outfits = load_outfits(catalog)
    styles = {s["id"]: s for s in catalog["styles"]}
    slots = rules["time_slots"]

    city = _render_header(load_json("cities.json"))

    try:
        data = load_weather(city["lat"], city["lon"])
    except WeatherError as e:
        _set_theme("cloudy")
        with st.container(key="weather_error", gap="small"):
            st.markdown(":material/water_drop:")
            st.markdown(f"**{e}**")
            st.button("다시 시도", key="weather_retry")
        _render_footer(None, city["name"])
        return

    now = datetime.now(data.tz)
    _set_theme(theme_of(data.current))
    _render_main_card(data, city["name"], sky_of(data.current, rules["sky"]), now)

    days = {d["id"]: d for d in rules["days"]}
    day_id = st.segmented_control(
        "날짜",
        list(days),
        default="today",
        required=True,
        format_func=lambda i: f"{days[i]['label']} {format_short_date(now + timedelta(days=days[i]['offset']))}",
        key="weather_day",
        width="stretch",
    )
    day = days[day_id]
    max_minutes = rules["thresholds"]["slot_match_minutes"]
    cells = day_timeline(data, now, day["offset"], max_minutes=max_minutes)
    cell = _render_hours(cells, day_id, rules["sky"])

    style = st.segmented_control(
        "스타일",
        list(styles),
        default=DEFAULT_STYLE,
        required=True,
        format_func=lambda i: styles[i]["name"],
        key="weather_style",
        width="stretch",
    )
    st.caption(styles[style]["summary"])

    if cell.snapshot is None:
        if cell.is_past:
            _render_notice("지난 시간이라 데이터가 없어요.", "지금 이후 시간을 고르면 코디를 추천해요.")
        else:
            _render_notice("아직 데이터가 없어요.", data.forecast_error)
        _render_footer(data, city["name"])
        return

    snapshot = cell.snapshot
    slot = slot_for_hour(cell.time.hour, slots)
    day_range = daily_range(data, now, rules["thresholds"]["min_forecast_points"], day["offset"])
    rec = recommend(snapshot, slot["id"], style, day_range, rules, outfits, day["label"])
    sky = sky_of(snapshot, rules["sky"])

    _render_hero(snapshot, slot["question"][day_id], rec, sky)

    # 넓은 화면: 완성 룩 | 아이템 3개. 좁은 화면에서는 세로로 쌓인다
    look_col, items_col = st.columns([5, 6], gap="medium")
    with look_col:
        _render_look(rec.outfit, styles[style]["name"])
    with items_col:
        for key, label, item in (
            ("top", "상의", rec.outfit.top),
            ("bottom", "하의", rec.outfit.bottom),
            ("outer", "아우터", rec.outfit.outer),
        ):
            _render_item(key, label, item)

    _render_basis(snapshot, rec, day_range, sky)
    _render_tips(rec)
    _render_footer(data, city["name"])


if __name__ == "__main__":
    st.set_page_config(page_title="MOIPJI", page_icon=":material/partly_cloudy_day:", layout="centered")
    page()
