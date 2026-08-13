"""Capture Embed setup against the active Study Participant Profile."""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import re
import sys
import time


ROWS = 52
COLUMNS = 180
CAPTURE_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SUPPORT_PATH = (
    CAPTURE_DIR.parent / "mem-embed-placement-20260813" / "capture.py"
)
EXPECTED_PROFILE = "study-20260813T135528Z-d61e7a16"
EXPECTED_CURRENT = "task-1/participant"
TARGET = "task-1/participant/construction-updates/route-changes"

if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


def _load_capture_support():
    spec = importlib.util.spec_from_file_location(
        "mem_embed_disposable_capture_support",
        SUPPORT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load the shared Embed PTY renderer.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.CAPTURE_DIR = CAPTURE_DIR
    return module


SUPPORT = _load_capture_support()


def _store_snapshot(root: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    count = 0
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
        count += 1
    return count, digest.hexdigest()


def _child() -> None:
    from memcommit.cli import app
    from memcommit.profile_config import load_profile_registry
    from memcommit.store import MemoryStore, STORE_DIR

    registry = load_profile_registry()
    if registry.active.name != EXPECTED_PROFILE:
        raise RuntimeError(
            "Participant capture requires active Profile "
            f"'{EXPECTED_PROFILE}', got '{registry.active.name}'."
        )
    store = MemoryStore()
    if store.current_context_name() != EXPECTED_CURRENT:
        raise RuntimeError(
            "Participant capture requires current Context "
            f"'{EXPECTED_CURRENT}', got '{store.current_context_name()}'."
        )
    columns, rows = os.get_terminal_size()
    if (columns, rows) != (COLUMNS, ROWS):
        raise RuntimeError(
            f"Participant capture requires {COLUMNS}x{ROWS}, got {columns}x{rows}."
        )

    root = Path(STORE_DIR)
    before = _store_snapshot(root)
    print(f"CAPTURE PTY · {columns}x{rows}", flush=True)
    print(f"PROFILE · {registry.active.name} · PARTICIPANT", flush=True)
    print(f"CURRENT CONTEXT · {store.current_context_name()}", flush=True)
    app(prog_name="mem", args=["embed"], standalone_mode=False)
    after = _store_snapshot(root)

    print("PARTICIPANT PROFILE VERIFICATION · READ-ONLY")
    print(f"STORE FILES · {before[0]}")
    print(
        "STORE BYTE DIGEST UNCHANGED · "
        + ("YES" if before == after else "NO")
    )
    print(f"CURRENT CONTEXT · {store.current_context_name()}")
    print(f"VERIFICATION COMMAND · mem show --context {TARGET}")
    app(
        prog_name="mem",
        args=["show", "--context", TARGET],
        standalone_mode=False,
    )


def _spawn(environment: dict[str, str]):
    import pexpect

    return pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child"],
        env=environment,
        dimensions=(ROWS, COLUMNS),
        encoding=None,
        timeout=0.1,
    )


def _capture(environment: dict[str, str]) -> bytes:
    raw = bytearray()
    child = _spawn(environment)
    SUPPORT._wait_for(child, raw, b"MEM EMBED")
    SUPPORT._render_snapshot("01-participant-entry", bytes(raw))

    # Keep the initial Child `practice`. In the target tree, expand the current
    # `task-1/participant`, expand `construction-updates`, choose its
    # `route-changes` Memory leaf, and retain the explicit LAST default while
    # the real direct-Memory order reloads.
    child.send(b"\t\x1b[C\x1b[B\x1b[C\x1b[B\x1b[B\x1b[B\x1b[B\r")
    SUPPORT._settle(child, raw)
    SUPPORT._render_snapshot("02-participant-target", bytes(raw))

    # Entering Position anchors the scrollable order at the retained LAST
    # default even when a long real Memory sequence does not fit at once.
    child.send(b"\t")
    SUPPORT._settle(child, raw)
    SUPPORT._render_snapshot("03-participant-position-default", bytes(raw))

    # Hover two gaps above LAST. Hover must not rewrite the retained gap or
    # exact command.
    child.send(b"\x1b[A\x1b[A")
    SUPPORT._settle(child, raw)
    SUPPORT._render_snapshot("04-participant-gap-hover", bytes(raw))

    child.send(b"\r")
    SUPPORT._settle(child, raw)
    SUPPORT._render_snapshot("05-participant-gap-staged", bytes(raw))

    child.send(b"\t")
    SUPPORT._settle(child, raw)
    SUPPORT._render_snapshot("06-participant-exact-command", bytes(raw))

    child.send(b"\x1b")
    SUPPORT._wait_for(child, raw, b"STORE BYTE DIGEST UNCHANGED \xc2\xb7 YES")
    deadline = time.monotonic() + 5.0
    while child.isalive() and time.monotonic() < deadline:
        SUPPORT._drain(child, raw)
    SUPPORT._settle(child, raw)
    SUPPORT._render_snapshot("07-participant-cancelled-verified", bytes(raw))
    child.close()
    return bytes(raw)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--child", action="store_true")
    arguments = parser.parse_args()
    if arguments.child:
        _child()
        return

    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment["TERM"] = "xterm-256color"
    environment["COLORTERM"] = "truecolor"
    # The capture tests product behavior, not command-attempt telemetry. This
    # keeps the real participant store byte-identical after cancellation.
    environment["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"
    stream = _capture(environment)
    if b"\x1b[" not in stream or not re.search(rb"\x1b\[[0-9;]*38;", stream):
        raise RuntimeError("Capture did not preserve expected ANSI color styles.")
    if b"CAPTURE PTY \xc2\xb7 180x52" not in stream:
        raise RuntimeError("Capture child did not verify the 180x52 PTY.")
    if b"STORE BYTE DIGEST UNCHANGED \xc2\xb7 YES" not in stream:
        raise RuntimeError("Participant Profile changed during the capture.")


if __name__ == "__main__":
    main()
