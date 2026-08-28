"""Capture ordered flagless Embed setup through a real color PTY."""

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


def _configure_store(root: Path) -> None:
    import memcommit.persistence.store as store_module

    paths = {
        "STORE_DIR": root,
        "CONTEXTS_DIR": root / "contexts",
        "QUERY_SOURCES_DIR": root / "query-sources",
        "STATE_FILE": root / "state.json",
        "IMPACT_PLAN_FILE": root / "impact-plan.json",
        "STAGED_UPDATE_FILE": root / "staged-update.json",
        "REVIEW_SESSION_FILE": root / "review-session.json",
        "ATOMIZE_ANALYSES_DIR": root / "atomize-analyses",
        "ATOMIZE_WORKBENCHES_DIR": root / "atomize-workbenches",
        "ATOMIZE_GROUNDING_SESSIONS_DIR": root / "atomize-groundings",
        "ATOMIZE_GROUNDING_HISTORY_DIR": root / "atomize-grounding-history",
        "GROUND_SESSIONS_DIR": root / "ground-sessions",
        "MELD_SESSIONS_DIR": root / "meld-sessions",
    }
    for name, value in paths.items():
        setattr(store_module, name, value)


def _create_store():
    import memcommit.application.capabilities.ops as ops
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore()
    archive = ops.init("archive")
    ops.add(archive, "Opening orientation for the guide.")
    ops.add(archive, "Detailed operating notes follow the examples.")
    ops.add(archive, "Closing verification for the guide.")
    examples = ops.init("examples")
    ops.add(examples, "Example A remains owned by the Examples Context.")
    ops.add(examples, "Example B updates live wherever Examples is embedded.")
    guide = ops.init("guide")
    ops.add(guide, "The current Context is only the initial Into suggestion.")
    for context in (archive, examples, guide):
        store.save(context)
    store.set_current(guide.name)
    return store, archive, examples, guide


def _child(store_root: Path, *, mode: str) -> None:
    from memcommit.adapters.console.entrypoint import app

    _configure_store(store_root)
    os.environ["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"
    columns, rows = os.get_terminal_size()
    print(f"CAPTURE PTY · {columns}x{rows}", flush=True)
    store, archive, examples, guide = _create_store()
    originals = {
        context.name: store.load_direct(context.name).to_dict()
        for context in (archive, examples, guide)
    }
    app(prog_name="mem", args=["embed"], standalone_mode=False)

    if mode in {"apply", "memory"}:
        print("CAPTURE PAUSE · press Enter for read-only verification", flush=True)
        input()
        verification_name = guide.name
        print(
            "CAPTURE VERIFICATION COMMAND · mem show --context "
            f"{verification_name}"
        )
        app(
            prog_name="mem",
            args=["show", "--context", verification_name],
            standalone_mode=False,
        )
        reloaded = store.load_direct(verification_name)
        print(f"ORDER · {' → '.join(reloaded.ordered_uids())}")
        print(f"CURRENT CONTEXT · {store.current_context_name()}")
        return

    print(f"{mode.upper()} VERIFICATION · READ-ONLY")
    print(
        "ALL CONTEXTS UNCHANGED · "
        + (
            "YES"
            if all(
                store.load_direct(name).to_dict() == original
                for name, original in originals.items()
            )
            else "NO"
        )
    )
    print(f"CURRENT CONTEXT · {store.current_context_name()}")


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
            tail = bytes(raw[-12000:]).decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Timed out waiting for {marker!r}. Recent PTY stream:\n{tail}"
            )
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
    from PIL import Image, ImageDraw, ImageFont

    screen = pyte.Screen(COLUMNS, ROWS)
    stream = pyte.Stream(screen)
    stream.feed(raw.decode("utf-8", errors="replace"))
    (CAPTURE_DIR / f"{name}.txt").write_text(
        "\n".join(screen.display) + "\n",
        encoding="utf-8",
    )
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
    image = Image.new("RGB", (COLUMNS * cell_width, ROWS * cell_height), background)
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
                if character.underscore:
                    draw.line(
                        (x, y + cell_height - 3, x + cell_width - 1, y + cell_height - 3),
                        fill=fg,
                        width=1,
                    )
    image.save(CAPTURE_DIR / f"{name}.png")


