"""Capture typed Revert receipt effect colors in an isolated Store."""

from __future__ import annotations

import io
import os
from pathlib import Path
import shlex
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SUPPORT = ROOT / "agent-records/screenshots/distill-elaborate-shared-app-20260815"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(SUPPORT))

from capture_support import StreamRecorder, snapshot  # noqa: E402


COLUMNS = 180
ROWS = 52
CONTEXT = "receipt/colors"


def _configure_store(store_dir: Path) -> None:
    import memcommit.store as store_module

    store_module.STORE_DIR = store_dir


def _prepare_store(store_dir: Path) -> tuple[str, tuple[str, str, str, str]]:
    _configure_store(store_dir)
    import memcommit.ops as ops
    from memcommit.context import AutoCheckpoint, Memory
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_dir)
    source = ops.init("receipt/source")
    source_memory = ops.add(source, "embedded source Memory")
    store.save(
        source,
        AutoCheckpoint(
            command="init",
            args={"name": source.name},
            description=f"Initialized context '{source.name}'",
        ),
    )
    context = ops.init(CONTEXT)
    store.save(
        context,
        AutoCheckpoint(
            command="init",
            args={"name": CONTEXT},
            description=f"Initialized context '{CONTEXT}'",
        ),
    )
    restored, edited = ops.add_many(
        context,
        ("restored by revert", "target spelling"),
    )
    embedded = ops.embed_memory(source_memory, source, context)
    store.save(
        context,
        AutoCheckpoint(
            command="add",
            args={
                "memory_uids": [restored.uid, edited.uid],
                "memory_ref_uid": embedded.uid,
            },
            description="Added the target receipt fixture Memories and embed",
        ),
    )
    target_uid = store.list_checkpoints(CONTEXT)[0]["uid"]

    context.remove(restored.uid)
    context.remove(embedded.uid)
    context.replace(Memory(edited.uid, "changed after target"))
    later = ops.add(context, "removed by revert")
    store.save(
        context,
        AutoCheckpoint(
            command="update",
            args={"context": CONTEXT},
            description="Changed all three typed receipt effects after target",
        ),
    )
    store.set_current(CONTEXT)
    return target_uid, (restored.uid, edited.uid, later.uid, embedded.uid)


def _print_state(store_dir: Path, *, label: str) -> None:
    _configure_store(store_dir)
    from memcommit.context import Memory
    from memcommit.source_projection.model import SourceForm
    from memcommit.source_projection.presentation import source_object_label
    from memcommit.store import MemoryStore

    store = MemoryStore(create=False)
    context = store.load_direct(CONTEXT)
    print(label)
    print("LIVE COLOR PTY", *reversed(os.get_terminal_size()))
    print(f"Current Context: {store.current_context_name()}")
    memory_label = source_object_label(SourceForm.MEMORY)
    for item in context.iter_items():
        if isinstance(item, Memory):
            print(f"  [{memory_label} {item.uid[:8]}] {item.content!r}")


def _run_revert(store_dir: Path, target_uid: str) -> None:
    _configure_store(store_dir)
    from memcommit.commands.revert.command import cmd

    print("LIVE COLOR PTY", *reversed(os.get_terminal_size()))
    print(f"COMMAND · mem revert {target_uid[:8]} --context {CONTEXT}")
    cmd(target_uid[:8], keep=True, context_name=CONTEXT)


def _verify(store_dir: Path, expected_uids: tuple[str, str, str, str]) -> None:
    _configure_store(store_dir)
    from memcommit.context import Memory, MemoryRef
    from memcommit.store import MemoryStore

    restored_uid, edited_uid, removed_uid, embedded_uid = expected_uids
    store = MemoryStore(create=False)
    context = store.load_direct(CONTEXT)
    contents = {
        item.uid: item.content
        for item in context.iter_items()
        if isinstance(item, Memory)
    }
    restored_embeds = {
        item.uid for item in context.iter_items() if isinstance(item, MemoryRef)
    }
    print("READ-ONLY REVERT VERIFICATION")
    print("LIVE COLOR PTY", *reversed(os.get_terminal_size()))
    print(f"Current Context: {store.current_context_name()}")
    print(f"Added effect restored: {contents.get(restored_uid)!r}")
    print(f"Memory ref effect restored: {embedded_uid in restored_embeds}")
    print(f"Edit effect restored: {contents.get(edited_uid)!r}")
    print(f"Remove effect absent: {removed_uid not in contents}")
    print(
        "COMPLETE TARGET RESULT VERIFIED: "
        f"{contents == {restored_uid: 'restored by revert', edited_uid: 'target spelling'} and embedded_uid in restored_embeds}"
    )


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
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
    return child, recorder


