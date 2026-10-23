"""독서 챌린지 v2: 오늘 읽을 책 -> 읽을 시간(분) -> 한 줄 감상의 작은 루프. (PRD Epic C)

화면: 오늘(① 책 ② 시간 ③ 감상) / 책 찾기(추천·검색) / 읽고 싶은 책 / 기록(도감·감상)
실행: features/reading 폴더에서 `streamlit run reading.py`
병합: 홈 요약 카드는 get_today_summary()를 호출한다.
"""
import html
import json
import os
import random
import uuid
from datetime import date, timedelta
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

API_DIR = Path(__file__).resolve().parents[2] / "api" / "reading"
load_dotenv(API_DIR / ".env")  # 키는 여기서만 읽고 화면·로그에는 절대 내보내지 않는다

KAKAO_BOOK_URL = "https://dapi.kakao.com/v3/search/book"
TIMEOUT_SEC = 5
CACHE_TTL_SEC = 24 * 60 * 60  # 책 검색 캐시 24시간
MAX_COMMENT_LEN = 100
STORE_PATH = API_DIR / "reading2_store.json"

TOPICS = ["소설", "에세이", "과학", "자기계발", "역사", "시"]
RECOMMEND_COUNT = 3
GOAL_CHOICES = [10, 20, 30, 60]  # 오늘 목표(분)
ADD_CHOICES = [5, 10, 20, 30]  # 읽은 시간 기록 버튼(분)
CODEX_COLS = 3  # 도감 한 줄에 놓는 표지 수

VIEW_TODAY, VIEW_SEARCH, VIEW_WISH, VIEW_LOG = "🏠 오늘", "🔍 책 찾기", "💗 읽고 싶은 책", "🏆 기록"
VIEWS = [VIEW_TODAY, VIEW_SEARCH, VIEW_WISH, VIEW_LOG]
NEW_BADGE = " ✨ `방금 추가`"
WEEKDAYS = "월화수목금토일"

# 디자인 토큰(단독 실행용). 포인트 색은 .streamlit/config.toml의 primaryColor를 쓰고, 나머지 장식색만 여기 둔다.
PINK = "#FFE3EC"  # 파스텔 핑크 (스티커·리본 바탕)
ROSE = "#B8466F"  # 로즈 포인트 (포커스·강조 글자, 크림 위 대비 4.5:1 이상)
GOLD = "#8A6500"  # 골드 포인트 (왕관·별 글자, 대비 4.5:1 이상)

