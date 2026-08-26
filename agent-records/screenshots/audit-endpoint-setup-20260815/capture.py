"""Capture Audit's rebuilt endpoint setup in a real 180x52 color PTY."""

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

_BASE_PATH = ROOT / "agent-records/screenshots/atomize-memory-selection-20260814/capture.py"
_SPEC = importlib.util.spec_from_file_location("audit_endpoint_capture_base", _BASE_PATH)
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
    current = ops.init("audit/current")
    ops.add(current, "Current evidence remains unchanged.")
    peer = ops.init("audit/peer")
    ops.add(peer, "Peer evidence selected for Audit.")
    store.create_context(current)
    store.create_context(peer)
    store.set_current(current.name)
    return store, current, peer


def _run_child(store_root: Path, *, cancel: bool) -> None:
    from memcommit.interfaces.tui.operations.audit import choose_audit_setup

    store, current, peer = _prepare_store(store_root)
    before = {
        name: store._context_file(name).read_bytes()
        for name in (current.name, peer.name)
    }
    print("$ mem audit -> shared endpoint setup", flush=True)
    print(
        f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}",
        flush=True,
    )
    selected = choose_audit_setup(
        (current.name, peer.name),
        current=current.name,
    )
    label = "CANCEL RECEIPT" if cancel else "SETUP RECEIPT"
    print(f"\n{label} · {selected!r}")
    print("READ-ONLY SETUP VERIFICATION")
    print(
        "  CONTEXT BYTES UNCHANGED · "
        f"{all(store._context_file(name).read_bytes() == value for name, value in before.items())}"
    )
    print(f"  CURRENT CONTEXT · {store.current_context_name()}")
    print(f"  CONTEXT CHECKPOINTS · {sum(len(store.list_checkpoints(name)) for name in before)}")
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


def _capture_success(store_root: Path) -> None:
    child, recorder = _spawn("success", store_root)
    try:
        child.expect("MEM AUDIT")
        _BASE._settle(child)
        _snapshot(recorder, "01-entry-current-source")

        child.send("\x1b[B\r")
        _BASE._settle(child)
        _snapshot(recorder, "02-peer-source-selected")

        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "03-explicit-continue-action")

        child.send("\r")
        child.expect("SETUP RECEIPT")
        _BASE._settle(child)
        _snapshot(recorder, "04-read-only-setup-receipt")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_cancel(store_root: Path) -> None:
    child, recorder = _spawn("cancel", store_root)
    try:
        child.expect("MEM AUDIT")
        _BASE._settle(child)
        child.send("\x1b")
        child.expect("CANCEL RECEIPT")
        _BASE._settle(child)
        _snapshot(recorder, "05-cancelled-without-source")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="audit-endpoint-capture-") as directory:
        root = Path(directory)
        _capture_success(root / "success" / ".mem")
        _capture_cancel(root / "cancel" / ".mem")
    # The renderer preserves the complete fixed-width canvas for the PNG but
    # the companion text is review evidence, not a spacing fixture.
    for path in OUT.glob("*.txt"):
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text(
            "\n".join(line.rstrip() for line in lines) + "\n",
            encoding="utf-8",
        )
    raw = (OUT / "01-entry-current-source.typescript").read_text(encoding="utf-8")
    if "\x1b[" not in raw or "38;" not in raw:
        raise RuntimeError("Capture did not retain the expected ANSI color styles.")


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "--child":
        _run_child(Path(sys.argv[3]), cancel=sys.argv[2] == "cancel")
    else:
        main()
