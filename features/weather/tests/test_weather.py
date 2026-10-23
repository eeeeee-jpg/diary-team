"""MOIPJI 로직 테스트. 실제 API는 호출하지 않는다.
실행: .venv/Scripts/python -m pytest tests (features/weather 폴더에서)
"""

from datetime import datetime, timedelta, timezone

import pytest
import requests

import weather as m
from minimi import SUPPLY_KINDS

KST = timezone(timedelta(hours=9))
RULES = m.load_json("rules.json")
CATALOG = m.load_json("outfits.json")
OUTFITS = m.load_outfits(CATALOG)
SLOTS = RULES["time_slots"]
PALETTE = CATALOG["palette"]


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


def snap(pop=None, wind=None, feels=14, hour=13, cid=None, icon=None):
    return m.Snapshot(datetime(2026, 10, 22, hour, tzinfo=KST), feels + 1, feels, 50, wind, pop, "", icon, cid, False)


def sky_snap(condition_id, icon):
    return m.Snapshot(datetime(2026, 10, 22, 13, tzinfo=KST), 15, 14, 50, 2, 0.1, "원문 설명", icon, condition_id, False)


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


def test_every_item_has_pixel_spec():
    for item_id, item in CATALOG["items"].items():
        px = item["pixel"]
        assert px["color"].startswith("#"), item_id
        if item["category"] == "dress":  # 원피스·세트: 위·아래 모양
            assert px["top"]["shape"] and px["bottom"]["shape"], item_id
        else:
            assert px["shape"], item_id


def test_every_condition_and_accessory_has_a_supply():
    kinds = set(RULES["supplies"])
    assert all(c["supply"] in kinds for c in RULES["conditions"])
    for accessory in {a for o in OUTFITS for a in o.accessories}:
        assert any(word in accessory for word, _ in RULES["accessory_supplies"]), accessory
    assert {k for _, k in RULES["accessory_supplies"]} <= kinds
    assert kinds <= set(SUPPLY_KINDS)


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


# --- 일교차·조건·추천 -----------------------------------------------------


def test_daily_range_uses_today_forecast_and_current():
    data = m.parse_weather(current_raw(), forecast_raw(12, temps=(17, 18, 14, 9)))
    now = datetime(2026, 10, 22, 10, 30, tzinfo=KST)
    assert m.daily_range(data, now, 2) == pytest.approx(18 - 9)


def test_daily_range_skipped_when_forecast_is_short():
    data = m.parse_weather(current_raw(22, 30), forecast_raw(21))  # 오늘 남은 예보 1개
    now = datetime(2026, 10, 22, 22, 30, tzinfo=KST)
    assert m.daily_range(data, now, 2) is None


def test_conditions_thresholds_and_priority():
    assert m.detect_conditions([snap(pop=0.49, wind=7.9)], 9.9, RULES) == []
    conds = m.detect_conditions([snap(pop=0.5, wind=8.0)], 10.0, RULES)
    assert [c.id for c in conds] == ["rain", "daily_range", "wind"]
    assert conds[0].tip == "우산 챙기기 (강수확률 50%)"
    assert [c.supply for c in conds] == ["umbrella", "extra_layer", "windbreaker"]


def test_conditions_use_the_whole_outing():
    """비는 한 칸만 와도, 바람은 가장 셀 때 기준."""
    conds = m.detect_conditions([snap(pop=0.1, wind=3), snap(pop=0.8, wind=9, hour=18)], None, RULES)
    assert [c.id for c in conds] == ["rain", "wind"]
    assert conds[0].tip == "우산 챙기기 (강수확률 80%)"


@pytest.mark.parametrize(
    "feels, expected, supply",
    [(0, "cold", "hotpack"), (0.4, None, None), (-5, "cold", "hotpack"), (28, "hot", "water"), (27.4, None, None)],
)
def test_hotpack_and_water(feels, expected, supply):
    conds = m.detect_conditions([snap(feels=feels)], None, RULES)
    ids = [c.id for c in conds]
    assert (expected in ids) if expected else not {"cold", "hot"} & set(ids)
    if supply:
        assert next(c for c in conds if c.id == expected).supply == supply


def test_sunny_day_gets_sunglasses_and_hot_sunny_day_gets_parasol():
    mild = m.detect_conditions([snap(feels=20, cid=800, icon="01d")], None, RULES)
    assert [c.id for c in mild] == ["sunny"] and mild[0].tip == "선글라스 챙기기 (햇빛 쨍쨍)"
    hot = m.detect_conditions([snap(feels=29, cid=800, icon="01d")], None, RULES)
    assert [c.id for c in hot] == ["hot", "parasol", "sunny"]
    night = m.detect_conditions([snap(feels=20, cid=800, icon="01n")], None, RULES)
    assert night == []  # 밤에는 선글라스 없음


def test_recommend_combines_style_and_weather():
    rec = m.recommend([snap(pop=0.7)], "afternoon", "lovely", None, RULES, OUTFITS)
    assert rec.outfit.outfit_id == "lovely_T04_01"
    assert rec.headline == RULES["messages"]["T04"]["afternoon"]
    assert rec.conditions[0].id == "rain"


def test_outfit_follows_the_coldest_moment():
    rec = m.recommend([snap(feels=18, hour=12), snap(feels=8, hour=21)], "afternoon", "simple", 10, RULES, OUTFITS)
    assert rec.basis.time.hour == 21 and rec.outfit.temperature_code == "T05"


# --- 외출 시간 ------------------------------------------------------------


def test_outing_cells_skip_cells_without_data():
    data = m.parse_weather(current_raw(10, 30), forecast_raw(12))
    cells = m.day_timeline(data, datetime(2026, 10, 22, 10, 30, tzinfo=KST))
    chosen = m.outing_cells(cells, [6, 0, 3, 4, 4])  # 0시는 지난 시간
    assert [c.time.hour for c in chosen] == [9, 12, 18]


@pytest.mark.parametrize(
    "hours, label", [([9], "9시"), ([9, 12, 15], "9시~15시"), ([9, 18], "9시, 18시"), ([18, 21], "18시~21시")]
)
def test_outing_label(hours, label):
    cells = [m.HourCell(datetime(2026, 10, 22, h, tzinfo=KST), snap(hour=h), False, False) for h in hours]
    assert m.outing_label(cells) == label


def test_outing_label_says_now_for_current_cell():
    now_cell = m.HourCell(datetime(2026, 10, 22, 18, tzinfo=KST), snap(hour=18), True, False)
    later = m.HourCell(datetime(2026, 10, 22, 21, tzinfo=KST), snap(hour=21), False, False)
    assert m.outing_label([now_cell]) == "지금"
    assert m.outing_label([now_cell, later]) == "지금~21시"


def test_outing_swing_and_severest():
    a = m.HourCell(datetime(2026, 10, 22, 9, tzinfo=KST), snap(feels=8, hour=9, cid=800, icon="01d"), False, False)
    b = m.HourCell(datetime(2026, 10, 22, 15, tzinfo=KST), snap(feels=19, hour=15, cid=500, icon="10d"), False, False)
    assert m.outing_swing([a]) is None
    assert m.outing_swing([a, b]) == pytest.approx(11)
    assert m.severest([a.snapshot, b.snapshot]) is b.snapshot


# --- 날씨 상태 아이콘·테마 ------------------------------------------------


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


@pytest.mark.parametrize(
    "cid, icon, theme",
    [(800, "01d", "clear_day"), (801, "02n", "clear_night"), (804, "04d", "cloudy"), (500, "10n", "cloudy"), (None, None, "cloudy")],
)
def test_theme_by_weather(cid, icon, theme):
    assert m.theme_of(sky_snap(cid, icon)) == theme


@pytest.mark.parametrize(
    "cid, icon, scene",
    [(800, "01d", "clear_day"), (800, "01n", "clear_night"), (804, "04d", "cloudy"), (501, "10d", "rain"), (601, "13d", "snow"), (211, "11d", "rain")],
)
def test_scene_by_weather(cid, icon, scene):
    assert m.scene_of(sky_snap(cid, icon)) == scene


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
    s = m.Snapshot(datetime(2026, 10, 23, 9, tzinfo=KST), 10, 9, None, None, None, "", None, 800, False)
    assert m.basis_text(s) == "10월 23일 금요일 09:00 예보 기준"


