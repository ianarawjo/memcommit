"""Capture unified Ground Fit in plain CLI, Viewer, and AUTO-FIT surfaces."""

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
BASE_PATH = ROOT / "agent-records/docs/screenshots/atomize-memory-selection-20260814/capture.py"
ROWS = 52
COLUMNS = 180

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = _load_module("ground_unified_fit_capture_base", BASE_PATH)
BASE.OUT = OUT


class _DetectorProvider:
    total_calls = 0

    def __init__(self, *, delay: float = 0.0) -> None:
        self.delay = delay

    def complete(self, prompt, *, operation, output_schema=None):
        from memcommit.application.operations.fit.coherence import (
            FIT_COHERENCE_OPERATION,
            FIT_COHERENCE_PAYLOAD_MARKER,
        )

        type(self).total_calls += 1
        if self.delay:
            time.sleep(self.delay)
        if operation == FIT_COHERENCE_OPERATION:
            payload = json.loads(prompt.split(FIT_COHERENCE_PAYLOAD_MARKER, 1)[1])
            findings = []
            for check in payload["checks"]:
                status = "FIT"
                material = []
                reason = "The frozen relation stays within the reviewed scope."
                if check["check_id"] == "context:e1":
                    status = "UNDERDETERMINED"
                    material = ["e1", "k2"]
                    reason = (
                        "The real-company scope has no source-linked Context "
                        "Memory supporting this concrete ticker claim."
                    )
                elif check["check_id"] == "vertical:goal-examples":
                    status = "CONTRADICTS"
                    material = ["g1", "e1"]
                    reason = (
                        "The unsupported synthetic Example does not exercise "
                        "the Goal's real-company boundary."
                    )
                findings.append(
                    {
                        **check,
                        "status": status,
                        "material_aliases": material,
                        "reason": reason,
                    }
                )
            return json.dumps(
                {
                    "overview": "One Example needs contextual review.",
                    "findings": findings,
                }
            )
        if operation == "fit_propositions":
            return json.dumps(
                {
                    "overview": (
                        "The Rule and Example can coexist as propositions; "
                        "source support is checked separately."
                    ),
                    "judgments": [
                        {
                            "question_id": "e1",
                            "verdict": "YES",
                            "reason": (
                                "The Example is compatible with the Rule as " "written."
                            ),
                            "considered_proposition_ids": ["r1", "e1"],
                            "material_proposition_ids": ["r1", "e1"],
                            "consistent_reading": "",
                            "inconsistent_reading": "",
                        }
                    ],
                }
            )
        raise RuntimeError(f"Unexpected Fit capture operation: {operation}")


def _use_store_root(root: Path) -> None:
    import memcommit.persistence.store as store_module

    store_module.STORE_DIR = root


def _prepare_store(root: Path):
    import memcommit.application.capabilities.ops as ops
    from memcommit.application.operations.ground.model import (
        GroundTargetSpec,
        bind_ground_workbench,
        create_ground_session,
        propose_ground_example,
        propose_ground_rule,
        upgrade_ground_to_propositions,
    )
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=root)
    raw = ops.init("ticker/raw")
    ops.add(
        raw,
        "Use actual United States listed companies and source-grounded tickers.",
    )
    examples = ops.init("ticker/examples")
    output = ops.init("ticker/output")
    for context in (raw, examples, output):
        store.create_context(context)
    session = bind_ground_workbench(
        create_ground_session(
            "ticker-context-fit",
            goal="Learn how real United States company ticker symbols are formed.",
        ),
        description="Refine ticker Rules against real sourced company Examples.",
        raw_context=raw,
        derived_context=examples,
        target_contexts=(output,),
        target_requirements=(
            GroundTargetSpec(
                context_name=output.name,
                description="Publish only reviewed ticker Rules.",
                role="PUBLICATION_TARGET",
            ),
        ),
    )
    session = upgrade_ground_to_propositions(session)
    contexts = (raw, examples, output)
    session = propose_ground_rule(
        session,
        rule="Use actual companies and their observed tickers.",
        rationale="This is the reviewed scope boundary.",
        current_contexts=contexts,
        rule_provenance="USER_STATED",
    )
    session = propose_ground_example(
        session,
        proposition="North Star Energy Inc. has ticker NSE.",
        rationale="This initial synthetic Example still needs verification.",
        current_contexts=contexts,
    )
    store.save_ground_session(session)
    return store, session


def _print_verification(store, session, *, label: str) -> None:
    from memcommit.application.operations.fit.store import FitStore
    from memcommit.persistence.store import ground_session_record_digest

    current = store.load_ground_session(session.contract_name)
    latest = FitStore(store).latest_for_ground(current)
    print(label)
    print(f"  GROUND REVISION · {current.revision}")
    print(
        f"  GROUND UNCHANGED · {ground_session_record_digest(current) == ground_session_record_digest(session)}"
    )
    print(f"  FIT RECEIPTS · {len(FitStore(store).list(ground_uid=session.uid))}")
    print(f"  LATEST CURRENT · {latest.current if latest else False}")
    print(f"  PROVIDER CALLS · {_DetectorProvider.total_calls}", flush=True)


