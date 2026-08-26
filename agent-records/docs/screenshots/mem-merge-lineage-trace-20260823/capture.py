"""Capture bidirectional Merge lineage through real color PTYs."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/docs/screenshots/mem-merge-lineage-trace-20260823"
COLUMNS = 180
ROWS = 52
SOURCE_UID = "cd518767"
TARGET_UID = "423582d8"
END = "\x1b[F"

_BASE_PATH = (
    ROOT / "agent-records/docs/screenshots/context-endpoint-memory-preview-20260810/capture.py"
)
_SPEC = importlib.util.spec_from_file_location("merge_lineage_trace_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PYTHONPATH": str(ROOT / "src"),
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _spawn(command: str) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        "zsh",
        ["-lc", command],
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


def _interactive_capture(
    uid: str,
    stem: str,
    closed_label: str,
    *,
    bottom_stem: str | None = None,
) -> None:
    command = f"""
set -eu
printf 'LIVE PTY · '
stty size
mem profile current
before="$(python -c 'from memcommit.store import MemoryStore; print(MemoryStore().current_context_name() or "<none>")')"
mem trace {uid} --all --tui
after="$(python -c 'from memcommit.store import MemoryStore; print(MemoryStore().current_context_name() or "<none>")')"
test "$before" = "$after"
printf '{closed_label}\n'
""".strip()
    child, recorder = _spawn(command)
    try:
        child.expect("Source:")
        _BASE._settle(child)
        _snapshot(recorder, stem)
        if bottom_stem is not None:
            child.send(END)
            _BASE._settle(child)
            _snapshot(recorder, bottom_stem)
        child.send("q")
        child.expect(closed_label)
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _verification_capture() -> None:
    command = f"""
set -eu
printf 'LIVE PTY · '
stty size
mem profile current
before="$(python -c 'from memcommit.store import MemoryStore; print(MemoryStore().current_context_name() or "<none>")')"
mem trace {SOURCE_UID} --plain --all
after="$(python -c 'from memcommit.store import MemoryStore; print(MemoryStore().current_context_name() or "<none>")')"
test "$before" = "$after"
printf 'READ-ONLY VERIFIED · SOURCE AND TARGET UID TRACE CONNECTED · CURRENT CONTEXT UNCHANGED\n'
""".strip()
    child, recorder = _spawn(command)
    try:
        child.expect("READ-ONLY VERIFIED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "04-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for pattern in ("*.png", "*.txt", "*.typescript"):
        for path in OUT.glob(pattern):
            path.unlink()

    _interactive_capture(
        SOURCE_UID,
        "01-source-uid-connected-trace",
        "SOURCE TRACE CLOSED · READ ONLY",
        bottom_stem="02-source-history-origin",
    )
    _interactive_capture(
        TARGET_UID,
        "03-target-uid-connected-trace",
        "TARGET TRACE CLOSED · READ ONLY",
    )
    _verification_capture()

    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    plain = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.txt"))
    assert "52 180" in raw
    assert "[merge] [CHECKPOINT 604759a1] [MEMORIES 2]" in plain
    assert "[replace] [CHECKPOINT 1c513717] [MEMORY cd518767]" in plain
    assert "[move] [CHECKPOINT d736546d] [MEMORY cd518767]" in plain
    assert "Source: [cd518767] Wiki update draft:" in plain
    assert "Target: [423582d8] Wiki update draft:" in plain
    assert "READ-ONLY VERIFIED" in plain
    assert "CURRENT CONTEXT UNCHANGED" in plain
    assert "38;" in raw
    assert "48;" in raw


if __name__ == "__main__":
    main()
