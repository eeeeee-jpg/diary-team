"""MOIPJI 싸이월드 다이어리 테마: 화면을 감싸는 외곽 프레임과 팀 서비스 메뉴(GNB).

서비스 화면(weather.py)은 그대로 두고 바깥 레이어만 입힌다.
- 브라우저 배경: MOIPJI 대표색이 옅게 섞인 도트 무늬
- 바깥 프레임: 대표색 파스텔, 둥근 모서리, 얇은 테두리와 옅은 그림자 (Streamlit 본문 상자)
- 안쪽 페이지: 크림 테두리 한 겹 + 날씨 그라데이션 (MOIPJI 영역 .st-key-weather_root)
- GNB: 넓은 화면은 프레임 오른쪽 테두리 끝에 붙은 세로 탭(화면에 고정), 좁은 화면은 '=' 메뉴 버튼.
  팀 서비스(JOOYOU·guest·meal·reading·MOIPJI) 페이지로 이동하고, 지금 서비스(MOIPJI)는 대표색으로 강조한다.

지금은 MOIPJI만 쓴다. 팀원이 함께 쓰는 규칙은 팀 합의 전이라 파일 끝에 주석으로만 적어 두었다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape

import streamlit as st


@dataclass(frozen=True)
class Service:
    route: str  # 병합 앱 url_path = 서비스 폴더 이름 = __init__.py의 ROUTE
    name: str  # 서비스명
    color: str  # 대표색 "#RRGGBB"


# MOIPJI만 대표색을 정한다. 프레임·테두리·탭 색은 이 한 색에서 자동으로 만든다
SERVICE = Service("weather", "MOIPJI", "#7FA6D3")

# GNB 메뉴 (메뉴 이름, 병합 앱 url_path) — 링크만 둔다. 다른 서비스의 색은 팀 합의 전이라 정하지 않는다
GNB = (
    ("JOOYOU", "fuel"),
    ("guest", "guest"),
    ("meal", "meal"),
    ("reading", "reading"),
    (SERVICE.name, SERVICE.route),
)

FRAME_WIDTH = 860  # 프레임 최대 너비(px). 탭은 이 오른쪽 경계에 붙는다
HEADER_H = 60  # Streamlit 상단 바 높이. 투명하지만 클릭을 가로채므로 프레임과 탭을 그 아래에 둔다
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


# ---------------------------------------------------------------------------
# 대표색 한 개 → 테마 색 전체
# ---------------------------------------------------------------------------


def _rgb(color: str) -> tuple[int, int, int]:
    return tuple(int(color[i : i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]


def _hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{round(max(0, min(255, c))):02X}" for c in rgb)


def tint(color: str, amount: float) -> str:
    """흰색에 대표색을 amount만큼 섞는다 (0 = 흰색, 1 = 대표색)."""
    return _hex(tuple(255 - (255 - c) * amount for c in _rgb(color)))


def shade(color: str, factor: float) -> str:
    """대표색을 factor만큼 어둡게 (1 = 그대로, 0 = 검정)."""
    return _hex(tuple(c * factor for c in _rgb(color)))


def contrast(a: str, b: str) -> float:
    """WCAG 대비율."""
    def lum(color: str) -> float:
        def ch(c: int) -> float:
            v = c / 255
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        r, g, b_ = (ch(c) for c in _rgb(color))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b_
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def readable_on(color: str, background: str, start: float = 0.45, minimum: float = 4.5) -> str:
    """대표색을 어둡게 해서 background 위 글자 대비가 minimum 이상이 되는 색."""
    factor = start
    text = shade(color, factor)
    while contrast(text, background) < minimum and factor > 0.05:
        factor -= 0.05
        text = shade(color, factor)
    return text


def palette_for(color: str) -> dict[str, str]:
    """프레임·탭에 쓰는 색 묶음. 옅은 색은 흰색과 섞고, 글자는 대비를 보장해 어둡게 만든다."""
    tab = tint(color, 0.07)
    return {
        "bg": tint(color, 0.10),
        "dot": tint(color, 0.22),
        "frame": tint(color, 0.27),
        "frame_line": tint(color, 0.55),
        "paper": "#FFFDF6",
        "gray": "#E3E6EA",
        "page_a": tint(color, 0.04),
        "page_b": tint(color, 0.14),
        "tab": tab,
        "tab_text": readable_on(color, tab, start=0.45),
        "tab_on": "#FFFFFF",
        "tab_on_line": color,
        "tab_on_text": readable_on(color, "#FFFFFF", start=0.30, minimum=7.0),
    }


THEME_CSS = """
__APP__ {
  --dy-bg: __bg__;
  --dy-dot: __dot__;
  --dy-frame: __frame__;
  --dy-frame-line: __frame_line__;
  --dy-paper: __paper__;
  --dy-gray: __gray__;
  --dy-tab: __tab__;
  --dy-tab-text: __tab_text__;
  --dy-tab-on: __tab_on__;
  --dy-tab-on-line: __tab_on_line__;
  --dy-tab-on-text: __tab_on_text__;
  --dy-frame-pad: 14px;
  --dy-border: 6px;
  --dy-pad-top: 28px;
  --dy-pad-x: 24px;
}
/* 바깥은 다이어리 책상처럼 옅은 도트 무늬. weather.py의 page_css가 다시 들어와도 이기도록 body를 붙인다 */
body __APP__ {
  background: radial-gradient(var(--dy-dot) 1px, transparent 1px) 0 0 / 14px 14px, var(--dy-bg);
}

