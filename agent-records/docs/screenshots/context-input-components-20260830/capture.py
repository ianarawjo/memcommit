"""Capture four current Context-input terminal components for comparison."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
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
_SPEC = importlib.util.spec_from_file_location("context_component_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _prepare_store(root: Path) -> None:
    import memcommit.application.capabilities.ops as ops
    import memcommit.persistence.store as store_module
    from memcommit.persistence.store import MemoryStore

    store_module.STORE_DIR = root
    store = MemoryStore()
    current = ops.init("work/current")
    ops.add(current, "Current Context Memory shown by the selector.")
    ops.add(current, "Second directly owned Memory for exact selection.")
    child = ops.init("work/current/notes")
    ops.add(child, "A lexical descendant shown in the Context tree.")
    archive = ops.init("archive")
    ops.add(archive, "Another readable Context and possible parent location.")
    for context in (current, child, archive):
        store.create_context(context)
    store.set_current(current.name)


def _store_files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _run_child(kind: str, root: Path) -> None:
    from memcommit.adapters.console.entrypoint import app

    _prepare_store(root)
    before = _store_files(root)
    print(f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}")
    if kind == "context-selector":
        print("$ mem add · CONTEXT SELECTOR", flush=True)
        app(args=["add"], prog_name="mem", standalone_mode=False)
    elif kind == "direct-memory-selector":
        print("$ mem edit · DIRECT MEMORY SELECTOR", flush=True)
        app(args=["edit"], prog_name="mem", standalone_mode=False)
    elif kind == "context-name-editor":
        print("$ mem init · CONTEXT NAME EDITOR", flush=True)
        app(args=["init"], prog_name="mem", standalone_mode=False)
    elif kind == "readable-scope-editor":
        print("$ mem query · READABLE SCOPE EDITOR", flush=True)
        app(args=["query"], prog_name="mem", standalone_mode=False)
    else:
        raise SystemExit(f"unknown capture kind: {kind}")
    print(
        f"CANCELLED · STORE UNCHANGED {before == _store_files(root)} · "
        "PROVIDER CALLS 0",
        flush=True,
    )


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


def _spawn(kind: str, root: Path) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind, str(root)],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=30,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _capture(
    root: Path,
    *,
    kind: str,
    expected: str,
    stem: str,
    cancel: str = "\x1b",
) -> None:
    child, recorder = _spawn(kind, root)
    try:
        child.expect(expected)
        _BASE._settle(child)
        _BASE._snapshot(recorder, stem)
        child.send(cancel)
        child.expect("CANCELLED .* STORE UNCHANGED True .* PROVIDER CALLS 0")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for pattern in ("*.png", "*.txt", "*.typescript"):
        for path in OUT.glob(pattern):
            path.unlink()
    with tempfile.TemporaryDirectory(prefix="memcommit-context-components-") as raw:
        root = Path(raw)
        _capture(
            root / "context-selector",
            kind="context-selector",
            expected="MEM ADD",
            stem="01-context-selector",
        )
        _capture(
            root / "direct-memory-selector",
            kind="direct-memory-selector",
            expected="MEM EDIT",
            stem="02-direct-memory-selector",
        )
        _capture(
            root / "context-name-editor",
            kind="context-name-editor",
            expected="NEW CONTEXT NAME",
            stem="03-context-name-editor",
        )
        _capture(
            root / "readable-scope-editor",
            kind="readable-scope-editor",
            expected="MEM QUERY",
            stem="04-readable-scope-editor",
            cancel="\x03",
        )
    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("Component captures did not preserve true-color ANSI.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        _run_child(sys.argv[2], Path(sys.argv[3]))
    else:
        main()
