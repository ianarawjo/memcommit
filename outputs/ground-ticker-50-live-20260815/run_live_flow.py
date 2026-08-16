"""Run the real 1-to-50 synthetic ticker Ground semantic flow.

This is a diagnostic artifact, not product code. It uses an explicit isolated
MemoryStore and the subscription-backed Codex provider with gpt-5.6-sol / none.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import sys
import time
import traceback
import uuid


REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = Path(__file__).resolve().parent
STORE_ROOT = OUTPUT_ROOT / "store"
STALE_STORE_ROOT = OUTPUT_ROOT / "stale-branch-store"
REPORT_PATH = OUTPUT_ROOT / "report.json"
PROGRESS_PATH = OUTPUT_ROOT / "progress.json"

sys.path.insert(0, str(REPO_ROOT))

import memcommit.study_action_log as study_action_log
from memcommit.context import Context, Memory
from memcommit.distill import DistillError
from memcommit.elaborate import ElaborateError
from memcommit.fit import FitError
from memcommit.fit_runtime import run_fit_with_store
from memcommit.fit_application import FitRequest
from memcommit.ground import (
    GroundError,
    GroundTargetSpec,
    bind_ground_workbench,
    create_ground_session,
    propose_ground_example,
    propose_ground_rule,
    review_ground_item,
    upgrade_ground_to_propositions,
)
from memcommit.ground_distill import execute_ground_distill, freeze_ground_distill
from memcommit.ground_elaborate import (
    execute_ground_elaborate,
    freeze_ground_elaborate,
)
from memcommit.query_provider import CodexChatGPTProvider
from memcommit.store import MemoryStore, ground_session_record_digest


# A diagnostic run outside the active Profile must not add provider events to
# a participant Study ledger merely because the same machine is currently in
# a Study Profile.
study_action_log.record_study_action = lambda *args, **kwargs: None
os.environ["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"


GOAL = "Invent compact, consistent symbols for organization names."
GROUND_NAME = "ticker-50-live"
THRESHOLDS = (1, 4, 8, 12, 20, 35, 50)


# All symbols are generated expectations for this test; they are not claims
# about real exchange-listed tickers.
CASES = (
    ("North Star Energy Inc.", "NSE", "ordinary multiword initials"),
    ("Blue River Logistics LLC", "BRL", "ordinary legal suffix"),
    ("Redwood", "REDW", "single meaningful word"),
    ("Harbor Light Studios Ltd.", "HLS", "ordinary multiword initials"),
    ("The Green Valley Bank Corporation", "GVB", "leading article"),
    ("Cedar & Stone Foods Co.", "CSF", "standalone conjunction"),
    ("Axiom AI Technologies Inc.", "AAT", "acronym-like component"),
    ("Nova Health Group PLC", "NHG", "legal suffix after meaningful Group"),
    ("North Star Energy Inc. Class B", "NSE.B", "class suffix"),
    ("Blue River Logistics LLC Class A", "BRL.A", "class suffix"),
    ("Redwood Class C", "REDW.C", "single word plus class suffix"),
    ("Harbor Light Studios Ltd. Class B", "HLS.B", "class suffix"),
    ("North-West Transit Inc.", "NWT", "hyphenated components"),
    ("O'Brien Market Group", "OMG", "apostrophe inside one component"),
    ("Studio 54 Media LLC", "S5M", "numeric component"),
    ("Seven Seas 2 Logistics Inc.", "SS2L", "numeric component"),
    ("Quantum-X Labs Corp.", "QXL", "hyphenated components"),
    ("Atlas Research & Development Ltd.", "ARD", "standalone conjunction"),
    ("One World 360 Media PLC", "OW3M", "multi-digit component"),
    ("Élan Bio Systems Inc.", "EBS", "diacritic normalization"),
    ("Sunrise Robotics Company", "SR", "legal suffix"),
    ("Polar Data Works Incorporated", "PDW", "long legal suffix"),
    ("Maple Leaf Foods Limited", "MLF", "long legal suffix"),
    ("Urban Ocean Analytics LLC", "UOA", "ordinary multiword initials"),
    ("BrightMind AI Labs Inc.", "BAL", "acronym-like component"),
    ("Deep Space XR Studios Ltd.", "DSXS", "acronym-like component"),
    ("Lake-View Materials Corp.", "LVM", "hyphenated components"),
    ("King's Road Retail Company", "KRR", "apostrophe inside one component"),
    ("The Northern Grid Inc.", "NG", "leading article"),
    ("East & West Mobility LLC", "EWM", "standalone conjunction"),
    ("24 Seven Energy Ltd.", "2SE", "leading numeric component"),
    ("Route 66 Systems Corp.", "R6S", "numeric component"),
    ("Alpha Beta Gamma Delta Inc.", "ABGD", "four meaningful components"),
    ("Mono LLC", "MONO", "single meaningful word"),
    ("Zürich Cloud AG", "ZC", "diacritic and legal suffix"),
    ("Silver Pine Bio-Tech Inc.", "SPBT", "hyphenated components"),
    ("Open Source Network Foundation", "OSNF", "four meaningful components"),
    ("First Class Ventures Class B", "FCV.B", "meaningful Class plus class suffix"),
    ("MegaData 2X Labs LLC", "M2L", "alphanumeric component"),
    ("C++ Systems Inc.", "CS", "punctuation inside one component"),
    ("R&D Signal Labs Ltd.", "RSL", "punctuation inside one component"),
    ("Acme.com Services Corp.", "AS", "dot inside one component"),
    ("Neo-Élan Mobility PLC", "NEM", "hyphen and diacritic"),
    ("One-One-One Holdings Inc.", "OOOH", "repeated hyphen components"),
    ("Delta 9 Bio Group LLC", "D9BG", "numeric component"),
    ("New York AI Exchange Inc.", "NYAE", "acronym-like component"),
    ("The 7 Hills Company", "7H", "leading article and number"),
    ("Redwood Research Class A", "RR.A", "multiword plus class suffix"),
    ("A B C Networks Ltd.", "ABCN", "single-letter components"),
    ("Global Quantum 360 Class C", "GQ3.C", "number plus class suffix"),
)


def proposition(name: str, symbol: str) -> str:
    return (
        f'Applying the synthetic ticker policy to "{name}" produces '
        f'"{symbol}".'
    )


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def emit(stage: str, **details: object) -> None:
    payload = {"stage": stage, **details}
    write_json(PROGRESS_PATH, payload)
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def serialize_distill(result) -> dict[str, object]:
    return {
        "origin": result.origin,
        "overview": result.analysis.overview,
        "outside_memory_uids": list(result.analysis.outside_memory_uids),
        "rules": [
            {
                "content": rule.content,
                "rationale": rule.rationale,
                "support_count": len(rule.support_memory_uids),
                "boundary_count": len(rule.boundary_memory_uids),
            }
            for rule in result.analysis.rules
        ],
    }


def serialize_elaborate(result) -> dict[str, object]:
    analysis = result.analysis
    return {
        "origin": result.origin,
        "mode": analysis.mode.value,
        "overview": analysis.overview,
        "rules": [
            {"content": rule.content, "rationale": rule.rationale}
            for rule in analysis.rules
        ],
        "cases": [
            {
                "proposition": case.proposition,
                "expected": case.expected,
                "rationale": case.rationale,
                "case_role": case.case_role,
                "source_rule_index": case.source_rule_index,
            }
            for case in analysis.cases
        ],
    }


def serialize_fit(result) -> dict[str, object]:
    report = result.report
    counts = Counter(judgment.status for judgment in report.judgments)
    return {
        "receipt_uid": report.uid,
        "current": result.current,
        "ground_revision": report.ground_revision,
        "overview": report.overview,
        "issue_count": report.issue_count,
        "status_counts": dict(sorted(counts.items())),
        "judgments": [
            {
                "example_uid": judgment.example_uid,
                "status": judgment.status,
                "reason": judgment.reason,
            }
            for judgment in report.judgments
        ],
    }


def composite_rule(distill_result) -> str:
    rules = tuple(rule.content.strip() for rule in distill_result.analysis.rules)
    if not rules:
        raise RuntimeError("Distill returned no Rule to review.")
    value = "Synthetic ticker policy: " + " ".join(
        f"({index}) {rule}" for index, rule in enumerate(rules, 1)
    )
    if len(value) > 1_950:
        raise RuntimeError(
            "The reviewed Distill Rule set cannot fit the current Ground-to-"
            "Elaborate single-Rule bridge without truncation."
        )
    return value


def main() -> int:
    if STORE_ROOT.exists() or STALE_STORE_ROOT.exists() or REPORT_PATH.exists():
        raise RuntimeError("Live-flow output already exists; refusing to overwrite it.")
    STORE_ROOT.mkdir(parents=True)
    store = MemoryStore(root=STORE_ROOT)
    report: dict[str, object] = {
        "kind": "GROUND_TICKER_50_LIVE_FLOW",
        "model": "gpt-5.6-sol",
        "reasoning": "none",
        "goal": GOAL,
        "thresholds": list(THRESHOLDS),
        "cases": [
            {
                "ordinal": index,
                "input": name,
                "expected": symbol,
                "boundary": boundary,
                "proposition": proposition(name, symbol),
            }
            for index, (name, symbol, boundary) in enumerate(CASES, 1)
        ],
        "rounds": [],
        "stale_branch": {},
        "status": "RUNNING",
    }
    write_json(REPORT_PATH, report)

    raw = Context(uid=str(uuid.uuid4()), name="ticker/raw")
    candidates = Context(uid=str(uuid.uuid4()), name="ticker/examples")
    target = Context(uid=str(uuid.uuid4()), name="ticker/rules")
    for context in (raw, candidates, target):
        store.save(context)

    session = create_ground_session(GROUND_NAME, goal=GOAL)
    store.save_ground_session(session)

    def current_contexts(active_store: MemoryStore = store):
        return tuple(
            active_store.load_direct(name)
            for name in ("ticker/raw", "ticker/examples", "ticker/rules")
        )

    def save_transition(next_session) -> None:
        nonlocal session
        store.save_ground_session(
            next_session,
            expected_uid=session.uid,
            expected_revision=session.revision,
            expected_digest=ground_session_record_digest(session),
            verify_bound_frames=True,
        )
        session = next_session

    bound = bind_ground_workbench(
        session,
        description=(
            "Infer and test a synthetic, deterministic organization-name to "
            "symbol policy from reviewed propositions. Symbols are generated "
            "test expectations, not official market data."
        ),
        raw_context=raw,
        derived_context=candidates,
        target_contexts=(target,),
        target_requirements=(
            GroundTargetSpec(
                context_name=target.name,
                description="One reviewed synthetic ticker policy.",
                role="PUBLICATION_TARGET",
                minimum_accepted_cases=1,
            ),
        ),
    )
    save_transition(bound)
    save_transition(upgrade_ground_to_propositions(session))

    emit("provider-connect")
    started = time.monotonic()
    provider = CodexChatGPTProvider.connect(
        timeout=600,
        model="gpt-5.6-sol",
        reasoning_effort="none",
    )
    report["provider_connect_seconds"] = round(time.monotonic() - started, 3)

    emit("initial-elaborate-goal")
    started = time.monotonic()
    frozen_goal = freeze_ground_elaborate(
        store,
        ground_name=GROUND_NAME,
        direction="GOAL_TO_RULES",
    )
    initial_elaborate = execute_ground_elaborate(
        frozen_goal,
        store=store,
        provider_factory=lambda: provider,
    )
    report["initial_goal_elaborate"] = {
        **serialize_elaborate(initial_elaborate.elaborate),
        "seconds": round(time.monotonic() - started, 3),
    }
    write_json(REPORT_PATH, report)

    added = 0
    reviewed_rule_uid: str | None = None
    rounds = report["rounds"]
    assert isinstance(rounds, list)

    for threshold in THRESHOLDS:
        emit("add-examples", threshold=threshold, previous=added)
        for index in range(added, threshold):
            name, symbol, boundary = CASES[index]
            proposed = propose_ground_example(
                session,
                proposition=proposition(name, symbol),
                rationale=f"Synthetic reviewed {boundary} case.",
                current_contexts=current_contexts(),
                input_text=name,
                expected_output=symbol,
                case_role=(
                    "BOUNDARY"
                    if boundary
                    not in {"ordinary multiword initials", "ordinary legal suffix"}
                    else "FIT"
                ),
                disposition="INCLUDE",
                origin="USER",
            )
            save_transition(proposed)
            example_uid = next(
                item.uid
                for item in reversed(session.items)
                if item.kind == "CASE" and item.status == "PROPOSED"
            )
            accepted = review_ground_item(
                session,
                example_uid,
                action="ACCEPT",
                current_contexts=current_contexts(),
            )
            save_transition(accepted)
        added = threshold

        round_record: dict[str, object] = {
            "example_count": threshold,
            "ground_revision_before_semantics": session.revision,
        }
        rounds.append(round_record)
        write_json(REPORT_PATH, report)

        emit("distill", threshold=threshold, revision=session.revision)
        started = time.monotonic()
        frozen_distill = freeze_ground_distill(store, ground_name=GROUND_NAME)
        distill_result = execute_ground_distill(
            frozen_distill,
            store=store,
            provider_factory=lambda: provider,
        )
        round_record["distill"] = {
            **serialize_distill(distill_result.distill),
            "seconds": round(time.monotonic() - started, 3),
        }
        next_rule_text = composite_rule(distill_result.distill)

        emit("review-distilled-rule", threshold=threshold, characters=len(next_rule_text))
        if reviewed_rule_uid is None:
            proposed_rule = propose_ground_rule(
                session,
                rule=next_rule_text,
                rationale=(
                    f"Reviewed composite of the evidence-bound Distill proposal "
                    f"at {threshold} Examples."
                ),
                current_contexts=current_contexts(),
                rule_provenance="DISTILLED",
            )
            save_transition(proposed_rule)
            reviewed_rule_uid = next(
                item.uid
                for item in reversed(session.items)
                if item.kind == "RULE" and item.status == "PROPOSED"
            )
        else:
            refined_rule = review_ground_item(
                session,
                reviewed_rule_uid,
                action="REFINE",
                response=next_rule_text,
                current_contexts=current_contexts(),
            )
            save_transition(refined_rule)
        accepted_rule = review_ground_item(
            session,
            reviewed_rule_uid,
            action="ACCEPT",
            current_contexts=current_contexts(),
        )
        save_transition(accepted_rule)
        round_record["reviewed_rule"] = next_rule_text
        round_record["ground_revision_after_rule_review"] = session.revision

        emit("fit", threshold=threshold, revision=session.revision)
        started = time.monotonic()
        fit_result = run_fit_with_store(
            FitRequest(ground_name=GROUND_NAME),
            store=store,
            provider_factory=lambda: provider,
        )
        round_record["fit"] = {
            **serialize_fit(fit_result),
            "seconds": round(time.monotonic() - started, 3),
        }

        emit("elaborate-rules", threshold=threshold, revision=session.revision)
        started = time.monotonic()
        frozen_rules = freeze_ground_elaborate(
            store,
            ground_name=GROUND_NAME,
            direction="RULES_TO_CASES",
        )
        elaborate_cases = execute_ground_elaborate(
            frozen_rules,
            store=store,
            provider_factory=lambda: provider,
        )
        round_record["elaborate"] = {
            **serialize_elaborate(elaborate_cases.elaborate),
            "seconds": round(time.monotonic() - started, 3),
        }
        round_record["ground_revision_complete"] = session.revision
        write_json(REPORT_PATH, report)

        if threshold == 20:
            emit("stale-context-branch", threshold=threshold)
            shutil.copytree(STORE_ROOT, STALE_STORE_ROOT)
            stale_store = MemoryStore(root=STALE_STORE_ROOT)
            stale_candidates = stale_store.load_direct("ticker/examples")
            stale_candidates.add(
                Memory(
                    uid=str(uuid.uuid4()),
                    content="A newly added Context Memory after Ground binding.",
                )
            )
            stale_store.save(stale_candidates)
            stale_session = stale_store.load_ground_session(GROUND_NAME)
            assert stale_session is not None
            stale_results: dict[str, object] = {}

            try:
                freeze_ground_distill(stale_store, ground_name=GROUND_NAME)
            except Exception as error:
                stale_results["distill"] = {
                    "blocked_before_provider": True,
                    "error": f"{type(error).__name__}: {error}",
                }
            else:
                stale_results["distill"] = {"blocked_before_provider": False}

            try:
                propose_ground_example(
                    stale_session,
                    proposition="A stale-binding Example must not be accepted.",
                    rationale="stale branch probe",
                    current_contexts=tuple(
                        stale_store.load_direct(name)
                        for name in ("ticker/raw", "ticker/examples", "ticker/rules")
                    ),
                )
            except Exception as error:
                stale_results["ground_example_edit"] = {
                    "blocked": True,
                    "error": f"{type(error).__name__}: {error}",
                }
            else:
                stale_results["ground_example_edit"] = {"blocked": False}

            class ProviderWasConstructed(RuntimeError):
                pass

            def provider_spy():
                raise ProviderWasConstructed("provider factory reached")

            try:
                run_fit_with_store(
                    FitRequest(ground_name=GROUND_NAME),
                    store=stale_store,
                    provider_factory=provider_spy,
                )
            except ProviderWasConstructed as error:
                stale_results["fit"] = {
                    "blocked_before_provider": False,
                    "error": str(error),
                }
            except Exception as error:
                stale_results["fit"] = {
                    "blocked_before_provider": True,
                    "error": f"{type(error).__name__}: {error}",
                }
            else:
                stale_results["fit"] = {"blocked_before_provider": False}

            try:
                frozen_stale_elaborate = freeze_ground_elaborate(
                    stale_store,
                    ground_name=GROUND_NAME,
                    direction="RULES_TO_CASES",
                )
                execute_ground_elaborate(
                    frozen_stale_elaborate,
                    store=stale_store,
                    provider_factory=provider_spy,
                )
            except ProviderWasConstructed as error:
                stale_results["elaborate"] = {
                    "blocked_before_provider": False,
                    "error": str(error),
                }
            except Exception as error:
                stale_results["elaborate"] = {
                    "blocked_before_provider": True,
                    "error": f"{type(error).__name__}: {error}",
                }
            else:
                stale_results["elaborate"] = {"blocked_before_provider": False}

            report["stale_branch"] = stale_results
            write_json(REPORT_PATH, report)

    final_session = store.load_ground_session(GROUND_NAME)
    assert final_session is not None
    report["final"] = {
        "ground_uid": final_session.uid,
        "ground_revision": final_session.revision,
        "ground_digest": ground_session_record_digest(final_session),
        "example_count": len(
            [item for item in final_session.items if item.kind == "CASE"]
        ),
        "accepted_example_count": len(
            [
                item
                for item in final_session.items
                if item.kind == "CASE" and item.status == "ACCEPTED"
            ]
        ),
        "active_rule_count": len(
            [
                item
                for item in final_session.items
                if item.kind == "RULE"
                and item.status in {"PROPOSED", "ACCEPTED"}
            ]
        ),
        "status": final_session.status,
    }
    report["status"] = "COMPLETED"
    write_json(REPORT_PATH, report)
    emit("completed", rounds=len(THRESHOLDS), examples=50)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BaseException as error:
        if REPORT_PATH.exists():
            try:
                report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
            except Exception:
                report = {}
            report["status"] = "FAILED"
            report["failure"] = {
                "type": type(error).__name__,
                "message": str(error),
                "traceback": traceback.format_exc(),
            }
            write_json(REPORT_PATH, report)
        emit("failed", error_type=type(error).__name__, message=str(error))
        raise