/* 바깥 프레임: 본문 상자 */
__APP__ [data-testid="stMainBlockContainer"] {
  max-width: __FRAME__px;
  margin: calc(__HEADER__px + 12px) auto 40px;
  padding: var(--dy-frame-pad);
  background: var(--dy-frame);
  border: 1px solid var(--dy-frame-line);
  border-radius: 28px;
  box-shadow: 0 1px 0 #FFFFFF inset, 0 8px 24px rgba(60, 90, 130, 0.12);
}

/* 안쪽 페이지: 크림 테두리 한 겹 + 날씨 그라데이션 (--mj-start·--mj-end, 없으면 대표색이 옅게 섞인 크림) */
__ROOT__ {
  background: linear-gradient(165deg, var(--mj-start, __page_a__) 0%, var(--mj-end, __page_b__) 100%);
  border: var(--dy-border) solid var(--dy-paper);
  outline: 1px solid var(--dy-gray);
  border-radius: 20px;
  padding: var(--dy-pad-top) var(--dy-pad-x) 32px;
}

/* 넓은 화면에서는 '=' 메뉴가 감춰져 탭을 감싼 칸이 비므로, 칸과 앞 간격(1rem)을 접어 톱니바퀴가 오른쪽 끝에 붙게 한다 */
[data-testid="stElementContainer"]:has(.dy-tabs) {
  width: 0;
  min-width: 0;
  margin-left: -1rem;
}
/* GNB: 넓은 화면 — 프레임 오른쪽 테두리 끝에 붙은 세로 탭 (화면 가운데 + 프레임 너비 절반) */
.dy-tabs {
  position: fixed;
  top: 120px;
  left: calc(50% + __HALF__px - 2px);
  display: flex;
  flex-direction: column;
  gap: 6px;
  z-index: 50;
}
.dy-tab {
  display: flex;
  align-items: center;
  min-width: 84px;
  min-height: 44px;
  padding: 0 14px 0 12px;
  font-family: 'Galmuri11', 'Pretendard Variable', sans-serif;
  font-size: 12px;
  color: var(--dy-tab-text);
  text-decoration: none;
  background: var(--dy-tab);
  border: 1px solid var(--dy-frame-line);
  border-left: none;
  border-radius: 0 12px 12px 0;
  box-shadow: 2px 2px 0 rgba(60, 90, 130, 0.08);
}
.dy-tab:hover {
  background: #FFFFFF;
  color: var(--dy-tab-on-text);
}
.dy-tab[aria-current="page"] {
  background: var(--dy-tab-on);
  color: var(--dy-tab-on-text);
  border-color: var(--dy-tab-on-line);
  box-shadow: inset 4px 0 0 var(--dy-tab-on-line), 2px 2px 0 rgba(60, 90, 130, 0.08);
  font-weight: 700;
  min-width: 92px;
}
.dy-tab:focus-visible,
.dy-menu summary:focus-visible {
  outline: 2px dashed var(--dy-tab-on-line);
  outline-offset: 2px;
}

