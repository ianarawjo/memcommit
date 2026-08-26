"""Capture Query Answer semantic copy in a real color PTY."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import sys

import pexpect


ROOT = Path("/Users/KimMunyeong/Github/memcommit")
OUT = ROOT / "agent-records/docs/screenshots/query-tui-interface-20260815"
COLUMNS = 180
ROWS = 52
DOWN = "\x1b[B"

_BASE_PATH = (
    ROOT / "agent-records/docs/screenshots/ordinary-query-one-shot-20260813/capture.py"
)
_SPEC = importlib.util.spec_from_file_location("query_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _query_document():
    from memcommit.find_answer_references import (
        FindAnswerEvidence,
        FindAnswerSentence,
        build_find_answer_reference_document,
    )

    return build_find_answer_reference_document(
        (
            FindAnswerEvidence(
                "m1",
                "task-1/description",
                "memory",
                "2db26309-memory",
                "The Main Building is under construction.",
            ),
            FindAnswerEvidence(
                "m2",
                "task-1/participant/construction-updates",
                "memory",
                "5ab81742-memory",
                "Visitor parking moves to the east garage during construction.",
            ),
        ),
        (
            FindAnswerSentence("The Main Building is under construction.", ("m1",)),
            FindAnswerSentence("Visitor parking moves to the east garage.", ("m2",)),
            FindAnswerSentence("Use the verified updates before editing the wiki.", ("m1", "m2")),
        ),
    )


def _print_clipboard_writes(label: str, writes: list[str]) -> None:
    print(f"{label} CLIPBOARD WRITES {len(writes)}")
    for index, text in enumerate(writes, start=1):
        print(
            f"WRITE {index} · PHYSICAL LINES {len(text.splitlines())} "
            f"· UTF-8 BYTES {len(text.encode('utf-8'))}"
        )
        for line_index, line in enumerate(text.splitlines(), start=1):
            print(f"  {line_index}: {line}")


def _run_query_child(*, fail: bool = False) -> None:
    from memcommit.clipboard import ClipboardError
    from memcommit.operations.query.ordinary_application import OrdinaryQueryResponse
    from memcommit.interfaces.tui.operations.query import run_query_workbench

    writes: list[str] = []
    document = _query_document()

    def run_ordinary(request):
        return OrdinaryQueryResponse(request, document.text, True, document)

    def write(text: str) -> None:
        writes.append(text)
        if fail:
            raise ClipboardError("simulated clipboard unavailable")

    print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
    result = run_query_workbench(
        (
            "task-1",
            "task-1/description",
            "task-1/participant",
            "task-1/participant/construction-updates",
        ),
        current_context="task-1",
        initial_context="task-1",
        query_targets=(),
        run_ordinary=run_ordinary,
        run_granted=lambda _request: (_ for _ in ()).throw(AssertionError()),
        clipboard_writer=write,
    )
    print(
        "QUERY CLOSED · NO SESSION SAVE · NO SOURCE MUTATION"
        if result.status == "CLOSED"
        else f"UNEXPECTED QUERY RESULT {result!r}"
    )
    _print_clipboard_writes("QUERY", writes)
    if fail:
        print("FAILED QUERY COPY DID NOT REPLACE CLIPBOARD TEXT")
    else:
        print(
            "BODY/REFERENCE/DOCUMENT DISTINCT · "
            + (
                "YES"
                if len(writes) == 3 and len(set(writes)) == 3
                else "NO"
            )
        )


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update({"TERM": "xterm-256color", "COLORTERM": "truecolor"})
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
        timeout=15,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> None:
    _BASE._snapshot(recorder, stem)


def _capture_query() -> None:
    child, recorder = _spawn("query")
    try:
        child.expect("MEM QUERY")
        _BASE._settle(child)
        _snapshot(recorder, "01-query-entry")

        child.send("What changed during construction?")
        _BASE._settle(child)
        _snapshot(recorder, "02-query-question-entered")

        child.send("\r")
        child.expect("Main Building is under construction")
        _BASE._settle(child)
        _snapshot(recorder, "03-query-answer-body-focused")

        child.send("y")
        child.expect("COPIED")
        _BASE._settle(child)
        _snapshot(recorder, "04-query-answer-body-copied")

        child.send(DOWN)
        _BASE._settle(child)
        _snapshot(recorder, "05-query-reference-focused")

        child.send("y")
        child.expect("COPIED")
        _BASE._settle(child)
        _snapshot(recorder, "06-query-reference-copied")

        child.send("Y")
        _BASE._settle(child)
        _snapshot(recorder, "07-query-complete-answer-copied")

        child.send("\x03")
        child.expect("BODY/REFERENCE/DOCUMENT DISTINCT")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "08-query-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_query_failure() -> None:
    child, recorder = _spawn("query-failure")
    try:
        child.expect("MEM QUERY")
        child.send("What changed?\r")
        child.expect("Main Building is under construction")
        _BASE._settle(child)
        child.send("y")
        child.expect("COPY FAILED")
        _BASE._settle(child)
        _snapshot(recorder, "09-query-copy-failed")

        child.send("\x03")
        child.expect("FAILED QUERY COPY DID NOT REPLACE")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "10-query-failure-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _capture_query()
    _capture_query_failure()
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "38;" in raw
    assert "48;" in raw


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT / "src"))
        if sys.argv[2] == "query":
            _run_query_child()
        elif sys.argv[2] == "query-failure":
            _run_query_child(fail=True)
        else:
            raise SystemExit(f"unknown child kind: {sys.argv[2]}")
    else:
        main()
