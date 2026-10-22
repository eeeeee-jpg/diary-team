from . import storage
from .clock import today
from .models import LOG_SLOTS

ROUTE = "meal"


def page() -> None:
    from .view import render

    render()


def get_today_summary() -> dict[str, str]:
    """홈 카드용 요약. 오늘 끼니 3칸 중 몇 칸을 채웠는지 돌려준다."""
    done = len(storage.get_logs(today()))
    total = len(LOG_SLOTS)
    return {
        "title": "오늘의 한 끼",
        "value": f"{done}/{total}",
        "status": "done" if done == total else ("progress" if done else "empty"),
    }
