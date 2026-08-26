"""Capture Grant ownership and capability placement in the real Switch TUI."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import re

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/screenshots/mem-switch-grant-ownership-20260820"
COLUMNS = 180
ROWS = 52
DOWN = "\x1b[B"
RIGHT = "\x1b[C"

_BASE_PATH = (
    ROOT / "docs/screenshots/mem-help-a-z-boundary-20260813/capture_help_a_z.py"
)
_SPEC = importlib.util.spec_from_file_location("switch_grant_capture_base", _BASE_PATH)
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
            "PROMPT_TOOLKIT_COLOR_DEPTH": "DEPTH_24_BIT",
            "PYTHONPATH": str(ROOT / "src"),
        }
    )
    return environment


def _spawn() -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    command = f"""
set -eu
stty rows {ROWS} cols {COLUMNS} onlcr
printf 'LIVE COLOR PTY · '
stty size
before="$(mem pwd)"
printf 'CURRENT BEFORE · %s\n' "$before"
mem switch
after="$(mem pwd)"
test "$before" = "$after"
printf 'SWITCH CANCELLED · CURRENT UNCHANGED · %s\n' "$after"
""".strip()
    child = pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
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
        child.expect("Select a Context")
        _BASE._pump(child)
        _snapshot(recorder, "01-switch-entry")

        # From practice/source: task-1 is the next visible root. Expand it,
        # enter campus-wiki, expand the granted subtree, and focus its first
        # child so both focused and unfocused Grant rows remain visible.
        child.send(DOWN + RIGHT + DOWN * 3 + RIGHT + DOWN)
        _BASE._pump(child, seconds=1.0)
        _snapshot(recorder, "02-grant-prefix-and-capabilities")

        child.send("\x1b")
        child.expect("SWITCH CANCELLED · CURRENT UNCHANGED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "03-cancelled-current-unchanged")
    finally:
        if child.isalive():
            child.close(force=True)

    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
    plain = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", raw)
    assert "52 180" in plain
    assert "GRANT task-1/campus-wiki" in plain
    assert "READ + QUERY + EDIT + DELETE + EXPORT" in plain
    assert "Switch cancelled." in plain
    assert "SWITCH CANCELLED · CURRENT UNCHANGED" in plain
    assert "38;2;139;213;202" in raw


if __name__ == "__main__":
    main()
