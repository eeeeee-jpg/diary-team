"""임시 일러스트: 품종별 털 색과 귀 모양만 다른 간단한 얼굴 SVG.

정식 일러스트(직접 제작 또는 라이선스 확인)가 나오면 guest_svg()만 교체한다.
"""

from __future__ import annotations

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
