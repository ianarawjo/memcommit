"""Retry the exact failed 50-Example Distill once, then finish if valid."""

from __future__ import annotations

from collections import Counter
import json
import time

from run_live_flow import (
    GROUND_NAME,
    REPORT_PATH,
    STORE_ROOT,
    composite_rule,
    emit,
    serialize_distill,
    serialize_elaborate,
    serialize_fit,
    write_json,
)

from memcommit.fit_application import FitRequest
from memcommit.fit_runtime import run_fit_with_store
from memcommit.ground import review_ground_item
from memcommit.ground_distill import execute_ground_distill, freeze_ground_distill
from memcommit.ground_elaborate import (
    execute_ground_elaborate,
    freeze_ground_elaborate,
)
from memcommit.query_provider import CodexChatGPTProvider
from memcommit.store import MemoryStore, ground_session_record_digest


def main() -> int:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    if report.get("status") != "FAILED" or len(report.get("rounds", [])) != 7:
        raise RuntimeError("The expected first failed 50-Example run is unavailable.")
    report["first_failure"] = report.pop("failure", None)
    round_record = report["rounds"][-1]
    if round_record.get("example_count") != 50 or "distill" in round_record:
        raise RuntimeError("The final round is not at the expected retry boundary.")

    store = MemoryStore(root=STORE_ROOT)
    session = store.load_ground_session(GROUND_NAME)
    if session is None:
        raise RuntimeError("The failed run did not preserve its Ground.")

    def current_contexts():
        return tuple(
            store.load_direct(name)
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

    emit("retry-provider-connect", attempt=2)
    provider = CodexChatGPTProvider.connect(
        timeout=600,
        model="gpt-5.6-sol",
        reasoning_effort="none",
    )
    emit("retry-distill", threshold=50, attempt=2, revision=session.revision)
    started = time.monotonic()
    try:
        frozen = freeze_ground_distill(store, ground_name=GROUND_NAME)
        retried = execute_ground_distill(
            frozen,
            store=store,
            provider_factory=lambda: provider,
        )
    except Exception as error:
        report["retry_failure"] = {
            "type": type(error).__name__,
            "message": str(error),
            "seconds": round(time.monotonic() - started, 3),
        }
        report["status"] = "FAILED_AFTER_EXACT_RETRY"
        write_json(REPORT_PATH, report)
        emit("retry-failed", error_type=type(error).__name__, message=str(error))
        return 1

    round_record["distill"] = {
        **serialize_distill(retried.distill),
        "seconds": round(time.monotonic() - started, 3),
        "attempt": 2,
        "first_attempt_rejected": True,
    }
    next_rule_text = composite_rule(retried.distill)
    active_rules = [
        item
        for item in session.items
        if item.kind == "RULE" and item.status in {"PROPOSED", "ACCEPTED"}
    ]
    if len(active_rules) != 1:
        raise RuntimeError("The retry expected one reviewed composite Rule.")
    rule_uid = active_rules[0].uid
    refined = review_ground_item(
        session,
        rule_uid,
        action="REFINE",
        response=next_rule_text,
        current_contexts=current_contexts(),
    )
    save_transition(refined)
    accepted = review_ground_item(
        session,
        rule_uid,
        action="ACCEPT",
        current_contexts=current_contexts(),
    )
    save_transition(accepted)
    round_record["reviewed_rule"] = next_rule_text
    round_record["ground_revision_after_rule_review"] = session.revision

    emit("retry-fit", threshold=50, revision=session.revision)
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

    emit("retry-elaborate-rules", threshold=50, revision=session.revision)
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
    report["final"] = {
        "ground_uid": session.uid,
        "ground_revision": session.revision,
        "ground_digest": ground_session_record_digest(session),
        "example_count": len(
            [item for item in session.items if item.kind == "CASE"]
        ),
        "accepted_example_count": len(
            [
                item
                for item in session.items
                if item.kind == "CASE" and item.status == "ACCEPTED"
            ]
        ),
        "active_rule_count": len(
            [
                item
                for item in session.items
                if item.kind == "RULE"
                and item.status in {"PROPOSED", "ACCEPTED"}
            ]
        ),
        "status": session.status,
    }
    report["status"] = "COMPLETED_AFTER_EXACT_RETRY"
    write_json(REPORT_PATH, report)
    emit("retry-completed", examples=50, rounds=7)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
