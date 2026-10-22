from dataclasses import dataclass
from typing import Literal

Slot = Literal["breakfast", "lunch", "dinner"]
Source = Literal["recommend", "manual"]

LOG_SLOTS: tuple[Slot, ...] = ("breakfast", "lunch", "dinner")


@dataclass(frozen=True)
class MealLog:
    id: str
    date: str  # YYYY-MM-DD
    slot: Slot
    menu_name: str
    source: Source
    created_at: str  # ISO 8601


@dataclass(frozen=True)
class Menu:
    name: str
    tags: tuple[str, ...]
    slots: tuple[str, ...]


@dataclass(frozen=True)
class Recommendation:
    menu: Menu
    score: float
    reason: str


@dataclass(frozen=True)
class Restaurant:
    name: str
    distance_m: int
    category: str
    map_url: str