def test_fetched_at_is_kept():
    raw = current_raw()
    raw["_fetched_at"] = ts(18, 9)
    data = m.parse_weather(raw, forecast_raw())
    assert data.fetched_at == datetime(2026, 10, 22, 18, 9, tzinfo=KST)


# --- 준비물·말풍선 --------------------------------------------------------


def test_supplies_from_weather_then_outfit_accessories():
    s = [snap(feels=30, cid=800, icon="01d"), snap(feels=30, pop=0.9, hour=16, cid=500, icon="10d")]
    rec = m.recommend(s, "afternoon", "simple", None, RULES, OUTFITS)
    kinds = [x.kind for x in m.supplies_for(rec, RULES)]
    assert kinds[:2] == ["umbrella", "water"] and {"parasol", "sunglasses"} <= set(kinds)
    cold = m.recommend([snap(feels=-3)], "morning", "simple", None, RULES, OUTFITS)  # 목도리·장갑 코디
    supplies = m.supplies_for(cold, RULES)
    assert [x.kind for x in supplies] == ["hotpack", "earmuffs", "scarf", "gloves"]
    assert supplies[0].reason == "핫팩 챙기기 (최저 체감 -3°C)"
    assert supplies[2].name == "목도리" and all("{name}" not in line for line in supplies[2].lines)
    assert any("목도리" in line for line in supplies[2].lines)


def test_accessory_name_is_kept_for_variants():
    outfit = m.find_outfit(OUTFITS, "modern", "T06")  # 캐시미어 머플러, 가죽 장갑
    rec = m.Recommendation(outfit, {}, "", [], snap())
    names = {x.kind: x.name for x in m.supplies_for(rec, RULES)}
    assert names == {"scarf": "캐시미어 머플러", "gloves": "가죽 장갑"}


@pytest.mark.parametrize(
    "style, code, hat", [("casual", "T05", "beanie"), ("street", "T01", "bucket"), ("lovely", "T06", "earmuffs"), ("casual", "T01", "cap")]
)
def test_hats_come_from_packed_accessories(style, code, hat):
    outfit = m.find_outfit(OUTFITS, style, code)
    rec = m.Recommendation(outfit, {}, "", [], snap())
    kinds = [x.kind for x in m.supplies_for(rec, RULES)]
    assert hat in kinds
    if hat == "earmuffs":  # 귀마개는 모자와 따로 (비니 위에도 쓴다)
        assert m.look_for(outfit, kinds).earmuffs and not m.look_for(outfit).earmuffs
    else:
        assert m.look_for(outfit, kinds).hat == hat
    assert m.look_for(outfit).hat is None


def test_look_wears_only_packed_supplies():
    outfit = m.find_outfit(OUTFITS, "simple", "T06")  # 터틀넥 + 기모 슬랙스 + 롱패딩, 목도리·장갑
    bare = m.look_for(outfit)
    assert not bare.scarf and not bare.mittens and bare.props == ()  # 챙기기 전
    look = m.look_for(outfit, {"umbrella", "hotpack", "scarf", "gloves"})
    assert look.top.color == outfit.top.pixel["color"]
    assert look.bottom.shape == outfit.bottom.pixel["shape"]
    assert look.outer.shape == "padding_long"
    assert look.scarf and look.mittens and look.props == ("umbrella", "hotpack")
    assert m.look_for(m.find_outfit(OUTFITS, "simple", "T01")).outer is None


def test_minimi_never_holds_umbrella_and_parasol_together():
    outfit = m.find_outfit(OUTFITS, "simple", "T01")
    assert m.look_for(outfit, {"umbrella", "parasol", "water"}).props == ("umbrella", "water")
    assert m.look_for(outfit, {"parasol"}).props == ("parasol",)


def test_bubble_first_asks_then_says_a_random_line():
    rec = m.recommend([snap(feels=-3)], "morning", "simple", None, RULES, OUTFITS)
    supplies = m.supplies_for(rec, RULES)
    first, second = m.bubble_lines(supplies, 2, RULES, pick=lambda lines: lines[0])  # 핫팩·귀마개·목도리·장갑
    assert first == "다른 건 챙길 것 없나?"
    assert second == "추우니까 목도리 가져갈까?"
    _, wrapped = m.bubble_lines(supplies, 6, RULES, pick=lambda lines: lines[0])  # 4개 → 7번째는 다시 세 번째
    assert wrapped == second


def test_bubble_without_supplies():
    first, second = m.bubble_lines([], 0, RULES, pick=lambda lines: lines[0])
    assert first == "다른 건 챙길 것 없나?" and second in RULES["bubble"]["nothing"]


def test_every_supply_has_several_lines():
    for kind, d in RULES["supplies"].items():
        assert len(d["lines"]) >= 2, kind


# --- 미니미·아이콘 --------------------------------------------------------


def test_scene_svg_is_pixel_art_with_title():
    look = m.look_for(m.find_outfit(OUTFITS, "lovely", "T03"))
    svg = m.render_scene(look, "rain", "오늘의 미니미")
    assert svg.startswith("<svg") and 'shape-rendering="crispEdges"' in svg
    assert "<title>오늘의 미니미</title>" in svg and svg.count("<rect") > 100
    assert m.render_scene(None, "clear_day", "바깥 풍경").count("<rect") < svg.count("<rect")


def test_outdoor_scene_has_weather_effects():
    rain = m.render_scene(None, "rain", "비")
    clear = m.render_scene(None, "clear_day", "맑음")
    assert "#4C7FCF" in rain and "#4C7FCF" not in clear  # 빗줄기
    assert "#FFD54A" in clear  # 해


def test_garment_icons_render_for_every_item():
    for item in [i for o in OUTFITS for i in (o.top, o.bottom, o.outer) if i]:
        g = m.Garment(item.pixel["shape"], item.pixel["color"], item.pixel.get("detail"))
        svg = m.render_garment(g, item.category, item.name)
        assert svg.count("<rect") > 5 and f"<title>{item.name}</title>" in svg


def test_supply_icons_render_for_every_kind():
    for kind, d in RULES["supplies"].items():
        svg = m.render_supply(kind, d["name"])
        assert svg.count("<rect") > 3 and f"<title>{d['name']}</title>" in svg, kind


# --- 색상 선택 팔레트 -----------------------------------------------------


def test_palette_has_named_colors():
    assert len(PALETTE) >= 10
    assert all(p["name"] and p["color"].startswith("#") for p in PALETTE)
    assert len({p["id"] for p in PALETTE}) == len(PALETTE)


def test_resolve_colors_defaults_and_choices():
    outfit = m.find_outfit(OUTFITS, "simple", "T04")
    default = m.resolve_colors(outfit, PALETTE, {})
    assert default["top"] == {"id": "default", "name": "기본", "color": outfit.top.pixel["color"]}
    chosen = m.resolve_colors(outfit, PALETTE, {m.color_key(outfit.top): "navy", m.color_key(outfit.outer): "nope"})
    assert chosen["top"]["name"] == "네이비" and chosen["top"]["color"] == "#2E3D63"
    assert chosen["outer"]["id"] == "default"  # 없는 색은 기본으로
    assert set(m.resolve_colors(m.find_outfit(OUTFITS, "simple", "T01"), PALETTE, {})) == {"top", "bottom"}


def test_color_choice_is_remembered_per_item():
    a, b = m.find_outfit(OUTFITS, "simple", "T04"), m.find_outfit(OUTFITS, "modern", "T04")
    assert m.color_key(a.outer) == m.color_key(b.outer)  # 같은 트렌치코트면 같은 색 유지
    assert m.color_key(a.top) != m.color_key(b.top)


def test_look_uses_chosen_colors():
    outfit = m.find_outfit(OUTFITS, "simple", "T04")
    look = m.look_for(outfit, (), {"top": "#D9505E"})
    assert look.top.color == "#D9505E" and look.bottom.color == outfit.bottom.pixel["color"]


