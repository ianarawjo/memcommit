"""Capture the shared quality-finder range setup in a real color PTY."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import sys

import pexpect


ROOT = Path("/Users/KimMunyeong/Github/memcommit")
OUT = ROOT / "docs/screenshots/quality-find-range-20260813"
COLUMNS = 180
ROWS = 52
DOWN = "\x1b[B"
UP = "\x1b[A"
RIGHT = "\x1b[C"
SHIFT_TAB = "\x1b[Z"

_BASE_PATH = (
    ROOT / "docs/screenshots/context-endpoint-memory-preview-20260810/capture.py"
)
_SPEC = importlib.util.spec_from_file_location("quality_find_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _run_child() -> None:
    from memcommit.commands.quality_find_workbench import choose_quality_find_setup

    print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
    receipt = choose_quality_find_setup(
        (
            "study",
            "study/policy",
            "study/policy/archive",
            "study/operations",
            "personal",
        ),
        current="study/policy",
        kind="duplicates",
    )
    if receipt is None:
        print("QUALITY FIND SETUP CANCELLED · NO PROVIDER · NO SOURCE MUTATION")
        return
    print(
        "APPROVED QUALITY FIND RANGE · "
        f"{receipt.selection_mode} · "
        f"{'INCLUDE DESCENDANTS' if receipt.include_descendants else 'THIS CONTEXT ONLY'}"
    )
    print("ROOTS", ", ".join(receipt.target_names) or "PROFILE")
    print("EFFECTIVE", ", ".join(receipt.context_names))
    input("PRESS ENTER FOR READ-ONLY VERIFICATION")
    print(
        "VERIFIED · SETUP CREATED NO CONTEXT, CHECKPOINT, FINDING ARTIFACT, "
        "OR PROVIDER CONNECTION"
    )


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update({"TERM": "xterm-256color", "COLORTERM": "truecolor"})
    return environment


def _spawn() -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child"],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=15,
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
        child.expect("MEM FIND DUPLICATES · SETUP")
        _BASE._settle(child)
        _snapshot(recorder, "01-entry-current-target")

        child.send(DOWN)
        child.send("\r")
        _BASE._settle(child)
        _snapshot(recorder, "02-multiple-independent-targets")

        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "03-multiple-target-setting")

        child.send(DOWN)
        child.send(RIGHT)
        _BASE._settle(child)
        _snapshot(recorder, "04-include-descendants-setting")

        child.send(SHIFT_TAB)
        child.send(UP)
        child.send(RIGHT)
        _BASE._settle(child)
        _snapshot(recorder, "05-effective-descendant-visible")

        child.send("\t\t")
        _BASE._settle(child)
        _snapshot(recorder, "06-exact-run-review")

        child.send("\r")
        child.expect("APPROVED QUALITY FIND RANGE")
        child.expect("PRESS ENTER FOR READ-ONLY VERIFICATION")
        _BASE._settle(child)
        _snapshot(recorder, "07-approved-range-receipt")

        child.send("\r")
        child.expect("VERIFIED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "08-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)

    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "38;5" in raw
    assert "48;5" in raw


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT))
        _run_child()
    else:
        main()
