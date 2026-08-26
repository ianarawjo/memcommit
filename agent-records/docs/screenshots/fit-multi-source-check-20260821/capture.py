"""Capture Ground-free Fit with multiple Context and Memory operands."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SOURCE_PATH = ROOT / "agent-records/docs/screenshots/fit-compact-receipt-20260821/capture.py"
ROWS = 52
COLUMNS = 180

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SOURCE = _load_module("fit_multi_source_capture_base", SOURCE_PATH)
BASE = SOURCE.BASE
BASE.OUT = OUT


def _context(
    name: str,
    *,
    context_uid: str,
    memory_uid: str,
    content: str,
):
    from memcommit.context import Context, Memory

    context = Context(uid=context_uid, name=name)
    context.add(Memory(uid=memory_uid, content=content))
    return context


def _run_contexts_child(store_root: Path) -> None:
    import memcommit.commands.fit.command as fit_command
    from memcommit.fit_store import FitStore
    from memcommit.store import MemoryStore, context_record_digest

    SOURCE._Provider.calls = 0
    SOURCE._use_store_root(store_root)
    store = MemoryStore(root=store_root)
    contexts = (
        _context(
            "context-a",
            context_uid="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            memory_uid="a1111111-1111-1111-1111-111111111111",
            content="Context A requires one stable public ticker.",
        ),
        _context(
            "context-b",
            context_uid="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            memory_uid="b2222222-2222-2222-2222-222222222222",
            content="Context B uses AAPL for Apple Inc.",
        ),
        _context(
            "context-c",
            context_uid="cccccccc-cccc-cccc-cccc-cccccccccccc",
            memory_uid="c3333333-3333-3333-3333-333333333333",
            content="Context C reserves AXAI for Axiom AI Technologies.",
        ),
    )
    for context in contexts:
        store.create_context(context)
    store.set_current("context-a")
    before = {
        context.name: context_record_digest(store.load_direct(context.name))
        for context in contexts
    }
    fit_command.connect_semantic_provider = SOURCE._Provider

    print("$ mem fit context-a context-b context-c")
    print(f"PTY · {os.get_terminal_size().columns}×{os.get_terminal_size().lines}")
    fit_command.cmd(
        [context.name for context in contexts],
        background=None,
        memory_sources=None,
        context_sources=None,
        ground_name=None,
        receipt=None,
        plain=False,
    )
    unchanged = all(
        context_record_digest(store.load_direct(name)) == digest
        for name, digest in before.items()
    )
    print("SOURCE KIND · 3 CONTEXTS · GROUND ABSENT")
    print(f"READ-ONLY VERIFICATION · {unchanged}")
    print(f"PROVIDER CALLS · {SOURCE._Provider.calls}")
    print(f"FIT RECEIPTS · {len(FitStore(store).list())}")
    SOURCE._gate()


def _run_memories_child(store_root: Path) -> None:
    import memcommit.commands.fit.command as fit_command
    from memcommit.context import Context, Memory
    from memcommit.fit_store import FitStore
    from memcommit.store import MemoryStore, context_record_digest

    SOURCE._Provider.calls = 0
    SOURCE._use_store_root(store_root)
    store = MemoryStore(root=store_root)
    context = Context(
        uid="dddddddd-dddd-dddd-dddd-dddddddddddd",
        name="memory-set",
    )
    memories = (
        Memory(
            uid="11111111-1111-1111-1111-111111111111",
            content="Use one stable public ticker per company.",
        ),
        Memory(
            uid="22222222-2222-2222-2222-222222222222",
            content="Apple Inc. uses AAPL.",
        ),
        Memory(
            uid="33333333-3333-3333-3333-333333333333",
            content="Axiom AI Technologies uses AXAI.",
        ),
    )
    for memory in memories:
        context.add(memory)
    store.create_context(context)
    store.set_current(context.name)
    before = context_record_digest(store.load_direct(context.name))
    selectors = [memory.uid[:8] for memory in memories]
    fit_command.connect_semantic_provider = SOURCE._Provider

    print(f"$ mem fit {' '.join(selectors)}")
    print(f"PTY · {os.get_terminal_size().columns}×{os.get_terminal_size().lines}")
    fit_command.cmd(
        selectors,
        background=None,
        memory_sources=None,
        context_sources=None,
        ground_name=None,
        receipt=None,
        plain=False,
    )
    unchanged = context_record_digest(store.load_direct(context.name)) == before
    print("SOURCE KIND · 3 DIRECT MEMORIES · GROUND ABSENT")
    print(f"READ-ONLY VERIFICATION · {unchanged}")
    print(f"PROVIDER CALLS · {SOURCE._Provider.calls}")
    print(f"FIT RECEIPTS · {len(FitStore(store).list())}")
    SOURCE._gate()


def _spawn(kind: str, store_root: Path):
    recorder = BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind, str(store_root)],
        cwd=str(ROOT),
        env=SOURCE._environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=15,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _capture(kind: str, store_root: Path, stem: str) -> None:
    child, recorder = _spawn(kind, store_root)
    try:
        child.expect("CAPTURE GATE")
        BASE._settle(child, seconds=0.15)
        BASE._snapshot(recorder, stem)
        child.send("v\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    from memcommit.interfaces.console.theme import (
        SemanticColorRole,
        semantic_color_rgb,
    )

    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-fit-multi-source-") as directory:
        root = Path(directory)
        _capture("contexts", root / "contexts", "01-three-contexts")
        _capture("memories", root / "memories", "02-three-memories")

    context_text = (OUT / "01-three-contexts.txt").read_text()
    memory_text = (OUT / "02-three-memories.txt").read_text()
    normalized_context = " ".join(context_text.split())
    normalized_memory = " ".join(memory_text.split())
    if "PTY · 180×52" not in context_text or "PTY · 180×52" not in memory_text:
        raise RuntimeError("The multi-source captures did not retain 180×52.")
    if "[TARGETS: CONTEXT context-a, context-b, context-c]" not in normalized_context:
        raise RuntimeError("The Context target group is incomplete.")
    if (
        "[TARGETS: MEMORY 11111111, 22222222, 33333333]" not in normalized_memory
        or "CONTEXT" in normalized_memory.split("SOURCE KIND", 1)[0]
    ):
        raise RuntimeError("The direct-Memory target group is incorrect.")
    if any(
        "FIT RECEIPTS · 0" not in text or "READ-ONLY VERIFICATION · True" not in text
        for text in (context_text, memory_text)
    ):
        raise RuntimeError("Fit did not remain process-local and read-only.")

    red, green, blue = semantic_color_rgb(SemanticColorRole.JUDGMENT_YES)
    styled_yes = f"\x1b[38;2;{red};{green};{blue}m\x1b[1mYES\x1b[0m"
    for stem in ("01-three-contexts", "02-three-memories"):
        stream = (OUT / f"{stem}.typescript").read_text()
        if styled_yes not in stream:
            raise RuntimeError(f"{stem} omitted the shared YES color.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        kind = sys.argv[2]
        root = Path(sys.argv[3])
        if kind == "contexts":
            _run_contexts_child(root)
        elif kind == "memories":
            _run_memories_child(root)
        else:
            raise RuntimeError(f"Unknown capture kind: {kind}")
    else:
        main()
