"""Capture a real init-study replay in a color-capable 180×52 PTY."""

from __future__ import annotations

import io
import math
import os
from pathlib import Path
import re
import shlex
import shutil
import sys
import time

import pexpect
import pyte
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLS = 180
ROWS = 52
FONT_PATH = "/System/Library/Fonts/Menlo.ttc"
PROFILE_NAME = "study-snapshot-replay-20260811"
CPR_REQUEST = "\x1b[6n"
CPR_RESPONSE = "\x1b[1;1R"

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
    environment.pop("MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PROMPT_TOOLKIT_COLOR_DEPTH": "DEPTH_24_BIT",
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


def _snapshot(recorder: _Recorder, stem: str) -> None:
    raw = recorder.getvalue()
    screen = pyte.Screen(COLS, ROWS)
    pyte.Stream(screen).feed(raw)
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
        (margin * 2 + COLS * cell_width, margin * 2 + ROWS * cell_height),
        "#101217",
    )
    draw = ImageDraw.Draw(image)
    for row in range(ROWS):
        for column in range(COLS):
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
            if character.data and character.data != " ":
                box_drawing = "\u2500" <= character.data <= "\u257f"
                draw.text(
                    (x, y),
                    character.data,
                    font=bold if character.bold and not box_drawing else regular,
                    fill=foreground,
                )
            if character.underscore:
                draw.line(
                    (x, y + cell_height - 3, x + cell_width - 1, y + cell_height - 3),
                    fill=foreground,
                )
    image.save(OUT / f"{stem}.png")


def _visible_text(recorder: _Recorder) -> str:
    screen = pyte.Screen(COLS, ROWS)
    pyte.Stream(screen).feed(recorder.getvalue())
    return "\n".join(screen.display)


def _spawn(*args: str) -> tuple[pexpect.spawn, _Recorder]:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    command = (
        f"stty rows {ROWS} cols {COLS}; stty size; "
        f"exec {shlex.join([executable, *args])}"
    )
    recorder = _Recorder()
    child = pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=30,
        dimensions=(ROWS, COLS),
    )
    child.logfile_read = recorder
    child._mem_cpr_responses = 0
    return child, recorder


def _pump(
    child: pexpect.spawn,
    recorder: _Recorder,
    *,
    seconds: float,
    require_eof: bool = False,
) -> None:
    deadline = time.monotonic() + seconds
    reached_eof = False
    while time.monotonic() < deadline:
        try:
            child.read_nonblocking(size=65_536, timeout=0.05)
        except pexpect.TIMEOUT:
            pass
        except pexpect.EOF:
            reached_eof = True
            break
        query_count = recorder.getvalue().count(CPR_REQUEST)
        while child._mem_cpr_responses < query_count:
            child.send(CPR_RESPONSE)
            child._mem_cpr_responses += 1
    if require_eof and not reached_eof:
        child.expect(pexpect.EOF, timeout=max(0.1, seconds))
    if reached_eof or require_eof:
        child.close()
        if child.exitstatus != 0:
            raise RuntimeError(
                f"PTY command failed: exit={child.exitstatus} signal={child.signalstatus}"
            )


def _capture_read_only(
    args: tuple[str, ...], *, stem: str, expected: tuple[str, ...]
) -> None:
    child, recorder = _spawn(*args)
    _pump(child, recorder, seconds=30, require_eof=True)
    raw = recorder.getvalue()
    if not all(value in raw for value in expected):
        raise RuntimeError(f"Read-only capture {stem} missed expected output.")
    _snapshot(recorder, stem)


def main() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from memcommit.application.operations.profile.config import load_profile_registry

    OUT.mkdir(parents=True, exist_ok=True)
    registry = load_profile_registry()
    existing = next(
        (profile for profile in registry.profiles if profile.name == PROFILE_NAME),
        None,
    )
    if existing is not None:
        if registry.active.uid != existing.uid:
            raise RuntimeError(
                f"Profile {PROFILE_NAME!r} exists but is not the active Profile."
            )
    else:
        child, recorder = _spawn("init-study")
        _pump(child, recorder, seconds=0.8)
        raw = recorder.getvalue()
        if "STUDY NAME" not in raw or "52 180" not in raw:
            raise RuntimeError("init-study did not open at the required PTY size.")
        _snapshot(recorder, "01-init-study-name-entry")

        child.send("\x15" + PROFILE_NAME)
        _pump(child, recorder, seconds=0.5)
        if PROFILE_NAME not in _visible_text(recorder):
            raise RuntimeError("Edited Study name was not rendered.")
        _snapshot(recorder, "02-init-study-name-edited")

        child.send("\r")
        _pump(child, recorder, seconds=45, require_eof=True)
        raw = recorder.getvalue()
        required = (
            f"Initialized Study run '{PROFILE_NAME}'.",
            "Declared Compare prewarms 6 installed.",
            "Declared Tutorial Atomize prewarms 1 installed.",
            "Declared Task 1 Update prewarms 1 installed.",
            "Declared Task 3 Sever prewarms 1 installed.",
            "Declared Task 1 Directional Meld prewarms 1 installed.",
            f"Active Profile: {PROFILE_NAME}",
        )
        if not all(value in raw for value in required):
            raise RuntimeError("init-study success receipt was incomplete.")
        if "Unhandled exception" in raw or "Traceback" in raw:
            raise RuntimeError("init-study emitted an unexpected exception.")
        if re.search(r"\x1b\[[0-9;:]*m", raw) is None:
            raise RuntimeError("PTY stream did not contain ANSI styling.")
        _snapshot(recorder, "03-init-study-success")

    _capture_read_only(
        ("profile", "current"),
        stem="04-active-profile-status",
        expected=(
            PROFILE_NAME,
            "task-1/participant/construction-updates",
        ),
    )
    _capture_read_only(
        ("log", "--actions", "--limit", "20"),
        stem="05-init-study-action-log",
        expected=("Study actions", "STUDY_CREATED", "PROFILE_ENTERED"),
    )


if __name__ == "__main__":
    main()
