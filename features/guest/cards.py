"""트레이딩 카드 모양 HTML.

모든 클래스에 guest- 접두사를 붙여 다른 서비스 화면에 영향을 주지 않게 한다.
shared/ 스타일 헬퍼가 나오면 이 CSS를 그쪽 방식으로 옮긴다 (README "팀에 확인할 것").
카드 기울기·홀로그램은 TILT_JS가 마우스 위치를 CSS 변수로 넘겨 주고, 나머지는 CSS가 그린다.
"""

from __future__ import annotations

import base64
from html import escape

from .config import BREEDS, RARITY_LABELS, SPECIES_LABELS
from .illustration import guest_svg
from .logic import loyalty_of
from .models import Breed, CollectionCard

LEVEL_BADGES = {1: "🎀", 2: "⭐", 3: "💖", 4: "👑"}
RARITY_STARS = {"common": "★", "rare": "★★", "legendary": "★★★"}
SPECIES_ICONS = {"dog": "🐶", "cat": "🐱"}
_NUMBER = {b.id: i + 1 for i, b in enumerate(BREEDS)}

CSS = """
<style>
.guest-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(156px, 1fr)); gap:18px; padding:6px; }

/* ── 카드 틀 ───────────────────────────────── */
/* 희귀도가 오를수록 화려해진다.
   일반: 은빛 펄 테두리 + 마우스를 올리면 옅은 무지개빛
   희귀: 로즈골드 금속 테두리 + 무지개빛 + 반짝이 가루 + 별 2개
   전설: 무지개 금박 테두리 + 은은한 빛무리 + 평소에도 빛나는 별 4개 + 촘촘한 은하 홀로 */
.guest-card {
  --guest-mx:50%; --guest-my:50%; --guest-rx:0deg; --guest-ry:0deg;
  --guest-edge:linear-gradient(150deg, #f7f5fb, #c9c3d8 40%, #fbfaff 52%, #b4adc6 70%, #ebe7f4);
  --guest-holo-opacity:.22;
  --guest-glow:0 0 0 transparent;
  position:relative; border-radius:18px; padding:7px; overflow:hidden; isolation:isolate;
  background:var(--guest-edge); background-size:220% 220%; background-position:var(--guest-mx) var(--guest-my);
  color:#3d2b38; font-family:inherit;
  box-shadow:var(--guest-glow), 0 6px 14px rgba(20,10,30,.35), inset 0 0 0 1px rgba(255,255,255,.6);
  transform:perspective(900px) rotateX(var(--guest-ry)) rotateY(var(--guest-rx));
  transition:transform .45s cubic-bezier(.2,.8,.2,1), box-shadow .45s;
  will-change:transform;
}
.guest-card.guest-active {
  transition:transform .06s linear, box-shadow .2s;
  box-shadow:var(--guest-glow), 0 18px 34px rgba(20,10,30,.5), inset 0 0 0 1px rgba(255,255,255,.8);
}
.guest-card.guest-rare {
  --guest-edge:linear-gradient(135deg, #ffe6ef, #f3a3c0 22%, #fff3f7 36%, #e07a9f 52%, #ffd6e4 66%, #c9587f 82%, #ffe6ef);
  --guest-holo-opacity:.36;
  --guest-glow:0 0 10px rgba(240,130,170,.45);
}
.guest-card.guest-legendary {
  --guest-edge:linear-gradient(115deg, #fff6c4, #f1c24e 14%, #fffbe8 24%, #f7b8d6 34%, #c9b8ff 44%, #b9e4ff 54%,
    #fff2a8 64%, #d99a22 78%, #fff1b0 90%, #f1c24e);
  --guest-holo-opacity:.52;
  --guest-glow:0 0 0 1px rgba(255,232,150,.9), 0 0 18px rgba(255,196,90,.6), 0 0 34px rgba(255,170,210,.35);
  background-size:320% 320%;
}
.guest-inner {
  position:relative; border-radius:12px; padding:8px 8px 9px;
  background:linear-gradient(180deg, #fffdf8, #fbf1ea);
  box-shadow:inset 0 0 0 1px rgba(160,120,140,.18);
}
.guest-card.guest-legendary .guest-inner { box-shadow:inset 0 0 0 2px #f0c75a, inset 0 0 0 4px #fff6d0; }

/* 단골 레벨이 오르면 안쪽 테두리가 바뀐다 (D-4) */
.guest-card.guest-lv2 .guest-inner { box-shadow:inset 0 0 0 2px #cdbff0; }
.guest-card.guest-lv3 .guest-inner { box-shadow:inset 0 0 0 3px #f29bb8; }
.guest-card.guest-lv4 .guest-inner { box-shadow:inset 0 0 0 3px #e9b949, inset 0 0 0 6px #fff3b0; }

.guest-top { display:flex; justify-content:space-between; align-items:center; font-size:11px; font-weight:800; color:#8a6a7c; letter-spacing:.3px; }
.guest-stars { color:#b8aec8; letter-spacing:1px; text-shadow:0 1px 0 #fff; }
.guest-card.guest-rare .guest-stars { color:#e2557f; }
.guest-card.guest-legendary .guest-stars {
  background:linear-gradient(90deg, #e8a21c, #f27aa8, #8f7bff, #3fb6e8, #e8a21c); background-size:200% 100%;
  background-position:var(--guest-mx) 0; -webkit-background-clip:text; background-clip:text; color:transparent;
  text-shadow:none; filter:drop-shadow(0 1px 0 #fff);
}
.guest-card.guest-rare .guest-inner { box-shadow:inset 0 0 0 1px #f6b7cc; }
.guest-photo {
  position:relative; margin:6px 0 0; aspect-ratio:1/1; border-radius:10px; overflow:hidden; background:#f1e6ee;
  box-shadow:inset 0 0 0 2px rgba(255,255,255,.7), 0 2px 6px rgba(60,30,50,.18);
}
.guest-photo img { width:100%; height:100%; object-fit:cover; display:block; }
.guest-banner {
  position:relative; margin:-12px 6px 0; padding:4px 8px; border-radius:999px; text-align:center;
  background:linear-gradient(180deg, #fff, #f6e9f0); box-shadow:0 2px 6px rgba(60,30,50,.2);
  font-size:15px; font-weight:800; line-height:1.3; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}
.guest-card.guest-rare .guest-banner { background:linear-gradient(180deg, #fff, #ffd9e7); }
.guest-card.guest-legendary .guest-banner { background:linear-gradient(180deg, #fffbe6, #ffe28a); }
.guest-meta { margin-top:6px; display:flex; justify-content:center; gap:6px; font-size:11px; color:#7a6272; }
.guest-gem { padding:1px 7px; border-radius:999px; font-weight:800; color:#fff; background:#a99fc0; }
.guest-card.guest-rare .guest-gem { background:#e2557f; }
.guest-card.guest-legendary .guest-gem { background:linear-gradient(90deg, #d38a12, #f3c246); }
.guest-foot { margin-top:6px; padding-top:6px; border-top:1px dashed #e2cfd9; font-size:11px; color:#5a4250; text-align:center; }
.guest-new {
  position:absolute; top:8px; left:8px; z-index:3; border-radius:999px;
  background:#e2557f; color:#fff; font-size:11px; font-weight:800; padding:3px 10px;
  box-shadow:0 2px 6px rgba(0,0,0,.25);
}

/* ── 홀로그램 · 반사광 (마우스 위치 = --guest-mx/--guest-my) ─────── */
.guest-holo, .guest-glare { position:absolute; inset:0; border-radius:inherit; pointer-events:none; z-index:2; opacity:0; transition:opacity .35s; }
/* 일반: 넓고 옅은 무지개 줄무늬 */
.guest-holo {
  mix-blend-mode:color-dodge;
  background:
    repeating-linear-gradient(115deg,
      rgba(255,170,215,.8) 0%, rgba(255,230,170,.8) 10%, rgba(170,240,215,.8) 20%,
      rgba(170,205,255,.8) 30%, rgba(215,180,255,.8) 40%, rgba(255,170,215,.8) 50%);
  background-size:260% 260%;
  background-position:var(--guest-mx) var(--guest-my);
  filter:brightness(.75) contrast(1.3) saturate(1.1);
}
/* 희귀: 더 촘촘하고 진한 무지개 + 반짝이 가루 (가루는 마우스 반대 방향으로 살짝 움직인다) */
.guest-card.guest-rare .guest-holo {
  background:
    radial-gradient(circle, rgba(255,255,255,.95) 0 .8px, transparent 1.4px)
      calc(100% - var(--guest-mx)) calc(100% - var(--guest-my)) / 11px 11px,
    repeating-linear-gradient(115deg,
      rgba(255,119,200,.9) 0%, rgba(255,214,110,.9) 7%, rgba(124,245,200,.9) 14%,
      rgba(122,184,255,.9) 21%, rgba(197,139,255,.9) 28%, rgba(255,119,200,.9) 35%) var(--guest-mx) var(--guest-my) / 260% 260%;
  filter:brightness(.8) contrast(1.45) saturate(1.3);
}
/* 전설: 크기가 다른 금·은 반짝이 3겹 + 엇갈린 무지개(은하 무늬) */
.guest-card.guest-legendary .guest-holo {
  background:
    radial-gradient(circle, rgba(255,255,255,1) 0 1px, transparent 1.8px)
      calc(100% - var(--guest-mx)) calc(100% - var(--guest-my)) / 13px 13px,
    radial-gradient(circle, rgba(255,236,160,.95) 0 1.2px, transparent 2px)
      calc(var(--guest-mx) * .6) calc(var(--guest-my) * .6) / 19px 21px,
    radial-gradient(circle, rgba(255,190,230,.9) 0 .7px, transparent 1.3px) 4px 9px / 7px 7px,
    repeating-linear-gradient(65deg,
      rgba(122,184,255,.55) 0%, rgba(255,119,200,.55) 6%, rgba(255,214,110,.55) 12%, rgba(122,184,255,.55) 18%)
      calc(100% - var(--guest-mx)) var(--guest-my) / 300% 300%,
    repeating-linear-gradient(115deg,
      rgba(255,119,200,.95) 0%, rgba(255,214,110,.95) 6%, rgba(124,245,200,.95) 12%,
      rgba(122,184,255,.95) 18%, rgba(197,139,255,.95) 24%, rgba(255,119,200,.95) 30%) var(--guest-mx) var(--guest-my) / 260% 260%;
  filter:brightness(.85) contrast(1.5) saturate(1.5);
}
.guest-glare {
  mix-blend-mode:overlay;
  background:radial-gradient(farthest-corner circle at var(--guest-mx) var(--guest-my),
    rgba(255,255,255,.9) 0%, rgba(255,255,255,.35) 22%, rgba(0,0,0,.25) 90%);
}
.guest-card.guest-active .guest-holo { opacity:var(--guest-holo-opacity); }
.guest-card.guest-active .guest-glare { opacity:.8; }

/* 반짝이 별 (희귀 2개, 전설 4개). 평소엔 작게, 카드를 움직이면 커지며 깜빡인다 */
.guest-spark {
  position:absolute; z-index:3; pointer-events:none; width:12px; height:12px;
  background:radial-gradient(circle, #fff 0 25%, #ffd6e6 60%, #f39ac0);
  clip-path:polygon(50% 0, 61% 39%, 100% 50%, 61% 61%, 50% 100%, 39% 61%, 0 50%, 39% 39%);
  opacity:0; transform:scale(.4) rotate(0deg); transition:opacity .3s, transform .3s;
}
.guest-card.guest-legendary .guest-spark { background:radial-gradient(circle, #fff 0 25%, #fff2b0 55%, #f1b93a); opacity:.85; transform:scale(.7); }
.guest-card.guest-active .guest-spark { opacity:1; transform:scale(1) rotate(45deg); animation:guest-twinkle .7s ease-in-out infinite alternate; }
.guest-s1 { top:14%; left:11%; }
.guest-s2 { top:44%; right:9%; width:9px; height:9px; animation-delay:.25s !important; }
.guest-s3 { top:62%; left:16%; width:8px; height:8px; animation-delay:.45s !important; }
.guest-s4 { top:7%; right:22%; width:15px; height:15px; animation-delay:.15s !important; }

/* 처음 나타날 때 빛이 한 번 스쳐 지나간다: 희귀는 분홍빛, 전설은 무지개빛으로 더 넓게 */
.guest-card.guest-rare::after, .guest-card.guest-legendary::after {
  content:""; position:absolute; inset:0; pointer-events:none; z-index:2;
  background:linear-gradient(115deg, transparent 35%, rgba(255,220,235,.75) 50%, transparent 65%);
  transform:translateX(-120%); animation:guest-shine .8s ease-out .3s 1 forwards;
}
.guest-card.guest-legendary::after {
  background:linear-gradient(115deg, transparent 22%, rgba(255,240,170,.6) 38%, rgba(255,255,255,.9) 50%,
    rgba(200,190,255,.6) 62%, transparent 78%);
  animation-duration:.95s;
}

/* ── 아직 못 만난 카드 (뒷면) ─────────────────── */
.guest-card.guest-back { --guest-edge:repeating-linear-gradient(45deg, #d8cfe6 0 10px, #cbc1db 10px 20px); }
.guest-card.guest-back .guest-inner { background:rgba(255,250,244,.78); }
.guest-card.guest-back .guest-photo { background:transparent; box-shadow:none; display:grid; place-items:center; }
.guest-card.guest-back .guest-photo img { width:70%; height:auto; opacity:.5; }
.guest-card.guest-back .guest-banner { color:#9a8796; background:rgba(255,255,255,.7); }

/* ── 손님 방문 연출: 뒤집히며 등장 ─────────────── */
.guest-reveal { max-width:270px; margin:0 auto; perspective:1000px; }
.guest-flip { animation:guest-flip .8s cubic-bezier(.2,.8,.2,1) both; }

@keyframes guest-flip { from { transform:rotateY(90deg) scale(.9); opacity:.2; } to { transform:none; opacity:1; } }
@keyframes guest-shine { to { transform:translateX(120%); } }
@keyframes guest-twinkle { from { transform:scale(.75) rotate(0deg); opacity:.6; } to { transform:scale(1.15) rotate(45deg); opacity:1; } }
@media (prefers-reduced-motion: reduce) {
  .guest-flip, .guest-spark, .guest-card.guest-rare::after, .guest-card.guest-legendary::after { animation:none !important; }
  .guest-card.guest-rare::after, .guest-card.guest-legendary::after { display:none; }
  .guest-card { transform:none !important; transition:none; }
}
</style>
"""

