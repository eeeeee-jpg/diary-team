"""손님 사진 API (둘 다 키 없이 호출).

- 강아지: Dog CEO  https://dog.ceo/api/breed/{품종 경로}/images/random
- 고양이: TheCatAPI https://api.thecatapi.com/v1/images/{사진 id}
  TheCatAPI는 키 없이 품종 목록(/v1/breeds)을 주지 않아(403), 품종별 사진 id를 config.toml에 직접 적었다.

실패하면 None을 돌려주고, 화면은 SVG 일러스트로 대신한다.
"""

from __future__ import annotations

import logging

import requests
import streamlit as st

from ..models import Breed

log = logging.getLogger("guest")

TIMEOUT = 5  # 초 (팀 규칙)


def _get_json(url: str) -> dict | None:
    try:
        res = requests.get(url, timeout=TIMEOUT)
        res.raise_for_status()
        return res.json()
    except (requests.RequestException, ValueError) as e:
        log.warning("guest 사진 API 실패 %s: %s", url, e)
        return None


def guest_dog_photo(path: str) -> str | None:
    """매번 다른 사진이 오도록 캐시하지 않는다."""
    data = _get_json(f"https://dog.ceo/api/breed/{path}/images/random")
    if data and data.get("status") == "success":
        return data.get("message")
    return None


@st.cache_data(ttl=86400, show_spinner=False)
def guest_cat_photo(image_id: str) -> str | None:
    data = _get_json(f"https://api.thecatapi.com/v1/images/{image_id}")
    return data.get("url") if data else None


def fetch_photo(breed: Breed) -> str | None:
    return guest_dog_photo(breed.photo) if breed.species == "dog" else guest_cat_photo(breed.photo)
