"""Capture content-free Summarize and Find Recents in a real color PTY."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import re
import shutil
import sys

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/docs/screenshots/read-report-recents-20260816"
COLUMNS = 180
ROWS = 52

_BASE_PATH = (
    ROOT
    / "agent-records/docs/screenshots/context-endpoint-memory-preview-20260810/capture.py"
)
_SPEC = importlib.util.spec_from_file_location("read_report_capture_base", _BASE_PATH)
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
        "GROUND_SESSIONS_DIR": store_dir / "ground-sessions",
        "MELD_SESSIONS_DIR": store_dir / "meld-sessions",
    }
    for name, value in assignments.items():
        setattr(store_module, name, value)


def _record_recent(store, target, started_at: str) -> None:
    from memcommit.persistence.command_ledger.attempts import (
        CommandAttempt,
        CommandAttemptLedger,
    )

    uid = (
        "11111111-1111-4111-8111-111111111111"
        if target.operation == "summarize"
        else "22222222-2222-4222-8222-222222222222"
    )
    CommandAttemptLedger(store.store_dir).create(
        CommandAttempt(
            uid=uid,
            operation=target.operation,
            status="COMPLETED",
            started_at=started_at,
            completed_at=started_at,
            elapsed_seconds=0.0,
            stdin_tty=True,
            stdout_tty=True,
            details={"read_report": target.to_metadata()},
            failure=None,
        )
    )


def _context_state(store, name: str) -> tuple[bytes, tuple[str, ...]]:
    return (
        store._context_file(name).read_bytes(),
        tuple(item["uid"] for item in store.list_checkpoints(name)),
    )


def _run_child(kind: str) -> None:
    import memcommit.application.capabilities.ops as ops
    from memcommit.adapters.console.entrypoint import app
    from memcommit.application.capabilities.reviewing.memory_issue_finding.model import (
        DuplicateReport,
    )
    from memcommit.application.capabilities.reviewing.read_report import (
        ReadReportTarget,
    )
    from memcommit.persistence.store import MemoryStore

    fixture_root = OUT / f".fixture-{kind}"
    if fixture_root.exists():
        # The exact repository-local scratch path is never part of the
        # evidence. Clearing it makes repeated captures byte-for-byte stable.
        shutil.rmtree(fixture_root)
    fixture_root.mkdir(parents=True)
    try:
        _isolate_store(fixture_root)
        store = MemoryStore()
        if kind == "summarize":
            context = ops.init("reports/empty")
            store.create_context(context)
            store.set_current(context.name)
            target = ReadReportTarget(
                operation="summarize",
                context_names=(context.name,),
                target_names=(context.name,),
                selection_mode="SINGLE",
                ranges=("DIRECT", "RECURSIVE"),
            )
            command = ["summarize"]
        elif kind == "find":
            context = ops.init("reports/find")
            ops.add(
                context,
                "A single Memory makes this report provider-independent.",
            )
            store.create_context(context)
            store.set_current(context.name)
            target = ReadReportTarget(
                operation="find-duplicates",
                context_names=(context.name,),
                target_names=(context.name,),
                selection_mode="SINGLE",
                ranges=("DIRECT",),
            )
            command = ["find-duplicates"]

            # This capture verifies lifecycle composition rather than provider
            # semantics. The real command, source freeze, report workbench, and
            # close path run against a deterministic empty finding report.
            ops.find_duplicates = lambda source, *_args, **_kwargs: DuplicateReport(
                memory_count=sum(1 for _item in source.iter_items()),
                findings=(),
            )
        else:
            raise ValueError(f"Unknown capture kind: {kind}")

        _record_recent(store, target, "2026-08-16T12:00:00+00:00")
        before = _context_state(store, context.name)
        size = os.get_terminal_size()
        assert (size.columns, size.lines) == (COLUMNS, ROWS)
        print("PTY", size.columns, size.lines)
        app(args=command, prog_name="mem", standalone_mode=False)
        assert _context_state(store, context.name) == before
        print(
            f"{kind.upper()} CLOSED · READ REPORT RECENT REVALIDATED · "
            "CONTEXT BYTES UNCHANGED · CHECKPOINTS UNCHANGED"
        )
    finally:
        shutil.rmtree(fixture_root)


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            # The fixture publishes the one prior completed attempt itself.
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
        timeout=30,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> None:
    _BASE._snapshot(recorder, stem)


def _capture_summarize() -> None:
    child, recorder = _spawn("summarize")
    try:
        child.expect("MEM SUMMARIZE · RECENTS OR SELECT")
        _BASE._settle(child)
        _snapshot(recorder, "01-summarize-recent-entry")

        child.send("\r")
        child.expect("MEM SUMMARIZE")
        _BASE._settle(child)
        _snapshot(recorder, "02-summarize-target-revalidated")

        child.send("s")
        child.expect("BOTH VIEWS")
        _BASE._settle(child)
        _snapshot(recorder, "03-summarize-both-results")

        child.send("q")
        child.expect("SUMMARIZE CLOSED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "04-summarize-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_find() -> None:
    child, recorder = _spawn("find")
    try:
        child.expect("MEM FIND DUPLICATES · RECENTS OR SELECT")
        _BASE._settle(child)
        _snapshot(recorder, "05-find-recent-entry")

        child.send("\r")
        child.expect(re.compile("FIND DUPLICATES|DUPLICATE FINDINGS"))
        _BASE._settle(child)
        _snapshot(recorder, "06-find-report")

        child.send("q")
        child.expect("FIND CLOSED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "07-find-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _capture_summarize()
    _capture_find()
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "PTY 180 52" in raw
    assert "Report and Memory content are not copied into Recents" in raw
    assert "DIRECT + RECURSIVE" in raw
    assert "FIND DUPLICATES · DIRECT" in raw
    assert "CONTEXT BYTES UNCHANGED · CHECKPOINTS UNCHANGED" in raw
    assert "\x1b[" in raw and "38;" in raw


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT / "src"))
        _run_child(sys.argv[2])
    else:
        main()
