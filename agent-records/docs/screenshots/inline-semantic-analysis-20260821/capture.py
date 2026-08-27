"""Capture inline initial semantic waits and one prior-review replacement wait."""

from __future__ import annotations

import os
from pathlib import Path
import re
import sys
import time


ROWS = 52
COLUMNS = 180
CAPTURE_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


INITIAL_CASES = (
    (
        "01-compare-inline-analysis",
        "COMPARE",
        "connecting provider",
        2,
        (("analyzing relations", 2),),
    ),
    (
        "02-meld-inline-analysis",
        "MELD",
        "connecting provider",
        2,
        (("analyzing meld turn", 2),),
    ),
    (
        "03-update-inline-analysis",
        "UPDATE",
        "connecting provider",
        2,
        (("planning memory changes", 2),),
    ),
    (
        "04-forget-inline-analysis",
        "FORGET",
        "analyzing 2 source memories x 1 instruction",
        1,
        (),
    ),
    (
        "05-sever-inline-analysis",
        "SEVER",
        "freezing source and criteria",
        3,
        (
            ("connecting provider", 2),
            ("analyzing 2 source x 1 criteria", 3),
        ),
    ),
    (
        "06-audit-inline-analysis",
        "AUDIT",
        "finding duplicates",
        3,
        (
            ("finding ambiguities", 2),
            ("finding conflicts", 3),
        ),
    ),
)


def _child() -> None:
    from memcommit.adapters.console.commands.shared.command_wait import CommandWaitView, run_command_wait

    columns, rows = os.get_terminal_size()
    print(f"CAPTURE PTY · {columns}x{rows}", flush=True)
    for _stem, operation, first_stage, total, updates in INITIAL_CASES:
        print(f"CAPTURE READY · {operation} · PRESS ENTER", flush=True)
        input()

        def work(progress, *, frozen_updates=updates, name=operation):
            time.sleep(0.35)
            for stage, step in frozen_updates:
                progress.update(stage, step=step)
                time.sleep(0.35)
            time.sleep(1.8)
            return f"{name} COMPLETE"

        result = run_command_wait(
            operation,
            first_stage,
            total=total,
            work=work,
            interval=0.2,
        )
        print(f"CAPTURE RESULT · {result}", flush=True)
        print("CAPTURE NEXT · PRESS ENTER", flush=True)
        input()

    print("CAPTURE READY · REVIEW REPLACEMENT · PRESS ENTER", flush=True)
    input()

    def revise(progress):
        time.sleep(0.5)
        progress.update("incorporating review comments", step=2)
        time.sleep(4.0)
        return "REVIEW REPLACEMENT COMPLETE"

    revised = run_command_wait(
        "UPDATE",
        "connecting provider",
        total=2,
        work=revise,
        interval=0.2,
        return_view=CommandWaitView(
            title="PREVIOUS UPDATE REPORT · READ-ONLY",
            text=[
                ("class:viewer-section", "STAGED UPDATE · COMPLETE REVIEW\n\n"),
                ("class:viewer-section", "PLAN\n"),
                (
                    "class:report-neutral",
                    "Replace the obsolete entrance claim with verified access "
                    "information.\n\n",
                ),
                ("class:viewer-section", "PLANNED CHANGES\n"),
                (
                    "class:memory-object",
                    "  ~ EDIT · The south entrance provides step-free public "
                    "access.\n\n",
                ),
                (
                    "class:warning",
                    "PENDING REVISION · SUBMITTED · NOT YET INCORPORATED\n",
                ),
                (
                    "class:report-neutral",
                    "Keep the claim limited to public step-free access.",
                ),
            ],
        ),
        context_view=CommandWaitView(
            title="UPDATE CONFIRMED INPUTS · READ-ONLY",
            text="\n".join(
                [
                    "SOURCE A · capture/update/source",
                    "TARGET B · capture/update/target",
                    "",
                    "SUBMITTED COMMENT · NOT YET INCORPORATED",
                    "Keep the claim limited to public step-free access.",
                ]
            ),
        ),
    )
    print(f"CAPTURE RESULT · {revised}", flush=True)
    print("CAPTURE VERIFY · PRESS ENTER", flush=True)
    input()
    print("CAPTURE VERIFICATION · READ-ONLY")
    print("INITIAL OPERATIONS · COMPARE · MELD · UPDATE · FORGET · SEVER · AUDIT")
    print("INITIAL PRESENTATION · ONE TRANSIENT PROGRESS LINE EACH")
    print("INITIAL REPORT-BUILDING SURFACES · NONE")
    print("REVIEW REPLACEMENT · PREVIOUS COMPLETE REPORT RETAINED")
    print("PROVIDER PAYLOADS · SYNTHETIC · DURABLE STATE · UNCHANGED")


def _drain(child, raw: bytearray, *, timeout: float = 0.1) -> bool:
    import pexpect

    try:
        raw.extend(child.read_nonblocking(size=65536, timeout=timeout))
        return True
    except (pexpect.TIMEOUT, pexpect.EOF):
        return False


def _wait_for(child, raw: bytearray, marker: bytes, *, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while marker not in raw:
        if time.monotonic() >= deadline:
            tail = bytes(raw[-8000:]).decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Timed out waiting for {marker!r}. Recent PTY stream:\n{tail}"
            )
        _drain(child, raw)
    time.sleep(0.2)
    while _drain(child, raw, timeout=0.02):
        pass


def _settle(child, raw: bytearray, *, delay: float = 0.3) -> None:
    time.sleep(delay)
    while _drain(child, raw, timeout=0.02):
        pass


