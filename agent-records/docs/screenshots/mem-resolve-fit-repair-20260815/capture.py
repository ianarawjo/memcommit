"""Capture public Resolve review paths in a real 180x52 color PTY."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
from pathlib import Path

import pexpect


ROOT = Path("/Users/KimMunyeong/Github/memcommit")
OUT = ROOT / "agent-records/docs/screenshots/mem-resolve-fit-repair-20260815"
COLUMNS = 180
ROWS = 52

_BASE_PATH = ROOT / "agent-records/docs/screenshots/context-endpoint-memory-preview-20260810/capture.py"
_SPEC = importlib.util.spec_from_file_location("resolve_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS

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
        "GROUND_SESSIONS_DIR": store_root / "ground-sessions",
        "MELD_SESSIONS_DIR": store_root / "meld-sessions",
    }
    for name, value in values.items():
        setattr(store_module, name, value)


def _initialize() -> None:
    from memcommit.core.context import Context, Memory
    from memcommit.persistence.store import MemoryStore

    context = Context(
        uid="10000000-0000-4000-8000-000000000001",
        name="resolve/capture",
    )
    context.add(
        Memory(
            uid="20000000-0000-4000-8000-000000000001",
            content="The office opens at 8.",
        )
    )
    context.add(
        Memory(
            uid="20000000-0000-4000-8000-000000000002",
            content="The office opens at 9.",
        )
    )
    store = MemoryStore()
    store.create_context(context)
    store.set_current(context.name)


class _Provider:
    def __init__(self, *, already_fit: bool = False) -> None:
        self.already_fit = already_fit

    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        assert output_schema is not None
        if operation == "fit_propositions":
            payload = json.loads(prompt.split(FIT_MARKER, 1)[1])
            judgments = []
            for question in payload["questions"]:
                aliases = [
                    item["proposition_id"]
                    for item in (*question["background"], *question["propositions"])
                ]
                initial = question["question_id"] == "resolve-initial"
                verdict = "YES" if self.already_fit or not initial else "NO"
                judgments.append(
                    {
                        "question_id": question["question_id"],
                        "verdict": verdict,
                        "reason": (
                            "The complete revised schedule is compatible."
                            if verdict == "YES"
                            else "The same office cannot ordinarily open at both times."
                        ),
                        "considered_proposition_ids": aliases,
                        "material_proposition_ids": aliases if verdict != "YES" else [],
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
                            "summary": "Qualify the second time as the weekend schedule.",
                            "effects": [
                                {
                                    "kind": "UPDATE",
                                    "target_id": "m2",
                                    "new_content": "The office opens at 9 on weekends.",
                                    "source_ids": ["m1", "m2"],
                                    "reason": "The added scope preserves both times.",
                                }
                            ],
                        },
                        {
                            "summary": "Add an explicit day-dependent schedule statement.",
                            "effects": [
                                {
                                    "kind": "CREATE",
                                    "target_id": "NEW",
                                    "new_content": "The opening time depends on the day.",
                                    "source_ids": ["m1", "m2"],
                                    "reason": "Both supplied times support a scoped schedule.",
                                }
                            ],
                        },
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
                            "reason": "Only the complete supplied frame is used.",
                        }
                        for candidate in payload["candidates"]
                    ]
                }
            )
        raise AssertionError(operation)


def _verification(kind: str) -> str:
    from memcommit.core.context import Memory
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore()
    context = store.load_direct("resolve/capture")
    contents = [
        item.content for item in context.iter_items() if isinstance(item, Memory)
    ]
    checkpoints = store.list_checkpoints(context.name)
    commands = [checkpoint["command"] for checkpoint in checkpoints]
    return (
        f"{kind.upper()} VERIFICATION · MEMORIES {contents!r} · "
        f"CHECKPOINTS {len(checkpoints)} · COMMANDS {commands!r}"
    )


def _pause(label: str) -> None:
    print(label, flush=True)
    sys.stdin.readline()


def _run_child(kind: str) -> None:
    import click
    import typer

    import memcommit.adapters.console.commands.resolve.command as resolve_command
    from memcommit.adapters.console.commands.resolve.command import cmd as resolve_cmd

    with tempfile.TemporaryDirectory(prefix="mem-resolve-capture-") as directory:
        _configure_isolated_store(Path(directory) / ".mem")
        _initialize()
        resolve_command.connect_semantic_provider = lambda: _Provider(
            already_fit=kind == "already-fit"
        )
        if kind == "stale":
            import memcommit.application.capabilities.ops as ops
            from memcommit.application.operations.resolve.runtime import MemoryStoreResolvePort

            original_apply = MemoryStoreResolvePort.apply

            def stale_apply(self, frame, candidate):
                changed = self.active_store.load_for_update(frame.context_name)
                ops.add(changed, "A concurrent schedule note arrived.")
                self.active_store.save(
                    changed,
                    expected_context_digest=changed._store_digest,
                )
                return original_apply(self, frame, candidate)

            MemoryStoreResolvePort.apply = stale_apply

        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        app = typer.Typer()

        @app.callback()
        def capture_root() -> None:
            """Keep Typer in command-group mode for the focused adapter."""

        app.command("resolve")(resolve_cmd)
        args = [
            "resolve",
            "--context",
            "resolve/capture",
            "--allow-create",
            "--tui",
        ]
        exit_code = 0
        try:
            returned = app(args=args, prog_name="mem", standalone_mode=False)
        except click.exceptions.Exit as error:
            exit_code = error.exit_code
        else:
            if isinstance(returned, int):
                exit_code = returned
        print(f"COMMAND EXIT · {exit_code}")
        _pause(_verification(kind))


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


def _snapshot(recorder: io.StringIO, stem: str) -> None:
    _BASE._snapshot(recorder, stem)


def _open_and_select(child: pexpect.spawn) -> None:
    child.expect("RESOLUTION SESSION")
    _BASE._settle(child)
    child.send("\t\r")
    _BASE._settle(child)
    child.send("\t")
    _BASE._settle(child)
    child.send("\r")
    _BASE._settle(child)


def _capture_apply() -> None:
    child, recorder = _spawn("apply")
    try:
        child.expect("RESOLUTION SESSION")
        _BASE._settle(child)
        _snapshot(recorder, "01-complete-analysis-entry")
        child.send("\t\r")
        _BASE._settle(child)
        _snapshot(recorder, "02-verified-candidate-detail")
        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "03-incomparable-candidate-responses")
        child.send("\r")
        _BASE._settle(child)
        _snapshot(recorder, "04-update-candidate-selected")
        child.send("\t\t")
        _BASE._settle(child)
        _snapshot(recorder, "05-ready-for-exact-review")
        child.send("\r")
        _BASE._settle(child)
        _snapshot(recorder, "06-exact-command-review")
        child.send("\r")
        _BASE._settle(child, seconds=0.8)
        _snapshot(recorder, "07-success-receipt")
        assert "STATUS · SUCCESS" in (
            OUT / "07-success-receipt.txt"
        ).read_text(encoding="utf-8")
        child.send("\r")
        child.expect("APPLY VERIFICATION")
        _snapshot(recorder, "08-read-only-store-verification")
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_already_fit() -> None:
    child, recorder = _spawn("already-fit")
    try:
        child.expect("READ-ONLY OUTCOME")
        _BASE._settle(child)
        _snapshot(recorder, "09-already-fit-read-only-outcome")
        child.send("q")
        child.expect("ALREADY-FIT VERIFICATION")
        _snapshot(recorder, "10-already-fit-no-checkpoint")
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_cancel() -> None:
    child, recorder = _spawn("cancel")
    try:
        child.expect("RESOLUTION SESSION")
        child.send("q")
        child.expect("CANCEL VERIFICATION")
        _snapshot(recorder, "11-cancel-no-checkpoint")
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_stale() -> None:
    child, recorder = _spawn("stale")
    try:
        _open_and_select(child)
        child.send("\t\t\r\r")
        child.expect("Apply failed")
        _BASE._settle(child)
        _snapshot(recorder, "12-stale-apply-failure")
        child.send("q")
        child.expect("STALE VERIFICATION")
        _snapshot(recorder, "13-stale-no-resolve-checkpoint")
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _capture_apply()
    _capture_already_fit()
    _capture_cancel()
    _capture_stale()
    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
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