@pytest.mark.parametrize("color, text", [("#FAFAFA", "#1A1A1A"), ("#26262B", "#FFFFFF"), ("#2E3D63", "#FFFFFF"), ("#F4A7B9", "#1A1A1A")])
def test_chip_text_color_is_readable(color, text):
    assert m._text_on(color) == text


# --- 옷장 ----------------------------------------------------------------


def make_entry(hour=9, style="simple", colors=None, packed=None):
    s = m.Snapshot(datetime(2026, 10, 23, hour, tzinfo=KST), 12, 11, 50, 2, 0.1, "", "04d", 804, False)
    rec = m.recommend([s], "morning", style, None, RULES, OUTFITS, "내일")
    cell = m.HourCell(s.time, s, False, False)
    return m.wardrobe_entry([cell], "서울", style, style.title(), rec, m.Sky("흐림", "cloud"), colors, packed)


def test_wardrobe_add_dedupe_remove(tmp_path):
    path = tmp_path / "wardrobe.json"
    assert m.load_wardrobe(path) == []
    first = make_entry(9)
    assert m.add_to_wardrobe(first, path)
    assert not m.add_to_wardrobe(make_entry(9), path)  # 같은 시각·지역·스타일·코디
    assert m.add_to_wardrobe(make_entry(12), path)
    saved = m.load_wardrobe(path)
    assert [e["basis_time"][11:16] for e in saved] == ["12:00", "09:00"]  # 최신이 앞
    assert saved[1]["items"][0] == m.find_outfit(OUTFITS, "simple", "T05").top.name
    m.remove_from_wardrobe(first["id"], path)
    assert [e["id"] for e in m.load_wardrobe(path)] == [saved[0]["id"]]


def test_broken_wardrobe_file_is_treated_as_empty(tmp_path):
    path = tmp_path / "wardrobe.json"
    path.write_text("{not json", encoding="utf-8")
    assert m.load_wardrobe(path) == []


def test_wardrobe_key_changes_with_color_and_packing():
    plain = make_entry(9)
    outfit = m.find_outfit(OUTFITS, "simple", "T05")
    red = make_entry(9, colors=m.resolve_colors(outfit, PALETTE, {m.color_key(outfit.top): "red"}))
    umbrella = make_entry(9, packed=[m.Supply("umbrella", "우산", "", ())])
    assert len({plain["key"], red["key"], umbrella["key"]}) == 3
    assert red["colors"]["top"] == {"name": "레드", "color": "#D9505E"}
    assert umbrella["supplies"] == [{"kind": "umbrella", "name": "우산"}]


def test_saved_kinds_new_and_old_entries():
    outfit = m.find_outfit(OUTFITS, "simple", "T06")
    assert m.saved_kinds({"supplies": [{"kind": "water", "name": "물"}]}, outfit, RULES) == ["water"]
    assert m.saved_kinds({"umbrella": True}, outfit, RULES) == ["umbrella", "scarf", "gloves"]  # 예전: 소품 자동 착용
    assert m.saved_kinds({"props": ["hotpack"]}, None, RULES) == ["hotpack"]


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


# --- 저장 이름·태그 -------------------------------------------------------


def test_clean_tags():
    assert m.clean_tags([" 직딩룩 ", "#데이트룩", "", "직딩룩", "#", "아주아주아주긴태그이름입니다"]) == [
        "직딩룩", "데이트룩", "아주아주아주긴태그이름입"
    ]


def test_tag_options_keep_presets_then_custom_tags():
    presets = RULES["wardrobe_tags"]
    assert {"여행 코디", "직딩룩", "백수룩", "데이트룩", "꾸안꾸룩"} <= set(presets)
    entries = [{"tags": ["캠핑룩", "직딩룩"]}, {"tags": ["캠핑룩", "소개팅"]}, {}]
    assert m.wardrobe_tag_options(presets, entries) == [*presets, "캠핑룩", "소개팅"]


def test_default_save_name():
    cells = [m.HourCell(datetime(2026, 10, 23, h, tzinfo=KST), snap(hour=h), False, False) for h in (9, 12, 15)]
    assert m.default_save_name(cells, m.Sky("흐림", "cloud"), "Simple") == "10/23(금) 9시~15시 흐림 Simple 코디"


def test_named_entry_round_trip(tmp_path):
    path = tmp_path / "wardrobe.json"
    entry = {**make_entry(9), "name": "금요일 출근", "tags": ["직딩룩"]}
    assert m.add_to_wardrobe(entry, path)
    saved = m.load_wardrobe(path)[0]
    assert saved["name"] == "금요일 출근" and saved["tags"] == ["직딩룩"]


def test_bubble_html_escapes_text_and_shows_position():
    supplies = [m.Supply("water", "물", "", ("<b>물</b> 챙길까?",)), m.Supply("hotpack", "핫팩", "", ("핫팩!",))]
    html = m.bubble_html(supplies, {"index": 3, "lines": ("다른 건 챙길 것 없나?", "<b>물</b> 챙길까?")})
    assert "&lt;b&gt;" in html and "<b>" not in html
    assert '<span class="mj-count">2/2</span>' in html and 'class="mj-tail"' in html


# --- 말풍선 준비물 하나씩 챙기기 -----------------------------------------


def test_pack_button_follows_bubble_item():
    rec = m.recommend([snap(feels=-3, pop=0.8)], "morning", "simple", None, RULES, OUTFITS)
    supplies = m.supplies_for(rec, RULES)  # 우산, 핫팩, 목도리, 장갑
    assert m.bubble_supply(supplies, 0).kind == "umbrella"
    assert m.bubble_supply(supplies, 1).kind == "hotpack"
    assert m.bubble_supply(supplies, len(supplies)).kind == "umbrella"  # 끝에서 다시 처음
    assert m.bubble_supply(supplies, -1).kind == supplies[-1].kind  # < 로 처음에서 끝으로


def test_pack_button_label_switches_to_cancel():
    umbrella = m.Supply("umbrella", "우산", "", ())
    assert m.pack_button_label(umbrella, False) == "우산 챙기기"
    assert m.pack_button_label(umbrella, True) == "우산 챙기기 취소"


@pytest.mark.parametrize(
    "line, name, expected",
    [
        ("추우니까 목도리 가져갈까?", "목도리", '추우니까 <strong class="mj-item">목도리</strong> 가져갈까?'),
        ("저녁엔 쌀쌀할 수 있어. 겉옷 챙기자!", "여벌 겉옷", '저녁엔 쌀쌀할 수 있어. <strong class="mj-item">겉옷</strong> 챙기자!'),
        ("오늘은 이대로 나가도 괜찮겠다!", "우산", "오늘은 이대로 나가도 괜찮겠다!"),
        ("<b>물</b> 챙길까?", "물", '&lt;b&gt;<strong class="mj-item">물</strong>&lt;/b&gt; 챙길까?'),
    ],
)
def test_bubble_highlights_item_name(line, name, expected):
    assert m.highlight_item(line, name) == expected


def test_every_bubble_line_highlights_its_item():
    """준비물마다 모든 말풍선 문장에 강조할 이름이 들어 있어야 한다."""
    for o in OUTFITS:
        for snapshot_feels in (-3, 30):
            rec = m.recommend([snap(feels=snapshot_feels, pop=0.8, wind=9, cid=800, icon="01d")], "morning", o.style, 12, RULES, OUTFITS)
            for supply in m.supplies_for(rec, RULES):
                for line in supply.lines:
                    assert "mj-item" in m.highlight_item(line, supply.name), (supply.kind, line)


# --- 아이템 등록 창 -------------------------------------------------------


def item_by_id(item_id):
    return next(i for o in OUTFITS for i in (o.top, o.bottom, o.outer) if i and i.item_id == item_id)


@pytest.mark.parametrize(
    "item_id, color_id, expected",
    [
        ("knit_turtleneck", "white", "화이트 터틀넥 니트"),
        ("knit_turtleneck", None, "터틀넥 니트"),
        ("knit_cream", "white", "화이트 니트"),  # 원래 색 단어(크림)는 빼고 새 색으로
        ("jeans_light", "navy", "네이비 데님 팬츠"),  # 연청 → 네이비
        ("tee_basic_short", "pink", "핑크 무지 반팔 티셔츠"),  # 색 단어가 아니면 그대로 두고 앞에 붙인다
        ("sweatshirt", "gray", "그레이 맨투맨"),  # 한 단어 이름
    ],
)
def test_display_name_reflects_chosen_color(item_id, color_id, expected):
    color = next((c for c in PALETTE if c["id"] == color_id), None)
    assert m.display_name(item_by_id(item_id), color) == expected


