"""밥때 손님 데이터 구조 (PRD 7장 Data Model)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, NotRequired, TypedDict

Species = Literal["dog", "cat"]
Rarity = Literal["common", "rare", "legendary"]
Slot = Literal["breakfast", "lunch", "dinner"]


@dataclass(frozen=True)
class Breed:
    """손님 품종 마스터 데이터 (`Guest`)"""

    id: str
    species: Species
    name: str
    rarity: Rarity
    description: str
    photo: str  # 강아지: Dog CEO 품종 경로, 고양이: TheCatAPI 사진 id
    fur: str
    accent: str
    ear: Literal["up", "down", "fold"]


class MealLoggedEvent(TypedDict):
    """한 끼 서비스가 보내는 끼니 기록 이벤트 (병합 계약)"""

    meal_log_id: str
    slot: Slot
    date: str  # YYYY-MM-DD
    photo: NotRequired[bytes | None]  # 밥상 사진 원본 (선택). 팀원 A에게 추가 요청할 필드


@dataclass
class GuestVisit:
    """같은 날 같은 끼니에는 1건만 생긴다."""

    id: str
    meal_log_id: str
    breed_id: str
    date: str
    slot: Slot
    visited_at: str
    seen: bool = False  # 방문 연출을 사용자가 확인했는지
    image_url: str | None = None  # 이번에 찾아온 손님 사진. 불러오지 못하면 None
    meal_photo: bytes | None = None  # 이 끼니에 내가 올린 밥상 사진 (줄인 JPEG)


@dataclass
class CollectionCard:
    breed_id: str
    first_met_at: str
    met_count: int
    loyalty_level: int
    image_url: str | None = None  # 도감에 보여 줄 사진 (가장 최근에 만난 사진)


class TodaySummary(TypedDict):
    """홈 요약 카드 (병합 계약 `get_today_summary()`)"""

    title: str
    value: str
    status: Literal["empty", "in_progress", "done"]