def _run_plain_child(store_root: Path) -> None:
    import memcommit.adapters.console.commands.fit.command as fit_command

    _DetectorProvider.total_calls = 0
    store, session = _prepare_store(store_root)
    _use_store_root(store_root)
    fit_command.connect_semantic_provider = _DetectorProvider
    print(f"$ mem fit --ground {session.contract_name} --plain", flush=True)
    print(f"PTY · {os.get_terminal_size().columns}×{os.get_terminal_size().lines}")
    fit_command.cmd(
        None,
        background=None,
        ground_name=session.contract_name,
        receipt=None,
        plain=True,
        tui=False,
    )
    _print_verification(store, session, label="READ-ONLY DETECTION VERIFICATION")
    print("CAPTURE GATE · PRESS V", flush=True)
    sys.stdin.read(1)


def _run_viewer_child(store_root: Path) -> None:
    import memcommit.adapters.console.commands.fit.command as fit_command

    _DetectorProvider.total_calls = 0
    store, session = _prepare_store(store_root)
    _use_store_root(store_root)
    fit_command.connect_semantic_provider = lambda: _DetectorProvider(delay=0.7)
    print(f"$ mem fit --ground {session.contract_name} --tui", flush=True)
    print(f"PTY · {os.get_terminal_size().columns}×{os.get_terminal_size().lines}")
    fit_command.cmd(
        None,
        background=None,
        ground_name=session.contract_name,
        receipt=None,
        plain=False,
        tui=True,
    )
    _print_verification(store, session, label="VIEWER CLOSED · READ-ONLY VERIFICATION")


def _run_ground_child(store_root: Path) -> None:
    from memcommit.adapters.console.commands.ground.named_shell import run_named_ground_shell
    from memcommit.application.operations.fit.runtime import execute_and_save_ground_fit
    from memcommit.application.operations.fit.store import FitStore

    _DetectorProvider.total_calls = 0
    store, session = _prepare_store(store_root)

    def run_fit(active):
        return execute_and_save_ground_fit(
            store=store,
            ground_name=active.contract_name,
            provider_factory=lambda: _DetectorProvider(delay=0.7),
        )

    print(f"$ mem ground {session.contract_name}", flush=True)
    print(f"PTY · {os.get_terminal_size().columns}×{os.get_terminal_size().lines}")
    result = run_named_ground_shell(
        session,
        interpret=lambda *_args: (_ for _ in ()).throw(
            RuntimeError("Capture does not submit Ground dialogue.")
        ),
        apply=lambda *_args: (_ for _ in ()).throw(
            RuntimeError("Capture does not apply Ground mutations.")
        ),
        reload_session=lambda name: store.load_ground_session(name),
        run_fit=run_fit,
        lookup_fit=lambda active: FitStore(store).latest_for_ground(active),
        auto_fit=True,
        require_tty=True,
    )
    _print_verification(store, session, label="GROUND CLOSED · READ-ONLY VERIFICATION")
    print(f"  CLOSE STATUS · {result.status}", flush=True)


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
    recorder = BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind, str(store_root)],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=15,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _capture_plain(store_root: Path) -> None:
    child, recorder = _spawn("plain", store_root)
    try:
        child.expect("CAPTURE GATE")
        BASE._settle(child, seconds=0.2)
        BASE._snapshot(recorder, "01-cli-complete-detection")
        child.send("v\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_viewer(store_root: Path) -> None:
    child, recorder = _spawn("viewer", store_root)
    try:
        BASE._settle(child, seconds=0.3)
        BASE._snapshot(recorder, "02-viewer-complete-graph-running")
        BASE._settle(child, seconds=1.5)
        BASE._snapshot(recorder, "03-viewer-summary")
        child.send("\x1b[B")
        BASE._settle(child, seconds=0.25)
        BASE._snapshot(recorder, "04-viewer-context-focused")
        child.send("\x1b[B\x1b[B\x1b[B")
        BASE._settle(child, seconds=0.25)
        BASE._snapshot(recorder, "05-viewer-example-issue-focused")
        child.send("q")
        child.expect("VIEWER CLOSED")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_ground(store_root: Path) -> None:
    child, recorder = _spawn("ground", store_root)
    try:
        BASE._settle(child, seconds=0.3)
        BASE._snapshot(recorder, "06-ground-auto-fit-running")
        BASE._settle(child, seconds=1.5)
        BASE._snapshot(recorder, "07-ground-detection-projected")
        child.send("\x03")
        child.expect("GROUND CLOSED")
        child.expect(pexpect.EOF)
        BASE._snapshot(recorder, "08-ground-close-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-unified-fit-") as directory:
        root = Path(directory)
        _capture_plain(root / "plain")
        _capture_viewer(root / "viewer")
        _capture_ground(root / "ground")
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("PTY stream did not contain true-color ANSI styles.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        kind = sys.argv[2]
        root = Path(sys.argv[3])
        if kind == "plain":
            _run_plain_child(root)
        elif kind == "viewer":
            _run_viewer_child(root)
        elif kind == "ground":
            _run_ground_child(root)
        else:
            raise RuntimeError(f"Unknown capture kind: {kind}")
    else:
        main()
