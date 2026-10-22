"""MOIPJI 로직 테스트. 실제 API는 호출하지 않는다.
실행: .venv/Scripts/python -m pytest tests (features/weather 폴더에서)
"""

from datetime import datetime, timedelta, timezone

import pytest
import requests

import weather as m

KST = timezone(timedelta(hours=9))
RULES = m.load_json("rules.json")
CATALOG = m.load_json("outfits.json")
OUTFITS = m.load_outfits(CATALOG)
SLOTS = RULES["time_slots"]


def ts(hour: int, minute: int = 0, day: int = 22) -> int:
    return int(datetime(2026, 10, day, hour, minute, tzinfo=KST).timestamp())


def current_raw(hour=10, minute=30, feels=13.6, **main):
    return {
        "dt": ts(hour, minute),
        "timezone": 32400,
        "main": {"temp": 15.2, "feels_like": feels, "humidity": 60, **main},
        "weather": [{"id": 800, "description": "맑음", "icon": "01d"}],
        "wind": {"speed": 3.1},
    }


def forecast_raw(start_hour=12, temps=(17, 18, 14, 9), pop=0.2):
    items = []
    for i in range(16):
        t = datetime(2026, 10, 22, start_hour, tzinfo=KST) + timedelta(hours=3 * i)
        temp = temps[i] if i < len(temps) else 10
        items.append(
            {
                "dt": int(t.timestamp()),
                "main": {"temp": temp, "feels_like": temp - 1},
                "pop": pop,
                "weather": [{"id": 500, "description": "비"}],
                "wind": {"speed": 4.0},
            }
        )
    return {"list": items, "city": {"timezone": 32400}}


# --- 체감온도 구간 --------------------------------------------------------


@pytest.mark.parametrize(
    "feels, code",
    [
        (35, "T01"), (28, "T01"), (27.5, "T01"), (27.4, "T02"), (23, "T02"),
        (22.5, "T02"), (22.4, "T03"), (17, "T03"), (16.4, "T04"), (12, "T04"),
        (11.5, "T04"), (11.4, "T05"), (6, "T05"), (5.5, "T05"), (5.4, "T06"),
        (5, "T06"), (-12, "T06"),
    ],
)
def test_temperature_range_is_continuous(feels, code):
    assert m.find_temperature_range(feels, RULES["temperature_ranges"])["code"] == code


@pytest.mark.parametrize("feels", [5.5, 11.5, 16.5, 22.5, 27.5])
def test_displayed_temperature_matches_range(feels):
    """화면에 보이는 정수 온도가 추천 구간 안에 있어야 한다."""
    shown = int(m._fmt(feels, ""))
    r = m.find_temperature_range(feels, RULES["temperature_ranges"])
    assert r["min"] is None or shown >= r["min"]
    assert m.find_temperature_range(shown, RULES["temperature_ranges"]) == r


# --- 데이터 파일 ----------------------------------------------------------


def test_every_style_and_range_has_one_outfit_with_matching_image_name():
    codes = [r["code"] for r in RULES["temperature_ranges"]]
    for style in (s["id"] for s in CATALOG["styles"]):
        for code in codes:
            outfit = m.find_outfit(OUTFITS, style, code)
            assert outfit.outfit_id == f"{style}_{code}_01"
            assert outfit.image_path == f"assets/outfits/{style}_{code}_01.webp"
    assert len(OUTFITS) == len(codes) * len(CATALOG["styles"])


def test_items_are_in_the_right_slot():
    for o in OUTFITS:
        assert o.top.category == "top" and o.bottom.category == "bottom"
        assert o.outer is None or o.outer.category == "outer"


def test_messages_exist_for_every_range_and_slot():
    for r in RULES["temperature_ranges"]:
        for slot in SLOTS:
            assert RULES["messages"][r["code"]][slot["id"]]


def test_missing_image_returns_none_so_placeholder_is_shown():
    assert m.image_file("assets/outfits/simple_T04_01.webp") is None
    assert m.image_file(None) is None


