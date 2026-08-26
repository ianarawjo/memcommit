"""Capture the complete provider-free Find terminal path."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shlex
import shutil


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/screenshots/mem-literal-find-20260816"

_BASE_PATH = ROOT / "agent-records/screenshots/mem-help-command-naming-20260813/capture.py"
_SPEC = importlib.util.spec_from_file_location("mem_find_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.ROOT = ROOT
_BASE.OUT = OUT


def _spawn(executable: str, arguments: list[str]):
    argv = shlex.join([executable, *arguments])
    command = (
        f"stty rows {_BASE.ROWS} cols {_BASE.COLUMNS}; stty size; exec {argv}"
    )
    recorder = _BASE._Recorder()
    child = _BASE.pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
        cwd=str(ROOT),
        env=_BASE._environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=10,
        dimensions=(_BASE.ROWS, _BASE.COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def main() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    OUT.mkdir(parents=True, exist_ok=True)

    child, recorder = _spawn(
        executable,
        [
            "find",
            "construction",
            "--context",
            "task-1/campus-wiki",
            "--ignore-case",
            "--tui",
        ],
    )
    _BASE._pump(child, seconds=0.8)
    entry = _BASE._snapshot(recorder, "01-pattern-entry")
    assert "MEM FIND" in entry
    assert "PATTERN · ENTER TO RUN" in entry
    assert "construction" in entry
    assert "Enter a pattern to run provider-free Find" in entry

    child.send("\t")
    _BASE._pump(child)
    target = _BASE._snapshot(recorder, "02-readable-context-target")
    assert "ALL READABLE CONTEXTS" in target
    assert "task-1/campus-wiki" in target

    child.send("\t")
    _BASE._pump(child)
    scope = _BASE._snapshot(recorder, "03-independent-scope-controls")
    assert "LEXICAL RANGE" in scope
    assert "EMBEDDED CONTEXTS" in scope
    assert "LITERAL" in scope
    assert "IGNORE CASE" in scope

    child.send("\r")
    _BASE._pump(child, seconds=0.8)
    results = _BASE._snapshot(recorder, "04-complete-results")
    assert "COMPLETE · 1 MEMORIES · 6 OCCURRENCES" in results
    assert "SPANS · 32:44" in results
    assert "construction-updates" in results
    _BASE._assert_color(recorder.getvalue())

    child.send("y")
    _BASE._pump(child)
    focused_copy = _BASE._snapshot(recorder, "05-focused-copy")
    assert "COPIED FOCUSED MATCH" in focused_copy

    child.send("Y")
    _BASE._pump(child)
    whole_copy = _BASE._snapshot(recorder, "06-whole-result-copy")
    assert "COPIED RESULT SET" in whole_copy

    child.send("q")
    child.expect(_BASE.pexpect.EOF, timeout=5)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)

    failure_child, failure_recorder = _spawn(
        executable,
        ["find", "--plain", "--regex", "^|"],
    )
    failure_child.expect(_BASE.pexpect.EOF, timeout=10)
    failure_child.close()
    assert failure_child.exitstatus == 1
    failure = _BASE._snapshot(failure_recorder, "07-zero-width-regex-rejected")
    assert "must consume at least one character" in failure


if __name__ == "__main__":
    main()
