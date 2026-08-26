"""Capture registered process-local Impact routes through real 180x52 PTYs."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52

_BASE_PATH = ROOT / "docs/screenshots/atomize-memory-selection-20260814/capture.py"
_SPEC = importlib.util.spec_from_file_location("impact_registry_capture_base", _BASE_PATH)
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
            "PROMPT_TOOLKIT_NO_CPR": "1",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
            "PYTHONPATH": str(ROOT),
        }
    )
    return environment


def _configure_store(root: Path) -> None:
    import memcommit.store as store_module

    store_module.STORE_DIR = root
    store_module.CONTEXTS_DIR = root / "contexts"
    store_module.STATE_FILE = root / "state.json"


def _print_terminal() -> None:
    size = os.get_terminal_size()
    print(f"PTY · {size.columns} columns × {size.lines} rows", flush=True)
    if (size.columns, size.lines) != (COLUMNS, ROWS):
        raise RuntimeError("Capture PTY dimensions are not 180×52.")


class _ForgetProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "forget"
        time.sleep(1.0)
        messages = json.loads(prompt.split("FORGET CHAT MESSAGES:\n", 1)[1])
        payload = json.loads(
            messages[1]["content"].split("FORGET PAYLOAD:\n", 1)[1]
        )
        decisions = (
            (
                "DELETE",
                "",
                "The instruction explicitly covers the obsolete location.",
            ),
            (
                "KEEP",
                payload["source"]["memories"][1]["content"],
                "Current accessibility guidance remains useful.",
            ),
        )
        return json.dumps(
            {
                "overview": "Remove the obsolete location and retain current access guidance.",
                "candidates": [
                    {
                        "source_memory_id": source["item_id"],
                        "decision": decision,
                        "proposed_content": content,
                        "rationale": rationale,
                        "criterion_item_ids": ["k1"],
                    }
                    for source, (decision, content, rationale) in zip(
                        payload["source"]["memories"], decisions, strict=True
                    )
                ],
            }
        )


class _DistillProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "distill_context"
        time.sleep(1.0)
        payload = json.loads(prompt.split("DISTILL CONTEXT PAYLOAD:\n", 1)[1])
        aliases = [
            memory["memory_id"] for memory in payload["source"]["memories"]
        ]
        return json.dumps(
            {
                "overview": "The examples support one bounded conversation preference.",
                "rules": [
                    {
                        "content": "Prefer a quiet setting when conversation is the purpose.",
                        "rationale": "The quiet example supports the condition; the noisy example bounds it.",
                        "support_memory_ids": aliases[:1],
                        "boundary_memory_ids": aliases[1:2],
                    }
                ],
                "outside_memory_ids": aliases[2:],
            }
        )


class _ResolveProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        time.sleep(0.4)
        if operation == "fit_propositions":
            payload = json.loads(prompt.split("FIT PROPOSITION PAYLOAD:\n", 1)[1])
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
                            "The original times conflict."
                            if initial
                            else "The revised complete frame is compatible."
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
                    "question": "Which schedule scope should be authoritative?",
                    "candidates": [
                        {
                            "summary": "Scope the second schedule to weekends.",
                            "effects": [
                                {
                                    "kind": "UPDATE",
                                    "target_id": "m2",
                                    "new_content": "The office opens at 9 on weekends.",
                                    "source_ids": ["m1", "m2"],
                                    "reason": "The weekend scope preserves both schedule claims.",
                                }
                            ],
                        }
                    ],
                }
            )
        if operation == "resolve_candidate_verification":
            payload = json.loads(prompt.split("VERIFY PAYLOAD:\n", 1)[1])
            return json.dumps(
                {
                    "reviews": [
                        {
                            "candidate_id": candidate["candidate_id"],
                            "grounded": True,
                            "preserves_information": True,
                            "delete_justified": True,
                            "reason": "The candidate uses only cited Source content.",
                        }
                        for candidate in payload["candidates"]
                    ]
                }
            )
        raise AssertionError(operation)


def _prepare(kind: str):
    import memcommit.ops as ops
    from memcommit.store import MemoryStore, context_record_digest

    store = MemoryStore()
    context = ops.init(f"capture/impact-{kind}")
    if kind == "forget":
        values = (
            "The desk used to be beside the west entrance.",
            "Step-free access remains at the north entrance.",
        )
    elif kind == "distill":
        values = (
            "A quiet setting supported a long conversation.",
            "A noisy setting made conversation difficult.",
        )
    else:
        values = (
            "The office opens at 8.",
            "The office opens at 9.",
        )
    for value in values:
        ops.add(context, value)
    store.create_context(context)
    store.set_current(context.name)
    return store, context, context_record_digest(context)


def _child(kind: str, root: Path) -> None:
    import memcommit.commands.impact.process_local as process_local
    from memcommit.cli import app
    from memcommit.store import context_record_digest

    _configure_store(root)
    _print_terminal()
    store, context, before = _prepare(kind)
    checkpoint_count = len(store.list_checkpoints(context.name))
    if kind == "forget":
        process_local.connect_forget_provider = _ForgetProvider
        argv = [
            "impact",
            "forget",
            "Forget the old desk location.",
            "--context",
            context.name,
        ]
    elif kind == "distill":
        process_local.connect_semantic_provider = _DistillProvider
        argv = [
            "impact",
            "distill",
            context.name,
            "--save-as",
            "capture/impact-distill-result",
        ]
    else:
        provider = _ResolveProvider()
        process_local.connect_semantic_provider = lambda: provider
        argv = ["impact", "resolve", "--context", context.name]
    print("$ mem " + " ".join(argv), flush=True)
    app(args=argv, prog_name="mem", standalone_mode=False)
    after = store.load_direct(context.name)
    print("\nREAD-ONLY ROUTE VERIFICATION")
    print(f"  OPERATION · {kind.upper()}")
    print(f"  SOURCE DIGEST UNCHANGED · {context_record_digest(after) == before}")
    print(
        "  CHECKPOINT COUNT UNCHANGED · "
        f"{len(store.list_checkpoints(context.name)) == checkpoint_count}"
    )
    if kind == "distill":
        print(
            "  RESULT NOT CREATED · "
            f"{not store.context_exists('capture/impact-distill-result')}"
        )
    print("  APPLY HANDOFF · ABSENT", flush=True)


def _spawn(kind: str, root: Path):
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind, str(root)],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _settle(child: pexpect.spawn, seconds: float = 0.35) -> None:
    _BASE._settle(child, seconds=seconds)


def _capture(kind: str, root: Path, number: int, report_title: str) -> None:
    child, recorder = _spawn(kind, root)
    try:
        child.expect(f"IMPACT .* {kind.upper()}")
        _settle(child, 0.2)
        _BASE._snapshot(recorder, f"{number:02d}-{kind}-analysis")

        child.expect(report_title)
        _settle(child, 0.5)
        _BASE._snapshot(recorder, f"{number + 1:02d}-{kind}-impact")

        child.send("q")
        child.expect("READ-ONLY ROUTE VERIFICATION")
        child.expect("APPLY HANDOFF .* ABSENT")
        child.expect(pexpect.EOF)
        _BASE._snapshot(recorder, f"{number + 2:02d}-{kind}-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="impact-process-local-capture-") as directory:
        root = Path(directory)
        _capture("forget", root / "forget", 1, "IMPACT .* FORGET .* SAME SOURCE")
        _capture(
            "distill",
            root / "distill",
            4,
            "IMPACT .* DISTILL RESULT .* SOURCE UNCHANGED",
        )
        _capture("resolve", root / "resolve", 7, "IMPACT .* RESOLVE .* SAME SOURCE")
    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("PTY streams did not contain expected true-color ANSI.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        _child(sys.argv[2], Path(sys.argv[3]))
    elif len(sys.argv) == 1:
        main()
    else:
        raise SystemExit("usage: capture.py [--child KIND STORE_ROOT]")