def test_entry_slots_have_icon_data_and_empty_outer():
    outfit = m.find_outfit(OUTFITS, "simple", "T06")  # 터틀넥 니트
    colors = m.resolve_colors(outfit, PALETTE, {m.color_key(outfit.top): "white"})
    slots = m.entry_slots(outfit, colors)
    assert [s["label"] for s in slots] == ["상의", "하의", "아우터"]
    assert slots[0]["item"] == {"name": "화이트 터틀넥 니트", "shape": "long", "color": "#FAFAFA", "detail": "turtleneck"}
    no_outer = m.entry_slots(m.find_outfit(OUTFITS, "simple", "T01"), {})
    assert no_outer[2] == {"category": "outer", "label": "아우터", "item": None}


def test_wardrobe_entry_saves_slots_and_colored_names():
    outfit = m.find_outfit(OUTFITS, "simple", "T05")
    colors = m.resolve_colors(outfit, PALETTE, {m.color_key(outfit.top): "red"})
    e = make_entry(9, colors=colors)
    assert e["items"][0] == "레드 두꺼운 크루넥 니트" and e["slots"][0]["item"]["color"] == "#D9505E"


def test_saved_slots_for_old_entries():
    outfit = m.find_outfit(OUTFITS, "simple", "T05")
    old = {"colors": {"top": {"name": "레드", "color": "#D9505E"}}}
    slots = m.saved_slots(old, outfit)
    assert slots[0]["item"]["name"] == "레드 두꺼운 크루넥 니트" and slots[0]["item"]["color"] == "#D9505E"
    assert m.saved_slots({}, None) == []


# --- 48시간 외출 시간 -----------------------------------------------------


def two_day_cells(now_hour=20, now_minute=30):
    data = m.parse_weather(current_raw(now_hour, now_minute), forecast_raw(21))
    now = datetime(2026, 10, 22, now_hour, now_minute, tzinfo=KST)
    return data, now, m.outing_timeline(data, now)


def test_outing_timeline_covers_today_and_tomorrow():
    data, now, cells = two_day_cells()
    assert len(cells) == 16
    assert [m.day_of(c, now) for c in cells] == [0] * 8 + [1] * 8
    assert cells[6].is_now and cells[8].time == datetime(2026, 10, 23, 0, tzinfo=KST)
    assert m.default_cell_index(cells) == 6


def test_outing_across_midnight():
    data, now, cells = two_day_cells()
    chosen = m.outing_cells(cells, [7, 8, 9])  # 21시, 내일 0시, 내일 3시
    assert m.outing_label(chosen) == "21시~내일 3시"
    assert m.outing_question(chosen, SLOTS, now) == "오늘 21시~내일 3시 외출엔 뭐 입지?"
    assert m.outing_date_label(chosen, now) == "10/22(목)~10/23(금)"
    assert m.outing_day(chosen, now) == ("today", "오늘")
    assert m.outing_swing(chosen) is not None  # 자정을 넘어도 기온 차를 계산


def test_outing_only_tomorrow():
    data, now, cells = two_day_cells()
    chosen = m.outing_cells(cells, [11, 12])  # 내일 9시, 12시
    assert m.outing_label(chosen) == "9시~12시"
    assert m.outing_question(chosen, SLOTS, now) == "내일 9시~12시 외출엔 뭐 입지?"
    assert m.outing_day(chosen, now) == ("tomorrow", "내일")
    assert m.outing_date_label(chosen, now) == "10/23(금)"
    single = m.outing_cells(cells, [11])
    assert m.outing_question(single, SLOTS, now) == "내일 아침엔 뭐 입지?"


def test_now_cell_label_across_midnight():
    data, now, cells = two_day_cells()
    assert m.outing_label(m.outing_cells(cells, [6, 7, 8])) == "지금~내일 0시"


# --- 화면 모드 ------------------------------------------------------------


@pytest.mark.parametrize("hour, mode", [(5, "dark"), (6, "light"), (12, "light"), (17, "light"), (18, "dark"), (23, "dark")])
def test_default_mode_by_time(hour, mode):
    assert m.default_mode(datetime(2026, 10, 22, hour, tzinfo=KST)) == mode


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("theme", ["clear_day", "clear_night", "cloudy"])
def test_page_css_has_mode_tokens(mode, theme):
    css = m.page_css(theme, mode)
    t = m.THEMES[mode][theme]
    assert f"--mj-start: {t['start']}" in css and f"--mj-text: {t['text']}" in css
    assert f"--mj-glass: {m.MODE_TOKENS[mode]['glass']}" in css and "--mj-thumb" in css


def contrast(a, b):
    def lum(h):
        r, g, bb = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
        f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(bb)
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("theme", ["clear_day", "clear_night", "cloudy"])
def test_text_contrast_on_both_gradient_ends(mode, theme):
    t = m.THEMES[mode][theme]
    assert min(contrast(t["text"], t["start"]), contrast(t["text"], t["end"])) >= 4.5


# --- 스타일 안에서 아이템 고르기 -------------------------------------------


def candidates_for(style):
    ranges = RULES["temperature_ranges"]
    return {c: m.style_candidates(OUTFITS, style, c, ranges) for c, _ in m.CATEGORIES}


def test_style_candidates_list_unique_items_warm_first():
    cands = candidates_for("simple")
    tops = cands["top"]
    assert len({c.item_id for c in tops}) == len(tops)
    assert tops[0].item_id == m.find_outfit(OUTFITS, "simple", "T01").top.item_id
    assert tops[0].band == "28°C 이상용"
    outers = cands["outer"]
    assert outers[0].item is None and outers[0].item_id == m.NO_ITEM_ID  # 더운 날 '아우터 없음'도 후보
    every_style_item = {o.top.item_id for o in OUTFITS if o.style == "simple"}
    assert {c.item_id for c in tops} == every_style_item | {"shirt_white_thin"}  # 아우터 셔츠를 상의로도


def test_compose_outfit_starts_from_recommendation_and_swaps_chosen():
    base = m.find_outfit(OUTFITS, "simple", "T04")
    cands = candidates_for("simple")
    assert m.compose_outfit(base, cands, {}) == base  # 고르기 전엔 추천 코디 그대로
    padding = m.find_outfit(OUTFITS, "simple", "T06").outer
    hot_top = m.find_outfit(OUTFITS, "simple", "T01").top
    choices = {m.choice_key("simple", "outer"): padding.item_id, m.choice_key("simple", "top"): hot_top.item_id}
    worn = m.compose_outfit(base, cands, choices)
    assert worn.outer == padding and worn.top == hot_top and worn.bottom == base.bottom
    assert worn.accessories == base.accessories and worn.outfit_id == base.outfit_id
    no_outer = m.compose_outfit(base, cands, {m.choice_key("simple", "outer"): m.NO_ITEM_ID})
    assert no_outer.outer is None
    # 다른 스타일의 선택이나 없는 아이템은 무시
    assert m.compose_outfit(base, cands, {m.choice_key("modern", "top"): hot_top.item_id}) == base
    assert m.compose_outfit(base, cands, {m.choice_key("simple", "top"): "nope"}) == base


def test_wardrobe_key_and_items_follow_chosen_combination():
    s = m.Snapshot(datetime(2026, 10, 23, 9, tzinfo=KST), 12, 11, 50, 2, 0.1, "", "04d", 804, False)
    rec = m.recommend([s], "morning", "simple", None, RULES, OUTFITS, "내일")
    cell = m.HourCell(s.time, s, False, False)
    padding = m.find_outfit(OUTFITS, "simple", "T06").outer
    worn = m.compose_outfit(rec.outfit, candidates_for("simple"), {m.choice_key("simple", "outer"): padding.item_id})
    plain = m.wardrobe_entry([cell], "서울", "simple", "Simple", rec, m.Sky("흐림", "cloud"))
    mixed = m.wardrobe_entry([cell], "서울", "simple", "Simple", m.replace(rec, outfit=worn), m.Sky("흐림", "cloud"))
    assert plain["key"] != mixed["key"]
    assert mixed["items"][2] == padding.name and mixed["item_ids"].endswith(padding.item_id)


