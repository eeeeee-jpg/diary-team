"""임시 일러스트: 품종별 털 색과 귀 모양만 다른 간단한 얼굴 SVG와, 방문 연출용 정면 꼬마 캐릭터 SVG.

정식 일러스트(직접 제작 또는 라이선스 확인)가 나오면 guest_svg()만 교체한다.
"""

from __future__ import annotations

import re

from .models import Breed

_INK = "#2b2222"
_CHEEK = "#f4a7b9"
_SILHOUETTE = "#cdbfc6"


def _ears(breed: Breed, fill: str, inner: str) -> str:
    if breed.species == "cat":
        if breed.ear == "fold":
            return f'<path d="M22 34 Q26 20 40 26 Z" fill="{fill}"/><path d="M74 34 Q70 20 56 26 Z" fill="{fill}"/>'
        return f'<path d="M20 40 L26 10 L44 28 Z" fill="{fill}"/><path d="M76 40 L70 10 L52 28 Z" fill="{fill}"/>'
    if breed.ear == "up":
        return f'<path d="M18 44 Q14 10 42 28 Z" fill="{fill}"/><path d="M78 44 Q82 10 54 28 Z" fill="{fill}"/>'
    return f'<ellipse cx="18" cy="48" rx="10" ry="20" fill="{inner}"/><ellipse cx="78" cy="48" rx="10" ry="20" fill="{inner}"/>'


def guest_svg(breed: Breed, silhouette: bool = False) -> str:
    """st.image()에 바로 넣을 수 있는 SVG 문자열. 못 만난 품종은 실루엣으로."""
    fill = _SILHOUETTE if silhouette else breed.fur
    inner = _SILHOUETTE if silhouette else breed.accent
    face = ""
    if not silhouette:
        face = (
            f'<ellipse cx="48" cy="66" rx="14" ry="10" fill="{breed.accent}"/>'
            f'<circle cx="37" cy="50" r="3.6" fill="{_INK}"/><circle cx="59" cy="50" r="3.6" fill="{_INK}"/>'
            f'<path d="M44 61 Q48 65 52 61 Z" fill="{_INK}"/>'
            f'<path d="M48 64 Q44 70 40 67 M48 64 Q52 70 56 67" stroke="{_INK}" stroke-width="1.6" fill="none" stroke-linecap="round"/>'
            f'<circle cx="30" cy="60" r="4" fill="{_CHEEK}" opacity=".55"/><circle cx="66" cy="60" r="4" fill="{_CHEEK}" opacity=".55"/>'
        )
    outline = "" if silhouette else ' stroke="rgba(0,0,0,.12)" stroke-width="1.5"'
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96" width="96" height="96">'
        f'{_ears(breed, fill, inner)}<circle cx="48" cy="54" r="32" fill="{fill}"{outline}/>{face}</svg>'
    )


# ── 손님 방문 연출용 꼬마 캐릭터 ─────────────────────────────
# 정면을 보는 2등신 스티커 캐릭터. 검은 펜 선 대신 털색보다 조금 진한 선, 바깥은 흰 스티커 테두리.
# st.html은 <svg> 태그를 지우므로 <img>(data URI)로 넣고, 걸음·꼬리 움직임은 SVG 안의 <style>에 둔다.
# 화면 속 이동(오른쪽 위 → 가운데로 다가오기)은 diary.py CSS가 맡는다.

WALK_SECONDS = 1.6  # diary.py 의 guest-approach 시간과 같아야 한다

_EYE = "#2f2328"
_BLUSH = "#ff9fb8"
_PINK = "#f7b5c6"
_STEPS = round(WALK_SECONDS / 0.2)  # 0.2초마다 한 발

_WALK_CSS = (
    f".b{{animation:hop .2s ease-in-out {_STEPS} alternate}}"
    f".w{{transform-origin:60px 112px;animation:sway .4s ease-in-out {_STEPS // 2} alternate}}"
    f".f1{{animation:step .2s ease-in-out {_STEPS} alternate}}"
    f".f2{{animation:step .2s ease-in-out {_STEPS} alternate-reverse}}"
    f".t{{transform-origin:78px 98px;animation:wag .25s ease-in-out {WALK_SECONDS}s 6 alternate}}"
    "@keyframes hop{to{transform:translateY(-3px)}}"
    "@keyframes sway{from{transform:rotate(-3deg)}to{transform:rotate(3deg)}}"
    "@keyframes step{to{transform:translateY(-3.5px)}}"
    "@keyframes wag{from{transform:rotate(-10deg)}to{transform:rotate(12deg)}}"
    "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
)

