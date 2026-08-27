"""Capture directional Distill/Elaborate Add and Impact in real 180x52 PTYs."""

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

_BASE_PATH = ROOT / "agent-records/docs/screenshots/atomize-memory-selection-20260814/capture.py"
_SPEC = importlib.util.spec_from_file_location("semantic_add_capture_base", _BASE_PATH)
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


class _DistillProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "distill_context"
        time.sleep(0.8)
        payload = json.loads(prompt.split("DISTILL CONTEXT PAYLOAD:\n", 1)[1])
        aliases = [item["memory_id"] for item in payload["source"]["memories"]]
        return json.dumps(
            {
                "overview": "The examples support one bounded ticker mapping Rule.",
                "rules": [
                    {
                        "content": "Use AAPL for Apple and MSFT for Microsoft.",
                        "rationale": "Both mappings are directly supported.",
                        "support_memory_ids": aliases,
                        "boundary_memory_ids": [],
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
        assert payload["mode"] == "RULES_TO_CASES"
        return json.dumps(
            {
                "overview": "A fit and boundary make the ticker Rule concrete.",
                "cases": [
                    {
                        "proposition": "Identifying Apple by ticker returns AAPL.",
                        "expected": "AAPL",
                        "rationale": "This is a fitting ticker Case.",
                        "case_role": "FIT",
                        "rule_checks": [
                            {
                                "source_rule_index": 1,
                                "evidence": "The Case uses the complete ticker Rule.",
                            }
                        ],
                    },
                    {
                        "proposition": "Mentioning Apple without asking for its ticker.",
                        "expected": "Do not infer a lookup request.",
                        "rationale": "This bounds when the Rule applies.",
                        "case_role": "BOUNDARY",
                        "rule_checks": [
                            {
                                "source_rule_index": 1,
                                "evidence": "The Case preserves the ticker Rule boundary.",
                            }
                        ],
                    },
                ],
            }
        )


def _prepare(root: Path, operation: str):
    import memcommit.application.ops as ops
    from memcommit.persistence.store import MemoryStore

    _configure_store(root)
    store = MemoryStore()
    source = ops.init(f"capture/{operation}-source")
    target = ops.init(f"capture/{operation}-target")
    values = (
        (
            "Apple Inc. trades on Nasdaq under AAPL.",
            "Microsoft Corporation trades on Nasdaq under MSFT.",
        )
        if operation == "distill"
        else ("Use AAPL for Apple and MSFT for Microsoft.",)
    )
    for value in values:
        ops.add(source, value)
    store.create_context(source)
    store.create_context(target)
    store.set_current(target.name)
    return store, source, target


def _child(kind: str, root: Path) -> None:
    from memcommit.adapters.console.entrypoint import app
    from memcommit.persistence.store import context_record_digest

    operation, route = kind.split("-", 1)
    store, source, target = _prepare(root, operation)
    if operation == "distill":
        import memcommit.adapters.console.commands.distill.command as add_command
        import memcommit.adapters.console.commands.impact.process_local as impact_command

        provider = _DistillProvider
    else:
        import memcommit.adapters.console.commands.elaborate.command as add_command
        import memcommit.adapters.console.commands.impact.process_local as impact_command

        provider = _ElaborateProvider
    add_command.connect_semantic_provider = provider
    impact_command.connect_semantic_provider = provider
    _print_terminal()
    before_source = context_record_digest(store.load_direct(source.name))
    before_target = context_record_digest(store.load_direct(target.name))
    argv = [route, operation, "--from", source.name, "--to", target.name]
    if route == "add":
        argv = [operation, "--from", source.name, "--to", target.name]
    print("$ mem " + " ".join(argv), flush=True)
    app(args=argv, prog_name="mem", standalone_mode=False)
    if route == "add":
        print("CAPTURE GATE · PRESS V FOR RESULT VERIFICATION", flush=True)
        if sys.stdin.read(1).lower() != "v":
            raise RuntimeError("Result verification gate was not acknowledged.")
        after = store.load_direct(target.name)
        print("\nDURABLE RESULT VERIFICATION")
        print(f"  SOURCE · {source.name}")
        print(f"  TARGET · {target.name}")
        print(f"  TARGET MEMORIES · {len(after.order)}")
        print(f"  CHECKPOINT COMMAND · {store.list_checkpoints(target.name)[0]['command']}")
        print(
            "  DISTINCT SOURCE UNCHANGED · "
            f"{context_record_digest(store.load_direct(source.name)) == before_source}",
            flush=True,
        )
    else:
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
        timeout=30,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _capture_add(operation: str, root: Path, number: int) -> None:
    child, recorder = _spawn(f"{operation}-add", root)
    try:
        child.expect(operation.upper())
        _BASE._settle(child, seconds=0.3)
        _BASE._snapshot(recorder, f"{number:02d}-{operation}-add-entry")
        child.expect("CAPTURE GATE .* RESULT VERIFICATION")
        _BASE._settle(child, seconds=0.2)
        _BASE._snapshot(recorder, f"{number + 1:02d}-{operation}-add-receipt")
        child.send("v\r")
        child.expect("DURABLE RESULT VERIFICATION")
        child.expect("DISTINCT SOURCE UNCHANGED .* True")
        child.expect(pexpect.EOF)
        _BASE._snapshot(recorder, f"{number + 2:02d}-{operation}-add-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_impact(operation: str, root: Path, number: int) -> None:
    child, recorder = _spawn(f"{operation}-impact", root)
    try:
        child.expect("IMPACT .* " + operation.upper())
        _BASE._settle(child, seconds=0.25)
        _BASE._snapshot(recorder, f"{number:02d}-{operation}-impact-entry")
        # Semantic styling can split the title with ANSI bytes; the shared
        # unstyled footer is the stable final-screen readiness boundary.
        child.expect("Enter inspect")
        _BASE._settle(child, seconds=0.4)
        _BASE._snapshot(recorder, f"{number + 1:02d}-{operation}-impact-result")
        child.send("q")
        child.expect("READ-ONLY IMPACT VERIFICATION")
        child.expect("APPLY HANDOFF .* ABSENT")
        child.expect(pexpect.EOF)
        _BASE._snapshot(recorder, f"{number + 2:02d}-{operation}-impact-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="semantic-add-endpoints-") as directory:
        root = Path(directory)
        _capture_add("distill", root / "distill-add", 1)
        _capture_add("elaborate", root / "elaborate-add", 4)
        _capture_impact("distill", root / "distill-impact", 7)
        _capture_impact("elaborate", root / "elaborate-impact", 10)
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
