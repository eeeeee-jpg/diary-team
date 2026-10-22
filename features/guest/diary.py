"""다이어리 느낌의 페이지 조각 (줄 노트, 마스킹 테이프, 도장, 폴라로이드).

모든 클래스에 guest- 접두사를 붙여 다른 서비스 화면에 영향을 주지 않게 한다.
폰트: Jua(제목·도장·탭), Poor Story(작은 손글씨 줄), Gowun Dodum(본문) — 모두 Google Fonts, SIL Open Font License.
"""

from __future__ import annotations

import base64
from datetime import date
from html import escape

from . import cards
from .config import SLOT_LABELS, SLOTS
from .illustration import PAW_SVG, WALK_SECONDS, guest_walker_svg
from .logic import Loyalty
from .models import Breed, CollectionCard

WEEKDAYS = "월화수목금토일"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Jua&family=Poor+Story&family=Gowun+Dodum&display=swap');

/* ── 줄 노트 한 장 ──────────────────────────── */
.guest-paper {
  position:relative; margin:22px 2px 8px; padding:28px 20px 20px 50px;
  background-color:#fffaf0;
  background-image:
    linear-gradient(90deg, transparent 36px, rgba(242,155,184,.55) 36px 38px, transparent 38px),
    repeating-linear-gradient(180deg, transparent 0 31px, rgba(196,176,200,.35) 31px 32px);
  border-radius:4px 16px 16px 4px;
  box-shadow:0 1px 0 #efe3d5, 0 10px 24px rgba(40,20,40,.22);
  color:#4a3640; font-family:'Gowun Dodum', 'Malgun Gothic', sans-serif; font-size:15px; line-height:32px;
}
.guest-paper::before {  /* 스프링 구멍 */
  content:""; position:absolute; left:10px; top:14px; bottom:14px; width:14px;
  background:radial-gradient(circle, #ddd2da 0 4.5px, transparent 5.5px) 0 0 / 14px 32px repeat-y;
}
.guest-paper .guest-card { line-height:1.35; }  /* 노트 줄 간격이 카드 안으로 번지지 않게 */
.guest-paper.guest-plain { background-image:linear-gradient(90deg, transparent 36px, rgba(242,155,184,.55) 36px 38px, transparent 38px); }
.guest-tape {
  position:absolute; top:-12px; left:50%; width:118px; height:26px; transform:translateX(-50%) rotate(-2deg);
  background:repeating-linear-gradient(45deg, rgba(255,186,208,.88) 0 8px, rgba(255,214,227,.88) 8px 16px);
  box-shadow:0 1px 3px rgba(0,0,0,.15); z-index:1;
}
.guest-tape.guest-lavender { background:repeating-linear-gradient(45deg, rgba(205,191,240,.9) 0 8px, rgba(226,216,250,.9) 8px 16px); transform:translateX(-50%) rotate(2deg); }
.guest-tape.guest-mint { background:repeating-linear-gradient(45deg, rgba(170,226,205,.9) 0 8px, rgba(205,240,226,.9) 8px 16px); }
.guest-h { font-family:'Jua', 'Gowun Dodum', sans-serif; font-weight:400; font-size:28px; line-height:34px; margin:0; color:#3d2b38; }
.guest-h2 { font-family:'Jua', 'Gowun Dodum', sans-serif; font-weight:400; font-size:21px; line-height:32px; margin:0; color:#3d2b38; }
.guest-hand { font-family:'Poor Story', 'Gowun Dodum', cursive; font-size:18px; line-height:32px; color:#5a4250; }
.guest-date { font-family:'Poor Story', 'Gowun Dodum', cursive; font-size:17px; line-height:32px; color:#8a6a7c; }
.guest-muted { color:#8a7480; font-size:14px; }

/* 일기장 첫 장: 왼쪽 글 + 오른쪽 발바닥 도장이 겹치지 않게 나란히 */
.guest-head { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; }
.guest-head-text { min-width:0; }
.guest-cover { padding-bottom:22px; }

/* 일차 도장: 고양이 발바닥 모양 (발가락 4개 + 볼록살 안에 N일째) */
.guest-stamp {
  position:relative; flex:none; width:104px; height:100px; margin:2px 4px 0 0; color:#e2557f;
  font-family:'Jua', 'Gowun Dodum', sans-serif; line-height:1; transform:rotate(-10deg); opacity:.9;
}
.guest-toe, .guest-pad { position:absolute; border:3px solid #e2557f; background:rgba(255,209,225,.5); }
.guest-toe { width:21px; height:26px; border-radius:50%; }
.guest-toe.guest-t1 { left:4px; top:30px; transform:rotate(-30deg); }
.guest-toe.guest-t2 { left:26px; top:6px; transform:rotate(-10deg); }
.guest-toe.guest-t3 { left:52px; top:6px; transform:rotate(10deg); }
.guest-toe.guest-t4 { left:74px; top:30px; transform:rotate(30deg); }
.guest-pad {
  left:15px; right:15px; bottom:0; height:54px; border-radius:46% 46% 42% 42% / 56% 56% 44% 44%;
  display:flex; flex-direction:column; align-items:center; justify-content:center;
}
.guest-pad b { font-weight:400; font-size:19px; }
.guest-pad small { font-size:10.5px; margin-top:3px; }

/* 최근 7일 스티커 */
.guest-week { display:grid; grid-template-columns:repeat(7, minmax(0, 1fr)); gap:6px; margin:14px 0 4px; max-width:440px; }
.guest-day { text-align:center; line-height:1.25; font-size:12px; color:#8a6a7c; }
.guest-sticker {
  width:36px; height:36px; margin:2px auto 0; border-radius:50%; display:grid; place-items:center;
  background:#f6eef2; border:2px dashed #e4d3dd; font-size:10px; letter-spacing:1px; color:#c08aa3;
}
.guest-day.guest-some .guest-sticker { background:#ffe7ef; border:2px solid #f6b9cc; }
.guest-day.guest-full .guest-sticker { background:#ffd1e1; border:2px solid #f29bb8; font-size:18px; letter-spacing:0; }
.guest-day.guest-today { color:#e2557f; font-weight:700; }

/* 모은 카드 막대 */
.guest-collect { margin-top:20px; }
.guest-collect .guest-bar { margin-top:6px; }
.guest-bar { height:12px; border-radius:999px; background:#f1e4ec; overflow:hidden; box-shadow:inset 0 1px 2px rgba(0,0,0,.08); }
.guest-bar > i { display:block; height:100%; border-radius:999px; background:linear-gradient(90deg, #f6a5c0, #c9b3f5); }

/* ── 폴라로이드 (오늘의 3칸) ─────────────────── */
.guest-polas { display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:14px; padding:8px 0 4px; }
.guest-pola {
  position:relative; background:#fff; padding:7px 7px 2px; text-align:center;
  box-shadow:0 4px 10px rgba(40,20,40,.22); transform:rotate(-2.2deg);
}
.guest-pola:nth-child(2) { transform:rotate(1.6deg); }
.guest-pola:nth-child(3) { transform:rotate(-1deg); }
.guest-pola::before {
  content:""; position:absolute; top:-9px; left:50%; width:46px; height:16px; transform:translateX(-50%) rotate(3deg);
  background:rgba(205,191,240,.8);
}
.guest-pic { position:relative; aspect-ratio:1/1; overflow:hidden; background:#f4ede6; }
.guest-pic > img { width:100%; height:100%; object-fit:cover; display:block; }
.guest-pic .guest-visitor {
  position:absolute; right:5px; bottom:5px; width:42%; height:auto; aspect-ratio:1/1; border-radius:50%;
  object-fit:cover; border:3px solid #fff; box-shadow:0 2px 6px rgba(0,0,0,.3);
}
.guest-pola .guest-menu { font-family:'Poor Story', 'Gowun Dodum', cursive; font-size:14px; line-height:20px; color:#8a6a7c; margin:-4px 0 4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.guest-pola .guest-cap { font-family:'Poor Story', 'Gowun Dodum', cursive; font-size:15px; line-height:28px; color:#4a3640; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.guest-pola.guest-empty .guest-pic {
  display:grid; place-items:center; background:#fbf6f1; border:2px dashed #e4d3dd;
  font-family:'Poor Story', 'Gowun Dodum', cursive; font-size:14px; line-height:1.3; color:#b39aa8; padding:6px;
}

/* ── 손님 방문 일기 ─────────────────────────── */
.guest-entry { display:flex; flex-wrap:wrap; gap:18px; align-items:center; justify-content:center; margin:6px 0; }
.guest-entry .guest-pola { width:190px; }
.guest-entry .guest-reveal { width:230px; margin:0; }

/* 손님이 오른쪽 위에서 가운데로 총총 다가온다 (0~1.6초, 점점 커짐) → 말풍선 (1.65초) → 카드가 뿅 (1.85초).
   기본 스타일이 '다 도착한 모습'이고, 애니메이션은 처음 모습에서 그쪽으로 움직인다.
   걷는 시간은 illustration.WALK_SECONDS와 맞춘다. */
.guest-arrival .guest-h2, .guest-arrival .guest-hand, .guest-arrival .guest-muted { text-align:center; }
.guest-walk { position:relative; height:150px; margin:2px 0 0; overflow:hidden; container-type:inline-size; }
.guest-walker {
  position:absolute; left:calc(50% - 60px); bottom:0; width:120px; z-index:1; transform-origin:50% 100%;
  animation:guest-approach 1.6s cubic-bezier(.3,.55,.35,1) both;
}
.guest-walker > img { display:block; width:120px; height:122px; }
.guest-bubble {
  position:absolute; top:4px; right:-40px; padding:0 10px; border-radius:14px; background:#fff;
  border:2px solid #4a3640; font-family:'Jua', 'Gowun Dodum', sans-serif; font-weight:400; font-size:16px; line-height:26px; color:#4a3640;
  transform-origin:0 100%; animation:guest-pop .3s cubic-bezier(.3,1.6,.5,1) 1.65s both;
}
.guest-bubble::after {
  content:""; position:absolute; left:6px; bottom:-7px; width:10px; height:10px; background:#fff;
  border-right:2px solid #4a3640; border-bottom:2px solid #4a3640; transform:rotate(45deg) skew(8deg, 8deg);
}
.guest-paw { position:absolute; opacity:.95; animation:guest-paw-in .25s ease-out both; }
.guest-paw img { display:block; width:18px; height:18px; }

/* 카드가 뿅: 작게 튀어 올랐다가 제자리에, 둘레로 별가루가 퍼진다 */
.guest-arrival .guest-reveal { position:relative; }
.guest-arrival .guest-flip { animation:guest-boing .6s cubic-bezier(.3,1.6,.5,1) 1.85s both; }
.guest-arrival .guest-card.guest-rare::after, .guest-arrival .guest-card.guest-legendary::after { animation-delay:2.5s; }
.guest-burst { position:absolute; left:50%; top:45%; z-index:4; pointer-events:none; }
.guest-burst i {
  position:absolute; left:-8px; top:-10px; font-style:normal; font-size:18px; color:#f1b93a; text-shadow:0 0 6px #fff;
  animation:guest-burst .75s ease-out 1.9s both;
}
.guest-burst i:nth-child(even) { color:#f27aa8; font-size:14px; }

@keyframes guest-approach {
  from { transform:translate(min(34cqw, 230px), -80px) scale(.42); opacity:0; }
  10% { opacity:1; }
  to { transform:none; opacity:1; }
}
@keyframes guest-pop { from { transform:scale(0); opacity:0; } to { transform:scale(1); opacity:1; } }
@keyframes guest-paw-in { from { opacity:0; } to { opacity:.95; } }
@keyframes guest-boing { from { transform:translateY(-50px) scale(.1); opacity:0; } 40% { opacity:1; } to { transform:none; opacity:1; } }
@keyframes guest-burst {
  from { transform:translate(0, 0) scale(.3); opacity:0; }
  25% { opacity:1; }
  to { transform:translate(var(--x), var(--y)) scale(1.1) rotate(90deg); opacity:0; }
}
@media (prefers-reduced-motion: reduce) {
  .guest-walker, .guest-bubble, .guest-paw { animation:none !important; }
  .guest-arrival .guest-flip { animation:none; }
  .guest-burst { display:none; }
}

/* ── 한 권의 노트 (st.container(key="guest_book") 안에서만 적용) ──────────
   일기장 첫 장·탭·오늘의 일기·카드 앨범을 노트 한 권에 담는다. 안쪽 조각은 종이 효과를 빼고 노트 위에 바로 쓴다. */
.st-key-guest_book {
  position:relative; margin-top:18px; padding:30px 18px 22px 54px; border-radius:4px 18px 18px 4px;
  background-color:#fffaf0;
  background-image:
    linear-gradient(90deg, transparent 38px, rgba(242,155,184,.55) 38px 40px, transparent 40px),
    repeating-linear-gradient(180deg, transparent 0 31px, rgba(196,176,200,.3) 31px 32px);
  box-shadow:0 1px 0 #efe3d5, 0 10px 24px rgba(40,20,40,.22); color:#4a3640;
}
.st-key-guest_book::before {  /* 스프링 구멍 */
  content:""; position:absolute; left:12px; top:16px; bottom:16px; width:14px;
  background:radial-gradient(circle, #ddd2da 0 4.5px, transparent 5.5px) 0 0 / 14px 32px repeat-y;
}
.st-key-guest_book::after {  /* 마스킹 테이프 */
  content:""; position:absolute; top:-12px; left:50%; width:118px; height:26px; transform:translateX(-50%) rotate(-2deg);
  background:repeating-linear-gradient(45deg, rgba(255,186,208,.88) 0 8px, rgba(255,214,227,.88) 8px 16px);
  box-shadow:0 1px 3px rgba(0,0,0,.15);
}
.st-key-guest_book .guest-paper { margin:0; padding:4px 0; background:none; box-shadow:none; border-radius:0; }
.st-key-guest_book .guest-paper::before, .st-key-guest_book .guest-tape { display:none; }
.st-key-guest_book .guest-paper.guest-cover { padding-bottom:22px; border-bottom:2px dashed rgba(196,176,200,.6); }
.st-key-guest_book [data-testid="stTabs"] { margin-top:14px; }
.st-key-guest_book [class*="st-key-guest_arrival_"] {
  padding-bottom:16px; border-bottom:2px dashed rgba(196,176,200,.7); scroll-margin-top:72px;  /* 위쪽 앱 막대에 제목이 가리지 않게 */
}

/* 탭 → 노트 옆에 붙인 인덱스 스티커 (Streamlit 탭: div[role=tablist] > div[role=tab]#stTab) */
.st-key-guest_book [role="tablist"] { gap:6px; border-bottom:2px solid #f0dfe7; }
.st-key-guest_book [data-testid="stTab"] > div:not([data-testid]) { display:none; }  /* 기본 밑줄 */
.st-key-guest_book [data-testid="stTab"] {
  min-height:44px; padding:6px 18px 4px; margin-bottom:-2px; border:2px solid #f0dfe7; border-bottom:none;
  border-radius:14px 14px 0 0; background:#f7eef3; cursor:pointer;
}
.st-key-guest_book [data-testid="stTab"] p { font-family:'Jua', 'Gowun Dodum', sans-serif; font-size:17px; font-weight:400; color:#9a8494; }
.st-key-guest_book [data-testid="stTab"][aria-selected="true"] { background:#ffdbe7; border-color:#f6b9cc; }
.st-key-guest_book [data-testid="stTab"][aria-selected="true"] p { color:#c23d6a; }
.st-key-guest_book [data-testid="stTab"]:nth-child(2)[aria-selected="true"] { background:#e6defa; border-color:#cdbff0; }
.st-key-guest_book [data-testid="stTab"]:nth-child(2)[aria-selected="true"] p { color:#6b55b0; }
.st-key-guest_book [data-testid="stTab"]:focus-visible { outline:2px dashed #c23d6a; outline-offset:2px; }

/* 노트 안의 기본 위젯 글씨가 어두운 테마에서도 읽히게 */
.st-key-guest_book [data-testid="stWidgetLabel"] p, .st-key-guest_book [data-testid="stRadio"] label p { color:#4a3640; }
.st-key-guest_book [data-testid="stRadioOption"] > div > div:first-child { background:#fff; box-shadow:inset 0 0 0 2px #e4c6d4; }
.st-key-guest_book [data-testid="stRadioOption"] > span:has(input:checked) + div > div:first-child {
  background:#f29bb8; box-shadow:inset 0 0 0 3px #fff, 0 0 0 2px #f29bb8;
}
.st-key-guest_book [data-baseweb="select"] > div { background:#fff; border-color:#e9d6e0; }
.st-key-guest_book [data-baseweb="select"] * { color:#4a3640; }

/* 앨범에 붙이기 버튼 → 손으로 찢어 붙인 마스킹 테이프 */
.st-key-guest_book [class*="st-key-guest_arrival_"] button[kind="primary"] {
  min-height:44px; padding:6px 30px; border:none; border-radius:2px; transform:rotate(-1.5deg);
  background:repeating-linear-gradient(-45deg, #ffcfe0 0 9px, #ffe2ec 9px 18px);
  clip-path:polygon(0 8%, 3% 0, 97% 4%, 100% 0, 98% 50%, 100% 100%, 96% 94%, 4% 100%, 0 96%, 2% 50%);
  box-shadow:none; filter:drop-shadow(0 2px 2px rgba(74,54,64,.22)); transition:transform .2s;
}
.st-key-guest_book [class*="st-key-guest_arrival_"] button[kind="primary"] p {
  font-family:'Jua', 'Gowun Dodum', sans-serif; font-size:18px; font-weight:400; color:#9c3460;
}
.st-key-guest_book [class*="st-key-guest_arrival_"] button[kind="primary"]:hover { transform:rotate(0deg) translateY(-2px); }
.st-key-guest_book [class*="st-key-guest_arrival_"] button[kind="primary"]:focus-visible { outline:2px dashed #c23d6a; outline-offset:4px; }
@media (prefers-reduced-motion: reduce) {
  .st-key-guest_book [class*="st-key-guest_arrival_"] button[kind="primary"] { transition:none; }
}

/* ── 카드 앨범 · 상세 ────────────────────────── */
.guest-album { background-color:#fbf4ea; }
.guest-album .guest-grid { grid-template-columns:repeat(auto-fill, minmax(136px, 1fr)); gap:14px; }
.guest-detail { display:flex; flex-wrap:wrap; gap:22px; align-items:flex-start; }
.guest-detail .guest-reveal { width:220px; margin:0; }
.guest-notes { flex:1; min-width:200px; }
.guest-notes dt { font-family:'Poor Story', 'Gowun Dodum', cursive; font-size:16px; color:#8a6a7c; }
.guest-notes dd { margin:0 0 0 10px; }

@media (max-width:480px) {
  .guest-paper { padding:26px 12px 16px 40px; }
  .st-key-guest_book { padding:26px 10px 18px 42px; }
  .st-key-guest_book [data-testid="stTab"] { padding:6px 12px 4px; }
  .guest-stamp { transform:rotate(-10deg) scale(.8); transform-origin:top right; margin:0 -6px -18px 0; }
  .guest-h { font-size:24px; }
  .guest-polas { gap:10px; }
}
</style>
"""


def _korean_date(d: date) -> str:
    return f"{d.year}년 {d.month}월 {d.day}일 {WEEKDAYS[d.weekday()]}요일"


def header(
    today: date, day_num: int, streak: int, best: int,
    week: list[tuple[date, set[str]]], collected: int, total: int,
) -> str:
    """일기장 첫 장: 날짜, N일째 도장, 최근 7일 스티커, 모은 카드."""
    toes = "".join(f'<i class="guest-toe guest-t{i}"></i>' for i in range(1, 5))
    stamp = (
        f'<div class="guest-stamp" role="img" aria-label="밥때 손님 {day_num}일째 발도장">{toes}'
        f'<div class="guest-pad"><b>{day_num}일째</b><small>밥때 손님</small></div></div>'
        if day_num else ""
    )
    if best:
        streak_line = f"🔥 세 끼 모두 챙긴 날 <b>{streak}일</b> 연속 · 최고 {best}일"
    elif day_num:
        streak_line = "세 끼를 다 채우면 발도장 스티커가 붙어요 🐾"
    else:
        streak_line = "끼니를 기록하면 첫 손님이 찾아와요"

    days = []
    for d, slots in week:
        n = len(slots)
        cls = "guest-day" + (" guest-today" if d == today else "") + (" guest-full" if n == len(SLOTS) else " guest-some" if n else "")
        inside = "🐾" if n == len(SLOTS) else "".join("●" if s in slots else "○" for s in SLOTS)
        label = "오늘" if d == today else WEEKDAYS[d.weekday()]
        days.append(f'<div class="{cls}" title="{d.isoformat()} · {n}/3 끼">{label}<div class="guest-sticker">{inside}</div></div>')

    pct = round(collected / total * 100) if total else 0
    return (
        CSS + '<div class="guest-paper guest-cover"><div class="guest-tape"></div>'
        f'<div class="guest-head"><div class="guest-head-text"><div class="guest-date">{_korean_date(today)}</div>'
        '<p class="guest-h">밥때 손님 일기</p>'
        f'<div>{streak_line}</div></div>{stamp}</div>'
        f'<div class="guest-week" aria-label="최근 7일 끼니 스티커">{"".join(days)}</div>'
        f'<div class="guest-collect"><span class="guest-hand">📒 모은 카드 <b>{collected}</b> / {total}장</span>'
        f'<div class="guest-bar" role="progressbar" aria-valuenow="{collected}" aria-valuemax="{total}"><i style="width:{pct}%"></i></div></div>'
        "</div>"
    )


def _polaroid(slot: str, breed: Breed | None, guest_url: str | None, meal: bytes | None, menu: str | None) -> str:
    label = SLOT_LABELS[slot]
    if breed is None:
        return (
            f'<div class="guest-pola guest-empty"><div class="guest-pic">아직 비어 있어요<br>🍚</div>'
            f'<div class="guest-cap">{label}</div></div>'
        )
    guest_img = cards.img_src(breed, guest_url)
    if meal:
        pic = (
            f'<img src="{cards.jpeg_src(meal)}" alt="내 {label} 밥상">'
            f'<img class="guest-visitor" src="{guest_img}" alt="{escape(breed.name)}">'
        )
    else:
        pic = f'<img src="{guest_img}" alt="{escape(breed.name)}">'
    menu_line = f'<div class="guest-menu">🍴 {escape(menu)}</div>' if menu else ""
    return (
        f'<div class="guest-pola"><div class="guest-pic">{pic}</div>'
        f'<div class="guest-cap">{label} · {escape(breed.name)}</div>{menu_line}</div>'
    )


def today_page(slots: dict[str, tuple[Breed, str | None, bytes | None, str | None]], waiting: int) -> str:
    """오늘의 3칸을 폴라로이드로 붙인 일기 한 장."""
    filled = len(slots)
    if filled == len(SLOTS):
        line = "오늘은 세 끼 모두 손님과 함께 먹었다! 🐾"
    elif filled:
        line = f"오늘 {filled}번 손님이 다녀갔다. 다음 끼니에는 누가 올까?"
    else:
        line = "아직 오늘의 손님이 없다. 밥을 먹으면 누군가 찾아올 거야."
    if waiting:
        line += f" (문 앞에 손님 {waiting}명이 기다리는 중)"
    pols = "".join(
        _polaroid(s, *(slots[s] if s in slots else (None, None, None, None))) for s in SLOTS
    )
    return (
        CSS + cards.CSS + '<div class="guest-paper"><div class="guest-tape guest-lavender"></div>'
        f'<p class="guest-h2">오늘의 밥상 손님</p><div class="guest-hand">{line}</div>'
        f'<div class="guest-polas">{pols}</div></div>'
    )


# 발자국: 걸어온 길(오른쪽 위 → 가운데)의 0.2·0.4·0.6·0.8 지점에 차례로 찍힌다. (진행률, 좌우 발 어긋남 px)
_PAW_STEPS = ((0.2, 7), (0.4, -7), (0.6, 7), (0.8, -7))
_BURST = ((-90, -70), (95, -60), (-110, 10), (110, 25), (-70, 85), (75, 90), (0, -105), (5, 110))  # 별가루 방향(px)


def _svg_src(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


# 기록 영역 아래에 있어 연출을 놓치지 않도록, 손님이 오면 한 번만 그 자리로 부드럽게 내려 준다.
_SCROLL_JS = """<script>
(() => {
  const id = '__ID__';
  window.guestScrolled = window.guestScrolled || new Set();
  if (window.guestScrolled.has(id)) return;
  window.guestScrolled.add(id);
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const el = document.getElementById(id);
  (el?.closest('[class*="st-key-guest_arrival_"]') || el?.closest('.guest-paper'))?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
})();
</script>"""


def _walk_in(breed: Breed, visit_id: str) -> str:
    """카드가 나오기 전, 손님이 오른쪽 위에서 발자국을 남기며 가운데로 총총 다가와 인사한다."""
    paw = f'<img src="{_svg_src(PAW_SVG)}" alt="">'
    paws = "".join(
        f'<span class="guest-paw" style="left:calc(50% + min({34 * (1 - t):.1f}cqw, {230 * (1 - t):.0f}px) + {side - 7}px); '
        f'bottom:{80 * (1 - t) + 4:.0f}px; transform:rotate(-109deg) scale({0.55 + 0.45 * t:.2f}); '
        f'animation-delay:{WALK_SECONDS * t:.2f}s">{paw}</span>'
        for t, side in _PAW_STEPS
    )
    hello = "멍!" if breed.species == "dog" else "냥~"
    walk_id = f"guest-walk-{escape(visit_id)}"
    return (
        f'<div class="guest-walk" id="{walk_id}" role="img" aria-label="{escape(breed.name)} 손님이 총총 다가와 인사해요">{paws}'
        f'<div class="guest-walker"><span class="guest-bubble">{hello}</span>'
        f'<img src="{_svg_src(guest_walker_svg(breed))}" alt=""></div></div>' + _SCROLL_JS.replace("__ID__", walk_id)
    )


def _burst() -> str:
    stars = "".join(f'<i style="--x:{x}px; --y:{y}px">✦</i>' for x, y in _BURST)
    return f'<div class="guest-burst" aria-hidden="true">{stars}</div>'


def arrival(
    visit_id: str, slot: str, breed: Breed, card_html: str, meal: bytes | None, menu: str | None,
    is_new: bool, loyalty: Loyalty, photo_ok: bool,
) -> str:
    """손님 방문 일기: 손님이 다가와 인사하고, 밥상 폴라로이드 옆에 카드가 뿅 나온다."""
    label = SLOT_LABELS[slot]
    name = escape(breed.name)
    if is_new:
        note = f"처음 보는 손님이다! <b>{name}</b> 카드를 얻었다 ✨"
    elif loyalty.remaining is not None:
        note = f"<b>{name}</b>가 또 놀러 왔다. 다음 단골 레벨까지 {loyalty.remaining}번!"
    else:
        note = f"우리 찐단골 <b>{name}</b>가 또 왔다 👑"
    meal_pola = (
        f'<div class="guest-pola"><div class="guest-pic"><img src="{cards.jpeg_src(meal)}" alt="내 {label} 밥상"></div>'
        f'<div class="guest-cap">내 {label} 밥상</div></div>'
        if meal else ""
    )
    if menu:
        sniff = f"{escape(menu)} 냄새를 맡고"
    else:
        sniff = f"{label} 밥 냄새를 맡고" if meal else f"{label}을 먹고 있는데"
    missing = '<div class="guest-muted">손님 사진을 불러오지 못해 그림으로 대신 붙였다.</div>' if not photo_ok else ""
    return (
        CSS + cards.CSS + '<div class="guest-paper guest-plain guest-arrival"><div class="guest-tape guest-mint"></div>'
        f'<p class="guest-h2">🔔 똑똑— {sniff} 손님이 찾아왔다!</p>'
        f"{_walk_in(breed, visit_id)}"
        f'<div class="guest-entry">{meal_pola}<div class="guest-reveal">{_burst()}<div class="guest-flip">{card_html}</div></div></div>'
        f'<div class="guest-hand">{note}</div>{missing}</div>' + cards.TILT_JS
    )


def album(title: str, collected: int, shown: int, cards_html: list[str], empty: bool) -> str:
    """카드 앨범 한 장"""
    hint = '<div class="guest-hand">아직 모은 카드가 없다. 끼니를 기록하면 첫 카드가 생긴다!</div>' if empty else ""
    return (
        CSS + cards.CSS + '<div class="guest-paper guest-plain guest-album"><div class="guest-tape"></div>'
        f'<p class="guest-h2">📒 카드 앨범 · {escape(title)} {collected} / {shown}장</p>{hint}'
        f'<div class="guest-grid">{"".join(cards_html)}</div></div>' + cards.TILT_JS
    )


def detail(breed: Breed, card: CollectionCard, card_html: str, loyalty: Loyalty) -> str:
    """카드 한 장을 꺼내 메모를 적어 둔 일기 한 장"""
    nxt = f" (다음 레벨까지 {loyalty.remaining}번)" if loyalty.remaining is not None else " (최고 레벨!)"
    return (
        CSS + cards.CSS + '<div class="guest-paper"><div class="guest-tape guest-lavender"></div>'
        f'<div class="guest-detail"><div class="guest-reveal">{card_html}</div><dl class="guest-notes">'
        f'<p class="guest-h2">{escape(breed.name)}</p><div>{escape(breed.description)}</div>'
        f'<dt>처음 만난 날</dt><dd>{card.first_met_at[:10].replace("-", ".")}</dd>'
        f"<dt>만난 횟수</dt><dd>{card.met_count}번</dd>"
        f"<dt>단골 레벨</dt><dd>{cards.LEVEL_BADGES.get(loyalty.level, '')} Lv.{loyalty.level} {loyalty.title}{nxt}</dd>"
        "</dl></div></div>" + cards.TILT_JS
    )
