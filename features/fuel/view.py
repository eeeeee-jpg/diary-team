"""JOOYOU 화면: 주변 주유소(E-1), 나의 주유 기록(E-2), 지역 평균 비교(E-3)."""

from datetime import date, datetime

import streamlit as st
from streamlit_geolocation import streamlit_geolocation

from api.fuel import opinet
from api.fuel.coords import CoordError, wgs84_to_katec
from api.fuel.opinet import PRODUCTS, OpinetError

from . import store
from .compare import KST, compare, take_snapshot, today_kst

CACHE_STATIONS = 30 * 60  # 주유소 30분
CACHE_AREAS = 24 * 60 * 60  # 지역 코드는 거의 바뀌지 않음

LOAD_FAILED = "정보를 불러오지 못했어요. 잠시 후 다시 시도해 주세요."


# ---------- 캐시된 오피넷 호출 ----------

@st.cache_data(ttl=CACHE_STATIONS, show_spinner="주변 주유소를 찾는 중…")
def _stations(x: float, y: float, radius_m: int, prodcd: str, sort: int) -> list[dict]:
    return opinet.around_stations(x, y, radius_m, prodcd, sort)


@st.cache_data(ttl=CACHE_AREAS, show_spinner=False)
def _sido_codes() -> list[dict]:
    return opinet.sido_codes()


@st.cache_data(ttl=CACHE_AREAS, show_spinner=False)
def _sigun_codes(sido_cd: str) -> list[dict]:
    return opinet.sigun_codes(sido_cd)


@st.cache_data(ttl=CACHE_STATIONS, show_spinner=False)
def _ensure_snapshot(sido_cd: str, day: str) -> None:
    """같은 시도·날짜는 30분에 한 번만 오피넷에서 평균가를 받아 저장한다."""
    take_snapshot(sido_cd, day)


# ---------- 공통 ----------

def _today() -> date:
    return datetime.now(KST).date()


def _won(value: float) -> str:
    return f"{value:,.0f}원"


def _distance(m: float) -> str:
    return f"{m:.0f}m" if m < 1000 else f"{m / 1000:.1f}km"


def _retry_button(key: str, *cached) -> None:
    if st.button("🔄 다시 시도", key=key):
        for fn in cached:
            fn.clear()
        st.rerun()


# ---------- E-1 주변 주유소 ----------

def _stations_tab(fixed_location: dict | None) -> None:
    if fixed_location:
        st.caption(f"📍 임시 위치: {fixed_location['label']} (GPS 미사용)")
        loc = {"latitude": fixed_location["lat"], "longitude": fixed_location["lng"]}
    else:
        st.caption("📍 버튼을 눌러 현재 위치 사용을 허용해 주세요. 위치는 조회에만 쓰고 저장하지 않아요.")
        loc = streamlit_geolocation() or {}

    c1, c2 = st.columns(2)
    radius = c1.radio(
        "반경", opinet.RADII_M, index=1,  # 기본 3km: 도심에서도 1km 안에 주유소가 없는 곳이 많다
        format_func=lambda m: f"{m // 1000}km", horizontal=True, key="fuel_radius",
    )
    prodcd = c2.selectbox("유종", list(PRODUCTS), format_func=PRODUCTS.get, key="fuel_prodcd")
    sort = st.radio(
        "정렬",
        (opinet.SORT_PRICE, opinet.SORT_DISTANCE),
        format_func=lambda s: "💰 가격순" if s == opinet.SORT_PRICE else "📍 거리순",
        horizontal=True,
        key="fuel_sort",
    )

    lat, lng = loc.get("latitude"), loc.get("longitude")
    if lat is None or lng is None:
        st.info("위치를 받으면 주변 주유소를 보여드릴게요.")
        return

    try:
        x, y = wgs84_to_katec(lat, lng)
    except CoordError:
        st.error("현재 위치를 주유소 검색용 좌표로 바꾸지 못했어요. 국내에서 위치를 다시 받아 주세요.")
        return
    try:
        # 10m 단위로 반올림해 같은 자리의 재조회는 캐시를 쓴다
        stations = _stations(round(x, -1), round(y, -1), radius, prodcd, sort)
    except OpinetError:
        st.error(f"주유소 {LOAD_FAILED}")
        _retry_button("fuel_retry_stations", _stations)
        return

    if not stations:
        st.info(f"반경 {radius // 1000}km 안에 {PRODUCTS[prodcd]}를 파는 주유소가 없어요. 반경을 넓혀 보세요.")
        return

    st.caption(f"{len(stations)}곳 · 가격은 오피넷 기준이에요")
    for s in stations:
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 1.4], vertical_alignment="center")
            c1.markdown(f"**{s['name']}**  \n{s['brand']}")
            c2.markdown(f"**{_won(s['price'])}**/L  \n📍 {_distance(s['distance_m'])}")
            if c3.button("✏️ 기록", key=f"fuel_pick_{s['id']}", help="이 주유소로 주유 기록 쓰기"):
                st.session_state.fuel_prefill = {
                    "id": s["id"], "name": s["name"], "prodcd": prodcd, "price": s["price"],
                }
                st.session_state.fuel_form_n = st.session_state.get("fuel_form_n", 0) + 1
                st.toast("📒 '나의 주유 기록' 탭에 주유소를 채워 뒀어요")