# --- 준비물 색 ------------------------------------------------------------


def test_supply_colors_resolve_and_tint_minimi_and_icon():
    umbrella = m.Supply("umbrella", "우산", "", ())
    water = m.Supply("water", "물", "", ())
    colors = m.resolve_supply_colors([umbrella, water], PALETTE, {m.supply_color_key("umbrella"): "pink"})
    assert set(colors) == {"umbrella"} and colors["umbrella"]["name"] == "핑크"
    pink = colors["umbrella"]["color"]
    outfit = m.find_outfit(OUTFITS, "simple", "T04")
    look = m.look_for(outfit, {"umbrella"}, None, {"umbrella": pink, "water": "#000000"})
    assert look.prop_colors == (("umbrella", pink),)  # 챙긴 것만
    assert pink in m.render_scene(look, "rain", "비") and pink in m.render_supply("umbrella", "우산", pink)
    assert pink not in m.render_supply("umbrella", "우산")


def test_wardrobe_saves_supply_color():
    umbrella = m.Supply("umbrella", "우산", "", ())
    pink = next(p for p in PALETTE if p["id"] == "pink")
    plain = make_entry(9, packed=[umbrella])
    s = m.Snapshot(datetime(2026, 10, 23, 9, tzinfo=KST), 12, 11, 50, 2, 0.1, "", "04d", 804, False)
    rec = m.recommend([s], "morning", "simple", None, RULES, OUTFITS, "내일")
    colored = m.wardrobe_entry(
        [m.HourCell(s.time, s, False, False)], "서울", "simple", "Simple", rec, m.Sky("흐림", "cloud"),
        None, [umbrella], {"umbrella": pink},
    )
    assert plain["key"] != colored["key"]
    assert colored["supplies"] == [{"kind": "umbrella", "name": "우산", "color": pink["color"], "color_name": "핑크"}]
    look = m.saved_look(colored, None, RULES)
    assert look.props == ("umbrella",) and look.prop_colors == (("umbrella", pink["color"]),)


def test_saved_look_rebuilds_from_slots_without_outfit():
    e = make_entry(9)
    look = m.saved_look(e, None, RULES)  # 코디 목록에 없어도 저장한 칸으로 그린다
    assert look.top.color == e["slots"][0]["item"]["color"]
    assert m.saved_look({}, None, RULES) is None


def test_spare_layer_is_called_cardigan():
    assert RULES["supplies"]["extra_layer"]["name"] == "여벌 가디건"
    assert all("가디건" in line for line in RULES["supplies"]["extra_layer"]["lines"])


# --- 포즈·움직이는 배경 -----------------------------------------------------


def test_umbrella_pose_raises_arm_and_animates_once():
    from minimi import pose_frames, final_pose

    outfit = m.find_outfit(OUTFITS, "simple", "T04")
    look = m.look_for(outfit, {"umbrella", "water"})
    frames = pose_frames(look, "umbrella")
    assert [f.canopy for f in frames] == [None, "closed", "open"]
    assert final_pose(look).right == "up" and final_pose(look).left == "bent"
    svg = m.render_scene(look, "rain", "비", action="umbrella")
    assert svg.count('class="frame') == 3 and "mj-on" in svg
    assert m.render_scene(look, "rain", "비").count('class="frame') == 1  # 방금 챙긴 게 없으면 움직이지 않는다
    assert pose_frames(look) == [final_pose(look)]


def test_sunglasses_are_pushed_up_then_rest():
    from minimi import pose_frames

    look = m.look_for(m.find_outfit(OUTFITS, "simple", "T01"), {"sunglasses"})
    assert [f.right for f in pose_frames(look, "sunglasses")] == ["push", "push", "down"]  # 코받침을 밀어 올린다
    assert [f.glasses_dy for f in pose_frames(look, "sunglasses")] == [0, -1, 0]


@pytest.mark.parametrize("scene, layer", [("rain", 'class="rain"'), ("snow", 'class="snow"'), ("clear_night", 'class="twinkle"')])
def test_background_moves_and_respects_reduced_motion(scene, layer):
    svg = m.render_scene(None, scene, "풍경")
    assert 'class="drift"' in svg or scene == "clear_night"
    assert layer in svg and "prefers-reduced-motion" in svg


# --- 미세먼지·마스크, 귀마개, 상의로도 입는 셔츠 ----------------------------------


def air_raw(*pairs, start_hour=9):
    return {"list": [
        {"dt": ts(start_hour + i), "main": {"aqi": 3}, "components": {"pm10": pm10, "pm2_5": pm25}}
        for i, (pm10, pm25) in enumerate(pairs)
    ]}


def test_parse_air_skips_broken_items():
    raw = air_raw((40, 20), (90, None))
    raw["list"].append({"dt": ts(12), "components": {}})
    raw["list"].append({"components": {"pm10": 10}})
    readings = m.parse_air(raw, KST)
    assert [(r.time.hour, r.pm10, r.pm25) for r in readings] == [(9, 40, 20), (10, 90, None)]
    assert m.parse_air(None, KST) == []


@pytest.mark.parametrize(
    "pairs, tip",
    [([(40, 20), (60, 40)], "마스크 챙기기 (초미세먼지 40㎍/㎥)"), ([(95, 20)], "마스크 챙기기 (미세먼지 95㎍/㎥)"), ([(80, 35)], None)],
)
def test_bad_dust_recommends_mask(pairs, tip):
    air = m.parse_air(air_raw(*pairs), KST)
    conds = m.detect_conditions([snap(feels=15)], None, RULES, air)
    dust = next((c for c in conds if c.id == "dust"), None)
    assert (dust.tip if dust else None) == tip
    if tip:
        rec = m.recommend([snap(feels=15)], "morning", "simple", None, RULES, OUTFITS, air=air)
        mask = next(s for s in m.supplies_for(rec, RULES) if s.kind == "mask")
        assert mask.name == "마스크" and len(mask.lines) >= 2


def test_air_window_follows_outing():
    data, now, cells = two_day_cells()
    air = [m.AirReading(datetime(2026, 10, 22, 19, tzinfo=KST) + timedelta(hours=i), 10, 5) for i in range(10)]  # 19시~내일 4시
    chosen = m.outing_cells(cells, [7, 8])  # 21시, 내일 0시 → 19:30~1:30
    assert [r.time.hour for r in m.air_window(chosen, air)] == [20, 21, 22, 23, 0, 1]
    assert m.air_window([], air) == []


def test_cold_ears_get_earmuffs_with_named_lines():
    conds = m.detect_conditions([snap(feels=2.6)], None, RULES)
    assert "ears" in [c.id for c in conds] and "cold" not in [c.id for c in conds]
    rec = m.recommend([snap(feels=2.6)], "morning", "simple", None, RULES, OUTFITS)
    ear = next(s for s in m.supplies_for(rec, RULES) if s.kind == "earmuffs")
    assert ear.reason == "귀마개 챙기기 (최저 체감 3°C)" and all("{name}" not in line for line in ear.lines)


def test_mask_and_earmuffs_on_minimi():
    from minimi import pose_frames

    outfit = m.find_outfit(OUTFITS, "casual", "T05")
    look = m.look_for(outfit, {"mask", "earmuffs", "beanie"}, None, {"mask": "#26262B"})
    assert "mask" in look.props and look.earmuffs and look.hat == "beanie"
    frames = pose_frames(look, "mask")  # 마스크: 주먹을 입에 대고 콜록
    assert [f.right for f in frames] == ["cough", "down", "cough", "down"] and frames[0].cough and frames[0].eyes == "closed"
    assert "#26262B" in m.render_scene(look, "cloudy", "미니미")
    for kind in ("mask", "earmuffs"):
        assert m.render_supply(kind, kind).count("<rect") > 5