def _spawn(environment: dict[str, str], directory: str, *, mode: str):
    import pexpect

    return pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", directory, "--mode", mode],
        env=environment,
        dimensions=(ROWS, COLUMNS),
        encoding=None,
        timeout=0.1,
    )


def _capture_apply(environment: dict[str, str]) -> bytes:
    raw = bytearray()
    with tempfile.TemporaryDirectory(prefix="memcommit-embed-placement-") as directory:
        child = _spawn(environment, directory, mode="apply")
        _wait_for(child, raw, b"MEM EMBED")
        _render_snapshot("01-setup-entry", bytes(raw))

        child.send(b"\t\x1b[B\r")
        _settle(child, raw)
        _render_snapshot("02-child-selected", bytes(raw))

        child.send(b"\t\x1b[A\x1b[A\r")
        _settle(child, raw)
        _render_snapshot("03-target-selected", bytes(raw))

        child.send(b"\t\x1b[A\x1b[A")
        _settle(child, raw)
        _render_snapshot("04-gap-hover", bytes(raw))

        child.send(b"\r")
        _settle(child, raw)
        _render_snapshot("05-gap-staged", bytes(raw))

        child.send(b"\t")
        _settle(child, raw)
        _render_snapshot("06-exact-command", bytes(raw))

        child.send(b"\x15archive --into")
        _settle(child, raw)
        _render_snapshot("06a-command-invalid-live", bytes(raw))

        child.send(b"\x15archive --into guide")
        _settle(child, raw)
        _render_snapshot("06b-command-live-synced", bytes(raw))

        child.send(b"\r")
        _wait_for(child, raw, b"CAPTURE PAUSE")
        _render_snapshot("07-success-receipt", bytes(raw))

        child.send(b"\r")
        _wait_for(child, raw, b"CURRENT CONTEXT")
        _render_snapshot("08-read-only-verification", bytes(raw))
        child.close()
    return bytes(raw)


def _capture_cancel(environment: dict[str, str]) -> bytes:
    raw = bytearray()
    with tempfile.TemporaryDirectory(prefix="memcommit-embed-cancel-") as directory:
        child = _spawn(environment, directory, mode="cancel")
        _wait_for(child, raw, b"MEM EMBED")
        child.send(b"\x1b")
        _wait_for(child, raw, b"ALL CONTEXTS UNCHANGED")
        _render_snapshot("09-cancelled", bytes(raw))
        child.close()
    return bytes(raw)


def _capture_invalid(environment: dict[str, str]) -> bytes:
    raw = bytearray()
    with tempfile.TemporaryDirectory(prefix="memcommit-embed-invalid-") as directory:
        child = _spawn(environment, directory, mode="invalid")
        _wait_for(child, raw, b"MEM EMBED")
        child.send(b"\t\x1b[B\x1b[B\r\t\t\t\r")
        _settle(child, raw, delay=0.5)
        _render_snapshot("10-self-embed-rejected", bytes(raw))
        child.send(b"\x1b")
        _wait_for(child, raw, b"ALL CONTEXTS UNCHANGED")
        child.close()
    return bytes(raw)


def _capture_invalid_command(environment: dict[str, str]) -> bytes:
    raw = bytearray()
    with tempfile.TemporaryDirectory(
        prefix="memcommit-embed-command-invalid-"
    ) as directory:
        child = _spawn(environment, directory, mode="command-invalid")
        _wait_for(child, raw, b"MEM EMBED")
        child.send(b"\t\t\t\t\x15examples --into missing\r")
        _settle(child, raw, delay=0.5)
        _render_snapshot("10a-command-edit-rejected", bytes(raw))
        child.send(b"\x1b")
        _wait_for(child, raw, b"ALL CONTEXTS UNCHANGED")
        child.close()
    return bytes(raw)


