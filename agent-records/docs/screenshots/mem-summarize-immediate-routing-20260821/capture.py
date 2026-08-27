"""Capture immediate Summarize defaults and the explicit TUI escape hatch."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/docs/screenshots/mem-summarize-immediate-routing-20260821"
COLUMNS = 180
ROWS = 52

_BASE_PATH = (
    ROOT / "agent-records/docs/screenshots/context-endpoint-memory-preview-20260810/capture.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "summarize_immediate_capture_base", _BASE_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _isolate_store(root: Path) -> None:
    import memcommit.persistence.store as store_module

    store_dir = root / ".mem"
    assignments = {
        "STORE_DIR": store_dir,
        "CONTEXTS_DIR": store_dir / "contexts",
        "QUERY_SOURCES_DIR": store_dir / "query-sources",
        "STATE_FILE": store_dir / "state.json",
        "IMPACT_PLAN_FILE": store_dir / "impact-plan.json",
        "STAGED_UPDATE_FILE": store_dir / "staged-update.json",
        "REVIEW_SESSION_FILE": store_dir / "review-session.json",
        "ATOMIZE_ANALYSES_DIR": store_dir / "atomize-analyses",
        "ATOMIZE_WORKBENCHES_DIR": store_dir / "atomize-workbenches",
        "ATOMIZE_GROUNDING_SESSIONS_DIR": store_dir / "atomize-groundings",
        "ATOMIZE_GROUNDING_HISTORY_DIR": store_dir / "atomize-grounding-history",
        "GROUND_SESSIONS_DIR": store_dir / "ground-sessions",
        "MELD_SESSIONS_DIR": store_dir / "meld-sessions",
    }
    for name, value in assignments.items():
        setattr(store_module, name, value)


def _store_bytes(store_dir: Path) -> tuple[tuple[str, bytes], ...]:
    return tuple(
        (str(path.relative_to(store_dir)), path.read_bytes())
        for path in sorted(store_dir.rglob("*"))
        if path.is_file()
    )


def _run_child(kind: str) -> None:
    import memcommit.application.ops as ops
    from memcommit.adapters.console.entrypoint import app
    from memcommit.persistence.store import MemoryStore

    with tempfile.TemporaryDirectory(prefix="mem-summarize-routing-") as temporary:
        root = Path(temporary)
        _isolate_store(root)
        store = MemoryStore()
        current = ops.init("route/current")
        explicit = ops.init("practice/source")
        store.create_context(current)
        store.create_context(explicit)
        store.set_current(current.name)
        before = _store_bytes(store.store_dir)
        size = os.get_terminal_size()
        assert (size.columns, size.lines) == (COLUMNS, ROWS)
        print("PTY", size.columns, size.lines)

        if kind == "current":
            command = ["summarize"]
        elif kind == "explicit":
            command = ["summarize", explicit.name]
        elif kind == "tui":
            command = ["summarize", explicit.name, "--tui"]
        else:
            raise ValueError(f"Unknown capture kind: {kind}")

        app(args=command, prog_name="mem", standalone_mode=False)
        assert _store_bytes(store.store_dir) == before
        print(
            f"{kind.upper()} ROUTE COMPLETE · CONTEXT BYTES UNCHANGED · "
            "CURRENT POINTER UNCHANGED"
        )


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PYTHONPATH": str(ROOT / "src"),
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _spawn(kind: str) -> tuple[pexpect.spawn, object]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _capture_immediate(kind: str, stem: str, expected_context: str) -> None:
    child, recorder = _spawn(kind)
    try:
        child.expect(f"{kind.upper()} ROUTE COMPLETE")
        child.expect(pexpect.EOF)
        child.close()
        assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)
        _BASE._snapshot(recorder, stem)
        raw = recorder.getvalue()
        assert "PTY 180 52" in raw
        assert f"SUMMARY · {expected_context}" in raw
        assert "STATUS · READ-ONLY · DIRECT" in raw
        assert "contains no ordinary Memories to summarize" in raw
        assert "\x1b[?1049h" not in raw
        assert "\x1b[?1049l" not in raw
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_tui() -> None:
    child, recorder = _spawn("tui")
    try:
        child.expect("MEM SUMMARIZE")
        _BASE._settle(child)
        _BASE._snapshot(recorder, "03-explicit-tui-setup")

        child.send("q")
        child.expect("TUI ROUTE COMPLETE")
        child.expect(pexpect.EOF)
        child.close()
        assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)
        _BASE._snapshot(recorder, "04-explicit-tui-cancel-verification")
        raw = recorder.getvalue()
        assert "practice/source" in raw
        assert "RUN SUMMARIZE" in raw
        assert "Summarize cancelled." in raw
        assert "\x1b[?1049h" in raw and "\x1b[?1049l" in raw
        assert re.search(r"\x1b\[[0-9;]*38;(?:2|5);", raw) is not None
        assert re.search(r"\x1b\[[0-9;]*48;(?:2|5);", raw) is not None
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _capture_immediate("current", "01-current-default-immediate", "route/current")
    _capture_immediate("explicit", "02-explicit-context-immediate", "practice/source")
    _capture_tui()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT / "src"))
        _run_child(sys.argv[2])
    else:
        main()
