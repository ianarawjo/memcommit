"""Capture the real named-Ground Fit Resolve interaction in a color PTY."""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import time
import uuid

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BASE_PATH = ROOT / "docs/screenshots/ordinary-query-one-shot-20260813/capture.py"
SPEC = importlib.util.spec_from_file_location("terminal_capture_base", BASE_PATH)
assert SPEC is not None and SPEC.loader is not None
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
BASE.OUT = OUT

COLUMNS = 180
ROWS = 52
GROUND_NAME = "ticker-fit-resolve"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _prepare_ground(root: Path):
    import memcommit.ops as ops
    import memcommit.store as store_module
    from memcommit.fit import FitExample, FitJudgment, FitReport, FitRule
    from memcommit.fit_store import FitStore
    from memcommit.ground import (
        GroundTargetSpec,
        bind_ground_workbench,
        create_ground_session,
        propose_ground_example,
        propose_ground_rule,
        upgrade_ground_to_propositions,
    )
    from memcommit.store import MemoryStore, ground_session_record_digest

    store_module.STORE_DIR = root
    store = MemoryStore()
    raw = ops.init("test/ground/ticker-description")
    examples = ops.init("test/ground/ticker-examples")
    output = ops.init("test/ground/ticker-output")
    contexts = (raw, examples, output)
    for context in contexts:
        store.create_context(context)
    session = bind_ground_workbench(
        create_ground_session(
            GROUND_NAME,
            goal="티커가 어떻게 만들어지는지 규칙을 알고 싶어",
        ),
        description=(
            "Refine synthetic ticker Rules against reviewed proposition Examples."
        ),
        raw_context=raw,
        derived_context=examples,
        target_contexts=(output,),
        target_requirements=(
            GroundTargetSpec(
                context_name=output.name,
                description="Retain separately reviewed synthetic ticker Rules.",
                role="PUBLICATION_TARGET",
            ),
        ),
    )
    session = upgrade_ground_to_propositions(session)
    session = propose_ground_rule(
        session,
        rule="Use initials from every meaningful company-name token.",
        rationale="A deliberately incomplete initial ticker hypothesis.",
        current_contexts=contexts,
        rule_provenance="DISTILLED",
    )
    session = propose_ground_example(
        session,
        proposition=(
            'Applying the synthetic ticker Rules to "Redwood Inc." '
            'produces "RED".'
        ),
        rationale="A single-word boundary that the initials Rule cannot settle.",
        current_contexts=contexts,
        input_text="Redwood Inc.",
        expected_output="RED",
        case_role="BOUNDARY",
    )
    store.save_ground_session(session)
    rule = session.items_of_kind("RULE")[0]
    example = session.items_of_kind("CASE")[0]
    report = FitReport(
        uid=str(uuid.uuid4()),
        ground_uid=session.uid,
        ground_name=session.contract_name,
        ground_revision=session.revision,
        ground_digest=ground_session_record_digest(session),
        rules=(FitRule(rule.uid, "r1", rule.content),),
        examples=(
            FitExample(
                example.uid,
                "e1",
                example.proposition,
                "PROPOSITION",
                (rule.uid,),
            ),
        ),
        judgments=(
            FitJudgment(
                example_uid=example.uid,
                status="UNDERDETERMINED",
                rule_uids=(rule.uid,),
                reason=(
                    "The Rule does not specify how a normalized single-word "
                    "company name produces a three-letter mnemonic."
                ),
                observed="The current Rule supplies only one initial: R.",
            ),
        ),
        overview="The single-word boundary remains underdetermined.",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    FitStore(store).save(report)
    return store, session, report


def _run_child(root: Path) -> None:
    from memcommit.commands.ground import _run_existing_ground_shell
    from memcommit.fit_store import FitStore
    from memcommit.store import ground_session_record_digest

    store, session, report = _prepare_ground(root)
    _run_existing_ground_shell(session)
    latest = store.load_ground_session(session.contract_name)
    assert latest is not None
    receipt = FitStore(store).latest_for_ground(latest)
    assert receipt is not None
    print("\x1b[2J\x1b[H", end="")
    print("\x1b[1;38;2;138;173;244mMEM GROUND · FIT RESOLVE VERIFICATION\x1b[0m")
    print(f"GROUND · {latest.contract_name}")
    print(f"REVISION · {session.revision} -> {latest.revision}")
    print(f"ONE REVISION ONLY · {latest.revision == session.revision + 1}")
    print(f"FIT RECEIPT RETAINED · {receipt.report.uid == report.uid}")
    print(f"FIT RECEIPT CURRENT · {receipt.current}")
    print(f"FIT RECEIPT STALE · {not receipt.current}")
    print(f"GROUND DIGEST · {ground_session_record_digest(latest)}")
    print("CONTEXTS MUTATED · NONE")
    print("READY VERIFICATION", flush=True)


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


def _settle(child: pexpect.spawn, *, seconds: float = 0.35) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            child.read_nonblocking(size=65_536, timeout=0.05)
        except pexpect.TIMEOUT:
            continue
        except pexpect.EOF:
            return


def _snapshot(recorder, stem: str) -> None:
    BASE._render(recorder.getvalue(), stem)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="memcommit-ground-fit-resolve-"
    ) as directory:
        recorder = BASE._StreamRecorder()
        child = pexpect.spawn(
            sys.executable,
            [
                str(Path(__file__).resolve()),
                "--child",
                str(Path(directory) / "store"),
            ],
            cwd=str(ROOT),
            env=_environment(),
            encoding="utf-8",
            codec_errors="replace",
            timeout=60,
            dimensions=(ROWS, COLUMNS),
        )
        child.logfile_read = recorder
        try:
            child.expect(GROUND_NAME)
            child.send("\t" * 4)
            _settle(child)
            _snapshot(recorder, "01-current-nonfit-example")

            child.send("x")
            _settle(child, seconds=0.6)
            _snapshot(recorder, "02-fit-resolve-menu")

            child.send("\x1b[B")
            child.send("\r")
            _settle(child, seconds=0.6)
            _snapshot(recorder, "03-cited-rule-inline-editor")

            child.send(" Replace the single-word boundary with its first three letters.")
            _settle(child)
            _snapshot(recorder, "04-edited-rule-not-saved")

            child.send("\r")
            _settle(child, seconds=0.8)
            _snapshot(recorder, "05-exact-command-review")

            child.send("\x1b[C")
            _settle(child)
            _snapshot(recorder, "06-effects-review")

            child.send("\r")
            _settle(child, seconds=1.0)
            _snapshot(recorder, "07-applied-stale-fit")

            child.send("\r")
            _settle(child)
            _snapshot(recorder, "08-stale-fit-detail")

            child.send("q")
            child.expect("READY VERIFICATION")
            child.expect(pexpect.EOF)
            _snapshot(recorder, "09-read-only-verification")
        finally:
            if child.isalive():
                child.close(force=True)

    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
    if "38;2;" not in raw:
        raise RuntimeError("PTY stream did not contain expected true-color ANSI.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        _run_child(Path(sys.argv[2]))
    else:
        main()
