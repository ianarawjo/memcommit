"""Capture exact Memory focus and descendant clearing in a 180x52 PTY."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52

_BASE_PATH = (
    ROOT
    / "agent-records/docs/screenshots/atomize-memory-selection-20260814/capture.py"
)
_SPEC = importlib.util.spec_from_file_location("endpoint_memory_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _prepare_store(root: Path):
    import memcommit.application.capabilities.ops as ops
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=root)
    source = ops.init("source")
    first = ops.add(source, "First frozen Source Memory.")
    second = ops.add(source, "Second frozen Source Memory.")
    target = ops.init("target")
    third = ops.add(target, "Frozen Target Memory.")
    for context in (source, target):
        store.create_context(context)
    store.set_current("target")
    return store, (source, target), {
        "source": (first, second),
        "target": (third,),
    }


def _run_child(store_root: Path, *, cancel: bool) -> None:
    from memcommit.adapters.console.terminal.components.endpoint_setup import (
        EndpointSetupMemory,
        EndpointSetupMode,
        EndpointSetupRole,
        EndpointSetupSpec,
        run_endpoint_setup,
    )

    store, contexts, memories = _prepare_store(store_root)
    before = {
        context.name: store._context_file(context.name).read_bytes()
        for context in contexts
    }
    loaded: list[tuple[str, str]] = []

    def load_memories(
        role_uid: str,
        context_name: str,
    ) -> tuple[EndpointSetupMemory, ...]:
        loaded.append((role_uid, context_name))
        return tuple(
            EndpointSetupMemory(context_name, memory.uid, memory.content)
            for memory in memories[context_name]
        )

    spec = EndpointSetupSpec(
        title="ENDPOINT SETUP · FOCUSED MEMORY",
        subtitle="ONE EXACT MEMORY CANNOT SURVIVE DESCENDANT REACH",
        modes=(EndpointSetupMode("DIRECTIONAL", "DIRECTIONAL · A → RESULT"),),
        initial_mode_uid="DIRECTIONAL",
        roles=(
            EndpointSetupRole(
                "A",
                "A · SOURCE",
                ("source", "target"),
                frozenset({"source", "target"}),
                "source",
                current_context="target",
                height=3,
                allow_descendants=True,
                allow_memory_focus=True,
                memory_height=9,
            ),
        ),
        action_label="CONTINUE WITH SELECTED A RANGE",
    )
    print("$ endpoint setup component harness · focused Memory", flush=True)
    print(
        f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}",
        flush=True,
    )
    draft = run_endpoint_setup(spec, memory_loader=load_memories)
    label = "CANCEL RECEIPT" if cancel else "TYPED SETUP RECEIPT"
    print(f"\n{label} · {draft!r}")
    if draft is not None:
        value = draft.value("A")
        print(
            "  A · "
            f"DESCENDANTS={value.include_descendants} · "
            f"MEMORY={value.memory_uid}"
        )
    print(f"  MEMORY PROJECTION LOADS · {loaded}")
    print("READ-ONLY SETUP VERIFICATION")
    print(
        "  CONTEXT BYTES UNCHANGED · "
        f"{all(store._context_file(name).read_bytes() == value for name, value in before.items())}"
    )
    print(f"  CURRENT CONTEXT · {store.current_context_name()}")
    print(
        "  CONTEXT CHECKPOINTS · "
        f"{sum(len(store.list_checkpoints(name)) for name in before)}"
    )
    print("  PROVIDER CALLS · 0", flush=True)


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PROMPT_TOOLKIT_COLOR_DEPTH": "DEPTH_24_BIT",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _spawn(kind: str, store_root: Path) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind, str(store_root)],
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


def _capture_exact(store_root: Path) -> None:
    child, recorder = _spawn("exact", store_root)
    try:
        child.expect("ENDPOINT SETUP")
        _BASE._settle(child)
        _snapshot(recorder, "01-entry-a-context")

        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "02-exact-range-focused")

        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "03-whole-context-memory-focus")

        child.send("\x1b[B")
        _BASE._settle(child)
        _snapshot(recorder, "04-first-memory-hovered")

        child.send("\r")
        _BASE._settle(child)
        _snapshot(recorder, "05-exact-memory-selected")

        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "06-exact-memory-review")

        child.send("\r")
        child.expect("TYPED SETUP RECEIPT")
        _BASE._settle(child)
        _snapshot(recorder, "07-exact-memory-receipt")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_clearing(store_root: Path) -> None:
    child, recorder = _spawn("clearing", store_root)
    try:
        child.expect("ENDPOINT SETUP")
        _BASE._settle(child)
        child.send("\t\t\x1b[B\r")
        _BASE._settle(child)
        _snapshot(recorder, "08-clearing-branch-memory-selected")

        child.send("\x1b[Z")
        _BASE._settle(child)
        _snapshot(recorder, "09-range-before-broadening")

        child.send("\x1b[C")
        _BASE._settle(child)
        _snapshot(recorder, "10-descendants-clear-memory")

        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "11-memory-focus-disabled-for-subtree")

        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "12-descendant-review-without-memory")

        child.send("\r")
        child.expect("TYPED SETUP RECEIPT")
        _BASE._settle(child)
        _snapshot(recorder, "13-descendant-receipt-without-memory")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_cancel(store_root: Path) -> None:
    child, recorder = _spawn("cancel", store_root)
    try:
        child.expect("ENDPOINT SETUP")
        _BASE._settle(child)
        child.send("\x1b")
        child.expect("CANCEL RECEIPT")
        _BASE._settle(child)
        _snapshot(recorder, "14-cancelled-without-memory-draft")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="endpoint-memory-capture-") as directory:
        root = Path(directory)
        _capture_exact(root / "exact" / ".mem")
        _capture_clearing(root / "clearing" / ".mem")
        _capture_cancel(root / "cancel" / ".mem")
    for path in OUT.glob("*.txt"):
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text(
            "\n".join(line.rstrip() for line in lines) + "\n",
            encoding="utf-8",
        )
    raw = (OUT / "01-entry-a-context.typescript").read_text(encoding="utf-8")
    if "\x1b[" not in raw or "38;" not in raw:
        raise RuntimeError("Capture did not retain the expected ANSI color styles.")


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "--child":
        _run_child(Path(sys.argv[3]), cancel=sys.argv[2] == "cancel")
    else:
        main()
