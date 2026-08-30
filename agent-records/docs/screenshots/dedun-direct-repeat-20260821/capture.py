"""Capture repeated Dedun execution without a Recents or setup screen."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/docs/screenshots/dedun-direct-repeat-20260821"
COLUMNS = 180
ROWS = 52

_BASE_PATH = (
    ROOT
    / "agent-records/docs/screenshots/context-endpoint-memory-preview-20260810/capture.py"
)
_SPEC = importlib.util.spec_from_file_location("dedun_direct_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _configure_isolated_store(store_root: Path) -> None:
    import memcommit.persistence.store as store_module

    values = {
        "STORE_DIR": store_root,
        "CONTEXTS_DIR": store_root / "contexts",
        "QUERY_SOURCES_DIR": store_root / "query-sources",
        "STATE_FILE": store_root / "state.json",
        "IMPACT_PLAN_FILE": store_root / "impact-plan.json",
        "STAGED_UPDATE_FILE": store_root / "staged-update.json",
        "REVIEW_SESSION_FILE": store_root / "review-session.json",
        "ATOMIZE_ANALYSES_DIR": store_root / "atomize-analyses",
        "ATOMIZE_WORKBENCHES_DIR": store_root / "atomize-workbenches",
        "GROUND_SESSIONS_DIR": store_root / "ground-sessions",
        "MELD_SESSIONS_DIR": store_root / "meld-sessions",
    }
    for name, value in values.items():
        setattr(store_module, name, value)


def _initialize() -> None:
    from memcommit.core.context import Context, Memory
    from memcommit.persistence.store import MemoryStore

    context = Context(
        uid="10000000-0000-4000-8000-000000000310",
        name="quality/direct-dedun",
    )
    context.add(
        Memory(
            uid="20000000-0000-4000-8000-000000000310",
            content="The east entrance opens at 8 a.m.",
        )
    )
    context.add(
        Memory(
            uid="20000000-0000-4000-8000-000000000320",
            content="The eastern doorway opens at eight in the morning.",
        )
    )
    store = MemoryStore()
    store.create_context(context)
    store.set_current(context.name)


def _run_child() -> None:
    import click

    import memcommit.application.operations.find_redundancies.application as find_application
    from memcommit.adapters.console.entrypoint import app
    from memcommit.application.capabilities.memory_issue_analysis.model import (
        DuplicateFinding,
        DuplicateReport,
    )
    from memcommit.application.capabilities.reviewing.read_report_recents import (
        read_report_recents,
    )
    from memcommit.persistence.store import MemoryStore

    with tempfile.TemporaryDirectory(prefix="dedun-direct-repeat-") as directory:
        _configure_isolated_store(Path(directory) / ".mem")
        _initialize()
        analysis_calls = 0

        def analyze(context, *_args, **_kwargs):
            nonlocal analysis_calls
            analysis_calls += 1
            memories = tuple(context.iter_items())
            if len(memories) < 2:
                return DuplicateReport(memory_count=len(memories), findings=())
            return DuplicateReport(
                memory_count=2,
                findings=(
                    DuplicateFinding(
                        left=memories[0],
                        right=memories[1],
                        relation="SEMANTIC_EQUIVALENT",
                        reason="Both Memories state the same entrance opening time.",
                    ),
                ),
            )

        find_application.detect_redundancies = analyze
        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)

        for ordinal in ("FIRST", "SECOND"):
            exit_code = 0
            try:
                returned = app(args=["dedun"], prog_name="mem", standalone_mode=False)
            except click.exceptions.Exit as error:
                exit_code = error.exit_code
            else:
                if isinstance(returned, int):
                    exit_code = returned
            print(f"{ordinal} COMMAND EXIT · {exit_code}")
            print(f"{ordinal} COMMAND COMPLETE · PRESS ENTER", flush=True)
            sys.stdin.readline()

        store = MemoryStore()
        context = store.load_direct("quality/direct-dedun")
        print(
            "READ-ONLY VERIFICATION · "
            f"MEMORIES {len(context.memories)} · "
            f"CHECKPOINTS {len(store.list_checkpoints(context.name))} · "
            f"DEDUN RECENTS {len(read_report_recents(store, operation='dedun'))} · "
            f"ANALYSES {analysis_calls} · CURRENT {store.current_context_name()}",
            flush=True,
        )
        sys.stdin.readline()


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.pop("MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG", None)
    environment.update({"TERM": "xterm-256color", "COLORTERM": "truecolor"})
    return environment


def _spawn() -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child"],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=25,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> str:
    _BASE._snapshot(recorder, stem)
    return (OUT / f"{stem}.txt").read_text(encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    child, recorder = _spawn()
    try:
        child.expect("FIRST COMMAND COMPLETE")
        first = _snapshot(recorder, "01-first-direct-apply")
        assert "Dedun 'quality/direct-dedun'" in first
        assert "review: mem review dedun --receipt" in first

        child.send("\r")
        child.expect("SECOND COMMAND COMPLETE")
        second = _snapshot(recorder, "02-second-direct-noop")
        assert "No applicable semantic redundancies" in second
        assert "RECENTS OR SELECT" not in second
        assert "SELECT A TARGET" not in second

        child.send("\r")
        child.expect("READ-ONLY VERIFICATION")
        verification = _snapshot(recorder, "03-read-only-verification")
        assert "MEMORIES 1" in verification
        assert "CHECKPOINTS 1" in verification
        assert "DEDUN RECENTS 1" in verification
        assert "ANALYSES 2" in verification
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)

    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "PTY 180 52" in raw
    assert "\x1b[" in raw
    assert "\x1b[32" in raw or "38;" in raw


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT / "src"))
        _run_child()
    else:
        main()