def test_thin_shirt_can_be_worn_as_top():
    cands = candidates_for("simple")
    shirt_top = next(c for c in cands["top"] if c.item_id == "shirt_white_thin")
    assert shirt_top.item.category == "top" and shirt_top.item.pixel["shape"] == "long"
    assert any(c.item_id == "shirt_white_thin" for c in cands["outer"])  # 아우터로도 그대로
    base = m.find_outfit(OUTFITS, "simple", "T03")
    worn = m.compose_outfit(base, cands, {m.choice_key("simple", "top"): "shirt_white_thin"})
    assert worn.top.name == "얇은 화이트 셔츠" and m.look_for(worn).top.detail == "collar"


def test_air_window_for_now_cell_uses_observation_time():
    data, now, cells = two_day_cells(20, 30)  # '지금' 칸은 18시 칸, 관측은 20:30
    now_cell = next(c for c in cells if c.is_now)
    air = [m.AirReading(datetime(2026, 10, 22, h, tzinfo=KST), 90, 40) for h in range(16, 23)]
    assert [r.time.hour for r in m.air_window([now_cell], air)] == [19, 20, 21, 22]


# --- 내 정보·남성 코디 -------------------------------------------------------

CITY_NAMES = [c["name"] for c in m.load_json("cities.json")]


def test_profile_from_form_values():
    values = {"nickname": "  모입  러  ", "gender": "male", "height": 183, "height_normal": False,
              "weight": 70, "weight_normal": True, "city": "부산"}
    p, error = m.profile_from_values(values)
    assert error is None and p == m.Profile("male", 183, None, "부산", nickname="모입 러")
    odd, _ = m.profile_from_values({**values, "height": 999, "eyes": "x", "skin": "blue", "hair": 3})
    assert (odd.height, odd.eyes, odd.skin, odd.hair) == (None, None, "light", None)  # 범위 밖·모르는 값은 기본
    assert m.profile_from_values({**values, "gender": None}) == (None, "성별을 골라 주세요.")
    blank, error = m.profile_from_values({**values, "nickname": "   "})
    assert blank is not None and error == "닉네임을 입력해 주세요."  # 미리보기는 되지만 저장은 막는다
    assert m.clean_nickname("가나다라마바사아자차카타") == "가나다라마바사아자차"  # 10자까지


def test_profile_text_with_nickname():
    assert m.profile_text(m.Profile("male", 175, None, "서울")) == "남성, 키 175cm, 몸무게 보통, 서울"
    assert m.profile_text(m.Profile("female", None, 52, "제주", nickname="모입러")) == "모입러, 여성, 키 보통, 몸무게 52kg, 제주"


@pytest.mark.parametrize(
    "profile, body",
    [
        (None, m.Body("female", "normal", "normal")),
        (m.Profile("female", None, None, "서울"), m.Body("female", "normal", "normal")),
        (m.Profile("female", 150, None, "서울"), m.Body("female", "short", "normal")),
        (m.Profile("male", 183, None, "서울"), m.Body("male", "tall", "normal")),
        (m.Profile("male", 172, None, "서울"), m.Body("male", "normal", "normal")),
        (m.Profile("female", 160, 75, "서울"), m.Body("female", "normal", "sturdy")),  # BMI 29
        (m.Profile("male", None, 55, "서울"), m.Body("male", "normal", "slim")),  # 평균 키 174cm로 BMI 18.2
    ],
)
def test_body_from_profile(profile, body):
    assert m.body_for(profile, RULES) == body


def test_styles_by_gender():
    female = m.styles_for(CATALOG["styles"], "female")
    male = m.styles_for(CATALOG["styles"], "male")
    assert list(female) == ["simple", "modern", "casual", "lovely", "street"]
    assert list(male) == ["simple", "modern", "casual", "dandy", "street"]


def test_men_get_an_outfit_for_every_style_and_band_without_skirts():
    for gender in ("female", "male"):
        for style in m.styles_for(CATALOG["styles"], gender):
            for r in RULES["temperature_ranges"]:
                outfit = m.find_outfit(OUTFITS, style, r["code"], gender)
                if gender == "male":
                    assert not outfit.bottom.pixel["shape"].startswith("skirt"), outfit.outfit_id
                    assert "기모 스타킹" not in outfit.accessories
    with pytest.raises(KeyError):
        m.find_outfit(OUTFITS, "dandy", "T03", "female")
    rec = m.recommend([snap(feels=19)], "morning", "dandy", None, RULES, OUTFITS, gender="male")
    assert rec.outfit.outer.name == "네이비 블레이저"


def test_male_candidates_come_from_male_outfits():
    ranges = RULES["temperature_ranges"]
    tops = m.style_candidates(OUTFITS, "dandy", "top", ranges, "male")
    assert "shirt_oxford" in {c.item_id for c in tops}
    assert m.style_candidates(OUTFITS, "dandy", "top", ranges, "female") == []


def test_body_shapes_minimi_and_is_saved():
    from minimi import Body, foot_y

    outfit = m.find_outfit(OUTFITS, "simple", "T03")
    woman, man = m.look_for(outfit), m.look_for(outfit, body=Body("male", "tall", "sturdy"))
    assert foot_y(man.body) > foot_y(woman.body)  # 키 큰 남성은 다리가 길다
    assert m.render_minimi(man, "x") != m.render_minimi(woman, "x")
    s = m.Snapshot(datetime(2026, 10, 23, 9, tzinfo=KST), 12, 11, 50, 2, 0.1, "", "04d", 804, False)
    rec = m.recommend([s], "morning", "simple", None, RULES, OUTFITS, "내일")
    cell = m.HourCell(s.time, s, False, False)
    args = ([cell], "서울", "simple", "Simple", rec, m.Sky("흐림", "cloud"))
    e_man = m.wardrobe_entry(*args, body=Body("male", "tall", "sturdy"))
    e_woman = m.wardrobe_entry(*args)
    assert e_man["key"] != e_woman["key"]
    assert e_man["body"] == {"gender": "male", "height": "tall", "build": "sturdy", "eyes": None, "skin": "light", "hair": None}
    assert m.saved_look(e_man, None, RULES).body == Body("male", "tall", "sturdy")
    assert m.saved_look({**e_man, "body": None}, None, RULES).body == Body()  # 예전 저장본은 기본 체형



def test_profile_keeps_face_choices():
    from minimi import eyes_of, hair_of

    p, _ = m.profile_from_values(
        {"set_gender": "male", "set_height_normal": True, "set_weight_normal": True, "set_city": "서울",
         "set_eyes": "smile", "set_skin": "tan", "set_hair": "curly", "set_nickname": "a"}, "set_",
    )
    assert (p.eyes, p.skin, p.hair) == ("smile", "tan", "curly")
    body = m.body_for(p, RULES)
    assert (eyes_of(body), body.skin, hair_of(body)) == ("smile", "tan", "curly")
    plain, _ = m.profile_from_values({"gender": "male", "nickname": "a"})
    assert (eyes_of(m.body_for(plain, RULES)), hair_of(m.body_for(plain, RULES))) == ("calm", "short")  # 남성 기본: 덜 또렷한 눈


def test_face_options_change_minimi():
    from minimi import EYE_STYLES, HAIR_STYLES, SKIN_TONES, Body

    outfit = m.find_outfit(OUTFITS, "simple", "T03")
    svgs = {m.render_minimi(m.look_for(outfit, body=Body(eyes=e)), "x") for e in EYE_STYLES}
    svgs |= {m.render_minimi(m.look_for(outfit, body=Body(hair=h)), "x") for h in HAIR_STYLES}
    assert len(svgs) == len(EYE_STYLES) + len(HAIR_STYLES) - 1  # 기본 모습(동그란 눈 + 단발)이 두 묶음에 한 번 겹친다
    for key, (_, color) in SKIN_TONES.items():
        assert color in m.render_minimi(m.look_for(outfit, body=Body(skin=key)), "x")
    saved = m.saved_look({"slots": m.entry_slots(outfit, {}), "body": {"gender": "female", "skin": "deep", "hair": "long"}}, None, RULES)
    assert saved.body == Body(skin="deep", hair="long")