# 흰 스티커 테두리 + 옅은 그림자
_STICKER = (
    '<filter id="s" x="-20%" y="-20%" width="140%" height="140%">'
    '<feMorphology in="SourceAlpha" operator="dilate" radius="2.6" result="d"/>'
    '<feFlood flood-color="#fff"/><feComposite in2="d" operator="in" result="w"/>'
    '<feGaussianBlur in="d" stdDeviation="1.4"/><feOffset dy="1.6" result="o"/>'
    '<feFlood flood-color="#4a3640" flood-opacity=".2"/><feComposite in2="o" operator="in" result="sh"/>'
    '<feMerge><feMergeNode in="sh"/><feMergeNode in="w"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
)


def _rgb(hex_color: str) -> tuple[int, int, int]:
    return int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)


def _mix(a: str, b: str, t: float) -> str:
    """a와 b를 t 비율로 섞은 색 (t=0이면 a)"""
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(_rgb(a), _rgb(b)))


def _lum(hex_color: str) -> float:
    r, g, b = _rgb(hex_color)
    return 0.299 * r + 0.587 * g + 0.114 * b


def _is_dark(hex_color: str) -> bool:
    return _lum(hex_color) < 90


def _mirror(d: str) -> str:
    """가로 120 기준 좌우 반전 (절대 좌표 path에서 x만 120-x)"""
    out, i = [], 0
    for tok in re.findall(r"[A-Za-z]|-?\d*\.?\d+", d):
        if tok.isalpha():
            out.append(tok)
            i = 0
            continue
        out.append(f"{120 - float(tok):g}" if i % 2 == 0 else tok)
        i += 1
    return " ".join(out)


def _pair(d: str, attrs: str) -> str:
    return f'<path d="{d}" {attrs}/><path d="{_mirror(d)}" {attrs}/>'


