"""날씨 + 코디 (MOIPJI). 병합 시 app.py가 가져다 쓰는 것만 내보낸다."""

from .weather import SERVICE_ROUTE, get_today_summary, get_weather, page

ROUTE = SERVICE_ROUTE  # "weather" (theme.SERVICES와 같은 값)

__all__ = ["page", "ROUTE", "get_today_summary", "get_weather"]
