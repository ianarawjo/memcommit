"""Capture the real Update command-wait PTY with a deterministic provider."""

from __future__ import annotations

import json
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
    import memcommit.store as store_module

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


def _child(store_root: Path) -> None:
    import memcommit.ops as ops
    import memcommit.commands.update.command as update_command
    from memcommit.cli import app
    from memcommit.store import MemoryStore

    _configure_store(store_root)
    os.environ["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"
    rows, columns = os.get_terminal_size()
    print(f"CAPTURE PTY · {columns}x{rows}", flush=True)

    store = MemoryStore()
    source = ops.init("capture/update/source")
    ops.add(source, "The south entrance now provides step-free public access.")
    target = ops.init("capture/update/target")
    target_memory = ops.add(
        target,
        "The north entrance provides the only public access.",
    )
    store.save(source)
    store.save(target)
    store.set_current(source.name)

    class DeterministicProvider:
        def complete(self, prompt, *, operation, output_schema=None):
            assert operation == "update planning"
            assert output_schema is not None
            # Leave enough time for the capture driver to render the report,
            # confirmed inputs, and nested Help while this one turn remains live.
            time.sleep(18.0)
            payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
            source_id = payload["source"]["memories"][0]["source_id"]
            target_id = payload["target"]["memories"][0]["target_id"]
            return json.dumps(
                {
                    "edits": [
                        {
                            "target_id": target_id,
                            "new_content": (
                                "The south entrance provides step-free public access."
                            ),
                            "source_ids": [source_id],
                            "reason": (
                                "The verified access update supersedes the old route."
                            ),
                        }
                    ],
                    "additions": [],
                    "removals": [],
                }
            )

    def connect_provider():
        time.sleep(1.2)
        return DeterministicProvider()

    update_command.connect_codex_chatgpt_provider = connect_provider
    app(
        prog_name="mem",
        args=["update", "--from", source.name, "--to", target.name],
        standalone_mode=False,
    )

    print("CAPTURE PAUSE · press Enter for read-only verification", flush=True)
    input()
    staged = store.load_staged_update()
    reloaded_source = store.load_direct(source.name)
    reloaded_target = store.load_direct(target.name)
    print("CAPTURE VERIFICATION · READ-ONLY")
    print(
        "STAGED RECEIPT · "
        + ("PRESENT" if staged is not None and staged.status == "staged" else "MISSING")
    )
    print(
        "SOURCE UNCHANGED · "
        + (
            "YES"
            if next(iter(reloaded_source.memories.values())).content
            == "The south entrance now provides step-free public access."
            else "NO"
        )
    )
    print(
        "TARGET UNCHANGED · "
        + (
            "YES"
            if reloaded_target.memories[target_memory.uid].content
            == "The north entrance provides the only public access."
            else "NO"
        )
    )


def _drain(child, raw: bytearray, *, timeout: float = 0.1) -> bool:
    import pexpect

    try:
        raw.extend(child.read_nonblocking(size=65536, timeout=timeout))
        return True
    except pexpect.TIMEOUT:
        return False
    except pexpect.EOF:
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
    with tempfile.TemporaryDirectory(prefix="memcommit-update-wait-") as directory:
        child = pexpect.spawn(
            sys.executable,
            [str(Path(__file__).resolve()), "--child", directory],
            env=environment,
            dimensions=(ROWS, COLUMNS),
            encoding=None,
            timeout=0.1,
        )
        _wait_for(child, raw, b"CONTENT PENDING", timeout=5)
        _render_snapshot("01-dot-cycle-report", bytes(raw))

        child.send(b"c")
        _settle(child, raw, delay=0.5)
        _render_snapshot("02-context-browser", bytes(raw))

        child.send(b"m\x1b[B")
        _wait_for(child, raw, b"south entrance now", timeout=3)
        _render_snapshot("03-context-memory-preview", bytes(raw))

        child.send(b"c")
        _settle(child, raw)
        _render_snapshot("04-report-after-context-repeat", bytes(raw))

        child.send(b"i")
        _wait_for(child, raw, b"SOURCE A", timeout=3)
        _render_snapshot("05-confirmed-inputs", bytes(raw))

        child.send(b"i")
        _settle(child, raw)
        _render_snapshot("06-report-after-input-repeat", bytes(raw))

        child.send(b"i")
        _settle(child, raw)
        _render_snapshot("07-inputs-before-help", bytes(raw))

        child.send(b"h")
        _wait_for(child, raw, b"mem help", timeout=3)
        _render_snapshot("08-help-during-update", bytes(raw))

        child.send(b"h")
        _settle(child, raw)
        _render_snapshot("09-inputs-after-help-repeat", bytes(raw))

        child.send(b"r")
        _settle(child, raw)
        _render_snapshot("10-report-destination", bytes(raw))

        child.send(b"r")
        _settle(child, raw)
        _render_snapshot("11-inputs-after-report-repeat", bytes(raw))

        child.send(b"r")
        _settle(child, raw)
        _render_snapshot("12-report-restored", bytes(raw))

        _wait_for(child, raw, b"CAPTURE PAUSE", timeout=25)
        _render_snapshot("13-applied-result", bytes(raw))

        child.send(b"\r")
        _wait_for(child, raw, b"TARGET UNCHANGED", timeout=5)
        deadline = time.monotonic() + 5
        while child.isalive() and time.monotonic() < deadline:
            _drain(child, raw)
        while _drain(child, raw, timeout=0.02):
            pass
        child.close()
        if child.exitstatus not in {0, None}:
            raise RuntimeError(f"Capture child exited with {child.exitstatus}.")
        _render_snapshot("14-read-only-verification", bytes(raw))

    for obsolete_stem in ("13-staged-review", "14-staged-receipt-verification"):
        for suffix in (".png", ".txt", ".typescript"):
            obsolete = CAPTURE_DIR / f"{obsolete_stem}{suffix}"
            if obsolete.exists():
                obsolete.unlink()

    if b"\x1b[" not in raw:
        raise RuntimeError("PTY stream did not contain ANSI control sequences.")
    if b"38;2;" not in raw and b"38;5;" not in raw:
        raise RuntimeError("PTY stream did not contain foreground color styles.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        _child(Path(sys.argv[2]))
    elif len(sys.argv) == 1:
        _parent()
    else:
        raise SystemExit("usage: capture_update_wait.py [--child STORE]")
