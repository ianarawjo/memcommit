"""Capture the real current-Profile Sever New setup without publishing state."""

from __future__ import annotations

import io
import math
import os
from pathlib import Path
import shlex
import sys
import time

import pexpect
import pyte
from PIL import Image, ImageDraw, ImageFont

ROOT = Path("/Users/KimMunyeong/Github/memcommit")
sys.path.insert(0, str(ROOT / "src"))

OUT = ROOT / "agent-records/docs/screenshots/sever-typed-grant-setup-20260810"
COLS = 180
ROWS = 52
FONT_PATH = "/System/Library/Fonts/Menlo.ttc"
SOURCE = "task-2/advisor1"
CRITERIA = "task-2/advisor2"
UP = "\x1b[A"
DOWN = "\x1b[B"
RIGHT = "\x1b[C"

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


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            # The capture verifies the operation without adding audit records.
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _settle(child: pexpect.spawn, *, seconds: float = 0.35) -> None:
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
    if len(value) == 6 and all(character in "0123456789abcdef" for character in value):
        return "#" + value
    return "#101217" if background else "#e6e9ef"


def _render(raw: str, stem: str) -> None:
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
                    # Menlo Bold omits box-drawing glyphs even though the
                    # terminal renders bold frame chrome with font fallback.
                    font=bold if char.bold and not box_drawing else regular,
                    fill=foreground,
                )
            if char.underscore:
                draw.line(
                    (x, y + cell_height - 3, x + cell_width - 1, y + cell_height - 3),
                    fill=foreground,
                )
    image.save(OUT / f"{stem}.png")


def _plain_screen(raw: str) -> str:
    screen = pyte.Screen(COLS, ROWS)
    pyte.Stream(screen).feed(raw)
    return "\n".join(screen.display)


def _snapshot(recorder: _StreamRecorder, stem: str) -> None:
    _render(recorder.getvalue(), stem)


def _spawn(argv: list[str]) -> tuple[pexpect.spawn, _StreamRecorder]:
    recorder = _StreamRecorder()
    child = pexpect.spawn(
        argv[0],
        argv[1:],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=12,
        dimensions=(ROWS, COLS),
    )
    child.logfile_read = recorder
    return child, recorder


def main() -> None:
    from memcommit.commands.sever.setup_shell import _shared_local_output_name
    from memcommit.sever_store import SeverSessionStore
    from memcommit.store import MemoryStore

    OUT.mkdir(parents=True, exist_ok=True)
    store = MemoryStore(create=False)
    current_before = store.current_context_name()
    sessions_before = len(SeverSessionStore(store).list())
    local_names = tuple(store.list_context_names())
    output_name = _shared_local_output_name(
        SOURCE,
        CRITERIA,
        local_names=local_names,
        occupied_names=frozenset(local_names),
    )
    output_existed_before = store.context_exists(output_name)

    command = [
        "/bin/zsh",
        "-f",
        "-c",
        "stty size; exec mem sever",
    ]
    child, recorder = _spawn(command)
    try:
        child.expect("Add new Sever session")
        _settle(child)
        _snapshot(recorder, "01-saved-session-launcher")

        child.send("n")
        child.expect("MEM SEVER · SETUP · SOURCE UNCHANGED")
        _settle(child)
        _snapshot(recorder, "02-new-setup-current")

        child.send(UP * 8 + RIGHT + DOWN * 3 + "\r")
        _settle(child, seconds=0.8)
        _snapshot(recorder, "03-source-read-grant-selected")
        assert f"SOURCE {SOURCE}" in _plain_screen(recorder.getvalue())

        child.send(UP * 8 + RIGHT + DOWN * 4 + "\r")
        _settle(child, seconds=0.8)
        _snapshot(recorder, "04-criteria-read-grant-selected")
        assert f"CRITERIA {CRITERIA}" in _plain_screen(recorder.getvalue())

        child.send("\x1b")
        child.expect("Sever setup cancelled. No session created.")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "05-cancel-receipt")
    finally:
        if child.isalive():
            child.close(force=True)

    current_after = store.current_context_name()
    sessions_after = len(SeverSessionStore(store).list())
    output_exists_after = store.context_exists(output_name)
    assert current_after == current_before
    assert sessions_after == sessions_before
    assert output_exists_after == output_existed_before

    verification = (
        "stty size; "
        "print -r -- 'READ-ONLY VERIFICATION · NO NEW SEVER STATE'; "
        "mem profile current; "
        "mem status; "
        "print -r -- 'SAVED SEVER SESSIONS · NON-TTY SNAPSHOT'; "
        "mem sever --sessions </dev/null; "
        f"print -r -- {shlex.quote('EXPECTED ABSENT OUTPUT · ' + output_name)}; "
        f"mem show --context {shlex.quote(output_name)} </dev/null || true"
    )
    verify_child, verify_recorder = _spawn(
        ["/bin/zsh", "-f", "-c", verification]
    )
    verify_child.expect(pexpect.EOF)
    _snapshot(verify_recorder, "06-read-only-verification")

    print(f"profile_current={current_before}")
    print(f"sessions_before={sessions_before}")
    print(f"sessions_after={sessions_after}")
    print(f"output_name={output_name}")
    print(f"output_existed_before={output_existed_before}")
    print(f"output_exists_after={output_exists_after}")


if __name__ == "__main__":
    main()
