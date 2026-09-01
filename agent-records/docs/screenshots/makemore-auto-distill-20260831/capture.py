"""Capture bare Context Distill→Makemore Impact in a real 180×52 PTY."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time

import pexpect


ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52

_BASE_PATH = (
    ROOT / "agent-records/docs/screenshots/atomize-memory-selection-20260814/capture.py"
)
_SPEC = importlib.util.spec_from_file_location("makemore_auto_capture_base", _BASE_PATH)
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
    import memcommit.persistence.store as store_module

    store_module.STORE_DIR = root


def _print_terminal() -> None:
    size = os.get_terminal_size()
    print(f"PTY · {size.columns} columns × {size.lines} rows", flush=True)
    if (size.columns, size.lines) != (COLUMNS, ROWS):
        raise RuntimeError("Capture PTY dimensions are not 180×52.")


class _PipelineProvider:
    operations: list[str] = []

    def complete(self, prompt, *, operation, output_schema=None):
        type(self).operations.append(operation)
        time.sleep(1.2)
        if operation == "distill_context":
            payload = json.loads(prompt.split("DISTILL CONTEXT PAYLOAD:\n", 1)[1])
            aliases = [item["memory_id"] for item in payload["source"]["memories"]]
            return json.dumps(
                {
                    "overview": (
                        "The Source supports concise state entries that preserve "
                        "review status and concurrency boundaries."
                    ),
                    "rules": [
                        {
                            "content": (
                                "Record each review state as a concise standalone "
                                "Memory."
                            ),
                            "rationale": (
                                "The repeated reviewed entries establish the concise "
                                "state form."
                            ),
                            "support_memory_ids": [aliases[0], aliases[3]],
                            "boundary_memory_ids": [],
                        },
                        {
                            "content": (
                                "Keep current and concurrent states distinguishable."
                            ),
                            "rationale": (
                                "The remaining Source entries distinguish retained "
                                "and concurrent work."
                            ),
                            "support_memory_ids": [aliases[1]],
                            "boundary_memory_ids": [aliases[2]],
                        },
                    ],
                    "outside_memory_ids": [],
                }
            )
        assert operation == "makemore"
        payload = json.loads(prompt.split("MAKEMORE PAYLOAD:\n", 1)[1])
        assert payload["mode"] == "RULES_TO_CASES"
        assert payload["number"] == 3
        return json.dumps(
            {
                "overview": (
                    "Three new state Memories instantiate both transient Rules "
                    "without claiming verification."
                ),
                "cases": [
                    {
                        "proposition": "queued for review",
                        "expected": "Retain a concise pending-review state.",
                        "rationale": "This adds a distinct review lifecycle member.",
                        "case_role": "FIT",
                        "rule_checks": [
                            {
                                "source_rule_index": 1,
                                "evidence": "APPLIES: the state is concise and standalone.",
                            },
                            {
                                "source_rule_index": 2,
                                "evidence": "APPLIES: queued remains distinct from current.",
                            },
                        ],
                    },
                    {
                        "proposition": "review blocked by concurrent change",
                        "expected": "Retain the concurrency boundary explicitly.",
                        "rationale": "This adds a bounded concurrent-review member.",
                        "case_role": "BOUNDARY",
                        "rule_checks": [
                            {
                                "source_rule_index": 1,
                                "evidence": "APPLIES: the state is one standalone Memory.",
                            },
                            {
                                "source_rule_index": 2,
                                "evidence": "APPLIES: the concurrent boundary is explicit.",
                            },
                        ],
                    },
                    {
                        "proposition": "current after review",
                        "expected": "Retain the post-review current state.",
                        "rationale": "This contrasts current-before and current-after review.",
                        "case_role": "CONTRAST",
                        "rule_checks": [
                            {
                                "source_rule_index": 1,
                                "evidence": "APPLIES: the state is concise and standalone.",
                            },
                            {
                                "source_rule_index": 2,
                                "evidence": "APPLIES: post-review current is distinguished.",
                            },
                        ],
                    },
                ],
            }
        )


def _prepare(root: Path):
    import memcommit.application.capabilities.ops as ops
    from memcommit.persistence.store import MemoryStore

    _configure_store(root)
    store = MemoryStore()
    context = ops.init("capture/makemore-auto")
    for content in ("reviewed", "keep current", "concurrent", "reviewed"):
        ops.add(context, content)
    store.create_context(context)
    store.set_current(context.name)
    return store, context


def _child(root: Path) -> None:
    import memcommit.adapters.console.commands.makemore.impact as impact_command
    from memcommit.adapters.console.entrypoint import app
    from memcommit.persistence.store import context_record_digest

    store, context = _prepare(root)
    before = context_record_digest(store.load_direct(context.name))
    _PipelineProvider.operations = []
    impact_command.connect_semantic_provider = _PipelineProvider
    _print_terminal()
    print("$ mem impact makemore --number 3", flush=True)
    app(
        args=["impact", "makemore", "--number", "3"],
        prog_name="mem",
        standalone_mode=False,
    )
    after = store.load_direct(context.name)
    print("\nREAD-ONLY IMPACT VERIFICATION")
    print(f"  CURRENT CONTEXT · {context.name}")
    print(f"  MEMORIES · {len(after.order)}")
    print(f"  DIGEST UNCHANGED · {context_record_digest(after) == before}")
    print(f"  CHECKPOINTS · {len(store.list_checkpoints(context.name))}")
    print(
        "  PROVIDER STAGES · " + " → ".join(_PipelineProvider.operations),
        flush=True,
    )


def _spawn(root: Path):
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", str(root)],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=30,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _capture(root: Path) -> None:
    child, recorder = _spawn(root)
    try:
        child.expect("DISTILLING SOURCE RULES")
        _BASE._settle(child, seconds=0.25)
        _BASE._snapshot(recorder, "01-distilling-source-rules")

        child.expect("GENERATING CASES")
        _BASE._settle(child, seconds=0.25)
        _BASE._snapshot(recorder, "02-generating-cases")

        child.expect("Enter inspect")
        _BASE._settle(child, seconds=0.4)
        _BASE._snapshot(recorder, "03-impact-entry-transient-rules")

        child.send("\t")
        _BASE._settle(child, seconds=0.3)
        _BASE._snapshot(recorder, "04-proposed-cases-focused")

        child.send("\x1b[B")
        _BASE._settle(child, seconds=0.3)
        child.send("\r")
        _BASE._settle(child, seconds=0.3)
        _BASE._snapshot(recorder, "05-first-case-detail")

        child.send("q")
        child.expect("READ-ONLY IMPACT VERIFICATION")
        child.expect("PROVIDER STAGES")
        child.expect(pexpect.EOF)
        _BASE._snapshot(recorder, "06-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for suffix in ("*.typescript", "*.txt", "*.png"):
        for path in OUT.glob(suffix):
            path.unlink()
    with tempfile.TemporaryDirectory(prefix="makemore-auto-distill-") as directory:
        _capture(Path(directory) / "store")
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("PTY streams did not contain expected true-color ANSI.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        _child(Path(sys.argv[2]))
    elif len(sys.argv) == 1:
        main()
    else:
        raise SystemExit("usage: capture.py [--child STORE_ROOT]")
