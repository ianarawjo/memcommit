"""Capture all flagless import branches through a real color PTY."""

from __future__ import annotations

import os
from pathlib import Path
import re
import sys
import tempfile
import time


ROWS = 52
COLUMNS = 180
CAPTURE_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


def _child(root: Path, *, branch: str) -> None:
    # This subprocess owns a disposable home so the real Profile registry and
    # authoring store never participate in capture setup or Apply.
    capture_home = root / "home"
    capture_home.mkdir(parents=True)
    os.environ["HOME"] = str(capture_home)
    os.environ["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"

    from memcommit.cli import app
    from memcommit.commands.list_memories.command import render_index
    from memcommit.context import Context, Memory
    from memcommit.store import MemoryStore
    from tests.test_resource_import import _write_source_store

    rows, columns = os.get_terminal_size()
    print(f"CAPTURE PTY · {columns}x{rows}", flush=True)

    store = MemoryStore()
    destination = Context(
        uid="40000000-0000-4000-8000-000000000001",
        name="destination",
    )
    destination.add(
        Memory(
            uid="40000000-0000-4000-8000-000000000002",
            content="Local destination Memory.",
        )
    )
    store.save(destination)
    store.set_current(destination.name)
    source_root = root / "source-store"
    _write_source_store(source_root)
    app(
        prog_name="mem",
        args=["import", "profile", "source-profile", "--from", str(source_root)],
        standalone_mode=False,
    )
    app(prog_name="mem", args=["import"], standalone_mode=False)

    if branch == "cancel":
        print("CANCEL VERIFICATION · READ-ONLY")
        print("CONTEXTS · " + ", ".join(store.list_context_names()))
        print(f"CURRENT CONTEXT · {store.current_context_name()}")
        print("READ-ONLY VERIFICATION COMPLETE", flush=True)
        return

    print("CAPTURE PAUSE · press Enter for read-only verification", flush=True)
    input()
    print("READ-ONLY VERIFICATION")
    if branch == "profile":
        print("COMMAND · mem profile list")
        app(prog_name="mem", args=["profile", "list"], standalone_mode=False)
    elif branch == "context":
        print("COMMAND · mem list source/root --direct")
        render_index(store.load("source/root"), recursive=False)
    elif branch == "memory":
        print("COMMAND · mem list destination --direct")
        render_index(store.load("destination"), recursive=False)
    else:  # pragma: no cover - parent validates branch spelling
        raise ValueError("Unknown capture branch.")
    print(f"CURRENT CONTEXT · {store.current_context_name()}")
    print("READ-ONLY VERIFICATION COMPLETE", flush=True)


def _drain(child, raw: bytearray, *, timeout: float = 0.1) -> bool:
    import pexpect

    try:
        raw.extend(child.read_nonblocking(size=65536, timeout=timeout))
        return True
    except (pexpect.TIMEOUT, pexpect.EOF):
        return False


def _settle(child, raw: bytearray, *, delay: float = 0.25) -> None:
    time.sleep(delay)
    while _drain(child, raw, timeout=0.02):
        pass


def _wait_for(child, raw: bytearray, marker: bytes, *, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while marker not in raw:
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Timed out waiting for {marker!r}.")
        _drain(child, raw)
    _settle(child, raw)


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
    from matplotlib import font_manager
    from PIL import Image, ImageDraw, ImageFont

    screen = pyte.Screen(COLUMNS, ROWS)
    stream = pyte.Stream(screen)
    stream.feed(raw.decode("utf-8", errors="replace"))

    plain = "\n".join(screen.display)
    (CAPTURE_DIR / f"{name}.txt").write_text(plain + "\n", encoding="utf-8")
    (CAPTURE_DIR / f"{name}.typescript").write_bytes(raw)

    font = ImageFont.truetype(font_manager.findfont("DejaVu Sans Mono"), 18)
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
                        (x + 1, y - 1),
                        character.data,
                        font=font,
                        fill=fg,
                    )
    image.save(CAPTURE_DIR / f"{name}.png")


def _spawn(environment: dict[str, str], directory: str, *, branch: str):
    import pexpect

    return pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", directory, branch],
        env=environment,
        dimensions=(ROWS, COLUMNS),
        encoding=None,
        timeout=0.1,
    )


def _close_checked(child, branch: str) -> None:
    child.close()
    if child.exitstatus not in {0, None}:
        raise RuntimeError(f"{branch} child exited with {child.exitstatus}.")


def _capture_profile(environment: dict[str, str]) -> bytearray:
    raw = bytearray()
    with tempfile.TemporaryDirectory(prefix="memcommit-import-profile-") as directory:
        child = _spawn(environment, directory, branch="profile")
        _wait_for(child, raw, b"MEM IMPORT \xc2\xb7 RESOURCE")
        _render_snapshot("01-resource-kind-entry", bytes(raw))

        child.send(b"\r")
        _wait_for(child, raw, b"CURRENT PROFILE HIDDEN FROM SOURCE LIST")
        _render_snapshot("02-source-profile-current-hidden", bytes(raw))

        child.send(b"\r")
        _wait_for(child, raw, b"NEW PROFILE NAME")
        _render_snapshot("03-profile-name", bytes(raw))

        child.send(b"\r")
        _wait_for(child, raw, b"PROFILE \xc2\xb7 FINAL APPROVAL")
        _render_snapshot("04-profile-exact-approval", bytes(raw))

        child.send(b"A")
        _wait_for(child, raw, b"CAPTURE PAUSE")
        _render_snapshot("05-profile-success-receipt", bytes(raw))

        child.send(b"\r")
        _wait_for(child, raw, b"READ-ONLY VERIFICATION COMPLETE")
        _render_snapshot("06-profile-read-only-verification", bytes(raw))
        _close_checked(child, "profile")
    return raw


