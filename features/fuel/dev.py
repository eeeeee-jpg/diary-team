"""단독 실행: 저장소 루트에서 `streamlit run features/fuel/dev.py`"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

from features.fuel import page  # noqa: E402

# 임시: GPS 없이 서울 강남구(강남구청)로 고정. None으로 바꾸면 GPS를 쓴다.
DEV_LOCATION = {"label": "서울 강남구", "lat": 37.5172, "lng": 127.0473, "sido_cd": "01", "sigun_cd": "0113"}

st.set_page_config(page_title="JOOYOU", page_icon="⛽")
page(fixed_location=DEV_LOCATION)
