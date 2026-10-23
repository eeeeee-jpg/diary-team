"""끼니 기록 이벤트 발행.

`meal_logged { meal_log_id, slot, date }`. 서비스 사이 전달 방식은 아직 미정(PRD 13장)이다.
확정되기 전까지는 같은 프로세스 안의 구독자 목록에만 알린다. 구독자가 없어도 에러 없이 끝난다.
"""

from collections.abc import Callable
from typing import Any

from .models import MealLog

EVENT_NAME = "meal_logged"

_subscribers: list[Callable[[dict[str, Any]], None]] = []


def subscribe(callback: Callable[[dict[str, Any]], None]) -> None:
    _subscribers.append(callback)


def emit_meal_logged(log: MealLog) -> None:
    payload = {"meal_log_id": log.id, "slot": log.slot, "date": log.date}
    for callback in list(_subscribers):
        try:
            callback(payload)
        except Exception:  # 수신자 오류가 기록 저장을 막지 않게 한다
            pass
