"""Capture BY KIND Tab traversal and the aligned A–Z bottom boundary."""

from __future__ import annotations

import io
import math
import os
from pathlib import Path
import re
import shlex
import shutil
import tempfile
import time

import pexpect
import pyte
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/screenshots/mem-help-a-z-boundary-20260813"
COLS = 180
ROWS = 52
TALL_ROWS = 86
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


class _StreamRecorder(io.StringIO):
    def flush(self) -> None:
        return


def _environment(home: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "HOME": str(home),
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PYTHONPATH": str(ROOT / "src"),
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


def _screen(raw: str, *, rows: int = ROWS) -> pyte.Screen:
    screen = pyte.Screen(COLS, rows)
    pyte.Stream(screen).feed(raw)
    return screen


def _snapshot(recorder: _StreamRecorder, stem: str, *, rows: int = ROWS) -> None:
    raw = recorder.getvalue()
    screen = _screen(raw, rows=rows)
    plain = "\n".join(screen.display).rstrip() + "\n"
    (OUT / f"{stem}.typescript").write_text(raw, encoding="utf-8")
    (OUT / f"{stem}.txt").write_text(plain, encoding="utf-8")

    regular = ImageFont.truetype(FONT_PATH, 16, index=0)
    bold = ImageFont.truetype(FONT_PATH, 16, index=1)
    cell_width = math.ceil(regular.getlength("M"))
    cell_height = 21
    margin = 16
    image = Image.new(
        "RGB",
        (margin * 2 + COLS * cell_width, margin * 2 + rows * cell_height),
        "#101217",
    )
    draw = ImageDraw.Draw(image)
    for row in range(rows):
        for column in range(COLS):
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
                    (x, y + cell_height - 3, x + cell_width - 1, y + cell_height - 3),
                    fill=foreground,
                )
    image.save(OUT / f"{stem}.png")


def _pump(child: pexpect.spawn, *, seconds: float = 0.5) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            child.read_nonblocking(65_536, timeout=0.05)
        except pexpect.TIMEOUT:
            pass
        except pexpect.EOF:
            return


def _wait_for_visible(
    child: pexpect.spawn,
    recorder: _StreamRecorder,
    expected: str,
    *,
    rows: int = ROWS,
    seconds: float = 8.0,
) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        _pump(child, seconds=0.1)
        if expected in "\n".join(_screen(recorder.getvalue(), rows=rows).display):
            return
    raise RuntimeError(f"Help capture did not render expected text: {expected}")


def _assert_a_z_boundary(raw: str) -> None:
    screen = _screen(raw)
    # Switching projections retains the selected command, so the visible A–Z
    # slice need not start at `add`; every command row shares this right edge.
    command_row = next(
        line for line in screen.display if "▸ mem " in line and line[COLS - 1] == " "
    )
    bottom_rule = next(line for line in screen.display if line.startswith("─" * 40))
    assert command_row[COLS - 2] in {"│", "┃"}
    assert command_row[COLS - 1] == " "
    assert len(bottom_rule.rstrip()) == COLS - 1
    assert bottom_rule[COLS - 1] == " "


def _assert_tall_a_z_fill(raw: str) -> None:
    screen = _screen(raw, rows=TALL_ROWS)
    update_row = next(
        index for index, line in enumerate(screen.display) if "▸ mem update" in line
    )
    box_bottom = next(
        index
        for index, line in enumerate(screen.display)
        if line.startswith(("└", "┗")) and line[COLS - 2] in {"┘", "┛"}
    )
    bottom_rule = next(
        index for index, line in enumerate(screen.display) if line.startswith("─" * 40)
    )
    blank_rows = screen.display[update_row + 1 : box_bottom]

    assert blank_rows
    assert all(
        line[0] in {"│", "┃"}
        and line[COLS - 2] in {"│", "┃"}
        and not line[1 : COLS - 2].strip()
        for line in blank_rows
    )
    assert box_bottom + 1 == bottom_rule