def _ansi_color(value: str, default: tuple[int, int, int]) -> tuple[int, int, int]:
    colors = {
        "black": (30, 32, 48),
        "red": (237, 135, 150),
        "green": (166, 218, 149),
        "brown": (238, 212, 159),
        "blue": (138, 173, 244),
        "magenta": (198, 160, 246),
        "cyan": (139, 213, 255),
        "white": (244, 245, 247),
        "brightblack": (91, 96, 120),
        "brightred": (237, 135, 150),
        "brightgreen": (166, 218, 149),
        "brightbrown": (238, 212, 159),
        "brightblue": (138, 173, 244),
        "brightmagenta": (198, 160, 246),
        "brightcyan": (145, 215, 227),
        "brightwhite": (255, 255, 255),
        "default": default,
    }
    if value in colors:
        return colors[value]
    if re.fullmatch(r"[0-9a-fA-F]{6}", value):
        return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))
    return default


def _render_snapshot(name: str, raw: bytes) -> None:
    import pyte
    from PIL import Image, ImageDraw, ImageFont

    screen = pyte.Screen(COLUMNS, ROWS)
    stream = pyte.Stream(screen)
    stream.feed(raw.decode("utf-8", errors="replace"))

    plain = "\n".join(screen.display)
    (CAPTURE_DIR / f"{name}.txt").write_text(plain + "\n", encoding="utf-8")
    (CAPTURE_DIR / f"{name}.typescript").write_bytes(raw)

    font = ImageFont.truetype(
        "/opt/anaconda3/lib/python3.12/site-packages/matplotlib/"
        "mpl-data/fonts/ttf/DejaVuSansMono.ttf",
        18,
    )
    cell_width = 11
    cell_height = 21
    background = (30, 32, 48)
    foreground = (244, 245, 247)
    image = Image.new(
        "RGB",
        (COLUMNS * cell_width, ROWS * cell_height),
        background,
    )
    draw = ImageDraw.Draw(image)
    for row in range(ROWS):
        for column in range(COLUMNS):
            character = screen.buffer[row][column]
            fg = _ansi_color(character.fg, foreground)
            bg = _ansi_color(character.bg, background)
            if character.reverse:
                fg, bg = bg, fg
            x = column * cell_width
            y = row * cell_height
            if bg != background:
                draw.rectangle(
                    (x, y, x + cell_width - 1, y + cell_height - 1),
                    fill=bg,
                )
            if character.data != " ":
                draw.text((x, y - 1), character.data, font=font, fill=fg)
                if character.bold:
                    draw.text((x + 1, y - 1), character.data, font=font, fill=fg)
    image.save(CAPTURE_DIR / f"{name}.png")


def _parent() -> None:
    import pexpect

    environment = dict(os.environ)
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    raw = bytearray()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child"],
        env=environment,
        dimensions=(ROWS, COLUMNS),
        encoding=None,
        timeout=0.1,
    )
    initial_segments: list[bytes] = []
    for stem, operation, first_stage, _total, updates in INITIAL_CASES:
        _wait_for(
            child,
            raw,
            f"CAPTURE READY · {operation}".encode(),
            timeout=5,
        )
        segment_start = len(raw)
        child.send(b"\r")
        visible_stage = updates[-1][0] if updates else first_stage
        marker = visible_stage.upper().encode()
        _wait_for(child, raw, marker, timeout=5)
        _settle(child, raw, delay=0.5)
        _render_snapshot(stem, bytes(raw))
        _wait_for(
            child,
            raw,
            f"CAPTURE RESULT · {operation} COMPLETE".encode(),
            timeout=5,
        )
        initial_segments.append(bytes(raw[segment_start:]))
        child.send(b"\r")

    _wait_for(
        child,
        raw,
        "CAPTURE READY · REVIEW REPLACEMENT".encode(),
        timeout=5,
    )
    review_start = len(raw)
    child.send(b"\r")
    _wait_for(child, raw, b"PENDING REVISION", timeout=5)
    _render_snapshot("07-prior-review-replacement", bytes(raw))

    child.send(b"i")
    _wait_for(child, raw, b"SUBMITTED COMMENT", timeout=3)
    _render_snapshot("08-submitted-review-inputs", bytes(raw))

    child.send(b"i")
    _wait_for(
        child,
        raw,
        "CAPTURE RESULT · REVIEW REPLACEMENT COMPLETE".encode(),
        timeout=7,
    )
    review_segment = bytes(raw[review_start:])
    _render_snapshot("09-review-replacement-result", bytes(raw))

    child.send(b"\r")
    _wait_for(child, raw, "DURABLE STATE · UNCHANGED".encode(), timeout=5)
    deadline = time.monotonic() + 5
    while child.isalive() and time.monotonic() < deadline:
        _drain(child, raw)
    while _drain(child, raw, timeout=0.02):
        pass
    child.close()
    if child.exitstatus not in {0, None}:
        raise RuntimeError(f"Capture child exited with {child.exitstatus}.")
    _render_snapshot("10-read-only-verification", bytes(raw))

    alternate_screen = b"\x1b[?1049h"
    if any(alternate_screen in segment for segment in initial_segments):
        raise RuntimeError("An initial analysis entered a full-screen surface.")
    if alternate_screen not in review_segment:
        raise RuntimeError("The prior-review replacement did not enter its TUI.")
    if "REPORT · BUILDING".encode() in b"".join(initial_segments):
        raise RuntimeError("An initial analysis rendered a report-building title.")
    if b"\x1b[" not in raw:
        raise RuntimeError("PTY stream did not contain ANSI control sequences.")
    if b"38;2;" not in raw and b"38;5;" not in raw:
        raise RuntimeError("PTY stream did not contain foreground color styles.")


if __name__ == "__main__":
    if sys.argv[1:] == ["--child"]:
        _child()
    elif len(sys.argv) == 1:
        _parent()
    else:
        raise SystemExit("usage: capture.py [--child]")
