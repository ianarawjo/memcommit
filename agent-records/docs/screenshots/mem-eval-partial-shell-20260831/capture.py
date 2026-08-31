"""Capture the reserved Eval shell and its PARTIAL Help presentation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shlex
import shutil


ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "agent-records/docs/screenshots/mem-eval-partial-shell-20260831"
COLUMNS = 180
ROWS = 52

_BASE_PATH = ROOT / "agent-records/docs/screenshots/mem-help-command-naming-20260813/capture.py"
_SPEC = importlib.util.spec_from_file_location("mem_help_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.ROOT = ROOT
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _close_help(child: object) -> None:
    child.send("q")
    child.expect(_BASE.pexpect.EOF, timeout=5)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)


def _capture_command(
    executable: str,
    *,
    arguments: tuple[str, ...],
    stem: str,
    expected_exit: int,
) -> str:
    argv = shlex.join((executable, *arguments))
    command = f"stty rows {ROWS} cols {COLUMNS}; stty size; exec {argv}"
    recorder = _BASE._Recorder()
    child = _BASE.pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
        cwd=str(ROOT),
        env=_BASE._environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=10,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    child.expect(_BASE.pexpect.EOF, timeout=10)
    child.close()
    assert child.exitstatus == expected_exit, (
        child.exitstatus,
        child.signalstatus,
        recorder.getvalue(),
    )
    assert f"{ROWS} {COLUMNS}" in recorder.getvalue()
    return _BASE._snapshot(recorder, stem)


def main() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    OUT.mkdir(parents=True, exist_ok=True)

    child, recorder = _BASE._spawn(executable, interactive=True)
    _BASE._pump(child, seconds=0.8)
    entry = _BASE._snapshot(recorder, "01-help-entry")
    assert "mem help · command inventory" in entry
    assert "BROWSE & NAVIGATE" in entry

    child.send("\x1b[F")
    _BASE._pump(child, seconds=0.8)
    focused = _BASE._snapshot(recorder, "02-eval-partial-focused")
    assert "▸ mem eval" in focused
    assert "[PARTIAL]" in focused
    assert "reserved Eval surface" in focused

    child.send("\x1b[C")
    _BASE._pump(child, seconds=0.8)
    expanded = _BASE._snapshot(recorder, "03-eval-reserved-detail")
    assert "▾ mem eval" in expanded
    assert "RESERVED SHELL" in expanded
    assert "no executable subcommands" in expanded
    _BASE._assert_color(recorder.getvalue())
    _close_help(child)

    shell = _capture_command(
        executable,
        arguments=("eval",),
        stem="04-reserved-shell-receipt",
        expected_exit=0,
    )
    assert "Eval is reserved for a future evaluation workflow" in shell
    assert "No evaluation commands are currently available" in shell

    direct_help = _capture_command(
        executable,
        arguments=("eval", "--help"),
        stem="05-reserved-shell-help",
        expected_exit=0,
    )
    assert "Reserve the Eval operation name" in direct_help
    assert "semantic" not in direct_help.lower()

    removed = _capture_command(
        executable,
        arguments=("eval", "semantic"),
        stem="06-semantic-route-removed",
        expected_exit=2,
    )
    assert "No such command 'semantic'" in removed


if __name__ == "__main__":
    main()
