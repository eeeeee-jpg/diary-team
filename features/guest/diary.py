"""다이어리 느낌의 페이지 조각 (줄 노트, 마스킹 테이프, 도장, 폴라로이드).

모든 클래스에 guest- 접두사를 붙여 다른 서비스 화면에 영향을 주지 않게 한다.
폰트: Gaegu(손글씨 제목), Gowun Dodum(본문) — 둘 다 Google Fonts, SIL Open Font License.
"""

from __future__ import annotations

from datetime import date
from html import escape

from . import cards
from .config import SLOT_LABELS, SLOTS
from .logic import Loyalty
from .models import Breed, CollectionCard

WEEKDAYS = "월화수목금토일"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Gaegu:wght@400;700&family=Gowun+Dodum&display=swap');

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
.guest-h { font-family:'Gaegu', cursive; font-weight:700; font-size:30px; line-height:32px; margin:0; color:#3d2b38; }
.guest-h2 { font-family:'Gaegu', cursive; font-weight:700; font-size:24px; line-height:32px; margin:0; color:#3d2b38; }
.guest-hand { font-family:'Gaegu', cursive; font-size:20px; line-height:32px; color:#5a4250; }
.guest-date { font-family:'Gaegu', cursive; font-size:20px; line-height:32px; color:#8a6a7c; }
.guest-muted { color:#8a7480; font-size:14px; }

/* 일차 도장 */
.guest-stamp {
  position:absolute; top:22px; right:18px; width:86px; height:86px; border-radius:50%;
  border:3px solid #e2557f; box-shadow:inset 0 0 0 3px #fffaf0, inset 0 0 0 5px rgba(226,85,127,.45);
  color:#e2557f; font-family:'Gaegu', cursive; font-weight:700; font-size:24px; line-height:1;
  display:flex; flex-direction:column; align-items:center; justify-content:center; transform:rotate(-12deg); opacity:.88;
}
.guest-stamp small { font-size:13px; margin-top:3px; }

/* 최근 7일 스티커 */
.guest-week { display:grid; grid-template-columns:repeat(7, minmax(0, 1fr)); gap:6px; margin:8px 0 2px; max-width:440px; }
.guest-day { text-align:center; line-height:1.25; font-size:12px; color:#8a6a7c; }
.guest-sticker {
  width:36px; height:36px; margin:2px auto 0; border-radius:50%; display:grid; place-items:center;
  background:#f6eef2; border:2px dashed #e4d3dd; font-size:10px; letter-spacing:1px; color:#c08aa3;
}
.guest-day.guest-some .guest-sticker { background:#ffe7ef; border:2px solid #f6b9cc; }
.guest-day.guest-full .guest-sticker { background:#ffd1e1; border:2px solid #f29bb8; font-size:18px; letter-spacing:0; }
.guest-day.guest-today { color:#e2557f; font-weight:700; }

/* 모은 카드 막대 */
.guest-collect { margin-top:8px; }
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
.guest-pola .guest-cap { font-family:'Gaegu', cursive; font-size:17px; line-height:28px; color:#4a3640; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.guest-pola.guest-empty .guest-pic {
  display:grid; place-items:center; background:#fbf6f1; border:2px dashed #e4d3dd;
  font-family:'Gaegu', cursive; font-size:16px; line-height:1.3; color:#b39aa8; padding:6px;
}

/* ── 손님 방문 일기 ─────────────────────────── */
.guest-entry { display:flex; flex-wrap:wrap; gap:18px; align-items:center; justify-content:center; margin:6px 0; }
.guest-entry .guest-pola { width:190px; }
.guest-entry .guest-reveal { width:230px; margin:0; }

/* ── 카드 앨범 · 상세 ────────────────────────── */
.guest-album { background-color:#fbf4ea; }
.guest-album .guest-grid { grid-template-columns:repeat(auto-fill, minmax(136px, 1fr)); gap:14px; }
.guest-detail { display:flex; flex-wrap:wrap; gap:22px; align-items:flex-start; }
.guest-detail .guest-reveal { width:220px; margin:0; }
.guest-notes { flex:1; min-width:200px; }
.guest-notes dt { font-family:'Gaegu', cursive; font-size:18px; color:#8a6a7c; }
.guest-notes dd { margin:0 0 0 10px; }

@media (max-width:480px) {
  .guest-paper { padding:26px 12px 16px 40px; }
  .guest-stamp { width:68px; height:68px; font-size:19px; top:16px; right:10px; }
  .guest-h { font-size:25px; }
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
    stamp = f'<div class="guest-stamp">{day_num}일째<small>밥때 손님</small></div>' if day_num else ""
    if best:
        streak_line = f"🔥 세 끼 모두 챙긴 날 <b>{streak}일</b> 연속 · 최고 {best}일"
    elif day_num:
        streak_line = "세 끼를 다 채우면 꽃 스티커가 붙어요 🌸"
    else:
        streak_line = "끼니를 기록하면 첫 손님이 찾아와요"

    days = []
    for d, slots in week:
        n = len(slots)
        cls = "guest-day" + (" guest-today" if d == today else "") + (" guest-full" if n == len(SLOTS) else " guest-some" if n else "")
        inside = "🌸" if n == len(SLOTS) else "".join("●" if s in slots else "○" for s in SLOTS)
        label = "오늘" if d == today else WEEKDAYS[d.weekday()]
        days.append(f'<div class="{cls}" title="{d.isoformat()} · {n}/3 끼">{label}<div class="guest-sticker">{inside}</div></div>')

    pct = round(collected / total * 100) if total else 0
    return (
        CSS + '<div class="guest-paper"><div class="guest-tape"></div>'
        f'{stamp}<div class="guest-date">{_korean_date(today)}</div>'
        '<p class="guest-h">밥때 손님 일기</p>'
        f'<div>{streak_line}</div>'
        f'<div class="guest-week" aria-label="최근 7일 끼니 스티커">{"".join(days)}</div>'
        f'<div class="guest-collect"><span class="guest-hand">📒 모은 카드 <b>{collected}</b> / {total}장</span>'
        f'<div class="guest-bar" role="progressbar" aria-valuenow="{collected}" aria-valuemax="{total}"><i style="width:{pct}%"></i></div></div>'
        "</div>"
    )


def _polaroid(slot: str, breed: Breed | None, guest_url: str | None, meal: bytes | None) -> str:
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
    return f'<div class="guest-pola"><div class="guest-pic">{pic}</div><div class="guest-cap">{label} · {escape(breed.name)}</div></div>'


def today_page(slots: dict[str, tuple[Breed, str | None, bytes | None]], waiting: int) -> str:
    """오늘의 3칸을 폴라로이드로 붙인 일기 한 장."""
    filled = len(slots)
    if filled == len(SLOTS):
        line = "오늘은 세 끼 모두 손님과 함께 먹었다! 🌸"
    elif filled:
        line = f"오늘 {filled}번 손님이 다녀갔다. 다음 끼니에는 누가 올까?"
    else:
        line = "아직 오늘의 손님이 없다. 밥을 먹으면 누군가 찾아올 거야."
    if waiting:
        line += f" (문 앞에 손님 {waiting}명이 기다리는 중)"
    pols = "".join(
        _polaroid(s, *(slots[s] if s in slots else (None, None, None))) for s in SLOTS
    )
    return (
        CSS + cards.CSS + '<div class="guest-paper"><div class="guest-tape guest-lavender"></div>'
        f'<p class="guest-h2">오늘의 밥상 손님</p><div class="guest-hand">{line}</div>'
        f'<div class="guest-polas">{pols}</div></div>'
    )


def arrival(slot: str, breed: Breed, card_html: str, meal: bytes | None, is_new: bool, loyalty: Loyalty, photo_ok: bool) -> str:
    """손님 방문 일기: 밥상 폴라로이드 + 뒤집히며 나오는 카드."""
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
    sniff = f"{label} 밥 냄새를 맡고" if meal else f"{label}을 먹고 있는데"
    missing = '<div class="guest-muted">손님 사진을 불러오지 못해 그림으로 대신 붙였다.</div>' if not photo_ok else ""
    return (
        CSS + cards.CSS + '<div class="guest-paper guest-plain"><div class="guest-tape guest-mint"></div>'
        f'<p class="guest-h2">🔔 똑똑— {sniff} 손님이 찾아왔다!</p>'
        f'<div class="guest-entry">{meal_pola}<div class="guest-reveal"><div class="guest-flip">{card_html}</div></div></div>'
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
