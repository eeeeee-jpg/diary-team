"""트레이딩 카드 모양 HTML.

모든 클래스에 guest- 접두사를 붙여 다른 서비스 화면에 영향을 주지 않게 한다.
shared/ 스타일 헬퍼가 나오면 이 CSS를 그쪽 방식으로 옮긴다 (README "팀에 확인할 것").
"""

from __future__ import annotations

import base64
from datetime import date
from html import escape

from .config import BREEDS, RARITY_LABELS, SLOT_LABELS, SLOTS, SPECIES_LABELS
from .illustration import guest_svg
from .logic import loyalty_of
from .models import Breed, CollectionCard

LEVEL_BADGES = {1: "🎀", 2: "⭐", 3: "💖", 4: "👑"}
RARITY_STARS = {"common": "★", "rare": "★★", "legendary": "★★★"}
WEEKDAYS = "월화수목금토일"
_NUMBER = {b.id: i + 1 for i, b in enumerate(BREEDS)}

CSS = """
<style>
.guest-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(150px, 1fr)); gap:14px; }
.guest-card {
  position:relative; border-radius:18px; padding:8px; overflow:hidden;
  background:linear-gradient(145deg, #e9e4f2, #c9c2d8); box-shadow:0 4px 12px rgba(60,40,70,.25);
  font-family:inherit; color:#3d2b38;
}
.guest-card.guest-rare { background:linear-gradient(145deg, #ffd6e4, #f29bb8); }
.guest-card.guest-legendary { background:linear-gradient(145deg, #fff3b0, #e9b949 45%, #fff3b0 55%, #d99a2b); }
.guest-card.guest-legendary::after {
  content:""; position:absolute; inset:0; pointer-events:none;
  background:linear-gradient(115deg, transparent 30%, rgba(255,255,255,.65) 50%, transparent 70%);
  transform:translateX(-120%); animation:guest-shine .9s ease-out .2s 1 forwards;
}
.guest-inner { background:#fffaf4; border-radius:12px; padding:8px; }
.guest-top { display:flex; justify-content:space-between; font-size:12px; font-weight:700; color:#8a6a7c; }
.guest-stars { color:#d9902b; letter-spacing:1px; }
.guest-photo { margin:6px 0; aspect-ratio:1/1; border-radius:10px; overflow:hidden; background:#f1e6ee; }
.guest-photo img { width:100%; height:100%; object-fit:cover; display:block; }
.guest-name { font-size:16px; font-weight:800; line-height:1.3; }
.guest-meta { font-size:12px; color:#7a6272; }
.guest-foot { margin-top:6px; padding-top:6px; border-top:1px dashed #e2cfd9; font-size:12px; color:#5a4250; }
.guest-new {
  position:absolute; top:44px; left:20px; z-index:2; border-radius:999px;
  background:#e2557f; color:#fff; font-size:11px; font-weight:800; padding:3px 10px;
  box-shadow:0 2px 6px rgba(0,0,0,.25);
}
.guest-card.guest-lv2 .guest-inner { box-shadow:inset 0 0 0 2px #cdbff0; }
.guest-card.guest-lv3 .guest-inner { box-shadow:inset 0 0 0 3px #f29bb8; }
.guest-card.guest-lv4 .guest-inner { box-shadow:inset 0 0 0 3px #e9b949, inset 0 0 0 6px #fff3b0; }

.guest-card.guest-back { background:repeating-linear-gradient(45deg, #d8cfe6 0 10px, #cbc1db 10px 20px); }
.guest-card.guest-back .guest-inner { background:rgba(255,250,244,.75); }
.guest-card.guest-back .guest-photo { background:transparent; display:grid; place-items:center; }
.guest-card.guest-back .guest-photo img { width:70%; height:auto; opacity:.55; }
.guest-card.guest-back .guest-name { color:#9a8796; }

.guest-reveal { perspective:1000px; max-width:260px; margin:0 auto; }
.guest-reveal .guest-card { animation:guest-flip .8s ease-out both; }

.guest-slots { display:grid; grid-template-columns:repeat(3, 1fr); gap:10px; }
.guest-slot {
  border:2px dashed #d9c6d3; border-radius:16px; padding:10px 6px; text-align:center;
  background:rgba(255,250,244,.06); min-height:120px; display:flex; flex-direction:column; justify-content:center; gap:4px;
}
.guest-slot b { font-size:15px; }
.guest-slot small { font-size:12px; opacity:.75; }
.guest-slot .guest-photo { width:72px; margin:4px auto; border-radius:50%; aspect-ratio:1/1; }
.guest-slot.guest-filled { border-style:solid; border-color:#f29bb8; }
.guest-meal { position:relative; aspect-ratio:1/1; border-radius:12px; overflow:hidden; margin:4px 0; }
.guest-meal .guest-food { width:100%; height:100%; object-fit:cover; display:block; }
.guest-meal .guest-visitor {
  position:absolute; right:6px; bottom:6px; width:42%; aspect-ratio:1/1; border-radius:50%;
  object-fit:cover; border:3px solid #fffaf4; box-shadow:0 2px 6px rgba(0,0,0,.3);
}

.guest-days { display:flex; align-items:center; gap:12px; flex-wrap:wrap; margin:4px 0 8px; }
.guest-daynum {
  background:linear-gradient(135deg, #ffd6e4, #cdbff0); color:#3d2b38; border-radius:16px;
  padding:8px 14px; font-weight:800; font-size:18px;
}
.guest-daynum small { display:block; font-size:12px; font-weight:600; opacity:.8; }
.guest-week { display:grid; grid-template-columns:repeat(7, 1fr); gap:6px; flex:1; min-width:260px; }
.guest-day { text-align:center; border-radius:10px; padding:4px 0; font-size:11px; background:rgba(205,191,240,.15); }
.guest-day.guest-today { outline:2px solid #e2557f; }
.guest-day.guest-full { background:rgba(242,155,184,.35); }
.guest-dots { letter-spacing:1px; font-size:10px; }

@keyframes guest-flip { from { transform:rotateY(90deg) scale(.9); opacity:.2; } to { transform:none; opacity:1; } }
@keyframes guest-shine { to { transform:translateX(120%); } }
@media (prefers-reduced-motion: reduce) {
  .guest-reveal .guest-card, .guest-card.guest-legendary::after { animation:none; }
}
</style>
"""


