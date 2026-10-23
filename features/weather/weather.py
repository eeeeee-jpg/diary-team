"""MOIPJI — 오늘 날씨에, 모입지?

OpenWeatherMap 날씨와 사용자가 고른 스타일을 조합해 오늘의 옷차림을 추천한다.
단독 실행: streamlit run features/weather/weather.py

규칙(체감온도 구간, 시간대, 문구, 기준값)은 data/rules.json,
코디·아이템·이미지 경로는 data/outfits.json, 지역 목록은 data/cities.json에서 관리한다.
"""

from __future__ import annotations

import importlib
import json
import math
import os
import random
import time
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone, tzinfo
from html import escape
from pathlib import Path
from types import ModuleType
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv

if __package__:  # 병합 후 패키지(features.weather)로 불릴 때
    from . import minimi as _minimi
    from . import theme as _theme
else:  # streamlit run weather.py 로 단독 실행할 때
    import minimi as _minimi
    import theme as _theme


def _fresh(module: ModuleType) -> ModuleType:
    """같은 폴더 모듈(minimi.py·theme.py)을 파일이 바뀌었으면 다시 읽는다.
    Streamlit은 실행 중에 고친 weather.py는 다시 읽지만 함께 쓰는 모듈은 예전 것을 그대로 둘 때가 있다
    (예: ImportError: cannot import name 'render_greeter' from 'minimi'). 파일 수정 시각으로 확인한다."""
    mtime = Path(module.__file__).stat().st_mtime
    if getattr(module, "_mj_mtime", None) != mtime:
        module = importlib.reload(module)
        module._mj_mtime = mtime
    return module


_minimi, _theme = _fresh(_minimi), _fresh(_theme)
EYE_STYLES, HAIR_STYLES, PROP_COLORS, SKIN_TONES = (
    _minimi.EYE_STYLES, _minimi.HAIR_STYLES, _minimi.PROP_COLORS, _minimi.SKIN_TONES,
)
Body, Garment, Look = _minimi.Body, _minimi.Garment, _minimi.Look
render_dress, render_garment, render_greeter = _minimi.render_dress, _minimi.render_garment, _minimi.render_greeter
render_minimi, render_scene, render_supply = _minimi.render_minimi, _minimi.render_scene, _minimi.render_supply
render_frame, render_gnb = _theme.render_frame, _theme.render_gnb

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
WARDROBE_PATH = BASE_DIR / ".local" / "wardrobe.json"  # 옷장 (.gitignore에 포함)

API_BASE = "https://api.openweathermap.org/data/2.5"
API_KEY_NAMES = ("OPENWEATHER_API_KEY", "WEATHER_KEY")  # WEATHER_KEY는 팀 공통 규칙의 이름
TIMEOUT_SECONDS = 5
CACHE_TTL_SECONDS = 600

SERVICE_ROUTE = "weather"  # url_path·__init__.py의 ROUTE·theme.SERVICE.route와 같다
DEFAULT_CITY = "서울"
DEFAULT_STYLE = "simple"
GENDERS = {"female": "여성", "male": "남성"}
BODY_FIELDS = ("gender", "height", "build", "eyes", "skin", "hair")  # 옷장에 저장하는 미니미 체형·얼굴
GENDER_DEFAULTS = {"female": {"eyes": "round", "hair": "bob"}, "male": {"eyes": "calm", "hair": "short"}}
NICKNAME_MAX = 10  # 닉네임 글자 수
HEIGHT_RANGE = (120, 220)  # cm
WEIGHT_RANGE = (30, 200)  # kg
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
    pixel: dict[str, Any] | None = None  # 미니미가 입을 모양·색
    variants: dict[str, dict[str, Any]] | None = None  # 다른 카테고리로도 입을 때: {"top": {"pixel", "reason"}}


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
    genders: tuple[str, ...] = ("female", "male")  # 이 코디를 추천할 성별
    dress: Item | None = None  # 원피스·세트를 입으면 상의·하의 대신 이것을 입는다


@dataclass(frozen=True)
class Condition:
    id: str
    headline: str
    tip: str
    supply: str | None = None  # 이 조건에서 챙길 준비물 종류 (umbrella, water …)


@dataclass(frozen=True)
class Recommendation:
    outfit: Outfit
    temperature_range: dict[str, Any]
    headline: str
    conditions: list[Condition]  # 우선순위 순서. 첫 번째가 핵심 안내
    basis: Snapshot  # 옷을 고른 기준 = 외출 중 체감온도가 가장 낮은 때


@dataclass(frozen=True)
class Supply:
    """챙길 것 한 가지. 날씨 준비물(우산·물 …) 또는 코디 소품(목도리·비니 …)."""

    kind: str  # minimi.SUPPLY_KINDS 중 하나. 아이콘·미니미 모습과 챙기기 상태 키에 쓴다
    name: str
    reason: str
    lines: tuple[str, ...]  # 말풍선 문장 후보


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
            pixel=info.get("pixel"),
            variants=info.get("as"),
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
            genders=tuple(o.get("genders") or ("female", "male")),
        )
        for o in catalog["outfits"]
    ]


def load_closet_extras(catalog: dict[str, Any], gender: str | None = None) -> list[tuple[Item, tuple[str, ...]]]:
    """코디에는 없지만 모든 스타일의 '옷 고르기'에서 고를 수 있는 아이템과 어울리는 온도 구간.
    gender를 주면 그 성별용만 (원피스는 여성, 수트 셋업은 남성 등)."""
    items = catalog["items"]
    extras = []
    for e in catalog.get("closet_extras", []):
        if gender is not None and gender not in e.get("genders", GENDERS):
            continue
        info = items[e["item_id"]]
        item = Item(
            item_id=e["item_id"], category=info["category"], name=info["name"], reason=e["reason"],
            image_path=info["image_path"], pixel=info.get("pixel"), variants=info.get("as"),
        )
        extras.append((item, tuple(e["codes"])))
    return extras


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


@dataclass(frozen=True)
class AirReading:
    """대기질 예보 한 시각. 단위 ㎍/㎥."""

    time: datetime
    pm10: float | None
    pm25: float | None


def parse_air(raw: dict[str, Any] | None, tz: tzinfo) -> list[AirReading]:
    """OpenWeather Air Pollution 응답. 시각이 없거나 미세먼지 값이 하나도 없는 항목은 버린다."""
    readings = []
    for item in (raw or {}).get("list", []):
        dt = _num(item.get("dt"))
        comp = item.get("components") or {}
        pm10, pm25 = _num(comp.get("pm10")), _num(comp.get("pm2_5"))
        if dt is None or (pm10 is None and pm25 is None):
            continue
        readings.append(AirReading(datetime.fromtimestamp(dt, tz), pm10, pm25))
    return sorted(readings, key=lambda r: r.time)


def load_air(lat: float, lon: float, tz: tzinfo) -> list[AirReading]:
    """미세먼지 예보(시간별 4일). 실패하면 빈 목록: 마스크 추천만 빠지고 나머지는 그대로 동작한다."""
    try:
        return parse_air(weather_fetch("air_pollution/forecast", lat, lon), tz)
    except WeatherError:
        return []


def air_window(chosen: list[HourCell], readings: list[AirReading], max_minutes: int = 90) -> list[AirReading]:
    """외출 시간(첫 칸 - 90분 ~ 마지막 칸 + 90분)에 드는 대기질 예보.
    칸 시각이 아니라 칸이 쓰는 날씨의 시각 기준이다 ('지금' 칸은 21시 칸이어도 23시 관측을 쓴다)."""
    times = [c.snapshot.time if c.snapshot else c.time for c in chosen]
    if not times:
        return []
    start = min(times) - timedelta(minutes=max_minutes)
    end = max(times) + timedelta(minutes=max_minutes)
    return [r for r in readings if start <= r.time <= end]


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


def find_outfit(outfits: list[Outfit], style: str, temperature_code: str, gender: str | None = None) -> Outfit:
    """스타일·온도 구간(·성별)에 맞는 코디. gender가 None이면 성별을 따지지 않는다."""
    for outfit in outfits:
        if (
            outfit.style == style
            and outfit.temperature_code == temperature_code
            and (gender is None or gender in outfit.genders)
        ):
            return outfit
    raise KeyError(f"outfit not found: {style} {temperature_code} {gender}")


def styles_for(styles: list[dict[str, Any]], gender: str) -> dict[str, dict[str, Any]]:
    """성별에 맞는 스타일만 (여성: 러블리, 남성: 댄디). 순서는 데이터 순서."""
    return {s["id"]: s for s in styles if gender in s.get("genders", GENDERS)}


def is_sunny(snapshot: Snapshot) -> bool:
    """햇빛 쨍쨍: 맑음·구름 조금인 낮. 무료 API엔 자외선 지수가 없어 하늘 상태로 판단한다."""
    return snapshot.condition_id in (800, 801) and bool(snapshot.icon and snapshot.icon.endswith("d"))


def dust_value(air: list[AirReading], th: dict[str, Any]) -> str | None:
    """외출 중 미세먼지가 '나쁨' 이상이면 표시 문구, 아니면 None. 초미세먼지를 먼저 본다."""
    pm25 = max((r.pm25 for r in air if r.pm25 is not None), default=None)
    pm10 = max((r.pm10 for r in air if r.pm10 is not None), default=None)
    if pm25 is not None and pm25 >= th["dust_pm25"]:
        return f"초미세먼지 {round_half_up(pm25)}㎍/㎥"
    if pm10 is not None and pm10 >= th["dust_pm10"]:
        return f"미세먼지 {round_half_up(pm10)}㎍/㎥"
    return None


def detect_conditions(
    snapshots: list[Snapshot], temp_swing: float | None, rules: dict[str, Any], air: list[AirReading] | None = None
) -> list[Condition]:
    """외출 시간 전체를 보고 준비물을 고른다. 비·바람·미세먼지는 가장 심할 때, 추위·더위는 가장 춥거나 더울 때 기준."""
    th = rules["thresholds"]
    pops = [s.pop for s in snapshots if s.pop is not None]
    winds = [s.wind_speed for s in snapshots if s.wind_speed is not None]
    feels = [s.feels_like for s in snapshots]
    max_pop = max(pops, default=None)
    max_wind = max(winds, default=None)
    sunny = any(is_sunny(s) for s in snapshots)
    values: dict[str, str | None] = {
        "rain": f"{round(max_pop * 100)}" if max_pop is not None and max_pop >= th["rain_pop"] else None,
        "dust": dust_value(air or [], th),
        "cold": f"{round_half_up(min(feels))}" if min(feels) <= th["cold_feels"] else None,
        "ears": f"{round_half_up(min(feels))}" if min(feels) <= th["ear_feels"] else None,
        "hot": f"{round_half_up(max(feels))}" if max(feels) >= th["hot_feels"] else None,
        "daily_range": f"{round_half_up(temp_swing)}"
        if temp_swing is not None and temp_swing >= th["daily_range"]
        else None,
        "wind": f"{max_wind:.1f}" if max_wind is not None and max_wind >= th["wind_speed"] else None,
        "parasol": f"{round_half_up(max(feels))}" if sunny and max(feels) >= th["parasol_feels"] else None,
        "sunny": "" if sunny else None,
    }
    return [
        Condition(id=c["id"], headline=c["headline"], tip=c["tip"].format(value=values[c["id"]]), supply=c.get("supply"))
        for c in rules["conditions"]  # rules.json 순서 = 우선순위
        if values.get(c["id"]) is not None
    ]


def recommend(
    snapshots: list[Snapshot],
    slot_id: str,
    style: str,
    temp_swing: float | None,
    rules: dict[str, Any],
    outfits: list[Outfit],
    day_label: str = "오늘",
    air: list[AirReading] | None = None,
    gender: str | None = None,
) -> Recommendation:
    """외출 중 체감온도가 가장 낮은 때에 맞춰 옷을 고르고, 준비물은 외출 시간 전체로 판단한다."""
    coldest = min(snapshots, key=lambda s: s.feels_like)
    temperature_range = find_temperature_range(coldest.feels_like, rules["temperature_ranges"])
    return Recommendation(
        outfit=find_outfit(outfits, style, temperature_range["code"], gender),
        temperature_range=temperature_range,
        headline=headline_for(rules, temperature_range["code"], slot_id, day_label),
        conditions=detect_conditions(snapshots, temp_swing, rules, air),
        basis=coldest,
    )


# ---------------------------------------------------------------------------
# 외출 시간: 여러 칸을 골라 확정
# ---------------------------------------------------------------------------


def outing_cells(cells: list[HourCell], indices: list[int]) -> list[HourCell]:
    """고른 칸 중 데이터가 있는 것만, 시간순."""
    return [cells[i] for i in sorted(set(indices)) if 0 <= i < len(cells) and cells[i].snapshot is not None]


def outing_timeline(data: WeatherData, now: datetime, max_minutes: int = 90) -> list[HourCell]:
    """외출 시간 칸 48시간: 오늘 0시~내일 21시 (16칸). 자정을 넘기는 외출도 고를 수 있다."""
    return day_timeline(data, now, 0, max_minutes=max_minutes) + day_timeline(data, now, 1, max_minutes=max_minutes)


def day_of(cell: HourCell, now: datetime) -> int:
    """오늘이면 0, 내일이면 1."""
    return (cell.time.date() - now.date()).days


def outing_label(chosen: list[HourCell], step_hours: int = 3) -> str:
    """이어진 칸이면 첫 칸~마지막 칸 시각('9시~18시'), 떨어져 있으면 '9시, 18시'.
    첫 칸보다 다음 날인 칸에는 '내일'을 붙인다 ('21시~내일 3시')."""
    if not chosen:
        return ""
    first_day = chosen[0].time.date()
    names = [
        "지금" if c.is_now else (f"내일 {c.time.hour}시" if c.time.date() > first_day else f"{c.time.hour}시")
        for c in chosen
    ]
    if len(names) == 1:
        return names[0]
    step = timedelta(hours=step_hours)
    if all(b.time - a.time == step for a, b in zip(chosen, chosen[1:])):
        return f"{names[0]}~{names[-1]}"
    return ", ".join(names)


def outing_swing(chosen: list[HourCell]) -> float | None:
    """외출 중 기온 차. 칸이 하나면 None (그날 일교차로 대신한다)."""
    temps = [c.snapshot.temp for c in chosen if c.snapshot]
    return max(temps) - min(temps) if len(temps) >= 2 else None


SCENE_SEVERITY = {"rain": 3, "snow": 3, "cloudy": 1, "clear_day": 0, "clear_night": 0}


def severest(snapshots: list[Snapshot]) -> Snapshot:
    """외출 중 날씨가 가장 궂은 때 (비·눈 > 흐림 > 맑음). 같으면 먼저 온 때."""
    return max(snapshots, key=lambda s: SCENE_SEVERITY[scene_of(s)])


# ---------------------------------------------------------------------------
# 미니미: 추천 코디 → 도트 캐릭터
# ---------------------------------------------------------------------------

CATEGORIES = (("top", "상의"), ("bottom", "하의"), ("outer", "아우터"))
DRESS = "dress"
DRESS_LABEL = "원피스·세트"
PICK_CATEGORIES = (("top", "상의"), ("bottom", "하의"), (DRESS, DRESS_LABEL), ("outer", "아우터"))  # 둘러보기 탭 순서
NO_DRESS_LABEL = "상의·하의 따로 입기"


def worn_categories(outfit: Outfit) -> tuple[tuple[str, str], ...]:
    """지금 입은 칸: 원피스·세트를 입으면 상의·하의 대신 한 칸."""
    if outfit.dress is not None:
        return ((DRESS, DRESS_LABEL), ("outer", "아우터"))
    return CATEGORIES


def _garment(item: Item | None, color: str | None = None) -> Garment | None:
    if item is None or not item.pixel or item.category == DRESS:
        return None
    return Garment(item.pixel["shape"], color or item.pixel["color"], item.pixel.get("detail"))


def dress_garments(item: Item, color: str | None = None) -> tuple[Garment, Garment]:
    """원피스·세트 → 미니미가 입을 위·아래. 고른 색은 한 벌 전체에 칠한다."""
    px = item.pixel
    c = color or px["color"]
    top, bottom = px["top"], px["bottom"]
    return (
        Garment(top["shape"], top.get("color") or c, top.get("detail")),
        Garment(bottom["shape"], bottom.get("color") or c, bottom.get("detail")),
    )


def item_icon(item: Item, color: str | None, gender: str = "female") -> str:
    """옷 카드 아이콘: 원피스·세트는 한 벌로, 나머지는 성별 재단으로."""
    if item.category == DRESS:
        return render_dress(*dress_garments(item, color), item.name)
    return render_garment(_garment(item, color), item.category, item.name, gender)


def color_key(item: Item) -> str:
    """색상 선택 팔레트 위젯 키. 아이템마다 따로 기억한다."""
    return f"weather_color_{item.item_id}"


def resolve_colors(
    outfit: Outfit, palette: list[dict[str, str]], choices: Mapping[str, Any]
) -> dict[str, dict[str, str]]:
    """상의·하의·아우터별로 고른 색. 고르지 않았거나 '기본'이면 아이템 원래 색."""
    by_id = {p["id"]: p for p in palette}
    result = {}
    for category, _ in (*CATEGORIES, (DRESS, DRESS_LABEL)):
        item = getattr(outfit, category)
        if item is None or not item.pixel:
            continue
        chosen = by_id.get(choices.get(color_key(item)))
        result[category] = (
            {"id": chosen["id"], "name": chosen["name"], "color": chosen["color"]}
            if chosen
            else {"id": "default", "name": "기본", "color": item.pixel["color"]}
        )
    return result


