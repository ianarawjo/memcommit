"""Capture common operation meaning composed with CLI/TUI Help."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import shutil


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/docs/screenshots/mem-help-composer-20260814"

_BASE_PATH = ROOT / "agent-records/docs/screenshots/mem-help-command-naming-20260813/capture.py"
_SPEC = importlib.util.spec_from_file_location("mem_help_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.ROOT = ROOT
_BASE.OUT = OUT


def main() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    OUT.mkdir(parents=True, exist_ok=True)

    child, recorder = _BASE._spawn(executable, interactive=True)
    _BASE._pump(child, seconds=0.8)
    entry = _BASE._snapshot(recorder, "01-by-kind-entry")
    assert "mem help · command inventory" in entry
    assert "INVENTORY VIEW" in entry

    # Contexts -> Memories -> Search & Explain -> Analyze & Transform, then
    # move from Audit to Update and expand its composed detail.
    child.send("\t\t\t" + "\x1b[B" * 6 + "\x1b[C")
    _BASE._pump(child, seconds=0.8)
    detail = _BASE._snapshot(recorder, "02-update-composed-detail")
    assert "▾ mem update" in detail
    assert "FLOW" in detail and "Source Context -> Target Context" in detail
    assert "EXECUTION · SEMANTIC" in detail
    assert "EFFECT" in detail and "reviewed Apply" in detail
    assert "RANGE" in detail and "readable descendants" in detail
    assert detail.index("FLOW") < detail.index("FORM 1")

    # H leaves the browser and prints the same composed overview and exact
    # forms before Typer's complete flag-oriented syntax reference.
    child.send("h")
    child.expect(_BASE.pexpect.EOF, timeout=8)
    full_help = _BASE._snapshot(recorder, "03-update-full-help")
    assert "Overview" in full_help
    assert "Command line" in full_help
    assert "Source Context -> Target Context" in full_help
    assert "--source-descendants" in full_help
    _BASE._assert_color(recorder.getvalue())
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)

    verify_child, verify_recorder = _BASE._spawn(executable, interactive=False)
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
    assert "list (ls)" in verification
    assert "Git-style syntax" in verification
    assert not re.search(r"^ls ", verification, re.MULTILINE)


if __name__ == "__main__":
    main()
