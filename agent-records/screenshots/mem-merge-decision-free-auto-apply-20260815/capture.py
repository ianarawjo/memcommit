"""Capture decision-free Merge auto-apply and checkpoint recovery."""

from __future__ import annotations

import importlib.util
import io
import os
import sys
import tempfile
from pathlib import Path

import pexpect


ROOT = Path("/Users/KimMunyeong/Github/memcommit")
OUT = ROOT / "agent-records/screenshots/mem-merge-decision-free-auto-apply-20260815"
COLUMNS = 180
ROWS = 52

_BASE_PATH = ROOT / "agent-records/screenshots/context-endpoint-memory-preview-20260810/capture.py"
_SPEC = importlib.util.spec_from_file_location("merge_auto_apply_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _configure_isolated_store(store_root: Path) -> None:
    import memcommit.store as store_module

    values = {
        "STORE_DIR": store_root,
        "CONTEXTS_DIR": store_root / "contexts",
        "QUERY_SOURCES_DIR": store_root / "query-sources",
        "STATE_FILE": store_root / "state.json",
        "IMPACT_PLAN_FILE": store_root / "impact-plan.json",
        "STAGED_UPDATE_FILE": store_root / "staged-update.json",
        "REVIEW_SESSION_FILE": store_root / "review-session.json",
        "ATOMIZE_ANALYSES_DIR": store_root / "atomize-analyses",
        "ATOMIZE_WORKBENCHES_DIR": store_root / "atomize-workbenches",
        "ATOMIZE_GROUNDING_SESSIONS_DIR": store_root / "atomize-groundings",
        "ATOMIZE_GROUNDING_HISTORY_DIR": store_root / "atomize-grounding-history",
        "GROUND_SESSIONS_DIR": store_root / "ground-sessions",
        "MELD_SESSIONS_DIR": store_root / "meld-sessions",
    }
    for name, value in values.items():
        setattr(store_module, name, value)


def _initialize(kind: str) -> str:
    import memcommit.ops as ops
    from memcommit.context import Memory
    from memcommit.store import MemoryStore

    store = MemoryStore()
    uid = "00000000-0000-0000-0000-000000000001"
    source = ops.init("source")
    target = ops.init("target")
    if kind == "noop":
        source.add(Memory(uid=uid, content="identical retained fact"))
        target.add(Memory(uid=uid, content="identical retained fact"))
    else:
        source.add(Memory(uid=uid, content="decision-free source addition"))
    store.create_context(source)
    store.create_context(target)
    store.set_current("target")
    return uid


def _state(label: str, uid: str) -> None:
    from memcommit.store import MemoryStore

    store = MemoryStore()
    target = store.load_direct("target")
    print(
        f"{label} · TARGET HAS UID {uid in target.memories} · "
        f"CHECKPOINTS {len(store.list_checkpoints('target'))}"
    )


def _run_child(kind: str) -> None:
    import click
    import typer

    from memcommit.commands.merge.command import cmd as merge_command
    from memcommit.commands.redo.command import cmd as redo_command
    from memcommit.commands.undo.command import cmd as undo_command

    with tempfile.TemporaryDirectory(prefix="mem-merge-auto-apply-") as directory:
        _configure_isolated_store(Path(directory) / ".mem")
        uid = _initialize(kind)
        if kind == "failure":
            from memcommit.merge_runtime import MemoryStoreMergePort

            def fail_before_persistence(*_args):
                raise OSError("injected auto-apply failure before persistence")

            MemoryStoreMergePort.apply = fail_before_persistence

        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        app = typer.Typer()

        @app.callback()
        def capture_root() -> None:
            """Keep the focused capture in command-group mode."""

        app.command("merge")(merge_command)
        app.command("undo")(undo_command)
        app.command("redo")(redo_command)

        exit_code = 0
        try:
            returned = app(args=["merge"], prog_name="mem", standalone_mode=False)
        except click.exceptions.Exit as error:
            exit_code = error.exit_code
        else:
            if isinstance(returned, int):
                exit_code = returned
        if kind == "failure":
            print(f"FAILURE COMMAND EXIT · {exit_code}")
            _state("FAILURE VERIFICATION", uid)
            return

        assert exit_code == 0
        _state(f"{kind.upper()} AFTER MERGE", uid)
        if kind != "noop":
            return

        print("CAPTURE PAUSE · PRESS ENTER FOR UNDO")
        sys.stdin.readline()
        app(args=["undo"], prog_name="mem", standalone_mode=False)
        _state("NOOP AFTER UNDO", uid)
        print("CAPTURE PAUSE · PRESS ENTER FOR REDO")
        sys.stdin.readline()
        app(args=["redo"], prog_name="mem", standalone_mode=False)
        _state("NOOP AFTER REDO", uid)


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


def _spawn(kind: str) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind],
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


def _capture_addition() -> None:
    child, recorder = _spawn("addition")
    try:
        child.expect("NEW MERGE")
        _BASE._settle(child)
        _snapshot(recorder, "01-decision-free-setup")
        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "02-conditional-auto-apply-action")
        child.send("\r")
        child.expect("ADDITION AFTER MERGE")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "03-auto-applied-checkpoint-receipt")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_noop_recovery() -> None:
    child, recorder = _spawn("noop")
    try:
        child.expect("NEW MERGE")
        child.send("\t\r")
        child.expect("NO TARGET CHANGE|nothing new")
        child.expect("CAPTURE PAUSE · PRESS ENTER FOR UNDO")
        _snapshot(recorder, "04-noop-auto-applied-checkpoint")
        child.send("\r")
        child.expect("NOOP AFTER UNDO")
        child.expect("CAPTURE PAUSE · PRESS ENTER FOR REDO")
        _snapshot(recorder, "05-noop-undo-receipt")
        child.send("\r")
        child.expect("NOOP AFTER REDO")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "06-noop-redo-receipt")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_failure() -> None:
    child, recorder = _spawn("failure")
    try:
        child.expect("NEW MERGE")
        child.send("\t\r")
        child.expect("injected auto-apply failure")
        child.expect("FAILURE VERIFICATION")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "07-auto-apply-failure-no-checkpoint")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _capture_addition()
    _capture_noop_recovery()
    _capture_failure()
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "PTY 180 52" in raw
    assert "\x1b[" in raw
    assert "48;5;" in raw
    assert "REVIEW FROZEN PLAN" not in (
        OUT / "03-auto-applied-checkpoint-receipt.typescript"
    ).read_text(encoding="utf-8")
    assert "CHECKPOINTS 1" in (
        OUT / "04-noop-auto-applied-checkpoint.txt"
    ).read_text(encoding="utf-8")
    assert "CHECKPOINTS 0" in (
        OUT / "07-auto-apply-failure-no-checkpoint.txt"
    ).read_text(encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT / "src"))
        _run_child(sys.argv[2])
    else:
        main()
