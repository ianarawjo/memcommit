"""Capture the role-aware Dedup/Dedun Help contract in a 180x52 color PTY."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/screenshots/dedup-role-aware-help-20260823"

_BASE_PATH = ROOT / "agent-records/screenshots/mem-help-command-naming-20260813/capture.py"
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


def main() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    OUT.mkdir(parents=True, exist_ok=True)

    child, recorder = _BASE._spawn(executable, interactive=True)
    _BASE._pump(child, seconds=0.8)
    child.send("\x1b[Z\x1b[C\t\x1b[H" + "\x1b[B" * 12)
    _BASE._pump(child, seconds=0.8)
    entry = _BASE._snapshot(recorder, "01-adjacent-operations")
    assert "▸ mem dedun" in entry
    assert "▸ mem dedup" in entry
    assert "same-role exact duplicates (dup)" in entry
    assert "role-aware exact plus direct-Memory semantic" in entry

    child.send("\x1b[C")
    _BASE._pump(child, seconds=0.8)
    dedun = _BASE._snapshot(recorder, "02-dedun-expanded")
    assert "▾ mem dedun" in dedun
    assert "EXECUTION · SEMANTIC" in dedun
    assert (
        "Direct Context items -> role-aware DUP + Memory semantic DUN groups" in dedun
    )
    assert "PARTIAL OVERLAP" in dedun
    assert "run Atomize first" in dedun
    assert "FORM 1 · mem dedun" in dedun

    child.send("\x1b[D\x1b[B\x1b[C")
    _BASE._pump(child, seconds=0.8)
    dedup = _BASE._snapshot(recorder, "03-dedup-expanded")
    assert "▾ mem dedup" in dedup
    assert "EXECUTION · DETERMINISTIC" in dedup
    assert "role-aware exact groups" in dedup
    assert "cross-role items never merge" in dedup
    assert "no provider or TUI" in dedup
    assert "FORM 1 · mem dedup" in dedup
    _BASE._assert_color(recorder.getvalue())
    _close(child)


if __name__ == "__main__":
    main()
