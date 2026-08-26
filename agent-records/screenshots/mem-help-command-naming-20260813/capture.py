"""Capture canonical List spelling and Git-style Checkout Help wording."""

from __future__ import annotations

import io
import math
import os
from pathlib import Path
import re
import shlex
import shutil
import time

import pexpect
import pyte
from PIL import Image, ImageDraw, ImageFont
from prompt_toolkit.utils import get_cwidth


ROOT = Path("/Users/KimMunyeong/Github/memcommit")
OUT = ROOT / "agent-records/screenshots/mem-help-command-naming-20260813"
COLUMNS = 180
ROWS = 52
FONT_PATH = "/System/Library/Fonts/Menlo.ttc"
WIDE_FONT_PATH = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
HAN_FONT_PATH = "/System/Library/Fonts/Hiragino Sans GB.ttc"

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


class _Recorder(io.StringIO):
    def flush(self) -> None:
        return


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PYTHONPATH": str(ROOT / "src"),
            # Help is read-only; suppress its otherwise unrelated attempt log.
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _color(value: str, *, background: bool = False) -> str:
    if value in _NAMED_COLORS:
        if value == "default" and background:
            return "#101217"
        return _NAMED_COLORS[value]
    if len(value) == 6 and all(character in "0123456789abcdef" for character in value):
        return "#" + value
    return "#101217" if background else "#e6e9ef"


def _screen(raw: str) -> pyte.Screen:
    screen = pyte.Screen(COLUMNS, ROWS)
    pyte.Stream(screen).feed(raw)
    return screen


def _plain(raw: str) -> str:
    return "\n".join(_screen(raw).display).rstrip() + "\n"


def _snapshot(recorder: _Recorder, stem: str) -> str:
    raw = recorder.getvalue()
    screen = _screen(raw)
    plain = "\n".join(screen.display).rstrip() + "\n"
    (OUT / f"{stem}.typescript").write_text(raw, encoding="utf-8")
    (OUT / f"{stem}.txt").write_text(plain, encoding="utf-8")

    regular = ImageFont.truetype(FONT_PATH, 16, index=0)
    bold = ImageFont.truetype(FONT_PATH, 16, index=1)
    # Menlo renders CJK glyphs as empty boxes. The real PTY stream is correct,
    # so use a macOS CJK fallback only for double-cell characters when turning
    # that stream into a PNG. Terminal placement still comes from pyte.
    wide_regular = ImageFont.truetype(WIDE_FONT_PATH, 16, index=0)
    wide_bold = ImageFont.truetype(WIDE_FONT_PATH, 16, index=6)
    han_regular = ImageFont.truetype(HAN_FONT_PATH, 16, index=0)
    han_bold = ImageFont.truetype(HAN_FONT_PATH, 16, index=2)
    cell_width = math.ceil(regular.getlength("M"))
    cell_height = 21
    margin = 16
    image = Image.new(
        "RGB",
        (margin * 2 + COLUMNS * cell_width, margin * 2 + ROWS * cell_height),
        "#101217",
    )
    draw = ImageDraw.Draw(image)
    # Paint the complete terminal background before any glyphs. A wide CJK
    # glyph is stored in its leading pyte cell but spans the following cell;
    # painting that following cell afterward would erase half of the glyph
    # whenever an ANSI background such as Help's zebra band is active.
    for row in range(ROWS):
        for column in range(COLUMNS):
            character = screen.buffer[row][column]
            foreground = _color(character.fg)
            background = _color(character.bg, background=True)
            if character.reverse:
                foreground, background = background, foreground
            x = margin + column * cell_width
            y = margin + row * cell_height
            if background != "#101217":
                draw.rectangle(
                    (x, y, x + cell_width - 1, y + cell_height - 1),
                    fill=background,
                )

    for row in range(ROWS):
        for column in range(COLUMNS):
            character = screen.buffer[row][column]
            foreground = _color(character.fg)
            background = _color(character.bg, background=True)
            if character.reverse:
                foreground, background = background, foreground
            x = margin + column * cell_width
            y = margin + row * cell_height
            if character.data and character.data != " ":
                box_drawing = "\u2500" <= character.data <= "\u257f"
                if any("\u3400" <= value <= "\u9fff" for value in character.data):
                    font = han_bold if character.bold else han_regular
                elif get_cwidth(character.data) > 1:
                    font = wide_bold if character.bold else wide_regular
                else:
                    font = bold if character.bold and not box_drawing else regular
                draw.text(
                    (x, y),
                    character.data,
                    font=font,
                    fill=foreground,
                )
            if character.underscore:
                draw.line(
                    (
                        x,
                        y + cell_height - 3,
                        x + cell_width - 1,
                        y + cell_height - 3,
                    ),
                    fill=foreground,
                )
    image.save(OUT / f"{stem}.png")
    return plain


def _pump(child: pexpect.spawn, *, seconds: float = 0.55) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            child.read_nonblocking(65_536, timeout=0.05)
        except pexpect.TIMEOUT:
            pass
        except pexpect.EOF:
            return


def _spawn(executable: str, *, interactive: bool) -> tuple[pexpect.spawn, _Recorder]:
    argv = shlex.join([executable, "help"])
    if not interactive:
        argv += " </dev/null | rg '^(branch|checkout|list|ls|switch) '"
    command = f"stty rows {ROWS} cols {COLUMNS}; stty size; exec {argv}"
    recorder = _Recorder()
    child = pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=10,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _assert_color(raw: str) -> None:
    assert "52 180" in raw
    assert re.search(r"\x1b\[[0-9;]*38;(?:2|5);", raw) is not None
    assert re.search(r"\x1b\[[0-9;]*48;(?:2|5);", raw) is not None


def main() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    OUT.mkdir(parents=True, exist_ok=True)

    child, recorder = _spawn(executable, interactive=True)
    _pump(child, seconds=0.8)
    entry = _snapshot(recorder, "01-by-kind-entry")
    assert "▸ mem list (ls)" in entry
    assert "▸ mem ls " not in entry
    assert "Switch Contexts using Git-style syntax" in entry

    child.send("\x1b[B\x1b[B\x1b[C")
    _pump(child)
    list_forms = _snapshot(recorder, "02-list-exact-spelling")
    assert "▾ mem list (ls)" in list_forms
    assert "FORM 1 · mem list" in list_forms

    child.send("\x1b[D\x1b[B\x1b[B\x1b[B\x1b[C")
    _pump(child)
    checkout_forms = _snapshot(recorder, "03-checkout-git-style-routes")
    assert "▾ mem checkout" in checkout_forms
    assert "FORM 2 · mem checkout [context]" in checkout_forms
    assert "FORM 3 · mem checkout -b" in checkout_forms
    _assert_color(recorder.getvalue())

    child.send("q")
    child.expect(pexpect.EOF, timeout=5)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)

    verify_child, verify_recorder = _spawn(executable, interactive=False)
    verify_child.expect(pexpect.EOF, timeout=10)
    verify_child.close()
    assert verify_child.exitstatus == 0, (
        verify_child.exitstatus,
        verify_child.signalstatus,
    )
    verification = _snapshot(verify_recorder, "04-plain-read-only-verification")
    assert "list (ls)" in verification
    assert not any(line.startswith("ls ") for line in verification.splitlines())
    assert "Git-style syntax" in verification
    assert "Alias for switch" not in verification


if __name__ == "__main__":
    main()
