"""Capture Conflict finding handoff into Resolve in a real 180x52 color PTY."""

from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile

import pexpect


ROOT = Path("/Users/KimMunyeong/Github/memcommit")
OUT = ROOT / "agent-records/docs/screenshots/quality-conflict-resolve-handoff-20260816"
COLUMNS = 180
ROWS = 52

_BASE_PATH = (
    ROOT / "agent-records/docs/screenshots/context-endpoint-memory-preview-20260810/capture.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "quality_handoff_capture_base", _BASE_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS

QUALITY_MARKER = "QUALITY FIND PAYLOAD:\n"
FIT_MARKER = "FIT PROPOSITION PAYLOAD:\n"
VERIFY_MARKER = "VERIFY PAYLOAD:\n"


def _configure_isolated_store(store_root: Path) -> None:
    import memcommit.persistence.store as store_module

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
    from memcommit.core.context import Context, Memory
    from memcommit.persistence.store import MemoryStore

    context = Context(
        uid="10000000-0000-4000-8000-000000000010",
        name="quality/capture",
    )
    context.add(
        Memory(
            uid="20000000-0000-4000-8000-000000000010",
            content="The main entrance opens at 8:00 every day.",
        )
    )
    context.add(
        Memory(
            uid="20000000-0000-4000-8000-000000000020",
            content="The main entrance remains closed until 9:00 every day.",
        )
    )
    context.add(
        Memory(
            uid="20000000-0000-4000-8000-000000000030",
            content="On weekends, the main entrance opens at 9:00.",
        )
    )
    store = MemoryStore()
    store.create_context(context)
    store.set_current(context.name)


class _Provider:
    def __init__(self) -> None:
        self.operations: list[str] = []

    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        assert output_schema is not None
        self.operations.append(operation)
        if operation == "find_conflicts":
            payload = json.loads(prompt.split(QUALITY_MARKER, 1)[1])
            return json.dumps(
                {
                    "findings": [
                        {
                            "pair_id": payload["pairs"][0]["pair_id"],
                            "conflict": "YES",
                            "reason": (
                                "Both Memories govern the same entrance every day "
                                "but require incompatible opening times."
                            ),
                            "question": "Which opening time should govern every day?",
                        }
                    ]
                }
            )
        if operation == "fit_propositions":
            payload = json.loads(prompt.split(FIT_MARKER, 1)[1])
            judgments = []
            for question in payload["questions"]:
                aliases = [
                    item["proposition_id"]
                    for item in (*question["background"], *question["propositions"])
                ]
                initial = question["question_id"] == "resolve-initial"
                judgments.append(
                    {
                        "question_id": question["question_id"],
                        "verdict": "NO" if initial else "YES",
                        "reason": (
                            "The same entrance cannot open at both 8:00 and 9:00 every day."
                            if initial
                            else "The weekend qualification makes the complete schedule compatible."
                        ),
                        "considered_proposition_ids": aliases,
                        "material_proposition_ids": aliases if initial else [],
                        "consistent_reading": "",
                        "inconsistent_reading": "",
                    }
                )
            return json.dumps(
                {"overview": "Complete Fit coverage.", "judgments": judgments}
            )
        if operation == "resolve_candidates":
            return json.dumps(
                {
                    "question": "Choose the smallest grounded schedule repair.",
                    "candidates": [
                        {
                            "summary": "Qualify the later opening time as a weekend rule.",
                            "classification": "EXACT_GROUNDING",
                            "resolution_level": "YES",
                            "rule_ids": [
                                "R04_EXACT_GROUNDING",
                                "R09_PRESERVE_UNAFFECTED",
                                "R11_EXACT_POSTCHECK",
                            ],
                            "issues": [
                                {
                                    "issue_id": "opening-time-scope",
                                    "kind": "TEMPORAL",
                                    "memory_ids": ["m1", "m2", "m3"],
                                    "selected_interpretation": (
                                        "The 9:00 opening is the weekend schedule."
                                    ),
                                    "basis_ids": ["m1", "m2", "m3"],
                                    "assumptions": [],
                                    "reason": (
                                        "The third Memory explicitly grounds the "
                                        "weekend qualification."
                                    ),
                                }
                            ],
                            "effects": [
                                {
                                    "kind": "UPDATE",
                                    "target_id": "m2",
                                    "new_content": (
                                        "The main entrance remains closed until 9:00 on weekends."
                                    ),
                                    "source_ids": ["m1", "m2", "m3"],
                                    "reason": (
                                        "One scope qualification preserves both supplied times."
                                    ),
                                }
                            ],
                        }
                    ],
                }
            )
        if operation == "resolve_candidate_verification":
            payload = json.loads(prompt.split(VERIFY_MARKER, 1)[1])
            return json.dumps(
                {
                    "reviews": [
                        {
                            "candidate_id": candidate["candidate_id"],
                            "grounded": True,
                            "preserves_information": True,
                            "delete_justified": True,
                            "reason": "The update uses only the complete frozen Source.",
                        }
                        for candidate in payload["candidates"]
                    ]
                }
            )
        raise AssertionError(operation)


def _verification(kind: str, provider: _Provider) -> str:
    from memcommit.core.context import Memory
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore()
    context = store.load_direct("quality/capture")
    contents = [
        item.content for item in context.iter_items() if isinstance(item, Memory)
    ]
    checkpoints = store.list_checkpoints(context.name)
    commands = [checkpoint["command"] for checkpoint in checkpoints]
    return (
        f"{kind.upper()} VERIFICATION · MEMORIES {contents!r} · "
        f"CHECKPOINTS {len(checkpoints)} · COMMANDS {commands!r} · "
        f"PROVIDER OPERATIONS {provider.operations!r}"
    )


def _pause(label: str) -> None:
    print(label, flush=True)
    sys.stdin.readline()


def _run_child(kind: str) -> None:
    import click

    import memcommit.adapters.console.commands.find_conflicts.resolve_handoff as handoff_command
    import memcommit.adapters.console.commands.find_conflicts.command as find_command
    import memcommit.application.ops as ops
    from memcommit.adapters.console.entrypoint import app

    with tempfile.TemporaryDirectory(prefix="quality-handoff-capture-") as directory:
        _configure_isolated_store(Path(directory) / ".mem")
        _initialize()
        provider = _Provider()
        find_command.connect_codex_chatgpt_provider = lambda: provider
        handoff_command.connect_semantic_provider = lambda: provider

        if kind == "stale":
            original_handoff = find_command.run_conflict_resolve_handoff

            def stale_handoff(store, *, current_name, handoff):
                changed = store.load_for_update("quality/capture")
                ops.add(changed, "A concurrent holiday schedule arrived.")
                store.save(changed, expected_context_digest=changed._store_digest)
                return original_handoff(
                    store,
                    current_name=current_name,
                    handoff=handoff,
                )

            find_command.run_conflict_resolve_handoff = stale_handoff

        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        exit_code = 0
        try:
            returned = app(
                args=["find-conflicts", "--select"],
                prog_name="mem",
                standalone_mode=False,
            )
        except click.exceptions.Exit as error:
            exit_code = error.exit_code
        else:
            if isinstance(returned, int):
                exit_code = returned
        print(f"COMMAND EXIT · {exit_code}")
        _pause(_verification(kind, provider))


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
        timeout=25,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> None:
    _BASE._snapshot(recorder, stem)


def _enter_finder(child: pexpect.spawn) -> None:
    child.expect("MEM FIND CONFLICTS · SETUP")
    _BASE._settle(child)
    child.send("\t\t\r")
    child.expect("CONFLICTS .* 1/3 PAIRS FLAGGED")
    _BASE._settle(child, seconds=0.8)


def _capture_success() -> None:
    child, recorder = _spawn("success")
    try:
        child.expect("MEM FIND CONFLICTS · SETUP")
        _BASE._settle(child)
        _snapshot(recorder, "01-finder-setup-entry")
        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "02-finder-scope")
        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "03-finder-run-approval")
        child.send("\r")
        child.expect("CONFLICTS .* 1/3 PAIRS FLAGGED")
        _BASE._settle(child, seconds=0.8)
        _snapshot(recorder, "04-conflict-report")
        report = (OUT / "04-conflict-report.txt").read_text(encoding="utf-8")
        assert "2/3 MEMORIES INVOLVED · 1/3 PAIRS FLAGGED" in report
        assert "QUESTION" in report
        assert "SCOPE DIMENSIONS" not in report
        child.send("\r")
        child.expect("RESOLVE NEEDS INPUT")
        _BASE._settle(child, seconds=0.8)
        _snapshot(recorder, "05-resolve-analysis")
        child.send("\x1b[B")
        _BASE._settle(child)
        _snapshot(recorder, "06-apply-row-ready")
        child.send("\r")
        child.expect("SUCCESS VERIFICATION")
        _BASE._settle(child, seconds=0.8)
        _snapshot(recorder, "07-success-receipt-and-store-verification")
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_stale() -> None:
    child, recorder = _spawn("stale")
    try:
        _enter_finder(child)
        child.send("\r")
        child.expect("Find conflicts error")
        child.expect("STALE VERIFICATION")
        _BASE._settle(child)
        _snapshot(recorder, "08-stale-source-rejected")
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for suffix in ("*.png", "*.txt", "*.typescript"):
        for path in OUT.glob(suffix):
            path.unlink()
    _capture_success()
    _capture_stale()
    verification = (OUT / "07-success-receipt-and-store-verification.txt").read_text(
        encoding="utf-8"
    )
    assert "APPLIED · UPDATE 1 · FIT YES" in verification
    assert "CHECKPOINTS 1" in verification
    assert "COMMANDS ['resolve']" in verification
    stale = (OUT / "08-stale-source-rejected.txt").read_text(encoding="utf-8")
    assert "source no longer matches" in stale
    assert "CHECKPOINTS 0" in stale
    assert "PROVIDER OPERATIONS ['find_conflicts']" in stale
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "PTY 180 52" in raw
    assert "\x1b[" in raw
    assert "38;" in raw
    assert "48;" in raw


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT / "src"))
        _run_child(sys.argv[2])
    else:
        main()