THEME_CSS = """
<style>
/* 글꼴: 제목은 손글씨풍(Gaegu), 본문은 둥근 고딕(Gowun Dodum). 둘 다 SIL OFL 라이선스(Google Fonts) */
@import url('https://fonts.googleapis.com/css2?family=Gowun+Dodum&family=Gaegu:wght@700&display=swap');
.stApp, .stApp p, .stApp label, .stApp li, .stApp button, .stApp input, .stApp textarea {
  font-family: 'Gowun Dodum', 'Noto Sans KR', sans-serif;
}
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5 { font-family: 'Gaegu', 'Gowun Dodum', sans-serif; }
.stApp h5 { font-size: 1.35rem; }
/* 다이어리 종이: 줄 노트 질감 + 핑크 리본 띠. 데스크톱은 중앙 정렬, 모바일은 화면 폭 꽉 채움 */
.stApp [data-testid="stMainBlockContainer"] {
  max-width: 760px; margin: 0 auto; padding: 1.25rem 1rem 3rem;
  background-color: rgba(255,255,255,.72);
  background-image: repeating-linear-gradient(to bottom, transparent 0, transparent 31px,
    color-mix(in srgb, __POINT__ 9%, transparent) 31px, color-mix(in srgb, __POINT__ 9%, transparent) 32px);
  border-top: 10px solid __PINK__; border-radius: 0 0 24px 24px;
}
@media (min-width: 768px) { .stApp [data-testid="stMainBlockContainer"] { padding: 1.5rem 2rem 3rem; } }
@media (min-width: 1024px) {
  .stApp [data-testid="stMainBlockContainer"] {
    margin: 1.5rem auto; border-radius: 24px; box-shadow: 0 6px 24px color-mix(in srgb, __POINT__ 18%, transparent);
  }
}
/* 접근성: 터치 영역 44px 이상, 키보드 포커스 표시 */
.stApp button, .stApp [role="tab"], .stApp input, .stApp [data-baseweb="select"] > div { min-height: 44px; }
.stApp *:focus-visible { outline: 3px solid __ROSE__ !important; outline-offset: 2px; }
/* 카드 느낌: 지표·알림·표지는 둥글게 */
.stApp [data-testid="stMetric"] {
  background: color-mix(in srgb, __POINT__ 8%, white); border: 1.5px dashed __POINT__;
  border-radius: 20px; padding: .6rem .9rem;
}
.stApp [data-testid="stAlert"] { border-radius: 16px; }
.stApp [data-testid="stImage"] img { border-radius: 14px; box-shadow: 0 2px 8px color-mix(in srgb, __POINT__ 25%, transparent); }
/* 스티커: 핑크 바탕에 점선 컷 라인. 새로 얻을 때(.pop)만 1초 이내로 톡 붙는다 */
.rd-sticker {
  display: flex; align-items: center; gap: .75rem; margin: .5rem 0 .75rem; padding: .75rem 1rem;
  background: __PINK__; border: 2px dashed __ROSE__; border-radius: 20px; color: #3B2F3F; transform: rotate(-1deg);
}
.rd-sticker .rd-e { font-size: 2rem; line-height: 1; }
.rd-sticker .rd-t { font-weight: 700; }
.rd-sticker .rd-s { font-size: .85rem; }
@keyframes rd-pop {
  0% { transform: scale(.6) rotate(-10deg); opacity: 0; }
  70% { transform: scale(1.06) rotate(2deg); opacity: 1; }
  100% { transform: scale(1) rotate(-1deg); opacity: 1; }
}
@media (prefers-reduced-motion: no-preference) { .rd-sticker.pop { animation: rd-pop .8s ease-out; } }
@media (prefers-reduced-motion: reduce) { .stApp * { animation: none !important; transition: none !important; } }
/* 이번 주 달성 카드 */
.rw { display: flex; gap: 6px; margin: .25rem 0 .75rem; }
.rw-d { flex: 1; min-width: 0; text-align: center; padding: 6px 2px 8px; border-radius: 16px;
  border: 1.5px solid color-mix(in srgb, currentColor 18%, transparent); }
.rw-d.ok { background: color-mix(in srgb, __POINT__ 20%, transparent); border-color: __POINT__; }
.rw-d.part { border: 1.5px dashed __POINT__; }
.rw-d.future { opacity: .5; }
.rw-d.today { border: 3px solid __POINT__; box-shadow: 0 2px 8px color-mix(in srgb, __POINT__ 35%, transparent); }
.rw-t { font-size: .65rem; font-weight: 700; color: __ROSE__; min-height: 1em; }
.rw-w { font-size: .8rem; opacity: .85; }
.rw-n { font-size: 1.3rem; font-weight: 700; line-height: 1.3; }
.rw-i { font-size: 1.2rem; line-height: 1.5; }
.rw-m { font-size: .7rem; opacity: .85; }
</style>
"""


def inject_theme() -> None:
    point = st.get_option("theme.primaryColor") or "#7A56B0"
    css = THEME_CSS.replace("__POINT__", point).replace("__PINK__", PINK).replace("__ROSE__", ROSE)
    st.markdown(css, unsafe_allow_html=True)


def sticker(emoji: str, title: str, sub: str = "", pop: bool = False) -> str:
    """스티커 카드 HTML. 이모지는 장식이라 스크린리더에서는 숨기고 글자로 같은 뜻을 전한다."""
    # 제목에는 외부 API·직접 입력 값(책 제목)이 들어오므로 HTML로 해석되지 않게 이스케이프한다
    sub_html = f'<div class="rd-s">{html.escape(sub)}</div>' if sub else ""
    return (f'<div class="rd-sticker{" pop" if pop else ""}"><div class="rd-e" aria-hidden="true">{emoji}</div>'
            f'<div><div class="rd-t">{html.escape(title)}</div>{sub_html}</div></div>')

# books: 책 목록(status: wish | reading | done)
# logs: 읽은 시간 기록 [{date, book_id, minutes}]  goals: {날짜: 목표 분}  reviews: 책별·날짜별 한 줄 감상
EMPTY_STORE = {"books": [], "logs": [], "goals": {}, "reviews": []}


