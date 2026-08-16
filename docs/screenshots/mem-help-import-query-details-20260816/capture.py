"""Capture Import maturity and typed Query/Import Help details."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/screenshots/mem-help-import-query-details-20260816"

_BASE_PATH = ROOT / "docs/screenshots/mem-help-command-naming-20260813/capture.py"
_SPEC = importlib.util.spec_from_file_location("mem_help_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.ROOT = ROOT
_BASE.OUT = OUT


def _close(child: object) -> None:
    child.send("q")
    child.expect(_BASE.pexpect.EOF, timeout=5)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)


def _capture_sequence(executable: str, *, compact: bool) -> None:
    if compact:
        _BASE.COLUMNS = 100
        _BASE.ROWS = 30
        prefix = "compact"
    else:
        _BASE.COLUMNS = 180
        _BASE.ROWS = 52
        prefix = "wide"

    child, recorder = _BASE._spawn(executable, interactive=True)
    _BASE._pump(child, seconds=0.8)

    # Browse -> Create, then init -> add -> branch -> import.
    child.send("\t" + "\x1b[B" * 3)
    _BASE._pump(child, seconds=0.6)
    import_collapsed = _BASE._snapshot(
        recorder,
        f"01-{prefix}-import-partial",
    )
    assert "mem import [PARTIAL]" in import_collapsed
    assert "CURRENT LIMITATION" not in import_collapsed

    child.send("\x1b[C")
    _BASE._pump(child, seconds=0.6)
    import_expanded = _BASE._snapshot(
        recorder,
        f"02-{prefix}-import-expanded",
    )
    import_expanded_line = " ".join(import_expanded.split())
    assert "CURRENT LIMITATION" in import_expanded
    assert "MemCommit-to-MemCommit transfer" in import_expanded_line
    assert "arbitrary documents or Skills" in import_expanded_line

    # Return from Form to command, collapse it, then move to Search & Explain.
    child.send("\x1b[D\x1b[D\t" + "\x1b[B" * 3)
    _BASE._pump(child, seconds=0.6)
    search_collapsed = _BASE._snapshot(
        recorder,
        f"03-{prefix}-search-explain",
    )
    assert "SEARCH & EXPLAIN" in search_collapsed
    assert "LLM-based semantic retrieval" in search_collapsed
    assert "Find exact text or explicit regular-expression" in search_collapsed
    assert "Semantically rank Memories" in search_collapsed
    assert "Generate an LLM-based answer" in search_collapsed
    assert "Show an LLM-derived overview" in search_collapsed

    child.send("\x1b[A\x1b[C")
    _BASE._pump(child, seconds=0.6)
    query_expanded = _BASE._snapshot(
        recorder,
        f"04-{prefix}-query-access",
    )
    query_expanded_line = " ".join(query_expanded.split())
    assert "QUERY-ONLY ACCESS" in query_expanded
    assert "QUERY without READ" in query_expanded_line
    assert "complete Source Memories" in query_expanded_line
    assert "underlying policy" in query_expanded_line
    assert "concealed." in query_expanded_line

    raw = recorder.getvalue()
    expected_size = "30 100" if compact else "52 180"
    assert expected_size in raw
    assert _BASE.re.search(r"\x1b\[[0-9;]*38;(?:2|5);", raw) is not None
    assert _BASE.re.search(r"\x1b\[[0-9;]*48;(?:2|5);", raw) is not None
    _close(child)


def main() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    OUT.mkdir(parents=True, exist_ok=True)
    _capture_sequence(executable, compact=False)
    _capture_sequence(executable, compact=True)


if __name__ == "__main__":
    main()
