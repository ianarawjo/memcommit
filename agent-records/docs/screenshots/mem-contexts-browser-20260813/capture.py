"""Capture ``mem contexts`` as a read-only browser in a real color PTY."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import re

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/docs/screenshots/mem-contexts-browser-20260813"
COLUMNS = 180
ROWS = 52
DOWN = "\x1b[B"

_BASE_PATH = (
    ROOT / "agent-records/docs/screenshots/mem-help-a-z-boundary-20260813/capture_help_a_z.py"
)
_SPEC = importlib.util.spec_from_file_location("mem_contexts_capture_base", _BASE_PATH)
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
printf 'PRE-BROWSE PROFILE/CURRENT\n'
mem profile current
before="$(python -c 'from memcommit.store import MemoryStore; print(MemoryStore().current_context_name() or "<none>")')"
mem contexts
after="$(python -c 'from memcommit.store import MemoryStore; print(MemoryStore().current_context_name() or "<none>")')"
printf 'POST-BROWSE PROFILE/CURRENT\n'
mem profile current
test "$before" = "$after"
printf 'READ-ONLY VERIFIED · CURRENT CONTEXT UNCHANGED · NO SWITCH RECEIPT\n'
""".strip()
    child = pexpect.spawn(
        "zsh",
        ["-lc", command],
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
    child, recorder = _spawn()
    try:
        child.expect("Browse Contexts")
        _BASE._pump(child)
        _snapshot(recorder, "01-entry")

        child.send(DOWN)
        _BASE._pump(child)
        _snapshot(recorder, "02-row-navigation")

        child.send("A")
        _BASE._pump(child, seconds=1.0)
        _snapshot(recorder, "03-expanded-namespace")

        child.send("q")
        child.expect("READ-ONLY VERIFIED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "04-close-read-only-verification")
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