# ---------- 저장소 ----------
def load_store() -> dict:
    try:
        data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    for k, v in EMPTY_STORE.items():  # 모르는 키(이전 버전 기록)는 지우지 않고 그대로 둔다
        data.setdefault(k, type(v)())
    return data


def save_store(store: dict) -> None:
    STORE_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def today_str() -> str:
    return date.today().isoformat()


# ---------- 외부 API (요청 주소·키는 화면에 노출하지 않는다) ----------
@st.cache_data(ttl=CACHE_TTL_SEC, show_spinner=False)
def search_books(query: str, _key: str) -> list[dict]:
    res = requests.get(
        KAKAO_BOOK_URL,
        headers={"Authorization": f"KakaoAK {_key}"},
        params={"query": query, "size": 10},
        timeout=TIMEOUT_SEC,
    )
    res.raise_for_status()
    return [
        {
            "id": (d.get("isbn") or "").strip() or uuid.uuid4().hex,
            "title": d.get("title", ""),
            "author": ", ".join(d.get("authors") or []),
            "cover": d.get("thumbnail", ""),
            "publisher": d.get("publisher", ""),
        }
        for d in res.json().get("documents", [])
    ]


def fetch_books(query: str) -> list[dict] | None:
    """검색 결과를 가져온다. 실패하면 화면에 일반 문구만 띄우고 None을 돌려준다."""
    key = os.getenv("KAKAO_REST_KEY", "")
    if not key or key == "your_kakao_rest_api_key":
        st.error("책 검색을 쓰려면 api/reading/.env에 KAKAO_REST_KEY를 설정해 주세요. 직접 추가는 그대로 쓸 수 있어요.")
        return None
    try:
        return search_books(query, key)
    except requests.HTTPError as e:  # 예외 문자열에는 요청 주소가 들어 있어 화면에 쓰지 않는다
        code = e.response.status_code if e.response is not None else 0
        st.error("API 키를 확인해 주세요." if code in (401, 403) else "책 검색에 실패했어요. 잠시 후 다시 시도해 주세요.")
    except requests.RequestException:
        st.error("책 검색에 실패했어요. 잠시 후 다시 시도해 주세요. 직접 추가할 수도 있어요.")
    return None


# ---------- 계산 ----------
def find_book(store: dict, book_id: str) -> dict | None:
    return next((b for b in store["books"] if b["id"] == book_id), None)


def minutes_on(store: dict, day: str, book_id: str | None = None) -> int:
    return sum(l["minutes"] for l in store["logs"] if l["date"] == day and (book_id is None or l["book_id"] == book_id))


def goal_for(store: dict, day: str) -> int:
    """그날 정한 목표. 안 정했으면 직전에 정한 목표를 이어서 쓴다."""
    dates = [d for d in store["goals"] if d <= day]
    return int(store["goals"][max(dates)]) if dates else 0


def achieved(store: dict, day: str) -> bool:
    read, goal = minutes_on(store, day), goal_for(store, day)
    return read > 0 and read >= goal


def streak(store: dict) -> int:
    """오늘 또는 어제부터 거꾸로 연속 달성한 일수. 오늘 아직 안 읽었어도 어제까지의 연속은 유지한다."""
    day = date.today()
    if not achieved(store, day.isoformat()):
        day -= timedelta(days=1)
    count = 0
    while achieved(store, day.isoformat()):
        count += 1
        day -= timedelta(days=1)
    return count


def days_read(store: dict, book_id: str) -> int:
    return len({l["date"] for l in store["logs"] if l["book_id"] == book_id})


def total_minutes(store: dict, book_id: str) -> int:
    return sum(l["minutes"] for l in store["logs"] if l["book_id"] == book_id)


def week_days() -> list[date]:
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return [monday + timedelta(days=i) for i in range(7)]


def get_today_summary() -> dict:
    """홈 요약 카드용 {title, value, status}. 병합 때 홈이 호출한다."""
    store = load_store()
    today = today_str()
    read, goal = minutes_on(store, today), goal_for(store, today)
    value = f"{read}/{goal}분" if goal else f"{read}분"
    status = "done" if achieved(store, today) else ("in_progress" if read else "empty")
    return {"title": "독서", "value": value, "status": status}