def guest_walker_svg(breed: Breed) -> str:
    """품종의 fur·accent·ear로 칠한 정면 꼬마 캐릭터 SVG."""
    fur = breed.fur
    line = _mix(fur, "#4a3640", 0.38)
    soft = _mix(fur, "#ffffff", 0.55)  # 주둥이
    belly = breed.accent if _lum(breed.accent) > _lum(fur) + 40 else soft  # 보더 콜리·시바처럼 가슴이 밝은 품종
    stroke = f'stroke="{line}" stroke-width="2" stroke-linejoin="round"'
    cat = breed.species == "cat"
    masked = _is_dark(breed.accent) and not _is_dark(fur)  # 샴·퍼그처럼 얼굴이 진한 품종
    muzzle = breed.accent if masked else soft

    # 꼬리 (몸 뒤). 고양이는 길게 말아 올리고, 강아지는 짧고 통통하게.
    if cat:
        tail = (
            f'<path d="M80 100 C100 98 106 78 98 64" fill="none" stroke="{line}" stroke-width="9" stroke-linecap="round"/>'
            f'<path d="M80 100 C100 98 106 78 98 64" fill="none" stroke="{fur}" stroke-width="5.4" stroke-linecap="round"/>'
        )
    else:
        tail = f'<ellipse cx="86" cy="88" rx="6.5" ry="10" transform="rotate(38 86 88)" fill="{fur}" {stroke}/>'
    tail = f'<g class="t">{tail}</g>'

    # 귀
    back_ears = front_ears = ""
    if cat and breed.ear == "fold":
        front_ears = _pair("M31 36 C33 25 44 22 51 27 C45 31 38 35 31 36 Z", f'fill="{fur}" {stroke}')
    elif cat:
        back_ears = _pair("M27 46 C25 28 29 15 34 12 C41 15 49 23 53 29 Z", f'fill="{fur}" {stroke}') + _pair(
            "M33 37 C32 27 34 20 37 19 C41 22 45 26 47 29 Z", f'fill="{_PINK}"'
        )
    elif breed.ear == "up":
        back_ears = _pair("M29 44 C23 24 29 9 38 10 C46 13 51 23 53 30 Z", f'fill="{fur}" {stroke}') + _pair(
            "M34 36 C31 24 34 16 38 17 C43 20 46 25 47 30 Z", f'fill="{_PINK}"'
        )
    else:
        front_ears = _pair(
            "M31 33 C18 33 13 52 17 65 C20 74 30 72 33 61 C35 51 37 40 31 33 Z", f'fill="{breed.accent}" {stroke}'
        )

    # 눈 (털이 진하면 금빛 눈)
    eyes = ""
    for cx in (45, 75):
        if _is_dark(fur):
            eyes += f'<ellipse cx="{cx}" cy="56" rx="7.4" ry="8.4" fill="#f4cf5d"/>'
        eyes += (
            f'<ellipse cx="{cx}" cy="56" rx="5.6" ry="6.6" fill="{_EYE}"/>'
            f'<circle cx="{cx + 1.9}" cy="53.4" r="2.3" fill="#fff"/><circle cx="{cx - 1.7}" cy="58.4" r="1" fill="#fff"/>'
        )

    if cat:
        nose = '<path d="M56.6 61.2 Q60 59.6 63.4 61.2 Q61.6 64.6 60 64.9 Q58.4 64.6 56.6 61.2 Z" fill="#ee8fa8"/>'
        whisker = f'stroke="{line}" stroke-width="1.3" stroke-linecap="round" opacity=".7"'
        extra = _pair("M27 61 L15 58.5", whisker) + _pair("M27 65.5 L15 66.5", whisker)
    else:
        nose = (
            f'<ellipse cx="60" cy="61.6" rx="4.8" ry="3.5" fill="{_EYE}"/>'
            '<ellipse cx="58.5" cy="60.5" rx="1.5" ry=".8" fill="#fff" opacity=".85"/>'
        )
        extra = '<path d="M57.8 68.6 Q60 74 62.2 68.6 Z" fill="#f28aa0"/>'  # 살짝 내민 혀
    mouth = (
        f'<path d="M53.6 66 Q57 70.4 60 66.6 Q63 70.4 66.4 66" fill="none" stroke="{_EYE}" '
        'stroke-width="1.6" stroke-linecap="round"/>'
    )

    head_rx, head_ry = (37, 30) if cat else (35, 31)
    feet = "".join(
        f'<g class="{cls}"><ellipse cx="{cx}" cy="110" rx="8.5" ry="5.6" fill="{fur}" {stroke}/>'
        f'<path d="M{cx - 2.5} 108.5 v3 M{cx + 2.5} 108.5 v3" stroke="{line}" stroke-width="1.2" stroke-linecap="round"/></g>'
        for cx, cls in ((49, "f1"), (71, "f2"))
    )
    blush = "".join(f'<ellipse cx="{cx}" cy="66" rx="6" ry="3.6" fill="{_BLUSH}" opacity=".55"/>' for cx in (35, 85))
    paws = "".join(f'<ellipse cx="{cx}" cy="92" rx="5.4" ry="4.6" fill="{fur}" {stroke}/>' for cx in (51.5, 68.5))
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 122" width="120" height="122">'
        f"<style>{_WALK_CSS}</style><defs>{_STICKER}</defs>"
        '<ellipse cx="60" cy="117" rx="30" ry="4" fill="rgba(74,54,64,.14)"/>'
        f'<g class="b"><g class="w" filter="url(#s)">{tail}{feet}'
        f'<path d="M60 70 C81 70 87 89 85 100 C84 108 75 111 60 111 C45 111 36 108 35 100 C33 89 39 70 60 70 Z" fill="{fur}" {stroke}/>'
        f'<ellipse cx="60" cy="97" rx="13" ry="10" fill="{belly}"/>{paws}'
        f'{back_ears}<ellipse cx="60" cy="52" rx="{head_rx}" ry="{head_ry}" fill="{fur}" {stroke}/>{front_ears}'
        f'<ellipse cx="60" cy="64.5" rx="12.5" ry="9" fill="{muzzle}"/>'
        f"{eyes}{blush}{extra}{mouth}{nose}"
        "</g></g></svg>"
    )


# 걸어온 자리에 남는 작은 발자국 (발가락이 위를 향함. 화면에서 걸어온 방향으로 돌린다)
PAW_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" width="14" height="14">'
    '<g fill="#e7aac2"><ellipse cx="10" cy="13" rx="4.6" ry="3.8"/>'
    '<circle cx="4.6" cy="7.6" r="2"/><circle cx="8.2" cy="4.6" r="2"/><circle cx="11.8" cy="4.6" r="2"/>'
    '<circle cx="15.4" cy="7.6" r="2"/></g></svg>'
)