def _img_src(breed: Breed, url: str | None, silhouette: bool = False) -> str:
    if url and not silhouette:
        return escape(url)
    svg = guest_svg(breed, silhouette=silhouette)
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def card(breed: Breed, c: CollectionCard | None, image_url: str | None = None, is_new: bool = False) -> str:
    """도감 카드 1장. c가 None이면 아직 못 만난 카드(뒷면 + 실루엣)."""
    no = f"No.{_NUMBER[breed.id]:02d}"
    if c is None:
        return (
            f'<div class="guest-card guest-back"><div class="guest-inner">'
            f'<div class="guest-top"><span>{no}</span><span class="guest-stars">{RARITY_STARS[breed.rarity]}</span></div>'
            f'<div class="guest-photo"><img src="{_img_src(breed, None, silhouette=True)}" alt="아직 만나지 못한 손님"></div>'
            f'<div class="guest-name">???</div>'
            f'<div class="guest-meta">{RARITY_LABELS[breed.rarity]} · {SPECIES_LABELS[breed.species]}</div>'
            f'<div class="guest-foot">아직 만나지 못한 손님</div>'
            f"</div></div>"
        )
    lv = loyalty_of(c.met_count)
    new = '<div class="guest-new">NEW!</div>' if is_new else ""
    return (
        f'<div class="guest-card guest-{breed.rarity} guest-lv{lv.level}">{new}<div class="guest-inner">'
        f'<div class="guest-top"><span>{no}</span><span class="guest-stars">{RARITY_STARS[breed.rarity]}</span></div>'
        f'<div class="guest-photo"><img src="{_img_src(breed, image_url or c.image_url)}" alt="{escape(breed.name)} 사진"></div>'
        f'<div class="guest-name">{escape(breed.name)}</div>'
        f'<div class="guest-meta">{RARITY_LABELS[breed.rarity]} · {SPECIES_LABELS[breed.species]}</div>'
        f'<div class="guest-foot">{LEVEL_BADGES.get(lv.level, "")} Lv.{lv.level} {lv.title} · {c.met_count}번 만남</div>'
        f"</div></div>"
    )


def grid(cards_html: list[str]) -> str:
    return CSS + '<div class="guest-grid">' + "".join(cards_html) + "</div>"


def reveal(card_html: str) -> str:
    """손님 방문 연출: 카드가 뒤집히며 나타난다 (0.8초)."""
    return CSS + f'<div class="guest-reveal">{card_html}</div>'


def jpeg_src(data: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(data).decode()


def today_slots(slots: dict[str, tuple[Breed, str | None, bytes | None]]) -> str:
    """오늘의 3칸. (손님 품종, 손님 사진, 내 밥상 사진). 없는 칸은 아직 손님이 오지 않은 칸."""
    cells = []
    for slot in SLOTS:
        got = slots.get(slot)
        if got:
            breed, url, meal = got
            if meal:
                picture = (
                    f'<div class="guest-meal"><img class="guest-food" src="{jpeg_src(meal)}" alt="내 {SLOT_LABELS[slot]} 밥상">'
                    f'<img class="guest-visitor" src="{_img_src(breed, url)}" alt="{escape(breed.name)}"></div>'
                )
            else:
                picture = f'<div class="guest-photo"><img src="{_img_src(breed, url)}" alt="{escape(breed.name)}"></div>'
            cells.append(
                f'<div class="guest-slot guest-filled"><b>{SLOT_LABELS[slot]}</b>{picture}'
                f"<small>{escape(breed.name)}</small></div>"
            )
        else:
            cells.append(f'<div class="guest-slot"><b>{SLOT_LABELS[slot]}</b><small>🍚 끼니를 기록하면<br>손님이 와요</small></div>')
    return CSS + '<div class="guest-slots">' + "".join(cells) + "</div>"


def day_board(day_num: int, streak: int, best: int, week: list[tuple[date, set[str]]], today: date) -> str:
    """며칠째인지 + 최근 7일 도장판 (하루 3칸)."""
    if day_num:
        head = f"밥때 손님 {day_num}일째"
        sub = f"🔥 세 끼 연속 {streak}일 · 최고 {best}일" if best else "세 끼를 다 채우면 연속 기록 시작"
    else:
        head, sub = "첫 손님을 기다려요", "끼니를 기록하면 1일째가 시작돼요"
    days = []
    for d, slots in week:
        dots = "".join("●" if s in slots else "○" for s in SLOTS)
        cls = "guest-day" + (" guest-today" if d == today else "") + (" guest-full" if len(slots) == len(SLOTS) else "")
        label = "오늘" if d == today else WEEKDAYS[d.weekday()]
        days.append(f'<div class="{cls}" title="{d.isoformat()}">{label}<br>{d.day}<div class="guest-dots">{dots}</div></div>')
    return (
        CSS + f'<div class="guest-days"><div class="guest-daynum">{head}<small>{sub}</small></div>'
        f'<div class="guest-week" aria-label="최근 7일 끼니 도장">{"".join(days)}</div></div>'
    )