def _capture_context(environment: dict[str, str]) -> bytearray:
    raw = bytearray()
    with tempfile.TemporaryDirectory(prefix="memcommit-import-context-") as directory:
        child = _spawn(environment, directory, branch="context")
        _wait_for(child, raw, b"MEM IMPORT \xc2\xb7 RESOURCE")
        child.send(b"\x1b[B")
        _settle(child, raw)
        _render_snapshot("07-context-kind-selected", bytes(raw))

        child.send(b"\r")
        _wait_for(child, raw, b"CURRENT PROFILE HIDDEN FROM SOURCE LIST")
        child.send(b"\r")
        _wait_for(child, raw, b"SOURCE CONTEXT")
        _render_snapshot("08-context-source-choice", bytes(raw))

        child.send(b"\r")
        _wait_for(child, raw, b"CONTEXT RANGE")
        child.send(b"\x1b[C")
        _settle(child, raw)
        _render_snapshot("09-context-subtree-range", bytes(raw))

        child.send(b"\r")
        _wait_for(child, raw, b"IMPORT DESTINATION")
        _render_snapshot("10-context-destination-name", bytes(raw))

        child.send(b"\r")
        _wait_for(child, raw, b"CONTEXT \xc2\xb7 FINAL APPROVAL")
        _render_snapshot("11-context-exact-approval", bytes(raw))

        child.send(b"A")
        _wait_for(child, raw, b"CAPTURE PAUSE")
        _render_snapshot("12-context-success-receipt", bytes(raw))

        child.send(b"\r")
        _wait_for(child, raw, b"READ-ONLY VERIFICATION COMPLETE")
        _render_snapshot("13-context-read-only-verification", bytes(raw))
        _close_checked(child, "context")
    return raw


def _capture_memory(environment: dict[str, str]) -> bytearray:
    raw = bytearray()
    with tempfile.TemporaryDirectory(prefix="memcommit-import-memory-") as directory:
        child = _spawn(environment, directory, branch="memory")
        _wait_for(child, raw, b"MEM IMPORT \xc2\xb7 RESOURCE")
        child.send(b"\x1b[B\x1b[B")
        _settle(child, raw)
        _render_snapshot("14-memory-kind-selected", bytes(raw))

        child.send(b"\r")
        _wait_for(child, raw, b"CURRENT PROFILE HIDDEN FROM SOURCE LIST")
        child.send(b"\r")
        _wait_for(child, raw, b"SOURCE MEMORY")
        child.send(b"\x1b[B\x1b[B\x1b[B")
        _settle(child, raw)
        _render_snapshot("15-memory-source-choice", bytes(raw))

        child.send(b"\r")
        _wait_for(child, raw, b"DESTINATION CONTEXT")
        _render_snapshot("16-memory-destination-context", bytes(raw))

        child.send(b"\r")
        _wait_for(child, raw, b"MEMORY \xc2\xb7 FINAL APPROVAL")
        _render_snapshot("17-memory-exact-approval", bytes(raw))

        child.send(b"A")
        _wait_for(child, raw, b"CAPTURE PAUSE")
        _render_snapshot("18-memory-success-receipt", bytes(raw))

        child.send(b"\r")
        _wait_for(child, raw, b"READ-ONLY VERIFICATION COMPLETE")
        _render_snapshot("19-memory-read-only-verification", bytes(raw))
        _close_checked(child, "memory")
    return raw


def _capture_cancel(environment: dict[str, str]) -> bytearray:
    raw = bytearray()
    with tempfile.TemporaryDirectory(prefix="memcommit-import-cancel-") as directory:
        child = _spawn(environment, directory, branch="cancel")
        _wait_for(child, raw, b"MEM IMPORT \xc2\xb7 RESOURCE")
        child.send(b"\x1b")
        _wait_for(child, raw, b"READ-ONLY VERIFICATION COMPLETE")
        _render_snapshot("20-cancelled-before-source-open", bytes(raw))
        _close_checked(child, "cancel")
    return raw


def _parent() -> None:
    environment = dict(os.environ)
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    streams = (
        _capture_profile(environment),
        _capture_context(environment),
        _capture_memory(environment),
        _capture_cancel(environment),
    )
    combined = b"".join(bytes(stream) for stream in streams)
    if b"\x1b[" not in combined:
        raise RuntimeError("PTY streams did not contain ANSI control sequences.")
    if b"38;2;" not in combined and b"38;5;" not in combined:
        raise RuntimeError("PTY streams did not contain foreground color styles.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        branch = sys.argv[3]
        if branch not in {"profile", "context", "memory", "cancel"}:
            raise SystemExit("unknown capture branch")
        _child(Path(sys.argv[2]), branch=branch)
    elif len(sys.argv) == 1:
        _parent()
    else:
        raise SystemExit(
            "usage: capture_import_tui.py [--child DIRECTORY "
            "{profile,context,memory,cancel}]"
        )