def _capture_memory_self_link(environment: dict[str, str]) -> bytes:
    raw = bytearray()
    with tempfile.TemporaryDirectory(
        prefix="memcommit-memory-embed-self-link-"
    ) as directory:
        child = _spawn(environment, directory, mode="memory-self-link")
        _wait_for(child, raw, b"MEM EMBED")

        child.send(b"\x1b[C")
        _settle(child, raw)
        _render_snapshot("10b-memory-current-source", bytes(raw))

        child.send(b"\t\x1b[B\r")
        _settle(child, raw)
        _render_snapshot("10c-same-context-memory-selected", bytes(raw))

        child.send(b"\t")
        _settle(child, raw)
        _render_snapshot("10d-same-context-target", bytes(raw))

        child.send(b"\t")
        _settle(child, raw)
        _render_snapshot("10e-same-context-position", bytes(raw))

        child.send(b"\t")
        _settle(child, raw)
        _render_snapshot("10f-same-context-exact-command", bytes(raw))

        child.send(b"\r")
        _wait_for(child, raw, b"must be distinct")
        _render_snapshot("10g-same-context-action-rejected", bytes(raw))

        child.send(b"\x1b")
        _wait_for(child, raw, b"ALL CONTEXTS UNCHANGED")
        _render_snapshot("10h-same-context-read-only-verification", bytes(raw))
        child.close()
    return bytes(raw)


def _capture_memory(environment: dict[str, str]) -> bytes:
    raw = bytearray()
    with tempfile.TemporaryDirectory(prefix="memcommit-memory-embed-") as directory:
        child = _spawn(environment, directory, mode="memory")
        _wait_for(child, raw, b"MEM EMBED")

        child.send(b"\x1b[C")
        _settle(child, raw)
        _render_snapshot("11-memory-mode", bytes(raw))

        child.send(b"\t\x1b[A\x1b[A\r\x1b[B\r")
        _settle(child, raw)
        _render_snapshot("12-memory-selected", bytes(raw))

        child.send(b"\t")
        _settle(child, raw)
        _render_snapshot("13-memory-target", bytes(raw))

        child.send(b"\t")
        _settle(child, raw)
        _render_snapshot("14-memory-position", bytes(raw))

        child.send(b"\t")
        _settle(child, raw)
        _render_snapshot("15-memory-exact-command", bytes(raw))

        child.send(b"\r")
        _wait_for(child, raw, b"CAPTURE PAUSE")
        _render_snapshot("16-memory-success-receipt", bytes(raw))

        child.send(b"\r")
        _wait_for(child, raw, b"CURRENT CONTEXT")
        _render_snapshot("17-memory-read-only-verification", bytes(raw))
        child.close()
    return bytes(raw)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--child")
    parser.add_argument(
        "--mode",
        choices=(
            "apply",
            "memory",
            "memory-self-link",
            "cancel",
            "invalid",
            "command-invalid",
        ),
        default="apply",
    )
    arguments = parser.parse_args()
    if arguments.child:
        _child(Path(arguments.child), mode=arguments.mode)
        return

    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment["TERM"] = "xterm-256color"
    environment["COLORTERM"] = "truecolor"
    environment["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"
    streams = (
        _capture_apply(environment),
        _capture_memory(environment),
        _capture_cancel(environment),
        _capture_invalid(environment),
        _capture_invalid_command(environment),
        _capture_memory_self_link(environment),
    )
    combined = b"".join(streams)
    if b"\x1b[" not in combined or not re.search(rb"\x1b\[[0-9;]*38;", combined):
        raise RuntimeError("Capture did not preserve expected ANSI color styles.")
    if any(b"CAPTURE PTY \xc2\xb7 180x52" not in stream for stream in streams):
        raise RuntimeError("Capture child did not verify the 180x52 PTY.")
    if not (
        re.search(rb"38(?:;|:)2(?:;|:)237(?:;|:)135(?:;|:)150", combined)
        or b"38;5;210" in combined
    ):
        raise RuntimeError("Invalid command capture did not render a red box.")
    invalid_text = (CAPTURE_DIR / "06a-command-invalid-live.txt").read_text(
        encoding="utf-8"
    )
    if "mem embed archive --into" not in invalid_text:
        raise RuntimeError("Ctrl-U removed or duplicated the fixed Embed prefix.")
    valid_text = (CAPTURE_DIR / "06b-command-live-synced.txt").read_text(
        encoding="utf-8"
    )
    if "mem embed archive --into guide" not in valid_text:
        raise RuntimeError("Valid Embed arguments did not retain the fixed prefix.")


if __name__ == "__main__":
    main()