# ---------- 상태 변경 (on_click 콜백) ----------
def add_book(book: dict, status: str) -> None:
    store = load_store()
    existing = find_book(store, book["id"])
    if existing:
        if existing["status"] == "done":  # 다시 읽기: 완독 기록을 걷어낸다
            existing.pop("finished", None)
        existing["status"] = status
    else:
        store["books"].append(
            {
                "id": book["id"],
                "title": book["title"],
                "author": book.get("author", ""),
                "cover": book.get("cover", ""),
                "publisher": book.get("publisher", ""),
                "status": status,
                "added": today_str(),
            }
        )
    save_store(store)


def add_and_go(book: dict, status: str) -> None:
    """책을 담고 해당 화면으로 이동한다. 화면 이동은 위젯 키(reading2_view)를 콜백에서 바꿔서 한다."""
    add_book(book, status)
    reading = status == "reading"
    st.session_state["reading2_view"] = VIEW_TODAY if reading else VIEW_WISH
    if reading:
        st.session_state["reading2_current"] = book["id"]  # 방금 시작한 책이 오늘의 책
    st.session_state["reading2_notice"] = (
        f"『{book['title']}』을(를) " + ("읽는 중인 책에 추가했어요 📖" if reading else "읽고 싶은 책에 담았어요 💗")
    )
    st.session_state["reading2_new_id"] = book["id"]


def go_view(view: str) -> None:
    st.session_state["reading2_view"] = view


def set_goal(minutes: int) -> None:
    store = load_store()
    store["goals"][today_str()] = int(minutes)
    save_store(store)
    # 칩 선택 상태를 목표와 맞춘다 (칩에 없는 값이면 선택 해제)
    st.session_state["reading2_goal_pick"] = minutes if minutes in GOAL_CHOICES else None


def on_goal_pick() -> None:
    picked = st.session_state.get("reading2_goal_pick")
    if picked:
        set_goal(picked)


def on_goal_custom() -> None:
    set_goal(int(st.session_state["reading2_goal_custom"]))


def add_minutes(book_id: str, minutes: int) -> None:
    store = load_store()
    today = today_str()
    before, goal = minutes_on(store, today), goal_for(store, today)
    store["logs"].append({"date": today, "book_id": book_id, "minutes": minutes})
    if goal and before < goal <= before + minutes:
        st.session_state["reading2_goal_hit"] = True  # 목표를 넘긴 순간에만 연출
    save_store(store)


def undo_minutes(book_id: str) -> None:
    store = load_store()
    mine = [l for l in store["logs"] if l["book_id"] == book_id and l["date"] == today_str()]
    if mine:
        store["logs"].remove(mine[-1])
        save_store(store)


def finish_book(book_id: str) -> None:
    store = load_store()
    book = find_book(store, book_id)
    if book:
        book["status"] = "done"
        book["finished"] = today_str()
        st.session_state["reading2_celebrate"] = book_id
        save_store(store)


def remove_book(book_id: str) -> None:
    store = load_store()
    store["books"] = [b for b in store["books"] if b["id"] != book_id]
    store["logs"] = [l for l in store["logs"] if l["book_id"] != book_id]
    store["reviews"] = [r for r in store["reviews"] if r["book_id"] != book_id]
    save_store(store)


def save_review(book_id: str, rating: int, comment: str) -> None:
    store = load_store()
    today = today_str()
    for r in store["reviews"]:
        if r["book_id"] == book_id and r["date"] == today:
            r.update(rating=rating, comment=comment)
            break
    else:
        store["reviews"].append(
            {"id": uuid.uuid4().hex, "book_id": book_id, "date": today, "rating": rating, "comment": comment}
        )
    save_store(store)


def update_review(review_id: str) -> None:
    """기록 화면의 수정 폼(키: reading2_edit_*)에서 값을 읽어 감상을 고친다."""
    comment = st.session_state.get(f"reading2_edit_comment_{review_id}", "").strip()
    rating = st.session_state.get(f"reading2_edit_rating_{review_id}")
    store = load_store()
    for r in store["reviews"]:
        if r["id"] == review_id:
            if comment:
                r["comment"] = comment
            if rating is not None:
                r["rating"] = rating + 1
    save_store(store)


def delete_review(review_id: str) -> None:
    store = load_store()
    store["reviews"] = [r for r in store["reviews"] if r["id"] != review_id]
    save_store(store)


def next_recommendation() -> None:
    st.session_state["reading2_rec_seed"] = st.session_state.get("reading2_rec_seed", 0) + 1


