"""Capture flagless Forget setup and Apply through a real color PTY."""

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
INSTRUCTION = (
    "Forget the previous west-entrance desk location and obsolete access code; "
    "keep general accessibility guidance."
)
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
    current = ops.init("alpha")
    ops.add(current, "Keep the current Context unchanged.")
    source = ops.init("beta")
    ops.add(
        source,
        "The desk was previously beside the west entrance. The route remains step-free.",
    )
    ops.add(source, "The obsolete access code was 4815.")
    ops.add(source, "Visitors should verify the step-free route before arrival.")
    store.save(current)
    store.save(source)
    store.set_current(current.name)
    return store, current, source


def _child(store_root: Path, *, cancel: bool) -> None:
    import memcommit.adapters.console.commands.forget.command as forget_command
    from memcommit.adapters.console.entrypoint import app
    from memcommit.providers.types import ProviderIdentity

    _configure_store(store_root)
    os.environ["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"
    rows, columns = os.get_terminal_size()
    print(f"CAPTURE PTY · {columns}x{rows}", flush=True)
    store, current, source = _create_store()
    original = source.to_dict()
    provider_connections = {"value": 0}

    class DeterministicForgetProvider:
        identity = ProviderIdentity(provider="capture", model="deterministic")

        def complete(self, prompt, *, operation, output_schema=None):
            assert operation == "forget"
            assert output_schema is not None
            # Keep the real command-wait surface visible for capture.
            time.sleep(8.0)
            messages = json.loads(prompt.split("FORGET CHAT MESSAGES:\n", 1)[1])
            payload = json.loads(
                messages[1]["content"].split("FORGET PAYLOAD:\n", 1)[1]
            )
            records = []
            for index, memory in enumerate(payload["source"]["memories"]):
                if index == 0:
                    decision = "EDIT"
                    content = "The route remains step-free."
                    rationale = (
                        "Remove the old desk location while retaining accessibility guidance."
                    )
                elif index == 1:
                    decision = "DELETE"
                    content = ""
                    rationale = "The instruction explicitly covers the obsolete access code."
                else:
                    decision = "KEEP"
                    content = memory["content"]
                    rationale = "This is general accessibility guidance to retain."
                records.append(
                    {
                        "source_memory_id": memory["item_id"],
                        "decision": decision,
                        "proposed_content": content,
                        "rationale": rationale,
                        "criterion_item_ids": ["k1"],
                    }
                )
            return json.dumps(
                {
                    "overview": (
                        "Remove the obsolete location and code while preserving "
                        "general step-free guidance."
                    ),
                    "candidates": records,
                }
            )

    def connect_provider():
        provider_connections["value"] += 1
        if cancel:
            raise AssertionError("Cancelled setup connected a provider.")
        return DeterministicForgetProvider()

    forget_command.connect_codex_chatgpt_provider = connect_provider
    app(prog_name="mem", args=["forget"], standalone_mode=False)

    if cancel:
        reloaded = store.load_direct(source.name)
        print("CANCEL VERIFICATION · READ-ONLY")
        print(f"PROVIDER CONNECTIONS · {provider_connections['value']}")
        print(
            "SOURCE UNCHANGED · "
            + ("YES" if reloaded.to_dict() == original else "NO")
        )
        print(f"CURRENT CONTEXT · {store.current_context_name()}")
        return

    print("CAPTURE PAUSE · press Enter for read-only verification", flush=True)
    input()
    print("CAPTURE VERIFICATION COMMAND · mem show --context beta")
    app(
        prog_name="mem",
        args=["show", "--context", source.name],
        standalone_mode=False,
    )
    print(f"CURRENT CONTEXT · {store.current_context_name()}")
    print(f"PROVIDER CONNECTIONS · {provider_connections['value']}")


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


def _wait_for(child, raw: bytearray, marker: bytes, *, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while marker not in raw:
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Timed out waiting for {marker!r}.")
        _drain(child, raw)
    _settle(child, raw, delay=0.2)


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
                    draw.text(
                        (x + 1, y - 1),
                        character.data,
                        font=font,
                        fill=fg,
                    )
    image.save(CAPTURE_DIR / f"{name}.png")


def _spawn(environment: dict[str, str], directory: str, *, cancel: bool):
    import pexpect

    arguments = [str(Path(__file__).resolve()), "--child", directory]
    if cancel:
        arguments.append("--cancel")
    return pexpect.spawn(
        sys.executable,
        arguments,
        env=environment,
        dimensions=(ROWS, COLUMNS),
        encoding=None,
        timeout=0.1,
    )


def _capture_apply(environment: dict[str, str]) -> bytearray:
    raw = bytearray()
    with tempfile.TemporaryDirectory(prefix="memcommit-forget-setup-") as directory:
        child = _spawn(environment, directory, cancel=False)
        _wait_for(child, raw, b"MEM FORGET", timeout=5)
        _render_snapshot("01-setup-entry", bytes(raw))

        child.send(INSTRUCTION.encode("utf-8"))
        _wait_for(child, raw, b"obsolete access code", timeout=3)
        _render_snapshot("02-instruction-entered", bytes(raw))

        child.send(b"\t\x1b[B\r")
        _settle(child, raw)
        _render_snapshot("03-source-selected", bytes(raw))

        child.send(b"\t")
        _settle(child, raw)
        _render_snapshot("04-todo-ready", bytes(raw))

        child.send(b"\r")
        _wait_for(child, raw, b"CONTENT PENDING", timeout=5)
        _render_snapshot("05-analysis-pending", bytes(raw))

        child.send(b"c")
        _settle(child, raw, delay=0.5)
        _render_snapshot("06-context-browser", bytes(raw))

        child.send(b"i")
        _wait_for(child, raw, b"FROZEN MEMORIES", timeout=3)
        _render_snapshot("07-confirmed-inputs", bytes(raw))
        child.send(b"r")

        _wait_for(child, raw, b"Remove the obsolete location", timeout=15)
        _render_snapshot("08-review-report", bytes(raw))

        child.send(b"\t\x1b[B\r")
        _wait_for(child, raw, b"WHY THIS ACTION", timeout=5)
        _render_snapshot("09-decision-detail", bytes(raw))

        child.send(b"a")
        _settle(child, raw, delay=0.5)
        _render_snapshot("10-approval-summary", bytes(raw))

        child.send(b"\x1b[F")
        _settle(child, raw)
        _render_snapshot("11-exact-apply-action", bytes(raw))

        child.send(b"\r")
        _wait_for(child, raw, b"CAPTURE PAUSE", timeout=8)
        _render_snapshot("12-success-receipt", bytes(raw))

        child.send(b"\r")
        _wait_for(child, raw, b"PROVIDER CONNECTIONS", timeout=5)
        _render_snapshot("13-read-only-verification", bytes(raw))
        child.close()
        if child.exitstatus not in {0, None}:
            raise RuntimeError(f"Apply capture child exited with {child.exitstatus}.")
    return raw


def _capture_cancel(environment: dict[str, str]) -> bytearray:
    raw = bytearray()
    with tempfile.TemporaryDirectory(prefix="memcommit-forget-cancel-") as directory:
        child = _spawn(environment, directory, cancel=True)
        _wait_for(child, raw, b"MEM FORGET", timeout=5)
        child.send(b"\x1b")
        _wait_for(child, raw, b"CANCEL VERIFICATION", timeout=5)
        _render_snapshot("14-cancelled-before-provider", bytes(raw))
        child.close()
        if child.exitstatus not in {0, None}:
            raise RuntimeError(f"Cancel capture child exited with {child.exitstatus}.")
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
    apply_raw = _capture_apply(environment)
    cancel_raw = _capture_cancel(environment)
    combined = bytes(apply_raw + cancel_raw)
    if b"\x1b[" not in combined:
        raise RuntimeError("PTY streams did not contain ANSI control sequences.")
    if b"38;2;" not in combined and b"38;5;" not in combined:
        raise RuntimeError("PTY streams did not contain foreground color styles.")


if __name__ == "__main__":
    if len(sys.argv) in {3, 4} and sys.argv[1] == "--child":
        _child(Path(sys.argv[2]), cancel=len(sys.argv) == 4)
    elif len(sys.argv) == 1:
        _parent()
    else:
        raise SystemExit("usage: capture_forget_setup.py [--child STORE [--cancel]]")