# ---------- E-2 / E-3 나의 주유 기록 ----------

def _region_picker() -> tuple[str, str] | None:
    try:
        sidos = _sido_codes()
    except OpinetError:
        st.error(f"지역 {LOAD_FAILED}")
        _retry_button("fuel_retry_sido", _sido_codes)
        return None

    c1, c2 = st.columns(2)
    names = {a["code"]: a["name"] for a in sidos}
    sido_cd = c1.selectbox("시도", list(names), format_func=names.get, key="fuel_sido")
    try:
        siguns = _sigun_codes(sido_cd)
    except OpinetError:
        st.error(f"시군구 {LOAD_FAILED}")
        _retry_button("fuel_retry_sigun", _sigun_codes)
        return None
    names = {a["code"]: a["name"] for a in siguns}
    sigun_cd = c2.selectbox("시군구", list(names), format_func=names.get, key=f"fuel_sigun_{sido_cd}")
    return sido_cd, sigun_cd


def _today_averages(sido_cd: str, sigun_cd: str) -> None:
    day = today_kst()
    try:
        _ensure_snapshot(sido_cd, day)
    except OpinetError:
        st.warning("오늘 지역 평균가를 받지 못했어요. 오늘 기록은 비교 데이터가 없을 수 있어요.")
        return
    cols = st.columns(len(PRODUCTS))
    for col, (code, name) in zip(cols, PRODUCTS.items()):
        avg = store.get_avg(day, "sigun", sigun_cd, code)
        col.metric(f"오늘 {name} 평균", _won(avg["price"]) if avg else "—")


def _new_record_form(sido_cd: str, sigun_cd: str) -> None:
    n = st.session_state.get("fuel_form_n", 0)
    pre = st.session_state.get("fuel_prefill", {})
    codes = list(PRODUCTS)

    with st.expander("✏️ 새 주유 기록", expanded=bool(pre)):
        day = st.date_input("날짜", value=_today(), max_value=_today(), key=f"fuel_new_date_{n}")
        name = st.text_input("주유소명", value=pre.get("name", ""), key=f"fuel_new_name_{n}")
        prodcd = st.selectbox(
            "유종", codes, index=codes.index(pre.get("prodcd", codes[0])),
            format_func=PRODUCTS.get, key=f"fuel_new_prod_{n}",
        )
        c1, c2 = st.columns(2)
        price = c1.number_input(
            "리터당 가격(원)", min_value=0.0, max_value=5000.0, value=float(pre.get("price", 0)),
            step=1.0, format="%.0f", key=f"fuel_new_price_{n}",
        )
        liters = c2.number_input(
            "주유량(L)", min_value=0.0, max_value=200.0, value=0.0, step=0.1, format="%.2f",
            key=f"fuel_new_liters_{n}",
        )
        st.markdown(f"**총액: {_won(round(price * liters))}**")

        if st.button("💾 저장", type="primary", key=f"fuel_new_save_{n}"):
            if not name.strip() or price <= 0 or liters <= 0:
                st.warning("주유소명, 리터당 가격, 주유량을 모두 입력해 주세요.")
                return
            store.add_record(
                date=day.isoformat(),
                station_name=name.strip(),
                station_id=pre.get("id") if name == pre.get("name") else None,
                prodcd=prodcd,
                price_per_l=price,
                liters=liters,
                sido_cd=sido_cd,
                sigun_cd=sigun_cd,
            )
            st.session_state.fuel_form_n = n + 1
            st.session_state.pop("fuel_prefill", None)
            st.session_state.fuel_flash = "📒 기록했어요!"
            st.rerun()


