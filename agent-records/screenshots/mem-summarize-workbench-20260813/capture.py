"""Capture the picker-first Summarize workbench in a real color PTY."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import sys

import pexpect


ROOT = Path("/Users/KimMunyeong/Github/memcommit")
OUT = ROOT / "agent-records/screenshots/mem-summarize-workbench-20260813"
COLUMNS = 180
ROWS = 52
DOWN = "\x1b[B"
LEFT = "\x1b[D"
RIGHT = "\x1b[C"
TAB = "\t"
ENTER = "\r"

_BASE_PATH = ROOT / "agent-records/screenshots/context-endpoint-memory-preview-20260810/capture.py"
_SPEC = importlib.util.spec_from_file_location("summarize_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _context_state() -> tuple[bytes, tuple[str, ...]]:
    from memcommit.store import MemoryStore

    store = MemoryStore(create=False)
    name = "task-1/participant"
    record = store._context_file(name).read_bytes()
    checkpoints = tuple(item["uid"] for item in store.list_checkpoints(name))
    return record, checkpoints


def _run_tui_child(*, cancel: bool) -> None:
    from memcommit.cli import app

    before = _context_state()
    print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
    app(
        args=["summarize", "task-1/participant", "--tui"],
        prog_name="mem",
        standalone_mode=False,
    )
    assert _context_state() == before
    outcome = "CANCELLED BEFORE EXECUTION" if cancel else "RESULT CLOSED"
    print(
        f"SUMMARIZE {outcome} · READ-ONLY VERIFIED · "
        "CONTEXT BYTES UNCHANGED · CHECKPOINTS UNCHANGED"
    )


def _run_plain_child() -> None:
    from memcommit.cli import app

    before = _context_state()
    print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
    app(
        args=["summarize", "task-1/participant", "--plain"],
        prog_name="mem",
        standalone_mode=False,
    )
    assert _context_state() == before
    print("PLAIN VERIFICATION COMPLETE · READ-ONLY · CONTEXT UNCHANGED")


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _spawn(kind: str) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=12,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> None:
    _BASE._snapshot(recorder, stem)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    child, recorder = _spawn("result")
    try:
        child.expect("MEM SUMMARIZE")
        _BASE._settle(child)
        _snapshot(recorder, "01-picker-entry")

        child.send(TAB)
        _BASE._settle(child)
        _snapshot(recorder, "02-descendants-focused")

        child.send(RIGHT)
        _BASE._settle(child)
        _snapshot(recorder, "03-descendants-included")

        child.send(LEFT + TAB)
        _BASE._settle(child)
        _snapshot(recorder, "04-direct-ready-to-run")

        child.send(ENTER)
        child.expect("SUMMARY · task-1/participant")
        _BASE._settle(child)
        _snapshot(recorder, "05-result-focused")

        child.send(DOWN)
        _BASE._settle(child)
        _snapshot(recorder, "06-result-status-focused")

        child.send(DOWN)
        _BASE._settle(child)
        _snapshot(recorder, "07-result-understanding-focused")

        child.send("q")
        child.expect("SUMMARIZE RESULT CLOSED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "08-read-only-close-verification")
    finally:
        if child.isalive():
            child.close(force=True)

    child, recorder = _spawn("cancel")
    try:
        child.expect("MEM SUMMARIZE")
        child.send("q")
        child.expect("CANCELLED BEFORE EXECUTION")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "09-cancel-before-execution")
    finally:
        if child.isalive():
            child.close(force=True)

    child, recorder = _spawn("plain")
    try:
        child.expect("PLAIN VERIFICATION COMPLETE")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "10-nontui-plain-verification")
    finally:
        if child.isalive():
            child.close(force=True)

    child, recorder = _spawn("result")
    child.timeout = 120
    try:
        child.expect("MEM SUMMARIZE")
        child.send(TAB + RIGHT + "s")
        child.expect("SUMMARY · task-1/participant")
        _BASE._settle(child)
        _snapshot(recorder, "11-recursive-provider-result")

        child.send("q")
        child.expect("SUMMARIZE RESULT CLOSED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "12-recursive-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)

    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "\x1b[" in raw
    assert "38;" in raw


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT / "src"))
        if sys.argv[2] == "result":
            _run_tui_child(cancel=False)
        elif sys.argv[2] == "cancel":
            _run_tui_child(cancel=True)
        elif sys.argv[2] == "plain":
            _run_plain_child()
        else:
            raise SystemExit(f"unknown child kind: {sys.argv[2]}")
    else:
        main()
