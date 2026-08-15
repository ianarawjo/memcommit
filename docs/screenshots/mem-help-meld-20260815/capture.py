"""Capture the reviewed Meld Help copy and both example forms."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/screenshots/mem-help-meld-20260815"

_BASE_PATH = ROOT / "docs/screenshots/mem-help-command-naming-20260813/capture.py"
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

    # Contexts -> Memories -> Search & Explain -> Analyze & Transform, then
    # Audit -> Atomize -> Distill -> Compare -> Impact -> Review -> Meld.
    child.send("\t\t\t" + "\x1b[B" * 6)
    _BASE._pump(child, seconds=0.8)
    collapsed = _BASE._snapshot(recorder, "01-collapsed-meld")
    assert "▸ mem meld" in collapsed
    assert "Combine two Contexts and resolve their differences" in collapsed
    assert "Combining independently edited Contexts" in collapsed
    assert "FORM 1" not in collapsed
    _BASE._assert_color(recorder.getvalue())

    child.send("\x1b[C")
    _BASE._pump(child, seconds=0.8)
    expanded = _BASE._snapshot(recorder, "02-expanded-contract")
    assert "▾ mem meld" in expanded
    assert "PEER A + PEER B -> RESULT; INCOMING -> BASELINE" in expanded
    assert "Symmetric mode requires a distinct empty Result" in expanded
    assert "FORM 1" in expanded

    child.send("\x1b[B" * 4)
    _BASE._pump(child, seconds=0.8)
    symmetric = _BASE._snapshot(recorder, "03-symmetric-example")
    assert (
        "FORM 5 · mem meld team/draft-a team/draft-b --to team/merged-draft"
        in symmetric
    )
    assert "example: symmetric Result" in symmetric

    child.send("\x1b[B" * 4)
    _BASE._pump(child, seconds=0.8)
    directional = _BASE._snapshot(recorder, "04-directional-example")
    assert (
        "FORM 9 · mem meld team/proposed-changes --into team/current-policy"
        in directional
    )
    assert "example: directional Baseline" in directional

    _close(child)


if __name__ == "__main__":
    main()
