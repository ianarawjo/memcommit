"""Capture aggregate and Atomize-filtered Impact launchers in a real PTY."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

import click
import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52
DOWN = "\x1b[B"

_BASE_PATH = ROOT / "agent-records/docs/screenshots/atomize-memory-selection-20260814/capture.py"
_SPEC = importlib.util.spec_from_file_location(
    "impact_launcher_capture_base", _BASE_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _configure_store(store_root: Path) -> None:
    import memcommit.persistence.store as store_module

    paths = {
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
    for name, path in paths.items():
        setattr(store_module, name, path)


class _AtomizeProvider:
    calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        type(self).calls += 1
        assert operation == "impact_atomize"
        payload = json.loads(prompt.split("ATOMIZE IMPACT PAYLOAD:\n", 1)[1])
        source_ids = [item["candidate_id"] for item in payload["memories"]]
        return json.dumps(
            {
                "overview": {
                    "understood": {
                        "text": "The source records one independently revisable policy.",
                        "source_ids": source_ids,
                    },
                    "changed": {
                        "text": "No split is required.",
                        "source_ids": source_ids,
                    },
                    "unresolved": {"text": "", "source_ids": []},
                },
                "items": [
                    {
                        "candidate_id": source_id,
                        "classification": "ATOMIC",
                        "reason_codes": ["A01_ONE_FOCUS"],
                        "children": [],
                        "reason": "The source contains one independent policy.",
                    }
                    for source_id in source_ids
                ],
                "quality_issues": [],
            }
        )


class _UpdateProvider:
    calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        type(self).calls += 1
        payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
        source_id = payload["source"]["memories"][0]["source_id"]
        target_id = payload["target"]["memories"][0]["target_id"]
        return json.dumps(
            {
                "edits": [
                    {
                        "target_id": target_id,
                        "new_content": "Publication review closes after fourteen days.",
                        "source_ids": [source_id],
                        "reason": "The verified policy supersedes the prior window.",
                    }
                ],
                "additions": [],
                "removals": [],
            }
        )


def _context(store, name: str, content: str):
    import memcommit.application.capabilities.ops as ops

    context = ops.init(name)
    ops.add(context, content)
    store.create_context(context)
    return context


def _prepare_store(store_root: Path):
    from memcommit.application.operations.atomize.analysis_application import AtomizeAnalysisOpenRequest
    from memcommit.application.operations.atomize.analysis_runtime import execute_atomize_analysis_open
    from memcommit.persistence.store import MemoryStore
    from memcommit.application.operations.update.model import plan_update

    store = MemoryStore(root=store_root)
    atomize_context = _context(
        store,
        "capture/impact/atomize",
        "Publication review closes after seven days.",
    )
    atomize_open = execute_atomize_analysis_open(
        AtomizeAnalysisOpenRequest(context=atomize_context),
        store=store,
        provider_factory=_AtomizeProvider,
    )
    source = _context(
        store,
        "capture/impact/update-source",
        "Publication review closes after fourteen days.",
    )
    target = _context(
        store,
        "capture/impact/update-target",
        "Publication review closes after seven days.",
    )
    update = plan_update(source, target, _UpdateProvider)
    store.save_impact_plan(update)
    store.set_current(atomize_context.name)
    return store, atomize_context, atomize_open.analysis, update


def _invoke(argv: list[str]) -> int:
    from memcommit.adapters.console.entrypoint import app

    print("$ mem " + " ".join(argv), flush=True)
    try:
        result = app(args=argv, prog_name="mem", standalone_mode=False)
    except click.exceptions.Exit as error:
        return error.exit_code
    return result if isinstance(result, int) else 0


def _run_child(kind: str, store_root: Path) -> None:
    _configure_store(store_root)
    store, context, analysis, update = _prepare_store(store_root)
    context_path = store._context_file(context.name)
    context_before = context_path.read_bytes()
    workbench_path = store._atomize_workbench_path(context.uid)
    workbench_before = workbench_path.read_bytes()
    impact_plan_before = store.impact_plan_file.read_bytes()
    checkpoints_before = tuple(store.list_checkpoints(context.name))
    atomize_calls_before = _AtomizeProvider.calls
    update_calls_before = _UpdateProvider.calls
    print(
        f"PTY · {os.get_terminal_size().columns} COLUMNS × "
        f"{os.get_terminal_size().lines} ROWS",
        flush=True,
    )
    argv = ["impact", "--sessions"]
    if kind == "atomize":
        argv = ["impact", "atomize", "--sessions"]
    exit_code = _invoke(argv)
    print(f"\n{kind.upper()} IMPACT LAUNCHER CLOSED", flush=True)
    print(f"  EXIT · {exit_code}")
    print(f"  CURRENT · {store.current_context_name()}")
    print(f"  SELECTED ANALYSIS UID · {analysis.uid}")
    print(f"  UPDATE UID RETAINED · {store.load_impact_plan().uid == update.uid}")
    print(f"  CONTEXT BYTES UNCHANGED · {context_path.read_bytes() == context_before}")
    print(
        "  CHECKPOINTS UNCHANGED · "
        f"{tuple(store.list_checkpoints(context.name)) == checkpoints_before}"
    )
    print(
        "  WORKBENCH BYTES UNCHANGED · "
        f"{workbench_path.read_bytes() == workbench_before}"
    )
    print(
        "  IMPACT PLAN BYTES UNCHANGED · "
        f"{store.impact_plan_file.read_bytes() == impact_plan_before}"
    )
    print(
        "  PROVIDER CALLS WHILE OPEN · "
        f"{(_AtomizeProvider.calls - atomize_calls_before) + (_UpdateProvider.calls - update_calls_before)}",
        flush=True,
    )


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


def _spawn(kind: str, store_root: Path):
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind, str(store_root)],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _capture_aggregate(store_root: Path) -> None:
    child, recorder = _spawn("aggregate", store_root)
    try:
        child.expect("MEM IMPACT .* SAVED ANALYSES")
        _BASE._settle(child)
        _BASE._snapshot(recorder, "01-aggregate-launcher-entry")

        child.send(DOWN)
        _BASE._settle(child)
        _BASE._snapshot(recorder, "02-atomize-analysis-selected")

        child.send("\r")
        _BASE._settle(child, seconds=0.8)
        _BASE._snapshot(recorder, "03-exact-atomize-impact-opened")

        child.send("q")
        child.expect("AGGREGATE IMPACT LAUNCHER CLOSED")
        child.expect(pexpect.EOF)
        _BASE._snapshot(recorder, "04-aggregate-close-no-write-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_atomize_filter(store_root: Path) -> None:
    child, recorder = _spawn("atomize", store_root)
    try:
        child.expect("MEM IMPACT .* ATOMIZE ANALYSES")
        _BASE._settle(child)
        _BASE._snapshot(recorder, "05-atomize-filtered-launcher")

        child.send("\r")
        _BASE._settle(child, seconds=0.8)
        child.send("q")
        child.expect("ATOMIZE IMPACT LAUNCHER CLOSED")
        child.expect(pexpect.EOF)
        _BASE._snapshot(recorder, "06-filtered-close-no-write-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for suffix in ("*.png", "*.txt", "*.typescript"):
        for path in OUT.glob(suffix):
            path.unlink()
    with tempfile.TemporaryDirectory(prefix="memcommit-impact-launcher-") as directory:
        root = Path(directory)
        _capture_aggregate(root / "aggregate-store")
        _capture_atomize_filter(root / "atomize-store")
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    if "38;2;" not in raw or "48;2;" not in raw:
        raise RuntimeError(
            "PTY stream did not contain foreground and background color."
        )
    for stem in (
        "04-aggregate-close-no-write-verification",
        "06-filtered-close-no-write-verification",
    ):
        verification = (OUT / f"{stem}.txt").read_text(encoding="utf-8")
        for expected in (
            "CONTEXT BYTES UNCHANGED · True",
            "CHECKPOINTS UNCHANGED · True",
            "WORKBENCH BYTES UNCHANGED · True",
            "IMPACT PLAN BYTES UNCHANGED · True",
            "PROVIDER CALLS WHILE OPEN · 0",
        ):
            if expected not in verification:
                raise RuntimeError(f"Missing Impact verification: {expected}")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        _run_child(sys.argv[2], Path(sys.argv[3]))
    else:
        main()
