"""Capture the Switch application boundary and Ground's neutral-picker reuse."""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from types import SimpleNamespace


ROWS = 52
COLUMNS = 180
CAPTURE_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SUPPORT_PATH = (
    CAPTURE_DIR.parent / "mem-embed-placement-20260813" / "capture.py"
)

if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


def _load_capture_support():
    spec = importlib.util.spec_from_file_location(
        "switch_application_capture_support",
        SUPPORT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load the shared color-PTY renderer.")
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


def _setup_store():
    from memcommit.adapters.console.entrypoint import app
    from memcommit.persistence.store import MemoryStore

    app(prog_name="mem", args=["init", "alpha"], standalone_mode=False)
    app(
        prog_name="mem",
        args=["add", "Alpha evidence Memory."],
        standalone_mode=False,
    )
    app(prog_name="mem", args=["init", "beta"], standalone_mode=False)
    app(
        prog_name="mem",
        args=["add", "Beta evidence Memory."],
        standalone_mode=False,
    )
    return app, MemoryStore()


def _assert_pty() -> None:
    columns, rows = os.get_terminal_size()
    if (columns, rows) != (COLUMNS, ROWS):
        raise RuntimeError(
            f"Switch capture requires {COLUMNS}x{ROWS}, got {columns}x{rows}."
        )


def _switch_child(*, apply_selection: bool) -> None:
    app, store = _setup_store()
    _assert_pty()
    before = _store_snapshot(store.store_dir)
    before_contexts = _store_snapshot(store.contexts_dir)
    initial = store.current_context_name()
    print(f"CAPTURE PTY · {COLUMNS}x{ROWS}", flush=True)
    print(f"CURRENT BEFORE · {initial}", flush=True)
    app(prog_name="mem", args=["switch"], standalone_mode=False)
    after = _store_snapshot(store.store_dir)
    after_contexts = _store_snapshot(store.contexts_dir)
    current = store.current_context_name()
    expected = "alpha" if apply_selection else initial
    print("SWITCH APPLICATION VERIFICATION")
    print(f"CURRENT AFTER · {current}")
    print("EXPECTED CURRENT · " + str(expected))
    print(
        "CONTEXT BYTES UNCHANGED · "
        + ("YES" if before_contexts == after_contexts else "NO")
    )
    if apply_selection:
        print(
            "ONLY POINTER EFFECT EXPECTED · "
            + ("YES" if before != after and current == expected else "NO")
        )
    else:
        print(
            "COMPLETE STORE UNCHANGED · "
            + ("YES" if before == after else "NO")
        )
    print("READ-ONLY VERIFICATION · mem pwd")
    app(prog_name="mem", args=["pwd"], standalone_mode=False)


def _ground_child() -> None:
    _app, store = _setup_store()
    from memcommit.adapters.console.commands.ground_workbench.ground.shell import (
        GroundShellContextSuggestion,
        run_ground_shell,
    )

    _assert_pty()
    before = _store_snapshot(store.store_dir)
    initial = store.current_context_name()

    def interpret(_text: str):
        return SimpleNamespace(
            kind="PROPOSE",
            understanding="Choose existing evidence Contexts before binding roles.",
            question="Which Context should remain a process-local starting hint?",
            ground_name="ticker-rules",
            goal="Understand how ticker symbols are formed.",
            command="ignored provider command",
            context_suggestions=(
                GroundShellContextSuggestion(
                    role="MAIN",
                    context_name="alpha",
                    reason="Name-only starting candidate.",
                ),
                GroundShellContextSuggestion(
                    role="ALTERNATIVE",
                    context_name="beta",
                    reason="Name-only alternative candidate.",
                ),
            ),
            new_context_suggestions=(),
            rule_drafts=(),
            memory_drafts=(),
        )

    print(f"CAPTURE PTY · {COLUMNS}x{ROWS}", flush=True)
    print(f"CURRENT BEFORE · {initial}", flush=True)
    result = run_ground_shell(
        interpret=interpret,
        apply=lambda _proposal: (_ for _ in ()).throw(
            RuntimeError("Ground capture must not apply a proposal.")
        ),
        initial_request="I want to understand how ticker symbols are formed.",
        current_context_name=initial,
        context_catalog_names=("alpha", "beta"),
        context_catalog_count=2,
        require_tty=True,
        background_interpretation=False,
    )
    after = _store_snapshot(store.store_dir)
    print("GROUND DIRECT-PICKER VERIFICATION")
    print(f"RESULT · {result.status}")
    print("SELECTED HINTS · " + ", ".join(result.selected_context_names))
    print(f"CURRENT AFTER · {store.current_context_name()}")
    print("COMPLETE STORE UNCHANGED · " + ("YES" if before == after else "NO"))


def _spawn(mode: str, environment: dict[str, str]):
    import pexpect

    return pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", mode],
        env=environment,
        dimensions=(ROWS, COLUMNS),
        encoding=None,
        timeout=0.1,
    )


