"""Capture the shared Trace/Rationale range launcher in a real color PTY."""

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
OUT = ROOT / "agent-records/docs/screenshots/memory-report-shared-launcher-20260813"
COLUMNS = 180
ROWS = 52
RIGHT = "\x1b[C"
DOWN = "\x1b[B"
SHIFT_TAB = "\x1b[Z"

_BASE_PATH = (
    ROOT / "agent-records/docs/screenshots/context-endpoint-memory-preview-20260810/capture.py"
)
_SPEC = importlib.util.spec_from_file_location("memory_report_capture_base", _BASE_PATH)
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


def _prepare_fixture() -> str:
    from memcommit.adapters.console.commands import add, delete, edit, init, switch
    from memcommit.core.context import Memory
    from memcommit.persistence.store import MemoryStore

    # Invoke the same command functions directly so this focused capture does
    # not depend on unrelated CLI-module imports elsewhere in the prototype.
    init.cmd("other-empty", parents=False)
    init.cmd("notes", parents=False)
    add.cmd(
        "First wording",
        input_source=None,
        paste=False,
        context_name=None,
    )
    store = MemoryStore()
    memory = next(
        item
        for item in store.load_current_direct().iter_items()
        if isinstance(item, Memory)
    )
    for content in ("Second wording", "Final wording used by both reports"):
        edit.cmd(
            memory.uid,
            content,
            input_source=None,
            context_name=None,
        )
    add.cmd(
        "Retained historical wording",
        input_source=None,
        paste=False,
        context_name=None,
    )
    historical = next(
        item
        for item in store.load_current_direct().iter_items()
        if isinstance(item, Memory) and item.content == "Retained historical wording"
    )
    edit.cmd(
        historical.uid,
        "Revised historical wording",
        input_source=None,
        context_name=None,
    )
    delete.cmd(historical.uid, context_name=None, force=False)
    init.cmd("notes/child", parents=False)
    add.cmd(
        "Descendant wording visible only after range expansion",
        input_source=None,
        paste=False,
        context_name=None,
    )
    switch.cmd("notes")
    return historical.uid


def _run_child(operation: str) -> None:
    from memcommit.adapters.console.commands import rationale, trace

    with tempfile.TemporaryDirectory(prefix="memcommit-report-capture-") as temporary:
        _isolate_store(Path(temporary))
        memory_uid = _prepare_fixture()
        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        if operation == "trace":
            trace.cmd()
        elif operation == "rationale":
            # The launcher is the subject of this evidence. Recorded-only keeps
            # the result deterministic and proves cancellation/selection does
            # not require a provider connection.
            rationale.cmd(recorded_only=True)
        else:
            raise ValueError(f"Unknown operation: {operation}")
        print(
            f"{operation.upper()} CLOSED · SELECTED [{memory_uid[:8]}] · "
            "CURRENT notes · READ ONLY · STORE CONTENT UNCHANGED"
        )


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


def _spawn(operation: str) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", operation],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=15,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> None:
    _BASE._snapshot(recorder, stem)


def _capture(operation: str, start: int) -> int:
    child, recorder = _spawn(operation)
    try:
        child.expect(f"{operation.upper()} · SELECT A MEMORY · notes")
        _BASE._settle(child)
        _snapshot(recorder, f"{start:02d}-{operation}-current-memories-entry")

        child.send("\t\r")
        _BASE._settle(child)
        _snapshot(recorder, f"{start + 1:02d}-{operation}-context-rejected")

        child.send(SHIFT_TAB + RIGHT)
        _BASE._settle(child)
        _snapshot(recorder, f"{start + 2:02d}-{operation}-descendants")

        child.send("\t" + DOWN + DOWN)
        _BASE._settle(child)
        _snapshot(recorder, f"{start + 3:02d}-{operation}-memory-focused")

        child.send("\r")
        if operation == "trace":
            child.expect("TRACE REPORT")
        else:
            child.expect("RATIONALE REPORT")
        _BASE._settle(child)
        _snapshot(recorder, f"{start + 4:02d}-{operation}-result")

        child.send("q")
        child.expect(f"{operation.upper()} CLOSED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, f"{start + 5:02d}-{operation}-verification")
    finally:
        if child.isalive():
            child.close(force=True)
    return start + 6


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for pattern in ("*.png", "*.txt", "*.typescript"):
        for path in OUT.glob(pattern):
            path.unlink()
    next_index = _capture("trace", 1)
    _capture("rationale", next_index)
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    plain = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.txt"))
    assert re.search(r"\[[0-9a-f]{8}\]\s*\[r3\]", raw.casefold())
    assert re.search(
        r"\[historical\]\s*\[[0-9a-f]{8}\]\s*\[r3\]",
        plain.casefold(),
    )
    assert re.search(
        r"\x1b\[[0-9;]*38;5;180m\[historical\]",
        raw,
    )
    assert re.search(
        r"\x1b\[[0-9;]*7m\s+› "
        r"\[historical\]\s*\[[0-9a-f]{8}\]\s*\[r3\]",
        raw.casefold(),
    )
    assert "[current" not in raw.casefold()
    assert "CURRENT notes" in raw
    assert "SELECT A CONTEXT" not in raw
    assert "SELECT A MEMORY" in raw
    assert "INCLUDE DESCENDANTS" in raw
    assert "CONTEXTS & MEMORIES" in raw
    assert plain.count("CONTEXT NOT SELECTABLE") >= 2
    assert plain.count("Select an exact Memory row") >= 2
    for index, operation in ((2, "trace"), (8, "rationale")):
        rejection_raw = (
            OUT / f"{index:02d}-{operation}-context-rejected.typescript"
        ).read_text(encoding="utf-8")
        assert re.search(
            r"\x1b\[[0-9;]*38;5;210(?:;[0-9]+)*m\s*CONTEXT NOT SELECTABLE",
            rejection_raw,
        )
    trace_result = (
        OUT / "05-trace-result.txt"
    ).read_text(encoding="utf-8")
    trace_raw = (
        OUT / "05-trace-result.typescript"
    ).read_text(encoding="utf-8")
    assert "[remove] [CHECKPOINT " in trace_result
    assert "[edit] [CHECKPOINT " in trace_result
    assert "[add] [CHECKPOINT " in trace_result
    assert "[MEMORY " in trace_result
    assert " · CREATED · RECORDED" not in trace_result
    assert " · REMOVED · RECORDED" not in trace_result
    assert "content changed · Memory identity preserved" not in trace_result
    assert "NOW" not in trace_result and "ORIGIN" not in trace_result
    assert "−" in trace_result and "+" in trace_result
    assert trace_result.count("  − ") == 1
    assert trace_result.count("  + ") == 1
    assert "  − ∅" not in trace_result and "  + ∅" not in trace_result
    assert "ITEMS" not in trace_result
    for color_index in (111, 189, 210):
        assert re.search(
            rf"\x1b\[[0-9;]*38;5;{color_index}[;m]",
            trace_raw,
        )
    assert "┏" in raw and "┗" in raw
    assert "38;" in raw
    assert any(
        "7" in codes.split(";") for codes in re.findall("\x1b\\[([0-9;]*)m", raw)
    )


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT / "src"))
        _run_child(sys.argv[2])
    else:
        main()
