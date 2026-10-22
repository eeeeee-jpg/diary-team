"""순수 로직 테스트 (표준 라이브러리 unittest).

실행: python -m unittest discover -s features/guest/tests -t .
"""

import random
import unittest
from datetime import date

from features.guest.config import BREEDS
from features.guest.logic import (
    apply_visit,
    build_summary,
    compute_streak,
    day_count,
    loyalty_of,
    pick_breed,
    recent_days,
)
from features.guest.models import GuestVisit


def visit(day: str, slot: str) -> GuestVisit:
    return GuestVisit(id=f"{day}-{slot}", meal_log_id="mock", breed_id="dog_shiba", date=day, slot=slot, visited_at=day)


def full_day(day: str) -> list[GuestVisit]:
    return [visit(day, s) for s in ("breakfast", "lunch", "dinner")]


class BreedTest(unittest.TestCase):
    def test_breeds_are_40_with_unique_ids(self):
        self.assertEqual(len(BREEDS), 40)
        self.assertEqual(sum(b.species == "dog" for b in BREEDS), 20)
        self.assertEqual(len({b.id for b in BREEDS}), 40)
        self.assertEqual([sum(b.rarity == r for b in BREEDS) for r in ("common", "rare", "legendary")], [22, 14, 4])

    def test_pick_follows_weights(self):
        only_legendary = {"common": 0, "rare": 0, "legendary": 1}
        self.assertEqual(pick_breed(BREEDS, only_legendary).rarity, "legendary")
        rng = random.Random(1)
        n = 20000
        legendary = sum(pick_breed(BREEDS, rng=rng).rarity == "legendary" for _ in range(n))
        self.assertAlmostEqual(legendary / n, 0.05, delta=0.015)


class LoyaltyTest(unittest.TestCase):
    def test_levels_at_1_3_7_15(self):
        self.assertEqual([loyalty_of(n).level for n in (0, 1, 2, 3, 7, 15, 30)], [0, 1, 1, 2, 3, 4, 4])
        self.assertEqual(loyalty_of(2).remaining, 1)
        self.assertIsNone(loyalty_of(15).remaining)

    def test_apply_visit(self):
        card, unlocked, up = apply_visit(None, "dog_shiba", "t1")
        self.assertEqual((card.met_count, unlocked, up), (1, True, False))
        card, _, _ = apply_visit(card, "dog_shiba", "t2")
        card, unlocked, up = apply_visit(card, "dog_shiba", "t3")
        self.assertEqual((card.met_count, unlocked, up, card.first_met_at), (3, False, True, "t1"))


class StreakTest(unittest.TestCase):
    def test_counts_only_full_days(self):
        visits = [
            *full_day("2026-10-18"), *full_day("2026-10-19"), *full_day("2026-10-20"),  # 3일 연속 (최고)
            visit("2026-10-21", "lunch"),                                                # 하루 놓침
            *full_day("2026-10-22"),
        ]
        self.assertEqual(compute_streak(visits, date(2026, 10, 22)), (1, 3))
        self.assertEqual(compute_streak(visits, date(2026, 10, 23)), (1, 3))  # 오늘 아직이면 어제까지
        self.assertEqual(compute_streak(visits, date(2026, 10, 24)), (0, 3))

    def test_crosses_month_end(self):
        visits = full_day("2026-10-31") + full_day("2026-11-01")
        self.assertEqual(compute_streak(visits, date(2026, 11, 1)), (2, 2))


class DayTest(unittest.TestCase):
    def test_day_count_starts_at_first_visit(self):
        self.assertEqual(day_count([], date(2026, 10, 22)), 0)
        visits = [visit("2026-10-20", "lunch"), visit("2026-10-22", "dinner")]
        self.assertEqual(day_count(visits, date(2026, 10, 22)), 3)

    def test_recent_days(self):
        visits = [visit("2026-10-22", "lunch"), visit("2026-10-22", "dinner"), visit("2026-10-16", "lunch")]
        days = recent_days(visits, date(2026, 10, 22))
        self.assertEqual(len(days), 7)
        self.assertEqual(days[0], (date(2026, 10, 16), {"lunch"}))
        self.assertEqual(days[-1], (date(2026, 10, 22), {"lunch", "dinner"}))
        self.assertEqual(days[3][1], set())


class SummaryTest(unittest.TestCase):
    def test_summary(self):
        self.assertEqual(build_summary(0, 0, 20)["status"], "empty")
        self.assertEqual(
            build_summary(2, 5, 20),
            {"title": "밥때 손님", "value": "오늘 손님 2/3 · 도감 5/20", "status": "in_progress"},
        )
        self.assertEqual(build_summary(3, 5, 20)["status"], "done")


if __name__ == "__main__":
    unittest.main()