/* 좁은 화면용 '=' 메뉴. 넓은 화면에서는 버튼만 감춘다 (같은 칸에 든 세로 탭은 그대로 보여야 한다) */
.dy-menu {
  display: none;
  position: relative;
}
.dy-menu summary {
  list-style: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border: 2px solid var(--mj-glass-border, var(--dy-frame-line));
  border-radius: 12px;
  background: var(--mj-glass, var(--dy-tab));
  cursor: pointer;
}
.dy-menu summary::-webkit-details-marker {
  display: none;
}
.dy-bars,
.dy-bars::before {
  display: block;
  width: 20px;
  height: 3px;
  border-radius: 2px;
  background: var(--mj-text, var(--dy-tab-text));
}
.dy-bars {
  position: relative;
  top: -3px;
}
.dy-bars::before {
  content: "";
  position: absolute;
  top: 7px;
}
.dy-menu nav {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;  /* 톱니바퀴 옆 오른쪽 끝 버튼이라 오른쪽에 맞춰 연다 */
  z-index: 60;
  display: flex;
  flex-direction: column;
  min-width: 168px;
  padding: 6px;
  background: #FFFFFF;
  border: 1px solid var(--dy-frame-line);
  border-radius: 14px;
  box-shadow: 0 8px 24px rgba(60, 90, 130, 0.18);
}
.dy-menu nav a {
  display: flex;
  align-items: center;
  min-height: 44px;
  padding: 0 12px;
  border-radius: 10px;
  font-family: 'Galmuri11', 'Pretendard Variable', sans-serif;
  font-size: 14px;
  color: var(--dy-tab-text);
  text-decoration: none;
  text-shadow: none;
}
.dy-menu nav a:hover,
.dy-menu nav a:focus-visible {
  background: var(--dy-tab);
  color: var(--dy-tab-on-text);
}
.dy-menu nav a[aria-current="page"] {
  background: var(--dy-frame);
  color: var(--dy-tab-on-text);
  font-weight: 700;
}

