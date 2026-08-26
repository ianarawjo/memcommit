#!/usr/bin/env python3
"""Attach reviewed ticker CORE issue dispositions to the immutable attempt ledger."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path("/Users/KimMunyeong/Github/memcommit")
WORLD = ROOT / "agent-records/outputs/study-long-audit-20260825-v2/worlds/ticker"
PHASE = WORLD / "phase-core.json"


ISSUES = [
    {
        "id": "TICK-V2-CONTEXTS-01",
        "title": "Ticker orientation still requires a whole-Profile scan",
        "expected": "A maintainer can focus Context discovery on the five lane-local ticker roles while preserving current and Grant annotations.",
        "actual": "All five calls emitted the same 112-line whole-Profile catalog. The operation accepts no focus operand, so unrelated worlds and Grants occupy more than two 52-row screens at every checkpoint.",
        "workaround": "Locate the reused ticker role Contexts once, then use exact direct operands on every operation that supports them.",
        "severity": "MEDIUM",
        "classification": "USABILITY_INFORMATION_OVERLOAD",
        "reproduction": "5/5 attempts",
        "evidence": [
            "worlds/ticker/raw/core/001-contexts-attempt-1.stdout.txt",
            "worlds/ticker/raw/core/022-contexts-attempt-2.stdout.txt",
            "worlds/ticker/raw/core/043-contexts-attempt-3.stdout.txt",
            "worlds/ticker/raw/core/064-contexts-attempt-4.stdout.txt",
            "worlds/ticker/raw/core/085-contexts-attempt-5.stdout.txt",
        ],
    },
    {
        "id": "TICK-V2-CHUNK-RECEIPT-01",
        "title": "Successful Chunk receipts omit every created Memory UID",
        "expected": "A mutating split receipt maps the old UID to every new UID so Edit, Move, Reference, and automation can consume the result directly.",
        "actual": "Four successful sentence, clause, punctuation, and length-bound splits showed the proposed text and only `Done — N memories added`; none printed a created UID or the removed Memory disposition.",
        "workaround": "Run exact List immediately, match fragment text and position, and manually recover the new UIDs.",
        "severity": "HIGH",
        "classification": "USABILITY_OUTPUT_REUSE",
        "reproduction": "4/4 successful splits; the fifth attempt was a deliberate unavailable-selector control",
        "evidence": [
            "worlds/ticker/raw/core/014-chunk-attempt-1.stdout.txt",
            "worlds/ticker/raw/core/035-chunk-attempt-2.stdout.txt",
            "worlds/ticker/raw/core/056-chunk-attempt-3.stdout.txt",
            "worlds/ticker/raw/core/077-chunk-attempt-4.stdout.txt",
            "worlds/ticker/raw/core/023-list-attempt-2.stdout.txt",
            "worlds/ticker/raw/core/044-list-attempt-3.stdout.txt",
        ],
    },
    {
        "id": "TICK-V2-AMBIG-TIMEOUT-INFRA-01",
        "title": "One direct ambiguity scan exceeded the audit provider-turn ceiling",
        "expected": "The bounded provider call returns a validated result or an operation-owned recoverable provider error within the audit ceiling.",
        "actual": "The direct `task-1` scan emitted no result and was terminated by the lane driver after 240 seconds. Four other ambiguity scans completed, including the late archive control.",
        "workaround": "Preserve the frozen Source and retry in a later campaign turn; no partial result exists to reuse.",
        "severity": "INFRASTRUCTURE",
        "classification": "PROVIDER_INFRASTRUCTURE_TIMEOUT_NOT_PRODUCT_DEFECT",
        "reproduction": "1/5 attempts",
        "evidence": [
            "worlds/ticker/raw/core/082-find-ambiguities-attempt-4.stderr.txt",
            "worlds/ticker/raw/core/103-find-ambiguities-attempt-5.stdout.txt",
        ],
    },
]


def main() -> None:
    phase = json.loads(PHASE.read_text())
    issue_by_sequence = {
        **{sequence: ["TICK-V2-CONTEXTS-01"] for sequence in (1, 22, 43, 64, 85)},
        **{sequence: ["TICK-V2-CHUNK-RECEIPT-01"] for sequence in (14, 35, 56, 77)},
        82: ["TICK-V2-AMBIG-TIMEOUT-INFRA-01"],
    }
    attempts = [
        attempt
        for operation in phase["operations"].values()
        for attempt in operation["attempts"]
    ]
    for attempt in attempts:
        attempt["defect_ids"] = issue_by_sequence.get(attempt["sequence"], [])

    expected_overrides = {
        16: "Reject the comparison cleanly because the exact examples peer is still empty in round 1.",
        50: "Reject recursive summarization atomically when an immutable snapshot and later live Memory expose divergent content for one identity.",
        58: "Reject overlapping recursive endpoints when one evidence identity is reachable on both sides.",
        79: "Reject asymmetric peers when archive Embeds re-expose an identity already present under the workspace reference side.",
        92: "Reject recursive summarization atomically when historical References and live descendants expose divergent content for one identity.",
        100: "Reject the comparison because tests live-Embed the rules endpoint and therefore expose the same identity on both sides.",
    }
    for attempt in attempts:
        if attempt["sequence"] in expected_overrides:
            attempt["expected"] = expected_overrides[attempt["sequence"]]

    phase["workspace_mapping"]["initial_direct_memory_counts"] = {
        "task-2": 0,
        "task-2/participant": 0,
        "task-2/participant/proposal-workspace": 0,
        "task-1": 0,
        "task-3": 0,
    }
    phase["workspace_mapping"]["initial_empty_set_verification"] = (
        "Verified from each exact lane-local context.json before sequence 1; "
        "the first durable ticker mutation was counted Add sequence 3."
    )
    phase["campaign_limitations"] = [
        {
            "id": "TICK-V2-NO-DEDICATED-CONTEXT",
            "classification": "CAMPAIGN_FIXTURE_LIMITATION_NOT_PRODUCT_DEFECT",
            "detail": "The frozen template contained no dedicated ticker Context and prohibited uncounted bootstrap commands. Five empty direct fixture Contexts were reused.",
        },
        {
            "id": "TICK-V2-RECURSIVE-DESCENDANT-NOISE",
            "classification": "DELIBERATE_NOISY_BOUNDARY_NOT_CLEAN_TICKER_EVIDENCE",
            "detail": "Recursive reads under task-2/task-3 also expose their pre-existing local and granted semantic descendants. Exact/direct attempts are the clean ticker evidence; recursive attempts measure overload and identity safety boundaries.",
            "evidence": [
                "worlds/ticker/raw/core/023-list-attempt-2.stdout.txt",
                "worlds/ticker/raw/core/060-find-redundancies-attempt-3.stdout.txt",
                "worlds/ticker/raw/core/102-find-redundancies-attempt-5.stdout.txt",
            ],
        },
    ]
    phase["reviewed_nondefects"] = [
        {
            "id": "TICK-V2-IDENTITY-DIVERGENCE-SAFETY",
            "detail": "Recursive Summarize rejected historical Reference/live divergence for one Memory identity atomically in sequences 50 and 92.",
        },
        {
            "id": "TICK-V2-COMPARE-OVERLAP-SAFETY",
            "detail": "Compare rejected empty or overlapping endpoint frames in sequences 16, 58, 79, and 100; the disjoint Memory-to-Memory control in sequence 37 succeeded.",
        },
    ]
    phase["issues"] = [issue["id"] for issue in ISSUES]
    PHASE.write_text(json.dumps(phase, ensure_ascii=False, indent=2) + "\n")
    payload = {"world": "ticker", "phase": "core", "issues": ISSUES}
    (WORLD / "issues-core.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    (WORLD / "issues.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
