"""Capture complete compact Distill/Elaborate Rule rows in real 180x52 PTYs."""

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
LONG_RULE = (
    "When generating a synthetic ticker, remove a leading article, discard "
    "legal-form suffixes, preserve meaningful numeric tokens, and keep the "
    "exact security-class qualifier before applying the reviewed mapping; "
    "this final qualification remains part of the complete Rule and must "
    "remain visible without shortening the Rule."
)

_BASE_PATH = ROOT / "agent-records/docs/screenshots/atomize-memory-selection-20260814/capture.py"
_SPEC = importlib.util.spec_from_file_location("semantic_rule_row_capture_base", _BASE_PATH)
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
            "PYTHONPATH": str(ROOT / "src"),
        }
    )
    return environment


def _configure_store(root: Path) -> None:
    import memcommit.store as store_module

    store_module.STORE_DIR = root


def _print_terminal() -> None:
    size = os.get_terminal_size()
    print(f"PTY · {size.columns} columns × {size.lines} rows", flush=True)
    if (size.columns, size.lines) != (COLUMNS, ROWS):
        raise RuntimeError("Capture PTY dimensions are not 180×52.")


class _DistillProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "distill_context"
        time.sleep(0.8)
        payload = json.loads(prompt.split("DISTILL CONTEXT PAYLOAD:\n", 1)[1])
        aliases = [item["memory_id"] for item in payload["source"]["memories"]]
        return json.dumps(
            {
                "overview": "The complete evidence supports one qualified ticker Rule.",
                "rules": [
                    {
                        "content": LONG_RULE,
                        "rationale": (
                            "The final security-class qualification is part of the "
                            "evidence-supported boundary and cannot be dropped."
                        ),
                        "support_memory_ids": aliases[:1],
                        "boundary_memory_ids": aliases[1:2],
                    }
                ],
                "outside_memory_ids": [],
            }
        )


class _ElaborateProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "elaborate"
        time.sleep(0.8)
        payload = json.loads(prompt.split("ELABORATE PAYLOAD:\n", 1)[1])
        assert payload["mode"] == "GOAL_TO_RULES"
        return json.dumps(
            {
                "overview": "One complete unverified Rule elaborates the Goal.",
                "rules": [
                    {
                        "content": LONG_RULE,
                        "rationale": (
                            "This is an unverified operational hypothesis whose "
                            "final qualification must remain inspectable."
                        ),
                    }
                ],
            }
        )


def _prepare(root: Path, operation: str):
    import memcommit.application.ops as ops
    from memcommit.store import MemoryStore

    _configure_store(root)
    store = MemoryStore()
    source = ops.init(f"capture/{operation}-source")
    target = ops.init(f"capture/{operation}-target")
    values = (
        (
            "Apple Inc. Class C trades under the reviewed symbol.",
            "Omitting the share class can identify a different security.",
        )
        if operation == "distill"
        else ("Generate a qualified synthetic ticker mapping Rule.",)
    )
    for value in values:
        ops.add(source, value)
    store.create_context(source)
    store.create_context(target)
    store.set_current(target.name)
    return store, source, target


def _child(operation: str, root: Path) -> None:
    from memcommit.cli import app
    from memcommit.store import context_record_digest

    store, source, target = _prepare(root, operation)
    import memcommit.commands.impact.process_local as impact_command

    impact_command.connect_semantic_provider = (
        _DistillProvider if operation == "distill" else _ElaborateProvider
    )
    before_source = context_record_digest(store.load_direct(source.name))
    before_target = context_record_digest(store.load_direct(target.name))
    argv = ["impact", operation, "--from", source.name, "--to", target.name]
    if operation == "elaborate":
        argv.extend(("--as", "goal"))
    _print_terminal()
    print("$ mem " + " ".join(argv), flush=True)
    app(args=argv, prog_name="mem", standalone_mode=False)
    print("\nREAD-ONLY IMPACT VERIFICATION")
    print(
        "  SOURCE DIGEST UNCHANGED · "
        f"{context_record_digest(store.load_direct(source.name)) == before_source}"
    )
    print(
        "  TARGET DIGEST UNCHANGED · "
        f"{context_record_digest(store.load_direct(target.name)) == before_target}"
    )
    print(f"  TARGET CHECKPOINTS · {len(store.list_checkpoints(target.name))}")
    print("  COMPLETE RULE TAIL · without shortening the Rule.", flush=True)


def _spawn(operation: str, root: Path):
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", operation, str(root)],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=30,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _capture(operation: str, root: Path, number: int) -> None:
    child, recorder = _spawn(operation, root)
    try:
        child.expect("IMPACT .* " + operation.upper())
        _BASE._settle(child, seconds=0.25)
        _BASE._snapshot(recorder, f"{number:02d}-{operation}-impact-entry")
        child.expect("PROPOSED RULES")
        child.expect("without shortening the Rule")
        _BASE._settle(child, seconds=0.45)
        _BASE._snapshot(recorder, f"{number + 1:02d}-{operation}-complete-rule-row")
        child.send("\t\x1b[B\r")
        child.expect("REVIEW DETAIL")
        child.expect(
            "EVIDENCE BOUNDARY"
            if operation == "distill"
            else "WHY THIS NEEDS REVIEW"
        )
        _BASE._settle(child, seconds=0.35)
        _BASE._snapshot(recorder, f"{number + 2:02d}-{operation}-rule-detail")
        child.send("q")
        child.expect("READ-ONLY IMPACT VERIFICATION")
        child.expect("TARGET CHECKPOINTS .* 0")
        child.expect("COMPLETE RULE TAIL .* without shortening the Rule")
        child.expect(pexpect.EOF)
        _BASE._snapshot(recorder, f"{number + 3:02d}-{operation}-close-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="semantic-rule-rows-") as directory:
        root = Path(directory)
        _capture("distill", root / "distill", 1)
        _capture("elaborate", root / "elaborate", 5)
    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("PTY streams did not contain expected true-color ANSI.")
    for path in OUT.glob("*-complete-rule-row.txt"):
        text = path.read_text(encoding="utf-8")
        if "without shortening the Rule." not in text:
            raise RuntimeError(f"Complete Rule tail is absent from {path.name}.")
        if "Rule.…" in text or "Rule…" in text:
            raise RuntimeError(f"Rule content was shortened in {path.name}.")
        if "IMPACT · DISTILL ADD" in text or "IMPACT · ELABORATE ADD" in text:
            raise RuntimeError(f"Duplicate Impact ledger remains in {path.name}.")
        if "[ADD]" in text:
            raise RuntimeError(f"Duplicate Add row remains in {path.name}.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        _child(sys.argv[2], Path(sys.argv[3]))
    elif len(sys.argv) == 1:
        main()
    else:
        raise SystemExit("usage: capture.py [--child OPERATION STORE_ROOT]")
