"""MOIPJI 미니미: 추천 코디를 입은 도트 캐릭터(약 6.5등신)와 날씨가 보이는 바깥 풍경을 SVG로 그린다.

픽셀 격자에 색을 칠한 뒤 가로로 이어진 같은 색을 하나의 <rect>로 묶어 내보낸다.
shape-rendering="crispEdges"라서 어떤 크기로 늘려도 도트가 흐려지지 않는다.
옷 모양과 색은 data/outfits.json 아이템의 "pixel" 값에서 온다.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import random
from html import escape

OUTLINE = "#2B2430"
SKIN = "#FFE0C8"
HAIR = "#4A3426"
CHEEK = "#FFADB5"
EYE = "#2B2430"
MOUTH = "#D0636B"
SHOE = "#4A3F44"
WHITE = "#FFFFFF"
ACCENT = "#E8616D"  # 그래픽 티 로고, 리본, 목도리

CHAR_W, CHAR_H = 66, 117  # 캐릭터 판 (위 18px은 큰 우산·모자 자리, 양옆은 펼친 우산 자리, 아래는 큰 키 다리 자리)
SCENE_W, SCENE_H = 96, 152  # 위쪽 하늘을 넉넉히 둬서 말풍선이 캐릭터를 가리지 않게 한다


@dataclass(frozen=True)
class Garment:
    shape: str
    color: str
    detail: str | None = None


PROPS = ("umbrella", "parasol", "sunglasses", "glasses", "mask", "water", "hotpack")


@dataclass(frozen=True)
class Body:
    """체형과 얼굴: 성별(어깨·허리선), 키(다리 길이), 체격(몸통·허벅지 폭), 눈·피부색·헤어.
    눈·헤어를 비워 두면 성별 기본값 (여성: 동그란 눈·단발, 남성: 차분한 눈·짧은 커트)."""

    gender: str = "female"  # female | male
    height: str = "normal"  # short | normal | tall
    build: str = "normal"  # slim | normal | sturdy
    eyes: str | None = None  # EYE_STYLES
    skin: str = "light"  # SKIN_TONES
    hair: str | None = None  # HAIR_STYLES


# 설정 화면에 보여 줄 이름. 순서 = 선택지 순서
EYE_STYLES = {"round": "동그란 눈", "calm": "차분한 눈", "smile": "웃는 눈"}
SKIN_TONES = {
    "porcelain": ("아주 밝은", "#FFEDE2"),
    "light": ("밝은", "#FFE0C8"),
    "medium": ("중간", "#EDC29E"),
    "tan": ("구릿빛", "#C98F64"),
    "deep": ("짙은", "#8A5A3C"),
}
HAIR_STYLES = {"bob": "단발", "long": "긴 머리", "ponytail": "묶은 머리", "short": "짧은 커트", "curly": "곱슬 펌"}


def eyes_of(body: Body) -> str:
    return body.eyes if body.eyes in EYE_STYLES else ("calm" if body.gender == "male" else "round")


def hair_of(body: Body) -> str:
    return body.hair if body.hair in HAIR_STYLES else ("short" if body.gender == "male" else "bob")


@dataclass(frozen=True)
class Look:
    """미니미가 입을 것. 아이템 pixel 값 + 준비물에서 만든다."""

    top: Garment
    bottom: Garment
    outer: Garment | None = None
    hat: str | None = None  # beanie | cap | bucket
    earmuffs: bool = False  # 모자 위에도 쓸 수 있어 따로 둔다
    scarf: bool = False
    mittens: bool = False
    tights: bool = False
    props: tuple[str, ...] = ()  # PROPS 중 들고 있거나 쓴 것
    prop_colors: tuple[tuple[str, str], ...] = ()  # (준비물 종류, 고른 색) — 없으면 PROP_COLORS 기본색
    body: Body = Body()
    onepiece: bool = False  # 원피스: 상의와 하의 사이에 허리선·밑단을 그리지 않는다


# 준비물 기본색. 사용자가 팔레트에서 고르면 Look.prop_colors가 우선한다
PROP_COLORS = {
    "umbrella": "#5AA9E6", "parasol": "#FFD3DE", "sunglasses": "#1E1E24", "water": "#3FA2E0",
    "hotpack": "#FF8A3D", "windbreaker": "#3FA7A0", "extra_layer": "#C9B6E4", "scarf": ACCENT,
    "gloves": ACCENT, "beanie": "#E86A5C", "cap": "#3C5A9A", "bucket": "#E9E1CF",
    "earmuffs": "#F49AB0", "tights": "#4A4048", "mask": "#F2F4F7", "glasses": "#3A2E2A",
}


def prop_color(look: Look, kind: str) -> str:
    return dict(look.prop_colors).get(kind) or PROP_COLORS[kind]


def _shade(color: str, factor: float) -> str:
    """factor < 1이면 어둡게, > 1이면 밝게."""
    r, g, b = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    if factor < 1:
        r, g, b = (int(c * factor) for c in (r, g, b))
    else:
        r, g, b = (int(c + (255 - c) * (factor - 1)) for c in (r, g, b))
    return f"#{r:02X}{g:02X}{b:02X}"


class Grid:
    def __init__(self, width: int, height: int) -> None:
        self.width, self.height = width, height
        self.px: dict[tuple[int, int], str] = {}

    def fill(self, x: int, y: int, w: int, h: int, color: str) -> None:
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                if 0 <= xx < self.width and 0 <= yy < self.height:
                    self.px[(xx, yy)] = color

    def dot(self, x: int, y: int, color: str) -> None:
        self.fill(x, y, 1, 1, color)

    def paste(self, other: Grid, ox: int, oy: int) -> None:
        for (x, y), color in other.px.items():
            self.dot(x + ox, y + oy, color)

    def scaled(self, k: int) -> Grid:
        """도트 하나를 k×k로 키운 새 격자."""
        out = Grid(self.width * k, self.height * k)
        for (x, y), color in self.px.items():
            out.fill(x * k, y * k, k, k, color)
        return out

    def outlined(self, color: str = OUTLINE) -> Grid:
        """칠해진 영역 바깥 테두리에 1px 윤곽선을 두른 새 격자."""
        out = Grid(self.width, self.height)
        for (x, y) in self.px:
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) not in self.px:
                    out.dot(nx, ny, color)
        out.px.update(self.px)
        return out

    def cropped(self) -> Grid:
        """칠해진 영역만 남긴 새 격자 (빈 여백을 잘라 썸네일이 작아지지 않게)."""
        if not self.px:
            return self
        xs, ys = [x for x, _ in self.px], [y for _, y in self.px]
        out = Grid(max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)
        for (x, y), color in self.px.items():
            out.px[(x - min(xs), y - min(ys))] = color
        return out

    def rects(self) -> str:
        parts = []
        for y in range(self.height):
            x = 0
            while x < self.width:
                color = self.px.get((x, y))
                if color is None:
                    x += 1
                    continue
                start = x
                while x < self.width and self.px.get((x, y)) == color:
                    x += 1
                parts.append(f'<rect x="{start}" y="{y}" width="{x - start}" height="1" fill="{color}"/>')
        return "".join(parts)


def _svg(grid: Grid, title: str) -> str:
    t = escape(title)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {grid.width} {grid.height}" '
        f'shape-rendering="crispEdges" role="img" aria-label="{t}" '
        f'style="width:100%;height:auto;display:block;image-rendering:pixelated">'
        f"<title>{t}</title>{grid.rects()}</svg>"
    )

# ---------------------------------------------------------------------------
# 캐릭터: 약 6.5등신 패션 일러스트 비율 (머리 14px, 다리를 늘인 몸 전체 약 90px)
# ---------------------------------------------------------------------------
# 몸 기준 좌표는 폭 36(x 0~35)이며 판에는 (DX, DY)만큼 옮겨 칠한다. 위쪽 DY는 우산·모자 자리.
# 빛은 왼쪽 위에서 온다고 보고, 오른쪽 가장자리를 어둡게(_shade 0.82) 칠한다.

DY = 18  # 몸 기준 y를 판에서 아래로 옮기는 값 (머리 위 큰 우산 자리)
DX = 15  # 몸 기준 x를 판에서 오른쪽으로 옮기는 값 (오른손에 든 우산이 판 안에 들어오고, 풍경 가운데에 서게)
SKIN_SHADE = "#F2C3A3"
HAIR_LIGHT = "#6E4C36"
HAIR_DARK = "#33231A"
SHOE_LIGHT = "#6A5D63"

# 몸통 줄별 가로 범위 (y: (x0, x1)) — 어깨·가슴·허리·골반. 여성은 허리가 들어가고, 남성은 어깨가 넓고 허리선이 곧다
TORSO = {
    **{y: (10, 25) for y in range(15, 19)},
    **{y: (11, 24) for y in range(19, 27)},
    **{y: (12, 23) for y in range(27, 34)},
    **{y: (11, 24) for y in range(34, 43)},
}
TORSO_MALE = {
    **{y: (9, 26) for y in range(15, 19)},
    **{y: (10, 25) for y in range(19, 27)},
    **{y: (11, 24) for y in range(27, 43)},
}
# 다리 (왼쪽 기준): (y0, y1, x0, x1)
LEG = ((43, 52, 11, 16), (53, 60, 12, 16), (61, 72, 13, 16), (73, 75, 14, 16))
# 키별로 다리에 더하는 줄 수 (남성은 같은 '보통'이어도 조금 더 크다). 머리 크기는 같아서 키가 크면 등신이 늘어난다
LEG_EXTRA_BY = {
    ("female", "short"): 6, ("female", "normal"): 11, ("female", "tall"): 15,
    ("male", "short"): 11, ("male", "normal"): 14, ("male", "tall"): 18,
}


def torso_of(body: Body) -> dict[int, tuple[int, int]]:
    """체형에 맞는 몸통. 마른 체격은 가슴 아래를 1px 좁히고, 탄탄한 체격은 전체를 1px 넓힌다."""
    base = TORSO_MALE if body.gender == "male" else TORSO
    if body.build == "slim":
        return {y: (x0 + 1, x1 - 1) if y >= 19 else (x0, x1) for y, (x0, x1) in base.items()}
    if body.build == "sturdy":
        return {y: (x0 - 1, x1 + 1) for y, (x0, x1) in base.items()}
    return dict(base)


def legs_of(body: Body) -> tuple[tuple[int, int, int, int], ...]:
    """탄탄한 체격은 허벅지·종아리를 바깥쪽으로 1px 넓힌다."""
    if body.build == "sturdy":
        return tuple((y0, y1, x0 - 1, x1) for y0, y1, x0, x1 in LEG)
    return LEG


def _mirror(x0: int, x1: int) -> tuple[int, int]:
    return 35 - x1, 35 - x0


class _Body:
    """몸 기준 좌표로 칠하는 붓 (DY만큼 아래로 옮겨 칠한다). 체형별 몸통·다리·팔 위치를 함께 갖는다."""

    def __init__(self, g: Grid, body: Body = Body()) -> None:
        self.g = g
        self.body = body
        self.torso = torso_of(body)
        self.legs = legs_of(body)
        self.arm_dx = TORSO[15][0] - self.torso[15][0]  # 어깨가 넓은 만큼 팔을 바깥으로
        self.hip = self.torso[42][0] - TORSO[42][0]  # 골반이 넓으면 음수 (치마·밑단 위치 보정)
        self.skin = SKIN_TONES.get(body.skin, SKIN_TONES["light"])[1]
        self.skin_shade = _shade(self.skin, 0.9)

    def row(self, y: int, x0: int, x1: int, color: str) -> None:
        self.g.fill(x0 + DX, y + DY, x1 - x0 + 1, 1, color)

    def rect(self, x0: int, y0: int, x1: int, y1: int, color: str) -> None:
        self.g.fill(x0 + DX, y0 + DY, x1 - x0 + 1, y1 - y0 + 1, color)

    def dot(self, x: int, y: int, color: str) -> None:
        self.g.dot(x + DX, y + DY, color)

    def both(self, x0: int, y0: int, x1: int, y1: int, color: str) -> None:
        """왼쪽과 거울 대칭 오른쪽에 함께 칠한다."""
        self.rect(x0, y0, x1, y1, color)
        m0, m1 = _mirror(x0, x1)
        self.rect(m0, y0, m1, y1, color)

    def shaded_rows(self, rows: dict[int, tuple[int, int]], color: str, y0: int, y1: int) -> None:
        """몸통 모양대로 칠하고 왼쪽 가장자리는 밝게, 오른쪽 두 줄은 어둡게."""
        light, shade = _shade(color, 1.12), _shade(color, 0.82)
        for y in range(y0, y1 + 1):
            if y not in rows:
                continue
            x0, x1 = rows[y]
            self.row(y, x0, x1, color)
            self.dot(x0, y, light)
            self.row(y, x1 - 1, x1, shade)


def _draw_skin(b: _Body, look: Look) -> None:
    """몸통·다리 피부. 팔은 포즈에 따라 _draw_arm에서 따로 그린다."""
    for y, (x0, x1) in b.torso.items():
        b.row(y, x0, x1, b.skin)
    leg = prop_color(look, "tights") if look.tights else b.skin
    for y0, y1, x0, x1 in b.legs:
        b.both(x0, y0, x1, y1, leg)
        b.rect(x1, y0, x1, y1, _shade(leg, 0.9))  # 다리 안쪽 그늘


def _draw_head(b: _Body, look: Look, eyes: str | None = None, mouth: str | None = None) -> None:
    skin, skin_shade = b.skin, b.skin_shade
    male = look.body.gender == "male"
    # 목
    b.rect(16, 13, 19, 14, skin)
    b.row(13, 16, 19, skin_shade)
    # 얼굴 (계란형)
    for y, (x0, x1) in {2: (14, 21), **{y: (13, 22) for y in range(3, 10)}, 10: (14, 21), 11: (15, 20), 12: (16, 19)}.items():
        b.row(y, x0, x1, skin)
    b.rect(12, 6, 12, 8, skin)  # 귀
    b.rect(23, 6, 23, 8, skin)
    b.row(11, 19, 20, skin_shade)  # 턱선 그늘
    b.row(12, 18, 19, skin_shade)
    # 눈썹: 남성은 조금 길고 진하게
    if male:
        b.row(6, 13, 15, HAIR_DARK)
        b.row(6, 20, 22, HAIR_DARK)
    else:
        b.row(6, 14, 15, HAIR_DARK)
        b.row(6, 19, 20, HAIR_DARK)
    _draw_eyes(b, eyes or eyes_of(look.body))
    b.rect(17, 9, 17, 10, skin_shade)
    if mouth == "open":  # 말하는 입
        b.rect(17, 11, 18, 12, "#8A3A40")
        b.row(12, 17, 18, MOUTH)
    elif mouth == "smile":  # 활짝 웃는 입
        b.row(11, 16, 19, MOUTH)
        b.row(12, 17, 18, "#8A3A40")
    else:
        b.row(11, 17, 18, MOUTH)
    if male:  # 볼터치는 작게
        b.dot(13, 10, CHEEK)
        b.dot(22, 10, CHEEK)
    else:
        b.row(10, 13, 14, CHEEK)
        b.row(10, 21, 22, CHEEK)
    HAIR_DRAWERS[hair_of(look.body)](b)


def _draw_eyes(b: _Body, style: str) -> None:
    for x in (14, 19):  # 왼눈·오른눈 왼쪽 끝
        if style == "calm":  # 가로로 긴 눈, 바깥쪽 눈꼬리만 살짝 (하이라이트 없음)
            b.row(8, x, x + 1, EYE)
            b.dot(x if x == 14 else x + 1, 7, EYE)
        elif style == "closed":  # 질끈 감은 눈 (기침·마실 때)
            b.row(8, x, x + 1, EYE)
            b.dot(x if x == 14 else x + 1, 9, EYE)
        elif style == "smile":  # 웃어서 휘어진 눈 (∩)
            b.dot(x, 8, EYE)
            b.dot(x + 1, 7, EYE)
            b.dot(x + 2, 8, EYE)
        else:  # 동그란 눈 + 하이라이트
            b.rect(x, 7, x + 1, 8, EYE)
            b.dot(x + 1, 7, WHITE)


def _hair_bob(b: _Body) -> None:
    """단발, 옆가르마."""
    b.row(-1, 14, 21, HAIR)
    b.rect(12, 0, 23, 4, HAIR)
    b.row(0, 13, 22, HAIR)
    b.rect(11, 3, 12, 13, HAIR)
    b.rect(23, 3, 24, 13, HAIR)
    b.row(5, 13, 16, HAIR)  # 앞머리
    b.row(5, 20, 22, HAIR)
    b.dot(13, 6, HAIR)
    b.row(13, 11, 13, HAIR_DARK)  # 머리끝
    b.row(13, 22, 24, HAIR_DARK)
    b.rect(24, 4, 24, 12, HAIR_DARK)
    b.row(0, 15, 18, HAIR_LIGHT)  # 윤기
    b.row(1, 14, 15, HAIR_LIGHT)
    b.rect(11, 5, 11, 9, HAIR_LIGHT)


def _hair_long(b: _Body) -> None:
    """어깨 아래까지 내려오는 긴 생머리."""
    _hair_bob(b)
    b.rect(10, 6, 12, 22, HAIR)  # 어깨 위로 흘러내린 옆머리
    b.rect(23, 6, 25, 22, HAIR)
    b.rect(25, 6, 25, 22, HAIR_DARK)
    b.rect(10, 8, 10, 18, HAIR_LIGHT)
    b.row(23, 10, 12, HAIR_DARK)
    b.row(23, 23, 25, HAIR_DARK)


def _hair_ponytail(b: _Body) -> None:
    """뒤로 묶은 머리. 이마가 보이고 오른쪽 뒤로 꼬리가 내려온다."""
    b.row(-1, 14, 21, HAIR)
    b.rect(12, 0, 23, 3, HAIR)
    b.row(4, 13, 15, HAIR)
    b.row(4, 20, 22, HAIR)
    b.rect(12, 3, 12, 6, HAIR)
    b.rect(23, 3, 23, 6, HAIR_DARK)
    b.rect(24, 1, 25, 2, ACCENT)  # 머리끈
    b.rect(25, 3, 27, 9, HAIR)  # 꼬리
    b.rect(26, 10, 27, 15, HAIR)
    b.rect(27, 3, 27, 15, HAIR_DARK)
    b.row(0, 15, 18, HAIR_LIGHT)
    b.rect(25, 4, 25, 8, HAIR_LIGHT)


def _hair_short(b: _Body) -> None:
    """짧은 커트, 귀가 보이고 앞머리를 옆으로 넘겼다."""
    b.row(-1, 14, 21, HAIR)
    b.rect(12, 0, 23, 3, HAIR)
    b.row(4, 13, 17, HAIR)  # 앞머리
    b.dot(13, 5, HAIR)
    b.rect(12, 3, 12, 5, HAIR)  # 구레나룻
    b.rect(23, 3, 23, 5, HAIR_DARK)
    b.row(4, 21, 22, HAIR)
    b.row(0, 15, 18, HAIR_LIGHT)  # 윤기
    b.row(1, 14, 15, HAIR_LIGHT)


def _hair_curly(b: _Body) -> None:
    """볼륨 있는 곱슬 펌. 가장자리를 2px 둥근 컬로 울퉁불퉁하게, 안쪽에 컬 무늬."""
    b.rect(11, -1, 24, 4, HAIR)
    for x in (12, 15, 18, 21):  # 정수리 컬
        b.rect(x, -2, x + 1, -2, HAIR)
    b.rect(10, 1, 11, 9, HAIR)  # 옆머리 (귀 위로 부풀었다)
    b.rect(24, 1, 25, 9, HAIR)
    for y in (2, 6):
        b.rect(9, y, 9, y + 1, HAIR)
        b.rect(26, y, 26, y + 1, HAIR_DARK)
    b.rect(25, 1, 25, 9, HAIR_DARK)
    b.row(5, 13, 15, HAIR)  # 앞머리 컬
    b.row(5, 20, 22, HAIR)
    for x, y in ((13, 0), (16, 1), (19, 0), (22, 1), (14, 3), (18, 3), (21, 3), (11, 3), (11, 7)):
        b.dot(x, y, HAIR_LIGHT)  # 컬 무늬


HAIR_DRAWERS = {"bob": _hair_bob, "long": _hair_long, "ponytail": _hair_ponytail, "short": _hair_short, "curly": _hair_curly}


def _top_hem(b: _Body, onepiece: bool) -> int:
    """상의 밑단 줄. 남성 상의는 바지 위로 조금 길게 내려 입는다. 원피스는 허리까지만 (아래는 치마가 잇는다)."""
    return 40 if b.body.gender == "male" and not onepiece else 38


def _draw_top(b: _Body, top: Garment, onepiece: bool = False) -> None:
    """상의 몸판 (소매는 _draw_arm). 여성은 넓은 라운드 넥·허리선, 남성은 좁은 크루넥·긴 밑단."""
    c, shade = top.color, _shade(top.color, 0.82)
    male = b.body.gender == "male"
    hem = _top_hem(b, onepiece)
    if top.shape == "hood":  # 목 뒤로 넘긴 후드
        b.rect(12, 12, 23, 15, shade)
    rows = dict(b.torso)
    if male:
        rows |= {y: b.torso[42] for y in range(39, 41)}
    b.shaded_rows(rows, c, 15, hem)
    if not onepiece:
        b.row(hem, *rows[hem], shade)  # 밑단
    if top.shape == "sleeveless":  # 민소매: 어깨선이 안쪽으로 들어온다
        for y in range(15, 19):
            x0, x1 = b.torso[y]
            b.row(y, x0, x0 + 2, b.skin)
            b.row(y, x1 - 2, x1, b.skin)
    d = top.detail
    if d == "turtleneck":
        b.rect(15, 12, 20, 15, c)
        b.row(13, 15, 20, shade)
    elif d in ("collar", "suit"):
        collar = WHITE if c != "#FFFFFF" else "#D8D8D8"
        b.row(15, 14, 16, collar)
        b.row(16, 15, 16, collar)
        b.row(15, 19, 21, collar)
        b.row(16, 19, 20, collar)
        placket_end = hem - 1 if male else 24
        b.rect(17, 16, 18, placket_end, shade)  # 단추 여밈 (남성 셔츠는 밑단까지)
        for y in range(18, placket_end + 1, 3):
            b.dot(17, y, collar)
        if d == "suit":  # 수트 라펠
            for i, y in enumerate(range(16, 24)):
                b.row(y, 14 - min(i, 2), 15, shade)
                b.row(y, 20, 21 + min(i, 2), shade)
    elif d == "zip":  # 트레이닝 집업: 스탠드 칼라 + 가운데 지퍼
        b.rect(14, 13, 21, 15, c)
        b.row(14, 14, 21, shade)
        b.rect(17, 15, 18, hem, _shade(c, 1.5))
    elif top.shape not in ("hood",):
        if male:  # 크루넥: 좁고 둥근 목선 + 시보리
            b.row(15, 15, 20, b.skin)
            b.row(16, 16, 19, shade)
        else:  # 라운드 넥: 넓게 파인 목선
            b.row(15, 14, 21, b.skin)
            b.row(16, 15, 20, b.skin)
            b.row(17, 16, 19, b.skin)
            b.row(18, 17, 18, shade)
    if top.shape == "hood":
        b.row(15, 15, 20, b.skin)
        b.rect(16, 16, 16, 21, WHITE)  # 끈
        b.rect(19, 16, 19, 21, WHITE)
        b.rect(14, 29, 21, 33, shade)  # 캥거루 주머니
    if d == "stripe":
        for y in range(18, hem - 1, 3):
            x0, x1 = rows[y]
            b.row(y, x0, x1, "#5B7DB1")
    elif d == "knit":
        for x in range(13, 23, 2):
            b.rect(x, 19, x, hem - 3, shade)  # 골지
        if not onepiece:
            b.row(hem - 2, *rows[hem - 2], shade)
            b.row(hem - 1, *rows[hem - 1], shade)
    elif d == "graphic":
        b.rect(15, 21, 20, 26, ACCENT)
        b.rect(16, 22, 19, 23, WHITE)
    elif d == "ribbon":
        b.row(16, 15, 20, ACCENT)
        b.rect(17, 17, 18, 19, ACCENT)
    elif d == "tweed":  # 트위드: 알록달록한 짜임 + 흰 테두리
        _tweed(b, rows, c, 17, hem)
        b.row(15, 14, 21, WHITE)
        for y in range(16, hem + 1):
            b.dot(16, y, WHITE)
            b.dot(19, y, WHITE)
    elif d == "floral":  # 하와이안 셔츠 꽃무늬
        _floral(b, rows, c, 18, hem)
    if male:  # 남성 상의: 어깨선 봉제
        b.dot(rows[15][0] + 2, 16, shade)
        b.dot(rows[15][1] - 2, 16, shade)
    else:  # 여성 상의: 허리 주름 (허리선)
        b.dot(14, 31, shade)
        b.dot(15, 32, shade)
        b.dot(21, 30, shade)


def _tweed(b: _Body, rows: dict[int, tuple[int, int]], c: str, y0: int, y1: int) -> None:
    for y in range(y0, y1):
        if y not in rows:
            continue
        x0, x1 = rows[y]
        for x in range(x0 + 1 + (y % 3), x1, 3):
            b.dot(x, y, _shade(c, 0.7) if (x + y) % 2 else WHITE)


def _floral(b: _Body, rows: dict[int, tuple[int, int]], c: str, y0: int, y1: int) -> None:
    petal = ACCENT if c.upper() == WHITE else WHITE
    for y in range(y0, y1 - 1, 5):
        x0, x1 = rows.get(y, rows[max(rows)])
        for x in range(x0 + 2 + (y % 2) * 2, x1 - 1, 5):
            b.dot(x, y, petal)
            b.dot(x - 1, y + 1, petal)
            b.dot(x + 1, y + 1, petal)
            b.dot(x, y + 1, "#F2C14E")
            b.dot(x, y + 2, petal)


def _draw_bottom(b: _Body, look: Look) -> None:
    bottom = look.bottom
    c, shade = bottom.color, _shade(bottom.color, 0.82)
    s = bottom.shape
    b.shaded_rows(b.torso, c, 38, 42)
    if s.startswith("skirt_fit"):  # H라인: 골반 폭 그대로 곧게 내려오고 뒤트임이 있다
        end = 63 if s == "skirt_fit_midi" else 74
        x0, x1 = b.torso[42]
        for y in range(43, end + 1):
            b.row(y, x0, x1, c)
            b.dot(x0, y, _shade(c, 1.12))
            b.row(y, x1 - 1, x1, shade)
        b.rect(17, end - 7, 17, end, shade)  # 뒤트임
        b.row(end, x0, x1, shade)
        if not look.onepiece:
            b.row(38, *b.torso[38], shade)  # 허리 밴드
        _bottom_detail(b, bottom, x0, x1, 43, end)
        return
    if s.startswith("skirt"):
        end = {"skirt_mini": 52, "skirt_midi": 63}.get(s, 74)
        for i, y in enumerate(range(38, end + 1)):
            spread = min(i // 4, 3)
            b.row(y, 11 + b.hip - spread, 24 - b.hip + spread, c)
            b.row(y, 23 - b.hip + spread, 24 - b.hip + spread, shade)
        for x in range(13, 24, 3):  # 주름
            b.rect(x, 44, x, end - 1, shade)
        b.row(end, 8 + b.hip, 27 - b.hip, shade)
        _bottom_detail(b, bottom, 9 + b.hip, 26 - b.hip, 44, end)
        return
    b.row(38, *b.torso[38], shade)  # 허리 밴드
    b.dot(17, 39, shade)  # 지퍼
    b.dot(17, 40, shade)
    if s == "shorts":
        b.both(b.legs[0][2], 43, 16, 50, c)
        b.both(b.legs[0][2], 50, 16, 50, shade)
        return
    wide = s == "wide"
    male = b.body.gender == "male"
    for y0, y1, x0, x1 in b.legs:
        if wide:
            x0 = min(x0, b.legs[0][2]) - (1 if y0 >= 53 else 0)
            x1 = 16
        elif male:  # 남성 바지: 허벅지 폭 그대로 곧게 (일자핏)
            x0 = b.legs[0][2]
        b.both(x0, y0, x1, y1, c)
    end = 76 if wide else 75
    if wide:
        b.both(9, 73, 16, end, c)
    b.rect(14, 45, 14, end - 1, shade)  # 다림질 주름
    b.rect(21, 45, 21, end - 1, shade)
    b.rect(16, 43, 16, end, shade)  # 안쪽 솔기 그늘
    b.rect(24 if not wide else 25, 43, 24 if not wide else 25, end, shade)
    if s == "joggers":
        b.both(14, 71, 16, 75, shade)  # 밴딩 밑단
    if bottom.detail == "stripe_side":  # 트레이닝 바지 옆선
        b.both(b.legs[0][2], 43, b.legs[0][2], end, WHITE)


def _bottom_detail(b: _Body, bottom: Garment, x0: int, x1: int, y0: int, y1: int) -> None:
    """치마 무늬: 트위드 짜임, 니트 골지."""
    c = bottom.color
    if bottom.detail == "tweed":
        _tweed(b, {y: (x0, x1) for y in range(y0, y1)}, c, y0, y1)
        b.row(y1, x0, x1, WHITE)
    elif bottom.detail == "knit":
        for x in range(x0 + 2, x1 - 1, 2):
            b.rect(x, y0, x, y1 - 1, _shade(c, 0.86))


def _draw_outer(b: _Body, outer: Garment) -> None:
    """아우터 앞판 (소매는 _draw_arm)."""
    c, shade, light = outer.color, _shade(outer.color, 0.82), _shade(outer.color, 1.12)
    s = outer.shape
    male = b.body.gender == "male"
    short = 46 if male else 42  # 짧은 아우터 길이: 남성은 엉덩이를 덮고, 여성은 허리 아래에서 끊는다
    end = {"coat": 64, "trench": 64, "padding_long": 70}.get(s, short)
    padding = s.startswith("padding")
    puff = 1 if padding else 0
    # 앞판: 가운데(16~19)는 열려 상의가 보인다. 여성 코트는 아래로 갈수록 살짝 퍼지고, 남성은 곧게 떨어진다
    for y in range(15, end + 1):
        flare = 0 if y < 40 or male else (y - 40) // 8
        x0 = b.torso.get(y, b.torso[42])[0] - puff - flare
        b.row(y, x0, 15, c)
        b.row(y, 20, 35 - x0, c)
        b.dot(x0, y, light)
        b.row(y, 34 - x0, 35 - x0, shade)
    hem_flare = (end - 40) // 8 if end >= 40 and not male else 0  # 남성 코트는 밑단도 곧게
    b.row(end, b.torso[42][0] - puff - hem_flare, 15, shade)
    b.row(end, 20, b.torso[42][1] + puff + hem_flare, shade)
    if s in ("jacket", "coat", "trench"):  # 라펠
        for i, y in enumerate(range(15, 22)):
            b.row(y, 14 - min(i, 2), 15, shade)
            b.row(y, 20, 21 + min(i, 2), shade)
    if padding:
        b.rect(13, 12, 22, 14, c)  # 스탠드 칼라
        b.row(14, 13, 22, shade)
        for y in range(19, end, 4):  # 퀼팅
            x0 = b.torso.get(y, b.torso[42])[0] - puff - (0 if y < 40 or male else (y - 40) // 8)  # 몸판과 같은 퍼짐
            b.row(y, x0, 15, shade)
            b.row(y, 20, 35 - x0, shade)
    if s == "trench":
        b.row(31, 10, 25, shade)  # 벨트
        b.rect(17, 30, 18, 32, "#8A6A45")
        b.both(10, 15, 12, 15, shade)  # 견장
    if outer.detail in ("buttons", "toggle"):
        mark = WHITE if c not in ("#FFFFFF", "#F5F1E6", "#E9DCCB") else _shade(c, 0.6)
        if outer.detail == "toggle":
            mark = "#F3E3C3"
        for y in range(23, min(end, 60), 6):
            b.dot(15, y, mark)
    if outer.detail == "fur":
        for x in range(12, 24):
            b.rect(x, 12 + (x % 2), x, 16, "#FFF7EC")
    if outer.detail == "varsity":
        b.row(end, 10, 25, "#F2EEE6")
    if outer.detail == "leather":  # 광택 하이라이트와 비스듬한 지퍼
        shine = _shade(c, 1.45)
        for x, y in ((12, 20), (12, 21), (13, 22), (22, 26), (23, 27), (12, 33)):
            b.dot(x, y, shine)
        for y in range(24, end - 1, 2):
            b.dot(14, y, "#C9C9CF")
    if outer.detail == "light":  # 경량 패딩: 촘촘하고 얇은 퀼팅
        for y in range(17, end, 2):
            x0 = b.torso.get(y, b.torso[42])[0] - puff
            b.row(y, x0, 15, _shade(c, 0.9))
            b.row(y, 20, 35 - x0, _shade(c, 0.9))
    if end >= 60:  # 주머니
        b.row(48, 11, 13, shade)
        b.row(48, 22, 24, shade)
    if male and s in ("jacket", "coat", "trench"):  # 가슴 주머니
        b.row(23, 21, 23, shade)
    elif not male and not padding:  # 허리 다트
        for x in (13, 22):
            b.rect(x, 28, x, 33, shade)


def _draw_shoes(b: _Body) -> None:
    b.rect(12, 76, 16, 78, SHOE)
    b.rect(19, 76, 23, 78, SHOE)
    b.row(79, 11, 16, OUTLINE)
    b.row(79, 19, 24, OUTLINE)
    b.row(76, 13, 14, SHOE_LIGHT)
    b.row(76, 20, 21, SHOE_LIGHT)



# ---------------------------------------------------------------------------
# 팔 포즈: 화면 왼쪽 팔 기준 좌표, 오른쪽 팔은 거울 대칭
# ---------------------------------------------------------------------------
# upper: 어깨~팔꿈치, lower: 팔꿈치~손목, hand: 손 — 모두 (x0, y0, x1, y1)
ARM_POSES = {
    "down": {"upper": ((9, 15, 11, 18), (8, 19, 10, 30)), "lower": ((7, 31, 9, 42),), "hand": (7, 43, 9, 46)},
    # 팔을 굽혀 몸 앞에 물건을 든다 (물·핫팩)
    "bent": {"upper": ((9, 15, 11, 18), (8, 19, 10, 30)), "lower": ((8, 28, 15, 30),), "hand": (15, 27, 17, 30)},
    # 팔꿈치를 굽혀 손을 어깨 높이로 든다 (우산 손잡이)
    "up": {"upper": ((9, 15, 11, 18), (8, 19, 10, 24)), "lower": ((7, 12, 9, 24),), "hand": (7, 9, 9, 12)},
    # 손을 얼굴에 댄다 (선글라스·안경·마스크 쓰기)
    "face": {"upper": ((9, 15, 11, 18), (8, 19, 10, 24)), "lower": ((9, 12, 11, 24),), "hand": (11, 8, 13, 11)},
    # 경례하듯 손끝을 이마(모자 챙)에 댄다
    "salute": {"upper": ((9, 15, 11, 18), (8, 19, 10, 24)), "lower": ((9, 8, 11, 24),), "hand": (11, 3, 14, 5)},
    # 박수: 두 손이 가슴 앞에서 맞닿는다 / 벌린다
    "clap": {"upper": ((9, 15, 11, 18), (8, 19, 10, 30)), "lower": ((8, 28, 16, 30),), "hand": (16, 26, 17, 30)},
    "clap_open": {"upper": ((9, 15, 11, 18), (8, 19, 10, 30)), "lower": ((8, 28, 13, 30),), "hand": (13, 25, 14, 30)},
    # 만세: 두 팔을 머리 위로 쭉 뻗는다
    "raise": {"upper": ((9, 13, 11, 18), (8, 8, 10, 13)), "lower": ((7, 3, 9, 8),), "hand": (6, -1, 8, 2)},
    # 안녕 손 흔들기: 팔꿈치를 굽혀 손을 머리 옆으로 / 바깥으로
    "wave": {"upper": ((9, 15, 11, 18), (8, 10, 10, 15)), "lower": ((6, 4, 8, 10),), "hand": (5, 1, 7, 4)},
    "wave_out": {"upper": ((9, 15, 11, 18), (8, 10, 10, 15)), "lower": ((5, 5, 7, 10),), "hand": (3, 2, 5, 5)},
    # 안경 코받침을 손끝으로 밀어 올린다
    "push": {"upper": ((9, 15, 11, 18), (8, 19, 10, 24)), "lower": ((10, 12, 12, 24), (12, 10, 14, 12)), "hand": (15, 8, 17, 10)},
    # 주먹을 입에 대고 기침한다
    "cough": {"upper": ((9, 15, 11, 18), (8, 19, 10, 24)), "lower": ((10, 13, 12, 24), (12, 12, 14, 14)), "hand": (15, 10, 18, 12)},
    # 물병을 입으로 가져가 마신다
    "drink": {"upper": ((9, 15, 11, 18), (8, 19, 10, 24)), "lower": ((9, 12, 11, 24),), "hand": (12, 9, 14, 12)},
    # 핫팩을 쥔 손을 위로 흔든다
    "bent_hi": {"upper": ((9, 15, 11, 18), (8, 19, 10, 28)), "lower": ((8, 26, 15, 28),), "hand": (15, 25, 17, 28)},
}
FOREARM_ACROSS = ("bent", "bent_hi", "clap", "clap_open")  # 몸 앞을 가로지르는 아랫팔 (밑에 그늘을 넣는다)
HOLDING = ("bent", "bent_hi", "drink")  # 왼손에 물·핫팩을 쥐는 팔  # 몸 앞을 가로지르는 아랫팔 (밑에 그늘을 넣는다)


def _arm_rect(
    side: str, rect: tuple[int, int, int, int], widen: int = 0, shift: int = 0
) -> tuple[int, int, int, int]:
    """왼쪽 팔 좌표를 해당 쪽 좌표로. widen만큼 바깥쪽으로 넓히고, shift만큼 팔 전체를 바깥으로 옮긴다."""
    x0, y0, x1, y1 = rect
    x0 -= widen + shift
    x1 -= shift
    if side == "R":
        x0, x1 = _mirror(x0, x1)
    return x0, y0, x1, y1


def _draw_arm(b: _Body, look: Look, side: str, pose: str) -> None:
    """피부 → 상의 소매 → 아우터 소매 → 손 순서로 그린다. 몸 앞으로 오도록 몸판 뒤에 그린다."""
    geo = ARM_POSES[pose]
    segments = [("upper", r) for r in geo["upper"]] + [("lower", r) for r in geo["lower"]]
    edge_x = lambda r: r[0] if side == "L" else r[2]  # 바깥쪽 가장자리 열

    def paint(rect, color, widen=0, max_y=None):
        x0, y0, x1, y1 = _arm_rect(side, rect, widen, b.arm_dx)
        if max_y is not None:
            y1 = min(y1, max_y)
        if y0 <= y1:
            b.rect(x0, y0, x1, y1, color)
        return x0, y0, x1, y1

    for _, r in segments:
        paint(r, b.skin)
    # 상의 소매
    top = look.top
    long_sleeve = top.shape in ("long", "hood")
    short_end = 23 if b.body.gender == "male" else 21  # 반팔 길이
    tone = top.color if side == "L" else _shade(top.color, 0.9)
    for part, r in segments:
        if (part == "lower" and not long_sleeve) or top.shape == "sleeveless":
            continue
        limit = None if long_sleeve else (18 if top.shape == "puff" else short_end)
        x0, y0, x1, y1 = paint(r, tone, widen=1 if top.shape == "puff" and r[1] < 19 else 0, max_y=limit)
        if top.detail == "stripe":
            for y in range(y0 + 2, y1 + 1, 3):
                b.row(y, x0, x1, "#5B7DB1")
    if not long_sleeve and top.shape != "sleeveless":
        cuff_y = 18 if top.shape == "puff" else short_end
        for _, r in segments[:2]:
            x0, y0, x1, y1 = _arm_rect(side, r, 0, b.arm_dx)
            if y0 <= cuff_y <= y1:
                b.row(cuff_y, x0, x1, _shade(top.color, 0.78))
    # 아우터 소매 (늘 긴소매)
    outer = look.outer
    if outer:
        sleeve = "#F2EEE6" if outer.detail == "varsity" else outer.color
        tone = sleeve if side == "L" else _shade(sleeve, 0.9)
        widen = 1 if outer.shape.startswith("padding") else 0
        for _, r in segments:
            x0, y0, x1, y1 = paint(r, tone, widen=widen)
            b.rect(edge_x((x0, y0, x1, y1)), y0, edge_x((x0, y0, x1, y1)), y1, _shade(sleeve, 1.12 if side == "L" else 0.8))
            if outer.shape.startswith("padding"):
                for y in range(y0 + 3, y1 + 1, 4):
                    b.row(y, x0, x1, _shade(sleeve, 0.78))
        # 소맷단
        x0, y0, x1, y1 = _arm_rect(side, segments[-1][1], widen, b.arm_dx)
        cuff = outer.color if outer.detail == "varsity" else _shade(sleeve, 0.78)
        if geo is ARM_POSES["down"]:
            b.row(y1, x0, x1, cuff)
    if pose in FOREARM_ACROSS:  # 몸 앞을 가로지르는 아랫팔 밑에 그늘을 넣어 몸판과 구분한다
        layer = ("#F2EEE6" if outer.detail == "varsity" else outer.color) if outer else (top.color if long_sleeve else b.skin)
        x0, y0, x1, y1 = _arm_rect(side, geo["lower"][0], 0, b.arm_dx)
        edge = _shade(layer, 0.6)
        b.row(y0 - 1, x0 + 2 if side == "L" else x0, x1 if side == "L" else x1 - 2, edge)
        b.row(y1 + 1, x0, x1, edge)
    # 손
    hx0, hy0, hx1, hy1 = _arm_rect(side, geo["hand"], 0, b.arm_dx)
    b.rect(hx0, hy0, hx1, hy1, prop_color(look, "gloves") if look.mittens else b.skin)


# ---------------------------------------------------------------------------
# 소품: 목도리·모자·선글라스·우산·물·핫팩
# ---------------------------------------------------------------------------

UMBRELLA_X = 27  # 우산대 위치 (오른쪽 팔 'up' 포즈 손 가운데)
# 펼친 우산 돔: 줄(y)별 반폭. 반폭 21이면 지름 43px로, 오른손에 들어도 왼쪽 어깨 바깥까지 덮는다
CANOPY_ROWS = {-16: 4, -15: 9, -14: 13, -13: 15, -12: 17, -11: 19, -10: 20, -9: 21, -8: 21}
CANOPY_EDGE_Y = -7  # 물결 가장자리 줄 (머리·비니 방울 바로 위)
CANOPY_HALF = max(CANOPY_ROWS.values())


def _draw_canopy(b: _Body, color: str, lace: bool) -> None:
    """펼친 큰 우산: 높은 돔 캐노피, 빛 받는 면, 꼭지에서 뻗는 살 8개, 물결 가장자리, 꼭지."""
    cx = UMBRELLA_X + b.arm_dx
    light, dark = _shade(color, 1.18), _shade(color, 0.78)
    for y, half in CANOPY_ROWS.items():
        b.row(y, cx - half, cx + half, color)
        b.row(y, cx - half + 1, cx - half // 3, light)  # 빛 받는 왼쪽 면
        b.dot(cx + half, y, dark)  # 그늘진 오른쪽 끝
    # 살: 꼭지에서 가장자리 물결 사이(6px 간격)로 뻗는 선
    top = min(CANOPY_ROWS)
    span = CANOPY_EDGE_Y - top
    for edge in range(-CANOPY_HALF, CANOPY_HALF + 1, 6):
        for y in range(top + 1, CANOPY_EDGE_Y + 1):
            b.dot(cx + round(edge * (y - top) / span), y, dark)
    # 물결 가장자리: 살 사이마다 아래로 볼록
    for x in range(cx - CANOPY_HALF, cx + CANOPY_HALF + 1):
        k = (x - (cx - CANOPY_HALF)) % 6
        if k in (1, 2, 3, 4):
            b.dot(x, CANOPY_EDGE_Y, WHITE if lace else color)
        if k in (2, 3):
            b.dot(x, CANOPY_EDGE_Y + 1, WHITE if lace else dark)
    b.rect(cx, top - 2, cx, top - 1, "#6B4E3D")  # 꼭지


def canopy_box(body: Body) -> tuple[int, int, int, int]:
    """판 기준 펼친 우산 영역 (x0, y0, x1, y1). 풍경에서 우산 아래 비를 지울 때 쓴다."""
    cx = UMBRELLA_X + (TORSO[15][0] - torso_of(body)[15][0]) + DX
    return cx - CANOPY_HALF, min(CANOPY_ROWS) + DY, cx + CANOPY_HALF, CANOPY_EDGE_Y + 1 + DY


def _draw_closed_umbrella(b: _Body, color: str) -> None:
    """접은 긴 우산 (꺼내는 중)."""
    cx = UMBRELLA_X + b.arm_dx
    b.rect(cx, -15, cx, -14, "#6B4E3D")
    b.rect(cx - 1, -13, cx + 1, 7, color)
    b.rect(cx + 1, -13, cx + 1, 7, _shade(color, 0.78))
    for y in (-8, -1):  # 묶음 끈
        b.row(y, cx - 1, cx + 1, _shade(color, 0.6))
    b.dot(cx, 8, _shade(color, 0.78))


def _draw_handle(b: _Body) -> None:
    cx = UMBRELLA_X + b.arm_dx
    wood = "#6B4E3D"
    b.rect(cx, 13, cx, 17, wood)
    b.dot(cx - 1, 18, wood)
    b.dot(cx - 2, 17, wood)


def _draw_shaft(b: _Body, top_y: int) -> None:
    b.rect(UMBRELLA_X + b.arm_dx, top_y, UMBRELLA_X + b.arm_dx, 12, "#4A3A30")


def _draw_wearables(b: _Body, look: Look, face_on: bool, glasses_dy: int = 0) -> None:
    """목도리·모자·귀마개, 그리고 face_on이면 선글라스·마스크."""
    if look.scarf:
        c = prop_color(look, "scarf")
        b.rect(13, 13, 22, 16, c)
        b.row(14, 13, 22, _shade(c, 0.82))
        b.rect(19, 17, 21, 27, c)
        b.rect(21, 17, 21, 27, _shade(c, 0.82))
        for x in (19, 21):
            b.dot(x, 28, c)
    if look.hat == "beanie":
        c = prop_color(look, "beanie")
        b.rect(12, -3, 23, 3, c)
        b.row(-4, 14, 21, c)
        b.rect(11, 2, 24, 4, _shade(c, 0.8))
        for x in range(12, 24, 2):
            b.rect(x, -2, x, 1, _shade(c, 0.88))
        b.rect(17, -6, 18, -5, WHITE)
    elif look.hat == "cap":
        c = prop_color(look, "cap")
        b.rect(12, -2, 23, 2, c)
        b.row(-3, 14, 21, c)
        b.rect(7, 2, 14, 3, _shade(c, 0.8))
    elif look.hat == "bucket":
        c = prop_color(look, "bucket")
        b.rect(13, -3, 22, 2, c)
        b.rect(9, 2, 26, 3, c)
        b.row(1, 13, 22, _shade(c, 0.85))
    if look.earmuffs or look.hat == "earmuffs":  # 머리띠 + 귀를 덮는 털 뭉치
        c = prop_color(look, "earmuffs")
        band = -4 if look.hat == "beanie" else -1
        b.row(band, 13, 22, _shade(c, 0.8))
        b.rect(11, band + 1, 11, 4, _shade(c, 0.8))
        b.rect(24, band + 1, 24, 4, _shade(c, 0.8))
        b.rect(9, 5, 12, 10, c)
        b.rect(23, 5, 26, 10, c)
        b.rect(10, 4, 11, 4, c)
        b.rect(24, 4, 25, 4, c)
        b.dot(10, 6, _shade(c, 1.35))  # 털 윤기
        b.dot(24, 6, _shade(c, 1.35))
    if face_on and "mask" in look.props:  # 코와 입을 덮는 마스크, 귀에 거는 끈
        c = prop_color(look, "mask")
        b.rect(14, 9, 21, 12, c)
        b.row(8, 15, 20, c)
        b.row(10, 15, 20, _shade(c, 0.86))  # 주름
        b.row(12, 15, 20, _shade(c, 0.86))
        b.dot(13, 8, _shade(c, 0.7))
        b.dot(22, 8, _shade(c, 0.7))
        b.dot(12, 7, _shade(c, 0.7))
        b.dot(23, 7, _shade(c, 0.7))
    if face_on and "glasses" in look.props:  # 투명한 안경: 눈 둘레 테두리 + 코받침
        c, dy = prop_color(look, "glasses"), glasses_dy
        for x in (13, 18):
            b.row(6 + dy, x, x + 3, c)
            b.row(9 + dy, x, x + 3, c)
            b.rect(x, 7 + dy, x, 8 + dy, c)
            b.rect(x + 3, 7 + dy, x + 3, 8 + dy, c)
        b.dot(17, 7 + dy, c)
    if face_on and "sunglasses" in look.props:
        c = prop_color(look, "sunglasses")
        b.rect(13, 7 + glasses_dy, 16, 8 + glasses_dy, c)
        b.rect(19, 7 + glasses_dy, 22, 8 + glasses_dy, c)
        b.row(7 + glasses_dy, 17, 18, c)
        b.dot(13, 7 + glasses_dy, _shade(c, 1.4))
        b.dot(19, 7 + glasses_dy, _shade(c, 1.4))


def _draw_held(b: _Body, look: Look, arm: str = "bent") -> None:
    """왼손에 든 물병·핫팩. 손이 감싸도록 손을 다시 덮는다.
    arm: bent(몸 앞) · bent_hi(흔들어 올린 손) · drink(입에 대고 마시는 손)"""
    props = set(look.props)
    hand = prop_color(look, "gloves") if look.mittens else b.skin
    if arm == "drink":
        if "water" in props:  # 비스듬히 기울인 물병, 병목이 입에 닿는다
            c = prop_color(look, "water")
            b.rect(9, 4, 12, 8, c)
            b.rect(10, 5, 11, 6, WHITE)  # 라벨
            b.dot(13, 9, c)
            b.dot(14, 10, c)
            b.dot(15, 10, _shade(c, 0.5))  # 뚜껑을 연 병목
            b.rect(12, 9, 14, 12, hand)
        return
    dy = -2 if arm == "bent_hi" else 0
    if "water" in props:
        c = prop_color(look, "water")
        b.row(19 + dy, 15, 17, _shade(c, 0.5))  # 뚜껑
        b.rect(15, 20 + dy, 17, 31 + dy, c)
        b.rect(15, 23 + dy, 17, 25 + dy, WHITE)  # 라벨
        b.dot(15, 21 + dy, _shade(c, 1.5))
    elif "hotpack" in props:
        c = prop_color(look, "hotpack")
        b.rect(13, 25 + dy, 18, 31 + dy, c)
        b.rect(14, 26 + dy, 17, 27 + dy, _shade(c, 1.45))
        if dy:  # 흔들 때 나는 온기
            for x, y in ((12, 22), (19, 23), (11, 25)):
                b.dot(x, y, "#FFD8B0")
    b.rect(15, 27 + dy, 17, 29 + dy, hand)


def _draw_wind(b: _Body, look: Look, level: int) -> None:
    """바람에 머리칼과 목도리 끝이 오른쪽으로 날린다. level이 클수록 더 멀리."""
    for i, y in enumerate(range(1, 12, 2)):
        reach = 24 + level + (i % 2) + (1 if 3 <= y <= 7 else 0)
        b.row(y, 24, reach, HAIR)
        b.row(y + 1, 24, reach - 1, HAIR_DARK)
        b.dot(reach, y, HAIR_LIGHT)
    if look.scarf:  # 목도리 끝자락이 펄럭인다
        c = prop_color(look, "scarf")
        b.rect(21, 16, 22 + level * 3, 18, c)
        b.row(17, 21, 22 + level * 3, _shade(c, 0.82))
        b.dot(23 + level * 3, 16 + level % 2, c)


def _draw_cough(b: _Body) -> None:
    """기침할 때 입 옆으로 퍼지는 작은 숨."""
    for x, y in ((23, 10), (25, 9), (24, 12), (26, 11)):
        b.dot(x, y, "#E6E9EE")


@dataclass(frozen=True)
class Pose:
    """한 장면(프레임)의 자세."""

    left: str = "down"
    right: str = "down"
    canopy: str | None = None  # "open" | "closed" | None
    hold: bool = True  # 굽힌 왼팔에 물·핫팩을 드는지
    face_on: bool = True  # 선글라스·안경·마스크를 쓴 상태인지
    eyes: str | None = None  # 이 장면에서만 바꿀 눈 (예: 만세할 때 웃는 눈)
    wind: int = 0  # 머리칼·목도리가 날리는 정도 (0~2)
    glasses_dy: int = 0  # 안경·선글라스를 추켜올린 높이 (-1)
    cough: bool = False  # 기침하는 숨
    mouth: str | None = None  # "open"(말할 때) | "smile"(활짝) | None(기본)


def final_pose(look: Look) -> Pose:
    props = set(look.props)
    canopy = "open" if props & {"umbrella", "parasol"} else None
    return Pose(left="bent" if props & {"water", "hotpack"} else "down", right="up" if canopy else "down", canopy=canopy)


HATS = ("beanie", "cap", "bucket", "earmuffs")
FACE_ITEMS = ("sunglasses", "glasses", "mask")


def pose_frames(look: Look, action: str | None = None) -> list[Pose]:
    """방금 챙긴 준비물(action)에 맞는 동작 → 최종 자세. action이 없으면 움직이지 않고 최종 자세만.
    - 우산·양산: 그냥 서 있다가 → 접은 우산을 들어 올려 → 펼친다
    - 물: 입에 대고 꿀꺽 마신다 → 몸 앞에 든다
    - 핫팩: 쥔 손을 위아래로 흔든다
    - 선글라스·안경: 손끝으로 코받침을 밀어 추켜올린다
    - 마스크: 주먹을 입에 대고 콜록 기침한다
    - 목도리: 바람에 머리칼과 목도리 끝이 휘날린다
    - 장갑: 짝짝 박수 두 번
    - 여벌 가디건: 웃는 눈으로 만세 → 돌아온다
    - 모자·귀마개: 경례하듯 모자를 만진다 → 내린다
    """
    final = final_pose(look)
    if not action:
        return [final]
    if action in ("umbrella", "parasol") and final.canopy:
        return [Pose(face_on=final.face_on, hold=False), replace(final, canopy="closed"), final]
    if action == "water" and final.left == "bent":
        drink = replace(final, left="drink", eyes="closed")
        return [drink, drink, final]
    if action == "hotpack" and final.left == "bent":
        shake = replace(final, left="bent_hi")
        return [shake, final, shake, final]
    if action in ("sunglasses", "glasses") and action in look.props:
        push = replace(final, right="push", canopy=None)
        return [push, replace(push, glasses_dy=-1), final]
    if action == "mask" and "mask" in look.props:
        cough = replace(final, right="cough", canopy=None, eyes="closed", cough=True)
        return [cough, replace(final, canopy=None), cough, final]
    if action == "scarf" and look.scarf:
        return [replace(final, wind=1), replace(final, wind=2), replace(final, wind=1), final]
    if action == "gloves":
        open_, shut = Pose("clap_open", "clap_open", hold=False), Pose("clap", "clap", hold=False)
        return [open_, shut, open_, shut, final]
    if action == "extra_layer":
        cheer = Pose("raise", "raise", hold=False, eyes="smile")
        return [cheer, cheer, final]
    if action in HATS:
        touch = replace(final, right="salute", canopy=None)
        return [touch, touch, final]
    return [final]


# 다리 늘이기: 몸 기준 44~74행 사이에서 고르게 고른 줄을 복제해 다리를 길게 한다 (키별 줄 수는 LEG_EXTRA_BY).
# 직선인 바지·치마·코트 밑단은 줄을 복제해도 모양이 그대로라 좌표를 다시 잡지 않아도 된다.
LEG_SPAN = (44, 74)
LEG_EXTRA = LEG_EXTRA_BY[("female", "normal")]
FOOT_Y = DY + 79 + LEG_EXTRA  # 기본 체형의 판 기준 신발 밑창 줄


def leg_extra(body: Body) -> int:
    return LEG_EXTRA_BY.get((body.gender, body.height), LEG_EXTRA)


def foot_y(body: Body) -> int:
    """판 기준 신발 밑창 줄. 풍경에서 발을 땅에 맞출 때 쓴다."""
    return DY + 79 + leg_extra(body)


def _stretch_legs(g: Grid, extra: int = LEG_EXTRA) -> Grid:
    y0, y1 = (v + DY for v in LEG_SPAN)
    span = y1 - y0 + 1
    dup = {y0 + i * span // extra for i in range(extra)} if extra else set()
    out = Grid(g.width, g.height)
    for (x, y), color in g.px.items():
        shift = sum(1 for d in dup if d < y)  # 이 줄 위에서 복제된 줄 수
        out.dot(x, y + shift, color)
        if y in dup:
            out.dot(x, y + shift + 1, color)
    return out


def draw_character(look: Look, pose: Pose | None = None) -> Grid:
    pose = pose or final_pose(look)
    g = Grid(CHAR_W, CHAR_H)
    b = _Body(g, look.body)
    _draw_skin(b, look)
    _draw_bottom(b, look)
    _draw_top(b, look.top, look.onepiece)
    if look.outer:
        _draw_outer(b, look.outer)
    _draw_shoes(b)
    _draw_head(b, look, pose.eyes, pose.mouth)
    _draw_wearables(b, look, pose.face_on, pose.glasses_dy)
    if pose.wind:
        _draw_wind(b, look, pose.wind)
    if pose.cough:
        _draw_cough(b)
    umbrella = "umbrella" if "umbrella" in look.props else "parasol"
    if pose.canopy:
        _draw_shaft(b, CANOPY_EDGE_Y if pose.canopy == "open" else 8)
    _draw_arm(b, look, "L", pose.left)
    _draw_arm(b, look, "R", pose.right)
    if pose.left in HOLDING and pose.hold:
        _draw_held(b, look, pose.left)
    if pose.canopy == "open":
        _draw_canopy(b, prop_color(look, umbrella), lace=umbrella == "parasol")
        _draw_handle(b)
    elif pose.canopy == "closed":
        _draw_closed_umbrella(b, prop_color(look, umbrella))
        _draw_handle(b)
    return _stretch_legs(g, leg_extra(look.body)).outlined()


def render_minimi(look: Look, title: str) -> str:
    """캐릭터만, 최종 자세 (옷장 썸네일·저장 창용)."""
    return _svg(draw_character(look).cropped(), title)


# ---------------------------------------------------------------------------
# 바깥 풍경: 하늘(날씨)·건물·나무·길 + 움직이는 층(구름·별·비·눈)
# 배경은 48×76 판에 그린 뒤 2배로 키우고, 비·눈과 캐릭터는 원래 해상도로 그린다.
# ---------------------------------------------------------------------------

SKY = {
    "clear_day": ("#7CC6FF", "#B4E4FF"),
    "clear_night": ("#25214A", "#3E3A66"),
    "cloudy": ("#A9C1C8", "#C7DADF"),
    "rain": ("#7F98A6", "#9DB3BF"),
    "snow": ("#C3D1DC", "#DCE6EE"),
}
NIGHT_SCENES = ("clear_night",)
BG_W, BG_H = 48, 76
GROUND_Y = 64  # 배경 판 기준 땅 높이
PRECIP_PERIOD = 28  # 비·눈 무늬가 반복되는 높이 (이만큼 내려가면 처음 모습과 같아져 끊김 없이 반복된다)
FRAME_SECONDS = 0.35  # 포즈 한 장면 길이


def _cloud(g: Grid, x: int, y: int, color: str = "#F5F7F8") -> None:
    g.fill(x + 2, y, 5, 1, color)
    g.fill(x + 1, y + 1, 8, 1, color)
    g.fill(x, y + 2, 11, 2, color)


def _draw_sky(g: Grid, scene: str) -> None:
    top, low = SKY.get(scene, SKY["cloudy"])
    band = 26
    g.fill(0, 0, BG_W, band, top)
    g.fill(0, band, BG_W, GROUND_Y - band, low)
    for x in range(0, BG_W, 2):  # 두 색 사이 도트 디더링
        g.dot(x, band - 1, low)
        g.dot(x + 1, band, top)
    if scene == "clear_day":
        g.fill(40, 4, 6, 6, "#FFD54A")
        g.fill(41, 3, 4, 8, "#FFD54A")
        for x, y in ((43, 0), (43, 13), (37, 7), (38, 2), (38, 12)):
            g.dot(x, y, "#FFE58A")
    elif scene == "clear_night":
        g.fill(40, 4, 5, 5, "#F6E7A1")
        g.fill(42, 3, 3, 4, top)


def _draw_clouds(g: Grid, scene: str) -> None:
    if scene == "clear_day":
        _cloud(g, 4, 24)
        _cloud(g, 22, 12, "#EEF6FC")
    elif scene in ("cloudy", "rain", "snow"):
        shade = "#E3E9EC" if scene != "rain" else "#C9D2D8"
        _cloud(g, 3, 4, shade)
        _cloud(g, 24, 2, shade)
        _cloud(g, 36, 10, shade)
        _cloud(g, 8, 28, shade)


def _draw_stars(g: Grid) -> None:
    for x, y in ((5, 3), (12, 8), (19, 2), (26, 6), (30, 12), (8, 26), (44, 20), (23, 30), (34, 24)):
        g.dot(x, y, WHITE)


def _draw_town(g: Grid, scene: str) -> None:
    night = scene in NIGHT_SCENES
    building = "#6B7894" if not night else "#2F2C4F"
    window = "#FFE9A8" if night else "#C9DDF0"
    for x, w, h in ((0, 7, 15), (7, 5, 10), (31, 6, 12), (43, 5, 17)):
        g.fill(x, GROUND_Y - h, w, h, building)
        for wy in range(GROUND_Y - h + 2, GROUND_Y - 1, 3):
            for wx in range(x + 1, x + w - 1, 2):
                g.dot(wx, wy, window)
    trunk, leaf = "#7A5235", "#5DAF6B" if scene != "snow" else "#A9C8B0"
    g.fill(39, GROUND_Y - 5, 2, 5, trunk)
    g.fill(36, GROUND_Y - 12, 8, 7, leaf)
    g.fill(37, GROUND_Y - 13, 6, 1, leaf)
    if scene == "snow":
        g.fill(36, GROUND_Y - 13, 8, 2, WHITE)


def _draw_ground(g: Grid, scene: str) -> None:
    grass = "#7CC77E" if scene != "snow" else "#F4F8FB"
    g.fill(0, GROUND_Y, BG_W, 2, grass)
    walk, joint = ("#D9D4CC", "#C4BEB4") if scene != "snow" else ("#EEF2F6", "#D8E0E8")
    g.fill(0, GROUND_Y + 2, BG_W, BG_H - GROUND_Y - 2, walk)
    for y in range(GROUND_Y + 4, BG_H, 3):
        g.fill(0, y, BG_W, 1, joint)
        for x in range((y // 3) % 2 * 4, BG_W, 8):
            g.dot(x, y - 1, joint)
    if scene == "rain":  # 물웅덩이
        g.fill(2, GROUND_Y + 8, 8, 2, "#8FB6D9")
        g.fill(37, GROUND_Y + 6, 7, 2, "#8FB6D9")


def _precip_layer(scene: str) -> Grid | None:
    """비·눈 무늬. PRECIP_PERIOD마다 같은 모양이 반복되어, 그만큼 내려가는 애니메이션이 끊김 없이 이어진다."""
    if scene not in ("rain", "snow"):
        return None
    g = Grid(SCENE_W, SCENE_H + PRECIP_PERIOD)
    cell_w, cell_h = 12, PRECIP_PERIOD // 2
    for row, top in enumerate(range(0, g.height, cell_h)):
        for col, left in enumerate(range(0, g.width, cell_w)):
            n = (row % 2) * 31 + col * 17  # 두 줄마다 반복 → 높이 PRECIP_PERIOD 주기
            x, y = left + (n * 7) % cell_w, top + (n * 5) % cell_h
            if scene == "rain":
                g.fill(x, y, 1, 4, "#4C7FCF")
            else:
                size = 2 if n % 3 == 0 else 1
                g.fill(x, y, size, size, WHITE)
    return g


SCENE_CSS = f"""
.drift {{ animation: mj-drift 16s steps(16) infinite alternate; }}
.twinkle {{ animation: mj-twinkle 2.4s steps(2) infinite alternate; }}
.rain {{ animation: mj-fall 0.7s linear infinite; }}
.snow {{ animation: mj-fall 3.6s linear infinite; }}
@keyframes mj-drift {{ from {{ transform: translateX(-4px); }} to {{ transform: translateX(4px); }} }}
@keyframes mj-twinkle {{ from {{ opacity: 1; }} to {{ opacity: 0.35; }} }}
@keyframes mj-fall {{ from {{ transform: translateY(0); }} to {{ transform: translateY({PRECIP_PERIOD}px); }} }}
@keyframes mj-on {{ to {{ opacity: 1; }} }}
@keyframes mj-off {{ to {{ opacity: 0; }} }}
@media (prefers-reduced-motion: reduce) {{
  .drift, .twinkle, .rain, .snow, .frame {{ animation: none !important; }}
  .frame {{ opacity: 0 !important; }}
  .frame.last {{ opacity: 1 !important; }}
}}
"""


def _frame_style(i: int, count: int) -> str:
    """i번째 포즈를 i*T초에 보이고 (i+1)*T초에 숨긴다. 마지막 장면은 계속 보인다."""
    t = FRAME_SECONDS
    if count == 1:
        return ""
    if i == 0:
        return f"animation: mj-off .01s {t:.2f}s forwards;"
    on = f"mj-on .01s {i * t:.2f}s forwards"
    if i == count - 1:
        return f"opacity: 0; animation: {on};"
    return f"opacity: 0; animation: {on}, mj-off .01s {(i + 1) * t:.2f}s forwards;"


# ---------------------------------------------------------------------------
# 첫 화면 안내 캐릭터: 상반신만 크게, 말하고 손 흔들고 박수치고 웃는 동작을 무작위로 이어서 반복
# ---------------------------------------------------------------------------
GREETER_SECONDS = 0.35  # 한 장면 길이
GREETER_MOVES = {
    "talk": [Pose(mouth="open"), Pose(), Pose(mouth="open"), Pose(), Pose(mouth="open"), Pose()],
    "wave": [Pose(right="wave", eyes="smile", mouth="smile"), Pose(right="wave_out", eyes="smile", mouth="smile")] * 2,
    "clap": [Pose("clap_open", "clap_open", mouth="smile"), Pose("clap", "clap", eyes="smile", mouth="open")] * 2,
    "smile": [Pose(eyes="smile", mouth="smile")] * 3,
    "blink": [Pose(), Pose(eyes="closed"), Pose(), Pose()],
}


def greeter_moves(seed: int) -> list[str]:
    """안녕(손 흔들기)으로 시작해 나머지 동작을 seed에 따라 섞는다. 말하기는 꼭 두 번."""
    rest = ["talk", "clap", "smile", "blink", "talk"]
    random.Random(seed).shuffle(rest)
    return ["wave", *rest]


def render_greeter(look: Look, title: str, seed: int = 0) -> str:
    """상반신 안내 캐릭터 SVG. 장면들을 CSS로 이어 붙여 무한 반복한다 (움직임 줄이기면 첫 장면만)."""
    frames = [pose for move in greeter_moves(seed) for pose in GREETER_MOVES[move]]
    n, t = len(frames), GREETER_SECONDS
    x0, y0, x1, y1 = DX - 4, DY - 8, DX + 39, DY + 46  # 머리 위로 든 손부터 허리까지
    groups = []
    for i, pose in enumerate(frames):
        g = draw_character(look, pose)
        crop = Grid(x1 - x0, y1 - y0)
        crop.px = {(x - x0, y - y0): c for (x, y), c in g.px.items() if x0 <= x < x1 and y0 <= y < y1}
        cls = "g first" if i == 0 else "g"
        groups.append(f'<g class="{cls}" style="animation-delay: -{(n - i) * t:.2f}s">{crop.rects()}</g>')
    css = (
        f".g {{ opacity: 0; animation: mj-g {n * t:.2f}s step-end infinite; }}"
        f"@keyframes mj-g {{ 0% {{ opacity: 1; }} {100 / n:.3f}% {{ opacity: 0; }} 100% {{ opacity: 0; }} }}"
        "@media (prefers-reduced-motion: reduce) { .g { animation: none; opacity: 0; } .g.first { opacity: 1; } }"
    )
    tt = escape(title)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {x1 - x0} {y1 - y0}" '
        f'shape-rendering="crispEdges" role="img" aria-label="{tt}" '
        f'style="width:100%;height:auto;display:block;image-rendering:pixelated">'
        f"<title>{tt}</title><style>{css}</style>{''.join(groups)}</svg>"
    )


def render_scene(look: Look | None, scene: str, title: str, action: str | None = None) -> str:
    """집 밖 풍경. 구름이 흐르고 비·눈이 내리고 별이 반짝인다. 챙긴 준비물이 바뀌면 캐릭터가 그 동작을 한 번 한다."""
    bg = Grid(BG_W, BG_H)
    _draw_sky(bg, scene)
    _draw_town(bg, scene)
    _draw_ground(bg, scene)
    clouds = Grid(BG_W, BG_H)
    _draw_clouds(clouds, scene)
    parts = [bg.scaled(2).rects(), f'<g class="drift">{clouds.scaled(2).rects()}</g>']
    if scene == "clear_night":
        stars = Grid(BG_W, BG_H)
        _draw_stars(stars)
        parts.append(f'<g class="twinkle">{stars.scaled(2).rects()}</g>')
    feet = SCENE_H - 12  # 발이 인도 한가운데에 오도록
    x, y = (SCENE_W - CHAR_W) // 2, feet - foot_y(look.body if look else Body())
    precip = _precip_layer(scene)
    if precip is not None:
        layer = f'<g transform="translate(0 -{PRECIP_PERIOD})"><g class="{scene}">{precip.rects()}</g></g>'
        if look is not None and final_pose(look).canopy == "open":
            # 우산 아래(가장자리에서 발끝까지, 양옆 1px 여유)는 비·눈이 닿지 않는다
            x0, y0, x1, y1 = canopy_box(look.body)
            dry = f'<rect x="{x + x0 - 1}" y="{y + y1}" width="{x1 - x0 + 3}" height="{feet - y - y1 + 2}" fill="#000"/>'
            parts.append(
                f'<mask id="mj-dry" maskUnits="userSpaceOnUse" x="0" y="0" width="{SCENE_W}" height="{SCENE_H}">'
                f'<rect width="{SCENE_W}" height="{SCENE_H}" fill="#fff"/>{dry}</mask>'
            )
            layer = f'<g mask="url(#mj-dry)">{layer}</g>'
        parts.append(layer)
    if look is not None:
        shadow = Grid(SCENE_W, SCENE_H)
        shadow.fill(36, feet + 1, 24, 2, "#B9B3A9")  # 발밑 그림자
        parts.append(shadow.rects())
        frames = pose_frames(look, action)
        groups = []
        for i, pose in enumerate(frames):
            cls = "frame last" if i == len(frames) - 1 else "frame"
            style = _frame_style(i, len(frames))
            attr = f' style="{style}"' if style else ""
            groups.append(f'<g class="{cls}"{attr}>{draw_character(look, pose).rects()}</g>')
        parts.append(f'<g transform="translate({x} {y})">{"".join(groups)}</g>')
    t = escape(title)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SCENE_W} {SCENE_H}" '
        f'shape-rendering="crispEdges" role="img" aria-label="{t}" '
        f'style="width:100%;height:auto;display:block;image-rendering:pixelated">'
        f"<title>{t}</title><style>{SCENE_CSS}</style>{''.join(parts)}</svg>"
    )


# ---------------------------------------------------------------------------
# 옷 아이콘 (상의·하의·아우터 카드)
# ---------------------------------------------------------------------------


def _icon_top(g: Grid, top: Garment) -> None:
    c = top.color
    g.fill(4, 3, 8, 10, c)
    if top.detail not in ("turtleneck",) and top.shape != "hood":
        for x in range(6, 10):  # 둥근 목선
            g.px.pop((x, 3), None)
        g.px.pop((7, 4), None)
        g.px.pop((8, 4), None)
    if top.shape in ("long", "hood"):
        g.fill(1, 4, 3, 9, c)
        g.fill(12, 4, 3, 9, c)
        g.fill(2, 3, 2, 1, c)
        g.fill(12, 3, 2, 1, c)
        seam = _shade(c, 0.8)  # 소매와 몸판 사이
        g.fill(4, 6, 1, 7, seam)
        g.fill(11, 6, 1, 7, seam)
        g.fill(1, 12, 3, 1, seam)  # 소맷단
        g.fill(12, 12, 3, 1, seam)
    elif top.shape == "puff":
        g.fill(0, 3, 4, 4, c)
        g.fill(12, 3, 4, 4, c)
    else:
        g.fill(1, 3, 3, 4, c)
        g.fill(12, 3, 3, 4, c)
    if top.shape == "hood":
        g.fill(5, 1, 6, 2, _shade(c, 0.85))
        g.dot(7, 5, WHITE)
        g.dot(8, 5, WHITE)
    d = top.detail
    if d == "turtleneck":
        g.fill(6, 1, 4, 2, c)
    elif d == "collar":
        collar = WHITE if c != "#FFFFFF" else "#D8D8D8"
        g.fill(5, 3, 2, 2, collar)
        g.fill(9, 3, 2, 2, collar)
    elif d == "stripe":
        for y in (5, 7, 9, 11):
            g.fill(1, y, 14, 1, "#5B7DB1")
    elif d == "knit":
        for y in (5, 8, 11):
            for x in range(4, 12, 2):
                g.dot(x, y, _shade(c, 0.82))
    elif d == "graphic":
        g.fill(6, 6, 4, 3, ACCENT)
    elif d == "ribbon":
        g.fill(7, 3, 2, 1, ACCENT)
        g.dot(6, 4, ACCENT)
        g.dot(9, 4, ACCENT)


def _icon_bottom(g: Grid, bottom: Garment) -> None:
    c, s = bottom.color, bottom.shape
    if s.startswith("skirt"):
        end = {"skirt_mini": 8, "skirt_midi": 11}.get(s, 14)
        g.fill(4, 1, 8, 2, c)
        for i, y in enumerate(range(3, end)):
            spread = min(i // 2, 3)
            g.fill(4 - spread, y, 8 + spread * 2, 1, c)
        return
    g.fill(3, 1, 10, 2, c)
    length = 6 if s == "shorts" else 12
    left, width = (2, 5) if s == "wide" else (3, 4)
    g.fill(left, 3, width, length, c)
    g.fill(16 - left - width, 3, width, length, c)
    if s == "joggers":
        g.fill(3, 2 + length, 4, 1, _shade(c, 0.8))
        g.fill(9, 2 + length, 4, 1, _shade(c, 0.8))


def _icon_outer(g: Grid, outer: Garment) -> None:
    c = outer.color
    length = {"coat": 13, "trench": 13, "padding_long": 13}.get(outer.shape, 10)
    sleeve = "#F2EEE6" if outer.detail == "varsity" else c
    g.fill(1, 2, 3, 10, sleeve)
    g.fill(12, 2, 3, 10, sleeve)
    g.fill(4, 2, 4, length, c)
    g.fill(8, 2, 4, length, c)
    g.fill(7, 2, 2, length, _shade(c, 0.86))  # 여밈선
    g.fill(6, 1, 4, 1, _shade(c, 0.75))  # 깃
    if outer.shape in ("padding_short", "padding_long"):
        line = _shade(c, 0.78) if c != "#1F2124" else "#3A3D42"
        for y in range(4, 2 + length, 2 if outer.detail == "light" else 3):
            g.fill(1, y, 14, 1, line)
    if outer.detail == "leather":
        g.fill(5, 4, 1, 2, _shade(c, 1.5))
        g.fill(10, 6, 1, 2, _shade(c, 1.5))
    if outer.shape == "trench":
        g.fill(4, 7, 8, 1, _shade(c, 0.72))
    if outer.detail in ("buttons", "toggle"):
        for y in (4, 7, 10):
            g.dot(6, y, WHITE if c not in ("#FFFFFF", "#F5F1E6", "#E9DCCB") else _shade(c, 0.6))
    elif outer.detail == "fur":
        g.fill(4, 1, 8, 2, "#FFF7EC")


def _icon_supply(g: Grid, kind: str, c: str) -> None:
    if kind in ("umbrella", "parasol"):
        dark = _shade(c, 0.78)
        g.fill(6, 0, 4, 1, c)  # 돔 캐노피
        g.fill(3, 1, 10, 1, c)
        g.fill(1, 2, 14, 2, c)
        g.fill(0, 4, 16, 2, c)
        g.fill(1, 1, 6, 1, _shade(c, 1.18))  # 빛 받는 면
        g.fill(1, 2, 5, 2, _shade(c, 1.18))
        for x in (4, 8, 12):  # 살 이음선
            g.fill(x, 2, 1, 4, dark)
        for x in range(0, 16, 4):  # 물결 가장자리
            g.fill(x + 1, 6, 3, 1, WHITE if kind == "parasol" else c)
        g.dot(8, 0, "#6B4E3D")
        g.fill(8, 6, 1, 7, "#4A3A30")  # 우산대
        g.fill(8, 12, 1, 2, "#6B4E3D")  # J 손잡이
        g.dot(7, 14, "#6B4E3D")
        g.dot(6, 13, "#6B4E3D")
    elif kind == "sunglasses":
        g.fill(1, 6, 6, 4, c)
        g.fill(9, 6, 6, 4, c)
        g.fill(7, 6, 2, 1, c)
        g.fill(0, 6, 1, 1, c)
        g.fill(15, 6, 1, 1, c)
        g.fill(2, 7, 2, 1, _shade(c, 1.4))
        g.fill(10, 7, 2, 1, _shade(c, 1.4))
    elif kind == "water":
        g.fill(6, 1, 4, 2, _shade(c, 0.5))
        g.fill(5, 3, 6, 11, c)
        g.fill(5, 7, 6, 3, WHITE)
        g.fill(6, 4, 1, 2, _shade(c, 1.5))
    elif kind == "hotpack":
        g.fill(2, 3, 12, 10, c)
        g.fill(3, 4, 10, 1, _shade(c, 1.3))
        g.fill(5, 7, 6, 2, _shade(c, 1.6))
    elif kind == "windbreaker":
        _icon_outer(g, Garment("jacket", c))
        g.fill(7, 2, 2, 10, _shade(c, 1.75))  # 지퍼
    elif kind == "extra_layer":
        _icon_outer(g, Garment("cardigan", c, "buttons"))
    elif kind == "scarf":
        g.fill(2, 3, 12, 4, c)
        g.fill(9, 7, 4, 7, c)
        for y in (4, 6):
            g.fill(2, y, 12, 1, _shade(c, 0.82))
        g.fill(9, 13, 4, 1, WHITE)
    elif kind == "gloves":
        g.fill(3, 4, 7, 9, c)
        g.fill(10, 6, 3, 4, c)
        g.fill(3, 12, 7, 2, _shade(c, 0.75))
    elif kind == "beanie":
        g.fill(7, 1, 2, 2, WHITE)
        g.fill(4, 3, 8, 2, c)
        g.fill(2, 5, 12, 5, c)
        g.fill(2, 10, 12, 3, _shade(c, 0.8))
    elif kind == "cap":
        g.fill(4, 4, 9, 2, c)
        g.fill(3, 6, 11, 4, c)
        g.fill(0, 9, 6, 2, _shade(c, 0.8))
    elif kind == "bucket":
        g.fill(4, 3, 8, 6, c)
        g.fill(1, 9, 14, 2, c)
        g.fill(4, 8, 8, 1, _shade(c, 0.85))
    elif kind == "earmuffs":
        g.fill(5, 2, 6, 1, c)
        g.fill(3, 3, 2, 3, c)
        g.fill(11, 3, 2, 3, c)
        g.fill(1, 6, 5, 6, c)
        g.fill(10, 6, 5, 6, c)
    elif kind == "glasses":
        for x in (1, 9):  # 두 알의 테두리 (가운데는 비어 있다)
            g.fill(x, 5, 6, 1, c)
            g.fill(x, 10, 6, 1, c)
            g.fill(x, 6, 1, 4, c)
            g.fill(x + 5, 6, 1, 4, c)
        g.fill(7, 6, 2, 1, c)  # 코받침
        g.fill(0, 5, 1, 1, c)
        g.fill(15, 5, 1, 1, c)
        g.fill(2, 6, 1, 1, _shade(c, 1.8))  # 렌즈 반짝임
        g.fill(10, 6, 1, 1, _shade(c, 1.8))
    elif kind == "mask":
        g.fill(3, 4, 10, 8, c)
        g.fill(4, 3, 8, 1, c)
        g.fill(4, 12, 8, 1, c)
        for y in (6, 9):  # 주름
            g.fill(3, y, 10, 1, _shade(c, 0.82))
        g.fill(0, 4, 3, 1, _shade(c, 0.6))  # 귀걸이 끈
        g.fill(0, 5, 1, 5, _shade(c, 0.6))
        g.fill(0, 10, 3, 1, _shade(c, 0.6))
        g.fill(13, 4, 3, 1, _shade(c, 0.6))
        g.fill(15, 5, 1, 5, _shade(c, 0.6))
        g.fill(13, 10, 3, 1, _shade(c, 0.6))
    elif kind == "tights":
        g.fill(3, 1, 10, 2, c)
        g.fill(3, 3, 4, 11, c)
        g.fill(9, 3, 4, 11, c)


SUPPLY_KINDS = tuple(PROP_COLORS)


def render_supply(kind: str, title: str, color: str | None = None) -> str:
    """준비물 하나를 16×16 도트 아이콘으로. color가 없으면 기본색."""
    g = Grid(16, 16)
    _icon_supply(g, kind, color or PROP_COLORS[kind])
    framed = Grid(18, 18)
    framed.paste(g, 1, 1)
    return _svg(framed.outlined(), title)


def _icon_cut(g: Grid, category: str, gender: str) -> None:
    """성별 재단: 여성 상의는 허리를 좁히고, 남성 상의·아우터는 어깨를 넓힌다. 남성 바지는 일자."""
    if category in ("top", "outer"):
        if gender == "male":
            for (x, y), color in list(g.px.items()):
                if y in (3, 4) and x in (4, 11) and (x - 1 if x == 4 else x + 1, y) not in g.px:
                    g.dot(x - 1 if x == 4 else x + 1, y, color)
        else:
            for y in (8, 9):
                for x in (4, 11):
                    if (x - 1 if x == 4 else x + 1, y) not in g.px:  # 소매가 없는 곳만
                        g.px.pop((x, y), None)
    elif category == "bottom" and gender == "male":
        for (x, y), color in list(g.px.items()):
            if y >= 9 and x in (3, 12):
                g.dot(x - 1 if x == 3 else x + 1, y, color)


def _icon_dress(g: Grid, top: Garment, bottom: Garment) -> None:
    """원피스·세트: 위는 상의 실루엣, 아래는 치마(사다리꼴) 또는 바지(두 다리)."""
    c = top.color
    g.fill(5, 1, 6, 6, c)
    if top.shape != "sleeveless":
        g.fill(2, 1, 3, 3 if top.shape in ("short", "puff") else 6, c)
        g.fill(11, 1, 3, 3 if top.shape in ("short", "puff") else 6, c)
    g.fill(7, 1, 2, 1, _shade(c, 0.75))  # 목선
    bc = bottom.color
    if bottom.shape.startswith("skirt"):
        end = 11 if "mini" in bottom.shape else 15
        fitted = bottom.shape.startswith("skirt_fit")
        for i, y in enumerate(range(7, end)):
            spread = 0 if fitted else min(i // 2, 3)
            g.fill(5 - spread, y, 6 + spread * 2, 1, bc)
    else:
        length = 11 if bottom.shape == "shorts" else 15
        g.fill(5, 7, 6, 1, bc)
        g.fill(4, 8, 3, length - 8, bc)
        g.fill(9, 8, 3, length - 8, bc)
    if top.detail == "tweed":
        for x, y in ((6, 3), (9, 4), (7, 5), (5, 9), (9, 10), (7, 12)):
            g.dot(x, y, WHITE)
    elif top.detail == "floral":
        for x, y in ((6, 3), (9, 5)):
            g.dot(x, y, WHITE)


def render_dress(top: Garment, bottom: Garment, title: str) -> str:
    """원피스·세트 한 벌을 16×16 도트 아이콘으로."""
    g = Grid(16, 16)
    _icon_dress(g, top, bottom)
    framed = Grid(18, 18)
    framed.paste(g, 1, 1)
    return _svg(framed.outlined(), title)


def render_garment(garment: Garment, category: str, title: str, gender: str = "female") -> str:
    """옷 한 벌만 16×16 도트 아이콘으로. 성별에 따라 재단이 다르다."""
    g = Grid(16, 16)
    {"top": _icon_top, "bottom": _icon_bottom, "outer": _icon_outer}[category](g, garment)
    _icon_cut(g, category, gender)
    framed = Grid(18, 18)  # 가장자리 윤곽선이 잘리지 않게 1px 여백
    framed.paste(g, 1, 1)
    return _svg(framed.outlined(), title)
