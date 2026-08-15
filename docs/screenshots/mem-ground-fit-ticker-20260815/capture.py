"""Capture one real incremental ticker Ground and Fit evaluation."""

from __future__ import annotations

from collections import Counter
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
BASE_PATH = ROOT / "docs/screenshots/atomize-memory-selection-20260814/capture.py"
SPEC = importlib.util.spec_from_file_location("terminal_capture_base", BASE_PATH)
assert SPEC is not None and SPEC.loader is not None
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
BASE.OUT = OUT

COLUMNS = 180
ROWS = 52
MODEL = "gpt-5.6-sol"
REASONING = "none"
GROUND_NAME = "ticker-fit-incremental"
GOAL = (
    "Refine deterministic synthetic ticker Rules against concrete reviewed "
    "Examples without claiming official market symbols."
)
CASES = (
    ("North Star Energy Inc.", "NSE"),
    ("Blue River Holdings LLC", "BRH"),
    ("Cedar Valley Technologies Corporation", "CVT"),
    ("Aurora Robotics Ltd.", "AR"),
    ("Harbor Point Foods PLC", "HPF"),
    ("The Meridian Group Inc.", "MG"),
    ("Lumen Labs LLC", "LL"),
    ("Quanta Systems & Services Inc.", "QSS"),
    ("Atlas 7 Networks Corp.", "A7N"),
    ("3 Rivers Logistics LLC", "3RL"),
    ("Redwood Inc.", "RED"),
    ("Meridian Corporation", "MER"),
    ("Solstice Ltd.", "SOL"),
    ("International Business Fabricators Inc.", "IBF"),
    ("North Star Energy Inc., Class B", "NSE.B"),
    ("North Star Energy Inc., Class A", "NSE.A"),
    ("Blue River Holdings LLC, Preferred", "BRH.P"),
    ("Acme & Sons Ltd.", "AS"),
    ("Axiom AI Technologies Inc.", "AAT"),
    ("The 5th Avenue Retail Group LLC", "5ARG"),
)
DISTILLED_RULES = (
    (
        "When generating a synthetic ticker, first remove a leading article "
        "such as ‘The,’ discard legal-form suffixes such as Inc., LLC, Ltd., "
        "PLC, Corp., or Corporation, and ignore connectors such as ‘&’ when "
        "selecting ticker characters; preserve meaningful numeric tokens."
    ),
    (
        "When the normalized company name has two or more meaningful words, "
        "form the base ticker from the initial character of each meaningful "
        "word, using the numeric character for a number-bearing word; preserve "
        "a meaningful abbreviation such as ‘AI’ as a single ticker component."
    ),
    (
        "When the normalized company name is a single word, derive a concise "
        "three-letter mnemonic from that word rather than applying the "
        "multiword-initial rule."
    ),
    (
        "When share-class details are present, keep the ordinary company base "
        "ticker and append a dot suffix: ‘.A’ or ‘.B’ for the corresponding "
        "class and ‘.P’ for Preferred."
    ),
    (
        "Treat every generated symbol under these rules as a synthetic "
        "mnemonic; do not represent it as an official, unique, or "
        "exchange-valid market ticker without separate verification."
    ),
)
REVISED_RULE_2 = (
    "When a normalized company name has two or more meaningful words, form the "
    "base ticker from exactly one leading alphanumeric character per meaningful "
    "word; a multi-letter abbreviation such as ‘AI’ contributes only its first "
    "character, while a number-bearing word preserves its leading numeric character."
)
REVISED_RULE_3 = (
    "When the normalized company name is a single word, form the base ticker "
    "from exactly its first three alphabetic characters in uppercase."
)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _clear() -> None:
    print("\x1b[2J\x1b[H", end="")


def _heading(text: str) -> None:
    print(f"\x1b[1;38;2;138;173;244m{text}\x1b[0m")


def _memory(text: str) -> str:
    return f"\x1b[38;2;202;211;245m{text}\x1b[0m"


def _proposition(company: str, ticker: str) -> str:
    return (
        f'Applying the synthetic ticker Rules to "{company}" produces '
        f'"{ticker}".'
    )


def _save_next(store, previous, revised) -> None:
    from memcommit.store import ground_session_record_digest

    store.save_ground_session(
        revised,
        replace=True,
        expected_uid=previous.uid,
        expected_revision=previous.revision,
        expected_digest=ground_session_record_digest(previous),
    )


def _add_example(store, session, contexts, company: str, ticker: str):
    from memcommit.ground import propose_ground_example

    revised = propose_ground_example(
        session,
        proposition=_proposition(company, ticker),
        rationale="Reviewed synthetic mapping imported from the ticker fixture.",
        current_contexts=contexts,
        input_text=company,
        expected_output=ticker,
    )
    _save_next(store, session, revised)
    return revised