NO_ITEM_ID = "none"  # '아우터 없음' 후보


@dataclass(frozen=True)
class Candidate:
    """스타일 안에서 고를 수 있는 아이템 하나. 아우터는 '없음'(item=None)도 후보다."""

    item: Item | None
    codes: tuple[str, ...]  # 이 아이템이 들어간 코디의 온도 구간 (따뜻한 구간부터)
    band: str  # 화면 표시용: '28°C 이상용'

    @property
    def item_id(self) -> str:
        return self.item.item_id if self.item else NO_ITEM_ID


def choice_key(style: str, category: str) -> str:
    """'선택' 버튼으로 고른 아이템을 기억하는 세션 키. 스타일마다 따로 기억한다."""
    return f"weather_choice_{style}_{category}"


def style_candidates(
    outfits: list[Outfit],
    style: str,
    category: str,
    ranges: list[dict[str, Any]],
    gender: str | None = None,
    extras: Iterable[tuple[Item, tuple[str, ...]]] = (),
) -> list[Candidate]:
    """이 스타일의 코디들에 나오는 아이템 (같은 아이템은 한 번). 따뜻한 구간용부터.
    다른 카테고리 아이템이라도 이 카테고리로 입는 법(variants)이 있으면 함께 넣는다."""
    order = {r["code"]: i for i, r in enumerate(ranges)}
    labels = {r["code"]: r["label"] for r in ranges}
    found: dict[str, tuple[Item | None, list[str]]] = {}
    if category == DRESS:  # 원피스·세트는 코디에 없고 closet_extras에서만 온다. 맨 앞은 '따로 입기'
        found[NO_ITEM_ID] = (None, [])
        outfits = []
    mine = (o for o in outfits if o.style == style and (gender is None or gender in o.genders))
    for o in sorted(mine, key=lambda o: order.get(o.temperature_code, len(order))):
        worn = [getattr(o, category)]
        for other, _ in CATEGORIES:  # 예: 아우터인 얇은 셔츠를 상의로도
            item = getattr(o, other)
            if other != category and item is not None and category in (item.variants or {}):
                v = item.variants[category]
                worn.append(replace(item, category=category, pixel=v["pixel"], reason=v.get("reason", item.reason)))
        for item in worn:
            if item is not None and not item.pixel:
                continue
            item_id = item.item_id if item else NO_ITEM_ID
            found.setdefault(item_id, (item, []))[1].append(o.temperature_code)
    for item, codes in extras:  # 코디 밖 아이템 (모든 스타일 공통)
        if item.category == category and item.pixel:
            found.setdefault(item.item_id, (item, []))[1].extend(c for c in codes if c not in found.get(item.item_id, (None, []))[1])
    warmest = lambda pair: min((order.get(c, len(order)) for c in pair[1]), default=len(order))  # noqa: E731
    ranked = sorted(found.values(), key=lambda pair: (pair[0] is not None, warmest(pair)) if category == DRESS else warmest(pair))
    return [
        Candidate(item, tuple(sorted(codes, key=lambda c: order.get(c, len(order)))),
                  ", ".join(labels.get(c, c) for c in sorted(codes, key=lambda c: order.get(c, len(order)))) + "용"
                  if codes else "상의와 하의를 따로 골라 입어요")
        for item, codes in ranked
    ]


def compose_outfit(base: Outfit, candidates: Mapping[str, list[Candidate]], choices: Mapping[str, Any]) -> Outfit:
    """추천 코디에서 시작해, 사용자가 '선택'한 카테고리만 바꾼다. 소품·설명은 추천 코디 것을 그대로 쓴다."""
    picked: dict[str, Item | None] = {}
    for category, _ in PICK_CATEGORIES:
        by_id = {c.item_id: c for c in candidates.get(category, [])}
        choice = by_id.get(choices.get(choice_key(base.style, category)))
        if choice is not None and (choice.item is not None or category in ("outer", DRESS)):
            picked[category] = choice.item
    return replace(base, **picked) if picked else base


def item_ids(outfit: Outfit) -> str:
    """조합 식별자: 상의+하의+아우터 아이템 id (원피스·세트를 입으면 원피스+아우터)."""
    worn = (outfit.dress, outfit.outer) if outfit.dress is not None else (outfit.top, outfit.bottom, outfit.outer)
    return "+".join(i.item_id if i else NO_ITEM_ID for i in worn)


def supply_color_key(kind: str) -> str:
    """준비물 색상 선택 팔레트 위젯 키."""
    return f"weather_scolor_{kind}"


def resolve_supply_colors(
    supplies: list[Supply], palette: list[dict[str, str]], choices: Mapping[str, Any]
) -> dict[str, dict[str, str]]:
    """준비물별로 고른 색. 고르지 않았거나 '기본'이면 빠진다 (미니미 기본색)."""
    by_id = {p["id"]: p for p in palette}
    result = {}
    for s in supplies:
        chosen = by_id.get(choices.get(supply_color_key(s.kind)))
        if chosen:
            result[s.kind] = {"id": chosen["id"], "name": chosen["name"], "color": chosen["color"]}
    return result


HAT_KINDS = ("beanie", "cap", "bucket")
HAND_PROPS = ("umbrella", "parasol", "sunglasses", "glasses", "mask", "water", "hotpack")  # 들거나 얼굴에 쓰는 것
SUPPLY_ORDER = tuple(PROP_COLORS)  # '기타' 탭에 보여 줄 준비물·소품 순서

# 같이 쓰거나 들 수 없는 것: 하나를 챙기면 같은 묶음의 다른 것은 뺀다
EXCLUSIVE_KINDS = (("sunglasses", "glasses"), ("beanie", "cap", "bucket"), ("umbrella", "parasol"))
# 겹쳐 입기: 가디건류끼리, 자켓류끼리는 하나만 (가디건 + 자켓은 된다)
LAYER_SHAPES = {"cardigan": ("cardigan", "shirt"), "jacket": ("jacket", "trench", "coat", "padding_short", "padding_long")}
LAYER_NAMES = {"cardigan": "가디건류", "jacket": "자켓류"}
SUPPLY_LAYER = {"extra_layer": "cardigan", "windbreaker": "jacket"}


def exclusive_with(kind: str) -> tuple[str, ...]:
    """kind와 함께 챙길 수 없는 다른 종류들."""
    return next((tuple(k for k in group if k != kind) for group in EXCLUSIVE_KINDS if kind in group), ())


def outer_layer(item: Item | None) -> str | None:
    """아우터가 가디건류인지 자켓류인지."""
    if item is None or not item.pixel:
        return None
    return next((layer for layer, shapes in LAYER_SHAPES.items() if item.pixel["shape"] in shapes), None)


def blocked_kinds(outer: Item | None) -> dict[str, str]:
    """지금 입은 아우터와 겹쳐 입게 되어 챙길 수 없는 준비물 → 안내 문구."""
    layer = outer_layer(outer)
    return {
        kind: f"{outer.name}을(를) 입고 있어서 {LAYER_NAMES[layer]}는 하나만 고를 수 있어요."
        for kind, kind_layer in SUPPLY_LAYER.items()
        if layer and kind_layer == layer
    }


def supply_def(kind: str, rules: dict[str, Any], reason: str = "필요할 때 직접 챙겨요.") -> Supply:
    """추천에 없는 준비물을 직접 고를 때 쓰는 기본 정보."""
    d = rules["supplies"][kind]
    return Supply(kind, d["name"], reason, tuple(line.replace("{name}", d["name"]) for line in d["lines"]))


def all_supplies(recommended: list[Supply], rules: dict[str, Any]) -> list[Supply]:
    """'기타' 탭 목록: 추천 준비물은 추천 이유 그대로, 나머지는 기본 정보로. SUPPLY_ORDER 순서."""
    by_kind = {s.kind: s for s in recommended}
    return [by_kind.get(kind) or supply_def(kind, rules) for kind in SUPPLY_ORDER if kind in rules["supplies"]]


def supplies_for(rec: Recommendation, rules: dict[str, Any]) -> list[Supply]:
    """추천 준비물: 날씨 조건(우선순위 순) 다음 코디 소품. 같은 종류는 한 번만."""
    defs = rules["supplies"]
    found: dict[str, Supply] = {}
    for c in rec.conditions:
        if c.supply and c.supply not in found:
            d = defs[c.supply]
            lines = tuple(line.replace("{name}", d["name"]) for line in d["lines"])
            found[c.supply] = Supply(c.supply, d["name"], c.tip, lines)
    for accessory in rec.outfit.accessories:
        kind = next((k for word, k in rules["accessory_supplies"] if word in accessory), None)
        if kind and kind not in found:
            d = defs[kind]
            lines = tuple(line.replace("{name}", accessory) for line in d["lines"])
            found[kind] = Supply(kind, accessory, "코디와 함께 챙기면 좋아요.", lines)
    return list(found.values())


def pack_key(kind: str) -> str:
    """'챙기기' 토글 위젯 키."""
    return f"weather_pack_{kind}"


def _dress(
    top: Garment | None,
    bottom: Garment | None,
    outer: Garment | None,
    packed: Iterable[str],
    prop_colors: Mapping[str, str] | None,
    body: Body | None = None,
    onepiece: bool = False,
) -> Look:
    """옷을 입히고, 챙긴 준비물만 쓰거나 들게 한다. 우산과 양산은 함께 들지 않는다."""
    packed = set(packed)
    props = [k for k in HAND_PROPS if k in packed]
    if "umbrella" in props and "parasol" in props:
        props.remove("parasol")
    return Look(
        top=top or Garment("short", "#FAFAFA"),
        bottom=bottom or Garment("pants", "#4A6FA5"),
        outer=outer,
        hat=next((k for k in HAT_KINDS if k in packed), None),
        earmuffs="earmuffs" in packed,
        scarf="scarf" in packed,
        mittens="gloves" in packed,
        tights="tights" in packed,
        props=tuple(props),
        prop_colors=tuple(sorted((k, v) for k, v in (prop_colors or {}).items() if k in packed)),
        body=body or Body(),
        onepiece=onepiece,
    )


def look_for(
    outfit: Outfit,
    packed: Iterable[str] = (),
    colors: Mapping[str, str] | None = None,
    prop_colors: Mapping[str, str] | None = None,
    body: Body | None = None,
) -> Look:
    """코디를 고른 색으로 입히고, 챙긴 준비물은 고른 색으로 쓰거나 들게 한다. body는 내 정보로 정한 체형."""
    colors = colors or {}
    if outfit.dress is not None:
        top, bottom = dress_garments(outfit.dress, colors.get(DRESS))
        onepiece = bool(outfit.dress.pixel.get("onepiece"))
        return _dress(top, bottom, _garment(outfit.outer, colors.get("outer")), packed, prop_colors, body, onepiece)
    return _dress(
        _garment(outfit.top, colors.get("top")),
        _garment(outfit.bottom, colors.get("bottom")),
        _garment(outfit.outer, colors.get("outer")),
        packed,
        prop_colors,
        body,
    )


def look_from_slots(
    slots: list[dict[str, Any]],
    packed: Iterable[str] = (),
    prop_colors: Mapping[str, str] | None = None,
    body: Body | None = None,
) -> Look:
    """옷장에 저장한 장비 칸(모양·색)으로 미니미를 다시 입힌다. 코디 목록이 바뀌어도 저장한 모습 그대로."""
    worn = {
        s["category"]: Garment(s["item"]["shape"], s["item"]["color"], s["item"].get("detail"))
        for s in slots
        if s.get("item") and s["category"] != DRESS
    }
    dress = next((s["item"] for s in slots if s["category"] == DRESS and s.get("item")), None)
    if dress is not None:  # 원피스·세트: 저장한 위·아래 모양
        top, bottom = (Garment(p["shape"], p["color"], p.get("detail")) for p in (dress["top"], dress["bottom"]))
        return _dress(top, bottom, worn.get("outer"), packed, prop_colors, body, bool(dress.get("onepiece")))
    return _dress(worn.get("top"), worn.get("bottom"), worn.get("outer"), packed, prop_colors, body)


def scene_of(snapshot: Snapshot) -> str:
    """미니룸 창밖 풍경: clear_day | clear_night | cloudy | rain | snow"""
    cid = snapshot.condition_id
    if cid is None:
        return "cloudy"
    if cid // 100 in (2, 3, 5):
        return "rain"
    if cid // 100 == 6:
        return "snow"
    if cid in (800, 801):
        return "clear_night" if snapshot.icon and snapshot.icon.endswith("n") else "clear_day"
    return "cloudy"


# ---------------------------------------------------------------------------
# 옷장: 저장한 코디 (로컬 JSON 파일 한 곳에서만 읽고 쓴다)
# ---------------------------------------------------------------------------


def load_wardrobe(path: Path = WARDROBE_PATH) -> list[dict[str, Any]]:
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return []
    return entries if isinstance(entries, list) else []


def _write_wardrobe(entries: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def add_to_wardrobe(entry: dict[str, Any], path: Path = WARDROBE_PATH) -> bool:
    """같은 시각·지역·스타일 코디가 이미 있으면 저장하지 않고 False."""
    entries = load_wardrobe(path)
    if any(e.get("key") == entry["key"] for e in entries):
        return False
    _write_wardrobe([entry, *entries], path)  # 최신이 앞
    return True


def remove_from_wardrobe(entry_id: str, path: Path = WARDROBE_PATH) -> None:
    _write_wardrobe([e for e in load_wardrobe(path) if e.get("id") != entry_id], path)


# ---------------------------------------------------------------------------
# 내 정보: 처음 들어올 때 받고, 설정(톱니바퀴)에서 바꾼다.
# 이번 접속(세션)에만 둔다. 새로고침하면 새 접속이라 처음 화면부터 다시 시작한다
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Profile:
    gender: str  # female | male
    height: int | None  # cm. None이면 '보통'
    weight: int | None  # kg. None이면 '보통'
    city: str
    eyes: str | None = None  # EYE_STYLES. None이면 성별 기본
    skin: str = "light"  # SKIN_TONES
    hair: str | None = None  # HAIR_STYLES. None이면 성별 기본
    nickname: str = ""


def _in_range(value: Any, bounds: tuple[int, int]) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value) if bounds[0] <= value <= bounds[1] else None


def clean_nickname(value: Any) -> str:
    """앞뒤·겹친 공백을 정리하고 NICKNAME_MAX 글자까지."""
    return " ".join(str(value or "").split())[:NICKNAME_MAX]


def profile_from_values(values: Mapping[str, Any], prefix: str = "") -> tuple[Profile | None, str | None]:
    """입력 칸 값 → (내 정보, 안내 문구). 성별이 없으면 내 정보를 만들 수 없고,
    닉네임이 비면 내 정보는 만들되(미리보기용) 저장은 막는다. 키·몸무게는 범위 밖이면 '보통'."""
    get = lambda field: values.get(f"{prefix}{field}")  # noqa: E731
    gender = get("gender")
    if gender not in GENDERS:
        return None, "성별을 골라 주세요."
    profile = Profile(
        gender=gender,
        height=None if get("height_normal") else _in_range(get("height"), HEIGHT_RANGE),
        weight=None if get("weight_normal") else _in_range(get("weight"), WEIGHT_RANGE),
        city=get("city") or DEFAULT_CITY,
        eyes=get("eyes") if get("eyes") in EYE_STYLES else None,
        skin=get("skin") if get("skin") in SKIN_TONES else "light",
        hair=get("hair") if get("hair") in HAIR_STYLES else None,
        nickname=clean_nickname(get("nickname")),
    )
    return profile, None if profile.nickname else "닉네임을 입력해 주세요."


def body_for(profile: Profile | None, rules: dict[str, Any]) -> Body:
    """내 정보 → 미니미 체형. 키는 성별 기준으로 작음·보통·큼, 체격은 BMI로 마름·보통·탄탄.
    키를 '보통'으로 두고 몸무게만 적었으면 성별 평균 키로 BMI를 계산한다."""
    if profile is None:
        return Body()
    cfg = rules["body"]
    short_max, tall_min = cfg["height"][profile.gender]
    height = "normal"
    if profile.height is not None:
        height = "short" if profile.height < short_max else "tall" if profile.height > tall_min else "normal"
    build = "normal"
    if profile.weight is not None:
        cm = profile.height or cfg["average_height"][profile.gender]
        bmi = profile.weight / (cm / 100) ** 2
        slim_max, sturdy_min = cfg["bmi"]
        build = "slim" if bmi < slim_max else "sturdy" if bmi >= sturdy_min else "normal"
    return Body(profile.gender, height, build, profile.eyes, profile.skin, profile.hair)


def profile_text(profile: Profile) -> str:
    """예: '모입러, 여성, 키 162cm, 몸무게 보통, 서울'"""
    height = f"{profile.height}cm" if profile.height else "보통"
    weight = f"{profile.weight}kg" if profile.weight else "보통"
    name = f"{profile.nickname}, " if profile.nickname else ""
    return f"{name}{GENDERS[profile.gender]}, 키 {height}, 몸무게 {weight}, {profile.city}"


# 아이템 이름 맨 앞의 색 단어. 색을 바꾸면 이 단어를 빼고 고른 색 이름을 붙인다 (크림 니트 → 화이트 니트)
COLOR_WORDS = (
    "화이트", "아이보리", "베이지", "카멜", "브라운", "블랙", "차콜", "그레이", "네이비", "데님",
    "스카이", "카키", "핑크", "라벤더", "레드", "크림", "파스텔", "연청", "생지", "무광",
)
BAG_SIZE = 5  # 가방 칸 수 (준비물이 더 많으면 줄이 늘어난다)