# --- 시간대 ---------------------------------------------------------------


@pytest.mark.parametrize(
    "hour, slot", [(0, "morning"), (7, "morning"), (11, "morning"), (12, "afternoon"), (16, "afternoon"), (17, "evening"), (23, "evening")]
)
def test_current_slot(hour, slot):
    assert m.current_slot_id(datetime(2026, 10, 22, hour, tzinfo=KST), SLOTS) == slot


def test_today_timeline_covers_whole_day():
    data = m.parse_weather(current_raw(10, 30), forecast_raw(12))
    now = datetime(2026, 10, 22, 10, 30, tzinfo=KST)
    cells = m.day_timeline(data, now)
    assert [c.time.hour for c in cells] == [0, 3, 6, 9, 12, 15, 18, 21]
    assert [c.is_past for c in cells] == [True, True, True, False, False, False, False, False]
    assert all(c.snapshot is None for c in cells[:3])  # 지난 시간: 무료 API는 과거를 주지 않음
    assert cells[3].is_now and cells[3].snapshot.is_current  # 9시 칸(9~12시)에 지금 10:30이 들어감
    assert cells[4].snapshot.time.hour == 12 and not cells[4].snapshot.is_current
    assert cells[7].snapshot.time.hour == 21
    assert m.default_cell_index(cells) == 3


def test_now_at_midnight_hour():
    data = m.parse_weather(current_raw(1, 10), forecast_raw(3))
    now = datetime(2026, 10, 22, 1, 10, tzinfo=KST)
    cells = m.day_timeline(data, now)
    assert cells[0].is_now and not any(c.is_past for c in cells)


@pytest.mark.parametrize("hour, slot", [(0, "morning"), (9, "morning"), (12, "afternoon"), (15, "afternoon"), (18, "evening"), (21, "evening")])
def test_slot_for_hour(hour, slot):
    assert m.slot_for_hour(hour, SLOTS)["id"] == slot


def test_forecast_times_are_local():
    data = m.parse_weather(current_raw(), forecast_raw(12))
    assert data.forecast[0].time.hour == 12
    assert data.forecast[0].time.utcoffset() == timedelta(hours=9)


# --- 일교차·조건 ----------------------------------------------------------


def test_daily_range_uses_today_forecast_and_current():
    data = m.parse_weather(current_raw(), forecast_raw(12, temps=(17, 18, 14, 9)))
    now = datetime(2026, 10, 22, 10, 30, tzinfo=KST)
    assert m.daily_range(data, now, 2) == pytest.approx(18 - 9)


def test_daily_range_skipped_when_forecast_is_short():
    data = m.parse_weather(current_raw(22, 30), forecast_raw(21))  # 오늘 남은 예보 1개
    now = datetime(2026, 10, 22, 22, 30, tzinfo=KST)
    assert m.daily_range(data, now, 2) is None


def snap(pop=None, wind=None):
    return m.Snapshot(datetime(2026, 10, 22, 13, tzinfo=KST), 15, 14, 50, wind, pop, "", None, None, False)


def test_conditions_thresholds_and_priority():
    assert m.detect_conditions(snap(pop=0.49, wind=7.9), 9.9, RULES) == []
    conds = m.detect_conditions(snap(pop=0.5, wind=8.0), 10.0, RULES)
    assert [c.id for c in conds] == ["rain", "daily_range", "wind"]
    assert conds[0].tip == "우산 챙기기 (강수확률 50%)"


def test_recommend_combines_style_and_weather():
    rec = m.recommend(snap(pop=0.7), "afternoon", "lovely", None, RULES, OUTFITS)
    assert rec.outfit.outfit_id == "lovely_T04_01"
    assert rec.headline == RULES["messages"]["T04"]["afternoon"]
    assert rec.conditions[0].id == "rain"


# --- 날씨 상태 아이콘 -----------------------------------------------------