def _prepare_store(root: Path):
    import memcommit.ops as ops
    from memcommit.ground import (
        GroundTargetSpec,
        bind_ground_workbench,
        create_ground_session,
        propose_ground_rule,
        upgrade_ground_to_propositions,
    )
    from memcommit.store import MemoryStore, ground_session_record_digest

    store = MemoryStore(root=root)
    description = ops.init("test/ground/ticker-description")
    candidates = ops.init("test/ground/ticker-examples")
    output = ops.init("test/ground/ticker-output")
    for context in (description, candidates, output):
        store.create_context(context)
    contexts = (description, candidates, output)
    session = bind_ground_workbench(
        create_ground_session(GROUND_NAME, goal=GOAL),
        description="Fit synthetic ticker Rules to reviewed mapping propositions.",
        raw_context=description,
        derived_context=candidates,
        target_contexts=(output,),
        target_requirements=(
            GroundTargetSpec(
                context_name=output.name,
                description="Retain only separately approved ticker outputs.",
                role="PUBLICATION_TARGET",
            ),
        ),
    )
    session = upgrade_ground_to_propositions(session)
    store.save_ground_session(session)
    ledger = [
        {
            "action": "create-bound-upgrade-v3",
            "revision": session.revision,
            "digest": ground_session_record_digest(session),
        }
    ]
    for ordinal, rule in enumerate(DISTILLED_RULES, 1):
        revised = propose_ground_rule(
            session,
            rule=rule,
            rationale=(
                "Imported from the reviewed real Distill receipt as "
                f"Rule {ordinal}."
            ),
            current_contexts=contexts,
            rule_provenance="DISTILLED",
        )
        _save_next(store, session, revised)
        session = revised
        ledger.append(
            {
                "action": f"add-rule-{ordinal}",
                "revision": session.revision,
                "digest": ground_session_record_digest(session),
            }
        )
    for ordinal, (company, ticker) in enumerate(CASES[:18], 1):
        session = _add_example(store, session, contexts, company, ticker)
        ledger.append(
            {
                "action": f"add-example-{ordinal:02d}",
                "revision": session.revision,
                "digest": ground_session_record_digest(session),
            }
        )
    return store, contexts, session, ledger


def _status_lines(report) -> list[str]:
    counts = Counter(judgment.status for judgment in report.judgments)
    lines = [
        "COUNTS · "
        + " · ".join(
            f"{status} {counts.get(status, 0)}"
            for status in (
                "FIT",
                "CONTRADICTS",
                "UNDERDETERMINED",
                "NOT_APPLICABLE",
            )
        )
    ]
    for example, judgment in zip(report.examples, report.judgments, strict=True):
        statement = example.statement
        if len(statement) > 118:
            statement = statement[:117] + "…"
        lines.append(
            f"{example.alias.upper()} · {judgment.status:<15} · {statement}"
        )
    return lines


def _print_report(title: str, report, *, current: bool) -> None:
    _clear()
    _heading(title)
    print(
        f"STATUS · READ-ONLY · {'CURRENT' if current else 'STALE'} · "
        f"GROUND REVISION {report.ground_revision}"
    )
    print(f"RECEIPT · {report.uid} · DIGEST {report.digest[:16]}")
    print(f"PROVIDER · {MODEL} · REASONING {REASONING.upper()}")
    print()
    for line in _status_lines(report):
        print(_memory(line) if "Applying" in line else line)


def _run_fit(store, provider, session):
    from memcommit.fit_runtime import execute_and_save_ground_fit

    return execute_and_save_ground_fit(
        store=store,
        ground_name=session.contract_name,
        provider_factory=lambda: provider,
    )


