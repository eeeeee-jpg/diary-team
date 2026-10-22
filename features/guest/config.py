"""config.toml을 읽어 상수로 내놓는다."""

from __future__ import annotations

import tomllib
from pathlib import Path

from .models import Breed, Rarity, Slot

_raw = tomllib.loads((Path(__file__).with_name("config.toml")).read_text(encoding="utf-8"))

RARITY_WEIGHTS: dict[Rarity, int] = _raw["rarity_weights"]
RARITY_LABELS: dict[Rarity, str] = _raw["rarity_labels"]
LOYALTY_LEVELS: list[dict] = sorted(_raw["loyalty_levels"], key=lambda lv: lv["min_count"])
BREEDS: list[Breed] = [Breed(**b) for b in _raw["breeds"]]
BREED_BY_ID: dict[str, Breed] = {b.id: b for b in BREEDS}

SLOTS: tuple[Slot, ...] = ("breakfast", "lunch", "dinner")
SLOT_LABELS: dict[Slot, str] = {"breakfast": "아침", "lunch": "점심", "dinner": "저녁"}
SPECIES_LABELS = {"dog": "강아지", "cat": "고양이"}
