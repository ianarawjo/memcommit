"""Capture comprehensive read-only Audit Review in a 180x52 color PTY."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import sys

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52
DOWN = "\x1b[B"

_BASE_PATH = (
    ROOT / "agent-records/docs/screenshots/atomize-memory-selection-20260814/capture.py"
)
_SPEC = importlib.util.spec_from_file_location("audit_review_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _session(*, empty: bool):
    from memcommit.core.context import Context, Memory
    from memcommit.application.capabilities.reviewing.memory_issue_finding.model import (
        AmbiguityFinding,
        AmbiguityReport,
        ConflictFinding,
        ConflictReport,
        DuplicateFinding,
        DuplicateReport,
    )
    from memcommit.providers.types import ProviderIdentity
    from memcommit.application.operations.audit.application import create_quality_audit
    from memcommit.application.operations.audit.model import (
        QUALITY_AUDIT_RULESETS,
        QualityAuditCheck,
        QualityAuditProvenance,
    )

    context = Context(
        uid="00000000-0000-4000-8000-000000000801",
        name="study/audit-source",
    )
    duplicate_first = Memory(
        uid="a31f02c1-0000-4000-8000-000000000811",
        content="Report the incident to the office within 30 days of discovery.",
    )
    duplicate_second = Memory(
        uid="5ce891d4-0000-4000-8000-000000000812",
        content="Notify the office no later than 30 days after discovering the incident.",
    )
    underspecified = Memory(
        uid="7b94ee10-0000-4000-8000-000000000813",
        content="Contact the coordinator before entering.",
    )
    ambiguous = Memory(
        uid="32c71f88-0000-4000-8000-000000000814",
        content="The accessible entrance remains open during office hours.",
    )
    conflict_first = Memory(
        uid="f58d1a77-0000-4000-8000-000000000815",
        content="The main entrance opens at 08:00.",
    )
    conflict_second = Memory(
        uid="ce683206-0000-4000-8000-000000000816",
        content="The main entrance remains closed until 09:00.",
    )
    for memory in (
        duplicate_first,
        duplicate_second,
        underspecified,
        ambiguous,
        conflict_first,
        conflict_second,
    ):
        context.add(memory)

    def provenance(kind: str) -> QualityAuditProvenance:
        return QualityAuditProvenance(
            operation=f"find_{kind}",
            provider_called=True,
            identity=ProviderIdentity(provider="capture", model="audit-model"),
        )

    duplicate_findings = (
        ()
        if empty
        else (
            DuplicateFinding(
                duplicate_first,
                duplicate_second,
                "SEMANTIC_EQUIVALENT",
                "Both Memories impose the same recipient and reporting window.",
            ),
        )
    )
    ambiguity_findings = (
        ()
        if empty
        else (
            AmbiguityFinding(
                underspecified,
                "SINGLE",
                "REQUIRED",
                ("Contact the responsible coordinator before entering.",),
                "No coordinator identity or contact route is provided.",
                "Who is the coordinator and how can they be contacted?",
            ),
            AmbiguityFinding(
                ambiguous,
                "COMPETING",
                "HELPFUL",
                (
                    "The entrance follows the staffed office schedule.",
                    "The entrance follows the published public-office schedule.",
                ),
                "Office hours can refer to two different schedules.",
                "Which schedule defines office hours?",
            ),
        )
    )
    conflict_findings = (
        ()
        if empty
        else (
            ConflictFinding(
                conflict_first,
                conflict_second,
                "YES",
                "The same entrance cannot be open at 08:00 and closed until 09:00.",
                "Which opening time is authoritative?",
            ),
        )
    )
    session = create_quality_audit(
        context,
        (
            QualityAuditCheck(
                "duplicates",
                QUALITY_AUDIT_RULESETS["duplicates"],
                DuplicateReport(6, duplicate_findings),
                provenance("duplicates"),
            ),
            QualityAuditCheck(
                "ambiguities",
                QUALITY_AUDIT_RULESETS["ambiguities"],
                AmbiguityReport(6, ambiguity_findings),
                provenance("ambiguities"),
            ),
            QualityAuditCheck(
                "conflicts",
                QUALITY_AUDIT_RULESETS["conflicts"],
                ConflictReport(6, 15, conflict_findings),
                provenance("conflicts"),
            ),
        ),
        uid="00000000-0000-4000-8000-000000000899",
        created_at="2026-08-22T12:00:00+00:00",
    )
    return session


def _run_child(kind: str, store_root: Path) -> None:
    from memcommit.adapters.console.commands.audit.command import (
        run_quality_audit_review,
    )
    from memcommit.application.operations.audit.model import quality_audit_record_digest
    from memcommit.persistence.store import MemoryStore

    session = _session(empty=kind == "empty")
    before = quality_audit_record_digest(session)
    print(f"$ mem review audit --session {session.uid}")
    print(
        f"PTY · {os.get_terminal_size().columns} COLUMNS × "
        f"{os.get_terminal_size().lines} ROWS",
        flush=True,
    )
    run_quality_audit_review(MemoryStore(root=store_root), session)
    print("AUDIT REVIEW CLOSED · READ-ONLY")
    print(
        f"  RECORD DIGEST UNCHANGED · {quality_audit_record_digest(session) == before}"
    )
    print(f"  HISTORICAL NOTES · {session.answered_count}")
    print("  RESPONSE WRITES · 0")
    print("  PROVIDER CALLS · 0")
    print("  CONTEXT WRITES · 0")
    print("  CHECKPOINTS · 0", flush=True)


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PROMPT_TOOLKIT_COLOR_DEPTH": "DEPTH_24_BIT",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _spawn(kind: str, store_root: Path) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind, str(store_root)],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _capture_full(store_root: Path) -> None:
    child, recorder = _spawn("full", store_root)
    try:
        child.expect("SAVED .* 3/3 CHECKS .* READ-ONLY REPORT")
        _BASE._settle(child)
        _BASE._snapshot(recorder, "01-compact-overview-and-source")

        child.send(DOWN)
        _BASE._settle(child)
        _BASE._snapshot(recorder, "02-duplicate-check-header")

        child.send(DOWN)
        _BASE._settle(child)
        _BASE._snapshot(recorder, "03-duplicate-one-line-evidence")

        child.send(DOWN)
        _BASE._settle(child)
        _BASE._snapshot(recorder, "04-ambiguity-check-header")

        child.send(DOWN)
        _BASE._settle(child)
        _BASE._snapshot(recorder, "05-first-ambiguity-finding")

        child.send(DOWN)
        _BASE._settle(child)
        _BASE._snapshot(recorder, "06-second-ambiguity-finding")

        child.send(DOWN)
        _BASE._settle(child)
        _BASE._snapshot(recorder, "07-conflict-check-header")

        child.send(DOWN)
        _BASE._settle(child)
        _BASE._snapshot(recorder, "08-conflict-one-line-evidence")

        child.send(DOWN)
        _BASE._settle(child)
        _BASE._snapshot(recorder, "09-compact-provenance")

        child.send(DOWN)
        _BASE._settle(child)
        _BASE._snapshot(recorder, "10-explicit-read-only-boundary")

        child.send("q")
        child.expect("AUDIT REVIEW CLOSED .* READ-ONLY")
        child.expect(pexpect.EOF)
        _BASE._snapshot(recorder, "11-close-no-write-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_empty(store_root: Path) -> None:
    child, recorder = _spawn("empty", store_root)
    try:
        child.expect("0/6 MEMORIES FLAGGED")
        _BASE._settle(child)
        _BASE._snapshot(recorder, "12-zero-finding-complete-report")
        child.send("q")
        child.expect("AUDIT REVIEW CLOSED .* READ-ONLY")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    import tempfile

    OUT.mkdir(parents=True, exist_ok=True)
    for suffix in ("*.png", "*.txt", "*.typescript"):
        for path in OUT.glob(suffix):
            path.unlink()
    with tempfile.TemporaryDirectory(prefix="memcommit-audit-review-") as directory:
        root = Path(directory)
        _capture_full(root / "full-store")
        _capture_empty(root / "empty-store")
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("PTY stream did not contain expected true-color ANSI.")
    verification = (OUT / "11-close-no-write-verification.txt").read_text(
        encoding="utf-8"
    )
    for expected in (
        "RECORD DIGEST UNCHANGED · True",
        "RESPONSE WRITES · 0",
        "PROVIDER CALLS · 0",
        "CONTEXT WRITES · 0",
        "CHECKPOINTS · 0",
    ):
        if expected not in verification:
            raise RuntimeError(f"Missing Audit Review verification: {expected}")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        _run_child(sys.argv[2], Path(sys.argv[3]))
    else:
        main()
