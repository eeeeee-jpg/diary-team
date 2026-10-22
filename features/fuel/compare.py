"""내가 낸 가격 vs 그날 지역 평균 (E-3), 일별 평균가 스냅샷."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from api.fuel import opinet

from . import store

KST = timezone(timedelta(hours=9))
SAME_PRICE_WON = 1  # 이 금액 이하 차이는 "평균과 같아요"


def today_kst() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


def take_snapshot(sido_cd: str, date: str | None = None) -> None:
    """오늘의 시도·시군구 평균가(전 유종)를 저장한다. 오피넷은 '현재' 평균만 주므로 오늘 날짜로만 쌓는다."""
    date = date or today_kst()
    store.save_snapshots(date, "sigun", opinet.sigun_avg(sido_cd))
    store.save_snapshots(date, "sido", opinet.sido_avg(sido_cd))


@dataclass
class Comparison:
    area_level: str  # 'sigun' | 'sido'
    area_nm: str
    avg_price: float
    my_price: float

    @property
    def diff(self) -> float:
        return self.my_price - self.avg_price

    @property
    def pct(self) -> float:
        return self.diff / self.avg_price * 100

    @property
    def verdict(self) -> str:
        if abs(self.diff) <= SAME_PRICE_WON:
            return "same"
        return "cheaper" if self.diff < 0 else "pricier"

    @property
    def message(self) -> str:
        won, pct = f"{abs(self.diff):,.0f}원", f"{abs(self.pct):.1f}%"
        return {
            "cheaper": f"🎀 평균보다 {won}({pct}) 싸게 넣었어요! 알뜰 공주님 👑",
            "pricier": f"🥺 평균보다 {won}({pct}) 비싸게 넣었어요. 다음엔 더 싼 곳을 찾아봐요",
            "same": "⭐ 평균과 거의 같은 가격이에요",
        }[self.verdict]


def compare(record: dict) -> Comparison | None:
    """시군구 평균을 먼저 쓰고, 없으면 시도 평균. 둘 다 없으면 None(비교 데이터 없음)."""
    for level, area_cd in (("sigun", record["sigun_cd"]), ("sido", record["sido_cd"])):
        avg = store.get_avg(record["date"], level, area_cd, record["prodcd"])
        if avg:
            return Comparison(level, avg["area_nm"], avg["price"], record["price_per_l"])
    return None