def _write_evidence(*, ledger, reports, final_session, stale_checks) -> None:
    from memcommit.store import ground_session_record_digest

    data = {
        "evaluation": "incremental ticker Ground Fit",
        "provider": {
            "name": "codex_chatgpt",
            "model": MODEL,
            "reasoning_effort": REASONING,
        },
        "source_distill_evidence": (
            "docs/screenshots/mem-distill-ticker-20260815/actual-run.json"
        ),
        "ground": {
            "name": final_session.contract_name,
            "schema_version": final_session.schema_version,
            "final_revision": final_session.revision,
            "final_digest": ground_session_record_digest(final_session),
            "rule_count": len(final_session.items_of_kind("RULE")),
            "example_count": len(final_session.items_of_kind("CASE")),
        },
        "incremental_revision_ledger": ledger,
        "stale_checks": stale_checks,
        "fit_runs": [report.to_dict() for report in reports],
        "temporary_store_removed": True,
    }
    (OUT / "actual-run.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _run_child(store_root: Path) -> None:
    from memcommit.commands.ground_named_shell import (
        render_named_ground_memories_pane,
    )
    from memcommit.fit_store import FitStore
    from memcommit.ground import review_ground_item
    from memcommit.query_provider import CodexChatGPTProvider
    from memcommit.store import ground_session_record_digest

    store, contexts, session, ledger = _prepare_store(store_root)
    _clear()
    _heading("MEM GROUND · INCREMENTAL TICKER FIT")
    print(f"GROUND · {GROUND_NAME} · SCHEMA V3 · REVISION {session.revision}")
    print("RULES · 5 REVIEWED DISTILL PROPOSALS · ADDED ONE REVISION AT A TIME")
    print("EXAMPLES · 18/20 · ADDED ONE REVISION AT A TIME")
    print(f"MODEL · {MODEL} · REASONING {REASONING.upper()}")
    print()
    for index, (company, ticker) in enumerate(CASES[:18], 1):
        print(_memory(f"E{index:02d} · {company} → {ticker}"))
    print()
    print("R · RUN FIRST FIT", flush=True)
    if sys.stdin.readline().strip().lower() != "r":
        raise RuntimeError("First Fit was not approved by the capture driver.")

    _clear()
    _heading("MEM FIT · PROVIDER TURN 1")
    print("GROUND · REVISION 23 · RULES 5 · EXAMPLES 18")
    print("STATE · RUNNING · NO RECEIPT PUBLISHED", flush=True)
    provider = CodexChatGPTProvider.connect(
        model=MODEL,
        reasoning_effort=REASONING,
        timeout=300,
    )
    first = _run_fit(store, provider, session)
    _print_report("MEM FIT · FIRST 18 EXAMPLES", first, current=True)
    print("N · ADD EXAMPLE 19", flush=True)
    if sys.stdin.readline().strip().lower() != "n":
        raise RuntimeError("Example 19 was not approved by the capture driver.")

    company, ticker = CASES[18]
    session = _add_example(store, session, contexts, company, ticker)
    ledger.append(
        {
            "action": "add-example-19",
            "revision": session.revision,
            "digest": ground_session_record_digest(session),
        }
    )
    stale_first = FitStore(store).latest_for_ground(session)
    assert stale_first is not None and not stale_first.current
    rendered = render_named_ground_memories_pane(
        session,
        selected_memory_index=18,
        fit_receipt=stale_first,
    )
    selected_card = rendered.split("\n\n")[-1]
    _clear()
    _heading("MEM GROUND · EXAMPLE 19 ADDED")
    print(f"GROUND · REVISION {session.revision} · PREVIOUS FIT STALE")
    print("ONE EXAMPLE ADDITION · ONE DURABLE REVISION")
    print()
    print(selected_card)
    print()
    print("R · RUN FIT WITH AXIOM BOUNDARY", flush=True)
    if sys.stdin.readline().strip().lower() != "r":
        raise RuntimeError("Second Fit was not approved by the capture driver.")

    _clear()
    _heading("MEM FIT · PROVIDER TURN 2")
    print("GROUND · REVISION 24 · RULES 5 · EXAMPLES 19")
    print("STATE · RUNNING · NO RECEIPT PUBLISHED", flush=True)
    second = _run_fit(store, provider, session)
    _print_report("MEM FIT · AXIOM BOUNDARY", second, current=True)
    print("N · REFINE TWO RULES AND ADD EXAMPLE 20", flush=True)
    if sys.stdin.readline().strip().lower() != "n":
        raise RuntimeError("Rule revision was not approved by the capture driver.")

    rules = session.items_of_kind("RULE")
    for rule, replacement, label in (
        (rules[1], REVISED_RULE_2, "refine-rule-2"),
        (rules[2], REVISED_RULE_3, "refine-rule-3"),
    ):
        revised = review_ground_item(
            session,
            rule.uid,
            action="REFINE",
            response=replacement,
            current_contexts=contexts,
        )
        _save_next(store, session, revised)
        session = revised
        ledger.append(
            {
                "action": label,
                "revision": session.revision,
                "digest": ground_session_record_digest(session),
            }
        )
    company, ticker = CASES[19]
    session = _add_example(store, session, contexts, company, ticker)
    ledger.append(
        {
            "action": "add-example-20",
            "revision": session.revision,
            "digest": ground_session_record_digest(session),
        }
    )
    stale_second = FitStore(store).latest_for_ground(session)
    assert stale_second is not None and not stale_second.current
    _clear()
    _heading("MEM GROUND · RULES REFINED · EXAMPLE 20 ADDED")
    print(f"GROUND · REVISION {session.revision} · PREVIOUS FIT STALE")
    print("R2 · " + REVISED_RULE_2)
    print("R3 · " + REVISED_RULE_3)
    print(_memory("E20 · The 5th Avenue Retail Group LLC → 5ARG"))
    print()
    print("R · RUN FINAL FIT", flush=True)
    if sys.stdin.readline().strip().lower() != "r":
        raise RuntimeError("Final Fit was not approved by the capture driver.")

    _clear()
    _heading("MEM FIT · PROVIDER TURN 3")
    print(f"GROUND · REVISION {session.revision} · RULES 5 · EXAMPLES 20")
    print("STATE · RUNNING · NO RECEIPT PUBLISHED", flush=True)
    final = _run_fit(store, provider, session)
    _print_report("MEM FIT · FINAL 20 EXAMPLES", final, current=True)
    print("V · VERIFY REVISION AND RECEIPT INVARIANTS", flush=True)
    if sys.stdin.readline().strip().lower() != "v":
        raise RuntimeError("Verification was not approved by the capture driver.")

    final_receipt = FitStore(store).latest_for_ground(session)
    assert final_receipt is not None and final_receipt.current
    stale_checks = {
        "first_receipt_stale_after_example_19": not stale_first.current,
        "second_receipt_stale_after_rule_and_example_revisions": (
            not stale_second.current
        ),
        "final_receipt_current": final_receipt.current,
    }
    _write_evidence(
        ledger=ledger,
        reports=(first, second, final),
        final_session=session,
        stale_checks=stale_checks,
    )
    _clear()
    _heading("MEM GROUND + FIT · VERIFICATION")
    print(f"GROUND SCHEMA · V{session.schema_version}")
    print(f"FINAL REVISION · {session.revision}")
    print(f"DURABLE RULES · {len(session.items_of_kind('RULE'))}")
    print(f"DURABLE EXAMPLES · {len(session.items_of_kind('CASE'))}")
    print(f"REVISION LEDGER ENTRIES · {len(ledger)}")
    print(f"EACH EXAMPLE HAS DISTINCT ADD REVISION · {len(CASES) == 20}")
    print(f"FIRST RECEIPT STALE AFTER E19 · {not stale_first.current}")
    print(f"SECOND RECEIPT STALE AFTER REVISIONS · {not stale_second.current}")
    print(f"FINAL RECEIPT CURRENT · {final_receipt.current}")
    print(f"FINAL RECEIPT GROUND REVISION · {final.ground_revision}")
    print("CONTEXTS MUTATED BY FIT · NONE")
    print("TEMPORARY STORE · REMOVED AFTER CAPTURE")
    print("EVIDENCE · docs/screenshots/mem-ground-fit-ticker-20260815/actual-run.json")
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
    with tempfile.TemporaryDirectory(prefix="memcommit-ground-fit-ticker-") as directory:
        recorder = BASE._StreamRecorder()
        child = pexpect.spawn(
            sys.executable,
            [str(Path(__file__).resolve()), "--child", str(Path(directory) / "store")],
            cwd=str(ROOT),
            env=_environment(),
            encoding="utf-8",
            codec_errors="replace",
            timeout=960,
            dimensions=(ROWS, COLUMNS),
        )
        child.logfile_read = recorder
        try:
            for stem, marker, key in (
                ("01-ground-rules-and-18-examples", "RUN FIRST FIT", "r"),
                ("02-first-fit-running", "STATE .* RUNNING .* NO RECEIPT PUBLISHED", None),
                ("03-first-fit-receipt", "ADD EXAMPLE 19", "n"),
                ("04-example-19-stales-fit", "RUN FIT WITH AXIOM BOUNDARY", "r"),
                ("05-second-fit-running", "PROVIDER TURN 2", None),
                ("06-fit-after-example-19", "REFINE TWO RULES", "n"),
                ("07-revisions-stale-fit", "RUN FINAL FIT", "r"),
                ("08-final-fit-running", "PROVIDER TURN 3", None),
                ("09-final-fit-receipt", "VERIFY REVISION", "v"),
            ):
                child.expect(marker)
                _settle(child, seconds=0.15 if "running" in stem else 0.35)
                _snapshot(recorder, stem)
                if key is not None:
                    child.sendline(key)
            child.expect("READY VERIFICATION")
            child.expect(pexpect.EOF)
            _snapshot(recorder, "10-verification")
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
