"""Capture automatic Resolve paths in a real 180x52 color PTY."""

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
OUT = ROOT / "agent-records/screenshots/mem-resolve-automatic-interpretation-20260820"
COLUMNS = 180
ROWS = 52

_LEGACY_PATH = ROOT / "agent-records/screenshots/mem-resolve-fit-repair-20260815/capture.py"
_SPEC = importlib.util.spec_from_file_location("resolve_capture_legacy", _LEGACY_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_LEGACY = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_LEGACY)
_LEGACY._BASE.OUT = OUT
_LEGACY._BASE.COLUMNS = COLUMNS
_LEGACY._BASE.ROWS = ROWS

FIT_MARKER = "FIT PROPOSITION PAYLOAD:\n"
VERIFY_MARKER = "VERIFY PAYLOAD:\n"


class _Provider:
    def __init__(self, *, kind: str) -> None:
        self.kind = kind

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
                verdict = "YES" if self.kind == "already-fit" or not initial else "NO"
                judgments.append(
                    {
                        "question_id": question["question_id"],
                        "verdict": verdict,
                        "reason": (
                            "The complete revised schedule is compatible."
                            if verdict == "YES"
                            else "The unqualified times need one explicit scope interpretation."
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
            assumed = self.kind == "assumed"
            return json.dumps(
                {
                    "question": "No clarification needed.",
                    "candidates": [
                        {
                            "summary": "Use one explicit schedule interpretation.",
                            "classification": (
                                "MINIMUM_REPAIR" if assumed else "EXACT_GROUNDING"
                            ),
                            "resolution_level": "MAY" if assumed else "YES",
                            "rule_ids": (
                                ["R06_NO_INVENTED_DISCRIMINATOR"]
                                if assumed
                                else [
                                    "R01_WHOLE_FRAME",
                                    "R02_DEFAULT_REMOVE_NO",
                                    "R04_EXACT_GROUNDING",
                                    "R09_PRESERVE_UNAFFECTED",
                                    "R11_EXACT_POSTCHECK",
                                ]
                            ),
                            "issues": [
                                {
                                    "issue_id": "opening-time-scope",
                                    "kind": "SCOPE",
                                    "memory_ids": (
                                        ["m1", "m2"] if assumed else ["m1", "m2", "m3"]
                                    ),
                                    "selected_interpretation": (
                                        "Eight is the weekday time and nine is the weekend time."
                                    ),
                                    "basis_ids": (
                                        ["m1", "m2"] if assumed else ["m1", "m2", "m3"]
                                    ),
                                    "assumptions": (
                                        ["The 9 o'clock schedule applies on weekends."]
                                        if assumed
                                        else []
                                    ),
                                    "reason": (
                                        "The scope interpretation preserves both opening times."
                                    ),
                                }
                            ],
                            "effects": (
                                [
                                    {
                                        "kind": "UPDATE",
                                        "target_id": "m2",
                                        "new_content": "The office opens at 9 on weekends.",
                                        "source_ids": ["m1", "m2"],
                                        "reason": "The assumed weekend scope separates the times.",
                                    }
                                ]
                                if assumed
                                else [
                                    {
                                        "kind": "UPDATE",
                                        "target_id": "m1",
                                        "new_content": "The office opens at 8 on weekdays.",
                                        "source_ids": ["m1", "m3"],
                                        "reason": "The supplied schedule grounds weekdays.",
                                    },
                                    {
                                        "kind": "UPDATE",
                                        "target_id": "m2",
                                        "new_content": "The office opens at 9 on weekends.",
                                        "source_ids": ["m2", "m3"],
                                        "reason": "The supplied schedule grounds weekends.",
                                    },
                                ]
                            ),
                        }
                    ],
                }
            )
        if operation == "resolve_candidate_verification":
            payload = json.loads(prompt.split(VERIFY_MARKER, 1)[1])
            grounded = self.kind != "assumed"
            return json.dumps(
                {
                    "reviews": [
                        {
                            "candidate_id": candidate["candidate_id"],
                            "grounded": grounded,
                            "preserves_information": True,
                            "delete_justified": True,
                            "reason": (
                                "The complete frame grounds the interpretation."
                                if grounded
                                else "The weekend scope is reasonable but unstated."
                            ),
                        }
                        for candidate in payload["candidates"]
                    ]
                }
            )
        raise AssertionError(operation)


def _verification(kind: str) -> str:
    from memcommit.context import Memory
    from memcommit.store import MemoryStore

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


def _run_child(kind: str) -> None:
    import click
    import typer

    import memcommit.commands.resolve.command as resolve_command
    from memcommit.commands.resolve.command import cmd as resolve_cmd
    from memcommit.context import Context, Memory
    from memcommit.store import MemoryStore

    with tempfile.TemporaryDirectory(prefix="mem-resolve-auto-capture-") as directory:
        _LEGACY._configure_isolated_store(Path(directory) / ".mem")
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
        if kind != "assumed":
            context.add(
                Memory(
                    uid="20000000-0000-4000-8000-000000000003",
                    content=(
                        "The weekday opening time is 8 and the weekend opening time is 9."
                    ),
                )
            )
        store = MemoryStore()
        store.create_context(context)
        store.set_current(context.name)
        resolve_command.connect_semantic_provider = lambda: _Provider(kind=kind)
        if kind == "stale":
            import memcommit.ops as ops
            from memcommit.resolve_runtime import MemoryStoreResolvePort

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
        exit_code = 0
        try:
            returned = app(
                args=["resolve", "--context", "resolve/capture", "--tui"],
                prog_name="mem",
                standalone_mode=False,
            )
        except click.exceptions.Exit as error:
            exit_code = error.exit_code
        else:
            if isinstance(returned, int):
                exit_code = returned
        print(f"COMMAND EXIT · {exit_code}")
        print("READY FOR VERIFICATION", flush=True)
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
    recorder = _LEGACY._BASE._StreamRecorder()
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
    _LEGACY._BASE._snapshot(recorder, stem)


def _capture_apply() -> None:
    child, recorder = _spawn("apply")
    try:
        child.expect("RESOLVE APPLIED")
        child.expect("READY FOR VERIFICATION")
        _LEGACY._BASE._settle(child)
        _snapshot(recorder, "01-automatic-success-receipt")
        child.send("\r")
        child.expect("APPLY VERIFICATION")
        _snapshot(recorder, "02-store-verification")
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_read_only(kind: str, screen_stem: str, verify_stem: str) -> None:
    child, recorder = _spawn(kind)
    try:
        child.expect("READ-ONLY OUTCOME")
        _LEGACY._BASE._settle(child)
        _snapshot(recorder, screen_stem)
        child.send("q")
        child.expect("READY FOR VERIFICATION")
        child.send("\r")
        child.expect(f"{kind.upper()} VERIFICATION")
        _snapshot(recorder, verify_stem)
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_stale() -> None:
    child, recorder = _spawn("stale")
    try:
        child.expect("Resolve error")
        child.expect("READY FOR VERIFICATION")
        _LEGACY._BASE._settle(child)
        _snapshot(recorder, "07-stale-automatic-apply-failure")
        child.send("\r")
        child.expect("STALE VERIFICATION")
        _snapshot(recorder, "08-stale-verification")
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    # Remove only reproducible capture outputs from this focused directory so
    # renamed states cannot leave stale evidence beside the current sequence.
    for suffix in ("*.png", "*.txt", "*.typescript"):
        for path in OUT.glob(suffix):
            path.unlink()
    _capture_apply()
    _capture_read_only(
        "assumed",
        "03-assumed-working-view",
        "04-assumed-no-checkpoint",
    )
    _capture_read_only(
        "already-fit",
        "05-already-fit-outcome",
        "06-already-fit-no-checkpoint",
    )
    _capture_stale()
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
