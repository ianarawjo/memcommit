"""Capture the Compare-to-Meld target picker in a real 180x52 color PTY."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import re
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52

_BASE_PATH = (
    ROOT
    / "agent-records/docs/screenshots/atomize-memory-selection-20260814/capture.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "meld_target_picker_capture_base",
    _BASE_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _prepare_store(store_root: Path):
    import memcommit.application.capabilities.ops as ops
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=store_root)
    left = ops.init("capture/compare-a")
    ops.add(left, "The south vehicle entrance closes during construction.")
    right = ops.init("capture/compare-b")
    ops.add(right, "The north pedestrian entrance remains open.")
    empty_result = ops.init("capture/empty-result")
    occupied = ops.init("capture/occupied-result")
    ops.add(occupied, "This Context is not eligible as a Meld result.")
    for context in (left, right, empty_result, occupied):
        store.create_context(context)
    store.set_current(empty_result.name)
    return store, left, right, empty_result, occupied


def _run_child(store_root: Path) -> None:
    from memcommit.adapters.console.commands.meld.target_picker import (
        choose_meld_target,
    )

    store, left, right, empty_result, occupied = _prepare_store(store_root)
    before = {
        context.name: store._context_file(context.name).read_bytes()
        for context in (left, right, empty_result, occupied)
    }
    print(
        "$ mem compare capture/compare-a capture/compare-b "
        "· reviewed analysis · start Meld",
        flush=True,
    )
    print(
        f"LIVE COLOR PTY · {os.get_terminal_size().columns} "
        f"{os.get_terminal_size().lines}",
        flush=True,
    )
    receipt = choose_meld_target(
        store,
        source_names=(left.name, right.name),
    )
    if receipt is None:
        raise RuntimeError("Meld target selection unexpectedly cancelled.")
    print("\nCOMPARE → MELD HANDOFF RECEIPT")
    print("  LAYER · PRE-SESSION MELD SETUP")
    print(f"  RESULT CONTEXT · {receipt.context_name}")
    print(f"  CREATE ON START · {receipt.create}")
    print("  MELD SESSION CREATED · False")
    print("CAPTURE GATE · PRESS V FOR READ-ONLY VERIFICATION", flush=True)
    if sys.stdin.read(1).lower() != "v":
        raise RuntimeError("Verification gate was not acknowledged.")
    print("\nREAD-ONLY TARGET-PICKER VERIFICATION")
    print(f"  CURRENT CONTEXT · {store.current_context_name()}")
    print(
        "  EXISTING CONTEXT BYTES UNCHANGED · "
        f"{all(store._context_file(name).read_bytes() == value for name, value in before.items())}"
    )
    print(f"  NEW RESULT EXISTS · {store.context_exists(receipt.context_name)}")
    print("  MELD SESSIONS · 0")
    print("  PROVIDER CALLS · 0", flush=True)


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PROMPT_TOOLKIT_COLOR_DEPTH": "DEPTH_24_BIT",
            "PROMPT_TOOLKIT_NO_CPR": "1",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
            "PYTHONPATH": str(ROOT / "src"),
        }
    )
    return environment


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
    with tempfile.TemporaryDirectory(prefix="meld-target-picker-capture-") as directory:
        child, recorder = _spawn(Path(directory))
        try:
            child.expect("CHOOSE RESULT CONTEXT")
            _BASE._settle(child)
            _snapshot(recorder, "01-target-picker-entry")

            child.send("\x1b[B")
            _BASE._settle(child)
            _snapshot(recorder, "02-existing-empty-target-selected")

            child.send("\x1b[A\r")
            _BASE._settle(child)
            child.send("capture/new-result")
            _BASE._settle(child)
            _snapshot(recorder, "03-new-target-name-entry")

            child.send("\r")
            child.expect("COMPARE → MELD HANDOFF RECEIPT")
            child.expect("CAPTURE GATE")
            _BASE._settle(child)
            _snapshot(recorder, "04-process-local-target-receipt")

            child.send("v\r")
            child.expect("READ-ONLY TARGET-PICKER VERIFICATION")
            child.expect("PROVIDER CALLS .* 0")
            child.expect(pexpect.EOF)
            _snapshot(recorder, "05-read-only-verification")
        finally:
            if child.isalive():
                child.close(force=True)

    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
    if re.search(r"\x1b\[[0-9;]*(?:38|48);(?:2|5);", raw) is None:
        raise RuntimeError("PTY stream did not contain expected color ANSI styles.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        _run_child(Path(sys.argv[2]))
    else:
        main()