def display_name(item: Item, color: Mapping[str, str] | None = None) -> str:
    """고른 색을 반영한 아이템 이름. 예: 터틀넥 니트 + 화이트 → 화이트 터틀넥 니트"""
    if not color or color.get("id", "default") == "default":
        return item.name
    words = item.name.split()
    if len(words) > 1 and words[0] in COLOR_WORDS:
        words = words[1:]
    return " ".join([color["name"], *words])


def entry_slots(outfit: Outfit, colors: Mapping[str, Mapping[str, str]]) -> list[dict[str, Any]]:
    """옷장에 등록할 장비 칸: 상의·하의·아우터 (원피스·세트를 입으면 원피스·아우터). 아우터가 없으면 빈 칸(item=None)."""
    slots = []
    for category, label in worn_categories(outfit):
        item = getattr(outfit, category)
        if item is None or not item.pixel:
            slots.append({"category": category, "label": label, "item": None})
            continue
        color = colors.get(category)
        if category == DRESS:
            top, bottom = dress_garments(item, color["color"] if color else None)
            slots.append({
                "category": category,
                "label": label,
                "item": {
                    "name": display_name(item, color),
                    "shape": DRESS,
                    "color": color["color"] if color else item.pixel["color"],
                    "detail": None,
                    "onepiece": bool(item.pixel.get("onepiece")),
                    "top": {"shape": top.shape, "color": top.color, "detail": top.detail},
                    "bottom": {"shape": bottom.shape, "color": bottom.color, "detail": bottom.detail},
                },
            })
            continue
        slots.append({
            "category": category,
            "label": label,
            "item": {
                "name": display_name(item, color),
                "shape": item.pixel["shape"],
                "color": color["color"] if color else item.pixel["color"],
                "detail": item.pixel.get("detail"),
            },
        })
    return slots


def wardrobe_entry(
    chosen: list[HourCell],
    city: str,
    style: str,
    style_name: str,
    rec: Recommendation,
    sky: Sky,
    colors: dict[str, dict[str, str]] | None = None,
    packed: list[Supply] | None = None,
    supply_colors: Mapping[str, Mapping[str, str]] | None = None,
    body: Body | None = None,
) -> dict[str, Any]:
    """rec.outfit은 사용자가 고른 조합(compose_outfit 결과)이다."""
    outfit = rec.outfit
    start = chosen[0].time
    label = outing_label(chosen)
    colors = colors or {}
    packed = packed or []
    supply_colors = supply_colors or {}
    body = body or Body()
    # 고른 아이템·색이나 챙긴 준비물(과 그 색)이 다르면 다른 코디로 저장한다
    color_ids = ",".join(f"{k}:{v['id']}" for k, v in sorted(colors.items()))
    pack_ids = ",".join(
        sorted(s.kind + (f":{supply_colors[s.kind]['id']}" if s.kind in supply_colors else "") for s in packed)
    )
    return {
        "id": uuid.uuid4().hex,
        "key": f"{city}|{start.date().isoformat()}|{label}|{body.gender}|{style}|{item_ids(outfit)}|{color_ids}|{pack_ids}",
        "saved_at": datetime.now(start.tzinfo).isoformat(timespec="seconds"),
        "city": city,
        "basis_time": start.isoformat(),
        "outing": label,
        "sky": sky.label,
        "scene": scene_of(severest([c.snapshot for c in chosen])),
        "temp": rec.basis.temp,
        "feels_like": rec.basis.feels_like,
        "style": style,
        "style_name": style_name,
        "outfit_id": outfit.outfit_id,  # 추천 코디 (소품·설명의 출처)
        "item_ids": item_ids(outfit),
        # 썸네일 미니미 체형·얼굴
        "body": {k: getattr(body, k) for k in BODY_FIELDS},
        "items": [s["item"]["name"] if s["item"] else None for s in entry_slots(outfit, colors)],
        "slots": entry_slots(outfit, colors),
        "tips": [c.tip for c in rec.conditions],
        "headline": rec.headline,
        "supplies": [_saved_supply(s, supply_colors.get(s.kind)) for s in packed],
        "colors": {k: {"name": v["name"], "color": v["color"]} for k, v in colors.items()},
    }


def _saved_supply(supply: Supply, color: Mapping[str, str] | None) -> dict[str, str]:
    saved = {"kind": supply.kind, "name": supply.name}
    if color:
        saved |= {"color": color["color"], "color_name": color["name"]}
    return saved


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
    profile = st.session_state.get("weather_profile")
    home = profile.city if profile else DEFAULT_CITY
    city = cities.get(st.session_state.get("weather_city", home), cities[DEFAULT_CITY])
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
# 화면 — 투명 유리(Atmospheric Glass) + 싸이월드 도트 그래픽
# ---------------------------------------------------------------------------

KST = timezone(timedelta(hours=9))
WEEKDAYS = ("월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일")

# 날씨 상태별 배경 그라데이션과 글자색 (디자인 시스템 2.1)
# shadow: 흰 글자가 밝은 그라데이션 끝(민트 등)에서 대비가 낮아 도트식 1px 그림자로 보완한다
# 화면 모드(브라이트/어두움) × 날씨별 배경 그라데이션과 글자색.
# 브라이트는 밝은 그라데이션에 어두운 글자, 어두움은 어두운 그라데이션에 흰 글자. 유리 카드·스크롤바도 모드에 맞춘다
MODE_TOKENS = {
    "light": {
        "glass": "rgba(255, 255, 255, 0.55)", "glass_strong": "rgba(255, 255, 255, 0.9)",
        "glass_border": "rgba(23, 50, 77, 0.16)", "on_border": "rgba(23, 50, 77, 0.6)",
        "thumb": "rgba(23, 50, 77, 0.55)", "track": "rgba(23, 50, 77, 0.1)", "shadow": "none",
    },
    "dark": {
        "glass": "rgba(255, 255, 255, 0.12)", "glass_strong": "rgba(255, 255, 255, 0.28)",
        "glass_border": "rgba(255, 255, 255, 0.3)", "on_border": "rgba(255, 255, 255, 0.95)",
        "thumb": "rgba(255, 255, 255, 0.85)", "track": "rgba(255, 255, 255, 0.16)",
        "shadow": "1px 1px 0 rgba(0, 0, 0, 0.35)",
    },
}
THEMES = {
    "light": {
        "clear_day": {"start": "#BFE3FF", "end": "#E6FBF3", "text": "#17324D"},
        "clear_night": {"start": "#D9D4F2", "end": "#F0EDFA", "text": "#2B2440"},
        "cloudy": {"start": "#CFE2E6", "end": "#EEF5F6", "text": "#22343C"},
    },
    "dark": {
        "clear_day": {"start": "#1B3B66", "end": "#1C5C5A", "text": "#FFFFFF"},
        "clear_night": {"start": "#1F1C2C", "end": "#3D3858", "text": "#FFFFFF"},
        "cloudy": {"start": "#1F3340", "end": "#35525C", "text": "#F2F7F8"},
    },
}
MODES = {"light": ":material/light_mode: 브라이트", "dark": ":material/dark_mode: 어두움"}
DEFAULT_THEME = "clear_day"

