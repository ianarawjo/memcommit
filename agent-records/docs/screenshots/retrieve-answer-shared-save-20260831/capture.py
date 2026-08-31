"""Capture the shared Find, Search, and Query SAVE flow in a real color PTY."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import re
import shlex
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "agent-records/docs/screenshots/retrieve-answer-shared-save-20260831"

_BASE_PATH = ROOT / "agent-records/docs/screenshots/mem-help-command-naming-20260813/capture.py"
_SPEC = importlib.util.spec_from_file_location("retrieve_answer_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.ROOT = ROOT
_BASE.OUT = OUT


def _build_store(store_root: Path):
    import memcommit.application.capabilities.ops as ops
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=store_root)
    task = ops.init("task")
    store.save(task)
    source = ops.init("task/source")
    memory = ops.add(source, "Needle: accessible entrance is on the east side.")
    store.save(source)
    archive = ops.init("task/archive")
    ops.add(archive, "Archived schedule retained for comparison.")
    store.save(archive)
    store.set_current(source.name)
    return store, source, memory


def _search_harness(store_root: Path) -> None:
    import memcommit.adapters.console.commands.search.command as search_command
    from memcommit.application.capabilities.authority.context_access import resolve_context_access
    from memcommit.application.operations.search.application import SearchResponse, SearchResult
    from memcommit.persistence.store import MemoryStore

    store, source, memory = _build_store(store_root)
    access = resolve_context_access(
        store,
        source.name,
        current_name=source.name,
        required_permission="READ",
    )

    def deterministic_search(_store, _catalog, request):
        time.sleep(0.25)
        return SearchResponse(
            request,
            "CURRENT",
            (
                SearchResult(
                    context_name=source.name,
                    kind="memory",
                    uid=memory.uid,
                    content=memory.content,
                    source_context_name=source.name,
                    source_context_uid=source.uid,
                    source_memory_uid=memory.uid,
                ),
            ),
        )

    search_command._run_search_request = deterministic_search
    search_command._open_search_workbench(
        store,
        access,
        current_name=source.name,
        include_descendants=False,
        follow_embeds=False,
        limit=5,
    )
    destination = "task/archive/search-result"
    print(f"SEARCH SAVE COMPLETE · {destination}", flush=True)
    input("PRESS ENTER FOR READ-ONLY SEARCH VERIFICATION")
    saved = tuple(MemoryStore(root=store_root).load(destination).iter_items())
    assert len(saved) == 1
    content = getattr(saved[0], "content", None)
    if content is None:
        assert saved[0].target is not None
        content = saved[0].target.content
    print(f"SEARCH READ-ONLY RESULT · {content}", flush=True)
    print("SEARCH SOURCE UNCHANGED · True", flush=True)


def _find_harness(store_root: Path) -> None:
    from memcommit.adapters.console.commands.find.workbench import FindTuiSetup, run_find_workbench
    from memcommit.application.capabilities.authority.context_access import resolve_context_access
    from memcommit.application.capabilities.authority.readable_contexts import freeze_readable_context_catalog
    from memcommit.application.capabilities.save_context_from_selection.runtime import execute_save_context_from_selection
    from memcommit.application.operations.find.application import FindRequest
    from memcommit.application.operations.find.runtime import execute_find
    from memcommit.application.operations.find.save_context import save_context_request_from_find
    from memcommit.persistence.store import MemoryStore

    store, source, _memory = _build_store(store_root)
    access = resolve_context_access(
        store,
        source.name,
        current_name=source.name,
        required_permission="READ",
    )
    catalog = freeze_readable_context_catalog(store, access)
    outcome = run_find_workbench(
        None,
        setup=FindTuiSetup(
            names=tuple(catalog.list_context_names()),
            current_name=source.name,
            initial_targets=(source.name,),
        ),
        execute=lambda request: execute_find(request, catalog=catalog),
        local_context_names=tuple(store.list_context_names()),
        validate_save_location=store.assert_context_creatable,
    )
    assert outcome is not None and outcome.status == "SAVE"
    assert outcome.save_as is not None and outcome.save_location is not None
    saved = execute_save_context_from_selection(
        save_context_request_from_find(
            outcome.result,
            outcome.selected_match_indices,
            mode=outcome.save_as,
            destination_name=outcome.save_location,
            catalog=catalog,
        ),
        store=store,
        catalog=catalog,
    )
    print(
        f"Saved {len(saved.item_uids)} checked Find match(es) as {saved.mode} "
        f"in new Context '{saved.context_name}'; sources unchanged.",
        flush=True,
    )
    print(f"FIND SAVE COMPLETE · {saved.context_name}", flush=True)
    input("PRESS ENTER FOR READ-ONLY FIND VERIFICATION")
    loaded = tuple(MemoryStore(root=store_root).load(saved.context_name).iter_items())
    assert len(loaded) == 1
    content = getattr(loaded[0], "content", None)
    if content is None:
        assert loaded[0].target is not None
        content = loaded[0].target.content
    print(f"FIND READ-ONLY RESULT · {content}", flush=True)
    print("FIND SOURCE UNCHANGED · True", flush=True)


def _query_harness(store_root: Path) -> None:
    from memcommit.adapters.console.commands.query.workbench import run_query_workbench
    from memcommit.application.operations.query.ordinary_application import OrdinaryQueryResponse
    from memcommit.application.operations.query.save_answer import SaveQueryAnswerRequest
    from memcommit.application.operations.query.save_answer_runtime import execute_save_query_answer
    from memcommit.persistence.store import MemoryStore

    store, source, _memory = _build_store(store_root)

    def deterministic_query(request):
        time.sleep(0.25)
        return OrdinaryQueryResponse(
            request,
            "The accessible entrance is on the east side.",
            True,
        )

    outcome = run_query_workbench(
        tuple(store.list_context_names()),
        current_context=source.name,
        initial_context=source.name,
        query_targets=(),
        run_ordinary=deterministic_query,
        run_granted=lambda _request: None,
        local_context_names=tuple(store.list_context_names()),
        validate_save_location=store.assert_context_creatable,
    )
    assert outcome.status == "SAVE"
    assert outcome.response is not None and outcome.save_location is not None
    saved = execute_save_query_answer(
        SaveQueryAnswerRequest(outcome.response, outcome.save_location),
        store=store,
    )
    print(
        f"Saved complete Query answer in new Context '{saved.context_name}'.",
        flush=True,
    )
    print(f"QUERY SAVE COMPLETE · {saved.context_name}", flush=True)
    input("PRESS ENTER FOR READ-ONLY QUERY VERIFICATION")
    loaded = tuple(MemoryStore(root=store_root).load_direct(saved.context_name).iter_items())
    assert len(loaded) == 1
    print(f"QUERY READ-ONLY ANSWER · {loaded[0].content}", flush=True)
    print("QUERY SOURCE REOPENED DURING SAVE · False", flush=True)


def _shell_command(operation: str, store_root: Path) -> str:
    argv = shlex.join(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--harness",
            operation,
            str(store_root),
        ]
    )
    return "; ".join(
        (
            f"stty rows {_BASE.ROWS} cols {_BASE.COLUMNS}",
            "stty size",
            f"exec {argv}",
        )
    )


def _spawn(operation: str, store_root: Path):
    environment = _BASE._environment()
    environment["PROMPT_TOOLKIT_NO_CPR"] = "1"
    environment["PYTHONPATH"] = str(ROOT / "src")
    recorder = _BASE._Recorder()
    child = _BASE.pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", _shell_command(operation, store_root)],
        cwd=str(ROOT),
        env=environment,
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(_BASE.ROWS, _BASE.COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _wait_for(child, recorder, text: str, *, timeout: float = 12.0) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _BASE._pump(child, seconds=0.15)
        plain = _BASE._plain(recorder.getvalue())
        if text in plain:
            return plain
    raise AssertionError(f"Timed out waiting for {text!r}.\n{_BASE._plain(recorder.getvalue())}")


def _assert_tui_color(raw: str) -> None:
    assert "52 180" in raw
    assert re.search(r"\x1b\[[0-9;]*38;(?:2|5);", raw) is not None
    assert re.search(r"\x1b\[[0-9;]*48;(?:2|5);", raw) is not None


def _capture_search(first_number: int) -> int:
    with tempfile.TemporaryDirectory(prefix="memcommit-search-shared-save-") as root:
        child, recorder = _spawn("search", Path(root))
        number = first_number
        _BASE._pump(child, seconds=0.7)
        entry = _BASE._snapshot(recorder, f"{number:02d}-search-entry")
        assert "MEM SEARCH" in entry and "SEARCH · ENTER TO RUN" in entry
        number += 1

        child.send("accessibility")
        _BASE._pump(child)
        query = _BASE._snapshot(recorder, f"{number:02d}-search-query-entered")
        assert "accessibility" in query
        number += 1

        child.send("\r")
        _wait_for(child, recorder, "1 RESULT ·")
        result = _BASE._snapshot(recorder, f"{number:02d}-search-result-and-save")
        assert "Needle: accessible entrance" in result
        assert "CONTENT ·" in result and "LOCATION ·" in result and "ACTION ·" in result
        number += 1

        child.send("\r\t\x1b[C")
        _BASE._pump(child)
        checked = _BASE._snapshot(recorder, f"{number:02d}-search-checked-reference-mode")
        assert "1 CHECKED SEARCH RESULT" in checked and "REFERENCE" in checked
        number += 1

        child.send("\t\x15draft/search-result")
        _BASE._pump(child)
        location = _BASE._snapshot(recorder, f"{number:02d}-search-location-entered")
        assert "draft/search-result" in location and "SAVE LOCATION" not in location
        number += 1

        child.send("\t\r")
        _BASE._pump(child)
        browse = _BASE._snapshot(recorder, f"{number:02d}-search-browse-in-save")
        assert "SAVE LOCATION · EXISTING CONTEXTS" in browse and "task/archive" in browse
        number += 1

        child.send("\x1b[A\r")
        _BASE._pump(child)
        child.send("\t\t")
        _BASE._pump(child)
        review = _BASE._snapshot(recorder, f"{number:02d}-search-action-review")
        assert "task/archive/search-result" in review and "ACTION · > SAVE 1 CHECKED AS REFERENCE" in review
        number += 1

        child.send("\r")
        _wait_for(child, recorder, "PRESS ENTER FOR READ-ONLY SEARCH VERIFICATION")
        receipt = _BASE._snapshot(recorder, f"{number:02d}-search-success-receipt")
        assert "Saved 1 checked Search result(s) as REFERENCE" in receipt
        number += 1

        child.send("\r")
        child.expect(_BASE.pexpect.EOF, timeout=10)
        child.close()
        assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)
        verification = _BASE._snapshot(recorder, f"{number:02d}-search-read-only-verification")
        assert "SEARCH READ-ONLY RESULT" in verification and "SEARCH SOURCE UNCHANGED · True" in verification
        _assert_tui_color(recorder.getvalue())
        return number + 1


def _capture_find(first_number: int) -> int:
    with tempfile.TemporaryDirectory(prefix="memcommit-find-shared-save-") as root:
        child, recorder = _spawn("find", Path(root))
        number = first_number
        _BASE._pump(child, seconds=0.7)
        entry = _BASE._snapshot(recorder, f"{number:02d}-find-entry")
        assert "MEM FIND" in entry and "FIND · ENTER PATTERN TO RUN" in entry
        number += 1

        child.send("Needle")
        _BASE._pump(child)
        pattern = _BASE._snapshot(recorder, f"{number:02d}-find-pattern-entered")
        assert "Needle" in pattern
        number += 1

        child.send("\r")
        _wait_for(child, recorder, "1 OCCURRENCE")
        result = _BASE._snapshot(recorder, f"{number:02d}-find-result-and-save")
        assert "Needle: accessible entrance" in result and "CONTENT ·" in result
        number += 1

        child.send("\r\t\x1b[C\x1b[C")
        _BASE._pump(child)
        checked = _BASE._snapshot(recorder, f"{number:02d}-find-checked-embed-mode")
        assert "1 CHECKED FIND MATCH" in checked and "EMBED" in checked
        number += 1

        child.send("\t\x15draft/find-result")
        _BASE._pump(child)
        location = _BASE._snapshot(recorder, f"{number:02d}-find-location-entered")
        assert "draft/find-result" in location and "PARENT CONTEXT" not in location
        number += 1

        child.send("\t\r")
        _BASE._pump(child)
        browse = _BASE._snapshot(recorder, f"{number:02d}-find-browse-in-save")
        assert "SAVE LOCATION · EXISTING CONTEXTS" in browse and "task/archive" in browse
        number += 1

        child.send("\x1b[A\r\t\t")
        _BASE._pump(child)
        review = _BASE._snapshot(recorder, f"{number:02d}-find-action-review")
        assert "task/archive/find-result" in review and "ACTION · > SAVE 1 CHECKED AS EMBED" in review
        number += 1

        child.send("\r")
        _wait_for(child, recorder, "PRESS ENTER FOR READ-ONLY FIND VERIFICATION")
        receipt = _BASE._snapshot(recorder, f"{number:02d}-find-success-receipt")
        assert "Saved 1 checked Find match(es) as EMBED" in receipt
        number += 1

        child.send("\r")
        child.expect(_BASE.pexpect.EOF, timeout=10)
        child.close()
        assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)
        verification = _BASE._snapshot(recorder, f"{number:02d}-find-read-only-verification")
        assert "FIND READ-ONLY RESULT" in verification and "FIND SOURCE UNCHANGED · True" in verification
        _assert_tui_color(recorder.getvalue())
        return number + 1


def _capture_query(first_number: int) -> int:
    with tempfile.TemporaryDirectory(prefix="memcommit-query-shared-save-") as root:
        child, recorder = _spawn("query", Path(root))
        number = first_number
        _BASE._pump(child, seconds=0.7)
        entry = _BASE._snapshot(recorder, f"{number:02d}-query-entry")
        assert "MEM QUERY" in entry and "QUESTION · ENTER TO ASK" in entry
        number += 1

        child.send("Where is the accessible entrance?")
        _BASE._pump(child)
        question = _BASE._snapshot(recorder, f"{number:02d}-query-question-entered")
        assert "Where is the accessible entrance?" in question
        number += 1

        child.send("\r")
        _wait_for(child, recorder, "The accessible entrance is on the east side.")
        answer = _BASE._snapshot(recorder, f"{number:02d}-query-answer-and-save")
        assert "COMPLETE QUERY ANSWER" in answer and "SAVE COMPLETE ANSWER" in answer
        assert "MODE ·" not in answer
        number += 1

        child.send("\t\x15draft/query-result")
        _BASE._pump(child)
        location = _BASE._snapshot(recorder, f"{number:02d}-query-location-entered")
        assert "draft/query-result" in location
        number += 1

        child.send("\t\r")
        _BASE._pump(child)
        browse = _BASE._snapshot(recorder, f"{number:02d}-query-browse-in-save")
        assert "SAVE LOCATION · EXISTING CONTEXTS" in browse and "task/archive" in browse
        number += 1

        child.send("\x1b[A\r\t\t")
        _BASE._pump(child)
        review = _BASE._snapshot(recorder, f"{number:02d}-query-action-review")
        assert "task/archive/query-result" in review and "ACTION · > SAVE COMPLETE ANSWER" in review
        number += 1

        child.send("\r")
        _wait_for(child, recorder, "PRESS ENTER FOR READ-ONLY QUERY VERIFICATION")
        receipt = _BASE._snapshot(recorder, f"{number:02d}-query-success-receipt")
        assert "Saved complete Query answer in new Context" in receipt
        number += 1

        child.send("\r")
        child.expect(_BASE.pexpect.EOF, timeout=10)
        child.close()
        assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)
        verification = _BASE._snapshot(recorder, f"{number:02d}-query-read-only-verification")
        assert "QUERY READ-ONLY ANSWER" in verification
        assert "QUERY SOURCE REOPENED DURING SAVE · False" in verification
        _assert_tui_color(recorder.getvalue())
        return number + 1


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    number = _capture_search(1)
    number = _capture_find(number)
    _capture_query(number)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--harness", action="store_true")
    parser.add_argument("operation", nargs="?")
    parser.add_argument("store_root", nargs="?")
    arguments = parser.parse_args()
    if arguments.harness:
        if arguments.operation is None or arguments.store_root is None:
            parser.error("--harness requires OPERATION and STORE_ROOT")
        harness = {
            "find": _find_harness,
            "query": _query_harness,
            "search": _search_harness,
        }.get(arguments.operation)
        if harness is None:
            parser.error("OPERATION must be find, query, or search")
        harness(Path(arguments.store_root))
    else:
        main()
