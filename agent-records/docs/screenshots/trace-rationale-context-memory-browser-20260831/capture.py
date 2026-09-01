"""Capture the Trace/Rationale exact Context-or-Memory browser contract."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import os
from pathlib import Path
import re
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[4]
OUT = (
    ROOT
    / "agent-records/docs/screenshots/trace-rationale-context-memory-browser-20260831"
)
COLUMNS = 180
ROWS = 52
DOWN = "\x1b[B"

_BASE_PATH = (
    ROOT
    / "agent-records/docs/screenshots/mem-help-a-z-boundary-20260813/capture_help_a_z.py"
)
_SPEC = importlib.util.spec_from_file_location("history_browser_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLS = COLUMNS
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
        "GROUND_SESSIONS_DIR": store_dir / "ground-sessions",
        "MELD_SESSIONS_DIR": store_dir / "meld-sessions",
    }
    for name, value in assignments.items():
        setattr(store_module, name, value)


def _durable_digest(root: Path) -> str:
    """Hash Context/checkpoint/current state while excluding non-authority caches."""

    digest = hashlib.sha256()
    store_dir = root / ".mem"
    paths = [store_dir / "state.json"]
    contexts = store_dir / "contexts"
    if contexts.is_dir():
        paths.extend(sorted(path for path in contexts.rglob("*") if path.is_file()))
    for path in paths:
        if not path.is_file():
            continue
        digest.update(path.relative_to(store_dir).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _prepare_fixture() -> str:
    from memcommit.adapters.console.commands.add.command import cmd as add
    from memcommit.adapters.console.commands.edit.command import cmd as edit
    from memcommit.adapters.console.commands.init.command import cmd as init
    from memcommit.adapters.console.commands.switch.command import cmd as switch
    from memcommit.core.context import Memory
    from memcommit.persistence.store import MemoryStore

    init("empty", parents=False)
    init("notes", parents=False)
    add(
        "Initial policy wording retained for provenance.",
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
    edit(
        memory.uid,
        "Final policy wording selected for exact Memory history.",
        input_source=None,
        context_name=None,
    )
    add(
        "A supporting Memory keeps the whole Context report visibly distinct.",
        input_source=None,
        paste=False,
        context_name=None,
    )
    init("notes/child", parents=False)
    add(
        "A child Memory is browseable without broadening the selected parent.",
        input_source=None,
        paste=False,
        context_name=None,
    )
    switch("notes")
    return memory.uid


class _RationaleProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        if operation == "context rationale":
            return (
                '{"provenance":"Recorded Add and Edit operations explain how '
                'this exact Context reached its current direct state."}'
            )
        return (
            '{"provenance":"The retained Add introduced this Memory and the '
            'recorded Edit produced its current wording."}'
        )


def _run_child(mode: str) -> None:
    from memcommit.adapters.console.commands.rationale import command as rationale
    from memcommit.adapters.console.commands.trace import command as trace
    from memcommit.adapters.console.commands.switch.command import cmd as switch
    from memcommit.persistence.store import MemoryStore

    with tempfile.TemporaryDirectory(prefix="memcommit-history-browser-") as raw:
        fixture_root = Path(raw)
        _isolate_store(fixture_root)
        memory_uid = _prepare_fixture()
        if mode == "empty":
            switch("empty")
        rationale.connect_semantic_provider = _RationaleProvider
        before = _durable_digest(fixture_root)
        print(f"LIVE COLOR PTY · {os.get_terminal_size().columns}x{os.get_terminal_size().lines}")
        print(f"PROFILE · ISOLATED CAPTURE · CURRENT · {MemoryStore().current_context_name()}")
        print(f"$ mem {'trace' if mode.startswith('trace') or mode == 'empty' else 'rationale'}")

        if mode in {"empty", "trace-memory", "trace-context"}:
            trace.cmd()
        elif mode in {"rationale-memory", "rationale-context"}:
            rationale.cmd()
        else:
            raise ValueError(f"Unknown capture mode: {mode}")

        assert _durable_digest(fixture_root) == before
        print(
            "READ-ONLY VERIFICATION · "
            f"MODE {mode.upper()} · TARGET [{memory_uid[:8]}] · "
            f"CURRENT {MemoryStore().current_context_name()} · "
            "CONTEXTS + CHECKPOINTS + CURRENT POINTER UNCHANGED"
        )


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PROMPT_TOOLKIT_NO_CPR": "1",
            "PYTHONPATH": str(ROOT / "src"),
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _spawn(mode: str) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", mode],
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


def _capture_empty() -> None:
    child, recorder = _spawn("empty")
    try:
        child.expect("TRACE · SELECT A CONTEXT OR MEMORY · empty")
        _BASE._pump(child, seconds=0.7)
        _snapshot(recorder, "01-trace-empty-context-browser")
        child.send("q")
        child.expect("READ-ONLY VERIFICATION")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "02-trace-empty-cancel-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_trace_memory() -> None:
    child, recorder = _spawn("trace-memory")
    try:
        child.expect("TRACE · SELECT A CONTEXT OR MEMORY · notes")
        _BASE._pump(child, seconds=0.7)
        _snapshot(recorder, "03-trace-browser-context-focused")
        child.send(DOWN)
        _BASE._pump(child, seconds=0.7)
        _snapshot(recorder, "04-trace-browser-memory-focused")
        child.send("\r")
        child.expect("TRACE REPORT")
        _BASE._pump(child, seconds=0.7)
        _snapshot(recorder, "05-trace-memory-result-viewer")
        child.send("q")
        child.expect("READ-ONLY VERIFICATION")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "06-trace-memory-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_trace_context() -> None:
    child, recorder = _spawn("trace-context")
    try:
        child.expect("TRACE · SELECT A CONTEXT OR MEMORY · notes")
        _BASE._pump(child, seconds=0.7)
        child.send("\r")
        child.expect("CONTEXT LINEAGE")
        child.expect("TRACE REPORT")
        _BASE._pump(child, seconds=0.7)
        _snapshot(recorder, "07-trace-context-result-viewer")
        child.send("q")
        child.expect("READ-ONLY VERIFICATION")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "08-trace-context-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_rationale_memory() -> None:
    child, recorder = _spawn("rationale-memory")
    try:
        child.expect("RATIONALE · SELECT A CONTEXT OR MEMORY · notes")
        _BASE._pump(child, seconds=0.7)
        _snapshot(recorder, "09-rationale-browser-context-focused")
        child.send(DOWN)
        _BASE._pump(child, seconds=0.7)
        _snapshot(recorder, "10-rationale-browser-memory-focused")
        child.send("\r")
        child.expect("READ-ONLY VERIFICATION")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "11-rationale-memory-result-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_rationale_context() -> None:
    child, recorder = _spawn("rationale-context")
    try:
        child.expect("RATIONALE · SELECT A CONTEXT OR MEMORY · notes")
        _BASE._pump(child, seconds=0.7)
        child.send("\r")
        child.expect("READ-ONLY VERIFICATION")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "12-rationale-context-result-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for pattern in ("*.png", "*.txt", "*.typescript"):
        for path in OUT.glob(pattern):
            path.unlink()
    _capture_empty()
    _capture_trace_memory()
    _capture_trace_context()
    _capture_rationale_memory()
    _capture_rationale_context()

    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    plain = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.txt"))
    assert "LIVE COLOR PTY · 180x52" in raw
    assert "SELECT A CONTEXT OR MEMORY" in plain
    assert "CONTEXT NOT SELECTABLE" not in plain
    assert "INCLUDE DESCENDANTS" not in plain
    assert "RECENT" not in plain
    assert "RANGE" not in plain
    assert "Trace cancelled." in plain
    assert "TRACE REPORT" in plain
    assert "CONTEXT LINEAGE" in plain
    assert "Rationale [" in plain
    assert "Rationale · notes" in plain
    assert plain.count("READ-ONLY VERIFICATION") == 5
    assert re.search(r"\x1b\[[0-9;]*38;(?:2|5);", raw) is not None
    assert re.search(r"\x1b\[[0-9;]*48;(?:2|5);", raw) is not None


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        _run_child(sys.argv[2])
    else:
        main()
