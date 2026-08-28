"""Capture compact Ground Memory rows across four ticker examples."""

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
SPEC = importlib.util.spec_from_file_location("compact_ticker_capture_base", BASE_PATH)
assert SPEC is not None and SPEC.loader is not None
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
BASE.OUT = OUT
ROWS = 52
COLUMNS = 180

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


TICKERS = (
    ("Apple Inc.", "AAPL", "FIT"),
    ("Google LLC", "GOOG", "FIT"),
    ("Microsoft Corporation", "MSFT", "FIT"),
    ("Berkshire Hathaway Class B", "BRK.B", "BOUNDARY"),
)


def _proposition(company: str, ticker: str) -> str:
    return (
        f'Applying the ticker Rules to "{company}" produces "{ticker}".'
    )


class _DelayedTickerFitProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        if operation != "fit_propositions":
            raise RuntimeError(f"Unexpected Fit operation: {operation}")
        time.sleep(1.4)
        payload = json.loads(prompt.split("FIT PROPOSITION PAYLOAD:\n", 1)[1])
        return json.dumps(
            {
                "overview": "The Rule reproduces all four reviewed ticker examples.",
                "judgments": [
                    {
                        "question_id": question["question_id"],
                        "verdict": "YES",
                        "reason": "The active Rule supports the reviewed proposition.",
                        "considered_proposition_ids": [
                            item["proposition_id"]
                            for item in (
                                *question["background"],
                                *question["propositions"],
                            )
                        ],
                        "material_proposition_ids": [],
                        "consistent_reading": "",
                        "inconsistent_reading": "",
                    }
                    for question in payload["questions"]
                ],
            }
        )


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
    candidates = ops.init("ticker/examples")
    source_memories = [
        ops.add(candidates, content) for content, _expected, _role in TICKERS
    ]
    target = ops.init("ticker/output")
    for context in (raw, candidates, target):
        store.create_context(context)
    session = bind_ground_workbench(
        create_ground_session(
            "ticker-compact",
            goal="Use reviewed company examples to check ticker-symbol Rules.",
        ),
        description="Fit one ticker Rule to four concrete company examples.",
        raw_context=raw,
        derived_context=candidates,
        target_contexts=(target,),
        target_requirements=(
            GroundTargetSpec(
                context_name=target.name,
                description="Publish only ticker outputs that fit.",
                role="PUBLICATION_TARGET",
            ),
        ),
    )
    session = upgrade_ground_to_propositions(session)
    contexts = (raw, candidates, target)
    session = propose_ground_rule(
        session,
        rule="Use the conventional reviewed U.S. ticker symbol for each company.",
        rationale="The examples check ordinary symbols and one share-class boundary.",
        current_contexts=contexts,
    )
    rule = session.items_of_kind("RULE")[0]
    for source, (content, expected, role) in zip(source_memories, TICKERS):
        session = propose_ground_example(
            session,
            proposition=_proposition(content, expected),
            rule_selectors=(rule.uid,),
            source_context_uid=candidates.uid,
            source_memory_uid=source.uid,
            target_context_names=(target.name,),
            input_text=content,
            expected_output=expected,
            rationale="This is one concrete reviewed ticker expectation.",
            current_contexts=contexts,
            case_role=role,
        )
    store.save_ground_session(session)
    return store, session


def _run_child(store_root: Path) -> None:
    from memcommit.adapters.console.commands.ground.named_shell import run_named_ground_shell
    from memcommit.application.operations.fit.runtime import execute_and_save_ground_fit
    from memcommit.application.operations.fit.store import FitStore

    store, session = _prepare_store(store_root)

    def run_fit(active):
        return execute_and_save_ground_fit(
            store=store,
            ground_name=active.contract_name,
            provider_factory=_DelayedTickerFitProvider,
        )

    print("$ mem ground ticker-compact", flush=True)
    print(
        f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}",
        flush=True,
    )
    result = run_named_ground_shell(
        session,
        interpret=lambda *_args: (_ for _ in ()).throw(
            RuntimeError("Capture does not submit Ground dialogue.")
        ),
        apply=lambda *_args: (_ for _ in ()).throw(
            RuntimeError("Capture does not apply Ground mutations.")
        ),
        run_fit=run_fit,
        lookup_fit=lambda active: FitStore(store).latest_for_ground(active),
        reload_session=lambda name: store.load_ground_session(name),
        require_tty=True,
    )
    latest = FitStore(store).latest_for_ground(result.session)
    print("GROUND CLOSED · READ-ONLY VERIFICATION")
    print(f"  SHELL RESULT · {result.status}")
    print(f"  SAVED MEMORIES · {len(result.session.items_of_kind('CASE'))}")
    print(f"  SCHEMA · {result.session.schema_version} · PROPOSITION")
    print(f"  FIT JUDGMENTS · {len(latest.report.judgments) if latest else 0}")
    print(f"  FIT CURRENT · {latest.current if latest else False}", flush=True)


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


def _spawn(store_root: Path):
    recorder = BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", str(store_root)],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=15,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-ground-tickers-") as directory:
        child, recorder = _spawn(Path(directory))
        try:
            BASE._settle(child, seconds=0.8)
            BASE._snapshot(recorder, "01-entry")

            child.send("\t\t\t\t")
            BASE._settle(child, seconds=0.4)
            BASE._snapshot(recorder, "02-four-memories-before-fit")

            child.send("\r")
            BASE._settle(child, seconds=0.4)
            BASE._snapshot(recorder, "03-memory-detail")

            child.send("\x7f")
            BASE._settle(child, seconds=0.2)
            child.send("f")
            BASE._settle(child, seconds=0.25)
            BASE._snapshot(recorder, "04-fit-running")

            BASE._settle(child, seconds=1.8)
            BASE._snapshot(recorder, "05-four-memories-fit")

            child.send("q")
            child.expect("GROUND CLOSED")
            BASE._settle(child, seconds=0.2)
            BASE._snapshot(recorder, "06-close-verification")
            child.expect(pexpect.EOF)
        finally:
            if child.isalive():
                child.close(force=True)
    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("PTY stream did not contain true-color ANSI styles.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        _run_child(Path(sys.argv[2]))
    else:
        main()
