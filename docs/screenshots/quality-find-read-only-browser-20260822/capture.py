"""Capture the compact read-only quality-finding browser in a 180x52 PTY."""

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

_BASE_PATH = ROOT / "docs/screenshots/atomize-memory-selection-20260814/capture.py"
_SPEC = importlib.util.spec_from_file_location("quality_find_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _source():
    from memcommit.context import Context, Memory

    context = Context(
        uid="00000000-0000-4000-8000-000000000701",
        name="study/reporting",
    )
    memories = (
        Memory(
            uid="00000000-0000-4000-8000-000000000711",
            content="Report the incident within 30 days.",
        ),
        Memory(
            uid="00000000-0000-4000-8000-000000000712",
            content="Notify the office no later than one month after discovery.",
        ),
        Memory(
            uid="00000000-0000-4000-8000-000000000713",
            content="The accessible entrance remains open during office hours.",
        ),
    )
    for memory in memories:
        context.add(memory)
    return context, memories


def _session(kind: str, *, empty: bool = False):
    from memcommit.findings import (
        AmbiguityFinding,
        AmbiguityReport,
        ConflictFinding,
        ConflictReport,
        DuplicateFinding,
        DuplicateReport,
    )
    from memcommit.quality_find_workbench import create_quality_find_workbench

    context, (first, second, third) = _source()
    if kind == "ambiguities":
        findings = () if empty else (
            AmbiguityFinding(
                memory=first,
                interpretation="DOMINANT",
                clarification="REQUIRED",
                ordinary_readings=(
                    "Thirty days after the incident.",
                    "Thirty days after discovery.",
                    "Thirty days after notification.",
                ),
                reason="The deadline does not identify which event starts the clock.",
                question="Which event starts the 30-day period?",
            ),
        )
        report = AmbiguityReport(memory_count=3, findings=findings)
    elif kind == "conflicts":
        report = ConflictReport(
            memory_count=3,
            pair_count=3,
            findings=(
                ConflictFinding(
                    left=first,
                    right=second,
                    conflict="MAY",
                    scope_dimensions=("TIME",),
                    reason="The deadlines can disagree when discovery occurs after the incident.",
                    question="Which event governs the reporting deadline?",
                ),
            ),
        )
    elif kind == "duplicates":
        report = DuplicateReport(
            memory_count=3,
            findings=(
                DuplicateFinding(
                    left=first,
                    right=second,
                    relation="SEMANTIC_EQUIVALENT",
                    reason="Both Memories impose the same reporting window in this frame.",
                ),
                DuplicateFinding(
                    left=second,
                    right=third,
                    relation="OVERLAP",
                    reason="The Memories share operational context but are not substitutes.",
                ),
            ),
        )
    else:
        raise ValueError(kind)
    return context, create_quality_find_workbench(kind, context, report)


def _run_child(kind: str) -> None:
    from memcommit.interfaces.tui.workbenches.findings import run_quality_find_browser
    from memcommit.quality_find_workbench import quality_find_report_view

    empty = kind == "empty"
    report_kind = "ambiguities" if empty else kind
    context, session = _session(report_kind, empty=empty)
    operation = {
        "ambiguities": "FIND AMBIGUITIES",
        "conflicts": "FIND CONFLICTS",
        "duplicates": "FIND REDUNDANCIES",
    }[report_kind]
    handoff = report_kind in {"conflicts", "duplicates"} and not empty
    view = quality_find_report_view(
        session,
        context,
        operation_label=operation,
        handoff_available=handoff,
    )
    before = session.context_digest
    print(f"$ mem {operation.lower().replace(' ', '-')} --context {context.name}")
    print(
        f"PTY · {os.get_terminal_size().columns} COLUMNS × "
        f"{os.get_terminal_size().lines} ROWS",
        flush=True,
    )
    receipt = run_quality_find_browser(view)
    print()
    print(f"BROWSER RECEIPT · {receipt.action} · {receipt.item_uid or 'NO TARGET'}")
    print("READ-ONLY VERIFICATION")
    print(f"  RESPONSE STATE · {len(session.responses)}")
    print(f"  SOURCE DIGEST UNCHANGED · {session.context_digest == before}")
    print(f"  SOURCE MEMORIES · {len(context.memories)}")
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


def _spawn(kind: str) -> tuple[pexpect.spawn, io.StringIO]:
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


def _capture_ambiguity() -> None:
    child, recorder = _spawn("ambiguities")
    try:
        child.expect("FIND AMBIGUITIES .* FINDINGS")
        _BASE._settle(child)
        _BASE._snapshot(recorder, "01-ambiguity-compact-list")

        child.send("\r")
        child.expect("POSSIBLE READINGS")
        _BASE._settle(child)
        _BASE._snapshot(recorder, "02-ambiguity-read-only-detail")

        child.send("\x1b")
        _BASE._settle(child)
        _BASE._snapshot(recorder, "03-ambiguity-one-level-back")

        child.send("\x1b")
        child.expect("BROWSER RECEIPT .* CLOSE")
        child.expect("CHECKPOINTS .* 0")
        child.expect(pexpect.EOF)
        _BASE._snapshot(recorder, "04-ambiguity-close-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_handoff(kind: str, key: str, stems: tuple[str, str, str]) -> None:
    child, recorder = _spawn(kind)
    label = "FIND CONFLICTS" if kind == "conflicts" else "FIND REDUNDANCIES"
    try:
        child.expect(label + " .* FINDINGS")
        _BASE._settle(child)
        _BASE._snapshot(recorder, stems[0])

        child.send("\r")
        child.expect("FOLLOW-UP QUESTION" if kind == "conflicts" else "WHY THESE MEMORIES")
        _BASE._settle(child)
        _BASE._snapshot(recorder, stems[1])

        child.send(key)
        child.expect("BROWSER RECEIPT .* HANDOFF")
        child.expect(pexpect.EOF)
        _BASE._snapshot(recorder, stems[2])
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_empty() -> None:
    child, recorder = _spawn("empty")
    try:
        child.expect("NO FINDINGS")
        _BASE._settle(child)
        _BASE._snapshot(recorder, "11-empty-report")
        child.send("q")
        child.expect("BROWSER RECEIPT .* CLOSE")
        child.expect("CHECKPOINTS .* 0")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for suffix in ("*.png", "*.txt", "*.typescript"):
        for path in OUT.glob(suffix):
            path.unlink()
    _capture_ambiguity()
    _capture_handoff(
        "conflicts",
        "r",
        (
            "05-conflict-compact-list",
            "06-conflict-source-linked-detail",
            "07-conflict-resolve-handoff-verification",
        ),
    )
    _capture_handoff(
        "duplicates",
        "d",
        (
            "08-redundancy-compact-list",
            "09-redundancy-source-linked-detail",
            "10-redundancy-dedun-handoff-verification",
        ),
    )
    _capture_empty()
    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("PTY stream did not contain expected true-color ANSI.")
    for stem in (
        "04-ambiguity-close-verification",
        "07-conflict-resolve-handoff-verification",
        "10-redundancy-dedun-handoff-verification",
    ):
        plain = (OUT / f"{stem}.txt").read_text(encoding="utf-8")
        if "RESPONSE STATE · 0" not in plain or "CHECKPOINTS · 0" not in plain:
            raise RuntimeError(f"Read-only verification is incomplete for {stem}.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        _run_child(sys.argv[2])
    else:
        main()