# 마우스(또는 손가락) 위치를 카드의 CSS 변수로 넘긴다. 이미 붙인 카드는 건너뛴다.
TILT_JS = """
<script>
(() => {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const MAX = 16;  // 최대 기울기 (도)
  document.querySelectorAll('.guest-card:not([data-guest-tilt])').forEach((card) => {
    card.dataset.guestTilt = '1';
    const move = (e) => {
      const r = card.getBoundingClientRect();
      const x = Math.min(Math.max((e.clientX - r.left) / r.width, 0), 1);
      const y = Math.min(Math.max((e.clientY - r.top) / r.height, 0), 1);
      card.style.setProperty('--guest-mx', `${x * 100}%`);
      card.style.setProperty('--guest-my', `${y * 100}%`);
      card.style.setProperty('--guest-rx', `${(x - 0.5) * MAX * 2}deg`);
      card.style.setProperty('--guest-ry', `${(0.5 - y) * MAX * 2}deg`);
      card.classList.add('guest-active');
    };
    const leave = () => {
      card.classList.remove('guest-active');
      ['--guest-rx', '--guest-ry'].forEach((k) => card.style.setProperty(k, '0deg'));
    };
    card.addEventListener('pointermove', move);
    card.addEventListener('pointerleave', leave);
    card.addEventListener('pointercancel', leave);
  });
})();
</script>
"""


