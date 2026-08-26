"""Capture Forget application boundaries in a real 180x52 color PTY."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shlex
import sys
import tempfile
import time
from types import SimpleNamespace

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLS = 180
ROWS = 52


def _load_capture_helpers():
    path = (
        ROOT
        / "agent-records"
        / "screenshots"
        / "study-full-replay-20260811"
        / "capture_init_study.py"
    )
    spec = importlib.util.spec_from_file_location("memcommit_capture_helpers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the shared PTY capture helpers.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUT = OUT
    module.COLS = COLS
    module.ROWS = ROWS
    return module


HELPERS = _load_capture_helpers()


def _capture_environment() -> dict[str, str]:
    environment = HELPERS._environment()
    environment["PYTHONPATH"] = str(ROOT / "src")
    return environment


def _spawn_child(mode: str, store_root: Path):
    command = (
        f"stty rows {ROWS} cols {COLS}; stty size; "
        f"exec {shlex.join([sys.executable, str(__file__), '--child', mode, str(store_root)])}"
    )
    recorder = HELPERS._Recorder()
    child = pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
        cwd=str(ROOT),
        env=_capture_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=30,
        dimensions=(ROWS, COLS),
    )
    child.logfile_read = recorder
    child._mem_cpr_responses = 0
    return child, recorder


def _wait_for(child, recorder, *needles: str, seconds: float = 12.0) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        HELPERS._pump(child, recorder, seconds=0.12)
        visible = HELPERS._visible_text(recorder)
        if all(needle in visible for needle in needles):
            return
        if not child.isalive():
            break
    raise RuntimeError(
        "PTY did not reach expected state: "
        + ", ".join(repr(needle) for needle in needles)
        + "\n"
        + HELPERS._visible_text(recorder)
    )


def _finish(child, recorder) -> None:
    HELPERS._pump(child, recorder, seconds=15, require_eof=True)


class _ForgetProvider:
    def __init__(self, action: str, *, on_complete=None):
        self.action = action
        self.on_complete = on_complete

    def complete(self, prompt, *, operation, output_schema=None):
        del output_schema
        if operation != "forget":
            raise AssertionError(operation)
        messages = json.loads(prompt.split("FORGET CHAT MESSAGES:\n", 1)[1])
        payload = json.loads(
            messages[1]["content"].split("FORGET PAYLOAD:\n", 1)[1]
        )
        source = payload["source"]["memories"][0]
        if self.on_complete is not None:
            self.on_complete()
        time.sleep(3.0)
        proposed_content = source["content"] if self.action == "KEEP" else ""
        return json.dumps(
            {
                "overview": "Reviewed the complete frozen Source.",
                "candidates": [
                    {
                        "source_memory_id": source["item_id"],
                        "decision": self.action,
                        "proposed_content": proposed_content,
                        "rationale": "Compared the complete Source with the instruction.",
                        "criterion_item_ids": ["k1"],
                    }
                ],
            }
        )


def _create_source(store, name: str):
    from memcommit.context import Context, Memory

    context = Context(uid="11111111-1111-4111-8111-111111111111", name=name)
    context.add(
        Memory(
            uid="22222222-2222-4222-8222-222222222222",
            content="The service desk used to be beside the west entrance.",
        )
    )
    store.save(context)
    store.set_current(name)
    return context


def _run_forget_command(store, provider, *, granted: bool = False) -> None:
    from memcommit.commands import forget

    forget.MemoryStore = lambda: store
    forget.connect_codex_chatgpt_provider = lambda: provider
    if granted:
        access = SimpleNamespace(
            store=store,
            context_name=store.current_context_name(),
            display_name=store.current_context_name(),
            is_granted=True,
            view=None,
        )
        forget.resolve_context_access = lambda *_args, **_kwargs: access
    forget.cmd("Forget the old service desk location.")


def _child_local(store_root: Path) -> None:
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root)
    _create_source(store, "forget/local")
    _run_forget_command(store, _ForgetProvider("DELETE"))


def _child_verify(store_root: Path) -> None:
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    context = store.load_direct("forget/local")
    checkpoints = store.list_checkpoints(context.name)
    print("\x1b[38;2;138;173;244mREAD-ONLY FORGET VERIFICATION\x1b[0m")
    print(f"DIRECT MEMORIES · {len(context.memories)}")
    print(f"FORGET CHECKPOINTS · {sum(c.get('command') == 'forget' for c in checkpoints)}")


def _child_restore(store_root: Path, action: str) -> None:
    from memcommit.commands.shared.restoration_present import render_command_restore_receipt
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    result = store.restore_recent_context_command(action)
    render_command_restore_receipt(result)
    context = store.load_direct("forget/local")
    print(f"{action.upper()} VERIFICATION · DIRECT MEMORIES {len(context.memories)}")


def _child_granted_review(store_root: Path) -> None:
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root)
    _create_source(store, "forget/granted")
    _run_forget_command(store, _ForgetProvider("DELETE"), granted=True)
    context = store.load_direct("forget/granted")
    print(f"AUTHORITY SOURCE VERIFICATION · DIRECT MEMORIES {len(context.memories)}")


def _child_granted_noop(store_root: Path) -> None:
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root)
    _create_source(store, "forget/noop")
    before = len(store.list_checkpoints("forget/noop"))
    _run_forget_command(store, _ForgetProvider("KEEP"), granted=True)
    after = len(store.list_checkpoints("forget/noop"))
    print(f"MUTATION BOUNDARY · NONE · CHECKPOINT DELTA {after - before}")


def _child_stale(store_root: Path) -> None:
    import typer

    from memcommit.context import AutoCheckpoint, Memory
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root)
    source = _create_source(store, "forget/stale")

    def publish_concurrent_change() -> None:
        current = store.load_direct(source.name)
        current.add(
            Memory(
                uid="ffffffff-ffff-4fff-8fff-ffffffffffff",
                content="A concurrent note must survive.",
            )
        )
        store.save(
            current,
            AutoCheckpoint(
                command="add",
                args={},
                description="Concurrent capture change.",
            ),
        )

    try:
        _run_forget_command(
            store,
            _ForgetProvider("DELETE", on_complete=publish_concurrent_change),
        )
    except typer.Exit as error:
        if error.exit_code != 1:
            raise
    else:
        raise RuntimeError("Stale Forget unexpectedly succeeded.")
    current = store.load_direct(source.name)
    checkpoints = store.list_checkpoints(source.name)
    print("STALE REVIEW · REJECTED · CONTEXT PRESERVED")
    print(f"DIRECT MEMORIES · {len(current.memories)}")
    print(f"FORGET CHECKPOINTS · {sum(c.get('command') == 'forget' for c in checkpoints)}")


def _run_child(mode: str, store_root: Path) -> None:
    {
        "local": _child_local,
        "verify": _child_verify,
        "undo": lambda root: _child_restore(root, "undo"),
        "redo": lambda root: _child_restore(root, "redo"),
        "granted-review": _child_granted_review,
        "granted-noop": _child_granted_noop,
        "stale": _child_stale,
    }[mode](store_root)


def _capture_finished(mode: str, store_root: Path, stem: str, expected: str) -> None:
    child, recorder = _spawn_child(mode, store_root)
    _finish(child, recorder)
    if expected not in recorder.getvalue():
        raise RuntimeError(f"Verification capture {stem} missed {expected!r}.")
    HELPERS._snapshot(recorder, stem)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-forget-application-") as temporary:
        store_root = Path(temporary)

        child, recorder = _spawn_child("local", store_root)
        _wait_for(child, recorder, "FORGET REPORT · BUILDING", "CONTENT PENDING")
        HELPERS._snapshot(recorder, "01-local-result-pending")
        child.send("i")
        _wait_for(child, recorder, "FORGET CONFIRMED INPUTS", "RESULT PENDING")
        HELPERS._snapshot(recorder, "02-local-confirmed-input")
        _finish(child, recorder)
        if "recovery mem undo" not in recorder.getvalue():
            raise RuntimeError("Local Forget did not auto-apply with recovery receipt.")
        HELPERS._snapshot(recorder, "03-local-auto-application-receipt")

        _capture_finished(
            "verify",
            store_root,
            "04-read-only-applied-verification",
            "FORGET CHECKPOINTS · 1",
        )
        _capture_finished(
            "undo",
            store_root,
            "05-operation-unit-undo",
            "UNDO VERIFICATION · DIRECT MEMORIES 1",
        )
        _capture_finished(
            "redo",
            store_root,
            "06-operation-unit-redo",
            "REDO VERIFICATION · DIRECT MEMORIES 0",
        )

        granted_root = store_root / "granted"
        child, recorder = _spawn_child("granted-review", granted_root)
        _wait_for(child, recorder, "REVIEW AND APPLY", "Apply Forget")
        HELPERS._snapshot(recorder, "07-granted-change-final-review")
        child.send("\x1b")
        _wait_for(child, recorder, "WHAT MEM UNDERSTOOD", "IMPACT · PROPOSED")
        HELPERS._snapshot(recorder, "08-granted-change-complete-report")
        child.send("q")
        _finish(child, recorder)
        if "AUTHORITY SOURCE VERIFICATION · DIRECT MEMORIES 1" not in recorder.getvalue():
            raise RuntimeError("Cancelling granted Forget changed its Source.")
        HELPERS._snapshot(recorder, "09-granted-change-cancelled")

        _capture_finished(
            "granted-noop",
            store_root / "granted-noop",
            "10-granted-all-keep-noop",
            "MUTATION BOUNDARY · NONE · CHECKPOINT DELTA 0",
        )
        _capture_finished(
            "stale",
            store_root / "stale",
            "11-stale-review-rejected",
            "FORGET CHECKPOINTS · 0",
        )

        raw = (OUT / "07-granted-change-final-review.typescript").read_text(
            encoding="utf-8"
        )
        if "\x1b[" not in raw or "38;2" not in raw:
            raise RuntimeError("Capture did not preserve ANSI true-color output.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        _run_child(sys.argv[2], Path(sys.argv[3]))
    elif len(sys.argv) == 1:
        main()
    else:
        raise SystemExit("usage: capture.py [--child MODE STORE]")
