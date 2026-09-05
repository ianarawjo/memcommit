"""Capture the compact interactive Add and Init flows in a real color PTY."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "agent-records/docs/screenshots/compact-add-init-input-20260904"
COLUMNS = 180
ROWS = 52
DOWN = "\x1b[B"
SHIFT_TAB = "\x1b[Z"

_BASE_PATH = (
    ROOT / "agent-records/docs/screenshots/mem-help-a-z-boundary-20260813/capture_help_a_z.py"
)
_SPEC = importlib.util.spec_from_file_location("compact_input_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLS = COLUMNS
_BASE.ROWS = ROWS


def _environment(home: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "HOME": str(home),
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PROMPT_TOOLKIT_NO_CPR": "1",
            "PYTHONPATH": str(ROOT / "src"),
        }
    )
    return environment


def _run_setup(home: Path, *arguments: str) -> None:
    completed = subprocess.run(
        [shutil.which("mem") or "mem", *arguments],
        cwd=ROOT,
        env=_environment(home),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        raise RuntimeError(completed.stdout + completed.stderr)


def _spawn(home: Path, *arguments: str) -> tuple[pexpect.spawn, io.StringIO]:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    command = "\n".join(
        (
            "set -eu",
            f"stty rows {ROWS} cols {COLUMNS}",
            "printf 'LIVE PTY · '",
            "stty size",
            f"exec {shlex.join([executable, *arguments])}",
        )
    )
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
        cwd=str(ROOT),
        env=_environment(home),
        encoding="utf-8",
        codec_errors="replace",
        timeout=15,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> None:
    _BASE._snapshot(recorder, stem)


def _wait_visible(
    child: pexpect.spawn,
    recorder: io.StringIO,
    expected: str,
) -> None:
    _BASE._wait_for_visible(child, recorder, expected, seconds=10.0)
    _BASE._pump(child, seconds=0.3)


def _finish(child: pexpect.spawn) -> None:
    try:
        child.expect(pexpect.EOF, timeout=5)
    finally:
        child.close()
    if child.exitstatus != 0:
        raise RuntimeError(
            f"captured command failed: exit={child.exitstatus}, signal={child.signalstatus}"
        )


def _capture_add(home: Path) -> list[str]:
    raw_streams: list[str] = []
    child, recorder = _spawn(home, "add")
    _wait_visible(child, recorder, "MEM ADD")
    _snapshot(recorder, "01-add-entry")

    child.send(SHIFT_TAB)
    child.send(DOWN)
    child.send("\r")
    _wait_visible(child, recorder, "Tab Memory")
    _snapshot(recorder, "02-add-target-choice")

    child.send("\t")
    child.send("A compact Memory.\rSecond line stays together.")
    _wait_visible(child, recorder, "Second line stays together.")
    _snapshot(recorder, "03-add-memory-ready")

    child.send("\x13")
    _wait_visible(child, recorder, "Added 1 Memory to 'project'.")
    _finish(child)
    _snapshot(recorder, "04-add-success-receipt")
    raw_streams.append(recorder.getvalue())

    child, recorder = _spawn(home, "show", "project", "--direct")
    _wait_visible(child, recorder, "Second line stays together.")
    _finish(child)
    _snapshot(recorder, "05-add-read-only-verification")
    raw_streams.append(recorder.getvalue())
    return raw_streams


def _capture_init(home: Path) -> list[str]:
    raw_streams: list[str] = []
    child, recorder = _spawn(home, "init")
    _wait_visible(child, recorder, "MEM INIT")
    _snapshot(recorder, "06-init-entry")

    child.send("\x15")
    child.send("project/new-topic")
    _wait_visible(child, recorder, "project/new-topic")
    _snapshot(recorder, "07-init-name-ready")

    child.send("\r")
    _wait_visible(child, recorder, "Initialized context 'project/new-topic'.")
    _finish(child)
    _snapshot(recorder, "08-init-success-receipt")
    raw_streams.append(recorder.getvalue())

    child, recorder = _spawn(home, "show", "project/new-topic", "--direct")
    _wait_visible(child, recorder, "Context: project/new-topic")
    _finish(child)
    _snapshot(recorder, "09-init-read-only-verification")
    raw_streams.append(recorder.getvalue())
    return raw_streams


def _capture_init_parents(home: Path) -> list[str]:
    raw_streams: list[str] = []
    child, recorder = _spawn(home, "init", "--parents")
    _wait_visible(child, recorder, "CREATE MISSING PARENTS")
    child.send("\x15")
    child.send("archive/2026/notes")
    _wait_visible(child, recorder, "archive/2026/notes")
    _snapshot(recorder, "10-init-parents-name-ready")

    child.send("\r")
    _wait_visible(child, recorder, "Ensured context hierarchy 'archive/2026/notes'.")
    _finish(child)
    _snapshot(recorder, "11-init-parents-success-receipt")
    raw_streams.append(recorder.getvalue())

    child, recorder = _spawn(home, "show", "archive/2026/notes", "--direct")
    _wait_visible(child, recorder, "Context: archive/2026/notes")
    _finish(child)
    _snapshot(recorder, "12-init-parents-read-only-verification")
    raw_streams.append(recorder.getvalue())
    return raw_streams


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mem-compact-input-capture-") as temporary_home:
        home = Path(temporary_home)
        _run_setup(home, "init", "project")
        _run_setup(home, "init", "notes")
        _run_setup(home, "add", "Existing project Memory.", "--to", "project")

        raw_streams = [
            *_capture_add(home),
            *_capture_init(home),
            *_capture_init_parents(home),
        ]

    raw = "".join(raw_streams)
    assert "52 180" in raw
    assert "\x1b[" in raw
    assert re.search(r"\x1b\[[0-9;]*38;(?:2|5);", raw) is not None
    assert "doesn't support cursor position requests" not in raw


if __name__ == "__main__":
    main()
