"""Capture CPR-safe Study input across init-study, init, and profile."""

from __future__ import annotations

import io
import math
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

import pexpect
import pyte
from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/Users/KimMunyeong/Github/memcommit")
OUT = ROOT / "agent-records/docs/screenshots/study-cpr-input-20260810"
COLS = 180
ROWS = 52
FONT_PATH = "/System/Library/Fonts/Menlo.ttc"
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


class _StreamRecorder(io.StringIO):
    """Retain every decoded byte that pexpect reads from one real PTY."""

    def flush(self) -> None:
        return


def _environment(home: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.pop("MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG", None)
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


def _snapshot(recorder: _StreamRecorder, stem: str) -> None:
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


def _spawn(home: Path, *args: str) -> tuple[pexpect.spawn, _StreamRecorder]:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    command = f"stty rows {ROWS} cols {COLS}; stty size; exec {shlex.join([executable, *args])}"
    recorder = _StreamRecorder()
    child = pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
        cwd=str(ROOT),
        env=_environment(home),
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(ROWS, COLS),
    )
    child.logfile_read = recorder
    child._mem_cpr_responses = 0
    return child, recorder


def _pump(
    child: pexpect.spawn,
    recorder: _StreamRecorder,
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
        assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)


def _assert_clean_terminal(raw: str, *, expect_cpr: bool) -> None:
    assert "Unhandled exception" not in raw
    assert "Study action key is invalid" not in raw
    assert "doesn't support cursor position requests" not in raw
    assert (CPR_REQUEST in raw) is expect_cpr
    assert re.search(r"\x1b\[[0-9;]*m", raw) is not None


def _run(home: Path, *args: str) -> str:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    result = subprocess.run(
        [executable, *args],
        cwd=ROOT,
        env=_environment(home),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout + result.stderr


def _capture_read_only(
    home: Path,
    args: tuple[str, ...],
    *,
    stem: str,
    expected: tuple[str, ...],
) -> None:
    child, recorder = _spawn(home, *args)
    _pump(child, recorder, seconds=20, require_eof=True)
    raw = recorder.getvalue()
    assert all(value in raw for value in expected)
    assert "Unhandled exception" not in raw
    _snapshot(recorder, stem)


def main() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from memcommit.eval.study_bundle import build_all_study_bundles

    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-cpr-capture-") as temporary:
        capture_root = Path(temporary)
        home = capture_root / "home"
        home.mkdir()
        bundles = capture_root / "bundles"
        build_all_study_bundles(bundles)
        _run(home, "init", "capture-authoring-seed")
        _run(home, "profile", "import-study", "--from", str(bundles))
        _run(home, "init-study", "cpr-seed-study")

        child, recorder = _spawn(home, "init-study")
        _pump(child, recorder, seconds=0.8)
        assert "STUDY NAME" in recorder.getvalue()
        _snapshot(recorder, "01-init-study-name-entry")
        child.send("\x15cpr-verified-study")
        _pump(child, recorder, seconds=0.5)
        _snapshot(recorder, "02-init-study-name-edited")
        child.send("\r")
        _pump(child, recorder, seconds=30, require_eof=True)
        raw = recorder.getvalue()
        assert "Initialized Study run 'cpr-verified-study'." in raw
        _assert_clean_terminal(raw, expect_cpr=True)
        _snapshot(recorder, "03-init-study-success")

        child, recorder = _spawn(home, "init")
        _pump(child, recorder, seconds=0.8)
        assert "NEW CONTEXT NAME" in recorder.getvalue()
        _snapshot(recorder, "04-init-name-entry")
        child.send("\x15cpr-init-context")
        _pump(child, recorder, seconds=0.5)
        _snapshot(recorder, "05-init-name-edited")
        child.send("\r")
        _pump(child, recorder, seconds=20, require_eof=True)
        raw = recorder.getvalue()
        assert "Initialized context 'cpr-init-context'." in raw
        _assert_clean_terminal(raw, expect_cpr=True)
        _snapshot(recorder, "06-init-success")

        child, recorder = _spawn(home, "profile")
        _pump(child, recorder, seconds=3)
        assert "Select a Profile" in recorder.getvalue()
        _snapshot(recorder, "07-profile-picker")
        child.send("\x1b")
        _pump(child, recorder, seconds=20, require_eof=True)
        raw = recorder.getvalue()
        assert "Profile selection cancelled." in raw
        _assert_clean_terminal(raw, expect_cpr=False)
        _snapshot(recorder, "08-profile-cancelled")

        _capture_read_only(
            home,
            ("profile", "list"),
            stem="09-profile-list-verification",
            expected=("cpr-verified-study", "current=cpr-init-context"),
        )
        _capture_read_only(
            home,
            ("log", "--actions", "--limit", "100"),
            stem="10-study-action-log-verification",
            expected=("Study actions", "COMMAND_FINISHED", "operation=init"),
        )
        action_text = (OUT / "10-study-action-log-verification.typescript").read_text(
            encoding="utf-8"
        )
        assert "<cursor-position-response>" not in action_text


if __name__ == "__main__":
    main()