# ---------- 공통 화면 조각 ----------
def cover_or_icon(col, book: dict, width: int = 80) -> None:
    if book.get("cover"):
        col.image(book["cover"], width=width)
    else:
        col.markdown("## 📕")


def is_new(book: dict) -> bool:
    return book["id"] == st.session_state.get("reading2_new_id")


def title_line(book: dict) -> str:
    return f"**{book['title']}**{NEW_BADGE if is_new(book) else ''}  \n{book['author'] or '저자 정보 없음'}"


def render_header(store: dict) -> None:
    today = date.today()
    st.title("🎀 독서 챌린지 👑")
    st.caption(f"{today:%Y.%m.%d} {WEEKDAYS[today.weekday()]}요일 · 오늘 읽을 책 → 읽을 시간 → 한 줄 감상")
    render_week(store)


def render_week(store: dict) -> None:
    """이번 주 월~일 달성 현황을 카드 7장으로 보여준다.

    상태는 색뿐 아니라 아이콘·글자(달성/읽음/오늘)로도 구분한다. 카드는 한 줄 flex라 좁은 화면에서도 쌓이지 않는다.
    스타일은 THEME_CSS의 .rw-* (강조색은 config.toml의 primaryColor).
    """
    today = date.today()
    cells, ok_days = [], 0
    for i, day in enumerate(week_days()):
        iso = day.isoformat()
        read = minutes_on(store, iso)
        if day > today:
            state, icon, text = "future", "▫️", "–"
        elif achieved(store, iso):
            state, icon, text = "ok", "✅", f"{read}분"
            ok_days += 1
        elif read:
            state, icon, text = "part", "🌗", f"{read}분"
        else:
            state, icon, text = "none", "⬜", "–"
        if day == today:
            state += " today"
        label = {"ok": "달성", "part": "목표 미달", "none": "기록 없음", "future": "아직 오지 않음"}[state.split()[0]]
        tag = "오늘" if day == today else "&nbsp;"
        cells.append(
            f'<div class="rw-d {state}" title="{WEEKDAYS[i]}요일 {label}" aria-label="{WEEKDAYS[i]}요일 {label} {text}">'
            f'<div class="rw-t">{tag}</div><div class="rw-w">{WEEKDAYS[i]}</div>'
            f'<div class="rw-n">{day.day}</div><div class="rw-i">{icon}</div><div class="rw-m">{text}</div></div>'
        )
    week_min = sum(minutes_on(store, d.isoformat()) for d in week_days())
    st.markdown(f"**📅 이번 주 {ok_days}/7일 달성** · 읽은 시간 {week_min}분")
    st.markdown(f'<div class="rw">{"".join(cells)}</div>', unsafe_allow_html=True)


# ---------- 오늘 ----------
def render_summary(store: dict) -> None:
    today = today_str()
    read, goal = minutes_on(store, today), goal_for(store, today)
    c1, c2, c3 = st.columns(3)
    c1.metric("🔥 연속 기록", f"{streak(store)}일째")
    c2.metric("⏱ 오늘 읽은 시간", f"{read}분")
    c3.metric("🎯 오늘 목표", f"{goal}분" if goal else "미정")


def render_celebration(store: dict) -> None:
    """완독 연출: 풍선 대신 왕관 스티커가 톡 붙는다 (모션은 prefers-reduced-motion을 따른다)."""
    bid = st.session_state.pop("reading2_celebrate", None)
    book = find_book(store, bid) if bid else None
    if not book:
        return
    with st.container(border=True):
        c_img, c_body = st.columns([1, 3])
        cover_or_icon(c_img, book, 120)
        c_body.markdown(sticker("👑", f"『{book['title']}』 완독!", "도감에 표지가 한 장 모였어요", pop=True),
                        unsafe_allow_html=True)
        c_body.caption(f"{days_read(store, book['id'])}일 · 총 {total_minutes(store, book['id'])}분 읽었어요. "
                       "아래 한 줄 감상으로 마무리해 보세요.")


