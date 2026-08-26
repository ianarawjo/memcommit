"""Capture shared endpoint and Sever Memory previews in a real color PTY."""

from __future__ import annotations

import io
import math
import os
from pathlib import Path
import sys
import time

import pexpect
import pyte
from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/Users/KimMunyeong/Github/memcommit")
OUT = ROOT / "docs/screenshots/context-endpoint-memory-preview-20260810"
COLUMNS = 180
ROWS = 52
FONT_PATH = "/System/Library/Fonts/Menlo.ttc"
HANGUL_FONT_PATH: str | None = None
DOWN = "\x1b[B"

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


class _StreamRecorder(io.StringIO):
    def flush(self) -> None:
        return


def _memory_rows(name: str):
    from memcommit.commands.shared.context_picker import ContextMemoryRow

    rows = {
        "alpha": (
            ContextMemoryRow(
                "memory aaaaaaaa",
                "Alpha keeps the participant's exact source statement visible before execution.",
            ),
            ContextMemoryRow(
                "memory bbbbbbbb",
                "A second Alpha Memory proves Up and Down traverse individual preview rows.",
            ),
        ),
        "beta": (
            ContextMemoryRow(
                "memory cccccccc",
                "Beta is a separate readable peer revealed by uppercase M.",
            ),
        ),
    }
    return rows[name]


def _run_common_child() -> None:
    from memcommit.commands.shared.session_endpoint_setup import (
        EndpointModeSpec,
        EndpointRoleSpec,
        choose_session_endpoints,
    )

    print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
    receipt = choose_session_endpoints(
        ("alpha", "beta"),
        title="NEW UPDATE · A → B",
        modes=(
            EndpointModeSpec(
                "UPDATE",
                "A → B",
                ("A", "B"),
                {"A": "A · SOURCE", "B": "B · TARGET"},
                descendant_roles=frozenset({"A", "B"}),
            ),
        ),
        roles=(
            EndpointRoleSpec(
                "A", frozenset({"alpha", "beta"}), "alpha", allow_descendants=True
            ),
            EndpointRoleSpec(
                "B", frozenset({"alpha", "beta"}), "beta", allow_descendants=True
            ),
        ),
        initial_mode_uid="UPDATE",
        memory_loader=_memory_rows,
    )
    print(
        "COMMON ENDPOINT CANCELLED · NO RECEIPT · NO STORE · NO PROVIDER"
        if receipt is None
        else f"UNEXPECTED RECEIPT {receipt!r}"
    )


def _run_sever_child() -> None:
    from memcommit.commands.sever.setup_shell import choose_sever_setup

    print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
    receipt = choose_sever_setup(
        ("alpha", "beta"),
        current="alpha",
        memory_loader=_memory_rows,
    )
    print(
        "SEVER SETUP CANCELLED · NO RECEIPT · NO STORE · NO PROVIDER"
        if receipt is None
        else f"UNEXPECTED RECEIPT {receipt!r}"
    )


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update({"TERM": "xterm-256color", "COLORTERM": "truecolor"})
    return environment


def _settle(child: pexpect.spawn, *, seconds: float = 0.45) -> None:
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


def _render(raw: str, stem: str) -> None:
    screen = pyte.Screen(COLUMNS, ROWS)
    pyte.Stream(screen).feed(raw)
    plain = "\n".join(screen.display).rstrip() + "\n"
    (OUT / f"{stem}.typescript").write_text(raw, encoding="utf-8")
    (OUT / f"{stem}.txt").write_text(plain, encoding="utf-8")

    regular = ImageFont.truetype(FONT_PATH, 16, index=0)
    bold = ImageFont.truetype(FONT_PATH, 16, index=1)
    hangul_regular = (
        ImageFont.truetype(HANGUL_FONT_PATH, 16, index=0)
        if HANGUL_FONT_PATH is not None
        else None
    )
    hangul_bold = (
        ImageFont.truetype(HANGUL_FONT_PATH, 16, index=2)
        if HANGUL_FONT_PATH is not None
        else None
    )
    cell_width = math.ceil(regular.getlength("M"))
    cell_height = 21
    margin = 16
    image = Image.new(
        "RGB",
        (margin * 2 + COLUMNS * cell_width, margin * 2 + ROWS * cell_height),
        "#101217",
    )
    draw = ImageDraw.Draw(image)
    for row in range(ROWS):
        for column in range(COLUMNS):
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
                contains_hangul = any(
                    "\u1100" <= value <= "\u11ff"
                    or "\u3130" <= value <= "\u318f"
                    or "\uac00" <= value <= "\ud7af"
                    for value in char.data
                )
                selected_font = bold if char.bold and not box_drawing else regular
                if contains_hangul and hangul_regular is not None:
                    # The terminal still owns cell width; this only supplies
                    # glyphs that the monospaced Latin font does not contain.
                    selected_font = (
                        hangul_bold
                        if char.bold and hangul_bold is not None
                        else hangul_regular
                    )
                draw.text(
                    (x, y),
                    char.data,
                    font=selected_font,
                    fill=foreground,
                )
            if char.underscore:
                draw.line(
                    (x, y + cell_height - 3, x + cell_width - 1, y + cell_height - 3),
                    fill=foreground,
                )
    image.save(OUT / f"{stem}.png")


def _snapshot(recorder: _StreamRecorder, stem: str) -> None:
    _render(recorder.getvalue(), stem)


def _spawn(kind: str) -> tuple[pexpect.spawn, _StreamRecorder]:
    recorder = _StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=12,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _capture_common() -> None:
    child, recorder = _spawn("common")
    try:
        child.expect("NEW UPDATE")
        _settle(child)
        _snapshot(recorder, "01-common-entry")

        child.send("m")
        _settle(child)
        _snapshot(recorder, "02-common-memory-here")

        child.send(DOWN)
        _settle(child)
        _snapshot(recorder, "03-common-memory-focus")

        child.send("M")
        _settle(child)
        _snapshot(recorder, "04-common-memories-all")

        child.send("q")
        child.expect("COMMON ENDPOINT CANCELLED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "05-common-cancel-receipt")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_sever() -> None:
    child, recorder = _spawn("sever")
    try:
        child.expect("MEM SEVER · SETUP")
        _settle(child)
        _snapshot(recorder, "06-sever-entry")

        child.send("m")
        _settle(child)
        _snapshot(recorder, "07-sever-memory-here")

        child.send(DOWN)
        _settle(child)
        _snapshot(recorder, "08-sever-memory-focus")

        child.send("M")
        _settle(child)
        _snapshot(recorder, "09-sever-memories-all")

        child.send("q")
        child.expect("SEVER SETUP CANCELLED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "10-sever-cancel-receipt")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _capture_common()
    _capture_sever()
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "38;5" in raw
    assert "48;5" in raw


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT / "src"))
        if sys.argv[2] == "common":
            _run_common_child()
        elif sys.argv[2] == "sever":
            _run_sever_child()
        else:
            raise SystemExit(f"unknown child kind: {sys.argv[2]}")
    else:
        main()
