#!/usr/bin/env python3
"""Verify the retained ticker replay evidence without calling a provider."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path


EVIDENCE_DIRECTORY = Path(__file__).resolve().parent


def _load(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE_DIRECTORY / name).read_text(encoding="utf-8"))


def main() -> int:
    failed = _load("failed-overlap-run.json")
    assert failed["run"]["status"] == "FAILED"
    assert len(failed["run"]["provider_calls"]) == 15
    assert "both support and boundary" in failed["run"]["error"]

    completed = _load("actual-run.json")
    assert completed["run"]["status"] == "COMPLETED"
    assert len(completed["run"]["provider_calls"]) == 17
    replay = completed["replay"]
    ground = replay["ground"]
    events = replay["events"]
    assert ground["final_example_count"] == 50
    assert ground["final_revision"] == 112
    assert ground["final_goal"] == "티커가 어떻게 만들어지는지 규칙을 알고 싶어"
    assert len(ground["final_rules"]) == 6
    assert replay["explicit_unresolved_case_ids"] == ["t46", "t47", "t48", "t49"]
    assert len(events) == 143
    assert all(
        event["revision_after"] == event["revision_before"] + 1
        for event in events
        if event["mutated"]
    )
    assert all(
        event["revision_after"] == event["revision_before"]
        for event in events
        if not event["mutated"]
    )
    kinds = Counter(event["kind"] for event in events)
    assert kinds["EXAMPLE_PROPOSED"] == 50
    assert kinds["EXAMPLE_ACCEPTED"] == 50
    assert kinds["RESOLVE_APPLIED"] == 6
    assert kinds["RULE_ACCEPTED"] == 6

    evaluation = completed["evaluation"]
    assert evaluation["final_all_examples_fit"] is False
    assert evaluation[
        "final_unresolved_boundaries_fit_without_fabricated_outputs"
    ] is True
    assert evaluation["fit_to_non_fit_regressions"] == []
    assert [round_["counts"] for round_ in evaluation["rounds"]] == [
        {"FIT": 5},
        {"FIT": 10},
        {"FIT": 18, "UNDERDETERMINED": 2},
        {"FIT": 33, "CONTRADICTS": 2},
        {"FIT": 48, "CONTRADICTS": 2},
    ]

    case_by_proposition = {
        event["payload"]["proposition"]: event["payload"]["case_id"]
        for event in events
        if event["kind"] == "EXAMPLE_PROPOSED"
    }
    final_fit = next(
        event
        for event in reversed(events)
        if event["kind"] == "FIT_AFTER_DISTILL"
    )
    non_fit = {
        case_by_proposition[judgment["proposition"]]: judgment
        for judgment in final_fit["payload"]["judgments"]
        if judgment["status"] != "FIT"
    }
    assert set(non_fit) == {"t23", "t24"}
    assert non_fit["t23"]["status"] == "CONTRADICTS"
    assert "actually matches" in non_fit["t23"]["reason"]
    assert "coherent" in non_fit["t23"]["reason"]
    assert "numeric token" in non_fit["t24"]["reason"]

    print(
        "Verified failed fail-closed run and completed 5→50 replay: "
        "48/50 FIT, no prior-FIT regressions, four unresolved boundaries preserved."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
