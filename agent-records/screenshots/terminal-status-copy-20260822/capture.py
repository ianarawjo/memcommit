"""Capture representative task-oriented status copy in a 180x52 color PTY."""

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
_SPEC = importlib.util.spec_from_file_location("status_copy_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


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


def _prepare_compare_store(root: Path):
    import memcommit.ops as ops
    from memcommit.store import MemoryStore

    store = MemoryStore(root=root)
    reference = ops.init("capture/reference")
    ops.add(reference, "The accessible entrance remains open until 18:00.")
    peer = ops.init("capture/peer")
    ops.add(peer, "The north entrance closes at 17:00.")
    for context in (reference, peer):
        store.create_context(context)
    store.set_current(reference.name)
    return store


def _run_ground_child(_store_root: Path) -> None:
    from memcommit.commands.ground.shell import run_ground_shell

    print("$ mem ground", flush=True)
    print(
        f"PTY · {os.get_terminal_size().columns} COLUMNS × "
        f"{os.get_terminal_size().lines} ROWS",
        flush=True,
    )
    result = run_ground_shell(
        interpret=lambda _text: (_ for _ in ()).throw(
            AssertionError("blank Ground capture opened the provider")
        ),
        apply=lambda _proposal: (_ for _ in ()).throw(
            AssertionError("blank Ground capture applied a proposal")
        ),
        current_context_name="capture/reference",
        context_catalog_count=2,
        context_catalog_names=("capture/reference", "capture/peer"),
        background_interpretation=False,
    )
    print(f"\nCLOSE RECEIPT · {result.status}", flush=True)


def _run_compare_child(store_root: Path) -> None:
    from memcommit.commands.compare.setup import choose_compare_setup

    store = _prepare_compare_store(store_root)
    before = {
        name: store._context_file(name).read_bytes()
        for name in store.list_context_names()
    }
    print("$ mem compare · endpoint setup", flush=True)
    print(
        f"PTY · {os.get_terminal_size().columns} COLUMNS × "
        f"{os.get_terminal_size().lines} ROWS",
        flush=True,
    )
    receipt = choose_compare_setup(store)
    unchanged = all(
        store._context_file(name).read_bytes() == content
        for name, content in before.items()
    )
    print(f"\nCLOSE RECEIPT · {receipt!r}")
    print(f"CONTEXT BYTES UNCHANGED · {unchanged}", flush=True)


def _run_summary_child(_store_root: Path) -> None:
    from memcommit.interfaces.tui.operations.summarize.adapter import (
        project_summarize_result,
    )
    from memcommit.interfaces.tui.viewers.semantic import run_semantic_viewer
    from memcommit.summarize_application import SummarizeResult
    from memcommit.understanding import UnderstandingSummary

    result = SummarizeResult(
        context_name="capture/reference",
        include_descendants=False,
        follow_embeds=False,
        source_digest="a" * 64,
        source_count=2,
        understanding=UnderstandingSummary(
            "The current Context records an accessible entrance and its operating period.",
            ("memory-1", "memory-2"),
        ),
    )
    print("$ mem summarize capture/reference", flush=True)
    print(
        f"PTY · {os.get_terminal_size().columns} COLUMNS × "
        f"{os.get_terminal_size().lines} ROWS",
        flush=True,
    )
    run_semantic_viewer(
        project_summarize_result(result),
        title="SUMMARY",
    )
    print("\nCLOSE RECEIPT · SUMMARY VIEW CLOSED", flush=True)


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


def _capture(
    kind: str,
    store_root: Path,
    *,
    expected: str,
    stem: str,
) -> None:
    child, recorder = _spawn(kind, store_root)
    try:
        child.expect(expected)
        _BASE._settle(child)
        _BASE._snapshot(recorder, stem)
        child.send("\x1b")
        child.expect("CLOSE RECEIPT")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for pattern in ("*.png", "*.txt", "*.typescript"):
        for path in OUT.glob(pattern):
            path.unlink()
    with tempfile.TemporaryDirectory(prefix="terminal-status-copy-") as directory:
        base = Path(directory)
        _capture(
            "ground",
            base / "ground-store",
            expected="MEM GROUND .* DRAFT",
            stem="01-ground-draft",
        )
        _capture(
            "compare",
            base / "compare-store",
            expected="NEW COMPARE",
            stem="02-compare-task-setup",
        )
        _capture(
            "summary",
            base / "summary-store",
            expected="STATUS .* DIRECT .* SOURCES 2",
            stem="03-summarize-result",
        )
    streams = {
        path.name: path.read_text(encoding="utf-8")
        for path in OUT.glob("*.typescript")
    }
    if not streams or not all("\x1b[" in raw for raw in streams.values()):
        raise RuntimeError("Capture did not retain ANSI terminal control sequences.")
    if not any("38;2;" in raw or "48;2;" in raw for raw in streams.values()):
        raise RuntimeError("Capture did not retain true-color terminal styles.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        case = sys.argv[2]
        root = Path(sys.argv[3])
        if case == "ground":
            _run_ground_child(root)
        elif case == "compare":
            _run_compare_child(root)
        elif case == "summary":
            _run_summary_child(root)
        else:
            raise SystemExit(f"Unknown capture case: {case}")
    else:
        main()
