from datetime import date, datetime
from zoneinfo import ZoneInfo

_TZ = ZoneInfo("Asia/Seoul")


def now() -> datetime:
    return datetime.now(_TZ)


def today() -> date:
    return now().date()
