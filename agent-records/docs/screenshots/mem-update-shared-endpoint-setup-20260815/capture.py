"""Capture Update's shared Endpoint Setup migration in a 180x52 PTY."""

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

_BASE_PATH = ROOT / "agent-records/docs/screenshots/atomize-memory-selection-20260814/capture.py"
_SPEC = importlib.util.spec_from_file_location("update_setup_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _prepare_store(root: Path):
    import memcommit.ops as ops
    from memcommit.store import MemoryStore

    store = MemoryStore(root=root)
    source = ops.init("participant/construction-updates")
    source_focus = ops.add(
        source,
        "The Main Building south entrance reopens on August 23.",
    )
    ops.add(source, "The library help desk keeps its weekend schedule.")
    target = ops.init("campus-wiki")
    ops.add(target, "The Main Building south entrance is closed.")
    ops.add(target, "The library help desk opens on weekends.")
    target_child = ops.init("campus-wiki/buildings")
    ops.add(target_child, "The Main Building has accessible indoor routes.")
    target.add(target_child)
    for context in (source, target):
        store.create_context(context)
    store.set_current(source.name)
    return store, (source, target), source_focus


def _run_child(store_root: Path, *, cancel: bool) -> None:
    import memcommit.commands.update.setup as update_setup

    store, contexts, source_focus = _prepare_store(store_root)
    before = {
        context.name: store._context_file(context.name).read_bytes()
        for context in contexts
    }
    loaded: list[str] = []
    project = update_setup.context_memory_rows

    def observe(context):
        loaded.append(context.name)
        return project(context)

    update_setup.context_memory_rows = observe
    print("$ mem update · new Update endpoint setup", flush=True)
    print(
        f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}",
        flush=True,
    )
    receipt = update_setup.choose_update_setup(store)
    label = "CANCEL RECEIPT" if cancel else "UPDATE SETUP RECEIPT"
    print(f"\n{label} · {receipt!r}")
    if receipt is not None:
        print(
            "  A SOURCE · "
            f"DESCENDANTS={receipt.source_descendants} · "
            f"MEMORY={receipt.source_memory_uid}"
        )
        print(
            "  B TARGET · "
            f"DESCENDANTS={receipt.target_descendants} · "
            f"MEMORY={receipt.target_memory_uid}"
        )
        print(
            "  EXPECTED SOURCE MEMORY · "
            f"{source_focus.uid} · "
            f"MATCH={receipt.source_memory_uid == source_focus.uid}"
        )
    print(f"  DIRECT MEMORY PROJECTIONS · {loaded}")
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
    print(f"  STAGED UPDATE · {store.load_staged_update()!r}")
    print(f"  IMPACT CACHE · {store.load_impact_plan()!r}")
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


def _capture_selected_scope(store_root: Path) -> None:
    child, recorder = _spawn("selected", store_root)
    try:
        child.expect("NEW UPDATE")
        _BASE._settle(child)
        _snapshot(recorder, "01-entry-source-context")

        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "02-source-exact-range")

        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "03-source-whole-context")

        child.send("\x1b[B\r")
        _BASE._settle(child)
        _snapshot(recorder, "04-source-memory-selected")

        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "05-target-context")

        child.send("\t\x1b[C")
        _BASE._settle(child)
        _snapshot(recorder, "06-target-descendants-selected")

        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "07-target-memory-disabled")

        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "08-reviewed-independent-scope")

        child.send("\r")
        child.expect("UPDATE SETUP RECEIPT")
        _BASE._settle(child)
        _snapshot(recorder, "09-read-only-typed-receipt")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_cancel(store_root: Path) -> None:
    child, recorder = _spawn("cancel", store_root)
    try:
        child.expect("NEW UPDATE")
        _BASE._settle(child)
        child.send("\x1b")
        child.expect("CANCEL RECEIPT")
        _BASE._settle(child)
        _snapshot(recorder, "10-cancelled-before-update")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="update-shared-setup-") as directory:
        root = Path(directory)
        _capture_selected_scope(root / "selected" / ".mem")
        _capture_cancel(root / "cancel" / ".mem")
    for path in OUT.glob("*.txt"):
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text(
            "\n".join(line.rstrip() for line in lines) + "\n",
            encoding="utf-8",
        )
    raw = (OUT / "01-entry-source-context.typescript").read_text(
        encoding="utf-8"
    )
    if "\x1b[" not in raw or "38;" not in raw:
        raise RuntimeError("Capture did not retain the expected ANSI color styles.")


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "--child":
        _run_child(Path(sys.argv[3]), cancel=sys.argv[2] == "cancel")
    else:
        main()
