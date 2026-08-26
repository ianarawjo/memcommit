"""Capture interactive Add's exact multi-draft flow in a real color PTY."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile

import pexpect


ROOT = Path("/Users/KimMunyeong/Github/memcommit")
OUT = ROOT / "docs/screenshots/mem-add-tui-20260814"
COLUMNS = 180
ROWS = 52
UP = "\x1b[A"
SHIFT_TAB = "\x1b[Z"

_BASE_PATH = (
    ROOT / "docs/screenshots/context-endpoint-memory-preview-20260810/capture.py"
)
_SPEC = importlib.util.spec_from_file_location("add_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _configure_isolated_store(store_root: Path) -> None:
    import memcommit.store as store_module

    values = {
        "STORE_DIR": store_root,
        "CONTEXTS_DIR": store_root / "contexts",
        "QUERY_SOURCES_DIR": store_root / "query-sources",
        "STATE_FILE": store_root / "state.json",
        "IMPACT_PLAN_FILE": store_root / "impact-plan.json",
        "STAGED_UPDATE_FILE": store_root / "staged-update.json",
        "REVIEW_SESSION_FILE": store_root / "review-session.json",
        "ATOMIZE_ANALYSES_DIR": store_root / "atomize-analyses",
        "ATOMIZE_WORKBENCHES_DIR": store_root / "atomize-workbenches",
        "ATOMIZE_GROUNDING_SESSIONS_DIR": store_root / "atomize-groundings",
        "ATOMIZE_GROUNDING_HISTORY_DIR": store_root / "atomize-grounding-history",
        "GROUND_SESSIONS_DIR": store_root / "ground-sessions",
        "MELD_SESSIONS_DIR": store_root / "meld-sessions",
    }
    for name, value in values.items():
        setattr(store_module, name, value)

    # The capture exercises the real local Context catalog. It deliberately
    # excludes the host's registered Profiles and Grants from this fixture.
    import memcommit.commands.add.command as add_command

    add_command.freeze_granted_context_navigation = lambda _store: SimpleNamespace(
        names=(),
        annotations={},
    )


def _initialize() -> None:
    import memcommit.ops as ops
    from memcommit.store import MemoryStore

    store = MemoryStore()
    for name in ("alpha", "target"):
        store.save(ops.init(name))
    store.set_current("target")


def _run_add_child(*, cancel: bool) -> None:
    from memcommit.cli import app
    from memcommit.store import MemoryStore

    with tempfile.TemporaryDirectory(prefix="mem-add-capture-") as directory:
        _configure_isolated_store(Path(directory) / ".mem")
        _initialize()
        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        app(args=["add"], prog_name="mem", standalone_mode=False)

        store = MemoryStore()
        alpha = store.load_direct("alpha")
        target = store.load_direct("target")
        if cancel:
            print(
                "CANCEL VERIFIED · ALPHA MEMORIES 0 · TARGET MEMORIES 0 · "
                "NO ADD CHECKPOINT"
            )
            return
        contents = [memory.content for memory in alpha.memories.values()]
        checkpoints = store.list_checkpoints("alpha")
        print(
            "DURABLE VERIFICATION · ALPHA MEMORIES "
            f"{len(contents)} · TARGET MEMORIES {len(target.memories)} · "
            f"ADD CHECKPOINTS {sum(item['command'] == 'add' for item in checkpoints)}"
        )
        print("MEMORY 1", repr(contents[0]))
        print("MEMORY 2", repr(contents[1]))


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _spawn(kind: str) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind],
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


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    child, recorder = _spawn("add")
    try:
        child.expect("DRAFT MEMORIES")
        _BASE._settle(child)
        _snapshot(recorder, "01-entry")

        child.send(SHIFT_TAB + UP + "\r")
        _BASE._settle(child)
        _snapshot(recorder, "02-alpha-target-selected")

        child.send("\te")
        child.send("First exact Memory.\rSecond physical line.")
        _BASE._settle(child)
        _snapshot(recorder, "03-first-multiline-edit")

        child.send("\x13")
        _BASE._settle(child)
        _snapshot(recorder, "04-first-draft-staged")

        child.send("n")
        child.send(
            "Second Memory line 01\rline 02\rline 03\rline 04\rline 05\r"
            "line 06\rline 07\rline 08\rline 09\rline 10\rline 11\rline 12"
        )
        _BASE._settle(child)
        _snapshot(recorder, "05-second-editor-scrolled")

        child.send("\x13")
        _BASE._settle(child)
        _snapshot(recorder, "06-two-drafts-staged")

        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "07-exact-add-action")

        child.send("\r")
        child.expect("STATUS · SUCCESS")
        _BASE._settle(child)
        _snapshot(recorder, "08-success-receipt")

        child.send("\r")
        child.expect("DURABLE VERIFICATION")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "09-durable-verification")
    finally:
        if child.isalive():
            child.close(force=True)

    child, recorder = _spawn("cancel")
    try:
        child.expect("DRAFT MEMORIES")
        child.send("q")
        child.expect("CANCEL VERIFIED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "10-cancel-verification")
    finally:
        if child.isalive():
            child.close(force=True)

    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "\x1b[" in raw
    assert "38;" in raw


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT))
        _run_add_child(cancel=sys.argv[2] == "cancel")
    else:
        main()
