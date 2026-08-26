"""Capture selectable Merge Target behavior in a real 180x52 color PTY."""

from __future__ import annotations

import importlib.util
import io
import os
import sys
import tempfile
from pathlib import Path

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/screenshots/mem-merge-target-selection-20260820"
COLUMNS = 180
ROWS = 52
DOWN = "\x1b[B"
UP = "\x1b[A"

_BASE_PATH = (
    ROOT / "docs/screenshots/context-endpoint-memory-preview-20260810/capture.py"
)
_SPEC = importlib.util.spec_from_file_location("merge_target_capture_base", _BASE_PATH)
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


def _initialize() -> None:
    import memcommit.ops as ops
    from memcommit.store import MemoryStore

    store = MemoryStore()
    source = ops.init("source")
    ops.add(source, "source-only addition")
    store.create_context(source)
    store.create_context(ops.init("target-current"))
    store.create_context(ops.init("target-selected"))
    store.set_current("target-current")


def _verification(kind: str) -> str:
    from memcommit.context import Memory
    from memcommit.store import MemoryStore

    store = MemoryStore()

    def contents(name: str) -> list[str]:
        return [
            item.content
            for item in store.load_direct(name).iter_items()
            if isinstance(item, Memory)
        ]

    return (
        f"{kind.upper()} VERIFICATION\n"
        f"CURRENT POINTER · {store.current_context_name()}\n"
        f"CURRENT TARGET · {contents('target-current')!r}\n"
        f"SELECTED TARGET · {contents('target-selected')!r}\n"
        f"CHECKPOINTS · CURRENT {len(store.list_checkpoints('target-current'))} · "
        f"SELECTED {len(store.list_checkpoints('target-selected'))}"
    )


def _run_child(kind: str) -> None:
    import click
    import typer

    from memcommit.commands.merge.command import cmd as merge_command

    with tempfile.TemporaryDirectory(prefix="mem-merge-target-capture-") as directory:
        _configure_isolated_store(Path(directory) / ".mem")
        _initialize()
        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        app = typer.Typer()

        @app.callback()
        def capture_root() -> None:
            """Keep Typer in command-group mode for the focused adapter."""

        app.command("merge")(merge_command)
        exit_code = 0
        try:
            returned = app(args=["merge"], prog_name="mem", standalone_mode=False)
        except click.exceptions.Exit as error:
            exit_code = error.exit_code
        else:
            if isinstance(returned, int):
                exit_code = returned
        print(f"COMMAND EXIT · {exit_code}", flush=True)
        if kind == "selected":
            # Keep the command receipt and the separate read-only store check
            # as distinct captured states even though local decision-free
            # Merge intentionally applies without a duplicate review screen.
            sys.stdin.readline()
        print(_verification(kind), flush=True)
        sys.stdin.readline()


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
        timeout=20,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> str:
    _BASE._snapshot(recorder, stem)
    return (OUT / f"{stem}.txt").read_text(encoding="utf-8")


def _capture_selected_target() -> None:
    child, recorder = _spawn("selected")
    try:
        child.expect("NEW MERGE")
        _BASE._settle(child)
        canvas = _snapshot(recorder, "01-entry-current-target-default")
        assert "B · TARGET · CREATE AUTHORITY" in canvas
        assert "B · target-current" in canvas

        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "02-source-focused")

        child.send("\t")
        _BASE._settle(child)
        canvas = _snapshot(recorder, "03-target-focused")
        assert "target-current" in canvas
        assert "target-selected" in canvas

        child.send(DOWN + "\r")
        _BASE._settle(child)
        canvas = _snapshot(recorder, "04-alternate-target-selected")
        assert "› ✓   · target-selected" in canvas

        child.send("\t")
        _BASE._settle(child)
        canvas = _snapshot(recorder, "05-setup-ready")
        assert "B · target-selected" in canvas

        child.send("\r")
        child.expect("COMMAND EXIT")
        canvas = _snapshot(recorder, "06-selected-target-success-receipt")
        assert "Merged 'source' into 'target-selected'" in canvas
        assert "added 1 memory" in canvas

        child.send("\r")
        child.expect("SELECTED VERIFICATION")
        canvas = _snapshot(recorder, "07-read-only-verification")
        assert "CURRENT POINTER · target-current" in canvas
        assert "CURRENT TARGET · []" in canvas
        assert "CHECKPOINTS · CURRENT 0 · SELECTED 1" in canvas
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_same_endpoint_rejection() -> None:
    child, recorder = _spawn("same-endpoint")
    try:
        child.expect("NEW MERGE")
        # MODE -> Source -> Target. Select Source itself as Target, then try
        # Continue; validation must keep the setup open and publish nothing.
        child.send("\t\t" + UP + "\r\t\r")
        _BASE._settle(child)
        canvas = _snapshot(recorder, "08-same-endpoint-rejected")
        assert "Merge Source A and Target B must be distinct" in canvas
        assert "B · source" in canvas
        child.send("q")
        child.expect("SAME-ENDPOINT VERIFICATION")
        canvas = _snapshot(recorder, "09-rejection-read-only-verification")
        assert "CHECKPOINTS · CURRENT 0 · SELECTED 0" in canvas
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _capture_selected_target()
    _capture_same_endpoint_rejection()
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "PTY 180 52" in raw
    assert "\x1b[" in raw
    assert "38;" in raw
    assert "48;" in raw


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT))
        _run_child(sys.argv[2])
    else:
        main()
