"""Render source-free Flow Circular placeholders for terminal output."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any


# The font remains package-owned rather than presentation-module-owned. Keep
# relocation from changing the one bundled asset identity or duplicating it.
_FONT_PATH = (
    Path(__file__).resolve().parents[2] / "assets" / "FlowCircular-Regular.ttf"
)
_FONT_SIZE = 10
_BRAILLE_DOTS = (
    (0, 0, 0x01),
    (0, 1, 0x02),
    (0, 2, 0x04),
    (1, 0, 0x08),
    (1, 1, 0x10),
    (1, 2, 0x20),
    (0, 3, 0x40),
    (1, 3, 0x80),
)


class FlowPlaceholderError(RuntimeError):
    """The bundled Flow Circular renderer is unavailable or invalid."""


@lru_cache(maxsize=1)
def _pillow_modules() -> tuple[Any, Any, Any]:
    """Load the renderer dependency only when a placeholder is requested."""

    # The CLI imports every command while it builds its command tree.  Keeping
    # this feature-specific dependency behind the renderer boundary prevents a
    # broken installation from disabling unrelated commands such as Profile
    # selection, while the renderer itself still fails closed.
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as error:
        raise FlowPlaceholderError(
            "Flow Circular rendering requires Pillow; reinstall memcommit "
            "with its runtime dependencies."
        ) from error
    return Image, ImageDraw, ImageFont


@lru_cache(maxsize=1)
def _flow_font() -> Any:
    _image, _image_draw, image_font = _pillow_modules()
    try:
        return image_font.truetype(str(_FONT_PATH), _FONT_SIZE)
    except (OSError, ValueError) as error:
        raise FlowPlaceholderError(
            "The bundled Flow Circular font is unavailable."
        ) from error


@lru_cache(maxsize=512)
def _render_word(length: int) -> str:
    """Rasterize only an equal-length dummy mask, never source characters."""

    if length < 1:
        raise FlowPlaceholderError("Flow Circular word length must be positive.")
    image_module, image_draw, _image_font = _pillow_modules()
    font = _flow_font()
    dummy = "x" * length
    bounds = font.getbbox(dummy)
    if bounds is None:
        raise FlowPlaceholderError("Flow Circular could not render a word mask.")
    width = max(1, bounds[2] - bounds[0])
    height = max(1, bounds[3] - bounds[1])
    image = image_module.new("L", (width, height), color=255)
    image_draw.Draw(image).text(
        (-bounds[0], -bounds[1]),
        dummy,
        font=font,
        fill=0,
    )

    # One terminal cell represents a 2x4 Braille raster. Resizing each word to
    # exactly its source length keeps the requested length disclosure while
    # retaining Flow Circular's rounded beginning and end caps.
    image = image.resize(
        (length * 2, 4),
        resample=image_module.Resampling.LANCZOS,
    ).point(lambda pixel: 0 if pixel < 180 else 255)
    pixels = image.load()
    rendered: list[str] = []
    for x in range(0, image.width, 2):
        bits = sum(
            bit
            for dx, dy, bit in _BRAILLE_DOTS
            if pixels[x + dx, dy] == 0
        )
        rendered.append(chr(0x2800 + bits) if bits else " ")
    return "".join(rendered)


def render_flow_circular_placeholder(
    content: str,
    *,
    max_columns: int = 72,
) -> tuple[str, ...]:
    """Return wrapped Flow Circular raster lines derived only from word lengths."""

    if max_columns < 1:
        raise FlowPlaceholderError("Flow Circular width must be positive.")
    lengths = tuple(len(word) for word in content.split())
    if not lengths:
        raise FlowPlaceholderError("Flow Circular content must be non-empty.")

    lines: list[str] = []
    current: list[str] = []
    current_width = 0
    for word_length in lengths:
        remaining = word_length
        while remaining > 0:
            if current:
                available = max_columns - current_width - 1
                if available < 1:
                    lines.append(" ".join(current))
                    current = []
                    current_width = 0
                    continue
            else:
                available = max_columns

            chunk = min(remaining, available)
            current.append(_render_word(chunk))
            current_width += chunk + (1 if len(current) > 1 else 0)
            remaining -= chunk
            if remaining:
                lines.append(" ".join(current))
                current = []
                current_width = 0

    if current:
        lines.append(" ".join(current))
    return tuple(lines)
