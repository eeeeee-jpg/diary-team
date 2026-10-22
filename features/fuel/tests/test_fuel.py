"""저장소 루트에서 실행: python -m unittest features.fuel.tests.test_fuel"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_tmp = tempfile.TemporaryDirectory()
os.environ["FUEL_DB_PATH"] = str(Path(_tmp.name) / "test.db")

from api.fuel.coords import CoordError, katec_to_wgs84, wgs84_to_katec  # noqa: E402
from features.fuel import compare, store, summary  # noqa: E402


def _record(**over):
    r = dict(date="2026-10-22", station_name="테스트주유소", station_id=None, prodcd="B027",
             price_per_l=1850.0, liters=30.0, sido_cd="01", sigun_cd="0123")
    r.update(over)
    return r


class FuelTestCase(unittest.TestCase):
    def setUp(self):
        store.DB_PATH.unlink(missing_ok=True)


class CoordsTest(FuelTestCase):
    def test_round_trip(self):
        lat, lng = katec_to_wgs84(314996.159, 544938.50758)
        x, y = wgs84_to_katec(lat, lng)
        self.assertAlmostEqual(x, 314996.159, places=1)
        self.assertAlmostEqual(y, 544938.50758, places=1)

    def test_outside_korea(self):
        with self.assertRaises(CoordError):
            wgs84_to_katec(35.68, 139.76)  # 도쿄
        with self.assertRaises(CoordError):
            wgs84_to_katec(None, None)


class StoreTest(FuelTestCase):
    def test_crud_and_totals(self):
        a = store.add_record(**_record())
        store.add_record(**_record(date="2026-09-30", liters=10.0))
        self.assertEqual([r["date"] for r in store.list_records()], ["2026-10-22", "2026-09-30"])
        self.assertEqual(store.total_price(store.list_records()[0]), 55500)

        store.update_record(a, liters=40.0)
        months = store.monthly_totals(store.list_records())
        self.assertEqual(months[0], {"month": "2026-10", "count": 1, "liters": 40.0, "total": 74000})
        self.assertEqual(months[1]["total"], 18500)

        store.delete_record(a)
        self.assertEqual(len(store.list_records()), 1)


class CompareTest(FuelTestCase):
    def _snap(self, level, area_cd, price, date="2026-10-22"):
        store.save_snapshots(date, level, [{"area_cd": area_cd, "area_nm": f"지역{area_cd}", "prodcd": "B027", "price": price}])

    def test_no_data(self):
        self.assertIsNone(compare.compare(_record()))

    def test_sigun_preferred_then_sido(self):
        self._snap("sido", "01", 1900.0)
        self.assertEqual(compare.compare(_record()).area_level, "sido")
        self._snap("sigun", "0123", 1880.0)
        c = compare.compare(_record())
        self.assertEqual((c.area_level, c.avg_price), ("sigun", 1880.0))
        self.assertAlmostEqual(c.diff, -30.0)
        self.assertAlmostEqual(c.pct, -30 / 1880 * 100)
        self.assertEqual(c.verdict, "cheaper")
        self.assertIn("싸게", c.message)

    def test_other_date_has_no_data(self):
        self._snap("sigun", "0123", 1880.0, date="2026-10-21")
        self.assertIsNone(compare.compare(_record()))

    def test_verdicts(self):
        self.assertEqual(compare.Comparison("sigun", "x", 1850.0, 1851.0).verdict, "same")
        self.assertEqual(compare.Comparison("sigun", "x", 1850.0, 1900.0).verdict, "pricier")

    def test_take_snapshot_saves_both_levels(self):
        sigun = [{"area_cd": "0123", "area_nm": "서울 강남구", "prodcd": "B027", "price": 1880.0}]
        sido = [{"area_cd": "01", "area_nm": "서울", "prodcd": "B027", "price": 1900.0}]
        with mock.patch.object(compare.opinet, "sigun_avg", return_value=sigun), \
             mock.patch.object(compare.opinet, "sido_avg", return_value=sido):
            compare.take_snapshot("01", "2026-10-22")
        self.assertEqual(store.get_avg("2026-10-22", "sigun", "0123", "B027")["price"], 1880.0)
        self.assertEqual(store.get_avg("2026-10-22", "sido", "01", "B027")["price"], 1900.0)


class SummaryTest(FuelTestCase):
    def test_empty(self):
        self.assertEqual(summary.get_today_summary()["status"], "empty")

    def test_this_month(self):
        today = compare.today_kst()
        store.add_record(**_record(date=today))
        s = summary.get_today_summary()
        self.assertEqual(s["value"], "이번 달 1회 · 55,500원")
        self.assertEqual(s["status"], "no_data")


if __name__ == "__main__":
    unittest.main()