def main() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mem-help-capture-") as temporary_home:
        command = (
            f"stty rows {ROWS} cols {COLS}; stty size; "
            f"exec {shlex.join([executable, 'help'])}"
        )
        recorder = _StreamRecorder()
        child = pexpect.spawn(
            "/bin/zsh",
            ["-f", "-c", command],
            cwd=str(ROOT),
            env=_environment(Path(temporary_home)),
            encoding="utf-8",
            codec_errors="replace",
            timeout=10,
            dimensions=(ROWS, COLS),
        )
        child.logfile_read = recorder

        _wait_for_visible(child, recorder, "CORE CONCEPTS")
        _snapshot(recorder, "01-by-kind-entry")
        tab_stops = (
            ("02-memories-focused", "MEMORIES"),
            ("03-search-explain-focused", "SEARCH & EXPLAIN"),
            ("04-analyze-transform-focused", "ANALYZE & TRANSFORM"),
            ("05-history-recovery-focused", "HISTORY & RECOVERY"),
            ("06-ground-evaluation-focused", "GROUND & EVALUATION"),
            ("07-profile-sharing-focused", "PROFILE & SHARING"),
            ("08-system-focused", "SYSTEM"),
        )
        for stem, title in tab_stops:
            child.send("\t")
            _wait_for_visible(child, recorder, f"┏ {title} ")
            _snapshot(recorder, stem)
        child.send("\t")
        _wait_for_visible(child, recorder, "› VIEW")
        _snapshot(recorder, "09-view-focused")
        child.send("\x1b[C")
        _wait_for_visible(child, recorder, "┌ A–Z")
        _snapshot(recorder, "10-a-z-selected")
        child.send("\t")
        _pump(child)
        _snapshot(recorder, "11-a-z-list-boundary")

        raw = recorder.getvalue()
        assert "52 180" in raw
        assert re.search(r"\x1b\[[0-9;]*38;(?:2|5);", raw) is not None
        assert re.search(r"\x1b\[[0-9;]*48;(?:2|5);", raw) is not None
        assert " A–Z " in "\n".join(_screen(raw).display)
        _assert_a_z_boundary(raw)

        child.send("q")
        child.expect(pexpect.EOF, timeout=5)
        child.close()
        assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)

        tall_command = (
            f"stty rows {TALL_ROWS} cols {COLS}; stty size; "
            f"exec {shlex.join([executable, 'help'])}"
        )
        tall_recorder = _StreamRecorder()
        tall_child = pexpect.spawn(
            "/bin/zsh",
            ["-f", "-c", tall_command],
            cwd=str(ROOT),
            env=_environment(Path(temporary_home)),
            encoding="utf-8",
            codec_errors="replace",
            timeout=10,
            dimensions=(TALL_ROWS, COLS),
        )
        tall_child.logfile_read = tall_recorder
        _wait_for_visible(
            tall_child,
            tall_recorder,
            "CORE CONCEPTS",
            rows=TALL_ROWS,
        )
        tall_child.send("\t" * 8 + "\x1b[C\t")
        _wait_for_visible(tall_child, tall_recorder, "┏ A–Z", rows=TALL_ROWS)
        _pump(tall_child)
        _snapshot(
            tall_recorder,
            "12-a-z-tall-viewport-fill-180x86",
            rows=TALL_ROWS,
        )
        tall_raw = tall_recorder.getvalue()
        assert f"{TALL_ROWS} {COLS}" in tall_raw
        assert re.search(r"\x1b\[[0-9;]*38;(?:2|5);", tall_raw) is not None
        assert re.search(r"\x1b\[[0-9;]*48;(?:2|5);", tall_raw) is not None
        _assert_tall_a_z_fill(tall_raw)
        tall_child.send("q")
        tall_child.expect(pexpect.EOF, timeout=5)
        tall_child.close()
        assert tall_child.exitstatus == 0, (
            tall_child.exitstatus,
            tall_child.signalstatus,
        )


if __name__ == "__main__":
    main()
