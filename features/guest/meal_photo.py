"""밥상 사진을 저장하기 좋은 크기로 줄인다. Pillow는 Streamlit과 함께 설치된다."""

from __future__ import annotations

import io
import logging

from PIL import Image, ImageOps, UnidentifiedImageError

log = logging.getLogger("guest")

MAX_SIDE = 640  # 긴 변 기준 픽셀
QUALITY = 80


def shrink(raw: bytes | None) -> bytes | None:
    """사진을 긴 변 640px JPEG로 줄인다. 사진이 아니거나 읽을 수 없으면 None."""
    if not raw:
        return None
    try:
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img)  # 휴대폰 사진이 옆으로 눕지 않게
        img.thumbnail((MAX_SIDE, MAX_SIDE))
        out = io.BytesIO()
        img.convert("RGB").save(out, format="JPEG", quality=QUALITY)
        return out.getvalue()
    except (UnidentifiedImageError, OSError, ValueError) as e:
        log.warning("guest 밥상 사진 처리 실패: %s", e)
        return None
