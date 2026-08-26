"""Capture QUERY Grant visibility and opacity in the command-wait browser."""

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


def _child() -> None:
    from memcommit.commands.shared.command_wait import (
        CommandWaitContextBrowser,
        build_report_loading_view,
        run_command_wait,
    )
    from memcommit.commands.shared.context_picker import ContextMemoryRow
    from memcommit.context_targeting.catalog import grant_navigation_annotation
    from memcommit.source_projection.model import SourceDisplayFacts, SourceState
    from memcommit.source_projection.presentation import combine_source_display_tokens

    rows, columns = os.get_terminal_size()
    print(f"CAPTURE PTY · {columns}x{rows}", flush=True)
    loaded_names: list[str] = []

    def load_memories(name: str):
        if name == "public/query-guidance":
            raise AssertionError("QUERY Grant reached the ordinary Context loader")
        loaded_names.append(name)
        return (
            ContextMemoryRow(
                "memory 11111111",
                "Readable preview retained inside the browser only.",
            ),
        )

    def work(_progress):
        time.sleep(4.5)
        return "complete"

    result = run_command_wait(
        "SEVER",
        "analyzing",
        total=1,
        work=work,
        help_entries=(),
        interactive=True,
        interval=0.08,
        return_view=build_report_loading_view(
            "SEVER",
            sections=("What mem understood", "Review decisions", "To do"),
        ),
        context_browser=CommandWaitContextBrowser.create(
            (
                "capture/local",
                "public/query-guidance",
                "public/readable-guidance",
            ),
            current_name="capture/local",
            annotations={
                "public/query-guidance": combine_source_display_tokens(
                    grant_navigation_annotation(("QUERY", "SESSION_LOG")),
                    SourceDisplayFacts(states=(SourceState.UNAVAILABLE,)),
                ),
                "public/readable-guidance": grant_navigation_annotation(
                    ("READ", "DERIVE")
                ),
            },
            readable_names=frozenset(
                {"capture/local", "public/readable-guidance"}
            ),
            memory_loader=load_memories,
        ),
    )
    print("CAPTURE VERIFICATION · READ-ONLY", flush=True)
    print(f"WORKER RESULT · {result.upper()}", flush=True)
    print("LOADED CONTEXTS · " + " + ".join(loaded_names), flush=True)
    print(
        "QUERY LOADER CALLED · "
        + ("YES" if "public/query-guidance" in loaded_names else "NO"),
        flush=True,
    )


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
            raise RuntimeError(f"Timed out waiting for {marker!r}.")
        _drain(child, raw)
    time.sleep(0.2)
    while _drain(child, raw, timeout=0.02):
        pass


def _settle(child, raw: bytearray, *, delay: float = 0.35) -> None:
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
    pyte.Stream(screen).feed(raw.decode("utf-8", errors="replace"))
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
                    draw.text(
                        (x + 1, y - 1), character.data, font=font, fill=fg
                    )
    image.save(CAPTURE_DIR / f"{name}.png")


def _parent() -> None:
    import pexpect

    environment = dict(os.environ)
    environment.pop("NO_COLOR", None)
    environment.update(
        {"TERM": "xterm-256color", "COLORTERM": "truecolor"}
    )
    raw = bytearray()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child"],
        cwd=str(REPOSITORY_ROOT),
        env=environment,
        dimensions=(ROWS, COLUMNS),
        encoding=None,
        timeout=0.1,
    )
    _wait_for(child, raw, b"CONTENT PENDING", timeout=4)
    _render_snapshot("01-report-building", bytes(raw))

    child.send(b"c\x1b[B")
    _wait_for(child, raw, b"public/query-guidance", timeout=3)
    _render_snapshot("02-query-grant-visible", bytes(raw))

    child.send(b"m\r\x1b[CMc")
    _settle(child, raw)
    _render_snapshot("03-report-restored", bytes(raw))

    _wait_for(child, raw, b"QUERY LOADER CALLED", timeout=6)
    child.close()
    if child.exitstatus not in {0, None}:
        raise RuntimeError(f"Capture child exited with {child.exitstatus}.")
    _render_snapshot("04-read-only-verification", bytes(raw))

    if b"\x1b[" not in raw:
        raise RuntimeError("PTY stream did not contain ANSI control sequences.")
    if b"38;2;" not in raw and b"38;5;" not in raw:
        raise RuntimeError("PTY stream did not contain foreground color styles.")
    if b"QUERY LOADER CALLED \xc2\xb7 NO" not in raw:
        raise RuntimeError("QUERY Grant unexpectedly reached the Context loader.")


if __name__ == "__main__":
    if sys.argv[1:] == ["--child"]:
        _child()
    elif not sys.argv[1:]:
        _parent()
    else:
        raise SystemExit("usage: capture_query_grants.py [--child]")