def render_pick_book(store: dict, reading: list[dict]) -> dict:
    """① 오늘 읽을 책. 읽는 중인 책 중 하나를 고르고, 표지를 크게 보여준다."""
    ids = [b["id"] for b in reading]
    if st.session_state.get("reading2_current") not in ids:
        st.session_state.pop("reading2_current", None)
    if len(ids) > 1:
        titles = {b["id"]: b["title"] for b in reading}
        st.selectbox("오늘 읽을 책", ids, format_func=titles.get, key="reading2_current")
    book = find_book(store, st.session_state.get("reading2_current", ids[0]))
    with st.container(border=True):
        c_img, c_body = st.columns([1, 2], vertical_alignment="center")
        cover_or_icon(c_img, book, 120)
        c_body.markdown(title_line(book))
        c_body.caption(f"읽은 날 {days_read(store, book['id'])}일 · 총 {total_minutes(store, book['id'])}분 · "
                       f"오늘 {minutes_on(store, today_str(), book['id'])}분")
    return book


def render_time(store: dict, book: dict) -> None:
    """② 오늘 읽을 시간. 목표를 한 탭으로 고르고, 읽은 만큼 +분 버튼으로 기록한다."""
    today = today_str()
    goal, read = goal_for(store, today), minutes_on(store, today)
    st.session_state.setdefault("reading2_goal_pick", goal if goal in GOAL_CHOICES else None)  # 첫 표시 값
    st.pills("오늘은 몇 분 읽을까?", GOAL_CHOICES, format_func=lambda m: f"{m}분", key="reading2_goal_pick",
             on_change=on_goal_pick)
    with st.expander("다른 시간으로 정하기"):
        c1, c2 = st.columns([2, 1], vertical_alignment="bottom")
        c1.number_input("목표(분)", min_value=5, max_value=600, step=5, value=45, key="reading2_goal_custom")
        c2.button("정하기", key="reading2_goal_custom_set", on_click=on_goal_custom, use_container_width=True)

    if goal:
        st.progress(min(read / goal, 1.0), text=f"오늘 {read}/{goal}분 ({min(read / goal, 1.0):.0%})")
    else:
        st.caption("목표를 정하면 진행률 바가 보여요.")
    fresh = st.session_state.pop("reading2_goal_hit", False)  # 방금 달성한 순간에만 붙는 모션
    if goal and read >= goal:
        st.markdown(sticker("🌟", "오늘 목표 달성!", "스티커 한 장을 붙였어요", pop=fresh), unsafe_allow_html=True)

    st.caption("읽은 만큼 눌러 기록해요")
    cols = st.columns(len(ADD_CHOICES) + 1)
    for col, n in zip(cols, ADD_CHOICES):
        col.button(f"+{n}분", key=f"reading2_add_{n}", on_click=add_minutes, args=(book["id"], n),
                   use_container_width=True)
    cols[-1].button("↩ 되돌리기", key="reading2_undo", on_click=undo_minutes, args=(book["id"],),
                    use_container_width=True)


def render_review(store: dict, current: dict) -> None:
    """③ 한 줄 감상. 책별·날짜별로 하나씩 저장하며 같은 날 다시 저장하면 덮어쓴다."""
    today = today_str()
    candidates = [b for b in store["books"] if b["status"] == "reading"] + [
        b for b in store["books"] if b["status"] == "done" and b.get("finished") == today
    ]
    index = next((i for i, b in enumerate(candidates) if b["id"] == current["id"]), 0)
    book = current
    if len(candidates) > 1:
        book = st.selectbox("감상을 남길 책", candidates, index=index, format_func=lambda b: b["title"],
                            key="reading2_review_book")
    mine = next((r for r in store["reviews"] if r["book_id"] == book["id"] and r["date"] == today), None)
    with st.form("reading2_review_form"):
        rating = st.feedback("stars", key=f"reading2_rating_{book['id']}")
        comment = st.text_input("한 줄 감상", value=mine["comment"] if mine else "", max_chars=MAX_COMMENT_LEN,
                                key=f"reading2_comment_{book['id']}")
        submitted = st.form_submit_button("저장하기", use_container_width=True)
    if submitted:
        if rating is None and mine is None:
            st.warning("별점을 골라 주세요.")
        elif not comment.strip():
            st.warning("한 줄 감상을 적어 주세요.")
        else:
            save_review(book["id"], (rating + 1) if rating is not None else mine["rating"], comment.strip())
            st.success("오늘의 감상을 저장했어요 ✨")


