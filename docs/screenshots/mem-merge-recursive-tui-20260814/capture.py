"""Capture direct, recursive, and cancelled Merge flows in a real color PTY."""

from __future__ import annotations

import importlib.util
import io
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pexpect


ROOT = Path("/Users/KimMunyeong/Github/memcommit")
OUT = ROOT / "docs/screenshots/mem-merge-recursive-tui-20260814"
COLUMNS = 180
ROWS = 52
SHIFT_TAB = "\x1b[Z"
RIGHT = "\x1b[C"
DOWN = "\x1b[B"

_BASE_PATH = (
    ROOT / "docs/screenshots/context-endpoint-memory-preview-20260810/capture.py"
)
_SPEC = importlib.util.spec_from_file_location("merge_capture_base", _BASE_PATH)
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


def _initialize() -> tuple[str, str]:
    import memcommit.ops as ops
    from memcommit.store import MemoryStore

    store = MemoryStore()
    source = ops.init("source")
    root_memory = ops.add(source, "source root fact")
    store.create_context(source)
    child = ops.init("source/child")
    child_memory = ops.add(child, "source child fact")
    store.create_context(child)
    store.create_context(ops.init("target"))
    preserved = ops.init("target/preserved")
    ops.add(preserved, "target-only fact")
    store.create_context(preserved)
    store.set_current("target")
    return root_memory.uid, child_memory.uid


def _run_merge_child(kind: str) -> None:
    import click

    from memcommit.cli import app
    from memcommit.store import MemoryStore

    with tempfile.TemporaryDirectory(prefix="mem-merge-capture-") as directory:
        _configure_isolated_store(Path(directory) / ".mem")
        root_uid, child_uid = _initialize()
        if kind == "failure":
            from memcommit.merge_runtime import MemoryStoreMergePort

            def fail_before_persistence(_port, _plan):
                raise OSError("injected capture failure before persistence")

            MemoryStoreMergePort.apply = fail_before_persistence
        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        command_exit = 0
        try:
            returned = app(args=["merge"], prog_name="mem", standalone_mode=False)
        except click.exceptions.Exit as error:
            if kind != "failure" or error.exit_code != 1:
                raise
            command_exit = error.exit_code
        else:
            if isinstance(returned, int):
                command_exit = returned
        if kind == "failure":
            assert command_exit == 1
            print(f"FAILURE COMMAND EXIT · {command_exit}")

        store = MemoryStore()
        target = store.load_direct("target")
        root_copied = root_uid in target.memories
        child_exists = store.context_exists("target/child")
        child_copied = (
            child_exists and child_uid in store.load_direct("target/child").memories
        )
        checkpoints = store.list_checkpoints("target")
        print(
            f"{kind.upper()} VERIFICATION · ROOT COPIED {root_copied} · "
            f"CHILD EXISTS {child_exists} · CHILD COPIED {child_copied} · "
            f"PRESERVED EXISTS {store.context_exists('target/preserved')} · "
            f"ROOT CHECKPOINTS {len(checkpoints)}"
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


def _capture_direct() -> None:
    child, recorder = _spawn("direct")
    try:
        child.expect("MEM MERGE")
        _BASE._settle(child)
        _snapshot(recorder, "01-direct-entry")

        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "02-direct-exact-command")

        child.send("\r")
        child.expect("STATUS · SUCCESS")
        _BASE._settle(child)
        _snapshot(recorder, "03-direct-success")

        child.send("\r")
        child.expect("DIRECT VERIFICATION")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "04-direct-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_recursive() -> None:
    child, recorder = _spawn("recursive")
    try:
        child.expect("MEM MERGE")
        child.send(SHIFT_TAB + RIGHT)
        _BASE._settle(child)
        _snapshot(recorder, "05-recursive-range")

        child.send("\t\t")
        _BASE._settle(child)
        _snapshot(recorder, "06-recursive-exact-command")

        child.send("\r")
        child.expect("STATUS · SUCCESS")
        _BASE._settle(child)
        _snapshot(recorder, "07-recursive-success")

        child.send("\r")
        child.expect("RECURSIVE VERIFICATION")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "08-recursive-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_cancel() -> None:
    child, recorder = _spawn("cancel")
    try:
        child.expect("MEM MERGE")
        child.send("q")
        child.expect("CANCEL VERIFICATION")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "09-cancel-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_help() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        executable,
        ["help"],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=15,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    try:
        child.expect("command inventory")
        # Contexts -> Memories -> Search & Explain -> Analyze & Transform,
        # then move from Audit to Merge and open its complete typed detail.
        child.send("\t" * 3 + DOWN * 9 + RIGHT + DOWN * 2)
        _BASE._settle(child)
        _snapshot(recorder, "10-merge-help-detail")
        detail = (OUT / "10-merge-help-detail.txt").read_text(encoding="utf-8")
        assert "▾ mem merge" in detail
        assert "mem merge [source_context] --direct" in detail
        assert "mem merge [source_context] --recursive" in detail
        child.send("q")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_failure() -> None:
    child, recorder = _spawn("failure")
    try:
        child.expect("MEM MERGE")
        child.send("\t\r")
        child.expect("Merge failed")
        _BASE._settle(child)
        _snapshot(recorder, "11-failure-before-persistence")

        child.send("q")
        child.expect("FAILURE VERIFICATION")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "12-failure-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _capture_direct()
    _capture_recursive()
    _capture_cancel()
    _capture_help()
    _capture_failure()
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "PTY 180 52" in raw
    assert "\x1b[" in raw
    assert "38;" in raw
    assert "48;" in raw


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT))
        _run_merge_child(sys.argv[2])
    else:
        main()
