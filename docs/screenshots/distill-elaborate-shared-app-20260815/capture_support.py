"""Color-preserving PTY snapshot helpers for this evidence set."""

from __future__ import annotations

import io
import math
from pathlib import Path
import time

import pexpect
import pyte
from PIL import Image, ImageDraw, ImageFont


FONT_PATH = "/System/Library/Fonts/Menlo.ttc"

_NAMED_COLORS = {
    "default": "#e6e9ef",
    "black": "#101217",
    "red": "#ed8796",
    "green": "#a6da95",
    "brown": "#eed49f",
    "yellow": "#eed49f",
    "blue": "#8aadf4",
    "magenta": "#c6a0f6",
    "cyan": "#8bd5ca",
    "white": "#cad3f5",
    "brightblack": "#5b6078",
    "brightred": "#ed8796",
    "brightgreen": "#a6da95",
    "brightyellow": "#f5a97f",
    "brightblue": "#8aadf4",
    "brightmagenta": "#c6a0f6",
    "brightcyan": "#91d7e3",
    "brightwhite": "#f4dbd6",
}


class StreamRecorder(io.StringIO):
    """Keep the complete prompt-toolkit PTY stream between snapshots."""

    def flush(self) -> None:
        return


def settle(child: pexpect.spawn, *, seconds: float = 0.5) -> None:
    """Drain repaint bytes until one stable screenshot boundary."""

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            child.read_nonblocking(size=65_536, timeout=0.05)
        except pexpect.TIMEOUT:
            continue
        except pexpect.EOF:
            return


def _color(value: str, *, background: bool = False) -> str:
    if value in _NAMED_COLORS:
        if value == "default" and background:
            return "#101217"
        return _NAMED_COLORS[value]
    if len(value) == 6 and all(char in "0123456789abcdef" for char in value):
        return "#" + value
    return "#101217" if background else "#e6e9ef"


def snapshot(
    recorder: io.StringIO,
    stem: str,
    *,
    out: Path,
    columns: int,
    rows: int,
) -> None:
    """Write one raw stream, extracted terminal canvas, and PNG rendering."""

    raw = recorder.getvalue()
    screen = pyte.Screen(columns, rows)
    pyte.Stream(screen).feed(raw)
    plain = "\n".join(screen.display).rstrip() + "\n"
    (out / f"{stem}.typescript").write_text(raw, encoding="utf-8")
    (out / f"{stem}.txt").write_text(plain, encoding="utf-8")

    regular = ImageFont.truetype(FONT_PATH, 16, index=0)
    bold = ImageFont.truetype(FONT_PATH, 16, index=1)
    cell_width = math.ceil(regular.getlength("M"))
    cell_height = 21
    margin = 16
    image = Image.new(
        "RGB",
        (margin * 2 + columns * cell_width, margin * 2 + rows * cell_height),
        "#101217",
    )
    draw = ImageDraw.Draw(image)
    for row in range(rows):
        for column in range(columns):
            char = screen.buffer[row][column]
            foreground = _color(char.fg)
            background = _color(char.bg, background=True)
            if char.reverse:
                foreground, background = background, foreground
            x = margin + column * cell_width
            y = margin + row * cell_height
            if background != "#101217":
                draw.rectangle(
                    (x, y, x + cell_width - 1, y + cell_height - 1),
                    fill=background,
                )
            if char.data and char.data != " ":
                box_drawing = "\u2500" <= char.data <= "\u257f"
                draw.text(
                    (x, y),
                    char.data,
                    font=bold if char.bold and not box_drawing else regular,
                    fill=foreground,
                )
            if char.underscore:
                draw.line(
                    (
                        x,
                        y + cell_height - 3,
                        x + cell_width - 1,
                        y + cell_height - 3,
                    ),
                    fill=foreground,
                )
    image.save(out / f"{stem}.png")