def _monthly(records: list[dict]) -> None:
    st.subheader("🗓️ 월별 합계")
    st.dataframe(
        [
            {"월": m["month"], "횟수": m["count"], "주유량": f"{m['liters']:.1f}L", "총액": _won(m["total"])}
            for m in store.monthly_totals(records)
        ],
        hide_index=True,
        width="stretch",
    )


def _comparison(record: dict) -> None:
    cmp = compare(record)
    if cmp is None:
        st.info("📭 비교 데이터 없음 — 그날의 지역 평균가가 저장되어 있지 않아요.")
        return
    c1, c2 = st.columns(2)
    c1.metric("내가 낸 가격", _won(cmp.my_price))
    c2.metric(
        f"그날 {cmp.area_nm} 평균",
        _won(cmp.avg_price),
        delta=f"{cmp.diff:+,.0f}원 ({cmp.pct:+.1f}%)",
        delta_color="inverse",  # 내가 더 싸면 초록
    )
    st.markdown(cmp.message)


def _edit_form(record: dict) -> None:
    rid = record["id"]
    codes = list(PRODUCTS)
    with st.form(key=f"fuel_edit_{rid}"):
        day = st.date_input("날짜", value=date.fromisoformat(record["date"]), max_value=_today())
        name = st.text_input("주유소명", value=record["station_name"])
        prodcd = st.selectbox("유종", codes, index=codes.index(record["prodcd"]), format_func=PRODUCTS.get)
        c1, c2 = st.columns(2)
        price = c1.number_input("리터당 가격(원)", min_value=0.0, max_value=5000.0,
                                value=float(record["price_per_l"]), step=1.0, format="%.0f")
        liters = c2.number_input("주유량(L)", min_value=0.0, max_value=200.0,
                                 value=float(record["liters"]), step=0.1, format="%.2f")
        if st.form_submit_button("수정 저장"):
            if not name.strip() or price <= 0 or liters <= 0:
                st.warning("주유소명, 리터당 가격, 주유량을 모두 입력해 주세요.")
                return
            store.update_record(rid, date=day.isoformat(), station_name=name.strip(), prodcd=prodcd,
                                price_per_l=price, liters=liters)
            st.session_state.fuel_flash = "✏️ 수정했어요!"
            st.rerun()

    confirm = st.checkbox("이 기록을 삭제할게요", key=f"fuel_del_ok_{rid}")
    if st.button("🗑️ 삭제", key=f"fuel_del_{rid}", disabled=not confirm):
        store.delete_record(rid)
        st.session_state.fuel_flash = "🗑️ 삭제했어요."
        st.rerun()


def _record_list(records: list[dict]) -> None:
    st.subheader("📒 기록")
    for r in records:
        label = f"{r['date']} · {r['station_name']} · {PRODUCTS.get(r['prodcd'], r['prodcd'])} · {_won(store.total_price(r))}"
        with st.expander(label):
            st.caption(f"{_won(r['price_per_l'])}/L × {r['liters']:.2f}L")
            _comparison(r)
            st.divider()
            _edit_form(r)


def _records_tab() -> None:
    if flash := st.session_state.pop("fuel_flash", None):
        st.success(flash)

    st.caption("평균가 비교에 쓸 지역을 골라 주세요. 새 기록은 이 지역으로 저장돼요.")
    region = _region_picker()
    if region is None:
        return
    sido_cd, sigun_cd = region
    _today_averages(sido_cd, sigun_cd)
    _new_record_form(sido_cd, sigun_cd)

    records = store.list_records()
    if not records:
        st.info("아직 주유 기록이 없어요. 첫 주유를 기록해 보세요! ⛽")
        return
    _monthly(records)
    _record_list(records)


def page(fixed_location: dict | None = None) -> None:
    """fixed_location을 주면 GPS 대신 그 위치·지역을 쓴다(개발용).
    {"label", "lat", "lng", "sido_cd", "sigun_cd"}"""
    if fixed_location:
        st.session_state.setdefault("fuel_sido", fixed_location["sido_cd"])
        st.session_state.setdefault(f"fuel_sigun_{fixed_location['sido_cd']}", fixed_location["sigun_cd"])

    st.title("👑 JOOYOU")
    st.caption("주변 주유소 가격을 보고, 내가 낸 가격을 그날 지역 평균과 비교해요.")
    stations_tab, records_tab = st.tabs(["⛽ 주변 주유소", "📒 나의 주유 기록"])
    with stations_tab:
        _stations_tab(fixed_location)
    with records_tab:
        _records_tab()
