#!/usr/bin/env python3
"""Finalize task-1 TRANSFORM evidence without invoking mem again."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PHASE = ROOT / "phase-transform.json"
ISSUES = ROOT / "issues.json"
SUMMARY = ROOT / "issues-transform.md"


TRANSFORM_ISSUES = [
    {
        "id": "T1-V2-ATOMIZE-WHOLE-FRAME-UNCERTAIN",
        "title": "Whole-frame Atomize cannot reach semantic chunk normal form",
        "expected": "Whole direct construction frames should either produce complete reviewable Atomize sessions or identify a bounded input-size/schema limit before provider work.",
        "actual": "The 19-Memory facility frame ran for 51.07 s and returned 14 UNCERTAIN dispositions; the 15-Memory parking frame ran for 42.54 s and returned one UNCERTAIN disposition. Both rejected the whole result with no Context publication, while three focused-Memory routes succeeded.",
        "workaround": "Use exact Memory Atomize routes and review each source-bound result; do not treat focused success as whole-frame coverage.",
        "severity": "medium",
        "classification": "provider-schema-infrastructure/reliability",
        "evidence_ids": ["T1-V2-TRANSFORM-001", "T1-V2-TRANSFORM-073"],
    },
    {
        "id": "T1-V2-AUDIT-CROSS-FRAME-LATENCY",
        "title": "Cross-frame Audit approaches or exceeds the bounded call timeout",
        "expected": "A complete saved cross-Context Audit should finish within the declared 300-second bounded-call window or fail early with a size/cost diagnostic.",
        "actual": "Building-access against route-changes reached the 300-second harness timeout with no completed artifact; temporary-parking against building-access completed only after 252.01 s. Single-frame Audits completed in 18.29–30.38 s.",
        "workaround": "Run single-frame Audit snapshots and a separate Check Conformance call for the cross-area rule frame, preserving both receipts.",
        "severity": "medium",
        "classification": "provider-infrastructure/performance",
        "evidence_ids": ["T1-V2-TRANSFORM-050", "T1-V2-TRANSFORM-074"],
    },
    {
        "id": "T1-V2-IMPACT-AUDIT-ROUTE-GAP",
        "title": "Impact cannot consume a saved Audit session",
        "expected": "A saved read-only Audit artifact should have an operation-aware Impact route, consistent with other saved semantic analysis sessions.",
        "actual": "`impact audit --session deadbeef` was rejected by the command router with `No such command 'audit'`; the failure occurred at routing before artifact lookup, even though Audit is a saved session family and `review audit` exists.",
        "workaround": "Use `review audit --session … --snapshot` to inspect the immutable artifact; no Audit-specific Impact preview is available.",
        "severity": "low",
        "classification": "operation-consistency/usability",
        "evidence_ids": ["T1-V2-TRANSFORM-063"],
    },
    {
        "id": "T1-V2-RATIONALE-LANGUAGE-DRIFT",
        "title": "Rationale unexpectedly switches from English to Chinese",
        "expected": "Rationale prose should follow the English source and surrounding CLI language unless a target language is explicitly requested.",
        "actual": "The first facility Rationale rendered its entire provenance explanation in Chinese. The four otherwise equivalent construction Rationale routes rendered English.",
        "workaround": "Use Trace for language-stable lineage facts, or rerun Rationale and manually verify its prose against the typed provenance events.",
        "severity": "medium",
        "classification": "provider-presentation/usability",
        "evidence_ids": ["T1-V2-TRANSFORM-018"],
    },
    {
        "id": "T1-V2-ELABORATE-UNSUPPORTED-DETAILS",
        "title": "Bounded Elaborate invents venue verification procedures",
        "expected": "The inline rule requiring only verified venues, dates, and reservation status should not produce concrete operational channels, active/pending booking states, or loading-entrance details absent from the verified construction Source.",
        "actual": "Elaborate created three UNVERIFIED/BEST_EFFORT Memories that introduced an auditorium reservation channel, active and pending booking states, and a separate loading entrance for equipment. These details were not in the verified event-relocation Memories.",
        "workaround": "Keep Elaborate output in checkpointed scratch, treat UNVERIFIED as non-publishable, and Revert unless every generated detail can be independently grounded.",
        "severity": "high",
        "classification": "semantic-integrity/unsupported-generation",
        "evidence_ids": ["T1-V2-TRANSFORM-033"],
    },
    {
        "id": "T1-V2-AUDIT-HARNESS-SESSION-PARSE",
        "title": "Audit evidence runner did not recover bracketed session IDs",
        "expected": "The audit harness should recover the saved `SESSION [uid]` token so the later counted Review can consume that exact artifact.",
        "actual": "The world-local runner recognized only a printed `mem review audit --session` command, not Audit's actual `SESSION [uid]` header, so Review attempts 1 and 4 used the sentinel `deadbeef` and failed. The underlying Audit artifacts were successfully saved.",
        "workaround": "Read the bracketed SESSION UID from raw Audit output; do not attribute these Review failures to the product.",
        "severity": "low",
        "classification": "audit-harness-infrastructure",
        "evidence_ids": ["T1-V2-TRANSFORM-002", "T1-V2-TRANSFORM-020", "T1-V2-TRANSFORM-074", "T1-V2-TRANSFORM-092"],
    },
]

SEQUENCE_ISSUES = {
    1: ["T1-V2-ATOMIZE-WHOLE-FRAME-UNCERTAIN"],
    18: ["T1-V2-RATIONALE-LANGUAGE-DRIFT"],
    20: ["T1-V2-AUDIT-HARNESS-SESSION-PARSE"],
    33: ["T1-V2-ELABORATE-UNSUPPORTED-DETAILS"],
    50: ["T1-V2-AUDIT-CROSS-FRAME-LATENCY"],
    63: ["T1-V2-IMPACT-AUDIT-ROUTE-GAP"],
    73: ["T1-V2-ATOMIZE-WHOLE-FRAME-UNCERTAIN"],
    74: ["T1-V2-AUDIT-CROSS-FRAME-LATENCY", "T1-V2-AUDIT-HARNESS-SESSION-PARSE"],
    92: ["T1-V2-AUDIT-HARNESS-SESSION-PARSE"],
}


def main() -> None:
    phase = json.loads(PHASE.read_text())
    phase["study"] = "study-long-audit-20260825-v2"
    records = sorted(
        (record for payload in phase["operations"].values() for record in payload["attempts"]),
        key=lambda record: record["sequence"],
    )
    for record in records:
        record["defect_ids"] = SEQUENCE_ISSUES.get(record["sequence"], [])
    phase["issues"] = TRANSFORM_ISSUES
    phase["coverage_derivation"] = {
        "continuity_breaks": "count(attempt.state_continuity_facts.same_as_previous_post == false)",
        "durable_context_tree_mutations": "legacy field name; count(attempt.pre_target_digest != attempt.post_target_digest) over the whole profile-control lane digest, not a claim that every call changed semantic Context content",
        "lane_digest_changed_attempts": sum(
            record["pre_target_digest"] != record["post_target_digest"] for record in records
        ),
    }
    phase["safety"] = {
        "counted_invocations_used_pinned_runner": True,
        "external_share_or_disclosure": False,
        "unsupported_fact_approval": False,
        "ambiguous_meaning_apply": False,
        "clipboard_use": False,
        "writes_outside_lane": False,
        "tui_used": False,
        "all_five_scratch_reverts_succeeded": all(
            record["exit"] == 0 for record in phase["operations"]["revert"]["attempts"]
        ),
        "public_wiki_writes_in_transform": False,
    }
    phase["completion_summary"] = {
        "goal": "Preserve the completed campus-wiki contribution while exercising transform operations against verified construction Memories and recoverable lane-local scratch.",
        "result": "All 120 counted transform commands completed; every destructive round was recovered by its same-round checkpoint Revert; verified construction Sources and contributed public wiki areas were not mutated by transform.",
        "infrastructure_note": "One Audit timed out at 300 seconds; two Review failures were caused by the world-local runner's Audit session-token parser and are not product failures.",
    }
    PHASE.write_text(json.dumps(phase, ensure_ascii=False, indent=2) + "\n")

    registry = json.loads(ISSUES.read_text())
    existing = {issue["id"]: issue for issue in registry.get("issues", [])}
    for issue in TRANSFORM_ISSUES:
        existing[issue["id"]] = issue
    registry["issues"] = list(existing.values())
    ISSUES.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n")

    lines = [
        "# Task-1 transform issues",
        "",
        "Transform completed 24 operations × 5 materially different routes with one cumulative no-reset Store.",
        "",
    ]
    for issue in TRANSFORM_ISSUES:
        lines.extend(
            [
                f"## {issue['id']} — {issue['title']}",
                "",
                f"- Severity: {issue['severity']}",
                f"- Classification: {issue['classification']}",
                f"- Expected: {issue['expected']}",
                f"- Actual: {issue['actual']}",
                f"- Workaround: {issue['workaround']}",
                f"- Evidence: {', '.join(issue['evidence_ids'])}",
                "",
            ]
        )
    SUMMARY.write_text("\n".join(lines))


if __name__ == "__main__":
    main()