def sky_snap(condition_id, icon):
    return m.Snapshot(datetime(2026, 10, 22, 13, tzinfo=KST), 15, 14, 50, 2, 0.1, "원문 설명", icon, condition_id, False)


@pytest.mark.parametrize(
    "cid, icon, label, expected_icon",
    [
        (800, "01d", "맑음", "sunny"),
        (800, "01n", "맑음", "clear_night"),
        (801, "02n", "구름 조금", "partly_cloudy_night"),
        (804, "04d", "흐림", "cloud"),
        (804, "04n", "흐림", "cloud"),
        (500, "10d", "비", "rainy"),
        (502, "10d", "강한 비", "rainy_heavy"),
        (601, "13d", "눈", "weather_snowy"),
        (211, "11d", "천둥번개", "thunderstorm"),
        (741, "50d", "안개", "foggy"),
    ],
)
def test_sky_label_and_icon(cid, icon, label, expected_icon):
    sky = m.sky_of(sky_snap(cid, icon), RULES["sky"])
    assert (sky.label, sky.icon) == (label, expected_icon)


def test_unknown_sky_falls_back_to_description():
    assert m.sky_of(sky_snap(999, "01d"), RULES["sky"]) == m.Sky("원문 설명", "thermostat")
    assert m.sky_of(sky_snap(None, None), RULES["sky"]).icon == "thermostat"


# --- 내일 ----------------------------------------------------------------


def test_tomorrow_timeline_is_all_forecast():
    data = m.parse_weather(current_raw(18, 30), forecast_raw(21))
    now = datetime(2026, 10, 22, 18, 30, tzinfo=KST)
    cells = m.day_timeline(data, now, day_offset=1)
    assert [c.time for c in cells][0] == datetime(2026, 10, 23, 0, tzinfo=KST)
    assert not any(c.is_now or c.is_past for c in cells)
    assert all(c.snapshot is not None and not c.snapshot.is_current for c in cells)
    assert cells[m.default_cell_index(cells)].time.hour == 9  # 내일은 오전 8시 이후 첫 칸


def test_tomorrow_without_forecast_has_no_data():
    data = m.parse_weather(current_raw(18, 30), None, "예보 오류")
    now = datetime(2026, 10, 22, 18, 30, tzinfo=KST)
    cells = m.day_timeline(data, now, day_offset=1)
    assert all(c.snapshot is None and not c.is_past for c in cells)  # '아직 데이터가 없어요'


def test_day_extremes():
    data = m.parse_weather(current_raw(18, 30), forecast_raw(21, temps=(10, 9, 8, 7, 12, 16, 18, 14, 11, 9)))
    now = datetime(2026, 10, 22, 18, 30, tzinfo=KST)
    assert m.day_extremes(data, now) == (10, 15.2)  # 오늘: 21시 예보 10°, 현재 15.2°
    assert m.day_extremes(data, now, 1) == (7, 18)


@pytest.mark.parametrize(
    "cid, icon, theme",
    [(800, "01d", "clear_day"), (801, "02n", "clear_night"), (804, "04d", "cloudy"), (500, "10n", "cloudy"), (None, None, "cloudy")],
)
def test_theme_by_weather(cid, icon, theme):
    assert m.theme_of(sky_snap(cid, icon)) == theme


def test_daily_range_for_tomorrow_uses_only_tomorrow():
    temps = (10, 9, 8, 7, 12, 16, 18, 14, 11, 9)  # 21시부터 3시간 간격: 오늘 1칸, 내일 8칸
    data = m.parse_weather(current_raw(18, 30), forecast_raw(21, temps=temps))
    now = datetime(2026, 10, 22, 18, 30, tzinfo=KST)
    assert m.daily_range(data, now, 2, day_offset=1) == pytest.approx(18 - 7)
    assert m.daily_range(data, now, 2) is None  # 오늘 남은 예보 1칸