def img_src(breed: Breed, url: str | None, silhouette: bool = False) -> str:
    if url and not silhouette:
        return escape(url)
    svg = guest_svg(breed, silhouette=silhouette)
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def jpeg_src(data: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(data).decode()


_SHINE = '<div class="guest-holo"></div><div class="guest-glare"></div>'
_SPARKS = {"common": 0, "rare": 2, "legendary": 4}  # 희귀도별 반짝이 별 개수


def _sparks(breed: Breed) -> str:
    return "".join(f'<i class="guest-spark guest-s{i}"></i>' for i in range(1, _SPARKS[breed.rarity] + 1))


def card(breed: Breed, c: CollectionCard | None, image_url: str | None = None, is_new: bool = False) -> str:
    """도감 카드 1장. c가 None이면 아직 못 만난 카드(뒷면 + 실루엣)."""
    no = f"No.{_NUMBER[breed.id]:02d}"
    if c is None:
        return (
            f'<div class="guest-card guest-back"><div class="guest-inner">'
            f'<div class="guest-top"><span>{no}</span><span class="guest-stars">{RARITY_STARS[breed.rarity]}</span></div>'
            f'<div class="guest-photo"><img src="{img_src(breed, None, silhouette=True)}" alt="아직 만나지 못한 손님"></div>'
            f'<div class="guest-banner">???</div>'
            f'<div class="guest-meta"><span class="guest-gem">{RARITY_LABELS[breed.rarity]}</span>'
            f"<span>{SPECIES_ICONS[breed.species]} {SPECIES_LABELS[breed.species]}</span></div>"
            f'<div class="guest-foot">아직 만나지 못한 손님</div>'
            f'</div><div class="guest-glare"></div></div>'
        )
    lv = loyalty_of(c.met_count)
    new = '<div class="guest-new">NEW!</div>' if is_new else ""
    return (
        f'<div class="guest-card guest-{breed.rarity} guest-lv{lv.level}"><div class="guest-inner">'
        f'<div class="guest-top"><span>{no}</span><span class="guest-stars">{RARITY_STARS[breed.rarity]}</span></div>'
        f'<div class="guest-photo">{new}<img src="{img_src(breed, image_url or c.image_url)}" alt="{escape(breed.name)} 사진"></div>'
        f'<div class="guest-banner">{escape(breed.name)}</div>'
        f'<div class="guest-meta"><span class="guest-gem">{RARITY_LABELS[breed.rarity]}</span>'
        f"<span>{SPECIES_ICONS[breed.species]} {SPECIES_LABELS[breed.species]}</span></div>"
        f'<div class="guest-foot">{LEVEL_BADGES.get(lv.level, "")} Lv.{lv.level} {lv.title} · {c.met_count}번 만남</div>'
        f"</div>{_SHINE}{_sparks(breed)}</div>"
    )


def grid(cards_html: list[str]) -> str:
    return CSS + '<div class="guest-grid">' + "".join(cards_html) + "</div>" + TILT_JS


def reveal(card_html: str) -> str:
    """손님 방문 연출: 카드가 뒤집히며 나타난다 (0.8초). 뒤집기는 바깥 틀에 걸어 기울기와 겹치지 않게 한다."""
    return CSS + f'<div class="guest-reveal"><div class="guest-flip">{card_html}</div></div>' + TILT_JS
