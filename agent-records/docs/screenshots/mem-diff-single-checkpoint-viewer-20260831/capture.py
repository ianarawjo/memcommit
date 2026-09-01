"""Capture single-checkpoint Diff in a real 180x52 color PTY."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import re
import site
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52

_BASE_PATH = (
    ROOT
    / "agent-records/docs/screenshots/mem-help-a-z-boundary-20260813/capture_help_a_z.py"
)
_SPEC = importlib.util.spec_from_file_location("diff_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLS = COLUMNS
_BASE.ROWS = ROWS


def _environment(home: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "HOME": str(home),
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PROMPT_TOOLKIT_COLOR_DEPTH": "DEPTH_24_BIT",
            "PROMPT_TOOLKIT_NO_CPR": "1",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
            "PYTHONPATH": os.pathsep.join(
                (str(ROOT / "src"), site.getusersitepackages())
            ),
        }
    )
    return environment


def _store_bytes(root: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _child() -> None:
    import memcommit.application.capabilities.ops as ops
    from memcommit.adapters.console.entrypoint import app
    from memcommit.core.context import AutoCheckpoint
    from memcommit.persistence.store import MemoryStore

    size = os.get_terminal_size()
    print(f"LIVE PTY · {size.columns} columns × {size.lines} rows", flush=True)
    if (size.columns, size.lines) != (COLUMNS, ROWS):
        raise RuntimeError("Capture PTY dimensions are not 180×52.")

    store = MemoryStore()
    context = ops.init("coffee")
    for content in (
        "I like cafés near a subway stop.",
        "I prefer a seat with a backrest.",
        "I usually order a hand-drip coffee.",
        "I avoid cafés where several conversations overlap loudly.",
        "I avoid cafés where tables are too low to use plates or a laptop comfortably.",
        "Sparse flavor notes make it difficult for me to choose a coffee.",
        "I prefer menus with enough options for ordering with a companion.",
    ):
        ops.add(context, content)
    store.save(
        context,
        AutoCheckpoint(
            command="add",
            args={},
            description="Recorded the initial coffee preferences.",
        ),
    )
    replacements = (
        (
            "I avoid cafés where several conversations overlap loudly.",
            "I avoid cafés where several conversations overlap loudly, but a café "
            "where nobody talks also feels uncomfortable for a gathering.",
        ),
        (
            "I avoid cafés where tables are too low to use plates or a laptop comfortably.",
            "I avoid cafés where tables are too low to use plates or a laptop "
            "comfortably, as well as cafés with unusually high uniform tables.",
        ),
        (
            "Sparse flavor notes make it difficult for me to choose a coffee.",
            "Flavor descriptions that are too sparse, abstract, or exaggerated make "
            "it difficult for me to choose a coffee.",
        ),
        (
            "I prefer menus with enough options for ordering with a companion.",
            "I prefer menus with enough options for ordering with a companion, but "
            "too many options make it difficult to choose.",
        ),
    )
    memories = {
        memory.content: memory
        for memory in context.memories.values()
    }
    for before, after in replacements:
        ops.edit(context, memories[before].uid, after)
    store.save(
        context,
        AutoCheckpoint(
            command="update",
            args={},
            description="Merged four complementary coffee preferences.",
        ),
    )
    store.set_current(context.name)
    before = _store_bytes(store.store_dir)

    print("$ mem diff coffee", flush=True)
    app(args=["diff", "coffee"], prog_name="mem", standalone_mode=False)

    print("\n$ mem diff coffee --stat", flush=True)
    app(
        args=["diff", "coffee", "--stat"],
        prog_name="mem",
        standalone_mode=False,
    )
    after = _store_bytes(store.store_dir)
    if after != before:
        raise RuntimeError("Diff changed durable store bytes.")
    print(
        "READ-ONLY VERIFIED · STORE BYTES UNCHANGED · CURRENT coffee",
        flush=True,
    )


def _spawn(home: Path) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child"],
        cwd=str(ROOT),
        env=_environment(home),
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> None:
    _BASE._snapshot(recorder, stem)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mem-diff-viewer-") as temporary_home:
        child, recorder = _spawn(Path(temporary_home))
        try:
            child.expect("CHECKPOINT REVISION")
            _BASE._pump(child, seconds=1.0)
            _snapshot(recorder, "01-read-only-viewer-entry")

            child.send("q")
            child.expect("READ-ONLY VERIFIED")
            child.expect(pexpect.EOF)
            _snapshot(recorder, "02-close-and-read-only-verification")
        finally:
            if child.isalive():
                child.close(force=True)

    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
    if "180 columns × 52 rows" not in raw:
        raise RuntimeError("The live PTY did not verify 180×52 dimensions.")
    if re.search(r"\x1b\[[0-9;]*38;2;", raw) is None:
        raise RuntimeError("The Viewer stream did not contain true-color foreground ANSI.")
    if "38;2;237;135;150" not in raw or "38;2;166;218;149" not in raw:
        raise RuntimeError("The Viewer stream did not contain red/green diff semantics.")


if __name__ == "__main__":
    if sys.argv[1:] == ["--child"]:
        _child()
    else:
        main()
