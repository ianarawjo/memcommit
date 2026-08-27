"""Capture Revert's keep-all default and editable exact-command boundary."""

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
CONTEXT = "practice/greetings"
DOWN = "\x1b[B"
RIGHT = "\x1b[C"
SHIFT_TAB = "\x1b[Z"
CTRL_U = "\x15"
CPR_REQUEST = "\x1b[6n"
CPR_RESPONSE = "\x1b[1;1R"


def _configure_store(store_dir: Path) -> None:
    import memcommit.persistence.store as store_module

    store_module.STORE_DIR = store_dir


def _prepare_store(store_dir: Path) -> tuple[str, ...]:
    _configure_store(store_dir)
    import memcommit.application.ops as ops
    from memcommit.context import AutoCheckpoint
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=store_dir)
    context = ops.init(CONTEXT)
    store.save(
        context,
        AutoCheckpoint(
            command="init",
            args={"name": CONTEXT},
            description=f"Initialized context '{CONTEXT}'",
        ),
    )
    ops.add(context, "bonjour")
    store.save(
        context,
        AutoCheckpoint(
            command="add",
            args={"content": "bonjour"},
            description='Added: "bonjour"',
        ),
    )
    ops.add(context, "hi")
    store.save(
        context,
        AutoCheckpoint(
            command="add",
            args={"content": "hi"},
            description='Added newer greeting: "hi"',
        ),
    )
    store.set_current(CONTEXT)
    return tuple(checkpoint["uid"] for checkpoint in store.list_checkpoints(CONTEXT))


def _run_revert(store_dir: Path) -> None:
    _configure_store(store_dir)
    from memcommit.adapters.console.commands.revert.command import cmd
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(create=False)
    print("LIVE COLOR PTY", *reversed(os.get_terminal_size()))
    print("COMMAND · mem revert")
    print(f"CURRENT BEFORE · {store.current_context_name()}")
    cmd()


def _verify(
    store_dir: Path,
    target_uid: str,
    original_uids: tuple[str, ...],
) -> None:
    _configure_store(store_dir)
    from memcommit.context import Memory
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(create=False)
    context = store.load_direct(CONTEXT)
    checkpoints = store.list_checkpoints(CONTEXT)
    retained = {checkpoint["uid"] for checkpoint in checkpoints}
    contents = [
        item.content for item in context.iter_items() if isinstance(item, Memory)
    ]
    print("READ-ONLY REVERT VERIFICATION")
    print("LIVE COLOR PTY", *reversed(os.get_terminal_size()))
    print(f"Current Context: {store.current_context_name()}")
    print(f"Final edited target retained: {target_uid in retained}")
    print(f"KEEP ALL original checkpoints retained: {set(original_uids) <= retained}")
    print(f"Result Memories: {contents}")
    print(
        "EMPTY INIT TARGET VERIFIED: "
        f"{contents == []} · ACTIVE HISTORY PRESERVED: "
        f"{set(original_uids) <= retained}"
    )


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
    seconds: float = 0.6,
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


def _capture(store_dir: Path, original_uids: tuple[str, ...]) -> str:
    edited_target_uid = original_uids[-1]
    edited_target_prefix = edited_target_uid[:8]
    assert sum(uid.startswith(edited_target_prefix) for uid in original_uids) == 1
    child, recorder = _spawn("--revert", str(store_dir))
    try:
        child.expect(f"REVERT · {CONTEXT}")
        child.expect("FOCUS ITEMS")
        _pump(child, recorder)
        _snapshot(recorder, "01-entry-keep-all-default")

        child.send(DOWN)
        _pump(child, recorder)
        _snapshot(recorder, "02-target-preview")

        child.send("\r")
        _pump(child, recorder)
        _snapshot(recorder, "03-items-enter-direct-command")

        replacement = (
            f"{edited_target_prefix} --context {CONTEXT} --discard-newer"
        )
        child.send(CTRL_U + replacement)
        _pump(child, recorder)
        _snapshot(recorder, "04-command-edits-target-and-policy")

        child.send(SHIFT_TAB + RIGHT)
        _pump(child, recorder)
        _snapshot(recorder, "05-history-rewrites-command-keep-all")

        final_command = f"{edited_target_prefix} --context {CONTEXT} --keep"
        child.send("\r" + CTRL_U + final_command)
        _pump(child, recorder)
        _snapshot(recorder, "06-final-reviewed-command")

        child.send("\r")
        child.expect("Reverted Context")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "07-success-receipt")
    finally:
        if child.isalive():
            child.close(force=True)

    verify, verify_recorder = _spawn(
        "--verify",
        str(store_dir),
        edited_target_uid,
        *original_uids,
    )
    try:
        verify.expect("EMPTY INIT TARGET VERIFIED: True")
        verify.expect(pexpect.EOF)
        _snapshot(verify_recorder, "08-read-only-verification")
    finally:
        if verify.isalive():
            verify.close(force=True)
    return recorder.getvalue() + verify_recorder.getvalue()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-revert-editable-") as temp:
        store_dir = Path(temp) / "store"
        original_uids = _prepare_store(store_dir)
        raw = _capture(store_dir, original_uids)

    assert "52 180" in raw
    assert "38;" in raw and "48;" in raw
    assert "\x1b[?1049h" in raw and "\x1b[?1049l" in raw
    expected_plain = {
        "01-entry-keep-all-default.txt": "✓ KEEP ALL",
        "02-target-preview.txt": 'Added: "bonjour"',
        "03-items-enter-direct-command.txt": "FOCUS PROPOSED COMMAND",
        "04-command-edits-target-and-policy.txt": "✓ DISCARD NEWER",
        "05-history-rewrites-command-keep-all.txt": "--keep",
        "06-final-reviewed-command.txt": "FOCUS PROPOSED COMMAND",
        "07-success-receipt.txt": "Exact recovery checkpoint: mem revert",
        "08-read-only-verification.txt": "ACTIVE HISTORY PRESERVED: True",
    }
    for filename, expected in expected_plain.items():
        assert expected in (OUT / filename).read_text(encoding="utf-8")
    assert "--discard-newer" in (
        OUT / "04-command-edits-target-and-policy.txt"
    ).read_text(encoding="utf-8")
    edited_command = (
        OUT / "04-command-edits-target-and-policy.txt"
    ).read_text(encoding="utf-8")
    edited_target_prefix = original_uids[-1][:8]
    assert (
        f"mem revert {edited_target_prefix} --context "
        f"{CONTEXT} --discard-newer"
    ) in edited_command
    assert "MEANING" not in edited_command
    assert "MEANING" not in (
        OUT / "05-history-rewrites-command-keep-all.txt"
    ).read_text(encoding="utf-8")
    assert (
        f"mem revert {edited_target_prefix} --context {CONTEXT} --keep"
        in (OUT / "06-final-reviewed-command.txt").read_text(encoding="utf-8")
    )
    assert "--discard-newer" in (OUT / "07-success-receipt.txt").read_text(
        encoding="utf-8"
    )


if __name__ == "__main__":
    arguments = sys.argv[1:]
    if arguments[:1] == ["--revert"]:
        _run_revert(Path(arguments[1]))
    elif arguments[:1] == ["--verify"]:
        _verify(
            Path(arguments[1]),
            arguments[2],
            tuple(arguments[3:]),
        )
    else:
        main()
