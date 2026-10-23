"""추천 점수 계산. Streamlit에 의존하지 않는 순수 함수만 둔다."""

import json
import random
import tomllib
from pathlib import Path
from typing import Any, Iterable, Mapping

from .models import Menu, Recommendation

_DATA = Path(__file__).parent / "data"

Weather = Mapping[str, Any]


def load_config(path: Path = _DATA / "recommend.toml") -> dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def load_menus(path: Path = _DATA / "menus.json") -> list[Menu]:
    with path.open(encoding="utf-8") as f:
        return [Menu(m["name"], tuple(m["tags"]), tuple(m["slots"])) for m in json.load(f)]


def slot_for_hour(hour: int, config: Mapping[str, Any]) -> str:
    """시각(0~23)으로 끼니를 판별한다. 새벽은 전날 저녁 범위에 들어간다."""
    for slot, (start, end) in config["slots"].items():
        if start <= hour < end or start <= hour + 24 < end:
            return slot
    return "dinner"


def weather_conditions(weather: Weather | None, config: Mapping[str, Any]) -> list[str]:
    """날씨에서 해당하는 조건(rain/snow/cold/heat)을 우선순위 순으로 돌려준다."""
    if weather is None:
        return []
    th = config["weather_thresholds"]
    conditions: list[str] = []
    if weather.get("precip", 0) >= th["rain_mm"]:
        conditions.append("snow" if weather.get("temp", 10) <= th["snow_temp_max"] else "rain")
    feels = weather.get("feels_like", weather.get("temp", 15))
    if feels <= th["cold_feels_like"]:
        conditions.append("cold")
    if feels >= th["heat_feels_like"]:
        conditions.append("heat")
    return conditions


def score_menu(
    menu: Menu,
    slot: str,
    conditions: Iterable[str],
    recent_names: Iterable[str],
    config: Mapping[str, Any],
) -> float:
    cfg = config["score"]
    score = cfg["slot_match"] if slot in menu.slots else 0.0
    for cond in conditions:
        for tag, weight in config["weather_weights"].get(cond, {}).items():
            if tag in menu.tags:
                score += weight
    if menu.name in set(recent_names):
        score -= cfg["recent_penalty"]
    return score


def _reason(menu: Menu, slot: str, conditions: list[str], config: Mapping[str, Any]) -> str:
    label = config["slot_labels"][slot]
    for cond in conditions:
        weights = config["weather_weights"].get(cond, {})
        if any(weights.get(tag, 0) > 0 for tag in menu.tags):
            return config["reasons"][cond].format(slot=label)
    return config["reasons"]["slot"].format(slot=label)


def recommend(
    menus: Iterable[Menu],
    slot: str,
    weather: Weather | None,
    recent_names: Iterable[str],
    config: Mapping[str, Any],
    exclude: Iterable[str] = (),
    seed: int = 0,
) -> list[Recommendation]:
    """점수 상위 메뉴를 돌려준다. 동점은 seed로 섞어 '다시 추천'마다 달라지게 한다.

    exclude에 든 메뉴는 후보에서 뺀다. 후보가 모자라면 exclude를 무시하고 다시 고른다.
    """
    menus = [m for m in menus if slot in m.slots]
    conditions = weather_conditions(weather, config)
    recent = list(recent_names)
    count = config["score"]["count"]
    excluded = set(exclude)
    pool = [m for m in menus if m.name not in excluded]
    if len(pool) < count:
        pool = menus
    rng = random.Random(seed)
    scored = [(score_menu(m, slot, conditions, recent, config), rng.random(), m) for m in pool]
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [
        Recommendation(m, s, _reason(m, slot, conditions, config)) for s, _, m in scored[:count]
    ]
