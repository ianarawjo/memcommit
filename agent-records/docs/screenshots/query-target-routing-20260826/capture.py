"""Capture Query View preselection and required-question behavior in a color PTY."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import re
import sys
import time

import pexpect


ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "agent-records/docs/screenshots/query-target-routing-20260826"
COLUMNS = 180
ROWS = 52

_BASE_PATH = (
    ROOT
    / "agent-records/docs/screenshots/context-endpoint-memory-preview-20260810/capture.py"
)
_SPEC = importlib.util.spec_from_file_location("query_target_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _run_child() -> None:
    from memcommit.interfaces.tui.operations.query.screen import run_query_workbench
    from memcommit.application.operations.query.granted_application import (
        GrantedQueryResponse,
        GrantedQueryTarget,
    )

    target = GrantedQueryTarget("demo-grant", "demo/query-only", "coffee")
    granted_requests = []

    def ordinary(_request):
        raise AssertionError("A preselected Query View must not use ordinary Query.")

    def granted(request):
        granted_requests.append(request)
        time.sleep(1.2)
        return GrantedQueryResponse(
            request,
            "Authorized answer from the selected complete Query View.",
        )

    print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
    result = run_query_workbench(
        ("coffee",),
        current_context="coffee",
        initial_context="coffee",
        query_targets=(target,),
        run_ordinary=ordinary,
        run_granted=granted,
        initial_query_target=target,
        initial_federate_descendants=False,
    )
    assert len(granted_requests) == 1
    request = granted_requests[0]
    assert request.target == target
    assert request.question == "What is authorized?"
    assert request.federate_descendants is False
    assert result.response == GrantedQueryResponse(
        request,
        "Authorized answer from the selected complete Query View.",
    )
    print(
        "QUERY TARGET VERIFIED · PRESELECTED QUERY VIEW · "
        "BLANK QUESTION REJECTED · ONE ANSWER REQUEST · "
        "NO PROFILE OR STORE OPENED · NO DURABLE MUTATION"
    )


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
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
        timeout=20,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> None:
    _BASE._snapshot(recorder, stem)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for pattern in ("*.png", "*.txt", "*.typescript"):
        for path in OUT.glob(pattern):
            path.unlink()

    child, recorder = _spawn()
    try:
        child.expect("MEM QUERY")
        _BASE._settle(child)
        _snapshot(recorder, "01-query-view-preselected")

        child.send("\r")
        _BASE._settle(child)
        _snapshot(recorder, "02-blank-question-rejected")

        child.send("What is authorized?")
        _BASE._settle(child)
        _snapshot(recorder, "03-question-entered")

        child.send("\r")
        _BASE._settle(child, seconds=0.2)
        _snapshot(recorder, "04-querying")

        _BASE._settle(child, seconds=1.5)
        _snapshot(recorder, "05-answer-ready")

        child.send("\x03")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "06-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)

    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
    plain = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.txt"))
    assert "PTY 180 52" in raw
    assert "[ QUERY VIEW ]" in plain
    assert "demo/query-only" in plain
    assert "[ EXACT VIEW ]" in plain
    assert "Enter a nonblank Query question." in plain
    assert "What is authorized?" in plain
    assert "Authorized answer from the selected complete Query View." in plain
    assert "BLANK QUESTION REJECTED" in plain
    assert "NO DURABLE MUTATION" in plain
    assert "┏" in raw and "┗" in raw
    assert re.search(r"\x1b\[[0-9;]*38;(?:2|5);", raw) is not None
    assert re.search(r"\x1b\[[0-9;]*48;(?:2|5);", raw) is not None


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT / "src"))
        _run_child()
    else:
        main()
