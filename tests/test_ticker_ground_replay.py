from __future__ import annotations

import json

from memcommit.distill import DISTILL_OPERATION, DISTILL_PAYLOAD_MARKER
from memcommit.elaborate import ELABORATE_OPERATION, ELABORATE_PAYLOAD_MARKER
from memcommit.eval.ticker_ground_replay import (
    TICKER_REFINED_GOAL,
    run_ticker_ground_replay,
)
from memcommit.eval.ticker_ground_workflow import load_ticker_workflow
from memcommit.fit_judgment import (
    FIT_JUDGMENT_OPERATION,
    FIT_JUDGMENT_PAYLOAD_MARKER,
)


class _DeterministicTickerReplayProvider:
    def __init__(self) -> None:
        self.prompts: list[tuple[str, str]] = []
        self.distill_calls = 0
        self.fit_calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        assert output_schema is not None
        self.prompts.append((operation, prompt))
        if operation == ELABORATE_OPERATION:
            payload = json.loads(prompt.split(ELABORATE_PAYLOAD_MARKER, 1)[1])
            if payload["mode"] == "GOAL_TO_RULES":
                return json.dumps(
                    {
                        "overview": "The vague Goal needs one testable hypothesis.",
                        "rules": [
                            {
                                "content": (
                                    "Use a short uppercase mnemonic derived from "
                                    "the reviewed company name."
                                ),
                                "rationale": (
                                    "This makes the vague Goal inspectable without "
                                    "claiming an official ticker algorithm."
                                ),
                            }
                        ],
                    }
                )
            return json.dumps(
                {
                    "overview": "One unverified boundary Case could probe the Rules.",
                    "cases": [
                        {
                            "proposition": (
                                "An unseen synthetic company name may expose an "
                                "unhandled normalization boundary."
                            ),
                            "expected": "Review rather than guess.",
                            "rationale": "This suggestion is intentionally unverified.",
                            "case_role": "BOUNDARY",
                            "source_rule_index": 1,
                        }
                    ],
                }
            )
        if operation == DISTILL_OPERATION:
            self.distill_calls += 1
            payload = json.loads(prompt.split(DISTILL_PAYLOAD_MARKER, 1)[1])
            aliases = [
                memory["memory_id"]
                for memory in payload["source"]["memories"]
            ]
            return json.dumps(
                {
                    "overview": (
                        f"Round {self.distill_calls} accounts for every revealed "
                        "Example."
                    ),
                    "rules": [
                        {
                            "content": (
                                f"At replay round {self.distill_calls}, treat every "
                                "revealed synthetic ticker proposition as a reviewed "
                                "constraint and preserve any stated unresolved boundary."
                            ),
                            "rationale": (
                                "Every currently revealed proposition is cited by this "
                                "bounded evaluation Rule."
                            ),
                            "support_memory_ids": aliases,
                            "boundary_memory_ids": [],
                        }
                    ],
                    "outside_memory_ids": [],
                }
            )
        assert operation == FIT_JUDGMENT_OPERATION
        self.fit_calls += 1
        payload = json.loads(prompt.split(FIT_JUDGMENT_PAYLOAD_MARKER, 1)[1])
        first_fit = self.fit_calls == 1
        judgments = []
        for question in payload["questions"]:
            considered = [
                item["proposition_id"]
                for item in (*question["background"], *question["propositions"])
            ]
            material = [
                item["proposition_id"] for item in question["propositions"]
            ]
            judgments.append(
                {
                    "question_id": question["question_id"],
                    "verdict": "MAY" if first_fit else "YES",
                    "reason": (
                        "The initial hypothesis leaves an ordinary reading split."
                        if first_fit
                        else "The reviewed constraint set is jointly coherent."
                    ),
                    "considered_proposition_ids": considered,
                    "material_proposition_ids": material if first_fit else [],
                    "consistent_reading": (
                        "The mnemonic can follow the reviewed Example."
                        if first_fit
                        else ""
                    ),
                    "inconsistent_reading": (
                        "The vague mnemonic hypothesis permits another output."
                        if first_fit
                        else ""
                    ),
                }
            )
        return json.dumps(
            {
                "overview": (
                    "The first hypothesis remains ambiguous."
                    if first_fit
                    else "Every revealed Example fits the reviewed Rules."
                ),
                "judgments": judgments,
            }
        )


def test_ticker_replay_runs_all_rounds_without_provider_label_leakage(tmp_path):
    corpus = load_ticker_workflow()
    provider = _DeterministicTickerReplayProvider()

    result = run_ticker_ground_replay(
        corpus,
        root=tmp_path / "store",
        semantic_provider_factory=lambda: provider,
    )

    assert result.final_example_count == 50
    assert result.explicit_unresolved_case_ids == ("t46", "t47", "t48", "t49")
    assert result.final_goal == TICKER_REFINED_GOAL
    assert len(result.final_rules) == 6
    assert provider.distill_calls == 5
    assert provider.fit_calls == 6
    kinds = [event.kind for event in result.events]
    assert kinds.count("EXAMPLE_PROPOSED") == 50
    assert kinds.count("EXAMPLE_ACCEPTED") == 50
    assert kinds.count("DISTILL_EXAMPLES") == 5
    assert kinds.count("ELABORATE_RULES") == 5
    assert kinds.count("RESOLVE_GOAL_APPLIED") == 1
    assert kinds.count("FIT_REOPENED_STALE") == 1
    assert kinds[-1] == "FINAL_VERIFICATION"
    assert all(
        event.revision_after == event.revision_before + 1
        for event in result.events
        if event.mutated
    )
    assert all(
        event.revision_after == event.revision_before
        for event in result.events
        if not event.mutated
    )

    provider_text = "\n".join(prompt for _operation, prompt in provider.prompts)
    for category in corpus.coverage_categories:
        assert category not in provider_text
    assert '"resolution"' not in provider_text
    assert '"categories"' not in provider_text
    assert '"role":"BOUNDARY"' not in provider_text

    restored = result.to_dict()
    assert restored["schema_version"] == 1
    assert restored["ground"]["final_example_count"] == 50


def test_ticker_replay_keeps_elaborated_cases_unapplied(tmp_path):
    provider = _DeterministicTickerReplayProvider()

    result = run_ticker_ground_replay(
        load_ticker_workflow(),
        root=tmp_path / "store",
        semantic_provider_factory=lambda: provider,
    )

    elaborated = [
        event for event in result.events if event.kind == "ELABORATE_RULES"
    ]
    assert len(elaborated) == 5
    assert all(not event.mutated for event in elaborated)
    assert all(
        event.payload["application"]
        == "NOT_APPLIED; frozen benchmark Examples remain authoritative"
        for event in elaborated
    )
    final = result.events[-1].payload
    assert final["all_examples_accepted_and_included"] is True
