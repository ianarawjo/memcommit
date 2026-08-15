"""Capture the reviewed use-case column in the actual Help TUI."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shlex
import shutil


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/screenshots/mem-help-best-for-20260815"

_BASE_PATH = ROOT / "docs/screenshots/mem-help-command-naming-20260813/capture.py"
_SPEC = importlib.util.spec_from_file_location("mem_help_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.ROOT = ROOT
_BASE.OUT = OUT


def _spawn_plain_verification(
    executable: str,
) -> tuple[object, object]:
    command = (
        f"stty rows {_BASE.ROWS} cols {_BASE.COLUMNS}; stty size; "
        f"exec {shlex.quote(executable)} help </dev/null | "
        "rg '^(compare|update) '"
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


def _close(child: object) -> None:
    child.send("q")
    child.expect(_BASE.pexpect.EOF, timeout=5)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)


def main() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    OUT.mkdir(parents=True, exist_ok=True)

    entry_child, entry_recorder = _BASE._spawn(executable, interactive=True)
    _BASE._pump(entry_child, seconds=0.8)
    entry = _BASE._snapshot(entry_recorder, "01-by-kind-entry")
    assert "mem help · command inventory" in entry
    assert "INVENTORY VIEW" in entry
    assert "│ Quickly checking" in entry
    assert "BEST FOR" not in entry
    _BASE._assert_color(entry_recorder.getvalue())
    _close(entry_child)

    compare_child, compare_recorder = _BASE._spawn(executable, interactive=True)
    _BASE._pump(compare_child, seconds=0.8)
    # Contexts -> Memories -> Search & Explain -> Analyze & Transform, then
    # Audit -> Atomize -> Distill -> Compare. Keep the operation collapsed.
    compare_child.send("\t\t\t" + "\x1b[B" * 3)
    _BASE._pump(compare_child, seconds=0.8)
    compare = _BASE._snapshot(compare_recorder, "02-compare-best-for")
    assert "▸ mem compare" in compare
    assert "Comparing two Contexts as a whole to understand where they" in compare
    assert "BEST FOR" not in compare
    assert "FORM 1" not in compare
    _BASE._assert_color(compare_recorder.getvalue())
    _close(compare_child)

    update_child, update_recorder = _BASE._spawn(executable, interactive=True)
    _BASE._pump(update_child, seconds=0.8)
    # Enter Analyze & Transform and move from Audit to Update without opening it.
    update_child.send("\t\t\t" + "\x1b[B" * 7)
    _BASE._pump(update_child, seconds=0.8)
    update = _BASE._snapshot(update_recorder, "03-update-best-for")
    assert "▸ mem update" in update
    assert "Updating an existing Context using newly verified" in update
    assert "BEST FOR" not in update
    assert "FORM 1" not in update
    _BASE._assert_color(update_recorder.getvalue())
    _close(update_child)

    verify_child, verify_recorder = _spawn_plain_verification(executable)
    verify_child.expect(_BASE.pexpect.EOF, timeout=10)
    verify_child.close()
    assert verify_child.exitstatus == 0, (
        verify_child.exitstatus,
        verify_child.signalstatus,
    )
    verification = _BASE._snapshot(
        verify_recorder,
        "04-plain-read-only-verification",
    )
    assert "Compare Memories in two Contexts" in verification
    assert "Update Memories in the Target Context" in verification

    a_z_child, a_z_recorder = _BASE._spawn(executable, interactive=True)
    _BASE._pump(a_z_child, seconds=0.8)
    a_z_child.send("\x1b[Z\x1b[C")
    _BASE._pump(a_z_child, seconds=0.8)
    a_z = _BASE._snapshot(a_z_recorder, "05-a-z-global-best-for")
    assert "✓ A–Z" in a_z
    assert "│ Saving new facts" in a_z
    assert "│ Comparing two Contexts" in a_z
    assert "BEST FOR" not in a_z
    _BASE._assert_color(a_z_recorder.getvalue())
    _close(a_z_child)

    _BASE.COLUMNS = 90
    _BASE.ROWS = 40
    narrow_child, narrow_recorder = _BASE._spawn(executable, interactive=True)
    _BASE._pump(narrow_child, seconds=0.8)
    narrow = _BASE._snapshot(narrow_recorder, "06-narrow-stacked-best-for")
    assert "40 90" in narrow_recorder.getvalue()
    assert "Quickly checking" in narrow
    assert "BEST FOR" not in narrow
    assert (
        _BASE.re.search(
            r"\x1b\[[0-9;]*38;(?:2|5);",
            narrow_recorder.getvalue(),
        )
        is not None
    )
    assert (
        _BASE.re.search(
            r"\x1b\[[0-9;]*48;(?:2|5);",
            narrow_recorder.getvalue(),
        )
        is not None
    )
    _close(narrow_child)


if __name__ == "__main__":
    main()
