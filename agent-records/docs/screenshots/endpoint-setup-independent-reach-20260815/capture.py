"""Capture independent A/B descendant reach in a 180x52 color PTY."""

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
_SPEC = importlib.util.spec_from_file_location("endpoint_reach_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _prepare_store(root: Path):
    import memcommit.application.ops as ops
    from memcommit.store import MemoryStore

    store = MemoryStore(root=root)
    contexts = tuple(
        ops.init(name)
        for name in (
            "source",
            "source/child",
            "target",
            "target/child",
        )
    )
    for context in contexts:
        ops.add(context, f"Evidence owned by {context.name}.")
        store.create_context(context)
    store.set_current("target")
    return store, contexts


def _run_child(store_root: Path, *, cancel: bool) -> None:
    from memcommit.adapters.interfaces.tui.components.endpoint_setup import (
        EndpointSetupMode,
        EndpointSetupRole,
        EndpointSetupSpec,
        run_endpoint_setup,
    )

    store, contexts = _prepare_store(store_root)
    before = {
        context.name: store._context_file(context.name).read_bytes()
        for context in contexts
    }
    spec = EndpointSetupSpec(
        title="ENDPOINT SETUP · INDEPENDENT RANGE",
        subtitle="A AND B FREEZE EXACT ROOTS AND DESCENDANT REACH SEPARATELY",
        modes=(EndpointSetupMode("DIRECTIONAL", "DIRECTIONAL · A → B"),),
        initial_mode_uid="DIRECTIONAL",
        roles=(
            EndpointSetupRole(
                "A",
                "A · SOURCE",
                ("source", "source/child"),
                frozenset({"source", "source/child"}),
                "source",
                current_context="target",
                height=3,
                allow_descendants=True,
            ),
            EndpointSetupRole(
                "B",
                "B · TARGET",
                ("target", "target/child"),
                frozenset({"target", "target/child"}),
                "target",
                current_context="target",
                height=3,
                allow_descendants=True,
            ),
        ),
        action_label="CONTINUE WITH EXACT A/B RANGES",
    )
    print("$ endpoint setup component harness · independent A/B reach", flush=True)
    print(
        f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}",
        flush=True,
    )
    draft = run_endpoint_setup(spec)
    label = "CANCEL RECEIPT" if cancel else "TYPED SETUP RECEIPT"
    print(f"\n{label} · {draft!r}")
    if draft is not None:
        print(
            "  RANGES · "
            f"A={draft.value('A').include_descendants} · "
            f"B={draft.value('B').include_descendants}"
        )
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
        child.expect("ENDPOINT SETUP")
        _BASE._settle(child)
        _snapshot(recorder, "01-entry-a-context")

        child.send("\t\x1b[C")
        _BASE._settle(child)
        _snapshot(recorder, "02-a-descendants-selected")

        child.send("\t\t")
        _BASE._settle(child)
        _snapshot(recorder, "03-b-range-remains-exact")

        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "04-complete-range-review")

        child.send("\r")
        child.expect("TYPED SETUP RECEIPT")
        _BASE._settle(child)
        _snapshot(recorder, "05-read-only-range-receipt")
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
        _snapshot(recorder, "06-cancelled-without-ranges")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="endpoint-reach-capture-") as directory:
        root = Path(directory)
        _capture_success(root / "success" / ".mem")
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