def test_headline_says_tomorrow_on_tomorrow_tab():
    assert m.headline_for(RULES, "T01", "afternoon", "내일") == "내일은 반팔도 더울 각!"
    assert m.headline_for(RULES, "T01", "afternoon", "오늘") == "오늘은 반팔도 더울 각!"


def test_basis_text_shows_date_time_and_source():
    snap = m.Snapshot(datetime(2026, 10, 23, 9, tzinfo=KST), 10, 9, None, None, None, "", None, 800, False)
    assert m.basis_text(snap) == "10월 23일 금요일 09:00 예보 기준"


def test_fetched_at_is_kept():
    raw = current_raw()
    raw["_fetched_at"] = ts(18, 9)
    data = m.parse_weather(raw, forecast_raw())
    assert data.fetched_at == datetime(2026, 10, 22, 18, 9, tzinfo=KST)


# --- 파싱·조회 ------------------------------------------------------------


def test_current_without_feels_like_is_an_error_not_made_up():
    raw = current_raw()
    del raw["main"]["feels_like"]
    with pytest.raises(m.WeatherError):
        m.parse_weather(raw, forecast_raw())


def test_broken_forecast_entries_are_skipped_and_current_gets_pop():
    fc = forecast_raw(12, pop=0.6)
    fc["list"][1]["main"] = {}
    data = m.parse_weather(current_raw(), fc)
    assert len(data.forecast) == 15
    assert data.current.pop == 0.6


class FakeResponse:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self.ok = 200 <= status < 300
        self._body = body

    def json(self):
        if self._body is None:
            raise ValueError
        return self._body


@pytest.fixture
def api(monkeypatch):
    m.weather_fetch.clear()
    monkeypatch.setenv("OPENWEATHER_API_KEY", "secret-key")
    calls = []

    def install(handler):
        def fake_get(url, params, timeout):
            calls.append((url, params, timeout))
            return handler(url)

        monkeypatch.setattr(m.requests, "get", fake_get)
        return calls

    yield install
    m.weather_fetch.clear()


def test_fetch_sends_metric_korean_with_timeout_and_caches(api):
    calls = api(lambda url: FakeResponse(200, current_raw() if url.endswith("/weather") else forecast_raw()))
    m.load_weather(37.57, 126.98)
    m.load_weather(37.57, 126.98)
    assert len(calls) == 2  # weather + forecast 한 번씩, 두 번째는 캐시
    url, params, timeout = calls[0]
    assert params["units"] == "metric" and params["lang"] == "kr" and timeout == 5


@pytest.mark.parametrize("status", [401, 429, 500])
def test_http_errors_become_friendly_messages_without_key(api, status):
    api(lambda url: FakeResponse(status))
    with pytest.raises(m.WeatherError) as e:
        m.load_weather(37.57, 126.98)
    assert "secret-key" not in str(e.value)


def test_timeout_is_reported(api):
    def boom(url):
        raise requests.Timeout("https://api...appid=secret-key")

    api(boom)
    with pytest.raises(m.WeatherError) as e:
        m.load_weather(37.57, 126.98)
    assert "secret-key" not in str(e.value)


def test_missing_key(monkeypatch):
    m.weather_fetch.clear()
    for name in m.API_KEY_NAMES:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(m.WeatherError, match="API 키"):
        m.load_weather(37.57, 126.98)


def test_forecast_failure_keeps_current_weather(api):
    api(lambda url: FakeResponse(200, current_raw()) if url.endswith("/weather") else FakeResponse(500))
    data = m.load_weather(37.57, 126.98)
    assert data.forecast == [] and data.forecast_error


def test_get_weather_contract(api):
    api(lambda url: FakeResponse(200, current_raw() if url.endswith("/weather") else forecast_raw()))
    w = m.get_weather(37.56651, 126.97801)
    assert set(w) == {"temp", "feels_like", "precip", "min", "max", "hourly"}
    assert set(w["precip"]) == {"type", "probability"}
    assert len(w["hourly"]) == 8
