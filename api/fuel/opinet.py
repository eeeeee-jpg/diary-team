"""오피넷 오픈 API 호출. API 키(OPINET_KEY)는 서버 쪽에서만 읽는다."""

import os
from pathlib import Path

import requests

BASE_URL = "https://www.opinet.co.kr/api/"
TIMEOUT = 5  # 초

PRODUCTS = {
    "B027": "휘발유",
    "D047": "경유",
    "B034": "고급휘발유",
    "K015": "LPG",
}

BRANDS = {
    "SKE": "SK에너지",
    "GSC": "GS칼텍스",
    "HDO": "HD현대오일뱅크",
    "SOL": "S-OIL",
    "RTE": "자영알뜰",
    "RTX": "고속도로알뜰",
    "NHO": "농협알뜰",
    "ETC": "자가상표",
    "E1G": "E1",
    "SKG": "SK가스",
}

RADII_M = (1000, 3000, 5000)
SORT_PRICE = 1
SORT_DISTANCE = 2

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class OpinetError(RuntimeError):
    """오피넷 호출 실패 (네트워크, 키, 응답 형식)."""


def _load_key() -> str:
    key = os.environ.get("OPINET_KEY")
    if not key and _ENV_FILE.exists():
        for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("OPINET_KEY="):
                key = line.split("=", 1)[1].strip()
                break
    if not key:
        raise OpinetError("OPINET_KEY가 설정되지 않았습니다. .env를 확인하세요.")
    return key


def _get(endpoint: str, **params) -> list[dict]:
    params = {k: v for k, v in params.items() if v is not None}
    params.update(certkey=_load_key(), out="json")
    try:
        res = requests.get(BASE_URL + endpoint, params=params, timeout=TIMEOUT)
        res.raise_for_status()
        data = res.json()
    except requests.RequestException as e:
        raise OpinetError(f"{endpoint} 호출 실패: {type(e).__name__}") from e
    except ValueError as e:
        raise OpinetError(f"{endpoint} 응답이 JSON이 아닙니다.") from e
    try:
        rows = data["RESULT"]["OIL"]
    except (KeyError, TypeError) as e:
        raise OpinetError(f"{endpoint} 응답 형식이 예상과 다릅니다.") from e
    return rows if isinstance(rows, list) else []


def around_stations(x: float, y: float, radius_m: int, prodcd: str, sort: int = SORT_PRICE) -> list[dict]:
    """KATEC 좌표 기준 반경 내 주유소."""
    rows = _get("aroundAll.do", x=f"{x:.1f}", y=f"{y:.1f}", radius=radius_m, prodcd=prodcd, sort=sort)
    return [
        {
            "id": r["UNI_ID"],
            "name": r["OS_NM"],
            "brand_code": r.get("POLL_DIV_CD", ""),
            "brand": BRANDS.get(r.get("POLL_DIV_CD", ""), "기타"),
            "price": float(r["PRICE"]),
            "distance_m": float(r["DISTANCE"]),
        }
        for r in rows
    ]


def sido_codes() -> list[dict]:
    return [{"code": r["AREA_CD"], "name": r["AREA_NM"]} for r in _get("areaCode.do")]


def sigun_codes(sido_cd: str) -> list[dict]:
    return [{"code": r["AREA_CD"], "name": r["AREA_NM"]} for r in _get("areaCode.do", area=sido_cd)]


def sido_avg(sido_cd: str | None = None, prodcd: str | None = None) -> list[dict]:
    """시도별 현재 평균가. 인자를 비우면 전체."""
    return [
        {"area_cd": r["SIDOCD"], "area_nm": r["SIDONM"], "prodcd": r["PRODCD"], "price": float(r["PRICE"])}
        for r in _get("avgSidoPrice.do", sido=sido_cd, prodcd=prodcd)
    ]


def sigun_avg(sido_cd: str, prodcd: str | None = None) -> list[dict]:
    """시도 안 시군구별 현재 평균가."""
    return [
        {"area_cd": r["SIGUNCD"], "area_nm": r["SIGUNNM"], "prodcd": r["PRODCD"], "price": float(r["PRICE"])}
        for r in _get("avgSigunPrice.do", sido=sido_cd, prodcd=prodcd)
    ]
