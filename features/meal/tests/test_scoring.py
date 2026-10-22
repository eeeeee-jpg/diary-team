from features.meal.scoring import (
    load_config, load_menus, recommend, slot_for_hour, weather_conditions,
)

CFG = load_config()
MENUS = load_menus()
RAIN = {"temp": 16, "feels_like": 15, "precip": 4.0}
HEAT = {"temp": 35, "feels_like": 38, "precip": 0}
COLD = {"temp": -8, "feels_like": -14, "precip": 0}
SNOW = {"temp": -1, "feels_like": -5, "precip": 2.0}


def names(recs):
    return [r.menu.name for r in recs]


def tags(recs):
    return [set(r.menu.tags) for r in recs]


def test_slot_for_hour():
    assert [slot_for_hour(h, CFG) for h in (7, 12, 16, 19, 2)] == [
        "breakfast", "lunch", "snack", "dinner", "dinner",
    ]


def test_conditions():
    assert weather_conditions(None, CFG) == []
    assert weather_conditions(RAIN, CFG) == ["rain"]
    assert weather_conditions(SNOW, CFG) == ["snow", "cold"]
    assert weather_conditions(HEAT, CFG) == ["heat"]


def test_rain_snow_cold_prefer_soup():
    for w in (RAIN, SNOW, COLD):
        assert all("soup" in t for t in tags(recommend(MENUS, "lunch", w, [], CFG)))


def test_heat_prefers_cold_menu():
    assert all("cold" in t for t in tags(recommend(MENUS, "lunch", HEAT, [], CFG)))


def test_no_weather_still_recommends():
    recs = recommend(MENUS, "dinner", None, [], CFG)
    assert len(recs) == 3
    assert all("저녁" in r.reason for r in recs)


def test_recent_menu_penalized():
    first = recommend(MENUS, "lunch", RAIN, [], CFG)
    again = recommend(MENUS, "lunch", RAIN, names(first), CFG)
    assert not set(names(first)) & set(names(again))


def test_reroll_gives_other_menus():
    first = recommend(MENUS, "lunch", RAIN, [], CFG, seed=0)
    second = recommend(MENUS, "lunch", RAIN, [], CFG, exclude=names(first), seed=1)
    assert not set(names(first)) & set(names(second))


def test_same_seed_is_stable():
    assert names(recommend(MENUS, "lunch", RAIN, [], CFG, seed=5)) == names(
        recommend(MENUS, "lunch", RAIN, [], CFG, seed=5)
    )


def test_reason_mentions_weather():
    assert "비 오는 점심" in recommend(MENUS, "lunch", RAIN, [], CFG)[0].reason
