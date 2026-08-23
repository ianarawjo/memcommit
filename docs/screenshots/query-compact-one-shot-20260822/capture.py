"""Capture the compact one-shot Query path in a real 180x52 color PTY."""

from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch
import uuid

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/screenshots/query-compact-one-shot-20260822"
COLUMNS = 180
ROWS = 52
DOWN = "\x1b[B"

_BASE_PATH = ROOT / "docs/screenshots/ordinary-query-one-shot-20260813/capture.py"
_SPEC = importlib.util.spec_from_file_location("query_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _file_snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _run_child() -> None:
    import memcommit.ops as ops
    from memcommit.authority.access import ContextAccess
    from memcommit.context_targeting.readable_catalog import (
        freeze_readable_context_catalog,
    )
    from memcommit.interfaces.tui.operations.query import run_query_workbench
    from memcommit.operations.query.ordinary_runtime import execute_ordinary_query
    from memcommit.store import MemoryStore

    with tempfile.TemporaryDirectory(prefix="mem-query-compact-") as raw_root:
        fixture_root = Path(raw_root)
        store = MemoryStore(root=fixture_root)
        fixture_uids = (uuid.UUID(int=value) for value in range(1, 7))
        # Stable fixture identities keep the ordered study captures byte-for-byte
        # reproducible instead of changing every time the PTY path is verified.
        with patch.object(ops.uuid, "uuid4", side_effect=lambda: next(fixture_uids)):
            root = ops.init("task-1")
            ops.add(root, "The Main Building remains open through the east entrance.")
            campus = ops.init("task-1/campus-wiki")
            ops.add(campus, "The main entrance normally closes at 10 p.m.")
            updates = ops.init("task-1/participant/construction-updates")
            ops.add(updates, "During construction, general access ends at 5 p.m.")
        for context in (root, campus, updates):
            store.save(context)
        store.set_current(root.name)
        access = ContextAccess(
            store=store,
            context_name=root.name,
            display_name=root.name,
            attachment_name=None,
            permission="READ",
        )
        catalog = freeze_readable_context_catalog(store, access)
        before = _file_snapshot(fixture_root)
        requests = []
        provider_calls = []

        class Provider:
            def complete(self, prompt, *, operation, output_schema=None):
                assert operation == "ordinary query"
                provider_calls.append(prompt)
                payload = json.loads(prompt.split("ORDINARY QUERY PAYLOAD:\n", 1)[1])
                aliases = [item["alias"] for item in payload["complete_frozen_corpus"]]
                time.sleep(1.2)
                return json.dumps(
                    {
                        "outcome_kind": "ANSWER",
                        "blocks": [
                            {
                                "role": "SUPPORTED_CLAIM",
                                "text": "The east entrance remains available during construction.",
                                "source_aliases": [aliases[0]],
                            },
                            {
                                "role": "SUPPORTED_CLAIM",
                                "text": "General access changes from 10 p.m. to 5 p.m.",
                                "source_aliases": aliases[1:3],
                            },
                            {
                                "role": "SUPPORTED_CLAIM",
                                "text": "The answer uses the complete checked Context scope.",
                                "source_aliases": aliases,
                            },
                        ],
                    }
                )

        def run_ordinary(request):
            requests.append(request)
            return execute_ordinary_query(
                request,
                store=store,
                catalog=catalog,
                provider_factory=Provider,
            )

        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        result = run_query_workbench(
            tuple(catalog.list_context_names()),
            current_context=root.name,
            initial_context=root.name,
            query_targets=(),
            run_ordinary=run_ordinary,
            run_granted=lambda _request: (_ for _ in ()).throw(AssertionError()),
        )
        after = _file_snapshot(fixture_root)
        session_dir = fixture_root / "query-sessions"
        print(
            f"ONE-SHOT VERIFICATION · REQUESTS {len(requests)} · "
            f"PROVIDER CALLS {len(provider_calls)}"
        )
        print(
            "QUERY CLOSED · SOURCE FILES UNCHANGED "
            f"{before == after} · QUERY SESSION DIRECTORY EXISTS {session_dir.exists()}"
        )
        print(
            "NO SAVED TRANSCRIPT · NO TO DO · NO SOURCE MUTATION"
            if result.status == "CLOSED"
            and before == after
            and not session_dir.exists()
            else f"UNEXPECTED QUERY RESULT {result!r}"
        )


def _run_query_view_child() -> None:
    from memcommit.interfaces.tui.operations.query import run_query_workbench
    from memcommit.operations.query.granted_application import GrantedQueryTarget

    ordinary_calls = []
    granted_calls = []
    targets = (
        GrantedQueryTarget(
            grant_uid="grant-construction",
            public_name="campus-wiki/construction-details",
            attachment_name="task-1",
        ),
        GrantedQueryTarget(
            grant_uid="grant-guidelines",
            public_name="proposal-submission-guidelines",
            attachment_name="task-1",
        ),
    )
    print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
    result = run_query_workbench(
        ("task-1",),
        current_context="task-1",
        initial_context="task-1",
        query_targets=targets,
        run_ordinary=lambda request: ordinary_calls.append(request),
        run_granted=lambda request: granted_calls.append(request),
    )
    print(
        "QUERY VIEW BROWSE VERIFICATION · "
        f"ORDINARY CALLS {len(ordinary_calls)} · GRANTED CALLS {len(granted_calls)}"
    )
    print(
        "PUBLIC CONTROL-PLANE ONLY · NO PROVIDER · NO CONCEALED SOURCE OPEN"
        if result.status == "CLOSED" and not ordinary_calls and not granted_calls
        else f"UNEXPECTED QUERY VIEW RESULT {result!r}"
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
        timeout=20,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> None:
    _BASE._snapshot(recorder, stem)


def _capture() -> None:
    child, recorder = _spawn("ordinary")
    try:
        child.expect("MEM QUERY")
        _BASE._settle(child)
        _snapshot(recorder, "01-entry-compact-scope")

        child.send("\t\t\t\t\r")
        child.expect("CONTEXTS · PROFILE OR CHECKED READABLE CONTEXTS")
        _BASE._settle(child)
        _snapshot(recorder, "02-source-browse-open")

        child.send(DOWN * 2)
        _BASE._settle(child)
        _snapshot(recorder, "03-source-row-focused")

        child.send("\x1b/")
        _BASE._settle(child, seconds=0.8)
        _snapshot(recorder, "04-source-browse-closed")

        child.send("What changes during construction?")
        _BASE._settle(child)
        _snapshot(recorder, "05-question-entered")

        child.send("\r")
        child.expect("ANSWER · QUERYING")
        _BASE._settle(child, seconds=0.2)
        _snapshot(recorder, "06-one-shot-querying")

        child.expect("east entrance remains available")
        _BASE._settle(child)
        _snapshot(recorder, "07-answer-ready")

        child.send(DOWN)
        _BASE._settle(child)
        _snapshot(recorder, "08-reference-focused")

        child.send("\x03")
        child.expect("ONE-SHOT VERIFICATION")
        child.expect("NO SAVED TRANSCRIPT")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "09-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_query_view() -> None:
    child, recorder = _spawn("query-view")
    try:
        child.expect("MEM QUERY")
        child.send("\t\t")
        child.send("\x1b[C")
        _BASE._settle(child)
        _snapshot(recorder, "10-query-view-source-selected")

        child.send("\t\t\r")
        child.expect("QUERY VIEWS · AUTHORIZED CATALOG")
        _BASE._settle(child)
        _snapshot(recorder, "11-query-view-browse-open")

        child.send(DOWN)
        _BASE._settle(child)
        _snapshot(recorder, "12-query-view-row-focused")

        child.send("\x03")
        child.expect("QUERY VIEW BROWSE VERIFICATION")
        child.expect("NO CONCEALED SOURCE OPEN")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "13-query-view-no-disclosure-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _capture()
    _capture_query_view()
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "PTY 180 52" in raw
    assert "38;" in raw
    assert "48;" in raw


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT))
        if sys.argv[2] == "ordinary":
            _run_child()
        elif sys.argv[2] == "query-view":
            _run_query_view_child()
        else:
            raise SystemExit(f"unknown child kind: {sys.argv[2]}")
    else:
        main()