# 모든 선택자는 MOIPJI 페이지(.st-key-weather_root)가 있을 때만 적용된다. 병합 후 다른 페이지에 새지 않게 하기 위함.
# 글꼴: 도트(갈무리)는 제목·숫자·버튼, 긴 글은 Pretendard. 갈무리는 설계 크기의 정수배(11→22, 14→70)로 써야 선명하다.
PAGE_CSS = """
@import url('https://cdn.jsdelivr.net/npm/galmuri@2.40.3/dist/galmuri.css');
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css');

.stApp:has(.st-key-weather_root) {
  --mj-blur: blur(20px);
  --mj-pad: 24px;
  --mj-unit: 8px;
  --mj-ink: #1A1A1A;
  --mj-pixel: 'Galmuri11', 'Galmuri14', monospace;
  --mj-body: 'Pretendard Variable', Pretendard, -apple-system, BlinkMacSystemFont, sans-serif;
  /* 도트식 계단 모서리 */
  --mj-notch: polygon(0 6px, 3px 6px, 3px 3px, 6px 3px, 6px 0, calc(100% - 6px) 0, calc(100% - 6px) 3px,
    calc(100% - 3px) 3px, calc(100% - 3px) 6px, 100% 6px, 100% calc(100% - 6px), calc(100% - 3px) calc(100% - 6px),
    calc(100% - 3px) calc(100% - 3px), calc(100% - 6px) calc(100% - 3px), calc(100% - 6px) 100%, 6px 100%,
    6px calc(100% - 3px), 3px calc(100% - 3px), 3px calc(100% - 6px), 0 calc(100% - 6px));
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

/* 글자 */
.st-key-weather_root {
  color: var(--mj-text);
  text-shadow: var(--mj-shadow);
}
.st-key-weather_root :where(p, li, label, h1, h2, h3, input) {
  font-family: var(--mj-body);
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
  font-family: var(--mj-pixel);
  font-size: 11px;
}
.st-key-weather_root span[role="img"] {
  color: var(--mj-text);
}

/* 유리 카드: 그림자 없이 테두리로만, 모서리는 도트 계단 */
.st-key-weather_hero_card,
.st-key-weather_reco,
.st-key-weather_tips,
.st-key-weather_wardrobe,
.st-key-weather_error,
[class*="st-key-weather_item_"],
[class*="st-key-weather_saved_"],
.st-key-weather_root [data-testid="stExpander"] details {
  background: var(--mj-glass);
  border: 2px solid var(--mj-glass-border);
  border-radius: 0;
  clip-path: var(--mj-notch);
  -webkit-backdrop-filter: var(--mj-blur);
  backdrop-filter: var(--mj-blur);
  box-shadow: none;
}
.st-key-weather_hero_card,
.st-key-weather_reco,
.st-key-weather_tips,
.st-key-weather_wardrobe,
.st-key-weather_error {
  padding: var(--mj-pad);
}
[class*="st-key-weather_item_"],
[class*="st-key-weather_saved_"] {
  padding: calc(var(--mj-unit) * 2);
  gap: calc(var(--mj-unit) / 2);
}

/* 접기(날씨 및 추천 근거) 머리줄: Streamlit 기본은 포커스·열림 때 흰 바탕이라 흰 글자가 안 보인다 */
.st-key-weather_root [data-testid="stExpander"] summary,
.st-key-weather_root [data-testid="stExpander"] summary:hover,
.st-key-weather_root [data-testid="stExpander"] summary:focus,
.st-key-weather_root [data-testid="stExpander"] summary:focus-visible,
.st-key-weather_root [data-testid="stExpander"] details[open] > summary {
  background: transparent;
  color: var(--mj-text);
}
.st-key-weather_root [data-testid="stExpander"] summary:hover {
  background: var(--mj-glass-strong);
}
.st-key-weather_root [data-testid="stExpander"] summary :is(p, span, svg) {
  color: var(--mj-text);
  fill: currentColor;
}

/* 입력 요소: 도트 글꼴 + 유리 */
.st-key-weather_root [data-testid="stButtonGroup"] button,
.st-key-weather_root button[data-testid^="stBaseButton"],
.st-key-weather_root button[data-testid="stPopoverButton"],
.st-key-weather_root [data-testid="stPopoverButton"] button {
  background: var(--mj-glass);
  border: 2px solid var(--mj-glass-border);
  border-radius: 0;
  clip-path: var(--mj-notch);
  -webkit-backdrop-filter: var(--mj-blur);
  backdrop-filter: var(--mj-blur);
  color: var(--mj-text);
}
.st-key-weather_root [data-testid="stButtonGroup"] button p,
.st-key-weather_root button[data-testid^="stBaseButton"] p,
.st-key-weather_root [data-testid="stPopoverButton"] :is(p, span) {
  color: var(--mj-text);
}
.st-key-weather_root [data-testid="stButtonGroup"] button p,
.st-key-weather_root button[data-testid^="stBaseButton"] p {
  font-family: 'Galmuri14', var(--mj-pixel);
  font-size: 14px;
}
.st-key-weather_root [data-testid="stButtonGroup"] button:is([aria-checked="true"], [aria-pressed="true"]) {
  background: var(--mj-glass-strong);
  border-color: var(--mj-on-border);
}
/* 강조 버튼(옷장에 저장): 싸이월드 주황, 어두운 글자로 대비 확보 */
.st-key-weather_root button[data-testid="stBaseButton-primary"] {
  background: #FF9A4D;
  border-color: #FFC594;
  color: var(--mj-ink);
  text-shadow: none;
}
.st-key-weather_root button[data-testid="stBaseButton-primary"] p,
.st-key-weather_root button[data-testid="stBaseButton-primary"] span {
  color: var(--mj-ink);
}
/* 저장 창은 페이지 밖(body)에 뜨므로 따로 맞춘다 */
/* 창: 둥근 모서리 (흰 상자는 role="dialog"의 부모다) */
body:has(.st-key-weather_root) [data-testid="stDialog"] div:has(> [role="dialog"]) {
  border-radius: 20px;
  overflow: hidden;
}
/* 저장 창 태그: 고른 태그 칩과 목록 글자를 키운다 */
.st-key-weather_save_tags [data-tag] {
  min-height: 32px;
  padding: 4px 8px 4px 12px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.4;
}
.st-key-weather_save_tags [data-tag] span {
  font-size: 14px;
  max-width: none;
}
.st-key-weather_save_tags [data-tag] button svg {
  width: 12px;
  height: 12px;
}
.st-key-weather_save_tags input,
body:has(.st-key-weather_root) [role="listbox"] [role="option"] {
  font-size: 15px;
}
body:has(.st-key-weather_root) [role="dialog"] button[data-testid="stBaseButton-primary"],
body:has(.st-key-weather_root) [role="dialog"] button[data-testid="stBaseButton-primary"] p {
  color: var(--mj-ink, #1A1A1A);
  font-family: 'Galmuri14', monospace;
}
.st-key-weather_root button:disabled {
  opacity: 0.7;
}
.st-key-weather_root :focus-visible {
  outline: 2px dashed var(--mj-text);
  outline-offset: 2px;
}

/* 지역 선택: 흰 바탕에는 검은 글자 (Streamlit 1.66 선택 상자는 react-aria ComboBox 구조) */
.st-key-weather_city [role="group"],
.st-key-weather_country [role="group"] {
  background: rgba(255, 255, 255, 0.92);
  border: 2px solid #FFFFFF;
  border-radius: 0;
  clip-path: var(--mj-notch);
}
.st-key-weather_city input,
.st-key-weather_country input,
.st-key-weather_city [role="group"] button,
.st-key-weather_country [role="group"] button,
body:has(.st-key-weather_root) [data-testid="stSelectboxVirtualDropdown"] [role="option"] {
  color: var(--mj-ink);
  -webkit-text-fill-color: var(--mj-ink);
  text-shadow: none;
  font-family: 'Galmuri14', var(--mj-pixel);
  font-size: 14px;
}

/* 머리글: 톱니바퀴 버튼은 아이콘만 보이게 (글자는 스크린리더용으로 남긴다) */
.st-key-weather_settings button {
  min-width: 44px;
  min-height: 44px;
  padding: 0 10px;
}
.st-key-weather_settings button [data-testid="stMarkdownContainer"] {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
.st-key-weather_settings button [data-testid="stIconMaterial"] {
  font-size: 22px;
}

/* 첫 화면: 단계 진행 표시 */
.mj-steps-wrap {
  margin: 0;
}
.mj-steps-count {
  margin: 0 0 8px;
  font-family: var(--mj-pixel);
  font-size: 18px;
  color: var(--mj-text);
}
.mj-steps-count span {
  font-family: 'Galmuri11', var(--mj-pixel);
  font-size: 12px;
  margin-left: 6px;
  opacity: 0.85;
}
.mj-steps {
  display: flex;
  gap: 6px;
  list-style: none;
  margin: 0;
  padding: 0;
}
.mj-step {
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 0;
}
.mj-step::before {  /* 단계 막대 */
  content: "";
  align-self: stretch;
  height: 6px;
  background: var(--mj-glass-border);
}
.mj-step-done::before,
.mj-step-now::before {
  background: #FF9A4D;
}
.mj-step-dot {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  font-family: var(--mj-pixel);
  font-size: 13px;
  color: var(--mj-text);
  border: 2px solid var(--mj-glass-border);
  background: var(--mj-glass);
  clip-path: var(--mj-notch);
}
.mj-step-done .mj-step-dot {
  background: #FF9A4D;
  border-color: #FFC594;
  color: var(--mj-ink);
}
.mj-step-now .mj-step-dot {
  background: #FFFFFF;
  border-color: #FF9A4D;
  color: var(--mj-ink);
  transform: scale(1.15);
}
.mj-step-name {
  font-family: 'Galmuri11', var(--mj-pixel);
  font-size: 12px;
  color: var(--mj-text);
  white-space: nowrap;
}
.mj-step-todo .mj-step-name {
  opacity: 0.7;
}
/* 첫 화면: 안내 캐릭터 무대와 말풍선 */
.st-key-weather_ob_stage {
  background: radial-gradient(circle at 50% 60%, rgba(255, 255, 255, 0.35), transparent 70%);
  padding: 8px;
}
.st-key-weather_ob_stage img {
  image-rendering: pixelated;
  max-width: 320px;
  margin: 0 auto;
}
.mj-talk {
  position: relative;
  background: #FFFFFF;
  color: var(--mj-ink);
  border: 2px solid #FFFFFF;
  clip-path: var(--mj-notch);
  padding: 14px 16px;
  text-shadow: none;
}
.mj-talk p {
  margin: 0;
  font-family: 'Galmuri14', var(--mj-pixel);
  font-size: 16px;
  line-height: 1.6;
  color: var(--mj-ink);
}
.mj-talk::before {  /* 왼쪽 캐릭터를 가리키는 꼬리 */
  content: "";
  position: absolute;
  left: -8px;
  top: 22px;
  border: 8px solid transparent;
  border-right-color: #FFFFFF;
}
.st-key-weather_ob_nav button {
  min-height: 48px;
}

/* 첫 화면: 소개 + 내 정보 */
.st-key-weather_welcome {
  background: var(--mj-glass);
  border: 2px solid var(--mj-glass-border);
  clip-path: var(--mj-notch);
  -webkit-backdrop-filter: var(--mj-blur);
  backdrop-filter: var(--mj-blur);
  padding: var(--mj-pad);
}
.st-key-weather_welcome input {
  color: var(--mj-ink);
  -webkit-text-fill-color: var(--mj-ink);
  text-shadow: none;
}

/* 머리글 */
.st-key-weather_brand p {
  font-family: var(--mj-pixel);
  font-size: 22px;
  margin: 0;
}

/* 히어로 왼쪽: 날씨 */
.st-key-weather_hero_top p {
  font-family: 'Galmuri14', var(--mj-pixel);
  font-size: 14px;
  margin: 0;
}
.st-key-weather_hero_outing p {
  font-family: 'Galmuri14', var(--mj-pixel);
  font-size: 14px;
  margin: 0;
}
.st-key-weather_hero_icon span[role="img"] {
  font-size: 48px;
}
.st-key-weather_temp p {
  font-family: 'Galmuri14', var(--mj-pixel);
  font-size: 70px;
  letter-spacing: -0.05em;
  line-height: 1;
  margin: 0;
}
.st-key-weather_hero_sky p {
  font-family: var(--mj-pixel);
  font-size: 22px;
  margin: 0;
}
.st-key-weather_hero_range p {
  font-family: 'Galmuri14', var(--mj-pixel);
  font-size: 14px;
  margin: 0;
}

/* 히어로 오른쪽: 미니룸 */
.st-key-weather_room img {
  border: 2px solid rgba(255, 255, 255, 0.9);
  clip-path: var(--mj-notch);
  image-rendering: pixelated;
}
[class*="st-key-weather_saved_"] img {
  image-rendering: pixelated;
  margin: 0 auto;
}

/* 시간별 예보: 가로 스크롤, 같은 너비 (디자인 시스템 3.2) */
.st-key-weather_pick [data-testid="stButtonGroup"] > div:last-child {
  flex-wrap: nowrap;
  overflow-x: auto;
  padding-bottom: 4px;
  /* 브라우저 기본 스크롤바는 휴대폰·맥에서 스크롤할 때만 잠깐 보이는 오버레이라 숨기고,
     아래 .mj-scroll 전용 스크롤바를 항상 보이게 둔다 */
  scrollbar-width: none;
}
.st-key-weather_pick [data-testid="stButtonGroup"] > div:last-child::-webkit-scrollbar {
  display: none;
}
.mj-scroll {
  position: relative;
  height: 14px;
  margin: 2px 0 4px;
  background: var(--mj-track);
  border: 1px solid var(--mj-glass-border);
  cursor: pointer;
  touch-action: none;
}
.mj-scroll-thumb {
  position: absolute;
  top: 1px;
  bottom: 1px;
  min-width: 28px;
  background: var(--mj-thumb);
  cursor: grab;
}
.mj-scroll:focus-visible {
  outline: 2px dashed var(--mj-text);
  outline-offset: 2px;
}
.mj-scroll[hidden] {
  display: none;
}

/* 날짜 버튼: 고른 칸이 있는 날짜를 표시하고, 누르면 그 날짜 칸으로 이동 */
.mj-days {
  display: flex;
  gap: 8px;
}
.mj-day {
  flex: 1 1 0;
  min-height: 44px;
  font-family: 'Galmuri14', var(--mj-pixel);
  font-size: 14px;
  color: var(--mj-text);
  text-shadow: var(--mj-shadow);
  background: var(--mj-glass);
  border: 2px solid var(--mj-glass-border);
  clip-path: var(--mj-notch);
  -webkit-backdrop-filter: var(--mj-blur);
  backdrop-filter: var(--mj-blur);
  cursor: pointer;
}
.mj-day[aria-pressed="true"] {
  background: var(--mj-glass-strong);
  border-color: var(--mj-on-border);
}
.mj-day:focus-visible {
  outline: 2px dashed var(--mj-text);
  outline-offset: 2px;
}
.mj-days-label {
  font-family: var(--mj-pixel);
  font-size: 11px;
  color: var(--mj-text);
  margin: 0 0 6px;
}
.st-key-weather_pick button {
  flex: 0 0 76px;
  width: 76px;
  min-height: 104px;
  padding: var(--mj-unit) 0;
}
.st-key-weather_pick button p {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.st-key-weather_pick button span[role="img"] {
  font-size: 26px;
}

/* 추천 */
.st-key-weather_headline p {
  font-family: var(--mj-pixel);
  font-size: 22px;
  line-height: 1.5;
  margin: 0;
  word-break: keep-all;
}
.st-key-weather_alert p {
  font-weight: 600;
  margin: 0;
}

/* 말풍선: 풍경 하늘 쪽에 겹치는 흰 도트 풍선, 두 번째 줄은 잠시 뒤에 나타난다 */
.st-key-weather_room {
  position: relative;
}
.st-key-weather_room > div:has(.mj-bubble) {
  position: absolute;
  top: 3%;
  left: 3%;
  width: 78%;
  z-index: 2;
}
.mj-bubble {
  position: relative;
  padding-bottom: 15px;
}
.mj-bubble-box {
  position: relative;
  background: rgba(255, 255, 255, 0.95);
  color: var(--mj-ink);
  text-shadow: none;
  padding: 10px 14px 12px;
  clip-path: var(--mj-notch);
}
.mj-tail {
  position: absolute;
  left: 48%;
  bottom: 0;
  width: 18px;
  height: 15px;
  background: rgba(255, 255, 255, 0.95);
  clip-path: polygon(0 0, 100% 0, 100% 34%, 66% 34%, 66% 67%, 33% 67%, 33% 100%, 0 100%);
}
/* 갈무리14는 14px에서 가장 선명하다 */
.mj-bubble .mj-line {
  margin: 0;
  font-family: 'Galmuri14', var(--mj-pixel);
  font-size: 14px;
  line-height: 1.6;
  color: var(--mj-ink);
  padding-right: 28px;
  word-break: keep-all;
}
.mj-bubble .mj-line1 {
  color: #5B6270;
}
/* 추천 준비물 이름: 진한 주황(흰 바탕 대비 5.2:1). 갈무리14엔 굵은 글꼴이 없어
   같은 글자를 1px 옆에 겹치는 도트식 굵게로 한 단계 두껍게 한다 */
.mj-bubble .mj-item {
  color: #C2410C;
  font-weight: 400;
  text-shadow: 1px 0 0 #C2410C;
  letter-spacing: 1px;
}
.mj-bubble .mj-line2 {
  opacity: 0;
  animation: mj-say 0.3s steps(3) 1.1s forwards;
}
.mj-bubble .mj-count {
  position: absolute;
  right: 8px;
  top: 6px;
  font-family: 'Galmuri11', var(--mj-pixel);
  font-size: 11px;
  color: #5B6270;
}
@keyframes mj-say {
  to { opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
  .mj-bubble .mj-line2 { animation: none; opacity: 1; }
}
.st-key-weather_pack_row > .st-key-weather_bubble_prev,
.st-key-weather_pack_row > .st-key-weather_bubble_next {
  flex: 0 0 auto;
  width: auto;
}
.st-key-weather_bubble_prev button,
.st-key-weather_bubble_next button {
  min-width: 40px;
  min-height: 44px;
  padding: 0 8px;
}

/* 아이템 등록 창: 게임 장비창처럼 어두운 판 + 홈이 파인 칸. 창은 body에 뜨므로 키로만 고른다 */
.st-key-weather_inv {
  background: #2B2440;
  border: 3px solid #FFC594;
  padding: 16px;
  clip-path: polygon(0 6px, 3px 6px, 3px 3px, 6px 3px, 6px 0, calc(100% - 6px) 0, calc(100% - 6px) 3px,
    calc(100% - 3px) 3px, calc(100% - 3px) 6px, 100% 6px, 100% calc(100% - 6px), calc(100% - 3px) calc(100% - 6px),
    calc(100% - 3px) calc(100% - 3px), calc(100% - 6px) calc(100% - 3px), calc(100% - 6px) 100%, 6px 100%,
    6px calc(100% - 3px), 3px calc(100% - 3px), 3px calc(100% - 6px), 0 calc(100% - 6px));
}
.st-key-weather_inv p,
.st-key-weather_inv [data-testid="stCaptionContainer"],
.st-key-weather_inv [data-testid="stCaptionContainer"] p {
  color: #F3EEFF;
  opacity: 1;
  font-family: 'Galmuri11', monospace;
}
.st-key-weather_inv > div > [data-testid="stElementContainer"]:first-child p {
  font-size: 22px;
  color: #FFC594;
}
[class*="st-key-weather_inv_"],
[class*="st-key-weather_bag_"] {
  background: #3D3561;
  border: 2px solid #6E64A0;
  box-shadow: inset 2px 2px 0 #4F4680, inset -2px -2px 0 #211B38;  /* 홈이 파인 칸 */
  padding: 8px 4px;
  align-items: center;
  text-align: center;
  gap: 4px;
  animation: mj-slot-in 0.35s steps(3) both;
}
[class*="st-key-weather_inv_"] img,
[class*="st-key-weather_bag_"] img,
[class*="st-key-weather_strip_"] img {
  image-rendering: pixelated;
}
[class*="st-key-weather_inv_"] p {
  font-size: 11px;
  word-break: keep-all;
}
[class*="st-key-weather_bag_"] [data-testid="stCaptionContainer"] p {
  font-size: 11px;
  color: #CFC6F2;
}
/* 칸이 하나씩 채워지는 등록 연출 */
.st-key-weather_inv_top { animation-delay: 0.1s; }
.st-key-weather_inv_bottom { animation-delay: 0.25s; }
.st-key-weather_inv_outer { animation-delay: 0.4s; }
.st-key-weather_bag_0 { animation-delay: 0.55s; }
.st-key-weather_bag_1 { animation-delay: 0.65s; }
.st-key-weather_bag_2 { animation-delay: 0.75s; }
.st-key-weather_bag_3 { animation-delay: 0.85s; }
.st-key-weather_bag_4 { animation-delay: 0.95s; }
@keyframes mj-slot-in {
  0% { transform: scale(0.6); opacity: 0; }
  60% { transform: scale(1.08); opacity: 1; }
  100% { transform: scale(1); opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
  [class*="st-key-weather_inv_"],
  [class*="st-key-weather_bag_"] { animation: none; }
}

/* 옷장 태그 */
.mj-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.mj-tag {
  font-family: 'Galmuri11', var(--mj-pixel);
  font-size: 13px;
  padding: 4px 8px;
  background: rgba(255, 255, 255, 0.85);
  color: var(--mj-ink);
  text-shadow: none;
}

/* 챙길 것 카드: 챙긴 카드는 테두리를 또렷하게 */
[class*="st-key-weather_supply_"] {
  background: var(--mj-glass);
  border: 2px solid var(--mj-glass-border);
  clip-path: var(--mj-notch);
  -webkit-backdrop-filter: var(--mj-blur);
  backdrop-filter: var(--mj-blur);
  padding: calc(var(--mj-unit) * 2);
  gap: calc(var(--mj-unit) / 2);
}
[class*="st-key-weather_supply_"]:has([class*="st-key-weather_pack_"] input:checked) {
  background: var(--mj-glass-strong);
  border-color: var(--mj-on-border);
}
[class*="st-key-weather_row_"] {
  background: var(--mj-glass);
  border: 2px solid var(--mj-glass-border);
  clip-path: var(--mj-notch);
  padding: calc(var(--mj-unit) * 1.5) calc(var(--mj-unit) * 2);
}
[class*="st-key-weather_supply_"] img,
[class*="st-key-weather_item_"] img,
[class*="st-key-weather_cand_"] img,
[class*="st-key-weather_other_"] img {
  image-rendering: pixelated;
}

/* 둘러보기·되돌리기 버튼: 왼쪽부터 나란히. 좁은 화면에서는 반씩 나눠 한 줄에 둔다 */
@media (max-width: 480px) {
  .st-key-weather_choice_actions > [data-testid="stElementContainer"] {
    flex: 1 1 0;
    min-width: 0;
  }
  .st-key-weather_choice_actions button {
    width: 100%;
    height: auto;
    min-height: 44px;
    padding: 4px 8px;
  }
  .st-key-weather_choice_actions button [data-testid="stIconMaterial"] {
    display: none;  /* 반쪽 너비에서는 글자를 다 보이는 게 먼저 */
  }
  .st-key-weather_choice_actions button p {
    font-size: 12px;
    line-height: 1.3;
    white-space: normal;
    word-break: keep-all;  /* 한국어는 낱말 사이에서만 줄바꿈 (둘러/보기처럼 끊기지 않게) */
    overflow: visible;
    text-overflow: clip;
  }
}

/* 아이템 고르기: 후보 카드. 입는 중인 카드는 테두리를 또렷하게 */
[class*="st-key-weather_cand_"],
[class*="st-key-weather_other_on_"],
[class*="st-key-weather_other_off_"] {
  background: var(--mj-glass);
  border: 2px solid var(--mj-glass-border);
  clip-path: var(--mj-notch);
  padding: calc(var(--mj-unit) * 1.5);
  gap: calc(var(--mj-unit) / 2);
}
[class*="st-key-weather_cand_"]:has([data-testid="stBaseButton-primary"]),
[class*="st-key-weather_other_on_"] {
  background: var(--mj-glass-strong);
  border-color: var(--mj-on-border);
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


def default_mode(moment: datetime) -> str:
    """처음 화면 모드: 저녁 6시~아침 6시는 어두움, 나머지는 브라이트."""
    return "dark" if moment.hour >= 18 or moment.hour < 6 else "light"


def current_mode() -> str:
    mode = st.session_state.get("weather_mode") or default_mode(datetime.now(KST))
    return mode if mode in THEMES else "light"


def page_css(theme: str, mode: str = "dark") -> str:
    t, m = THEMES[mode][theme], MODE_TOKENS[mode]
    tokens = (
        ".stApp:has(.st-key-weather_root) {"
        f" --mj-start: {t['start']}; --mj-end: {t['end']}; --mj-text: {t['text']}; --mj-shadow: {m['shadow']};"
        f" --mj-glass: {m['glass']}; --mj-glass-strong: {m['glass_strong']}; --mj-glass-border: {m['glass_border']};"
        f" --mj-on-border: {m['on_border']}; --mj-thumb: {m['thumb']}; --mj-track: {m['track']}; }}"
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


def outing_basis_text(chosen: list[HourCell]) -> str:
    """외출 시간 전체가 어느 데이터로 만들어졌는지. 예: '10월 23일 금요일 09:00~18:00 예보 기준'"""
    if len(chosen) == 1:
        return basis_text(chosen[0].snapshot)
    first, last = chosen[0].snapshot, chosen[-1].snapshot
    source = "현재 관측·예보" if any(c.snapshot.is_current for c in chosen) else "예보"
    return f"{format_date(first.time)} {first.time:%H:%M}~{last.time:%H:%M} {source} 기준"


def cell_label(cell: HourCell, sky_rules: list[dict[str, Any]], tomorrow_start: bool = False) -> str:
    hour = "지금" if cell.is_now else (f"내일 {cell.time.hour}시" if tomorrow_start else f"{cell.time.hour}시")
    if cell.snapshot is None:
        return f"{hour} :material/remove: —"
    sky = sky_of(cell.snapshot, sky_rules)
    return f"{hour} :material/{sky.icon}: {round_half_up(cell.snapshot.temp)}°"


def _render_top_bar(cities: list[dict[str, Any]], profile: Profile | None) -> None:
    """머리글: 로고 · 화면 모드 · 설정 · (좁은 화면) '=' 메뉴. 넓은 화면 GNB 세로 탭도 여기서 넣는다."""
    with st.container(
        key="weather_header", horizontal=True, horizontal_alignment="distribute", vertical_alignment="center", gap="small",
    ):
        with st.container(key="weather_brand", width="content"):
            st.markdown("MOIPJI")
            st.caption("오늘 날씨에, 모입지?")
        with st.container(horizontal=True, width="content", gap="small", vertical_alignment="center"):
            if profile is not None:  # 첫 화면에는 화면 모드·설정 없이 메뉴만
                st.segmented_control(
                    "화면 모드",
                    list(MODES),
                    default=current_mode(),
                    required=True,
                    format_func=lambda m: MODES[m],
                    key="weather_mode",
                    label_visibility="collapsed",
                )
                if st.button(
                    "내 정보 설정",  # 글자는 화면에서 숨기고 톱니바퀴만 보인다 (스크린리더는 읽는다)
                    key="weather_settings",
                    icon=":material/settings:",
                    help=f"내 정보 설정 ({profile_text(profile)})",
                    on_click=_prepare_profile_form,
                    args=(SETTINGS_PREFIX, profile),
                ):
                    _settings_dialog(cities)
            render_gnb()  # 톱니바퀴 오른쪽 '=' 메뉴 (좁은 화면에서만 보인다)


def countries_of(cities: list[dict[str, Any]]) -> list[str]:
    """국가 목록 (데이터 순서, 대한민국 먼저)."""
    return list(dict.fromkeys(c.get("country", "대한민국") for c in cities))


def country_of(city: str, cities: list[dict[str, Any]]) -> str:
    return next((c.get("country", "대한민국") for c in cities if c["name"] == city), "대한민국")


def _render_place(country_key: str, city_key: str, cities: list[dict[str, Any]]) -> str:
    """국가를 고른 뒤 그 나라 도시를 고른다. 나라를 바꾸면 도시는 그 나라 첫 도시로."""
    state = st.session_state
    state.setdefault(city_key, DEFAULT_CITY)
    state.setdefault(country_key, country_of(state[city_key], cities))
    with st.container(horizontal=True, gap="small"):
        country = st.selectbox("국가", countries_of(cities), key=country_key)
        names = [c["name"] for c in cities if c.get("country", "대한민국") == country]
        if state.get(city_key) not in names:  # 도시 칸은 아직 그리기 전이라 값을 맞출 수 있다
            state[city_key] = names[0]
        return st.selectbox("도시", names, key=city_key)


def _render_header(cities: list[dict[str, Any]], profile: Profile) -> dict[str, Any]:
    _render_top_bar(cities, profile)
    st.session_state.setdefault("weather_city", profile.city)  # 처음엔 내 지역. 여기서 바꾸면 이번 접속에서만 바뀐다
    with st.container(key="weather_place"):
        name = _render_place("weather_country", "weather_city", cities)
    return next(c for c in cities if c["name"] == name)


WELCOME_PREFIX = "weather_ob_"
SETTINGS_PREFIX = "weather_set_"


def _prepare_profile_form(prefix: str, profile: Profile | None) -> None:
    """입력 칸을 저장된 내 정보(없으면 기본값)로 채운다. 설정 창을 열 때마다 새로 채운다."""
    st.session_state[f"{prefix}gender"] = profile.gender if profile else None
    st.session_state[f"{prefix}height_normal"] = profile is None or profile.height is None
    st.session_state[f"{prefix}height"] = (profile and profile.height) or 165
    st.session_state[f"{prefix}weight_normal"] = profile is None or profile.weight is None
    st.session_state[f"{prefix}weight"] = (profile and profile.weight) or 60
    st.session_state[f"{prefix}city"] = profile.city if profile else DEFAULT_CITY
    st.session_state.pop(f"{prefix}country", None)  # 도시에 맞춰 다시 정한다
    st.session_state[f"{prefix}nickname"] = profile.nickname if profile else ""
    defaults = GENDER_DEFAULTS[profile.gender if profile else "female"]
    st.session_state[f"{prefix}eyes"] = (profile and profile.eyes) or defaults["eyes"]
    st.session_state[f"{prefix}skin"] = profile.skin if profile else "light"
    st.session_state[f"{prefix}hair"] = (profile and profile.hair) or defaults["hair"]


def _follow_gender(prefix: str) -> None:
    """성별을 바꾸면, 눈·헤어를 아직 다른 성별 기본값 그대로 두었을 때만 이 성별 기본값으로 바꾼다."""
    gender = st.session_state.get(f"{prefix}gender")
    if gender not in GENDERS:
        return
    other = GENDER_DEFAULTS["male" if gender == "female" else "female"]
    for field in ("eyes", "hair"):
        if st.session_state.get(f"{prefix}{field}") == other[field]:
            st.session_state[f"{prefix}{field}"] = GENDER_DEFAULTS[gender][field]


def _render_profile_fields(prefix: str, cities: list[dict[str, Any]]) -> None:
    """닉네임·성별·지역(국가 → 도시) + 미니미 눈·피부색·헤어. 키·몸무게는 묻지 않는다 (보통 체형)."""
    st.text_input(
        "닉네임", key=f"{prefix}nickname", max_chars=NICKNAME_MAX, placeholder="예: 모입러",
        help=f"추천 카드에서 불러 드릴 이름이에요. {NICKNAME_MAX}자까지.",
    )
    st.segmented_control(
        "성별", list(GENDERS), format_func=lambda g: GENDERS[g], key=f"{prefix}gender", width="stretch",
        on_change=_follow_gender, args=(prefix,),
    )
    _render_place(f"{prefix}country", f"{prefix}city", cities)
    _render_look_fields(prefix)


def _render_look_fields(prefix: str, preview: bool = True) -> None:
    """미니미 얼굴: 눈 3가지·피부색 5가지·헤어 5가지와 (preview면) 바로 보이는 미리보기."""
    with st.container(key=f"{prefix}looks", horizontal=True, gap="medium", vertical_alignment="center"):
        form = _profile_from_form(prefix)
        body = body_for(form, load_json("rules.json")) if form else Body(
            "female", eyes=st.session_state.get(f"{prefix}eyes"), skin=st.session_state.get(f"{prefix}skin", "light"),
            hair=st.session_state.get(f"{prefix}hair"),
        )
        look = Look(Garment("short", "#F1EDE3", "collar"), Garment("pants", "#4A6FA5"), body=body)
        if preview:
            st.image(render_minimi(look, "내 미니미 미리보기"), width=72, alt="내 미니미 미리보기")
        with st.container(width="stretch", gap="small"):
            st.segmented_control("눈", list(EYE_STYLES), format_func=EYE_STYLES.get, key=f"{prefix}eyes", required=True)
            st.pills(
                "피부색", list(SKIN_TONES), format_func=lambda k: SKIN_TONES[k][0], key=f"{prefix}skin", required=True,
            )
            st.pills("헤어", list(HAIR_STYLES), format_func=HAIR_STYLES.get, key=f"{prefix}hair", required=True)
    # 피부색 칩은 그 색으로 칠한다 (이름도 함께 적어 색만으로 구분하지 않게)
    rules = [
        f".st-key-{prefix}skin button:nth-of-type({n}) {{ background: {color}; color: {_text_on(color)}; text-shadow: none; }}"
        f".st-key-{prefix}skin button:nth-of-type({n}) p {{ color: {_text_on(color)}; }}"
        for n, (_, color) in enumerate(SKIN_TONES.values(), 1)
    ]
    rules.append(
        f".st-key-{prefix}skin button:is([aria-checked='true'], [aria-pressed='true']) {{ outline: 3px solid var(--mj-text, #1F3B5C); outline-offset: -3px; }}"
    )
    st.html(f"<style>{''.join(rules)}</style>")


def _profile_from_form(prefix: str) -> Profile | None:
    return profile_from_values(st.session_state, prefix)[0]


# 설정을 저장하면 지금 고른 것들을 처음 상태로 돌린다 (성별·체형이 바뀌면 고른 아이템이 맞지 않을 수 있어서)
# 위젯 값은 지우면 브라우저가 이전 값을 다시 보내므로 기본값으로 덮어쓰고, 위젯이 아닌 값은 지운다
PICK_RESETS = (("weather_pack_", False), ("weather_palette_", False), ("weather_spalette_", False))
PICK_DROPS = ("weather_color_", "weather_scolor_")  # 고른 색 (위젯 밖 값과 옛 팔레트 위젯 값)
PICK_KEEP = {"weather_pack_one", "weather_pack_row"}  # 같은 접두사를 쓰는 버튼·상자


def _reset_picks() -> None:
    state = st.session_state
    for key in list(state.keys()):
        if key in PICK_KEEP:
            continue
        if (key.startswith("weather_choice_") and key != "weather_choice_reset") or key.startswith(PICK_DROPS):
            del state[key]
            continue
        for prefix, value in PICK_RESETS:
            if key.startswith(prefix):
                state[key] = value
    state.pop("weather_bubble", None)
    state.pop("weather_last_pack", None)
    _bump_palette_gen()
    state["weather_browse"] = False  # 둘러보기는 버튼으로 켜고 끄는 값 (위젯 값이 아니라 지워도 되지만 명시적으로 닫는다)


def _apply_profile(prefix: str, styles: list[dict[str, Any]]) -> None:
    """'시작하기'·'저장' 버튼 콜백. 저장하고 지역·스타일을 바로 맞춘다 (위젯이 그려지기 전이라 바꿀 수 있다)."""
    profile, error = profile_from_values(st.session_state, prefix)
    if error:
        st.session_state["weather_profile_error"] = error
        return
    st.session_state.pop("weather_profile_error", None)
    if prefix == SETTINGS_PREFIX:
        _reset_picks()
    st.session_state["weather_profile"] = profile
    st.session_state["weather_profile_saved"] = True  # 설정 창이 페이지 전체를 다시 그리게 하는 표시
    st.session_state["weather_city"] = profile.city
    st.session_state.pop("weather_country", None)  # 머리글 국가 칸은 새 도시에 맞춰 다시 정한다
    if st.session_state.get("weather_style") not in styles_for(styles, profile.gender):
        st.session_state["weather_style"] = DEFAULT_STYLE
    st.toast("내 정보를 저장했어요.", icon=":material/check:")


@st.dialog("내 정보 설정")
def _settings_dialog(cities: list[dict[str, Any]]) -> None:
    # 창 안의 버튼은 창만 다시 그린다. 저장했으면 페이지 전체를 다시 그려 창을 닫고 체형·코디·지역을 반영한다
    if st.session_state.pop("weather_profile_saved", False):
        st.rerun()
    st.caption("미니미 체형·얼굴과 추천 코디, 지역에 반영돼요.")
    st.warning(
        "저장하면 지금 고른 아이템·색과 챙긴 준비물이 초기화돼요. "
        "내 정보는 이번 접속에만 저장돼서, 새로고침하면 처음 화면으로 돌아가요.",
        icon=":material/warning:",
    )
    _render_profile_fields(SETTINGS_PREFIX, cities)
    if error := st.session_state.get("weather_profile_error"):
        st.error(error)
    st.button(
        "저장", key="weather_set_save", type="primary", width="stretch",
        on_click=_apply_profile, args=(SETTINGS_PREFIX, load_json("outfits.json")["styles"]),
    )


def current_profile() -> Profile | None:
    """이번 접속에서 입력한 내 정보. 새로고침(새 접속)하면 없어서 첫 화면이 나온다."""
    return st.session_state.get("weather_profile")


WELCOME_STEPS = (
    # (진행 표시 이름, 안내 캐릭터 말풍선) — {nick}은 닉네임
    ("닉네임", "안녕! 나는 오늘 날씨에 맞춰 옷을 골라 줄 모입이야. 뭐라고 부르면 될까?"),
    ("성별", "{nick}, 반가워! 어떤 코디를 추천해 줄까?"),
    ("지역", "어디 날씨를 볼까? 나라를 먼저 고르고 도시를 골라 줘. 해외 여행지도 돼!"),
    ("꾸미기", "이제 나를 {nick}랑 닮게 꾸며 줘. 눈, 피부색, 헤어를 골라 봐!"),
    ("시작", "준비 끝! {nick}의 오늘 코디, 같이 보러 갈까?"),
)


def welcome_progress(step: int, total: int = len(WELCOME_STEPS)) -> str:
    """예: '2단계 / 5단계, 앞으로 3단계 남았어요'"""
    left = total - step - 1
    tail = "마지막 단계예요" if left == 0 else f"앞으로 {left}단계 남았어요"
    return f"{step + 1}단계 / {total}단계, {tail}"


def welcome_check(step: int, values: Mapping[str, Any], prefix: str = WELCOME_PREFIX) -> str | None:
    """다음 단계로 넘어가기 전 확인. 문제가 있으면 안내 문구."""
    if step == 0 and not clean_nickname(values.get(f"{prefix}nickname")):
        return "닉네임을 입력해 주세요."
    if step == 1 and values.get(f"{prefix}gender") not in GENDERS:
        return "성별을 골라 주세요."
    return None


def _welcome_move(step: int) -> None:
    state = st.session_state
    current = state.get("weather_ob_step", 0)
    if step > current and (error := welcome_check(current, state)):
        state["weather_ob_error"] = error
        return
    state.pop("weather_ob_error", None)
    state["weather_ob_step"] = max(0, min(step, len(WELCOME_STEPS) - 1))


def _welcome_steps_html(step: int) -> str:
    items = []
    for i, (label, _) in enumerate(WELCOME_STEPS):
        state = "done" if i < step else "now" if i == step else "todo"
        mark = "✓" if i < step else str(i + 1)
        current = ' aria-current="step"' if i == step else ""
        items.append(f'<li class="mj-step mj-step-{state}"{current}><span class="mj-step-dot">{mark}</span>'
                     f'<span class="mj-step-name">{escape(label)}</span></li>')
    return (
        f'<div class="mj-steps-wrap"><p class="mj-steps-count">STEP {step + 1} / {len(WELCOME_STEPS)}'
        f' <span>{escape(welcome_progress(step))}</span></p>'
        f'<ol class="mj-steps" aria-label="시작 단계">{"".join(items)}</ol></div>'
    )


def _greeter_look(prefix: str) -> Look:
    """첫 화면 안내 캐릭터: 지금까지 고른 성별·얼굴로 그린다."""
    state = st.session_state
    gender = state.get(f"{prefix}gender") if state.get(f"{prefix}gender") in GENDERS else "female"
    body = Body(gender, eyes=state.get(f"{prefix}eyes"), skin=state.get(f"{prefix}skin", "light"), hair=state.get(f"{prefix}hair"))
    top = Garment("long", "#FFE3B3", "knit") if gender == "female" else Garment("hood", "#9FB7D9")
    return Look(top, Garment("pants", "#4A6FA5"), body=body)


def _render_welcome(cities: list[dict[str, Any]], styles: list[dict[str, Any]]) -> None:
    """처음 들어왔을 때: 큰 안내 캐릭터와 대화하듯 한 단계에 하나씩 내 정보를 받는다.
    모든 단계의 입력 칸을 늘 그리고 지금 단계만 보이게 한다 (안 보이는 단계의 입력값도 그대로 남게)."""
    state = st.session_state
    if f"{WELCOME_PREFIX}city" not in state:
        _prepare_profile_form(WELCOME_PREFIX, None)
    step = state.get("weather_ob_step", 0)
    last = len(WELCOME_STEPS) - 1
    nick = clean_nickname(state.get(f"{WELCOME_PREFIX}nickname")) or "친구"
    _render_top_bar(cities, None)
    hidden = "".join(f".st-key-weather_ob_step{i} {{ display: none; }}" for i in range(len(WELCOME_STEPS)) if i != step)
    st.html(f"<style>{hidden}</style>")
    with st.container(key="weather_welcome", gap="medium"):
        st.html(_welcome_steps_html(step))
        stage, talk = st.columns([2, 3], gap="medium", vertical_alignment="center")
        with stage, st.container(key="weather_ob_stage"):
            # 단계가 바뀔 때마다 동작 순서를 새로 섞는다 (안녕 손 흔들기로 시작)
            st.image(render_greeter(_greeter_look(WELCOME_PREFIX), "안내 캐릭터 모입", seed=step * 7 + len(nick)),
                     width="stretch", alt="손을 흔들며 인사하는 안내 캐릭터 모입")
        with talk:
            line = WELCOME_STEPS[step][1].format(nick=nick)
            st.html(f'<div class="mj-talk" role="status" aria-live="polite"><p>{escape(line)}</p></div>')
            with st.container(key="weather_ob_step0"):
                st.text_input(
                    "닉네임", key=f"{WELCOME_PREFIX}nickname", max_chars=NICKNAME_MAX, placeholder="예: 모입러",
                    help=f"추천 카드에서 불러 드릴 이름이에요. {NICKNAME_MAX}자까지.",
                )
            with st.container(key="weather_ob_step1"):
                st.segmented_control(
                    "성별", list(GENDERS), format_func=lambda g: GENDERS[g], key=f"{WELCOME_PREFIX}gender",
                    width="stretch", on_change=_follow_gender, args=(WELCOME_PREFIX,),
                )
                st.caption("여성은 Lovely, 남성은 Dandy 스타일이 함께 나와요.")
            with st.container(key="weather_ob_step2"):
                _render_place(f"{WELCOME_PREFIX}country", f"{WELCOME_PREFIX}city", cities)
            with st.container(key="weather_ob_step3"):
                _render_look_fields(WELCOME_PREFIX, preview=False)
            with st.container(key="weather_ob_step4"):
                country = state.get(f"{WELCOME_PREFIX}country") or country_of(state.get(f"{WELCOME_PREFIX}city"), cities)
                gender = GENDERS.get(state.get(f"{WELCOME_PREFIX}gender"), "—")
                st.markdown(f"**{nick}** 님, {gender}, {country} {state.get(f'{WELCOME_PREFIX}city')}")
                st.caption("내 정보는 이번 접속에만 저장돼서, 새로고침하면 처음 화면으로 돌아가요. 그 전엔 오른쪽 위 톱니바퀴에서 바꿀 수 있어요.")
            if error := state.get("weather_ob_error") or (step == last and state.get("weather_profile_error")):
                st.error(error)
            with st.container(key="weather_ob_nav", horizontal=True, gap="small"):
                st.button("이전", key="weather_ob_back", icon=":material/arrow_back:", disabled=step == 0,
                          on_click=_welcome_move, args=(step - 1,))
                if step < last:
                    st.button("다음", key="weather_ob_next", type="primary", icon=":material/arrow_forward:",
                              on_click=_welcome_move, args=(step + 1,), width="stretch")
                else:
                    st.button("MOIPJI 시작하기", key="weather_ob_start", type="primary", icon=":material/rocket_launch:",
                              on_click=_apply_profile, args=(WELCOME_PREFIX, styles), width="stretch")


def _render_hero(
    city_name: str,
    date_label: str,
    chosen: list[HourCell],
    sky: Sky | None,
    scene: str,
    look: Look | None,
    entry: dict[str, Any] | None,
    empty_reason: str,
    supplies: list[Supply],
    packed: set[str],
    bubble: dict[str, Any],
    save_name: str = "",
    tag_options: list[str] | None = None,
) -> None:
    """왼쪽: 확정한 외출 시간의 날씨 / 오른쪽: 말풍선, 바깥 풍경 속 미니미, 챙기기·저장 버튼."""
    with st.container(key="weather_hero_card"):
        left, right = st.columns([1, 1], gap="medium", vertical_alignment="center")
        with left:
            with st.container(key="weather_hero_top", horizontal=True, horizontal_alignment="distribute"):
                st.markdown(city_name)
                st.markdown(date_label)
            if not chosen or sky is None:
                st.markdown(f"**{empty_reason}**")
                st.caption("시간별 날씨에서 외출할 시간을 고르고 확정해 주세요.")
            else:
                snaps = [c.snapshot for c in chosen]
                temps = [s.temp for s in snaps]
                feels = [s.feels_like for s in snaps]
                low, high = round_half_up(min(temps)), round_half_up(max(temps))
                with st.container(key="weather_hero_outing"):
                    st.markdown(f"외출 {outing_label(chosen)}")
                with st.container(horizontal=True, vertical_alignment="center", gap="small"):
                    with st.container(key="weather_hero_icon", width="content"):
                        st.markdown(f":material/{sky.icon}:")
                    with st.container(key="weather_temp", width="content"):
                        st.markdown(f"{low}°" if low == high else f"{low}~{high}°")
                with st.container(key="weather_hero_sky"):
                    st.markdown(sky.label)
                with st.container(key="weather_hero_range", horizontal=True, gap="medium"):
                    low_f, high_f = round_half_up(min(feels)), round_half_up(max(feels))
                    st.markdown(f"체감 {low_f}°" if low_f == high_f else f"체감 {low_f}~{high_f}°")
                pops = [s.pop for s in snaps if s.pop is not None]
                winds = [s.wind_speed for s in snaps if s.wind_speed is not None]
                with st.container(horizontal=True, gap="small"):
                    st.caption(f"강수확률 최대 {_fmt(max(pops) * 100 if pops else None, '%')}")
                    st.caption(f"바람 최대 {_fmt(max(winds, default=None), 'm/s', 1)}")
                st.caption(outing_basis_text(chosen))
        with right:
            title = "오늘의 미니미" if look else "바깥 풍경"
            with st.container(key="weather_room"):
                # st.html은 SVG를 걸러내므로 이미지로 넣는다
                # 방금 챙긴 준비물이 있으면 그 동작을 한 번 보여 준다 (다음 실행부터는 최종 자세만)
                action = st.session_state.pop("weather_last_pack", None)
                action = action if look is not None and action in packed else None
                st.image(render_scene(look, scene, title, action), width="stretch", alt=title)
                if look is not None:  # 말풍선은 풍경 위 하늘 쪽에 겹쳐 띄운다
                    st.html(bubble_html(supplies, bubble))
            if supplies:
                _render_pack_row(supplies, packed, bubble.get("index", 0))
            if entry is not None:
                saved = any(e.get("key") == entry["key"] for e in load_wardrobe())
                if st.button(
                    "옷장에 있어요" if saved else "옷장에 저장",
                    key="weather_save",
                    icon=":material/checkroom:",
                    type="primary",
                    disabled=saved,
                    width="stretch",
                ):
                    _save_dialog(entry, save_name, tag_options or [], look)


def _render_pack_row(supplies: list[Supply], packed: set[str], index: int) -> None:
    """[<] (말풍선 속 준비물) 챙기기 [>] — 말풍선이 보여 주는 준비물 하나만 챙기거나 취소한다."""
    count = len(supplies)
    current = bubble_supply(supplies, index)
    is_packed = current.kind in packed
    with st.container(key="weather_pack_row", horizontal=True, vertical_alignment="center", gap="small", wrap=False):
        if count > 1:
            st.button("<", key="weather_bubble_prev", help="이전 준비물", on_click=_move_bubble, args=(-1, count))
        st.button(
            pack_button_label(current, is_packed),
            key="weather_pack_one",
            icon=":material/undo:" if is_packed else ":material/backpack:",
            on_click=_toggle_pack,
            args=(current.kind, current.name),
            width="stretch",
        )
        if count > 1:
            st.button(">", key="weather_bubble_next", help="다음 준비물", on_click=_move_bubble, args=(1, count))


def _slot_icon(slot: Mapping[str, Any], gender: str = "female") -> str:
    item = slot["item"]
    if slot["category"] == DRESS:
        top, bottom = (Garment(p["shape"], p["color"], p.get("detail")) for p in (item["top"], item["bottom"]))
        return render_dress(top, bottom, item["name"])
    return render_garment(Garment(item["shape"], item["color"], item.get("detail")), slot["category"], item["name"], gender)


def _entry_gender(entry: Mapping[str, Any]) -> str:
    return (entry.get("body") or {}).get("gender") or "female"


def _render_inventory(entry: dict[str, Any], look: Look | None) -> None:
    """게임 장비창처럼: 미니미 + 장비 칸(상의·하의·아우터) + 가방 칸(챙긴 준비물)."""
    supplies = entry.get("supplies") or []
    with st.container(key="weather_inv"):
        st.markdown("**아이템 등록**")
        st.caption("이 아이템들이 옷장에 한 칸씩 등록돼요.")
        # st.columns는 좁은 화면에서 한 칸씩 세로로 쌓이므로, 고정 너비 칸을 줄바꿈되는 가로 줄에 놓는다
        with st.container(horizontal=True, gap="medium", vertical_alignment="center"):
            if look is not None:
                st.image(render_minimi(look, "저장할 미니미"), width=96, alt="저장할 미니미")
            with st.container(width="stretch", gap="small"):
                st.caption("장비")
                with st.container(horizontal=True, gap="small"):
                    for slot in entry["slots"]:
                        with st.container(key=f"weather_inv_{slot['category']}", width=104):
                            st.caption(slot["label"])
                            if slot["item"]:
                                st.image(_slot_icon(slot, _entry_gender(entry)), width=48, alt=slot["item"]["name"])
                                st.markdown(f"**{slot['item']['name']}**")
                            else:
                                st.markdown("—")
                                st.caption("비어 있음")
                st.caption(f"가방 {len(supplies)}/{max(BAG_SIZE, len(supplies))}")
                bag = [*supplies, *([None] * (BAG_SIZE - len(supplies)))]
                with st.container(horizontal=True, gap="small"):
                    for n, supply in enumerate(bag):
                        with st.container(key=f"weather_bag_{n}", width=64):
                            if supply:
                                st.image(
                                    render_supply(supply["kind"], supply["name"], supply.get("color")), width=32, alt=supply["name"]
                                )
                                st.caption(supply["name"])
                            else:
                                st.caption("빈 칸")


@st.dialog("옷장에 저장", width="large")
def _save_dialog(entry: dict[str, Any], default_name: str, tag_options: list[str], look: Look | None = None) -> None:
    """등록될 아이템을 장비창으로 보여 주고, 저장할 이름과 태그를 정한다."""
    _render_inventory(entry, look)
    name = st.text_input(
        "저장할 이름", key="weather_save_name", max_chars=30, placeholder=default_name,
        help="비워 두면 placeholder의 이름으로 저장해요.",
    )
    tags = st.multiselect(
        "태그",
        tag_options,
        key="weather_save_tags",
        accept_new_options=True,
        placeholder="고르거나 새 태그를 입력하고 Enter",
        max_selections=5,
        select_all=False,  # 태그를 한꺼번에 고를 일은 없고, 기본 문구가 영어("Select all")라 끈다
    )
    st.caption("새 태그를 입력하면 다음부터 목록에서 고를 수 있어요. 최대 5개.")
    if st.button("이름과 태그로 저장", key="weather_save_confirm", type="primary", width="stretch"):
        named = {**entry, "name": (name or "").strip() or default_name, "tags": clean_tags(tags)}
        if add_to_wardrobe(named):
            for key in ("weather_save_name", "weather_save_tags"):
                st.session_state.pop(key, None)
            st.toast(f"'{named['name']}'(으)로 옷장에 저장했어요.", icon=":material/checkroom:")
            st.rerun()
        else:
            st.warning("이미 옷장에 있는 코디예요.")


def clean_tags(tags: list[str]) -> list[str]:
    """앞뒤 공백·'#'을 떼고, 빈 태그와 중복을 뺀다. 순서는 유지."""
    result: list[str] = []
    for tag in tags:
        t = str(tag).strip().lstrip("#").strip()[:12]
        if t and t not in result:
            result.append(t)
    return result


def wardrobe_tag_options(presets: list[str], entries: list[dict[str, Any]]) -> list[str]:
    """기본 태그 + 지금까지 옷장에 직접 추가한 태그."""
    options = list(presets)
    for e in entries:
        for tag in e.get("tags") or []:
            if tag not in options:
                options.append(tag)
    return options


def default_save_name(chosen: list[HourCell], sky: Sky, style_name: str) -> str:
    """예: '10/23(금) 9시~18시 흐림 Simple 코디'"""
    return f"{format_short_date(chosen[0].time)} {outing_label(chosen)} {sky.label} {style_name} 코디"


def bubble_supply(supplies: list[Supply], index: int) -> Supply:
    """말풍선이 지금 보여 주는 준비물."""
    return supplies[index % len(supplies)]


def pack_button_label(supply: Supply, is_packed: bool) -> str:
    return f"{supply.name} 챙기기 취소" if is_packed else f"{supply.name} 챙기기"


def _toggle_pack(kind: str, name: str) -> None:
    """말풍선 아래 '○○ 챙기기' 버튼."""
    _pick_supply(kind, not st.session_state.get(pack_key(kind), False))


def _move_bubble(step: int, count: int) -> None:
    st.session_state["weather_bubble"] = (st.session_state.get("weather_bubble", 0) + step) % count


def bubble_lines(supplies: list[Supply], index: int, rules: dict[str, Any], pick=random.choice) -> tuple[str, str]:
    """말풍선 두 줄: 먼저 '다른 건 챙길 것 없나?', 이어서 지금 보고 있는 준비물에 대한 랜덤 문장."""
    opener = rules["bubble"]["opener"]
    if not supplies:
        return opener, pick(rules["bubble"]["nothing"])
    return opener, pick(bubble_supply(supplies, index).lines)


def highlight_item(line: str, name: str) -> str:
    """말풍선 문장에서 준비물 이름을 강조한다. 이름이 그대로 없으면 마지막 단어로 찾는다 (여벌 가디건 → 가디건)."""
    text = escape(line)
    for word in dict.fromkeys((name, name.split()[-1])):
        target = escape(word)
        if target and target in text:
            return text.replace(target, f'<strong class="mj-item">{target}</strong>', 1)
    return text


def bubble_html(supplies: list[Supply], bubble: dict[str, Any]) -> str:
    """풍경 위에 겹치는 말풍선. 첫 줄 뒤에 둘째 줄이 잠시 뒤 나타난다."""
    count = len(supplies)
    first, second = bubble["lines"]
    position = f"{bubble['index'] % count + 1}/{count}" if count else ""
    second_html = highlight_item(second, bubble_supply(supplies, bubble["index"]).name) if count else escape(second)
    return (
        '<div class="mj-bubble" role="status" aria-live="polite"><div class="mj-bubble-box">'
        f'<p class="mj-line mj-line1">{escape(first)}</p>'
        f'<p class="mj-line mj-line2">{second_html}</p>'
        + (f'<span class="mj-count">{position}</span>' if position else "")
        + '</div><span class="mj-tail"></span></div>'
    )


def _confirm_outing() -> None:
    st.session_state["weather_outing"] = sorted(st.session_state.get("weather_pick") or [])


def _refresh_weather() -> None:
    weather_fetch.clear()
    st.toast("최신 날씨로 새로고침했어요.", icon=":material/refresh:")


def _render_days(cells: list[HourCell], now: datetime, picked: list[int]) -> None:
    """오늘·내일 버튼: 고른 칸이 있는 날짜가 선택 상태가 되고(둘 다일 수 있음), 누르면 그 날짜 칸으로 이동한다."""
    on = {day_of(cells[i], now) for i in picked if 0 <= i < len(cells)}
    first_index = {d: next(i for i, c in enumerate(cells) if day_of(c, now) == d) for d in (0, 1)}
    buttons = "".join(
        f'<button type="button" class="mj-day" data-index="{first_index[d]}" aria-pressed="{str(d in on).lower()}"'
        f' title="누르면 {label} 시간으로 이동해요">{label} {format_short_date(now + timedelta(days=d))}</button>'
        for d, label in ((0, "오늘"), (1, "내일"))
    )
    script = """
