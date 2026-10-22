"""카카오 로컬 API 클라이언트. 키는 st.secrets에서만 읽고 어디에도 출력하지 않는다."""

import requests
import streamlit as st

from ..models import Restaurant

_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
_RESTAURANT_CATEGORY = "FD6"
_MAX_RESULTS = 10


class KakaoError(Exception):
    """사용자에게 보여줄 수 있는 메시지만 담는다(키 값 금지)."""


def _api_key() -> str:
    try:
        key = st.secrets["KAKAO_REST_KEY"]
    except (KeyError, FileNotFoundError):
        raise KakaoError("카카오 API 키가 설정되지 않았어요") from None
    return str(key)


def _search(query: str, lat: float, lng: float, radius_m: int) -> list[Restaurant]:
    try:
        res = requests.get(
            _URL,
            headers={"Authorization": f"KakaoAK {_api_key()}"},
            params={
                "query": query,
                "x": lng,
                "y": lat,
                "radius": radius_m,
                "sort": "distance",
                "size": _MAX_RESULTS,
                "category_group_code": _RESTAURANT_CATEGORY,
            },
            timeout=5,
        )
        res.raise_for_status()
        docs = res.json().get("documents", [])
    except requests.RequestException as e:
        # 요청 URL·헤더가 담길 수 있어 원문 메시지는 버리고 상태 코드만 남긴다
        status = getattr(getattr(e, "response", None), "status_code", None)
        raise KakaoError(
            f"식당 정보를 불러오지 못했어요 ({status})" if status else "식당 정보를 불러오지 못했어요"
        ) from None
    except ValueError:
        raise KakaoError("식당 정보를 해석하지 못했어요") from None
    return [
        Restaurant(
            name=d["place_name"],
            distance_m=int(d.get("distance") or 0),
            category=d.get("category_name", "").split(" > ")[-1],
            map_url=d.get("place_url", ""),
        )
        for d in docs
    ]


@st.cache_data(ttl=600, show_spinner=False)
def meal_search_restaurants(query: str, lat: float, lng: float, radius_m: int) -> list[Restaurant]:
    """반경 안 식당을 거리순 최대 10개 돌려준다. 실패하면 KakaoError(캐시되지 않음)."""
    return _search(query, lat, lng, radius_m)
