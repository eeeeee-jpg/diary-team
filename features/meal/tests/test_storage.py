from datetime import date

import pytest

from features.meal import events, storage

D = date(2026, 10, 22)


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "meal.db")


def test_overwrite_keeps_id():
    a, created = storage.save_log(D, "lunch", "김치찌개", "manual")
    b, created2 = storage.save_log(D, "lunch", "냉면", "recommend")
    assert created and not created2
    assert a.id == b.id and a.created_at == b.created_at
    assert storage.get_logs(D)["lunch"].menu_name == "냉면"
    assert len(storage.get_logs(D)) == 1


def test_delete_then_record_again():
    storage.save_log(D, "dinner", "삼겹살", "manual")
    storage.delete_log(D, "dinner")
    assert storage.get_logs(D) == {}


def test_snack_not_recordable():
    with pytest.raises(ValueError):
        storage.save_log(D, "snack", "붕어빵", "manual")


def test_recent_names_window():
    storage.save_log(date(2026, 10, 19), "lunch", "옛날메뉴", "manual")
    storage.save_log(date(2026, 10, 20), "lunch", "최근메뉴", "manual")
    assert storage.recent_menu_names(D, 3) == ["최근메뉴"]


def test_emit_without_subscribers_is_safe():
    log, _ = storage.save_log(D, "breakfast", "토스트", "manual")
    events.emit_meal_logged(log)
