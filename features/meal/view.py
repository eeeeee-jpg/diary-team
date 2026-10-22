"""오늘의 한 끼 화면. set_page_config는 부르지 않는다(dev.py·app.py에서만)."""

import streamlit as st

from . import events, storage
from .clock import now, today
from .clients.kakao_local import KakaoError, meal_search_restaurants
from .models import LOG_SLOTS, MealLog, Recommendation
from .regions import DEFAULT_REGION, REGIONS
from .scoring import load_config, load_menus, recommend, slot_for_hour, weather_conditions
from .weather_source import get_weather

_CONFIG = load_config()
_MENUS = load_menus()
_LABELS: dict[str, str] = _CONFIG["slot_labels"]
_RADIUS_NEAR = 1000
_RADIUS_FAR = 3000

K_SLOT = "meal_slot"
K_REGION = "meal_region"
K_RECO = "meal_reco"
K_SELECTED = "meal_selected_menu"
K_RADIUS = "meal_radius"
K_EDIT = "meal_edit_slot"


def _init_state() -> None:
    st.session_state.setdefault(K_SLOT, slot_for_hour(now().hour, _CONFIG))
    st.session_state.setdefault(K_REGION, DEFAULT_REGION)
    st.session_state.setdefault(K_SELECTED, None)
    st.session_state.setdefault(K_RADIUS, _RADIUS_NEAR)
    st.session_state.setdefault(K_EDIT, None)


# ---------- 추천 ----------

def _make_reco(slot: str, weather: dict | None, seen: list[str], round_no: int) -> dict:
    items = recommend(
        _MENUS,
        slot,
        weather,
        storage.recent_menu_names(today(), _CONFIG["score"]["recent_days"]),
        _CONFIG,
        exclude=seen,
        seed=round_no,
    )
    return {
        "slot": slot,
        "wkey": tuple(weather_conditions(weather, _CONFIG)) if weather else None,
        "items": items,
        "seen": seen + [r.menu.name for r in items],
        "round": round_no,
    }


def _reroll(slot: str, weather: dict | None) -> None:
    prev = st.session_state[K_RECO]
    st.session_state[K_RECO] = _make_reco(slot, weather, prev["seen"], prev["round"] + 1)
    st.session_state[K_SELECTED] = None
    st.session_state[K_RADIUS] = _RADIUS_NEAR


def _ensure_reco(slot: str, weather: dict | None) -> dict:
    """끼니나 날씨 조건이 바뀌지 않는 한 같은 추천을 유지한다(리런에 흔들리지 않게)."""
    wkey = tuple(weather_conditions(weather, _CONFIG)) if weather else None
    reco = st.session_state.get(K_RECO)
    if reco is None or reco["slot"] != slot or reco["wkey"] != wkey:
        st.session_state[K_RECO] = _make_reco(slot, weather, [], 0)
        st.session_state[K_SELECTED] = None
        st.session_state[K_RADIUS] = _RADIUS_NEAR
    return st.session_state[K_RECO]


# ---------- 기록 ----------

def _record(slot: str, menu_name: str, source: str) -> None:
    menu_name = menu_name.strip()
    if not menu_name:
        return
    log, created = storage.save_log(today(), slot, menu_name, source)
    if created:  # 수정은 같은 id를 덮어쓰므로 이벤트를 다시 내지 않는다
        events.emit_meal_logged(log)
    st.session_state[K_EDIT] = None
    st.session_state.pop(f"meal_input_{slot}", None)


def _delete(slot: str) -> None:
    storage.delete_log(today(), slot)
    st.session_state[K_EDIT] = None


def _start_edit(slot: str, current: str) -> None:
    st.session_state[K_EDIT] = slot
    st.session_state[f"meal_input_{slot}"] = current


def _cancel_edit() -> None:
    st.session_state[K_EDIT] = None


def _select_menu(name: str) -> None:
    st.session_state[K_SELECTED] = name
    st.session_state[K_RADIUS] = _RADIUS_NEAR


def _widen_radius() -> None:
    st.session_state[K_RADIUS] = _RADIUS_FAR


# ---------- 화면 조각 ----------

def _render_reco_card(
    idx: int, rec: Recommendation, slot: str, logs: dict[str, MealLog]
) -> None:
    can_log = slot in LOG_SLOTS
    with st.container(border=True):
        st.markdown(f"##### 🎀 {rec.menu.name}")
        st.caption(f"💡 {rec.reason}")
        cols = st.columns(2 if can_log else 1)
        cols[0].button(
            "🍽️ 주변 식당 보기",
            key=f"meal_pick_{idx}",
            on_click=_select_menu,
            args=(rec.menu.name,),
            width="stretch",
        )
        if can_log:
            exists = slot in logs
            cols[1].button(
                "✏️ 이 메뉴로 수정" if exists else "⭐ 이걸로 기록",
                key=f"meal_log_{idx}",
                type="primary",
                on_click=_record,
                args=(slot, rec.menu.name, "recommend"),
                width="stretch",
            )


