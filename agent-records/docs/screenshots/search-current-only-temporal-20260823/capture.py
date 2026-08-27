"""Capture time-oriented wording staying in current-only semantic Search."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re
import sys
import time

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52

_BASE_PATH = ROOT / "agent-records/docs/screenshots/ordinary-query-one-shot-20260813/capture.py"
_SPEC = importlib.util.spec_from_file_location("search_current_only_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.ROOT = ROOT
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _verify_pty() -> None:
    size = os.get_terminal_size()
    if (size.columns, size.lines) != (COLUMNS, ROWS):
        raise RuntimeError(
            f"Expected {COLUMNS}x{ROWS} PTY, received "
            f"{size.columns}x{size.lines}."
        )
    print(f"PTY · {size.columns} COLUMNS × {size.lines} ROWS", flush=True)


def _run_child() -> None:
    from memcommit.adapters.console.commands.find.search_workbench import run_find_search_workbench
    from memcommit.application.operations.search.application import FindSearchResponse, FindSearchResult

    _verify_pty()

    def search(request):
        assert request.query == "a is apple during recess"
        time.sleep(0.8)
        return FindSearchResponse(
            request=request,
            mode="CURRENT",
            results=(
                FindSearchResult(
                    context_name="practice/source",
                    kind="memory",
                    uid="17cd32cc-current-result",
                    content="a is apple",
                ),
            ),
        )

    result = run_find_search_workbench(
        ("practice/source",),
        current="practice/source",
        initial_target="practice/source",
        initial_include_descendants=False,
        initial_follow_embeds=False,
        limit=5,
        run_search=search,
    )
    print(
        "SEARCH CLOSED · CURRENT ONLY · READ ONLY · NO RESULT SAVED · "
        "NO SOURCE MUTATION"
        if result.status == "CLOSED"
        else f"UNEXPECTED SEARCH RESULT · {result!r}",
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
            "PYTHONPATH": str(ROOT / "src"),
        }
    )
    return environment


def _spawn() -> tuple[pexpect.spawn, _BASE._StreamRecorder]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child"],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=15,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: _BASE._StreamRecorder, stem: str) -> str:
    _BASE._snapshot(recorder, stem)
    return (OUT / f"{stem}.txt").read_text(encoding="utf-8")


def _capture() -> None:
    child, recorder = _spawn()
    try:
        child.expect("MEM SEARCH")
        _BASE._settle(child)
        entry = _snapshot(recorder, "01-search-entry")
        assert "Enter a query to search" in entry

        child.send("a is apple during recess")
        _BASE._settle(child)
        entered = _snapshot(recorder, "02-time-wording-entered")
        assert "a is apple during recess" in entered
        assert "HISTORY" not in entered

        child.send("\r")
        _BASE._settle(child, seconds=0.2)
        searching = _snapshot(recorder, "03-current-search-running")
        assert "SEARCHING" in searching
        assert "SEARCH HISTORY" not in searching

        child.expect("a is apple")
        _BASE._settle(child)
        results = _snapshot(recorder, "04-current-memory-result")
        assert "1 RESULT" in results
        assert "[practice/source · MEMORY]" in results
        assert "HISTORY" not in results

        child.send(" ")
        _BASE._settle(child)
        checked = _snapshot(recorder, "05-current-result-checked")
        assert "CHECKED RESULT 1 · 1 TOTAL" in checked
        assert "SAVE 1 CHECKED AS COPY" in checked

        child.send("\x03")
        child.expect("SEARCH CLOSED · CURRENT ONLY · READ ONLY")
        child.expect(pexpect.EOF)
        receipt = _snapshot(recorder, "06-read-only-verification")
        assert "NO RESULT SAVED" in receipt
        assert "NO SOURCE MUTATION" in receipt
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _capture()
    streams = [path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")]
    if len(streams) != 6:
        raise RuntimeError("The ordered Search capture set is incomplete.")
    raw = "".join(streams)
    if re.search(r"\x1b\[[0-9;]*38;(?:2|5);", raw) is None:
        raise RuntimeError("Capture did not retain terminal foreground color.")
    if re.search(r"\x1b\[[0-9;]*48;(?:2|5);", raw) is None:
        raise RuntimeError("Capture did not retain terminal background color.")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--child":
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT / "src"))
        _run_child()
    else:
        main()
