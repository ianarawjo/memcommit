"""Capture Help's complete bottom record and folded redundancy alias."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shlex
import shutil


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/screenshots/mem-help-bottom-compatibility-20260820"

_BASE_PATH = ROOT / "docs/screenshots/mem-help-command-naming-20260813/capture.py"
_SPEC = importlib.util.spec_from_file_location("mem_help_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.ROOT = ROOT
_BASE.OUT = OUT
_BASE.COLUMNS = 180
_BASE.ROWS = 52


def _close(child: object) -> None:
    child.send("q")
    child.expect(_BASE.pexpect.EOF, timeout=5)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)


def _spawn_plain_verification(executable: str) -> tuple[object, object]:
    command = (
        f"stty rows {_BASE.ROWS} cols {_BASE.COLUMNS}; stty size; "
        f"exec {shlex.quote(executable)} help </dev/null | "
        "rg '^find-redundancies '"
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

    bottom_child, bottom_recorder = _BASE._spawn(executable, interactive=True)
    _BASE._pump(bottom_child, seconds=0.8)
    entry = _BASE._snapshot(bottom_recorder, "01-by-kind-entry")
    assert "mem help · command inventory" in entry
    assert "BROWSE & NAVIGATE" in entry

    bottom_child.send("\x1b[F")
    _BASE._pump(bottom_child, seconds=0.8)
    bottom = _BASE._snapshot(bottom_recorder, "02-complete-eval-bottom")
    assert "▸ mem eval" in bottom
    assert "WHEN · Using the existing research evaluation harness" in bottom
    assert "┗" in "\n".join(bottom.splitlines()[-4:])
    _BASE._assert_color(bottom_recorder.getvalue())
    _close(bottom_child)

    compatibility_child, compatibility_recorder = _BASE._spawn(
        executable,
        interactive=True,
    )
    _BASE._pump(compatibility_child, seconds=0.8)
    # Shift-Tab reaches VIEW. Enter A-Z, then use Home and an exact count to
    # reach the canonical row without relying on retained cursor state.
    compatibility_child.send(
        "\x1b[Z\x1b[C\t\x1b[H" + "\x1b[B" * 24
    )
    _BASE._pump(compatibility_child, seconds=0.8)
    rows = _BASE._snapshot(
        compatibility_recorder,
        "03-find-redundancies-alias-row",
    )
    # Long hyphenated names deliberately use the shared two-row label layout.
    assert "▸ mem find-" in rows
    assert "mem find-redundancies" in rows
    assert "(find-duplicates)" in rows
    assert "without changing any Source Context" in rows

    compatibility_child.send("\x1b[C")
    _BASE._pump(compatibility_child, seconds=0.8)
    expanded = _BASE._snapshot(
        compatibility_recorder,
        "04-find-redundancies-expanded",
    )
    assert "▾ mem find-" in expanded
    assert "mem find-redundancies" in expanded
    assert "(find-duplicates)" in expanded
    assert "FORM 1 · mem find-redundancies" in expanded
    assert "Read-only; reviewer responses remain process-local" in expanded
    _BASE._assert_color(compatibility_recorder.getvalue())
    _close(compatibility_child)

    verify_child, verify_recorder = _spawn_plain_verification(executable)
    verify_child.expect(_BASE.pexpect.EOF, timeout=10)
    verify_child.close()
    assert verify_child.exitstatus == 0, (
        verify_child.exitstatus,
        verify_child.signalstatus,
    )
    verification = _BASE._snapshot(
        verify_recorder,
        "05-plain-read-only-verification",
    )
    assert "52 180" in verify_recorder.getvalue()
    assert verification.count("find-redundancies") == 1
    assert "find-redundancies (find-duplicates)" in verification


if __name__ == "__main__":
    main()
