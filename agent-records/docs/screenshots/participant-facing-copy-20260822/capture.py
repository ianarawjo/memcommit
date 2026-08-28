"""Capture participant-facing Query, Search, and Find copy in a color PTY."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import sys
import time

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

_BASE_PATH = ROOT / "agent-records/docs/screenshots/ordinary-query-one-shot-20260813/capture.py"
_SPEC = importlib.util.spec_from_file_location("participant_copy_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _verify_pty() -> None:
    size = os.get_terminal_size()
    if (size.columns, size.lines) != (COLUMNS, ROWS):
        raise RuntimeError(f"Expected {COLUMNS}x{ROWS} PTY, received {size.columns}x{size.lines}.")
    print(f"PTY · {size.columns} COLUMNS × {size.lines} ROWS", flush=True)


def _run_query_child() -> None:
    from memcommit.adapters.interfaces.tui.operations.query import run_query_workbench
    from memcommit.application.operations.query.ordinary_application import OrdinaryQueryResponse

    _verify_pty()

    def answer(request):
        time.sleep(0.8)
        return OrdinaryQueryResponse(
            request,
            "The north entrance closes at 17:00 during construction.",
            True,
        )

    result = run_query_workbench(
        ("practice", "practice/construction"),
        current_context="practice",
        initial_context="practice",
        query_targets=(),
        run_ordinary=answer,
        run_granted=lambda _request: (_ for _ in ()).throw(AssertionError()),
    )
    print(
        "QUERY CLOSED · READ ONLY · NO SESSION SAVE · NO SOURCE MUTATION"
        if result.status == "CLOSED"
        else f"UNEXPECTED QUERY RESULT · {result!r}",
        flush=True,
    )


def _run_search_child() -> None:
    from memcommit.adapters.console.commands.search.search_workbench import run_search_workbench
    from memcommit.application.operations.search.application import SearchResponse, SearchResult

    _verify_pty()

    def search(request):
        time.sleep(0.8)
        return SearchResponse(
            request=request,
            mode="CURRENT",
            results=(
                SearchResult(
                    context_name="practice/construction",
                    kind="memory",
                    uid="11111111-search-result",
                    content="The north entrance closes at 17:00 during construction.",
                ),
                SearchResult(
                    context_name="practice",
                    kind="memory",
                    uid="22222222-search-result",
                    content="Visitor parking moves to the east garage.",
                ),
            ),
        )

    result = run_search_workbench(
        ("practice", "practice/construction"),
        current="practice",
        initial_target="practice",
        initial_include_descendants=True,
        initial_follow_embeds=True,
        limit=5,
        run_search=search,
    )
    print(
        "SEARCH CLOSED · READ ONLY · NO RESULT SAVED · NO SOURCE MUTATION"
        if result.status == "CLOSED"
        else f"UNEXPECTED SEARCH RESULT · {result!r}",
        flush=True,
    )


def _run_find_child() -> None:
    from memcommit.adapters.console.commands.find.workbench import (
        FindTuiSetup,
        run_find_workbench,
    )
    from memcommit.application.operations.find.application import (
        FindMatch,
        FindResult,
        FindSourceItem,
        FindSpan,
    )

    _verify_pty()

    def find(request):
        content = "Say nihao when greeting a new participant."
        start = content.index("nihao")
        source = FindSourceItem(
            context_name="practice",
            context_uid="practice-context-uid",
            kind="memory",
            item_uid="33333333-find-result",
            source_position=1,
            content=content,
        )
        return FindResult(
            request=request,
            scanned_item_count=2,
            matches=(
                FindMatch(
                    source=source,
                    spans=(FindSpan(start, start + 5, "nihao"),),
                ),
            ),
        )

    result = run_find_workbench(
        None,
        setup=FindTuiSetup(
            names=("practice", "practice/construction"),
            current_name="practice",
            initial_targets=("practice",),
        ),
        execute=find,
    )
    print(
        "FIND CLOSED · READ ONLY · NO SOURCE MUTATION"
        if result is not None
        else "FIND CLOSED · NO RESULT · NO SOURCE MUTATION",
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
        timeout=15,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> str:
    _BASE._snapshot(recorder, stem)
    return (OUT / f"{stem}.txt").read_text(encoding="utf-8")


def _capture_query() -> None:
    child, recorder = _spawn("query")
    try:
        child.expect("MEM QUERY")
        _BASE._settle(child)
        entry = _snapshot(recorder, "01-query-entry")
        assert "ENTER A QUESTION" in entry
        assert "INTERACTIVE" not in entry and "FROZEN" not in entry

        child.send("When does the north entrance close?\r")
        _BASE._settle(child, seconds=0.2)
        running = _snapshot(recorder, "02-querying")
        assert "QUERYING" in running and "FROZEN" not in running

        child.expect("north entrance closes at 17:00")
        _BASE._settle(child)
        answer = _snapshot(recorder, "03-query-answer")
        assert "ANSWER READY" in answer

        child.send("\x03")
        child.expect("QUERY CLOSED · READ ONLY")
        child.expect(pexpect.EOF)
        receipt = _snapshot(recorder, "04-query-read-only-verification")
        assert "NO SOURCE MUTATION" in receipt
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_search() -> None:
    child, recorder = _spawn("search")
    try:
        child.expect("MEM SEARCH")
        _BASE._settle(child)
        entry = _snapshot(recorder, "05-search-entry")
        assert "Enter a query to search" in entry
        assert "INTERACTIVE" not in entry and "FROZEN" not in entry

        child.send("entrance construction\r")
        _BASE._settle(child, seconds=0.2)
        running = _snapshot(recorder, "06-searching")
        assert "SEARCHING" in running and "FROZEN" not in running

        child.expect("north entrance closes at 17:00")
        _BASE._settle(child)
        results = _snapshot(recorder, "07-search-results")
        assert "2 RESULTS" in results and "SCOPE FROZEN" not in results

        child.send("\x03")
        child.expect("SEARCH CLOSED · READ ONLY")
        child.expect(pexpect.EOF)
        receipt = _snapshot(recorder, "08-search-read-only-verification")
        assert "NO SOURCE MUTATION" in receipt
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_find() -> None:
    child, recorder = _spawn("find")
    try:
        child.expect("MEM FIND")
        _BASE._settle(child)
        entry = _snapshot(recorder, "09-find-entry")
        assert "ENTER A PATTERN" in entry
        assert "COMPLETE" not in entry and "FROZEN" not in entry

        child.send("nihao\r")
        child.expect("nihao when greeting")
        _BASE._settle(child)
        results = _snapshot(recorder, "10-find-results")
        assert "1 MEMORY · 1 OCCURRENCE" in results
        assert "COMPLETE" not in results and "FROZEN" not in results

        child.send("\x03")
        child.expect("FIND CLOSED · READ ONLY")
        child.expect(pexpect.EOF)
        receipt = _snapshot(recorder, "11-find-read-only-verification")
        assert "NO SOURCE MUTATION" in receipt
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for pattern in ("*.png", "*.txt", "*.typescript"):
        for path in OUT.glob(pattern):
            path.unlink()
    _capture_query()
    _capture_search()
    _capture_find()

    streams = [path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")]
    if len(streams) != 11 or not all("\x1b[" in stream for stream in streams):
        raise RuntimeError("Every capture must retain the actual ANSI PTY stream.")
    if not any("38;2;" in stream or "48;2;" in stream for stream in streams):
        raise RuntimeError("Capture did not retain true-color terminal styles.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        case = sys.argv[2]
        if case == "query":
            _run_query_child()
        elif case == "search":
            _run_search_child()
        elif case == "find":
            _run_find_child()
        else:
            raise SystemExit(f"Unknown capture case: {case}")
    else:
        main()
