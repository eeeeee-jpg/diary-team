"""위경도(WGS84) ↔ 오피넷 KATEC 좌표 변환."""

from pyproj import Transformer

KATEC = (
    "+proj=tmerc +lat_0=38 +lon_0=128 +k=0.9999 +x_0=400000 +y_0=600000 "
    "+ellps=bessel +units=m +no_defs "
    "+towgs84=-115.80,474.99,674.11,1.16,-2.31,-1.63,6.43"
)

_to_katec = Transformer.from_crs("EPSG:4326", KATEC, always_xy=True)
_to_wgs84 = Transformer.from_crs(KATEC, "EPSG:4326", always_xy=True)

# 대한민국 대략 범위 (제주~독도 포함)
_LAT_RANGE = (33.0, 38.7)
_LNG_RANGE = (124.5, 132.0)


class CoordError(ValueError):
    """변환할 수 없는 좌표."""


def wgs84_to_katec(lat: float, lng: float) -> tuple[float, float]:
    if lat is None or lng is None:
        raise CoordError("위치 정보가 없습니다.")
    if not (_LAT_RANGE[0] <= lat <= _LAT_RANGE[1] and _LNG_RANGE[0] <= lng <= _LNG_RANGE[1]):
        raise CoordError("대한민국 밖의 좌표입니다.")
    x, y = _to_katec.transform(lng, lat)
    return x, y


def katec_to_wgs84(x: float, y: float) -> tuple[float, float]:
    lng, lat = _to_wgs84.transform(x, y)
    return lat, lng