def _capture_switch_cancel(environment: dict[str, str]) -> bytes:
    raw = bytearray()
    child = _spawn("switch-cancel", environment)
    SUPPORT._wait_for(child, raw, b"Select a Context")
    SUPPORT._render_snapshot("01-switch-entry", bytes(raw))
    child.send(b"m")
    SUPPORT._settle(child, raw)
    SUPPORT._render_snapshot("02-switch-direct-preview", bytes(raw))
    child.send(b"\x1b")
    SUPPORT._wait_for(child, raw, b"COMPLETE STORE UNCHANGED \xc2\xb7 YES")
    SUPPORT._settle(child, raw)
    SUPPORT._render_snapshot("03-switch-cancelled", bytes(raw))
    child.close()
    return bytes(raw)


def _capture_switch_apply(environment: dict[str, str]) -> bytes:
    raw = bytearray()
    child = _spawn("switch-apply", environment)
    SUPPORT._wait_for(child, raw, b"Select a Context")
    child.send(b"\x1b[A")
    SUPPORT._settle(child, raw)
    SUPPORT._render_snapshot("04-switch-target-selected", bytes(raw))
    child.send(b"\r")
    SUPPORT._wait_for(child, raw, b"ONLY POINTER EFFECT EXPECTED \xc2\xb7 YES")
    SUPPORT._settle(child, raw)
    SUPPORT._render_snapshot("05-switch-applied-and-verified", bytes(raw))
    child.close()
    return bytes(raw)


def _capture_ground(environment: dict[str, str]) -> bytes:
    raw = bytearray()
    child = _spawn("ground", environment)
    SUPPORT._wait_for(child, raw, b"DIRECT SELECT")
    SUPPORT._render_snapshot("06-ground-name-only-suggestions", bytes(raw))
    child.send(b"p")
    SUPPORT._wait_for(child, raw, b"Select a Context")
    SUPPORT._render_snapshot("07-ground-direct-picker", bytes(raw))
    child.send(b"\x1b[A")
    SUPPORT._settle(child, raw)
    child.send(b"\r")
    # Prompt-toolkit may insert cursor-motion ANSI bytes inside the status text,
    # so wait on the stable unsplit count prefix rather than rendered prose.
    SUPPORT._wait_for(child, raw, b"1 Context(s)")
    SUPPORT._settle(child, raw)
    SUPPORT._render_snapshot("08-ground-not-bound-selection", bytes(raw))
    child.send(b"\x1b")
    SUPPORT._wait_for(child, raw, b"COMPLETE STORE UNCHANGED \xc2\xb7 YES")
    deadline = time.monotonic() + 3.0
    while child.isalive() and time.monotonic() < deadline:
        SUPPORT._drain(child, raw)
    SUPPORT._settle(child, raw)
    SUPPORT._render_snapshot("09-ground-closed-and-verified", bytes(raw))
    child.close()
    return bytes(raw)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--child", choices=("switch-cancel", "switch-apply", "ground"))
    arguments = parser.parse_args()
    if arguments.child == "switch-cancel":
        _switch_child(apply_selection=False)
        return
    if arguments.child == "switch-apply":
        _switch_child(apply_selection=True)
        return
    if arguments.child == "ground":
        _ground_child()
        return

    streams: list[bytes] = []
    for capture in (
        _capture_switch_cancel,
        _capture_switch_apply,
        _capture_ground,
    ):
        with tempfile.TemporaryDirectory(
            prefix="memcommit-switch-capture-"
        ) as home:
            environment = os.environ.copy()
            environment.pop("NO_COLOR", None)
            environment["TERM"] = "xterm-256color"
            environment["COLORTERM"] = "truecolor"
            environment["HOME"] = home
            environment["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"
            streams.append(capture(environment))
    stream = b"".join(streams)
    if b"\x1b[" not in stream or not re.search(rb"\x1b\[[0-9;]*38;", stream):
        raise RuntimeError("Capture did not preserve expected ANSI color styles.")
    required = (
        b"CAPTURE PTY \xc2\xb7 180x52",
        b"COMPLETE STORE UNCHANGED \xc2\xb7 YES",
        b"ONLY POINTER EFFECT EXPECTED \xc2\xb7 YES",
        b"CONTEXT BYTES UNCHANGED \xc2\xb7 YES",
        b"SELECTED HINTS \xc2\xb7 alpha",
    )
    missing = [value for value in required if value not in stream]
    if missing:
        raise RuntimeError(f"Capture verification missing: {missing!r}")


if __name__ == "__main__":
    main()
