"""독서 챌린지: 책 검색 -> 카드 선택 -> 기록 폼(별점·한 줄 감상·읽은 날짜).

실행: streamlit run reading.py
"""
import json
import os
import uuid
from datetime import date
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

# API 키는 api/reading/.env에 둔다 (features/reading/reading.py 기준 ../../api/reading)
load_dotenv(Path(__file__).resolve().parents[2] / "api" / "reading" / ".env")  # API_DIR와 같은 경로

KAKAO_BOOK_URL = "https://dapi.kakao.com/v3/search/book"
TIMEOUT_SEC = 5
CACHE_TTL_SEC = 24 * 60 * 60  # 책 검색 캐시 24시간
MAX_COMMENT_LEN = 100
API_DIR = Path(__file__).resolve().parents[2] / "api" / "reading"
STORE_PATH = API_DIR / "reading_log.json"


@st.cache_data(ttl=CACHE_TTL_SEC, show_spinner=False)
def search_books(query: str, key: str) -> list[dict]:
    res = requests.get(
        KAKAO_BOOK_URL,
        headers={"Authorization": f"KakaoAK {key}"},
        params={"query": query, "size": 10},
        timeout=TIMEOUT_SEC,
    )
    res.raise_for_status()
    return [
        {
            "title": d.get("title", ""),
            "author": ", ".join(d.get("authors") or []),
            "cover": d.get("thumbnail", ""),
            "publisher": d.get("publisher", ""),
            "isbn": d.get("isbn", ""),
        }
        for d in res.json().get("documents", [])
    ]


def load_log() -> list[dict]:
    try:
        return json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_log(entries: list[dict]) -> None:
    STORE_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def pick_book(book: dict) -> None:
    st.session_state["reading_cover"] = book["cover"]
    st.session_state["reading_title"] = book["title"]
    st.session_state["reading_author"] = book["author"]
    st.session_state["reading_picked"] = True


def render_cards(books: list[dict]) -> None:
    for i, book in enumerate(books):
        with st.container(border=True):
            c_img, c_txt, c_btn = st.columns([1, 4, 1.4], vertical_alignment="center")
            if book["cover"]:
                c_img.image(book["cover"], width=70)
            else:
                c_img.write("📕")
            c_txt.markdown(f"**{book['title']}**  \n{book['author'] or '저자 정보 없음'} · {book['publisher']}")
            c_btn.button("선택", key=f"reading_pick_{i}", on_click=pick_book, args=(book,), use_container_width=True)


def render_form() -> None:
    st.subheader("📝 독서 기록")
    with st.form("reading_form", clear_on_submit=False):
        cover = st.session_state.get("reading_cover", "")
        if cover:
            st.image(cover, width=100)
        title = st.text_input("제목", key="reading_title")
        author = st.text_input("저자", key="reading_author")
        rating = st.feedback("stars", key="reading_rating")
        comment = st.text_input("한 줄 감상", max_chars=MAX_COMMENT_LEN, key="reading_comment")
        read_on = st.date_input("읽은 날짜", value=date.today(), key="reading_date")
        submitted = st.form_submit_button("기록하기", use_container_width=True)

    if not submitted:
        return
    if not title.strip():
        st.warning("책을 선택하거나 제목을 입력해 주세요.")
        return
    if rating is None:
        st.warning("별점을 골라 주세요.")
        return
    entries = load_log()
    entries.append(
        {
            "id": uuid.uuid4().hex,
            "title": title.strip(),
            "author": author.strip(),
            "cover": cover,
            "rating": rating + 1,
            "comment": comment.strip(),
            "date": read_on.isoformat(),
        }
    )
    save_log(entries)
    st.success("기록했어요! ✨")


def render_log() -> None:
    entries = load_log()
    if not entries:
        return
    st.subheader("📚 내 독서 기록")
    for e in sorted(entries, key=lambda x: x["date"], reverse=True):
        with st.container(border=True):
            c_img, c_txt, c_del = st.columns([1, 5, 1.2], vertical_alignment="center")
            if e["cover"]:
                c_img.image(e["cover"], width=60)
            c_txt.markdown(
                f"**{e['title']}** · {e['author']}  \n"
                f"{'⭐' * e['rating']} · {e['date']}  \n{e['comment']}"
            )
            if c_del.button("삭제", key=f"reading_del_{e['id']}"):
                save_log([x for x in entries if x["id"] != e["id"]])
                st.rerun()


def main() -> None:
    st.set_page_config(page_title="독서 챌린지", page_icon="📖")
    st.title("📖 독서 챌린지")

    key = os.getenv("KAKAO_REST_KEY", "")
    if not key or key == "your_kakao_rest_api_key":
        st.error("api/reading/.env 파일의 KAKAO_REST_KEY에 카카오 REST API 키를 넣어 주세요.")
        st.stop()

    query = st.text_input("책 이름 검색", placeholder="예: 어린 왕자", key="reading_query")
    if query.strip() != st.session_state.get("reading_last_query"):
        st.session_state["reading_last_query"] = query.strip()
        st.session_state["reading_picked"] = False  # 새 검색어면 결과를 다시 펼친다
    if query.strip():
        try:
            books = search_books(query.strip(), key)
        except requests.RequestException:
            st.error("책 검색에 실패했어요. 잠시 후 다시 시도해 주세요. 제목을 직접 입력해 기록할 수도 있어요.")
        else:
            if books:
                picked = st.session_state.get("reading_picked", False)
                with st.expander(f"검색 결과 {len(books)}권", expanded=not picked):
                    render_cards(books)
            else:
                st.info("검색 결과가 없어요.")

    render_form()
    render_log()


main()