/* 프레임 옆에 탭을 둘 자리가 없으면: 여백·장식을 줄이고 세로 탭 대신 '=' 메뉴 */
@media (max-width: __NARROW__px) {
  __APP__ {
    --dy-frame-pad: 6px;
    --dy-border: 3px;
    --dy-pad-top: 16px;
    --dy-pad-x: 12px;
  }
  __APP__ [data-testid="stMainBlockContainer"] {
    margin: calc(__HEADER__px + 4px) auto 16px;
    border-radius: 18px;
    box-shadow: none;
  }
  __ROOT__ {
    border-radius: 14px;
    padding-bottom: 24px;
  }
  .dy-tabs {
    display: none;
  }
  .dy-menu {
    display: block;
  }
  [data-testid="stElementContainer"]:has(.dy-tabs) {
    width: auto;
    margin-left: 0;
  }
}
"""

# '=' 메뉴는 바깥을 누르거나 Esc를 누르면 닫는다
MENU_SCRIPT = """
<script>
(() => {
  if (window.__dyMenuBound) return;
  window.__dyMenuBound = true;
  const close = except => document.querySelectorAll('details.dy-menu[open]').forEach(d => { if (d !== except) d.open = false; });
  document.addEventListener('click', e => close(e.target.closest('details.dy-menu')));
  document.addEventListener('keydown', e => { if (e.key === 'Escape') close(null); });
})();
</script>"""


def theme_css() -> str:
    """MOIPJI 대표색으로 칠한 프레임·GNB CSS. `.st-key-weather_root` 영역이 있을 때만 적용된다."""
    if not HEX.match(SERVICE.color):
        raise ValueError(f"대표색은 '#RRGGBB' 형식이어야 해요: {SERVICE.color!r}")
    narrow = FRAME_WIDTH + 2 * 100  # 탭(약 90px)이 양쪽 여백에 들어갈 수 있는 최소 너비
    css = (
        THEME_CSS.replace("__APP__", f".stApp:has(.st-key-{SERVICE.route}_root)")
        .replace("__ROOT__", f".st-key-{SERVICE.route}_root")
        .replace("__FRAME__", str(FRAME_WIDTH))
        .replace("__HALF__", str(FRAME_WIDTH // 2))
        .replace("__NARROW__", str(narrow))
        .replace("__HEADER__", str(HEADER_H))
    )
    for name, value in palette_for(SERVICE.color).items():
        css = css.replace(f"__{name}__", value)
    return f"<style>{css}</style>"


def render_frame() -> None:
    """프레임 CSS를 넣는다. page()에서 MOIPJI 영역을 그리기 전에 한 번 부른다."""
    st.html(theme_css())


def _links(css_class: str = "") -> str:
    """팀 서비스 링크. 상대 경로라 병합 앱의 어느 페이지에서 눌러도 해당 서비스 페이지로 간다."""
    cls = f' class="{css_class}"' if css_class else ""
    return "".join(
        f'<a{cls} href="{route}" target="_self"'
        + (' aria-current="page"' if route == SERVICE.route else "")
        + f">{escape(label)}</a>"
        for label, route in GNB
    )


def gnb_html() -> str:
    """넓은 화면 세로 탭과 좁은 화면 '=' 메뉴. 머리글의 톱니바퀴 옆에 한 번 넣는다."""
    return (
        f'<nav class="dy-tabs" aria-label="다이어리 서비스">{_links("dy-tab")}</nav>'
        '<details class="dy-menu"><summary aria-label="서비스 메뉴 열기" title="서비스 메뉴">'
        '<span class="dy-bars" aria-hidden="true"></span></summary>'
        f'<nav aria-label="다이어리 서비스">{_links()}</nav></details>'
        f"{MENU_SCRIPT}"
    )


def render_gnb() -> None:
    st.html(gnb_html(), unsafe_allow_javascript=True)


# ===========================================================================
# 팀원 수정 규칙 (팀 합의 전 — 아직 코드로 쓰지 않는다)
# ===========================================================================
# 다른 서비스도 이 테마를 각자 다른 대표색으로 쓰게 하려는 안이다. 합의되면 아래 순서로 바꾼다.
# 지금 다른 서비스가 이 파일을 import하면 팀 규칙(다른 서비스 내부 모듈 import 금지)에 어긋나고,
# MOIPJI 전용 값(SERVICE, .st-key-weather_root)이라 다른 화면에서는 오류가 나거나 엉뚱하게 칠해질 수 있다.
#
# 1) 이 파일을 shared/theme.py로 옮긴다 (공통 영역이라 팀원 A와 합의 후)
# 2) SERVICE 한 줄을 SERVICES 목록으로 바꾸고, 서비스마다 자기 줄의 서비스명·대표색만 고친다.
#    route = 병합 앱 url_path = 서비스 폴더 이름 = __init__.py의 ROUTE. 줄 순서가 GNB 순서다
#
#    SERVICES = (
#        Service("fuel", "JOOYOU", "#F0A04B"),
#        Service("guest", "guest", "#9B7FD4"),
#        Service("meal", "meal", "#E8768A"),
#        Service("reading", "reading", "#58A889"),
#        Service("weather", "MOIPJI", "#7FA6D3"),
#    )
#
# 3) theme_css, render_frame, render_gnb가 route를 받게 하고, route로 SERVICES에서 대표색을 찾는다.
#    없는 route나 "#RRGGBB"가 아닌 색이면 바로 ValueError를 내서 실수를 알린다.
#    GNB 탭마다 그 서비스 대표색 점(이름과 함께)을 붙이고, 지금 서비스 탭을 대표색으로 강조한다.
# 4) 각 서비스 page()에서:
#
#    from shared.theme import render_frame, render_gnb
#
#    def page():
#        render_frame("meal")                      # 화면을 그리기 전에 한 번
#        with st.container(key="meal_root"):       # 화면 전체를 {route}_root로 감싼다
#            render_gnb("meal")                    # 머리글 오른쪽 끝에 한 번
#            ...
#
# 5) 프레임, 테두리, 탭 색은 palette_for(대표색)이 만든다. 탭 글자는 대비 4.5:1 이상이 되게 어둡게 한다.
#    안쪽 페이지 배경은 CSS 변수 --mj-start, --mj-end로 바꿀 수 있다 (없으면 대표색이 옅게 섞인 크림).
