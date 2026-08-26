#!/usr/bin/env python3
"""Finalize task-1 ADMIN classifications without invoking mem."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PHASE = ROOT / "phase-admin.json"
ISSUES = ROOT / "issues.json"
SUMMARY = ROOT / "issues-admin.md"


ADMIN_ISSUES = [
    {
        "id": "T1-V2-ADMIN-HARNESS-POST-DIGEST-INTERRUPTION",
        "title": "Audit harness interruption lost Eval stdout after the child had exited",
        "expected": "The world runner should persist the child output and attempt record before an operator interruption can leave a counted call unrecorded.",
        "actual": "Eval M2 completed a durable 1/1 PASS run and the mandatory post-child identity assertion passed, but Ctrl-C arrived during the subsequent lane digest. The in-process stdout/cost wrapper was lost before phase-admin persistence.",
        "workaround": "Recover the counted attempt from the unique durable Eval run JSON and exact post-child identity host read; never rerun the mem command.",
        "severity": "low",
        "classification": "audit-harness-infrastructure",
        "evidence_ids": ["T1-V2-ADMIN-025"],
    },
    {
        "id": "T1-V2-ADMIN-SAME-PROFILE-CONTEXT-IMPORT-COLLISION",
        "title": "Same-world Context Import cannot create an aliased by-value scratch copy",
        "expected": "Importing a registered task-1 Context by value under a fresh scratch name should either create an independent identity or expose an explicit same-Profile copy route.",
        "actual": "Both direct and recursive Context Import stopped because the managed source Context UID already existed in the active Study Profile, even though each `--as` destination was fresh. Exact Memory Import into scratch later succeeded.",
        "workaround": "Use exact Memory Import for a selective by-value copy, or Branch/Copy within the active Profile when source identity already exists.",
        "severity": "medium",
        "classification": "operation-boundary/usability",
        "evidence_ids": ["T1-V2-ADMIN-012", "T1-V2-ADMIN-028"],
    },
    {
        "id": "T1-V2-ADMIN-INIT-MISSING-PARENT-AUTO-CREATES",
        "title": "Init creates a missing parent chain without --parents",
        "expected": "`init task-1/participant/admin-v2-scratch/missing-parent/leaf` should reject the absent lexical parent unless `--parents` is supplied, keeping the explicit parent-expansion method distinct.",
        "actual": "The command exited 0 and initialized the leaf even though `missing-parent` did not exist and `--parents` was absent.",
        "workaround": "Host-check the parent catalog before Init when missing-parent creation would broaden scope; use `--parents` only when the full chain is intentional.",
        "severity": "medium",
        "classification": "functional/creation-boundary",
        "evidence_ids": ["T1-V2-ADMIN-094"],
    },
]

SEQUENCE_ISSUES = {
    12: ["T1-V2-ADMIN-SAME-PROFILE-CONTEXT-IMPORT-COLLISION"],
    25: ["T1-V2-ADMIN-HARNESS-POST-DIGEST-INTERRUPTION"],
    28: ["T1-V2-ADMIN-SAME-PROFILE-CONTEXT-IMPORT-COLLISION"],
    94: ["T1-V2-ADMIN-INIT-MISSING-PARENT-AUTO-CREATES"],
}


def main() -> None:
    phase = json.loads(PHASE.read_text())
    records = sorted((record for payload in phase["operations"].values() for record in payload["attempts"]), key=lambda record: record["sequence"])
    for record in records:
        record["defect_ids"] = SEQUENCE_ISSUES.get(record["sequence"], [])
    phase["issues"] = ADMIN_ISSUES
    phase["safety"] = {
        "counted_invocations_used_pinned_runner": True,
        "counted_invocations": len(records),
        "counted_replays": 0,
        "external_share_deliveries": 0,
        "all_share_delivery_digests_unchanged": all(record.get("share_evidence", {}).get("unchanged") for record in phase["operations"]["share"]["attempts"]),
        "successful_init_study_creations": 0,
        "uuid_shaped_or_bare_non_tty_init_study_m5_used": False,
        "post_call_identity_assertions": 105,
        "active_profile_identity_preserved": True,
        "stack_builder_errors": 0,
        "all_producer_source_branch_checkpoint_gates_zero": True,
        "branch_or_checkout_targets_successfully_renamed": False,
        "entry_current_context_restored": True,
        "tui_used": False,
    }
    phase["completion_summary"] = {
        "result": "Captured all 105 counted ADMIN attempts in five interleaved methods on one cumulative Store; restored ENTRY practice; no Share delivery or Study activation occurred.",
        "transactions": "Branch1, recursive Branch2, Checkout3, and Checkout4 exact stack units passed host UID/member/granted-target gates. Checkout4 protected Undo failed while locked and succeeded after Unlock in round 5.",
        "instrumentation": "Eval M2 stdout was recovered from its unique durable PASS run after a harness interruption; the mem command was not replayed.",
        "positive_controls": "Rename M2/M3 succeeded only on init-created scratch. Rename M1 was inconclusive because same-world Context Import failed on an existing identity; no Branch/Checkout target was renamed.",
    }
    PHASE.write_text(json.dumps(phase, ensure_ascii=False, indent=2) + "\n")

    registry = json.loads(ISSUES.read_text())
    by_id = {issue["id"]: issue for issue in registry.get("issues", [])}
    for issue in ADMIN_ISSUES:
        by_id[issue["id"]] = issue
    registry["issues"] = list(by_id.values())
    ISSUES.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n")

    lines = ["# Task-1 ADMIN issues", ""]
    for issue in ADMIN_ISSUES:
        lines.extend([
            f"## {issue['id']} — {issue['title']}", "",
            f"- Severity: {issue['severity']}",
            f"- Classification: {issue['classification']}",
            f"- Expected: {issue['expected']}",
            f"- Actual: {issue['actual']}",
            f"- Workaround: {issue['workaround']}",
            f"- Evidence: {', '.join(issue['evidence_ids'])}", "",
        ])
    SUMMARY.write_text("\n".join(lines))


if __name__ == "__main__":
    main()
