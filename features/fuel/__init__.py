"""JOOYOU. 밖으로는 page, routes, get_today_summary만 내보낸다."""

from .summary import get_today_summary
from .view import page

routes = [{"path": "/fuel", "title": "JOOYOU", "page": page}]

__all__ = ["page", "routes", "get_today_summary"]