def render_manage(book: dict) -> None:
    bid = book["id"]
    with st.expander("책 관리"):
        c1, c2, c3 = st.columns(3)
        c1.button("🏁 완독", key=f"reading2_finish_{bid}", on_click=finish_book, args=(bid,), use_container_width=True)
        c2.button("💗 서랍으로", key=f"reading2_towish_{bid}", on_click=add_and_go, args=(book, "wish"),
                  use_container_width=True)
        c3.button("🗑 삭제", key=f"reading2_rm_{bid}", on_click=remove_book, args=(bid,), use_container_width=True)
        st.caption("삭제하면 이 책의 읽은 시간과 감상도 함께 지워져요.")


def render_today(store: dict) -> None:
    render_summary(store)
    render_celebration(store)
    reading = [b for b in store["books"] if b["status"] == "reading"]
    st.markdown("##### ⭐ ① 오늘 읽을 책")
    if not reading:
        st.info("읽는 중인 책이 없어요. 책을 골라 시작해 보세요.")
        st.button("🔍 오늘의 책 추천받기", on_click=go_view, args=(VIEW_SEARCH,), use_container_width=True)
        return
    book = render_pick_book(store, reading)
    st.markdown("##### ⏱ ② 오늘 읽을 시간")
    render_time(store, book)
    st.markdown("##### 💌 ③ 오늘의 한 줄 감상")
    render_review(store, book)
    render_manage(book)


# ---------- 책 찾기 ----------
def render_search_cards(books: list[dict], prefix: str) -> None:
    for i, book in enumerate(books):
        with st.container(border=True):
            c_img, c_txt, c_btn = st.columns([1, 4, 2], vertical_alignment="center")
            cover_or_icon(c_img, book, 70)
            c_txt.markdown(f"**{book['title']}**  \n{book['author'] or '저자 정보 없음'} · {book['publisher']}")
            with c_btn:
                st.button("이 책으로 시작", key=f"reading2_{prefix}_start_{i}", on_click=add_and_go,
                          args=(book, "reading"), use_container_width=True)
                st.button("담아두기", key=f"reading2_{prefix}_wish_{i}", on_click=add_and_go,
                          args=(book, "wish"), use_container_width=True)


def render_recommend(store: dict) -> None:
    st.markdown("##### ✨ 오늘의 책 추천")
    topic = st.pills("관심 주제", TOPICS, key="reading2_topic")
    if not topic:
        st.caption("관심 주제를 고르면 오늘 읽을 책을 골라 드려요.")
        return
    books = fetch_books(topic)
    if books is None:
        return
    skip = {b["id"] for b in store["books"] if b["status"] in ("done", "reading")}  # 읽은 책·읽는 중인 책 제외
    pool = [b for b in books if b["id"] not in skip]
    if not pool:
        st.info("추천할 책이 없어요. 다른 주제를 골라 보세요.")
        return
    seed = st.session_state.get("reading2_rec_seed", 0)
    picks = random.Random(f"{topic}-{seed}").sample(pool, min(RECOMMEND_COUNT, len(pool)))
    render_search_cards(picks, "rec")
    st.button("🔄 다른 책 추천받기", key="reading2_rec_next", on_click=next_recommendation)


def render_search(store: dict) -> None:
    render_recommend(store)
    st.divider()
    st.markdown("##### 🔍 도서명으로 찾기")
    with st.form("reading2_search_form"):
        query = st.text_input("도서명", placeholder="예: 어린 왕자", key="reading2_query")
        go = st.form_submit_button("검색", use_container_width=True)
    if go:
        st.session_state["reading2_last_query"] = query.strip()
    q = st.session_state.get("reading2_last_query", "")
    if q:
        books = fetch_books(q)
        if books is not None:
            if books:
                st.caption(f"검색 결과 {len(books)}권")
                render_search_cards(books, "search")
            else:
                st.info("검색 결과가 없어요.")

    with st.expander("검색에 없는 책 직접 추가"):
        with st.form("reading2_manual_form", clear_on_submit=True):
            title = st.text_input("제목")
            author = st.text_input("저자")
            ok = st.form_submit_button("읽는 중으로 추가", use_container_width=True)
        if ok:
            if title.strip():
                add_book({"id": uuid.uuid4().hex, "title": title.strip(), "author": author.strip()}, "reading")
                st.success("추가했어요. '오늘' 화면에서 확인해 보세요.")
            else:
                st.warning("제목을 입력해 주세요.")