<script>
document.querySelectorAll('.mj-day').forEach(btn => {
  btn.onclick = () => {
    const root = document.querySelector('.st-key-weather_pick');
    const cell = root && root.querySelectorAll('button')[Number(btn.dataset.index)];
    const strip = cell && cell.parentElement;
    if (!strip) return;
    const smooth = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    strip.scrollTo({left: cell.offsetLeft - 8, behavior: smooth ? 'smooth' : 'auto'});
  };
});
</script>"""
    st.html(
        f'<p class="mj-days-label">날짜</p><div class="mj-days" role="group" aria-label="날짜">{buttons}</div>{script}',
        unsafe_allow_javascript=True,
    )


# 전용 스크롤바: 손잡이 길이·위치는 보이는 범위, 막대를 누르거나 손잡이를 끌거나 좌우 화살표로 이동
SCROLLBAR_SCRIPT = """
<script>
(() => {
  // 화면이 다시 그려져도 계속 동작하도록 문서에 한 번만 연결하고, 매번 요소를 다시 찾는다
  const parts = () => {
    const first = document.querySelector('.st-key-weather_pick button');
    const strip = first && first.parentElement;
    const bar = document.querySelector('.mj-scroll');
    return strip && bar ? {strip, bar, thumb: bar.querySelector('.mj-scroll-thumb')} : null;
  };
  const max = strip => Math.max(strip.scrollWidth - strip.clientWidth, 0);
  const sync = () => {
    const p = parts();
    if (!p) return;
    const ratio = p.strip.clientWidth / p.strip.scrollWidth;
    p.bar.hidden = ratio >= 1;
    const w = Math.max(ratio * 100, 8);
    const pos = max(p.strip) ? p.strip.scrollLeft / max(p.strip) : 0;
    p.thumb.style.width = w + '%';
    p.thumb.style.left = pos * (100 - w) + '%';
    p.bar.setAttribute('aria-valuenow', String(Math.round(pos * 100)));
  };
  const jump = clientX => {
    const p = parts();
    if (!p) return;
    const r = p.bar.getBoundingClientRect();
    const w = p.thumb.getBoundingClientRect().width;
    const pos = Math.min(Math.max((clientX - r.left - w / 2) / (r.width - w), 0), 1);
    p.strip.scrollLeft = pos * max(p.strip);
    sync();
  };
  window.__mjScrollSync = sync;
  if (!window.__mjScrollBound) {
    window.__mjScrollBound = true;
    let dragging = false;
    document.addEventListener('pointerdown', e => {
      if (!e.target.closest('.mj-scroll')) return;
      dragging = true;
      e.preventDefault();
      jump(e.clientX);
    });
    document.addEventListener('pointermove', e => { if (dragging) jump(e.clientX); });
    document.addEventListener('pointerup', () => { dragging = false; });
    document.addEventListener('keydown', e => {
      if (!e.target.closest || !e.target.closest('.mj-scroll')) return;
      const p = parts();
      if (!p) return;
      if (e.key === 'ArrowRight') { p.strip.scrollLeft += 120; e.preventDefault(); }
      if (e.key === 'ArrowLeft') { p.strip.scrollLeft -= 120; e.preventDefault(); }
      sync();
    });
    // scroll 이벤트는 위로 전달되지 않으므로 캡처 단계에서 받는다
    document.addEventListener('scroll', () => window.__mjScrollSync(), true);
    window.addEventListener('resize', () => window.__mjScrollSync());
    new MutationObserver(() => window.requestAnimationFrame(() => window.__mjScrollSync()))
      .observe(document.body, {childList: true, subtree: true});
  }
  setTimeout(sync, 200);
  setTimeout(sync, 800);
})();
</script>"""


def _render_hours(cells: list[HourCell], now: datetime, confirmed: list[int], sky_rules: list[dict[str, Any]]) -> None:
    """오늘 0시부터 내일 21시까지 48시간 가로 스크롤. 여러 칸을 고른 뒤 확정하면 추천에 반영된다."""
    key = "weather_pick"
    tomorrow_index = next(i for i, c in enumerate(cells) if day_of(c, now) == 1)
    picked = st.pills(
        "외출할 시간 (여러 개 고를 수 있어요, 3시간 간격, 내일까지)",
        list(range(len(cells))),
        selection_mode="multi",
        default=confirmed,
        format_func=lambda i: cell_label(cells[i], sky_rules, tomorrow_start=i == tomorrow_index),
        key=key,
        wrap=False,
        width="stretch",
    )
    # 지난 칸은 흐리게, 지금 칸은 뒤에 은은한 빛, 내일이 시작되는 칸 앞에 구분선
    rules = [
        f".st-key-{key} button:nth-of-type({tomorrow_index + 1}) {{"
        " margin-left: 10px; box-shadow: -6px 0 0 -3px var(--mj-on-border); }"
    ]
    past = sum(1 for c in cells if c.is_past)
    if past:
        rules.append(f".st-key-{key} button:nth-of-type(-n+{past}) {{ opacity: 0.5; }}")
    now_index = next((i for i, c in enumerate(cells) if c.is_now), None)
    if now_index is not None:
        rules.append(
            f".st-key-{key} button:nth-of-type({now_index + 1}) {{"
            " box-shadow: 0 0 24px 6px rgba(255, 255, 255, 0.35); }"
        )
    # 처음 보일 때 첫 번째로 고른 칸이 가운데 오도록 가로 스크롤을 옮긴다
    first = min(confirmed) if confirmed else (now_index or 0)
    script = f"""
