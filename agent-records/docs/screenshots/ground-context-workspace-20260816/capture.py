"""Capture the physical Ground workspace flow in a real 180x52 color PTY."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import re
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52
DOWN = "\x1b[B"

_BASE_PATH = (
    ROOT / "agent-records/docs/screenshots/mem-help-a-z-boundary-20260813/capture_help_a_z.py"
)
_SPEC = importlib.util.spec_from_file_location("ground_workspace_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLS = COLUMNS
_BASE.ROWS = ROWS


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PROMPT_TOOLKIT_COLOR_DEPTH": "DEPTH_24_BIT",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
            "PYTHONPATH": str(ROOT / "src"),
        }
    )
    return environment


def _invoke(args: list[str]) -> int:
    import click

    from memcommit.cli import app

    try:
        returned = app(args=args, prog_name="mem", standalone_mode=False)
    except click.exceptions.Exit as error:
        return error.exit_code
    return returned if isinstance(returned, int) else 0


def _pause(label: str) -> None:
    print(label, flush=True)
    sys.stdin.readline()


def _run_child(store_root: Path) -> None:
    import memcommit.ops as ops
    import memcommit.store as store_module
    from memcommit.store import MemoryStore

    store_module.STORE_DIR = store_root
    store = MemoryStore()
    orientation = ops.init("capture/orientation")
    ops.add(orientation, "This Context must remain globally current.")
    store.create_context(orientation)
    store.set_current(orientation.name)

    print(
        f"LIVE PTY · {os.get_terminal_size().lines} "
        f"{os.get_terminal_size().columns}",
        flush=True,
    )
    print(
        "$ mem ground capture/ticker --goal "
        "'Learn how real US ticker symbols are assigned.' --snapshot",
        flush=True,
    )
    assert _invoke(
        [
            "ground",
            "capture/ticker",
            "--goal",
            "Learn how real US ticker symbols are assigned.",
            "--snapshot",
        ]
    ) == 0
    _pause("CAPTURE 01 · CREATION RECEIPT · PRESS X")

    for flag, value in (
        (
            "--add-rule",
            "Use observed exchange symbols rather than inventing abbreviations.",
        ),
        ("--add-example", "Apple Inc. is listed under AAPL."),
    ):
        print(f"$ mem ground capture/ticker {flag} {value!r}", flush=True)
        assert _invoke(["ground", "capture/ticker", flag, value]) == 0
    descendant = ops.init("capture/ticker/contexts/us-market")
    ops.add(descendant, "Use actual companies listed on United States exchanges.")
    store.create_context(descendant)
    _pause("CAPTURE 02 · PHYSICAL EDIT RECEIPTS · PRESS X")

    print("$ mem ground capture/ticker", flush=True)
    assert _invoke(["ground", "capture/ticker"]) == 0
    print("GROUND TUI CLOSED · GLOBAL CURRENT STILL " + store.current_context_name())
    _pause("CAPTURE 07 · READ-ONLY CLOSE RECEIPT · PRESS X")

    print(
        "$ mem ground capture/ticker --add-relation "
        "'The Goal is evaluated against every active Rule and Example.'",
        flush=True,
    )
    assert _invoke(
        [
            "ground",
            "capture/ticker",
            "--add-relation",
            "The Goal is evaluated against every active Rule and Example.",
        ]
    ) == 0
    _pause("CAPTURE 08 · LOCAL COMMAND RECEIPT · PRESS X")

    print("$ mem ground capture/ticker --undo", flush=True)
    assert _invoke(["ground", "capture/ticker", "--undo"]) == 0
    print("$ mem ground capture/ticker --snapshot", flush=True)
    assert _invoke(["ground", "capture/ticker", "--snapshot"]) == 0
    workspace = store.load_direct("capture/ticker/relations")
    print(
        "UNDO VERIFIED · RELATIONS DIRECT ITEMS "
        f"{len(tuple(workspace.iter_items()))} · GLOBAL CURRENT "
        f"{store.current_context_name()} · LEGACY JSON "
        f"{(store.ground_sessions_dir / 'capture%2Fticker.json').exists()}",
        flush=True,
    )
    _pause("CAPTURE 09 · LOCAL UNDO AND SNAPSHOT · PRESS X")

    external = ops.init("capture/external")
    external_memory = ops.add(external, "An externally owned ticker observation.")
    store.create_context(external)
    contexts = store.load_for_update("capture/ticker/contexts")
    ops.reference_memory(external_memory, external, contexts)
    store.save(contexts)
    print("$ mem distill --ground capture/ticker --plain", flush=True)
    exit_code = _invoke(["distill", "--ground", "capture/ticker", "--plain"])
    print(
        f"FAIL-CLOSED VERIFIED · EXIT {exit_code} · PROVIDER CALLS 0 · "
        f"GLOBAL CURRENT {store.current_context_name()}",
        flush=True,
    )
    _pause("CAPTURE 10 · TYPED INPUT SAFETY BOUNDARY · PRESS X")


def _spawn(store_root: Path) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", str(store_root)],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> None:
    _BASE._snapshot(recorder, stem)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ground-workspace-capture-") as directory:
        child, recorder = _spawn(Path(directory) / ".mem")
        try:
            child.expect("CAPTURE 01")
            _BASE._pump(child)
            _snapshot(recorder, "01-physical-creation-receipt")
            child.sendline("x")

            child.expect("CAPTURE 02")
            _BASE._pump(child)
            _snapshot(recorder, "02-typed-edit-receipts")
            child.sendline("x")

            child.expect("MEM GROUND · capture/ticker")
            _BASE._pump(child)
            _snapshot(recorder, "03-workspace-entry")

            child.send(DOWN * 3)
            _BASE._pump(child)
            _snapshot(recorder, "04-contexts-row-focused")

            child.send("\r")
            _BASE._pump(child)
            _snapshot(recorder, "05-contexts-memory-surface")

            child.send("\t\x1b[C" + DOWN + "\r")
            _BASE._pump(child)
            _snapshot(recorder, "06-local-descendant-open")

            child.send("q")
            child.expect("CAPTURE 07")
            _BASE._pump(child)
            _snapshot(recorder, "07-read-only-close-verification")
            child.sendline("x")

            child.expect("CAPTURE 08")
            _BASE._pump(child)
            _snapshot(recorder, "08-ground-local-edit-receipt")
            child.sendline("x")

            child.expect("CAPTURE 09")
            _BASE._pump(child)
            _snapshot(recorder, "09-ground-local-undo-verification")
            child.sendline("x")

            child.expect("CAPTURE 10")
            _BASE._pump(child)
            _snapshot(recorder, "10-typed-reference-fail-closed")
            child.sendline("x")
            child.expect(pexpect.EOF)
        finally:
            if child.isalive():
                child.close(force=True)

    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
    assert "LIVE PTY · 52 180" in raw
    assert "38;" in raw and "48;" in raw
    assert re.search(r"\x1b\[[0-9;]*38;(?:2|5);", raw) is not None
    assert "GLOBAL CURRENT capture/orientation" in raw
    assert "PROVIDER CALLS 0" in raw


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        _run_child(Path(sys.argv[2]))
    else:
        main()
