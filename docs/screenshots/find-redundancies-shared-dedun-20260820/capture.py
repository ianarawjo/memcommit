"""Capture read-only Find Redundancies and Dedun's exclusive handoff."""

from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/screenshots/find-redundancies-shared-dedun-20260820"
COLUMNS = 180
ROWS = 52

_SUPPORT_PATH = (
    ROOT / "docs/screenshots/quality-conflict-resolve-handoff-20260816/capture.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "quality_find_capture_support",
    _SUPPORT_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_SUPPORT = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_SUPPORT)
_BASE = _SUPPORT._BASE
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS

QUALITY_MARKER = "QUALITY FIND PAYLOAD:\n"


def _initialize() -> None:
    from memcommit.context import Context, Memory
    from memcommit.store import MemoryStore

    context = Context(
        uid="10000000-0000-4000-8000-000000000110",
        name="quality/redundancy-capture",
    )
    context.add(
        Memory(
            uid="20000000-0000-4000-8000-000000000110",
            content="The parking garage is inaccessible after 10 p.m.",
        )
    )
    context.add(
        Memory(
            uid="20000000-0000-4000-8000-000000000120",
            content="Do not enter the parking garage after 22:00.",
        )
    )
    store = MemoryStore()
    store.create_context(context)
    store.set_current(context.name)


class _Provider:
    def __init__(self) -> None:
        self.operations: list[str] = []

    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        assert operation == "find_duplicates"
        assert output_schema is not None
        self.operations.append(operation)
        payload = json.loads(prompt.split(QUALITY_MARKER, 1)[1])
        candidate_ids = [item["candidate_id"] for item in payload["memories"]]
        assert len(candidate_ids) == 2
        return json.dumps(
            {
                "findings": [
                    {
                        "candidate_ids": candidate_ids,
                        "relation": "SEMANTIC_EQUIVALENT",
                        "reason": (
                            "Both Memories prohibit garage access after the same "
                            "10 p.m. boundary."
                        ),
                    }
                ]
            }
        )


def _verification(label: str, provider: _Provider) -> str:
    from memcommit.context import Memory
    from memcommit.store import MemoryStore

    store = MemoryStore()
    context = store.load_direct("quality/redundancy-capture")
    memories = [item.content for item in context.iter_items() if isinstance(item, Memory)]
    return (
        f"{label} VERIFICATION · MEMORIES {len(memories)} · "
        f"CHECKPOINTS {len(store.list_checkpoints(context.name))} · "
        f"CURRENT {store.current_context_name()} · "
        f"PROVIDER OPERATIONS {provider.operations!r}"
    )


def _run_child(command: str) -> None:
    import click

    import memcommit.commands.find_duplicates.command as find_command
    from memcommit.cli import app

    with tempfile.TemporaryDirectory(prefix="find-redundancies-capture-") as directory:
        _SUPPORT._configure_isolated_store(Path(directory) / ".mem")
        _initialize()
        provider = _Provider()
        find_command.connect_codex_chatgpt_provider = lambda: provider

        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        exit_code = 0
        try:
            returned = app(args=[command], prog_name="mem", standalone_mode=False)
        except click.exceptions.Exit as error:
            exit_code = error.exit_code
        else:
            if isinstance(returned, int):
                exit_code = returned
        print(f"COMMAND EXIT · {exit_code}")
        print(_verification(command.upper(), provider), flush=True)
        sys.stdin.readline()


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


def _spawn(command: str) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", command],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=25,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> str:
    _BASE._snapshot(recorder, stem)
    return (OUT / f"{stem}.txt").read_text(encoding="utf-8")


def _capture_find() -> None:
    child, recorder = _spawn("find-redundancies")
    try:
        child.expect("MEM FIND REDUNDANCIES · SETUP")
        _BASE._settle(child)
        _snapshot(recorder, "01-find-setup-entry")

        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "02-find-source-scope")

        child.send("\t")
        _BASE._settle(child)
        run = _snapshot(recorder, "03-find-run-approval")
        assert "RUN FIND REDUNDANCIES" in run

        child.send("\r")
        child.expect("PROCESS LOCAL")
        _BASE._settle(child, seconds=0.8)
        report = _snapshot(recorder, "04-find-read-only-report")
        assert "PROCESS LOCAL" in report
        assert "No Context or Memory changes have been applied" in report

        child.send("\t\x1b[B")
        _BASE._settle(child)
        _snapshot(recorder, "05-find-evidence-row")

        child.send("\r")
        _BASE._settle(child)
        detail = _snapshot(recorder, "06-find-evidence-detail")
        assert "SEMANTIC_EQUIVALENT" in detail

        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "07-find-confirm-choice")

        child.send("\r")
        _BASE._settle(child)
        confirmed = _snapshot(recorder, "08-find-confirmed-process-local")
        assert "CONFIRM LINK" in confirmed

        child.send("\t\t")
        _BASE._settle(child)
        close = _snapshot(recorder, "09-find-close-without-handoff")
        assert "Dedun 1 confirmed" not in close

        child.send("q")
        child.expect("FIND-REDUNDANCIES VERIFICATION")
        _BASE._settle(child)
        verification = _snapshot(recorder, "10-find-read-only-verification")
        assert "MEMORIES 2" in verification
        assert "CHECKPOINTS 0" in verification
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_dedun_boundary() -> None:
    child, recorder = _spawn("dedun")
    try:
        child.expect("MEM DEDUN · SETUP")
        child.send("\t\t\r")
        child.expect("PROCESS LOCAL")
        _BASE._settle(child, seconds=0.8)
        child.send("\t\x1b[B\r\t\r\t\t")
        _BASE._settle(child)
        handoff = _snapshot(recorder, "11-dedun-exclusive-handoff")
        assert "Dedun 1 confirmed semantic redundancy link" in handoff

        child.send("q")
        child.expect("DEDUN VERIFICATION")
        _BASE._settle(child)
        verification = _snapshot(recorder, "12-dedun-cancelled-verification")
        assert "MEMORIES 2" in verification
        assert "CHECKPOINTS 0" in verification
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _capture_find()
    _capture_dedun_boundary()
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "PTY 180 52" in raw
    assert "\x1b[" in raw
    assert "38;" in raw
    assert "48;" in raw


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT))
        _run_child(sys.argv[2])
    else:
        main()
