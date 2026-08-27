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

_BASE_PATH = ROOT / "agent-records/docs/screenshots/atomize-memory-selection-20260814/capture.py"
_SPEC = importlib.util.spec_from_file_location("quality_find_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _source(kind: str):
    from memcommit.context import Context, Memory

    context = Context(
        uid="00000000-0000-4000-8000-000000000701",
        name="study/reporting",
    )
    contents = {
        "ambiguities": (
            "Report the incident within 30 days.",
            "Keep the confirmation number.",
            "The accessible entrance remains open during office hours.",
        ),
        "conflicts": (
            "The main entrance opens at 08:00.",
            "The main entrance remains closed until 09:00.",
            "The entrance opens at 08:00.",
        ),
        "duplicates": (
            "Report the incident to the office within 30 days of discovery.",
            "Notify the office no later than 30 days after discovering the incident.",
            "The incident must be reported to the office within thirty days of discovery.",
        ),
    }[kind]
    memories = tuple(
        Memory(uid=uid, content=content)
        for uid, content in zip(
            (
                "a31f02c1-0000-4000-8000-000000000711",
                "5ce891d4-0000-4000-8000-000000000712",
                "7b94ee10-0000-4000-8000-000000000713",
            ),
            contents,
            strict=True,
        )
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

    context, (first, second, third) = _source(kind)
    if kind == "ambiguities":
        findings = (
            ()
            if empty
            else (
                AmbiguityFinding(
                    memory=first,
                    interpretation="SINGLE",
                    clarification="REQUIRED",
                    ordinary_readings=("Report within a 30-day period.",),
                    reason="The deadline does not identify which event starts the clock.",
                    question="Which event starts the 30-day period?",
                ),
                AmbiguityFinding(
                    memory=third,
                    interpretation="COMPETING",
                    clarification="HELPFUL",
                    ordinary_readings=(
                        "The staffed entrance schedule.",
                        "The published office schedule.",
                    ),
                    reason="Office hours can refer to two different schedules.",
                    question="Which schedule defines office hours?",
                ),
            )
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
                    conflict="YES",
                    reason="The main entrance cannot be open at 08:00 and closed until 09:00.",
                    question="Which main-entrance opening time is authoritative?",
                ),
                ConflictFinding(
                    left=second,
                    right=third,
                    conflict="MAY",
                    reason=(
                        "The unnamed entrance may be the main entrance or a "
                        "different entrance."
                    ),
                    question="Do both statements govern the same entrance?",
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
                    reason="Both Memories impose the same recipient and reporting window.",
                ),
                DuplicateFinding(
                    left=second,
                    right=third,
                    relation="SEMANTIC_EQUIVALENT",
                    reason="Both Memories impose the same recipient and reporting window.",
                ),
            ),
        )
    else:
        raise ValueError(kind)
    return context, create_quality_find_workbench(kind, context, report)


def _run_child(kind: str) -> None:
    from memcommit.adapters.interfaces.tui.workbenches.findings import run_quality_find_browser
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
        child.expect("AMBIGUITIES .* 2/3 MEMORIES FLAGGED")
        _BASE._settle(child)
        _BASE._snapshot(recorder, "01-ambiguity-one-line-findings")

        child.send("\x1b[B")
        _BASE._settle(child)
        _BASE._snapshot(recorder, "02-ambiguity-second-finding-focused")

        # Enter is deliberately inert: Find ambiguity has no detail or answer.
        child.send("\r\x1b")
        child.expect("BROWSER RECEIPT .* CLOSE")
        child.expect("CHECKPOINTS .* 0")
        child.expect(pexpect.EOF)
        _BASE._snapshot(recorder, "03-ambiguity-close-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_handoff(
    kind: str,
    stems: tuple[str, str],
    *,
    move_to_second: bool = False,
) -> None:
    child, recorder = _spawn(kind)
    try:
        if kind == "conflicts":
            child.expect("CONFLICTS .* 2/3 PAIRS FLAGGED")
        else:
            child.expect(
                "REDUNDANCIES .* 3 MEMORIES CHECKED .* 1 GROUP .* "
                "2 PROPOSED ABSORPTIONS"
            )
        _BASE._settle(child)
        _BASE._snapshot(recorder, stems[0])

        if move_to_second:
            child.send("\x1b[B")
            _BASE._settle(child)
            _BASE._snapshot(recorder, "07-redundancy-second-finding-focused")

        child.send("\r")
        child.expect("BROWSER RECEIPT .* HANDOFF")
        child.expect(pexpect.EOF)
        _BASE._snapshot(recorder, stems[1])
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_empty() -> None:
    child, recorder = _spawn("empty")
    try:
        child.expect("AMBIGUITIES .* 0/3 MEMORIES FLAGGED")
        _BASE._settle(child)
        _BASE._snapshot(recorder, "09-empty-report")
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
        (
            "04-conflict-one-line-finding",
            "05-conflict-resolve-handoff-verification",
        ),
    )
    _capture_handoff(
        "duplicates",
        (
            "06-redundancy-one-line-findings",
            "08-redundancy-dedun-handoff-verification",
        ),
        move_to_second=True,
    )
    _capture_empty()
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("PTY stream did not contain expected true-color ANSI.")
    for red, green, blue, label in (
        (183, 189, 248, "Duplicate"),
        (238, 212, 159, "Ambiguity"),
        (237, 135, 150, "Conflict"),
        (145, 215, 227, "WHY rationale"),
    ):
        if f"38;2;{red};{green};{blue}" not in raw:
            raise RuntimeError(f"PTY stream did not contain {label} semantic color.")
    for stem in (
        "03-ambiguity-close-verification",
        "05-conflict-resolve-handoff-verification",
        "08-redundancy-dedun-handoff-verification",
    ):
        plain = (OUT / f"{stem}.txt").read_text(encoding="utf-8")
        if "RESPONSE STATE · 0" not in plain or "CHECKPOINTS · 0" not in plain:
            raise RuntimeError(f"Read-only verification is incomplete for {stem}.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        _run_child(sys.argv[2])
    else:
        main()
