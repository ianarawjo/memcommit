"""Capture exact Revert version selection and result-level Merge rejection."""

from __future__ import annotations

import io
import os
from pathlib import Path
import shlex
import sys
import tempfile
import time

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SUPPORT = ROOT / "agent-records/docs/screenshots/distill-elaborate-shared-app-20260815"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(SUPPORT))

from capture_support import StreamRecorder, snapshot  # noqa: E402


COLUMNS = 180
ROWS = 52
RIGHT = "\x1b[C"
DOWN = "\x1b[B"
CPR_REQUEST = "\x1b[6n"
CPR_RESPONSE = "\x1b[1;1R"


def _configure_store(store_dir: Path) -> None:
    import memcommit.store as store_module

    store_module.STORE_DIR = store_dir


def _prepare_revert_store(store_dir: Path) -> tuple[str, str]:
    import memcommit.application.ops as ops
    from memcommit.context import AutoCheckpoint
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_dir)
    context = ops.init("revert/versions")
    store.save(
        context,
        AutoCheckpoint(
            command="init",
            args={"name": context.name},
            description="Initialized exact-version example",
        ),
    )
    memory = ops.add(context, "Version one remains after the reviewed Revert.")
    shared_args = {
        "update_session_uid": "repeated-operation-example",
        "operation_digest": "same-command-unit-identity",
    }
    first = store.save(
        context,
        AutoCheckpoint(
            command="update",
            args=shared_args,
            description="Version one · repeated Update identity",
        ),
    )
    ops.edit(
        context,
        memory.uid,
        "Version two is removed by the reviewed Revert.",
    )
    second = store.save(
        context,
        AutoCheckpoint(
            command="update",
            args=shared_args,
            description="Version two · repeated Update identity",
        ),
    )
    store.set_current(context.name)
    return first.uid, second.uid


def _prepare_merge_store(store_dir: Path) -> None:
    import memcommit.application.ops as ops
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_dir)
    source = ops.init("merge/source")
    ops.add(source, "Source Memory remains unchanged.")
    store.create_context(source)
    target = ops.init("merge/target")
    ops.add(target, "Target Memory remains unchanged.")
    store.create_context(target)
    store.set_current(target.name)


def _run_revert(store_dir: Path) -> None:
    _configure_store(store_dir)
    from memcommit.commands.revert.command import cmd

    print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
    cmd()


def _run_merge(store_dir: Path) -> None:
    _configure_store(store_dir)
    from memcommit.commands.merge.command import cmd

    print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
    cmd()


def _verify_revert(store_dir: Path, first_uid: str, second_uid: str) -> None:
    _configure_store(store_dir)
    from memcommit.context import Memory
    from memcommit.store import MemoryStore

    store = MemoryStore(create=False)
    context = store.load_direct("revert/versions")
    contents = [
        item.content for item in context.iter_items() if isinstance(item, Memory)
    ]
    visible = {checkpoint["uid"] for checkpoint in store.list_checkpoints(context.name)}
    print("READ-ONLY REVERT VERIFICATION")
    print(f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}")
    print(f"Context: {context.name}")
    print(f"Memories: {contents}")
    print(f"Selected checkpoint retained: {first_uid in visible}")
    print(f"Newer checkpoint discarded: {second_uid not in visible}")
    print(f"Current pointer unchanged: {store.current_context_name() == context.name}")


def _verify_merge(store_dir: Path) -> None:
    _configure_store(store_dir)
    from memcommit.context import Memory
    from memcommit.store import MemoryStore

    store = MemoryStore(create=False)
    print("READ-ONLY MERGE REJECTION VERIFICATION")
    print(f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}")
    for name in ("merge/source", "merge/target"):
        context = store.load_direct(name)
        contents = [
            item.content for item in context.iter_items() if isinstance(item, Memory)
        ]
        print(f"{name}: {contents}")
        print(f"{name} checkpoints: {len(store.list_checkpoints(name))}")
    print(f"Current Context: {store.current_context_name()}")


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PROMPT_TOOLKIT_COLOR_DEPTH": "DEPTH_24_BIT",
            "PYTHONPATH": os.pathsep.join(
                (str(ROOT / "src"), environment.get("PYTHONPATH", ""))
            ),
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _spawn(*args: str) -> tuple[pexpect.spawn, StreamRecorder]:
    command = (
        f"stty rows {ROWS} cols {COLUMNS}; stty size; "
        f"exec {shlex.join([sys.executable, str(Path(__file__).resolve()), *args])}"
    )
    recorder = StreamRecorder()
    child = pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    child._mem_cpr_responses = 0
    return child, recorder