def test_gnb_links_to_team_services():
    import theme

    html = theme.gnb_html()
    assert [label for label, _ in theme.GNB] == ["JOOYOU", "guest", "meal", "reading", "MOIPJI"]
    for label, route in theme.GNB:
        assert f'href="{route}"' in html and f">{label}</a>" in html
    assert html.count('aria-current="page"') == 2  # 세로 탭과 '=' 메뉴에서 MOIPJI 하나씩
    assert 'aria-current="page">MOIPJI' in html
    assert "외출 시간" not in html  # 서비스 안 목차는 빼고 팀 서비스로만 이동


def test_theme_is_moipji_only_until_team_agrees():
    import inspect

    import theme

    assert theme.SERVICE == theme.Service("weather", "MOIPJI", "#7FA6D3") and theme.SERVICE.route == m.SERVICE_ROUTE
    assert not hasattr(theme, "SERVICES")  # 팀원 대표색 규칙은 합의 전이라 주석으로만 둔다
    source = inspect.getsource(theme)
    assert "# 팀원 수정 규칙" in source and '#        Service("meal", "meal", "#E8768A"),' in source
    css = theme.theme_css()
    assert ".st-key-weather_root" in css and theme.SERVICE.color in css
    assert "__" not in css  # 빈 자리 없이 다 채움
    assert inspect.signature(theme.render_frame).parameters == {} and inspect.signature(theme.render_gnb).parameters == {}


@pytest.mark.parametrize("color", ["#7FA6D3", "#F0A04B", "#9B7FD4", "#E8768A", "#58A889", "#FFE066", "#202020"])
def test_theme_palette_from_one_color_is_readable(color):
    import theme

    pal = theme.palette_for(color)
    assert theme.contrast(pal["tab_text"], pal["tab"]) >= 4.5  # 탭 글자
    assert theme.contrast(pal["tab_on_text"], "#FFFFFF") >= 4.5  # 지금 서비스 탭 글자
    assert all(theme.HEX.match(v) for v in pal.values())
    assert theme.contrast(pal["frame"], "#FFFFFF") < 2.0  # 프레임은 옅은 색 (아주 어두운 대표색이어도 연회색)



def test_big_umbrella_covers_the_body_and_keeps_rain_off():
    import re

    from minimi import CANOPY_HALF, DX, TORSO, canopy_box, Body

    x0, y0, x1, y1 = canopy_box(Body())
    body_left, body_right = min(v[0] for v in TORSO.values()), max(v[1] for v in TORSO.values())
    assert x1 - x0 + 1 >= 43 and CANOPY_HALF >= 21  # 장난감 우산(지름 25px)보다 훨씬 크게
    assert x0 - DX < body_left and x1 - DX >= body_right  # 판 기준 → 몸 기준: 어깨 양끝을 덮는다
    outfit = m.find_outfit(OUTFITS, "simple", "T04")
    rain = m.render_scene(m.look_for(outfit, {"umbrella"}), "rain", "비")
    assert 'mask="url(#mj-dry)"' in rain  # 우산 아래는 비가 닿지 않는다
    assert 'mask="url(#mj-dry)"' not in m.render_scene(m.look_for(outfit), "rain", "비")
    assert 'mask=' not in m.render_scene(m.look_for(outfit, {"parasol"}), "clear_day", "맑음")  # 비가 없으면 가릴 것도 없다
    thumb = m.render_minimi(m.look_for(outfit), "썸네일")
    width = int(re.search(r'viewBox="0 0 (\d+) ', thumb).group(1))
    assert width < 40  # 빈 여백을 잘라 썸네일 속 미니미가 작아지지 않는다



def test_pack_actions_gloves_clap_cardigan_cheers_hat_salutes():
    from minimi import pose_frames

    outfit = m.find_outfit(OUTFITS, "casual", "T05")
    gloves = pose_frames(m.look_for(outfit, {"gloves"}), "gloves")
    assert [f.left for f in gloves[:4]] == ["clap_open", "clap", "clap_open", "clap"] and gloves[-1].left == "down"
    cheer = pose_frames(m.look_for(outfit, {"extra_layer"}), "extra_layer")
    assert cheer[0].left == cheer[0].right == "raise" and cheer[0].eyes == "smile" and cheer[-1].eyes is None
    salute = pose_frames(m.look_for(outfit, {"beanie"}), "beanie")
    assert [f.right for f in salute] == ["salute", "salute", "down"]
    umbrella_hat = pose_frames(m.look_for(outfit, {"umbrella", "cap"}), "cap")
    assert umbrella_hat[-1].canopy == "open" and umbrella_hat[0].canopy is None  # 모자를 만지는 동안 우산은 잠시 내려놓는다
    look = m.look_for(outfit, {"glasses"})
    assert "glasses" in look.props and pose_frames(look, "glasses")[1].right == "push"
    assert m.render_scene(look, "cloudy", "x").count("#3A2E2A") > 0  # 안경테


# --- 기타 탭·겹쳐 입기 규칙·코디 밖 아우터 ------------------------------------


def test_exclusive_groups():
    assert m.exclusive_with("glasses") == ("sunglasses",)
    assert set(m.exclusive_with("cap")) == {"beanie", "bucket"}
    assert m.exclusive_with("parasol") == ("umbrella",)
    assert m.exclusive_with("earmuffs") == ()  # 귀마개는 모자와 함께 쓸 수 있다


def test_layering_blocks_same_kind_only():
    items = {i.item_id: i for o in OUTFITS for i in (o.outer,) if i}
    extras = {i.item_id: i for i, _ in m.load_closet_extras(CATALOG)}
    cardigan, leather, coat = items["cardigan_navy"], extras["jacket_leather"], items["coat_wool_single"]
    assert m.outer_layer(cardigan) == "cardigan" and m.outer_layer(leather) == "jacket" and m.outer_layer(None) is None
    assert set(m.blocked_kinds(cardigan)) == {"extra_layer"}  # 가디건 + 여벌 가디건은 안 된다
    assert set(m.blocked_kinds(leather)) == {"windbreaker"}  # 자켓 + 바람막이도 하나만
    assert set(m.blocked_kinds(coat)) == {"windbreaker"}
    assert m.blocked_kinds(None) == {}  # 아우터가 없으면 무엇이든 (가디건 + 자켓 조합도 된다)
    assert "가디건류" in m.blocked_kinds(cardigan)["extra_layer"]


def test_other_tab_lists_every_supply_with_recommended_reasons_first_class():
    rec = m.recommend([snap(feels=-3)], "morning", "simple", None, RULES, OUTFITS)
    recommended = m.supplies_for(rec, RULES)
    everything = m.all_supplies(recommended, RULES)
    kinds = [s.kind for s in everything]
    assert {"umbrella", "mask", "sunglasses", "glasses", "scarf", "gloves", "earmuffs"} <= set(kinds)
    assert len(kinds) == len(set(kinds)) == len(m.SUPPLY_ORDER)
    hotpack = next(s for s in everything if s.kind == "hotpack")
    assert hotpack.reason.startswith("핫팩 챙기기")  # 추천된 것은 추천 이유 그대로
    glasses = next(s for s in everything if s.kind == "glasses")
    assert glasses.name == "안경" and all("{name}" not in line for line in glasses.lines)


def test_leather_jacket_and_light_padding_in_every_style():
    extras = m.load_closet_extras(CATALOG)
    for gender in ("female", "male"):
        for style in m.styles_for(CATALOG["styles"], gender):
            outers = m.style_candidates(OUTFITS, style, "outer", RULES["temperature_ranges"], gender, extras)
            by_id = {c.item_id: c for c in outers}
            assert {"jacket_leather", "padding_light_short"} <= set(by_id), style
            assert by_id["jacket_leather"].band == "17~22°C, 12~16°C용"
            codes = [min(RULES_ORDER[x] for x in c.codes) for c in outers if c.codes]
            assert codes == sorted(codes)  # 따뜻한 구간용부터


RULES_ORDER = {r["code"]: i for i, r in enumerate(RULES["temperature_ranges"])}


