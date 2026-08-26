"""Capture the real named-Ground TUI consuming Fit receipts."""

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
SPEC = importlib.util.spec_from_file_location("terminal_capture_base", BASE_PATH)
assert SPEC is not None and SPEC.loader is not None
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
BASE.OUT = OUT
ROWS = 52
COLUMNS = 180

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


class _DelayedFitProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        time.sleep(1.4)
        return json.dumps(
            {
                "overview": "The active Rule reproduces the reviewed Example.",
                "predictions": [
                    {
                        "case_id": "e1",
                        "disposition": "PREDICTED",
                        "predicted": "AAT",
                        "reason": "The reviewed initials Rule produces AAT.",
                    }
                ],
            }
        )


def _prepare_store(root: Path):
    import memcommit.ops as ops
    from memcommit.ground import (
        GroundTargetSpec,
        bind_ground_workbench,
        create_ground_session,
        propose_ground_case,
        propose_ground_rule,
    )
    from memcommit.store import MemoryStore

    store = MemoryStore(root=root)
    raw = ops.init("ticker/raw")
    cases = ops.init("ticker/cases")
    example = ops.add(cases, "Axiom AI Technologies")
    target = ops.init("ticker/output")
    for context in (raw, cases, target):
        store.create_context(context)
    session = bind_ground_workbench(
        create_ground_session(
            "ticker-fit",
            goal="Generate reviewed deterministic ticker symbols.",
        ),
        description="Fit ticker Rules to concrete reviewed Examples.",
        raw_context=raw,
        derived_context=cases,
        target_contexts=(target,),
        target_requirements=(
            GroundTargetSpec(
                context_name=target.name,
                description="Publish only ticker outputs that fit.",
                role="PUBLICATION_TARGET",
            ),
        ),
    )
    contexts = (raw, cases, target)
    session = propose_ground_rule(
        session,
        rule="Use uppercase initials after removing legal-form suffixes.",
        rationale="This is the current generalized ticker policy.",
        current_contexts=contexts,
    )
    rule = session.items_of_kind("RULE")[0]
    session = propose_ground_case(
        session,
        rule_selector=rule.uid,
        case=example.content,
        source_context_uid=cases.uid,
        source_memory_uid=example.uid,
        target_context_names=(target.name,),
        expected="AAT",
        rationale="This is the reviewed concrete ticker outcome.",
        current_contexts=contexts,
    )
    store.save_ground_session(session)
    return store, session, contexts


def _run_child(store_root: Path, *, stale: bool) -> None:
    from memcommit.commands.ground.named_shell import run_named_ground_shell
    from memcommit.fit_runtime import execute_and_save_ground_fit
    from memcommit.fit_store import FitStore
    from memcommit.ground import propose_ground_rule
    from memcommit.store import ground_session_record_digest

    store, session, contexts = _prepare_store(store_root)

    def run_fit(active):
        return execute_and_save_ground_fit(
            store=store,
            ground_name=active.contract_name,
            provider_factory=_DelayedFitProvider,
        )

    if stale:
        run_fit(session)
        revised = propose_ground_rule(
            session,
            rule="Explicitly supplied short symbols take precedence.",
            rationale="This later Rule changes the fitted Rule set.",
            current_contexts=contexts,
        )
        store.save_ground_session(
            revised,
            replace=True,
            expected_uid=session.uid,
            expected_revision=session.revision,
            expected_digest=ground_session_record_digest(session),
        )
        session = revised

    result = run_named_ground_shell(
        session,
        interpret=lambda *_args: (_ for _ in ()).throw(
            RuntimeError("Capture does not submit semantic Ground dialogue.")
        ),
        apply=lambda *_args: (_ for _ in ()).throw(
            RuntimeError("Capture does not apply Ground mutations.")
        ),
        run_fit=run_fit,
        lookup_fit=lambda active: FitStore(store).latest_for_ground(active),
        reload_session=lambda name: store.load_ground_session(name),
        app_input=None,
        app_output=None,
        require_tty=True,
    )
    print(
        f"CAPTURE COMPLETE · {result.status} · GROUND REV {result.session.revision}",
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


def _capture_current(store_root: Path) -> None:
    child, recorder = _spawn("current", store_root)
    try:
        BASE._settle(child, seconds=0.8)
        child.send("\t\t\t\t")
        BASE._settle(child, seconds=0.4)
        BASE._snapshot(recorder, "01-cases-before-fit")

        child.send("f")
        BASE._settle(child, seconds=0.25)
        BASE._snapshot(recorder, "02-fit-running")

        BASE._settle(child, seconds=1.8)
        BASE._snapshot(recorder, "03-current-fit-receipt")

        child.send("q")
        child.expect("CAPTURE COMPLETE")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_stale(store_root: Path) -> None:
    child, recorder = _spawn("stale", store_root)
    try:
        BASE._settle(child, seconds=2.3)
        child.send("\t\t\t\t")
        BASE._settle(child, seconds=0.5)
        BASE._snapshot(recorder, "04-stale-after-rule-change")
        child.send("q")
        child.expect("CAPTURE COMPLETE")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-ground-fit-") as directory:
        root = Path(directory)
        _capture_current(root / "current")
        _capture_stale(root / "stale")
    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("PTY stream did not contain true-color ANSI styles.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        _run_child(Path(sys.argv[3]), stale=sys.argv[2] == "stale")
    else:
        main()