def _pump(
    child: pexpect.spawn,
    recorder: io.StringIO,
    *,
    seconds: float = 0.5,
) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            child.read_nonblocking(size=65_536, timeout=0.05)
        except pexpect.TIMEOUT:
            pass
        except pexpect.EOF:
            return
        query_count = recorder.getvalue().count(CPR_REQUEST)
        while child._mem_cpr_responses < query_count:
            child.send(CPR_RESPONSE)
            child._mem_cpr_responses += 1


def _snapshot(recorder: io.StringIO, stem: str) -> None:
    snapshot(recorder, stem, out=OUT, columns=COLUMNS, rows=ROWS)


def _capture_revert(
    store_dir: Path,
    first_uid: str,
    second_uid: str,
) -> None:
    child, recorder = _spawn("--revert", str(store_dir))
    try:
        child.expect("REVERT · SELECT A CONTEXT")
        _pump(child, recorder)
        _snapshot(recorder, "01-revert-context-entry")

        child.send(RIGHT)
        child.expect("Version one · repeated Update identity")
        _pump(child, recorder)
        _snapshot(recorder, "02-all-exact-versions-visible")

        child.send(DOWN * 2)
        _pump(child, recorder)
        _snapshot(recorder, "03-older-version-focused")

        child.send("\r")
        child.expect("REVERT · revert/versions")
        child.expect(first_uid[:8])
        _pump(child, recorder)
        _snapshot(recorder, "04-version-staged-history-policy")

        child.send("\r")
        _pump(child, recorder)
        _snapshot(recorder, "05-exact-apply")

        child.send("\r")
        child.expect("Reverted Context")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "06-revert-success-receipt")
    finally:
        if child.isalive():
            child.close(force=True)

    verify, verify_recorder = _spawn(
        "--verify-revert",
        str(store_dir),
        first_uid,
        second_uid,
    )
    try:
        verify.expect("Newer checkpoint discarded: True")
        verify.expect(pexpect.EOF)
        _snapshot(verify_recorder, "07-revert-read-only-verification")
    finally:
        if verify.isalive():
            verify.close(force=True)


def _capture_merge(store_dir: Path) -> None:
    child, recorder = _spawn("--merge", str(store_dir))
    try:
        child.expect("NEW MERGE · A")
        _pump(child, recorder)
        _snapshot(recorder, "08-merge-entry")

        child.send("\t" + DOWN + "\r")
        _pump(child, recorder)
        _snapshot(recorder, "09-same-target-source-selected")

        child.send("\t\r")
        child.expect("must be distinct")
        _pump(child, recorder)
        _snapshot(recorder, "10-same-result-rejected-at-continue")

        child.send("q")
        child.expect("Merge cancelled")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)

    verify, verify_recorder = _spawn("--verify-merge", str(store_dir))
    try:
        verify.expect("merge/target checkpoints: 0")
        verify.expect(pexpect.EOF)
        _snapshot(verify_recorder, "11-merge-read-only-verification")
    finally:
        if verify.isalive():
            verify.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-revert-inline-") as temporary:
        temporary_root = Path(temporary)
        revert_store = temporary_root / "revert-store"
        merge_store = temporary_root / "merge-store"
        first_uid, second_uid = _prepare_revert_store(revert_store)
        _prepare_merge_store(merge_store)
        _capture_revert(revert_store, first_uid, second_uid)
        _capture_merge(merge_store)
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "38;" in raw
    assert "48;" in raw


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--revert":
        _run_revert(Path(sys.argv[2]))
    elif len(sys.argv) == 3 and sys.argv[1] == "--merge":
        _run_merge(Path(sys.argv[2]))
    elif len(sys.argv) == 5 and sys.argv[1] == "--verify-revert":
        _verify_revert(Path(sys.argv[2]), sys.argv[3], sys.argv[4])
    elif len(sys.argv) == 3 and sys.argv[1] == "--verify-merge":
        _verify_merge(Path(sys.argv[2]))
    else:
        main()