def test_new_outer_details_render():
    extras = {i.item_id: i for i, _ in m.load_closet_extras(CATALOG)}
    for item_id in ("jacket_leather", "padding_light_short"):
        item = extras[item_id]
        assert m.render_garment(m._garment(item), "outer", item.name).count("<rect") > 5
    base = m.find_outfit(OUTFITS, "simple", "T04")
    worn = m.replace(base, outer=extras["jacket_leather"])
    assert "#2B2523" in m.render_minimi(m.look_for(worn), "x")
    assert m.render_supply("glasses", "안경").count("<rect") > 5



def test_scarf_water_hotpack_actions():
    from minimi import pose_frames

    outfit = m.find_outfit(OUTFITS, "simple", "T06")
    scarf = pose_frames(m.look_for(outfit, {"scarf"}), "scarf")
    assert [f.wind for f in scarf] == [1, 2, 1, 0]  # 머리칼이 휘날린다
    water = pose_frames(m.look_for(outfit, {"water"}), "water")
    assert [f.left for f in water] == ["drink", "drink", "bent"] and water[0].eyes == "closed"
    hotpack = pose_frames(m.look_for(outfit, {"hotpack"}), "hotpack")
    assert [f.left for f in hotpack] == ["bent_hi", "bent", "bent_hi", "bent"]  # 위아래로 흔든다
    look = m.look_for(outfit, {"scarf", "water", "hotpack"})
    for action in ("scarf", "water"):
        svg = m.render_scene(look, "snow", "x", action=action)
        assert svg.count('class="frame') == len(pose_frames(look, action))


# --- 원피스·세트, 핏한 울 스커트, 성별 그래픽 -----------------------------------


def test_wool_long_skirt_is_fitted():
    item = CATALOG["items"]["skirt_wool_long"]
    assert item["pixel"]["shape"] == "skirt_fit_long"


def test_dress_candidates_by_gender_and_worn_as_one_piece():
    ranges = RULES["temperature_ranges"]
    women = m.style_candidates(OUTFITS, "lovely", "dress", ranges, "female", m.load_closet_extras(CATALOG, "female"))
    men = m.style_candidates(OUTFITS, "dandy", "dress", ranges, "male", m.load_closet_extras(CATALOG, "male"))
    assert women[0].item is None and men[0].item is None  # 맨 앞은 '상의·하의 따로 입기'
    women_ids, men_ids = {c.item_id for c in women}, {c.item_id for c in men}
    assert {"dress_office", "dress_guest", "set_tweed", "dress_date"} <= women_ids and "set_suit" not in women_ids
    assert {"set_suit", "set_linen", "set_hawaiian"} <= men_ids and "dress_office" not in men_ids
    assert "set_track" in women_ids and "set_track" in men_ids  # 트레이닝 셋업은 함께
    base = m.find_outfit(OUTFITS, "lovely", "T03")
    cands = {"dress": women}
    worn = m.compose_outfit(base, cands, {m.choice_key("lovely", "dress"): "dress_office"})
    assert worn.dress.item_id == "dress_office" and m.worn_categories(worn)[0][0] == "dress"
    look = m.look_for(worn)
    assert look.onepiece and look.bottom.shape == "skirt_fit_midi" and look.top.color == look.bottom.color
    colors = m.resolve_colors(worn, PALETTE, {m.color_key(worn.dress): "red"})
    assert m.look_for(worn, (), {k: v["color"] for k, v in colors.items()}).top.color == "#D9505E"
    slots = m.entry_slots(worn, colors)
    assert [s["category"] for s in slots] == ["dress", "outer"]
    rebuilt = m.look_from_slots(slots)
    assert rebuilt.onepiece and rebuilt.top.color == "#D9505E"
    assert m.item_ids(worn).startswith("dress_office+")
    plain = m.compose_outfit(base, cands, {m.choice_key("lovely", "dress"): m.NO_ITEM_ID})
    assert plain.dress is None  # '따로 입기'로 원피스를 벗는다


def test_pants_set_is_not_one_piece():
    extras = {i.item_id: i for i, _ in m.load_closet_extras(CATALOG)}
    base = m.find_outfit(OUTFITS, "dandy", "T04")
    look = m.look_for(m.replace(base, dress=extras["set_suit"]))
    assert not look.onepiece and look.bottom.shape == "pants" and look.top.detail == "suit"


def test_gender_cut_changes_graphics():
    from minimi import Body

    g = m.Garment("short", "#E6DFD1")
    assert m.render_garment(g, "top", "x", "male") != m.render_garment(g, "top", "x", "female")
    outfit = m.find_outfit(OUTFITS, "simple", "T02")
    woman = m.look_for(outfit, body=Body("female", hair="short", eyes="calm"))
    man = m.look_for(outfit, body=Body("male", hair="short", eyes="calm"))
    assert m.render_minimi(woman, "x") != m.render_minimi(man, "x")  # 같은 옷도 재단이 다르다


# --- 국가·도시 --------------------------------------------------------------


def test_world_cities_by_country():
    cities = m.load_json("cities.json")
    countries = m.countries_of(cities)
    assert countries[0] == "대한민국"
    assert {"몰디브", "필리핀", "태국", "일본", "중국", "대만", "미국"} <= set(countries)
    assert m.country_of("방콕", cities) == "태국" and m.country_of("서울", cities) == "대한민국"
    assert len({c["name"] for c in cities}) == len(cities)  # 도시 이름은 겹치지 않는다 (내 정보에 이름으로 저장)
    seasonal = {i.item_id for i, _ in m.load_closet_extras(CATALOG)}
    assert {"dress_resort", "set_hawaiian", "shorts_board", "padding_arctic"} <= seasonal  # 더운 나라·혹한 도시용


# --- 첫 화면 단계 -------------------------------------------------------------


def test_welcome_steps_progress_and_checks():
    assert [label for label, _ in m.WELCOME_STEPS] == ["닉네임", "성별", "지역", "꾸미기", "시작"]
    assert m.welcome_progress(0) == "1단계 / 5단계, 앞으로 4단계 남았어요"
    assert m.welcome_progress(4) == "5단계 / 5단계, 마지막 단계예요"
    p = m.WELCOME_PREFIX
    assert m.welcome_check(0, {f"{p}nickname": "  "}) == "닉네임을 입력해 주세요."
    assert m.welcome_check(0, {f"{p}nickname": "구름이"}) is None
    assert m.welcome_check(1, {f"{p}gender": None}) == "성별을 골라 주세요."
    assert m.welcome_check(2, {}) is None
    html = m._welcome_steps_html(1)
    assert html.count('mj-step-done') == 1 and 'aria-current="step"' in html and "STEP 2 / 5" in html


def test_greeter_moves_and_animates():
    from minimi import GREETER_MOVES, greeter_moves, render_greeter

    moves = greeter_moves(3)
    assert moves[0] == "wave" and moves.count("talk") == 2 and set(moves) == set(GREETER_MOVES)
    assert greeter_moves(3) == greeter_moves(3) and greeter_moves(3) != greeter_moves(4)  # 단계마다 순서가 바뀐다
    svg = render_greeter(m.look_for(m.find_outfit(OUTFITS, "simple", "T03")), "모입", 3)
    frames = sum(len(GREETER_MOVES[mv]) for mv in moves)
    assert svg.count('class="g') == frames and "infinite" in svg and "prefers-reduced-motion" in svg


def test_sibling_module_is_reloaded_when_its_file_changes(tmp_path, monkeypatch):
    """실행 중인 앱이 예전 minimi.py를 들고 있어 생긴 ImportError(render_greeter) 재발 방지."""
    import importlib
    import os
    import sys

    path = tmp_path / "mj_probe.py"
    path.write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    module = m._fresh(importlib.import_module("mj_probe"))
    assert module.VALUE == 1
    assert m._fresh(module) is module  # 바뀌지 않았으면 그대로
    path.write_text("VALUE = 2\nNEW = 'render_greeter'\n", encoding="utf-8")
    stat = path.stat()
    os.utime(path, (stat.st_atime, stat.st_mtime + 5))  # 같은 초에 고쳐도 바뀐 것으로
    module = m._fresh(module)
    assert module.VALUE == 2 and module.NEW == "render_greeter"
    sys.modules.pop("mj_probe", None)


def test_weather_uses_current_minimi_and_theme():
    import minimi
    import theme

    assert m.render_greeter is minimi.render_greeter and m.render_gnb is theme.render_gnb
