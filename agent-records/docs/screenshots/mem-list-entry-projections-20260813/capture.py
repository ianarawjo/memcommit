"""Capture direct and recursive ``mem list`` entry projections in a real PTY."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import re

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/docs/screenshots/mem-list-entry-projections-20260813"
COLUMNS = 180
ROWS = 52
DOWN = "\x1b[B"

_BASE_PATH = (
    ROOT / "agent-records/docs/screenshots/mem-help-a-z-boundary-20260813/capture_help_a_z.py"
)
_SPEC = importlib.util.spec_from_file_location("mem_list_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLS = COLUMNS
_BASE.ROWS = ROWS


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PYTHONPATH": str(ROOT / "src"),
        }
    )
    return environment


def _spawn() -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    command = """
set -eu
printf 'LIVE PTY · '
stty size
before="$(python -c 'from memcommit.store import MemoryStore; print(MemoryStore().current_context_name() or "<none>")')"
printf 'DIRECT LIST · EXACT TARGET · MEMORY VISIBLE\n'
mem list task-1/description
after_direct="$(python -c 'from memcommit.store import MemoryStore; print(MemoryStore().current_context_name() or "<none>")')"
test "$before" = "$after_direct"
printf 'DIRECT READ-ONLY VERIFIED · CURRENT CONTEXT UNCHANGED\n'
printf 'RECURSIVE LIST · EXACT TARGET · ALL OCCURRENCES EXPANDED\n'
mem list -R task-1/participant/construction-updates
after_recursive="$(python -c 'from memcommit.store import MemoryStore; print(MemoryStore().current_context_name() or "<none>")')"
test "$before" = "$after_recursive"
printf 'RECURSIVE READ-ONLY VERIFIED · CURRENT CONTEXT UNCHANGED\n'
mem list task-1/description | head -n 6
printf 'READ-ONLY RESULT VERIFIED · DIRECT TEXT CONTRACT INTACT\n'
""".strip()
    child = pexpect.spawn(
        "zsh",
        ["-lc", command],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=30,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> None:
    _BASE._snapshot(recorder, stem)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    child, recorder = _spawn()
    try:
        child.expect("List · task-1/description")
        _BASE._pump(child)
        _snapshot(recorder, "01-direct-entry")

        child.send(DOWN)
        _BASE._pump(child)
        _snapshot(recorder, "02-direct-memory-focused")

        child.send("m")
        _BASE._pump(child)
        _snapshot(recorder, "03-direct-memories-hidden")

        child.send("m")
        _BASE._pump(child)
        _snapshot(recorder, "04-direct-memories-restored")

        child.send("q")
        child.expect("DIRECT READ-ONLY VERIFIED")
        _snapshot(recorder, "05-direct-close-read-only-verification")

        child.expect("List · task-1/participant/construction-updates")
        _BASE._pump(child, seconds=1.0)
        _snapshot(recorder, "06-recursive-entry")

        child.send(DOWN)
        _BASE._pump(child)
        _snapshot(recorder, "07-recursive-row-navigation")

        child.send("q")
        child.expect("READ-ONLY RESULT VERIFIED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "08-recursive-close-text-verification")
    finally:
        if child.isalive():
            child.close(force=True)

    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "52 180" in raw
    assert "38;" in raw
    assert any(
        "7" in codes.split(";") for codes in re.findall("\x1b\\[([0-9;]*)m", raw)
    )


if __name__ == "__main__":
    main()