def _render_restaurants(menu_name: str, region: str) -> None:
    radius = st.session_state[K_RADIUS]
    lat, lng = REGIONS[region]
    st.markdown(f"#### 📍 {region} 근처 '{menu_name}' 식당")
    try:
        with st.spinner("식당을 찾는 중이에요"):
            places = meal_search_restaurants(menu_name, lat, lng, radius)
    except KakaoError as e:
        st.warning(f"{e}. 잠시 후 다시 시도해 주세요.")
        st.button("🔄 다시 시도", key="meal_retry_places")
        return
    if not places:
        if radius < _RADIUS_FAR:
            st.info(f"반경 {radius // 1000}km 안에는 식당이 없어요. 3km로 넓혀서 다시 찾아볼까요?")
            st.button("🔎 3km로 넓혀 찾기", key="meal_widen", on_click=_widen_radius)
        else:
            st.info("반경 3km 안에도 식당이 없어요. 다른 메뉴나 지역을 골라 보세요.")
        return
    st.caption(f"반경 {radius / 1000:g}km · 가까운 순 {len(places)}곳")
    for i, p in enumerate(places):
        with st.container(border=True):
            st.markdown(f"**{p.name}**")
            st.caption(f"{p.distance_m}m · {p.category}")
            if p.map_url:
                st.link_button("🗺️ 지도 앱에서 보기", p.map_url, key=f"meal_map_{i}")


def _render_log_board(logs: dict[str, MealLog]) -> None:
    st.markdown(f"#### 📔 오늘의 기록 · {len(logs)}/{len(LOG_SLOTS)}")
    for slot in LOG_SLOTS:
        label = _LABELS[slot]
        log = logs.get(slot)
        editing = st.session_state[K_EDIT] == slot
        with st.container(border=True):
            if log and not editing:
                st.markdown(f"**{label}** · {log.menu_name}")
                c1, c2 = st.columns(2)
                c1.button(
                    "✏️ 수정", key=f"meal_edit_{slot}", on_click=_start_edit,
                    args=(slot, log.menu_name), width="stretch",
                )
                c2.button(
                    "🗑️ 삭제", key=f"meal_del_{slot}", on_click=_delete,
                    args=(slot,), width="stretch",
                )
            else:
                st.markdown(f"**{label}** · {'수정하기' if editing else '아직 기록이 없어요'}")
                name = st.text_input(
                    "메뉴 이름", key=f"meal_input_{slot}", label_visibility="collapsed",
                    placeholder=f"{label}에 먹은 메뉴를 적어 주세요",
                )
                c1, c2 = st.columns(2)
                c1.button(
                    "⭐ 저장", key=f"meal_save_{slot}", type="primary", on_click=_record,
                    args=(slot, name, "manual"), width="stretch",
                )
                if editing:
                    c2.button(
                        "취소", key=f"meal_cancel_{slot}", on_click=_cancel_edit,
                        width="stretch",
                    )


def render() -> None:
    _init_state()
    st.title("🍚 오늘의 한 끼")

    region = st.selectbox("지역", list(REGIONS), key=K_REGION)
    lat, lng = REGIONS[region]
    weather = get_weather(lat, lng)

    # 위치·날씨를 한 줄로 묶은 location pill 행
    if weather is None:
        st.caption(f"📍 {region} · ☁️ 날씨 정보 없이 추천했어요")
    else:
        st.caption(
            f"📍 {region} · 🌡️ 지금 {weather['temp']:g}° (체감 {weather['feels_like']:g}°)"
        )

    # 끼니 이항·다항 선택은 pill 버튼으로. 해제해도 기존 선택을 유지한다
    picked = st.pills(
        "끼니", list(_LABELS), format_func=_LABELS.__getitem__, selection_mode="single",
        key=K_SLOT, width="stretch",
    )
    slot = picked or slot_for_hour(now().hour, _CONFIG)

    reco = _ensure_reco(slot, weather)
    logs = storage.get_logs(today())

    tab_reco, tab_log = st.tabs(["✨ 추천", f"📔 기록 {len(logs)}/{len(LOG_SLOTS)}"])
    with tab_reco:
        st.markdown(f"#### {_LABELS[slot]} 시간에 어울리는 메뉴")
        for idx, rec in enumerate(reco["items"]):
            _render_reco_card(idx, rec, slot, logs)
        st.button(
            "🔄 다시 추천", key="meal_reroll", on_click=_reroll, args=(slot, weather),
            width="stretch",
        )
        selected = st.session_state[K_SELECTED]
        if selected:
            _render_restaurants(selected, region)
    with tab_log:
        _render_log_board(logs)
