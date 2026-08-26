"""Capture typed UID roles and inherited Branch lineage in Revert's browser."""

from __future__ import annotations

import io
import os
from pathlib import Path
import re
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
UP = "\x1b[A"
CPR_REQUEST = "\x1b[6n"
CPR_RESPONSE = "\x1b[1;1R"


def _configure_store(store_dir: Path) -> None:
    import memcommit.store as store_module

    store_module.STORE_DIR = store_dir


def _prepare_store(store_dir: Path) -> tuple[str, str, str, int]:
    _configure_store(store_dir)
    os.environ["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"
    from typer.testing import CliRunner

    from memcommit.cli import app
    from memcommit.store import MemoryStore

    runner = CliRunner()

    def run(*arguments: str) -> str:
        result = runner.invoke(app, list(arguments))
        if result.exit_code != 0:
            raise RuntimeError(
                f"Fixture command failed ({shlex.join(('mem', *arguments))}): "
                f"{result.output}"
            )
        return result.output

    run("init", "practice/1")
    added = run("add", "123123 gogogo")
    match = re.search(r"\[([0-9a-f-]{8,36})\]", added)
    if match is None:
        raise RuntimeError(f"Could not recover fixture Memory UID: {added!r}")
    memory_selector = match.group(1)
    source = MemoryStore(create=False).load_direct("practice/1")
    memory_uid = next(
        uid for uid in source.memories if uid.startswith(memory_selector)
    )
    run("branch", "practice/2")
    run("embed", "practice/1", "--into", "practice/2", "--after", memory_uid)
    run("edit", memory_uid, "dfadfadfadfasf")
    run("remove", memory_uid)
    run("undo")
    run("redo")
    run("undo")

    store = MemoryStore(create=False)
    checkpoints = store.list_checkpoints("practice/2")
    latest_undo_uid = next(
        checkpoint["uid"]
        for checkpoint in checkpoints
        if checkpoint.get("command") == "undo"
    )
    inherited_add_uid = next(
        checkpoint["uid"]
        for checkpoint in checkpoints
        if checkpoint.get("command") == "add"
    )
    return latest_undo_uid, inherited_add_uid, memory_uid, len(checkpoints)


def _run_revert(store_dir: Path) -> None:
    _configure_store(store_dir)
    from memcommit.commands.revert.command import cmd

    print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
    cmd()


def _verify(
    store_dir: Path,
    memory_uid: str,
    expected_checkpoint_count: int,
) -> None:
    _configure_store(store_dir)
    from memcommit.history_display import (
        checkpoint_command_identity,
        checkpoint_inherited_from,
    )
    from memcommit.store import MemoryStore

    store = MemoryStore(create=False)
    context = store.load_direct("practice/2")
    checkpoints = store.list_checkpoints(context.name)
    direct: set[str] = set()
    inherited: set[str] = set()
    for checkpoint in checkpoints:
        identity = checkpoint_command_identity(checkpoint)
        if identity is None:
            continue
        destination = (
            inherited
            if checkpoint_inherited_from(
                checkpoint,
                context_name=context.name,
                context_uid=context.uid,
            )
            is not None
            else direct
        )
        destination.add(identity)

    print("READ-ONLY HISTORY VERIFICATION")
    print(f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}")
    print(f"Context: {context.name}")
    print(f"Current pointer unchanged: {store.current_context_name() == context.name}")
    print(f"Memory restored by final Undo: {memory_uid in context.memories}")
    print(f"Direct commands: {len(direct)}")
    print(f"Inherited commands: {len(inherited)}")
    print(f"Checkpoint count unchanged: {len(checkpoints) == expected_checkpoint_count}")


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


def _capture(
    store_dir: Path,
    *,
    latest_undo_uid: str,
    inherited_add_uid: str,
    memory_uid: str,
    checkpoint_count: int,
) -> None:
    child, recorder = _spawn("--revert", str(store_dir))
    try:
        child.expect("REVERT · SELECT A CONTEXT")
        child.expect("6 direct · 1 inherited · 0 descendant commands")
        _pump(child, recorder)
        _snapshot(recorder, "01-context-entry")

        child.send(RIGHT)
        child.expect("DIRECT COMMANDS · practice/2")
        child.expect("INHERITED HISTORY · source practice/1")
        _pump(child, recorder)
        _snapshot(recorder, "02-typed-direct-and-inherited-history")

        child.send(DOWN)
        child.expect("SELECTED COMMAND · UNDO")
        child.expect(latest_undo_uid)
        child.expect("Receipt")
        child.expect("Source command unit")
        _pump(child, recorder)
        _snapshot(recorder, "03-undo-identities-focused")

        # The shared held-arrow accelerator reaches the creation baseline on
        # this burst; reversing direction once lands on the preceding Add.
        child.send(DOWN * 6)
        _pump(child, recorder)
        child.send(UP)
        _pump(child, recorder)
        _snapshot(recorder, "04-inherited-add-identities-focused")
        focused_add = (
            OUT / "04-inherited-add-identities-focused.txt"
        ).read_text(encoding="utf-8")
        assert "SELECTED COMMAND · ADD" in focused_add
        assert inherited_add_uid in focused_add
        assert memory_uid in focused_add
        assert "inherited from practice/1" in focused_add

        child.send("\r")
        child.expect("REVERT · practice/2")
        child.expect(inherited_add_uid[:8])
        _pump(child, recorder)
        _snapshot(recorder, "05-exact-checkpoint-review")

        child.send("q")
        child.expect("Revert cancelled.")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "06-cancelled-without-mutation")
    finally:
        if child.isalive():
            child.close(force=True)

    verifier, verify_recorder = _spawn(
        "--verify",
        str(store_dir),
        memory_uid,
        str(checkpoint_count),
    )
    try:
        verifier.expect("Memory restored by final Undo: True")
        verifier.expect("Direct commands: 6")
        verifier.expect("Inherited commands: 1")
        verifier.expect("Checkpoint count unchanged: True")
        verifier.expect(pexpect.EOF)
        _snapshot(verify_recorder, "07-read-only-verification")
    finally:
        if verifier.isalive():
            verifier.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-history-uid-capture-") as tmp:
        store_dir = Path(tmp) / "store"
        latest_undo_uid, inherited_add_uid, memory_uid, checkpoint_count = (
            _prepare_store(store_dir)
        )
        _capture(
            store_dir,
            latest_undo_uid=latest_undo_uid,
            inherited_add_uid=inherited_add_uid,
            memory_uid=memory_uid,
            checkpoint_count=checkpoint_count,
        )
    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
    assert "38;" in raw
    assert "48;" in raw


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--revert":
        _run_revert(Path(sys.argv[2]))
    elif len(sys.argv) == 5 and sys.argv[1] == "--verify":
        _verify(Path(sys.argv[2]), sys.argv[3], int(sys.argv[4]))
    else:
        main()
