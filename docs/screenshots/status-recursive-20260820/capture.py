"""Capture the committed recursive Status overview in a real color PTY."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/screenshots/status-recursive-20260820"
COLUMNS = 180
ROWS = 52

_BASE_PATH = (
    ROOT / "docs/screenshots/mem-help-a-z-boundary-20260813/capture_help_a_z.py"
)
_SPEC = importlib.util.spec_from_file_location("status_capture_base", _BASE_PATH)
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
            "PYTHONPATH": str(ROOT),
        }
    )
    return environment


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    recorder = _BASE._StreamRecorder()
    command = r"""
set -eu
previous="$(python -c 'from memcommit.store import MemoryStore; print(MemoryStore().current_context_name() or "")')"
restore_current() {
  if [ -n "$previous" ]; then
    mem switch "$previous" >/dev/null
  fi
}
trap restore_current EXIT
printf 'LIVE PTY · '
stty size
mem switch practice >/dev/null
printf '\033[2J\033[H'
printf '\033[38;2;138;173;244m$\033[0m mem status -r\n'
mem status -r
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
    try:
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)

    raw = recorder.getvalue()
    if "52 180" not in raw:
        raise RuntimeError("Capture child did not verify the 180x52 PTY.")
    if "\x1b[38;2;138;173;244m" not in raw:
        raise RuntimeError("Capture stream did not preserve prompt foreground color.")
    if "On context: practice" not in raw:
        raise RuntimeError("Capture did not render the requested practice Status.")
    _BASE._snapshot(recorder, "01-practice-recursive-status")


if __name__ == "__main__":
    main()