def _complete(*args: str) -> StreamRecorder:
    child, recorder = _spawn(*args)
    try:
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)
    return recorder


def _snapshot(recorder: io.StringIO, stem: str) -> None:
    snapshot(recorder, stem, out=OUT, columns=COLUMNS, rows=ROWS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-revert-receipt-") as temp:
        store_dir = Path(temp) / "store"
        target_uid, expected_uids = _prepare_store(store_dir)

        before = _complete("--before", str(store_dir))
        _snapshot(before, "01-before-state")

        receipt = _complete("--revert", str(store_dir), target_uid)
        _snapshot(receipt, "02-success-receipt")

        verification = _complete(
            "--verify",
            str(store_dir),
            *expected_uids,
        )
        _snapshot(verification, "03-read-only-verification")

    raw = receipt.getvalue()
    assert "52 180" in raw
    assert "\x1b[38;2;138;173;244m\x1b[1m+\x1b[0m" in raw
    assert "\x1b[38;2;166;218;149m\x1b[1m~\x1b[0m" in raw
    assert "\x1b[38;2;237;135;150m\x1b[1m-\x1b[0m" in raw
    summary = (
        "Affected content: 1 Memory added, 1 Memory ref added, "
        "1 Memory edited, 1 Memory removed"
    )
    assert summary in raw
    assert "\x1b[38;2;202;211;245m\"restored by revert\"\x1b[0m" in raw
    assert "\x1b[38;2;202;211;245m\"embedded source Memory\"\x1b[0m" in raw
    assert "\x1b[38;2;238;212;159membedded\x1b[0m" in raw
    assert "\x1b[38;2;237;135;150m\"changed after target\"\x1b[0m" in raw
    assert "\x1b[38;2;166;218;149m\"target spelling\"\x1b[0m" in raw
    assert "\x1b[38;2;138;173;244m\x1b[1mmem add\x1b[0m" in raw
    assert (
        f"\x1b[38;2;201;173;147m\x1b[1m[{target_uid[:8]}]\x1b[0m" in raw
    )
    assert "\x1b[38;2;245;169;127m\x1b[1mmem undo\x1b[0m" in raw
    assert "\x1b[38;2;245;169;127m\x1b[1mmem revert\x1b[0m" in raw
    receipt_text = (OUT / "02-success-receipt.txt").read_text(encoding="utf-8")
    assert summary in receipt_text
    assert "[memory " in receipt_text
    assert "] \"restored by revert\"" in receipt_text
    assert "[embedded " in receipt_text
    assert 'receipt/source:' in receipt_text
    assert '"embedded source Memory"  READ ONLY' in receipt_text
    assert "to Context" not in receipt_text
    assert "] Memory:" not in receipt_text
    assert "] Memory ref:" not in receipt_text
    verification_text = (OUT / "03-read-only-verification.txt").read_text(
        encoding="utf-8"
    )
    assert "COMPLETE TARGET RESULT VERIFIED: True" in verification_text


if __name__ == "__main__":
    arguments = sys.argv[1:]
    if arguments[:1] == ["--before"]:
        _print_state(Path(arguments[1]), label="READ-ONLY STATE BEFORE REVERT")
    elif arguments[:1] == ["--revert"]:
        _run_revert(Path(arguments[1]), arguments[2])
    elif arguments[:1] == ["--verify"]:
        _verify(Path(arguments[1]), tuple(arguments[2:6]))
    else:
        main()
