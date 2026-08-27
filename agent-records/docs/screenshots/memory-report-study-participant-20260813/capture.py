"""Capture Trace/Rationale against the current task-1 participant study data."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import os
from pathlib import Path
import re
import sys

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/docs/screenshots/memory-report-study-participant-20260813"
COLUMNS = 180
ROWS = 52
RIGHT = "\x1b[C"
DOWN = "\x1b[B"
CURRENT = "task-1/participant"

_BASE_PATH = (
    ROOT / "agent-records/docs/screenshots/context-endpoint-memory-preview-20260810/capture.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "study_participant_capture_base", _BASE_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _durable_study_digest() -> str:
    """Hash durable Context and current-pointer files without opening a provider."""

    import memcommit.persistence.store as store_module

    paths = [store_module.STATE_FILE]
    if store_module.CONTEXTS_DIR.exists():
        paths.extend(
            path for path in store_module.CONTEXTS_DIR.rglob("*") if path.is_file()
        )
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda value: str(value)):
        digest.update(str(path).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _run_child(operation: str) -> None:
    from memcommit.adapters.console.commands import rationale, trace
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(create=False)
    current = store.current_context_name()
    before = _durable_study_digest()
    print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
    if operation == "trace":
        trace.cmd(context_name=CURRENT)
    elif operation == "rationale":
        rationale.cmd(context_name=CURRENT, recorded_only=True)
    else:
        raise ValueError(f"Unknown operation: {operation}")
    if _durable_study_digest() != before:
        raise RuntimeError("Study Context data changed during read-only capture.")
    print(
        f"{operation.upper()} CLOSED · TARGET {CURRENT} · CURRENT {current} · "
        "READ ONLY · STUDY STORE UNCHANGED"
    )


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _spawn(operation: str) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", operation],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> None:
    _BASE._snapshot(recorder, stem)


def _capture(operation: str, start: int) -> int:
    child, recorder = _spawn(operation)
    try:
        child.expect(f"{operation.upper()} · SELECT A MEMORY · {CURRENT}")
        _BASE._settle(child)
        _snapshot(recorder, f"{start:02d}-{operation}-exact-entry")

        child.send(RIGHT)
        _BASE._settle(child)
        _snapshot(recorder, f"{start + 1:02d}-{operation}-descendants")

        # Root -> construction-updates -> building-access -> first real Memory.
        child.send("\t" + DOWN * 3)
        _BASE._settle(child)
        _snapshot(recorder, f"{start + 2:02d}-{operation}-study-memory-focused")

        child.send("\r")
        child.expect("TRACE · MEMORY" if operation == "trace" else "RATIONALE REPORT")
        _BASE._settle(child)
        _snapshot(recorder, f"{start + 3:02d}-{operation}-result")

        child.send("q")
        child.expect(f"{operation.upper()} CLOSED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, f"{start + 4:02d}-{operation}-verification")
    finally:
        if child.isalive():
            child.close(force=True)
    return start + 5


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    next_index = _capture("trace", 1)
    _capture("rationale", next_index)
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert CURRENT in raw
    assert "Modify campus-wiki/building-access" in raw
    assert "[8b077f2a][r0]" in raw.casefold()
    assert "[current" not in raw.casefold()
    assert "CONTEXTS & MEMORIES" in raw
    assert "┏" in raw and "┗" in raw
    assert "38;" in raw
    assert any(
        "7" in codes.split(";") for codes in re.findall("\x1b\\[([0-9;]*)m", raw)
    )


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT / "src"))
        _run_child(sys.argv[2])
    else:
        main()