# ---------- 읽고 싶은 책 ----------
def render_wishlist(store: dict) -> None:
    wish = [b for b in store["books"] if b["status"] == "wish"]
    if not wish:
        st.info("서랍이 비어 있어요. 책 찾기에서 '담아두기'를 눌러 보세요.")
        return
    for b in wish:
        with st.container(border=True):
            c_img, c_txt, c_btn = st.columns([1, 4, 2], vertical_alignment="center")
            cover_or_icon(c_img, b, 60)
            c_txt.markdown(title_line(b))
            with c_btn:
                st.button("읽기 시작", key=f"reading2_wstart_{b['id']}", on_click=add_and_go,
                          args=(b, "reading"), use_container_width=True)
                st.button("삭제", key=f"reading2_wrm_{b['id']}", on_click=remove_book,
                          args=(b["id"],), use_container_width=True)


# ---------- 기록 ----------
def render_codex_card(store: dict, book: dict) -> None:
    """도감 카드: 표지를 크게 두고 제목·완독일·별점을 아래에 얹는다."""
    reviews = [r for r in store["reviews"] if r["book_id"] == book["id"]]
    stars = "⭐" * max((r["rating"] for r in reviews), default=0)
    with st.container(border=True):
        if book.get("cover"):
            st.image(book["cover"], use_container_width=True)
        else:
            st.markdown("<div style='text-align:center;font-size:4rem'>📕</div>", unsafe_allow_html=True)
        st.markdown(f"**{book['title']}**")
        st.caption(f"{book['author'] or '저자 정보 없음'}  \n"
                   f"🏁 {book.get('finished', '')} · ⏱ {total_minutes(store, book['id'])}분")
        if stars:
            st.markdown(stars)


def render_history(store: dict) -> None:
    week_min = sum(minutes_on(store, d.isoformat()) for d in week_days())
    st.metric("📅 이번 주 읽은 시간", f"{week_min}분")

    done = sorted((b for b in store["books"] if b["status"] == "done"), key=lambda b: b.get("finished", ""),
                  reverse=True)
    st.markdown(f"##### 🏆 나의 책 도감 ({len(done)}권)")
    if not done:
        st.caption("책을 완독하면 표지가 도감에 한 장씩 모여요.")
    for start in range(0, len(done), CODEX_COLS):
        for col, book in zip(st.columns(CODEX_COLS), done[start:start + CODEX_COLS]):
            with col:
                render_codex_card(store, book)

    st.markdown("##### 💬 한 줄 감상")
    if not store["reviews"]:
        st.caption("아직 남긴 감상이 없어요.")
    for r in sorted(store["reviews"], key=lambda x: x["date"], reverse=True):
        book = find_book(store, r["book_id"])
        with st.container(border=True):
            c_txt, c_edit, c_del = st.columns([5, 1.4, 1.4], vertical_alignment="center")
            c_txt.markdown(f"**{book['title'] if book else '삭제된 책'}** · {r['date']}  \n"
                           f"{'⭐' * r['rating']}  \n{r['comment']}")
            with c_edit.popover("수정", use_container_width=True):
                st.feedback("stars", key=f"reading2_edit_rating_{r['id']}")
                st.text_input("한 줄 감상", value=r["comment"], max_chars=MAX_COMMENT_LEN,
                              key=f"reading2_edit_comment_{r['id']}")
                st.button("저장", key=f"reading2_edit_save_{r['id']}", on_click=update_review,
                          args=(r["id"],), use_container_width=True)
                st.caption("별점을 고르지 않으면 기존 별점을 유지해요.")
            c_del.button("삭제", key=f"reading2_rdel_{r['id']}", on_click=delete_review, args=(r["id"],),
                         use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="독서 챌린지", page_icon="📖")
    inject_theme()
    store = load_store()
    render_header(store)
    notice = st.session_state.pop("reading2_notice", None)
    if notice:
        st.success(notice)
    # 탭 상태를 추적(on_change="rerun")하므로 열린 탭만 그리고, 콜백에서 session_state[key]로 탭을 옮긴다
    tabs = st.tabs(VIEWS, key="reading2_view", on_change="rerun")
    renderers = [render_today, render_search, render_wishlist, render_history]
    for tab, render in zip(tabs, renderers):
        with tab:
            if tab.open:
                render(store)
    if st.session_state.get("reading2_view", VIEW_TODAY) != VIEW_SEARCH:  # 배지는 이동한 탭에서 한 번만 보여준다
        st.session_state.pop("reading2_new_id", None)


main()
