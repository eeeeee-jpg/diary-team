"""홈 카드용 요약."""

from . import store
from .compare import compare, today_kst


def get_today_summary() -> dict:
    records = store.list_records()
    if not records:
        return {"title": "JOOYOU", "value": "아직 주유 기록이 없어요", "status": "empty"}

    month = today_kst()[:7]
    this_month = [r for r in records if r["date"].startswith(month)]
    total = sum(store.total_price(r) for r in this_month)
    value = f"이번 달 {len(this_month)}회 · {total:,}원"

    cmp = compare(records[0])
    status = cmp.verdict if cmp else "no_data"
    return {"title": "JOOYOU", "value": value, "status": status}
