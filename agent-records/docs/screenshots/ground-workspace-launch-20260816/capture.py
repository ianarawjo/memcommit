"""Capture Ground launcher -> Save Location -> physical workspace in a PTY."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import pexpect


ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "agent-records/docs/screenshots/ground-workspace-launch-20260816"
COLUMNS = 180
ROWS = 52

_BASE_PATH = (
    ROOT
    / "agent-records/docs/screenshots/context-endpoint-memory-preview-20260810/capture.py"
)
_SPEC = importlib.util.spec_from_file_location("ground_launch_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _isolate_store(root: Path) -> None:
    import memcommit.persistence.store as store_module

    store_dir = root / ".mem"
    assignments = {
        "STORE_DIR": store_dir,
        "CONTEXTS_DIR": store_dir / "contexts",
        "QUERY_SOURCES_DIR": store_dir / "query-sources",
        "STATE_FILE": store_dir / "state.json",
        "IMPACT_PLAN_FILE": store_dir / "impact-plan.json",
        "STAGED_UPDATE_FILE": store_dir / "staged-update.json",
        "REVIEW_SESSION_FILE": store_dir / "review-session.json",
        "ATOMIZE_ANALYSES_DIR": store_dir / "atomize-analyses",
        "ATOMIZE_WORKBENCHES_DIR": store_dir / "atomize-workbenches",
        "GROUND_SESSIONS_DIR": store_dir / "ground-sessions",
        "MELD_SESSIONS_DIR": store_dir / "meld-sessions",
    }
    for name, value in assignments.items():
        setattr(store_module, name, value)


def _run_child() -> None:
    from typer.testing import CliRunner

    from memcommit.adapters.console.commands.ground_workbench.ground.command.workflow import (
        apply as ground_apply_workflow,
        create as ground_create_workflow,
    )
    import memcommit.application.capabilities.ops as ops
    from memcommit.adapters.console.entrypoint import app
    from memcommit.application.operations.ground_workbench.ground.dialogue import GroundDialogueProposal
    from memcommit.application.operations.ground_workbench.ground.workspace_runtime import (
        load_ground_workspace,
    )
    from memcommit.persistence.store import MemoryStore

    with tempfile.TemporaryDirectory(prefix="memcommit-ground-launch-capture-") as temp:
        _isolate_store(Path(temp))
        store = MemoryStore()
        store.create_context(ops.init("projects"))
        store.set_current("projects")
        before_current = store.current_context_name()

        def fixed_turn(_text, _provider, *, context_names=(), ground_name=None):
            assert context_names == ()
            assert ground_name == "projects/ticker-ground"
            # Keep the provider turn open long enough to capture the real
            # target-owned liveness title before returning a proposal.
            time.sleep(1)
            return GroundDialogueProposal(
                understanding=(
                    "The Ground will develop rules explaining how real US "
                    "ticker symbols are assigned."
                ),
                question="Approve this Goal and create the physical workspace?",
                ground_name=ground_name,
                goal="Find how real US ticker symbols are assigned.",
            )

        ground_create_workflow.interpret_ground_dialogue = fixed_turn

        runner = CliRunner()

        def run_in_process(argv):
            invoked = runner.invoke(app, [*argv[1:], "--snapshot"])
            return subprocess.CompletedProcess(
                argv,
                invoked.exit_code,
                stdout=invoked.output,
                stderr="",
            )

        ground_apply_workflow._run_approved_ground_command = run_in_process
        size = os.get_terminal_size()
        assert (size.columns, size.lines) == (COLUMNS, ROWS)
        print("PTY", size.columns, size.lines)
        app(args=["ground"], prog_name="mem", standalone_mode=False)

        workspace = load_ground_workspace(store, "projects/ticker-ground")
        assert tuple(context.name for context in workspace.all_contexts) == (
            "projects/ticker-ground",
            "projects/ticker-ground/goals",
            "projects/ticker-ground/rules",
            "projects/ticker-ground/examples",
            "projects/ticker-ground/contexts",
            "projects/ticker-ground/relations",
        )
        assert store.current_context_name() == before_current
        assert not (store.store_dir / "ground-sessions").exists()
        print(
            "GROUND CLOSED · SIX PHYSICAL CONTEXTS SAVED · "
            "LEGACY SESSION ABSENT · CURRENT UNCHANGED"
        )


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


def _spawn() -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child"],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=30,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> None:
    _BASE._snapshot(recorder, stem)


def _capture() -> None:
    child, recorder = _spawn()
    try:
        child.expect("MEM GROUND · WORKSPACES")
        _BASE._settle(child)
        _snapshot(recorder, "01-empty-launcher")

        child.send("\r")
        child.expect("SAVE LOCATION · NOT SET")
        _BASE._settle(child)
        _snapshot(recorder, "02-save-location")

        child.send("\x1b[Z\r")
        child.expect("NEW GROUND · SAVE LOCATION")
        child.send("\x15projects/ticker-ground")
        _BASE._settle(child)
        _snapshot(recorder, "03-exact-location-edited")

        child.send("\r")
        # Focus styling can split the workbench title across ANSI fragments;
        # the operation-owned Goal question is a stable visible readiness cue.
        child.expect("OPEN QUESTION · GOAL")
        _BASE._settle(child, seconds=0.2)
        _snapshot(recorder, "04-unsaved-workspace")

        # Returning from Location keeps that Surface focused. Move into Goal,
        # open its revision field, and submit from that semantic owner.
        child.send("\t\rFind how real US ticker symbols are assigned.\r")
        # Focus styling inserts ANSI boundaries inside the frame title, so
        # capture by bounded provider delay rather than matching a de-styled
        # substring that is not contiguous in the raw PTY stream.
        time.sleep(0.15)
        _BASE._settle(child, seconds=0.1)
        _snapshot(recorder, "05-goal-thinking")

        # prompt-toolkit inserts cursor-forward ANSI sequences between words
        # in this focused state, so allow those bytes inside the visible footer.
        child.expect(r"Goal.*proposed")
        _BASE._settle(child, seconds=0.2)
        _snapshot(recorder, "06-goal-revision-proposed")

        child.send("\t\t\t\t")
        _BASE._settle(child, seconds=0.25)
        _snapshot(recorder, "07-exact-creation-review")

        child.send("\r")
        child.expect("CONTEXT-ROOTED WORKSPACE")
        _BASE._settle(child)
        _snapshot(recorder, "08-physical-workspace")

        child.send("q")
        child.expect("GROUND CLOSED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "09-durable-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _capture()
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    plain = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.txt"))
    assert "PTY 180 52" in raw
    assert "START NEW GROUND WORKSPACE" in plain
    assert "SAVE LOCATION · NOT SET" in plain
    assert "NEW GROUND · SAVE LOCATION" in plain
    assert "Existing Contexts are not recommended or selected here." in plain
    assert "GOAL · THINKING" in plain
    assert "PROPOSED GOAL REVISION" in plain
    assert "PROPOSED COMMAND · NOT RUN" in plain
    assert "CONTEXT-ROOTED WORKSPACE" in plain
    assert "SIX PHYSICAL CONTEXTS SAVED" in plain
    assert "\x1b[" in raw and "38;" in raw


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT / "src"))
        _run_child()
    else:
        main()