<script>
setTimeout(() => {{
  const root = document.querySelector('.st-key-{key}');
  const btns = root ? root.querySelectorAll('button') : [];
  const btn = btns[{first}];
  const strip = btn && btn.parentElement;
  if (strip) strip.scrollLeft = btn.offsetLeft - strip.clientWidth / 2 + btn.clientWidth / 2;
}}, 150);
</script>"""
    scrollbar = (
        '<div class="mj-scroll" role="scrollbar" aria-label="외출 시간 가로 스크롤" aria-orientation="horizontal"'
        ' aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" tabindex="0"><div class="mj-scroll-thumb"></div></div>'
    )
    st.html(f"<style>{''.join(rules)}</style>{scrollbar}{script}{SCROLLBAR_SCRIPT}", unsafe_allow_javascript=True)
    pending = sorted(picked) != sorted(confirmed)
    with st.container(horizontal=True, vertical_alignment="center", gap="small"):
        st.button(
            "외출 시간 확정",
            key="weather_confirm",
            icon=":material/schedule:",
            on_click=_confirm_outing,
            disabled=not picked or not pending,
        )
        st.button(
            "날씨 새로고침",
            key="weather_refresh",
            icon=":material/refresh:",
            help="OpenWeather에서 최신 날씨를 다시 불러와요. (평소엔 10분마다 새로 불러와요)",
            on_click=_refresh_weather,
        )
        if not picked:
            st.caption("외출할 시간을 하나 이상 골라 주세요.")
        elif pending:
            st.caption("고른 시간을 확정하면 추천이 바뀌어요.")
        else:
            st.caption(f"{outing_label(outing_cells(cells, confirmed)) or '고른 시간'} 외출 기준으로 추천했어요.")



def _render_recommendation(question: str, rec: Recommendation, sky: Sky) -> None:
    with st.container(key="weather_reco", gap="small"):
        st.caption(question)
        with st.container(key="weather_headline"):
            st.markdown(rec.headline)
        if rec.conditions:
            with st.container(key="weather_alert"):
                st.markdown(f":material/priority_high: {rec.conditions[0].headline}")
        st.markdown(
            f":material/{sky.icon}: {sky.label}, 가장 추울 때 체감 {round_half_up(rec.basis.feels_like)}°C"
            f" ({rec.temperature_range['label']} 구간)"
        )
        st.caption(rec.outfit.description)


def _text_on(color: str) -> str:
    """컬러칩 위 글자색: 밝은 칩엔 검정, 어두운 칩엔 흰색."""
    r, g, b = (int(color[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return "#1A1A1A" if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.55 else "#FFFFFF"


def _palette_gen() -> int:
    return st.session_state.get("weather_palette_gen", 0)


def _bump_palette_gen() -> None:
    """팔레트 위젯을 새 키로 다시 만들게 한다 (같은 색을 고르는 칸이 여러 곳이어도 값이 맞도록)."""
    st.session_state["weather_palette_gen"] = _palette_gen() + 1


def _store_color(widget_key: str, store_key: str) -> None:
    st.session_state[store_key] = st.session_state.get(widget_key) or "default"
    _bump_palette_gen()


def _render_palette(key: str, label: str, base_color: str, palette: list[dict[str, str]], where: str = "card") -> None:
    """컬러칩을 골라 옷이나 준비물의 색을 바꾼다. 칩마다 색 이름을 함께 적어 색만으로 구분하지 않게 한다.
    고른 색은 key(위젯이 아닌 값)에 기억한다. 팔레트를 닫아 위젯이 사라져도 색이 남고,
    같은 아이템의 팔레트가 옷 카드·둘러보기에 함께 있어도 where로 위젯 키를 나눠 충돌하지 않는다."""
    options = [{"id": "default", "name": "기본", "color": base_color}, *palette]
    names = {o["id"]: o["name"] for o in options}
    widget_key = f"{key}__{where}{_palette_gen()}"
    st.pills(
        f"{label} 색상",
        [o["id"] for o in options],
        default=st.session_state.get(key, "default"),
        required=True,
        format_func=lambda i: names[i],
        key=widget_key,
        on_change=_store_color,
        args=(widget_key, key),
        label_visibility="collapsed",
    )
    rules = []
    for n, o in enumerate(options, 1):
        text = _text_on(o["color"])
        rules.append(
            f".st-key-weather_root .st-key-{widget_key} button:nth-of-type({n}) {{"
            f" background: {o['color']}; color: {text}; text-shadow: none; min-height: 32px; padding: 0 10px; }}"
            f".st-key-weather_root .st-key-{widget_key} button:nth-of-type({n}) p {{ color: {text}; font-size: 11px;"
            " font-family: 'Galmuri11', monospace; }"
        )
    rules.append(
        f".st-key-weather_root .st-key-{widget_key} button:is([aria-checked='true'], [aria-pressed='true']) {{"
        " outline: 3px solid #FFFFFF; outline-offset: -3px; }"
    )
    st.html(f"<style>{''.join(rules)}</style>")


def _color_popover(key: str, label: str, base_color: str, palette: list[dict[str, str]], where: str) -> None:
    """둘러보기 카드의 색상 선택: 카드가 작아서 팝오버 안에 팔레트를 연다.
    where는 탭 이름 (얇은 셔츠처럼 상의·아우터 두 탭에 나오는 아이템도 위젯 키가 겹치지 않게)."""
    with st.popover("색상", icon=":material/palette:", width="stretch"):
        st.caption(f"{label} 색상")
        _render_palette(key, label, base_color, palette, where=f"pick_{where}")


def _render_item(
    key: str, label: str, item: Item | None, color: dict[str, str] | None, palette, gender: str = "female"
) -> None:
    with st.container(key=f"weather_item_{key}", height="stretch"):
        image = image_file(item.image_path) if item else None
        if image:
            st.image(str(image), width=96, alt=item.name)
        elif item is not None and item.pixel:
            st.image(item_icon(item, color["color"] if color else None, gender), width=56, alt=item.name)
        st.caption(label)
        st.markdown(f"**{item.name if item else NO_OUTER_LABEL}**")
        st.caption(item.reason if item else NO_OUTER_REASON)
        if item is None or not item.pixel:
            return
        if color and color["id"] != "default":
            st.caption(f"고른 색: {color['name']}")
        if st.toggle("색상 선택 팔레트", key=f"weather_palette_{key}"):
            _render_palette(color_key(item), item.name, item.pixel["color"], palette, where="card")


def _choose_item(style: str, category: str, candidate: Candidate) -> None:
    st.session_state[choice_key(style, category)] = candidate.item_id
    if category in ("top", "bottom"):  # 상의·하의를 고르면 원피스·세트는 벗는다
        st.session_state.pop(choice_key(style, DRESS), None)
    name = candidate.item.name if candidate.item else (NO_DRESS_LABEL if category == DRESS else NO_OUTER_LABEL)
    st.toast(f"{name}(으)로 바꿨어요.", icon=":material/checkroom:")
    if category == "outer":  # 새 아우터와 겹쳐 입게 되는 준비물은 뺀다 (예: 가디건 + 여벌 가디건)
        names = load_json("rules.json")["supplies"]
        for kind in blocked_kinds(candidate.item):
            if st.session_state.get(pack_key(kind)):
                st.session_state[pack_key(kind)] = False
                st.toast(f"{names[kind]['name']}는 뺐어요. {LAYER_NAMES[SUPPLY_LAYER[kind]]}는 하나만 입어요.", icon=":material/undo:")


def _render_candidates(
    style: str,
    category: str,
    label: str,
    candidates: list[Candidate],
    worn: Item | None,
    recommended: Item | None,
    palette: list[dict[str, str]],
    gender: str = "female",
) -> None:
    """한 카테고리의 후보 카드. 지금 입은 것은 '입는 중', 날씨 추천은 '추천' 표시. 카드마다 색상 선택."""
    worn_id = worn.item_id if worn else NO_ITEM_ID
    rec_id = recommended.item_id if recommended else NO_ITEM_ID
    # st.columns는 좁은 화면에서 한 칸씩 쌓이므로, 고정 너비 카드를 줄바꿈되는 가로 줄에 놓는다 (휴대폰 2칸)
    with st.container(horizontal=True, gap="small"):
        for c in candidates:
            with st.container(key=f"weather_cand_{category}_{c.item_id}", width=164):
                if c.item is not None:
                    chosen = next((p["color"] for p in palette if p["id"] == st.session_state.get(color_key(c.item))), None)
                    st.image(item_icon(c.item, chosen, gender), width=40, alt=c.item.name)
                name = c.item.name if c.item else (NO_DRESS_LABEL if category == DRESS else NO_OUTER_LABEL)
                st.markdown(f"**{name}**" + (" :material/thumb_up: 추천" if c.item_id == rec_id else ""))
                st.caption(c.band.replace("~", r"\~"))  # 물결표 두 개가 취소선이 되지 않게
                is_worn = c.item_id == worn_id
                st.button(
                    "입는 중" if is_worn else "선택",
                    key=f"weather_choose_{category}_{c.item_id}",
                    icon=":material/check:" if is_worn else None,
                    type="primary" if is_worn else "secondary",
                    disabled=is_worn,
                    on_click=_choose_item,
                    args=(style, category, c),
                    width="stretch",
                    help=None if is_worn else f"{label}을(를) {name}(으)로 바꿔요",
                )
                if c.item is not None:
                    _color_popover(color_key(c.item), c.item.name, c.item.pixel["color"], palette, category)


def _pick_supply(kind: str, on: bool) -> None:
    """준비물을 챙기거나 뺀다. 챙기면 같은 묶음의 다른 것을 빼고, 방금 챙긴 것으로 기억해 미니미가 그 동작을 한다."""
    state = st.session_state
    names = load_json("rules.json")["supplies"]
    state[pack_key(kind)] = on
    if not on:
        st.toast(f"{names[kind]['name']} 챙기기를 취소했어요.", icon=":material/undo:")
        return
    swapped = [other for other in exclusive_with(kind) if state.get(pack_key(other))]
    for other in swapped:
        state[pack_key(other)] = False
    state["weather_last_pack"] = kind
    if swapped:
        st.toast(f"{', '.join(names[o]['name'] for o in swapped)} 대신 {names[kind]['name']}을(를) 챙겼어요.", icon=":material/swap_horiz:")
    else:
        st.toast(f"{names[kind]['name']} 챙겼어요.", icon=":material/backpack:")


def _on_pack_toggle(kind: str) -> None:
    """'챙길 것' 카드의 토글: 위젯이 값을 이미 바꿨으니 같은 규칙만 적용한다."""
    _pick_supply(kind, bool(st.session_state.get(pack_key(kind))))


def _render_other_tab(
    supplies: list[Supply],
    recommended: set[str],
    packed: set[str],
    blocked: Mapping[str, str],
    supply_colors: Mapping[str, Mapping[str, str]],
    palette: list[dict[str, str]],
) -> None:
    """기타: 우산·마스크·선글라스·안경 같은 준비물과 소품을 모두 보여 주고, 챙기기·빼기와 색을 고른다."""
    st.caption("안경과 선글라스, 모자, 우산과 양산은 하나만 챙길 수 있어요. 겹쳐 입는 가디건류·자켓류도 하나씩이에요.")
    with st.container(horizontal=True, gap="small"):
        for supply in supplies:
            kind = supply.kind
            on = kind in packed
            with st.container(key=f"weather_other_{'on' if on else 'off'}_{kind}", width=164):
                color = supply_colors.get(kind)
                st.image(render_supply(kind, supply.name, color["color"] if color else None), width=40, alt=supply.name)
                st.markdown(f"**{supply.name}**" + (" :material/thumb_up: 추천" if kind in recommended else ""))
                st.caption(blocked.get(kind) or supply.reason)
                st.button(
                    "빼기" if on else "챙기기",
                    key=f"weather_other_pick_{kind}",
                    icon=":material/undo:" if on else ":material/backpack:",
                    type="primary" if on else "secondary",
                    disabled=kind in blocked,
                    on_click=_pick_supply,
                    args=(kind, not on),
                    width="stretch",
                )
                _color_popover(supply_color_key(kind), supply.name, PROP_COLORS[kind], palette, "other")


def _render_closet(
    outfit: Outfit,
    recommended: Outfit,
    candidates: Mapping[str, list[Candidate]],
    styles: dict[str, dict[str, str]],
    colors: dict[str, dict[str, str]],
    palette,
    other: Mapping[str, Any] | None = None,
    gender: str = "female",
) -> None:
    """옷 고르기: 스타일 선택 → 지금 입은 상의·하의·아우터(색상 팔레트) → 스타일 안 아이템과 기타 소품을 하나씩 '선택'.
    other: '기타' 탭에 넘길 준비물 정보 (supplies, recommended, packed, blocked, supply_colors)."""
    st.segmented_control(
        "스타일",
        list(styles),
        required=True,
        format_func=lambda i: styles[i]["name"],
        key="weather_style",
        width="stretch",
    )
    st.caption(styles[outfit.style]["summary"])
    # 완성 룩 이미지는 실제 파일이 있을 때만 보여준다 (없으면 미니미가 그 역할)
    image = image_file(recommended.image_path)
    if image and outfit == recommended:
        st.image(str(image), width="stretch", alt=f"{styles[outfit.style]['name']} 완성 룩")
    shown = worn_categories(outfit)
    cols = st.columns(len(shown), gap="small")
    for col, (category, label) in zip(cols, shown):
        with col:
            _render_item(category, label, getattr(outfit, category), colors.get(category), palette, gender)
    with st.container(key="weather_choices", gap="small"):
        style_name = styles[outfit.style]["name"]
        # 되돌릴 것: 고른 아이템, 그리고 이 스타일 아이템에 고른 색
        color_keys = [color_key(c.item) for cs in candidates.values() for c in cs if c.item is not None]
        changed = outfit != recommended or any(v["id"] != "default" for v in colors.values())
        browse = st.session_state.get("weather_browse", False)
        # 두 버튼을 같은 모양으로 왼쪽부터 나란히 (좁은 화면에서는 줄바꿈된다)
        with st.container(
            key="weather_choice_actions", horizontal=True, horizontal_alignment="left", vertical_alignment="center",
            gap="small", wrap=False,
        ):
            st.button(
                "둘러보기 닫기" if browse else "다른 아이템 둘러보기",
                key="weather_browse_button",
                icon=":material/expand_less:" if browse else ":material/checkroom:",
                help="같은 스타일의 다른 상의·하의·아우터와 기타 소품을 보고 골라요",
                on_click=_toggle_browse,
            )
            st.button(
                "추천 코디로 되돌리기",
                key="weather_choice_reset",
                icon=":material/restart_alt:",
                disabled=not changed,
                help="고른 아이템과 색을 날씨 추천대로 돌려요",
                on_click=_reset_choices,
                args=(outfit.style, color_keys),
            )
        if not browse:
            return
        st.caption(f"{style_name} 스타일 아이템이에요. 날씨 추천에서 시작해, 마음에 드는 아이템을 골라 조합해 보세요.")
        tabs = st.tabs([label for _, label in PICK_CATEGORIES] + ["기타"])
        for tab, (category, label) in zip(tabs, PICK_CATEGORIES):
            with tab:
                _render_candidates(
                    outfit.style, category, label, list(candidates.get(category, [])),
                    getattr(outfit, category), getattr(recommended, category), palette, gender,
                )
        if other is not None:
            with tabs[-1]:
                _render_other_tab(palette=palette, **other)


def _toggle_browse() -> None:
    st.session_state["weather_browse"] = not st.session_state.get("weather_browse", False)


def _reset_choices(style: str, color_keys: list[str]) -> None:
    for category, _ in PICK_CATEGORIES:
        st.session_state.pop(choice_key(style, category), None)
    for key in color_keys:  # 고른 색(위젯 밖 값)을 지우고 팔레트 위젯을 새로 만든다
        st.session_state.pop(key, None)
    _bump_palette_gen()
    st.toast("날씨 추천 코디로 되돌렸어요.", icon=":material/restart_alt:")


def _render_basis(
    chosen: list[HourCell], rec: Recommendation, temp_swing: float | None, sky_rules, air: list[AirReading]
) -> None:
    with st.expander("날씨 및 추천 근거"):
        lines = [f"- **{outing_basis_text(chosen)}**"]
        for c in chosen:
            s = c.snapshot
            pop = _fmt(None if s.pop is None else s.pop * 100, "%")
            lines.append(
                f"- {s.time:%H:%M} {sky_of(s, sky_rules).label}, 기온 {round_half_up(s.temp)}°C, "
                f"체감 {s.feels_like:.1f}°C, 강수확률 {pop}, 바람 {_fmt(s.wind_speed, 'm/s', 1)}"
            )
        lines.append(
            f"- 옷은 가장 추운 {rec.basis.time:%H:%M}(체감 {rec.basis.feels_like:.1f}°C) 기준 → "
            f"**{rec.temperature_range['label']}** 구간"
        )
        lines.append(f"- 기온 차 {_fmt(temp_swing, '°C')}")
        if air:
            pm10 = max((r.pm10 for r in air if r.pm10 is not None), default=None)
            pm25 = max((r.pm25 for r in air if r.pm25 is not None), default=None)
            lines.append(f"- 미세먼지 최대 {_fmt(pm10, '㎍/㎥')}, 초미세먼지 최대 {_fmt(pm25, '㎍/㎥')} (OpenWeather 대기질 예보)")
        else:
            lines.append("- 미세먼지: 예보를 불러오지 못해 마스크 추천에서 뺐어요")
        st.markdown("\n".join(lines))


def _render_supplies(
    supplies: list[Supply],
    packed: set[str],
    supply_colors: Mapping[str, Mapping[str, str]],
    palette,
    blocked: Mapping[str, str] | None = None,
) -> None:
    """챙길 것: 옷 카드처럼 아이콘, '챙기기' 토글, 색상 선택 팔레트. 챙긴 것만 미니미가 고른 색으로 들거나 쓴다."""
    with st.container(key="weather_tips"):
        st.markdown("**챙길 것**")
        if not supplies:
            st.caption("따로 챙길 준비물은 없어요.")
            return
        done = sum(1 for s in supplies if s.kind in packed)
        st.caption(f"추천 {len(supplies)}개 중 {done}개 챙겼어요.")
        for row in range(0, len(supplies), 3):
            cols = st.columns(3, gap="small")
            for col, supply in zip(cols, supplies[row : row + 3]):
                with col, st.container(key=f"weather_supply_{supply.kind}", height="stretch"):
                    color = supply_colors.get(supply.kind)
                    st.image(
                        render_supply(supply.kind, supply.name, color["color"] if color else None), width=48, alt=supply.name
                    )
                    st.markdown(f"**{supply.name}**")
                    st.caption(supply.reason)
                    if color:
                        st.caption(f"고른 색: {color['name']}")
                    reason = (blocked or {}).get(supply.kind)
                    if reason:
                        st.caption(reason)
                    st.toggle(
                        "챙기기", key=pack_key(supply.kind), disabled=bool(reason),
                        on_change=_on_pack_toggle, args=(supply.kind,),
                    )
                    if st.toggle("색상 선택 팔레트", key=f"weather_spalette_{supply.kind}"):
                        _render_palette(
                            supply_color_key(supply.kind), supply.name, PROP_COLORS[supply.kind], palette, where="card",
                        )


def saved_kinds(entry: dict[str, Any], outfit: Outfit | None, rules: dict[str, Any]) -> list[str]:
    """저장한 코디의 준비물. 예전 저장본(props·umbrella)은 날씨 준비물 + 코디 소품을 모두 챙긴 것으로 본다."""
    if "supplies" in entry:
        return [s["kind"] for s in entry["supplies"]]
    kinds = list(entry.get("props") or (["umbrella"] if entry.get("umbrella") else []))
    for accessory in outfit.accessories if outfit else []:
        kind = next((k for word, k in rules["accessory_supplies"] if word in accessory), None)
        if kind:
            kinds.append(kind)
    return kinds


def saved_look(entry: dict[str, Any], outfit: Outfit | None, rules: dict[str, Any]) -> Look | None:
    """저장한 장비 칸과 챙긴 준비물(색 포함)로 미니미를 다시 입힌다. 칸도 코디도 없으면 None."""
    slots = saved_slots(entry, outfit)
    if not any(s.get("item") for s in slots):
        return None
    prop_colors = {s["kind"]: s["color"] for s in entry.get("supplies") or [] if s.get("color")}
    saved_body = entry.get("body") or {}
    body = Body(**{k: saved_body[k] for k in BODY_FIELDS if isinstance(saved_body.get(k), str)})
    return look_from_slots(slots, saved_kinds(entry, outfit, rules), prop_colors, body)


def _saved_title(entry: dict[str, Any]) -> str:
    when = datetime.fromisoformat(entry["basis_time"])
    return f"{format_short_date(when)} {entry.get('outing') or f'{when:%H:%M}'}"


def saved_slots(entry: dict[str, Any], outfit: Outfit | None) -> list[dict[str, Any]]:
    """저장한 장비 칸. 예전 저장본(slots 없음)은 코디와 저장한 색으로 다시 만든다."""
    if entry.get("slots"):
        return entry["slots"]
    if outfit is None:
        return []
    colors = {k: {"id": "saved", **v} for k, v in (entry.get("colors") or {}).items()}
    return entry_slots(outfit, colors)


def _render_slot_strip(entry: dict[str, Any], outfit: Outfit | None) -> None:
    """옷장 카드용 작은 아이템 칸 줄: 장비 아이콘 + 가방 아이콘."""
    slots = [s for s in saved_slots(entry, outfit) if s["item"]]
    supplies = entry.get("supplies") or []
    if not slots and not supplies:
        return
    with st.container(key=f"weather_strip_{entry['id']}", horizontal=True, gap="small"):
        for slot in slots:
            st.image(_slot_icon(slot, _entry_gender(entry)), width=28, alt=slot["item"]["name"])
        for supply in supplies:
            st.image(render_supply(supply["kind"], supply["name"], supply.get("color")), width=28, alt=supply["name"])


def _render_tags(entry: dict[str, Any]) -> None:
    tags = entry.get("tags") or []
    if tags:
        st.html('<div class="mj-tags">' + "".join(f'<span class="mj-tag">#{escape(t)}</span>' for t in tags) + "</div>")


def _saved_supply_names(entry: dict[str, Any]) -> str:
    return ", ".join(s["name"] for s in entry.get("supplies") or [])


def _remove_button(entry: dict[str, Any], **kwargs: Any) -> None:
    st.button(
        "옷장에서 빼기",
        key=f"weather_remove_{entry['id']}",
        on_click=remove_from_wardrobe,
        args=(entry["id"],),
        **kwargs,
    )


def _render_wardrobe(outfits: list[Outfit], rules: dict[str, Any]) -> None:
    """내 옷장: 리스트로 간단히 보거나, 미니미 썸네일로 본다."""
    entries = load_wardrobe()
    by_id = {o.outfit_id: o for o in outfits}
    with st.container(key="weather_wardrobe"):
        with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
            st.markdown(f"**내 옷장** ({len(entries)})")
            view = st.segmented_control(
                "보기",
                ["list", "grid"],
                default="grid",
                required=True,
                format_func=lambda v: {"list": ":material/view_list: 리스트", "grid": ":material/grid_view: 썸네일"}[v],
                key="weather_wardrobe_view",
                label_visibility="collapsed",
            )
        if not entries:
            st.caption("아직 저장한 코디가 없어요. 마음에 드는 코디를 옷장에 저장해 보세요.")
            return
        if view == "list":
            for e in entries:
                with st.container(
                    key=f"weather_row_{e['id']}", horizontal=True, vertical_alignment="center", gap="small"
                ):
                    with st.container(width="stretch", gap="small"):
                        st.markdown(f"**{e.get('name') or _saved_title(e)}**")
                        _render_tags(e)
                        _render_slot_strip(e, by_id.get(e.get("outfit_id")))
                        st.caption(
                            f"{_saved_title(e)}, {e['style_name']}, {e['city']}, {e['sky']} {round_half_up(e['temp'])}°, "
                            + " + ".join(i for i in e["items"] if i)
                            + (f", 챙길 것: {_saved_supply_names(e)}" if e.get("supplies") else "")
                        )
                    _remove_button(e, width="content")
            return
        for row in range(0, len(entries), 3):
            cols = st.columns(3, gap="small")
            for col, e in zip(cols, entries[row : row + 3]):
                with col, st.container(key=f"weather_saved_{e['id']}", height="stretch"):
                    outfit = by_id.get(e.get("outfit_id"))
                    look = saved_look(e, outfit, rules)
                    if look is not None:
                        alt = f"{e['style_name']} 미니미"
                        st.image(render_minimi(look, alt), width=56, alt=alt)
                    st.markdown(f"**{e.get('name') or _saved_title(e)}**")
                    _render_tags(e)
                    _render_slot_strip(e, outfit)
                    st.caption(f"{_saved_title(e)}, {e['city']}, {e['sky']} {round_half_up(e['temp'])}°, {e['style_name']}")
                    st.caption(" + ".join(i for i in e["items"] if i))
                    if e.get("supplies"):
                        st.caption(f"챙길 것: {_saved_supply_names(e)}")
                    _remove_button(e, width="stretch")


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
    st.html(page_css(st.session_state.get("weather_theme", DEFAULT_THEME), current_mode()))
    render_frame()  # 싸이월드 다이어리 외곽 프레임 (theme.py, MOIPJI 대표색)
    with st.container(key=f"{SERVICE_ROUTE}_root"):  # theme.py는 이 영역이 있을 때만 프레임을 입힌다
        cities = load_json("cities.json")
        profile = current_profile()
        if profile is None:  # 처음 들어왔으면 내 정보부터 받는다
            _render_welcome(cities, load_json("outfits.json")["styles"])
            return
        st.session_state.pop("weather_profile_saved", None)
        _render_page(profile)


def _set_theme(theme: str) -> None:
    if st.session_state.get("weather_theme", DEFAULT_THEME) != theme:
        st.html(page_css(theme, current_mode()))
    st.session_state["weather_theme"] = theme


def outing_day(chosen: list[HourCell], now: datetime) -> tuple[str, str]:
    """외출이 시작되는 날: ('today', '오늘') 또는 ('tomorrow', '내일')."""
    return ("tomorrow", "내일") if chosen and day_of(chosen[0], now) == 1 else ("today", "오늘")


def outing_date_label(chosen: list[HourCell], now: datetime) -> str:
    """히어로 날짜: 하루면 '10/22(목)', 자정을 넘기면 '10/22(목)~10/23(금)'."""
    if not chosen:
        return format_short_date(now)
    first, last = chosen[0].time, chosen[-1].time
    if first.date() == last.date():
        return format_short_date(first)
    return f"{format_short_date(first)}~{format_short_date(last)}"


def outing_question(chosen: list[HourCell], slots: list[dict[str, Any]], now: datetime) -> str:
    day_id, day_label = outing_day(chosen, now)
    if len(chosen) == 1:
        return slot_for_hour(chosen[0].time.hour, slots)["question"][day_id]
    prefix = f"{day_label} " if day_id == "tomorrow" or chosen[-1].time.date() > chosen[0].time.date() else ""
    return f"{prefix}{outing_label(chosen)} 외출엔 뭐 입지?"


def _render_page(profile: Profile) -> None:
    rules = load_json("rules.json")
    catalog = load_json("outfits.json")
    outfits = load_outfits(catalog)
    gender = profile.gender
    styles = styles_for(catalog["styles"], gender)  # 여성: 러블리, 남성: 댄디
    body = body_for(profile, rules)
    slots = rules["time_slots"]

    city = _render_header(load_json("cities.json"), profile)

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
    air = load_air(city["lat"], city["lon"], data.tz)

    # 추천·히어로를 그리기 전에 계산해야 하므로, 확정한 외출 시간과 (아래에 있는) 스타일을 세션에서 먼저 읽는다
    cells = outing_timeline(data, now, max_minutes=rules["thresholds"]["slot_match_minutes"])
    if "weather_outing" not in st.session_state:
        st.session_state["weather_outing"] = [default_cell_index(cells)]
    confirmed = [i for i in st.session_state["weather_outing"] if isinstance(i, int) and 0 <= i < len(cells)]
    picked_now = st.session_state.get("weather_pick", confirmed)  # 날짜 버튼 표시용 (확정 전 선택 포함)
    # 스타일 위젯은 아래에 있지만 아직 그려지기 전이라 값을 맞춰 둘 수 있다 (성별이 바뀌면 없는 스타일일 수 있음)
    if st.session_state.get("weather_style") not in styles:
        st.session_state["weather_style"] = DEFAULT_STYLE
    style = st.session_state["weather_style"]

    chosen = outing_cells(cells, confirmed)  # 데이터가 있는 칸만
    rec = sky = look = entry = temp_swing = worn = None
    everything: list[Supply] = []
    blocked: dict[str, str] = {}
    candidates: dict[str, list[Candidate]] = {}
    colors: dict[str, dict[str, str]] = {}
    supply_colors: dict[str, dict[str, str]] = {}
    supplies: list[Supply] = []
    packed: set[str] = set()
    bubble: dict[str, Any] = {}
    if chosen:
        snaps = [c.snapshot for c in chosen]
        temp_swing = outing_swing(chosen)
        if temp_swing is None:  # 한 칸만 골랐으면 그날 일교차로
            temp_swing = daily_range(data, now, rules["thresholds"]["min_forecast_points"], day_of(chosen[0], now))
        rec = recommend(
            snaps, slot_for_hour(chosen[0].time.hour, slots)["id"], style, temp_swing, rules, outfits,
            outing_day(chosen, now)[1], air_window(chosen, air, rules["thresholds"]["slot_match_minutes"]), gender,
        )
        worst = severest(snaps)
        sky = sky_of(worst, rules["sky"])
        # 아래 '옷 고르기'에서 '선택'한 아이템·색, '챙길 것'의 토글·색을 세션에서 먼저 읽어 히어로에 반영한다
        extras = load_closet_extras(catalog, gender)
        candidates = {
            category: style_candidates(outfits, style, category, rules["temperature_ranges"], gender, extras)
            for category, _ in PICK_CATEGORIES
        }
        worn = compose_outfit(rec.outfit, candidates, st.session_state)
        colors = resolve_colors(worn, catalog["palette"], st.session_state)
        supplies = supplies_for(rec, rules)  # 추천 준비물 (챙길 것·말풍선)
        everything = all_supplies(supplies, rules)  # 기타 탭: 추천 + 직접 고를 수 있는 것 모두
        blocked = blocked_kinds(worn.outer)
        packed = {s.kind for s in everything if st.session_state.get(pack_key(s.kind)) and s.kind not in blocked}
        supply_colors = resolve_supply_colors(everything, catalog["palette"], st.session_state)
        look = look_for(
            worn, packed, {k: v["color"] for k, v in colors.items()}, {k: v["color"] for k, v in supply_colors.items()},
            body,
        )
        packed_supplies = [s for s in everything if s.kind in packed]
        entry = wardrobe_entry(
            chosen, city["name"], style, styles[style]["name"], replace(rec, outfit=worn), sky, colors,
            packed_supplies, supply_colors, body,
        )
        index = st.session_state.get("weather_bubble", 0)
        bubble = {"index": index, "lines": bubble_lines(supplies, index, rules)}
        scene = scene_of(worst)
    else:
        scene = scene_of(data.current)
    skipped_past = any(cells[i].is_past for i in confirmed)
    empty_reason = "지난 시간이라 데이터가 없어요." if skipped_past and not chosen else "아직 데이터가 없어요."

    # 1) 지역 선택 바로 아래: 날짜·외출할 시간(48시간)·확정·새로고침
    with st.container(key="weather_when", gap="small"):
        _render_days(cells, now, picked_now)
        _render_hours(cells, now, confirmed, rules["sky"])

    # 2) 옷 추천 카드
    if rec is not None:
        _render_recommendation(f"{profile.nickname}님, {outing_question(chosen, slots, now)}", rec, sky)
        if skipped_past:
            st.caption("지난 시간은 데이터가 없어서 빼고 추천했어요.")

    # 3) 히어로: 외출 날씨 + 미니미
    save_name = default_save_name(chosen, sky, styles[style]["name"]) if chosen else ""
    tag_options = wardrobe_tag_options(rules["wardrobe_tags"], load_wardrobe())
    _render_hero(
        city["name"], outing_date_label(chosen, now), chosen, sky, scene, look, entry, empty_reason,
        supplies, packed, bubble, save_name, tag_options,
    )

    # 4) 옷 고르기: 스타일 + 입은 옷(색상 선택 팔레트) + 스타일 안 아이템 선택, 챙길 것(색상 선택 팔레트)
    if rec is not None:
        other = {
            "supplies": everything, "recommended": {s.kind for s in supplies}, "packed": packed,
            "blocked": blocked, "supply_colors": supply_colors,
        }
        _render_closet(worn, rec.outfit, candidates, styles, colors, catalog["palette"], other, gender)
        _render_supplies(supplies, packed, supply_colors, catalog["palette"], blocked)
        _render_basis(chosen, rec, temp_swing, rules["sky"], air_window(chosen, air, rules["thresholds"]["slot_match_minutes"]))

    _render_wardrobe(outfits, rules)
    _render_footer(data, city["name"])


if __name__ == "__main__":
    st.set_page_config(page_title="MOIPJI", page_icon=":material/checkroom:", layout="centered")
    page()
