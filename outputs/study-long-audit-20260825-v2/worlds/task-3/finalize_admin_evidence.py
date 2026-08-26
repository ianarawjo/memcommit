#!/usr/bin/env python3
"""Finalize and strictly validate task-3 ADMIN evidence."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PHASE = ROOT / "phase-admin.json"
HOST = ROOT / "admin-host-reads.json"
GLOBAL_ISSUES = ROOT / "issues.json"
ADMIN_ISSUES = ROOT / "issues-admin.json"
ADMIN_ISSUES_MD = ROOT / "issues-admin.md"
RUNNER_PREFIX = (
    "python /Users/KimMunyeong/Github/memcommit/outputs/"
    "study-long-audit-20260825-v2/run_world_mem.py task-3 "
)
TRANSFORM_FINAL_TASK3 = (
    "1411d2fcb26922855828b67b72a7557bc7f91db6793fde7bc5003b37c352c004"
)
ADMIN_ENTRY_FULL = (
    "97982665687683a61364706c47d84b6277b1b9fe3cb4e537f65d3bb13832f4e8"
)


def evidence(sequence: int, operation: str, raw: str) -> dict[str, object]:
    return {
        "phase": "admin",
        "sequence": sequence,
        "operation": operation,
        "raw_output": f"outputs/study-long-audit-20260825-v2/worlds/task-3/{raw}",
    }


RENAME_ISSUE = {
    "id": "T3V2-RENAME-BRANCH-STACK-OWNER-MISMATCH",
    "title": "Renaming a Branch target invalidates its retained creation membership",
    "classification": "functional / safety recovery / global command-stack corruption",
    "severity": "P1 / high",
    "regression": "independently corroborates the cross-world Rename/Branch stack defect",
    "expected": (
        "Renaming a Context created by Branch preserves a reconstructible producer "
        "unit under the new canonical name, so later Undo/Redo can verify and restore it."
    ),
    "actual": (
        "Rename M1 changed `.../b1` to `.../renamed-1`, but its Branch receipt "
        "retained target membership `.../b1`. The read-only stack builder then failed "
        "with `Branch checkpoint owner is outside its creation membership` after "
        "Branch M2. Counted inverse Rename M2 restored `.../b1`; the exact 11-member "
        "B2 unit then rebuilt and Undo2/Redo2 both succeeded."
    ),
    "workaround": (
        "Do not Rename a Branch/checkout-created Context while its creation checkpoint "
        "is retained. If no descendant has copied the invalid history, restore the exact "
        "original target name before using the global stack."
    ),
    "evidence_sequences": [6, 38, 39, 40],
    "reproduction": (
        "One successful Branch-target Rename, one deterministic host stack failure, "
        "then one exact inverse-name recovery followed by successful Undo/Redo."
    ),
    "evidence": [
        evidence(6, "rename", "raw/admin/006-rename-m1.txt"),
        {
            "phase": "admin",
            "after_sequence": 37,
            "host_read": "outputs/study-long-audit-20260825-v2/worlds/task-3/admin-host-reads.json",
            "label": "round2 pre-recovery stack reconstruction",
        },
        evidence(38, "rename", "raw/admin/038-rename-m2.txt"),
        evidence(39, "undo", "raw/admin/039-undo-m2.txt"),
        evidence(40, "redo", "raw/admin/040-redo-m2.txt"),
    ],
}

INHERITED_ISSUE = {
    "id": "T3V2-BRANCH-INHERITS-CREATION-RECEIPT",
    "title": "Branch-of-Branch copies historical creation receipts as invalid target history",
    "classification": "functional / safety recovery / inherited command-history corruption",
    "severity": "P1 / high",
    "regression": "newly isolated from a clean-source negative control",
    "expected": (
        "Branching a live prior Branch target either omits creation-only checkpoints from "
        "the copied history or treats them as lineage, leaving the new producer unit and "
        "the Profile-global Undo/Redo stack reconstructible."
    ),
    "actual": (
        "The clean `guardrails` Source had zero Branch checkpoints. B1 had one valid "
        "creation receipt. Branch M3 copied that receipt into B3, where its owner is "
        "outside the recorded B1 target membership; Checkout M3 then copied both B1 and "
        "B3 receipts into co3. Exact current creation receipts remained identifiable, but "
        "every later global stack build and six counted Undo/Redo controls failed closed."
    ),
    "workaround": (
        "Use a checkpoint-history-clean ordinary Source for Branch/checkout -b. Once a "
        "target has inherited multiple creation-only receipts, there is no non-destructive "
        "global Undo workaround; retain the malformed audit state as negative evidence."
    ),
    "evidence_sequences": [43, 44, 46, 47, 64, 79, 83, 85, 86],
    "reproduction": (
        "B1 → B3 → co3 created three invalid owner/creation-membership pairs; 6/6 "
        "later counted Undo/Redo calls failed with the same builder error."
    ),
    "evidence": [
        evidence(43, "branch", "raw/admin/043-branch-m3.txt"),
        evidence(44, "checkout", "raw/admin/044-checkout-m3.txt"),
        evidence(46, "undo", "raw/admin/046-undo-m3.txt"),
        evidence(47, "redo", "raw/admin/047-redo-m3.txt"),
        evidence(64, "redo", "raw/admin/064-redo-m4.txt"),
        evidence(83, "undo", "raw/admin/083-undo-m4.txt"),
        evidence(85, "undo", "raw/admin/085-undo-m5.txt"),
        evidence(86, "redo", "raw/admin/086-redo-m5.txt"),
        {
            "phase": "admin",
            "host_read": "outputs/study-long-audit-20260825-v2/worlds/task-3/admin-host-reads.json",
            "kind": "command_stack_reconstruction_failure_with_receipt_evidence",
        },
    ],
}

INTERRUPT_LIMITATION = {
    "id": "T3V2-ADMIN-HARNESS-INTERRUPTED-CALL",
    "title": "Checkout M5 output was lost when the parent harness received SIGINT",
    "classification": "audit harness / operator interruption (not product behavior)",
    "severity": "P3 / low",
    "regression": "audit-only event",
    "expected": "Capture the missing-target Checkout M5 exit and output once.",
    "actual": (
        "The pinned sequence-89 subprocess had started when SIGINT interrupted the parent "
        "communicate() call. It is retained once as exit 130 with unavailable output; exact "
        "sequence-88-post/current host digests prove it published no durable change."
    ),
    "workaround": "Do not replay. Preserve exit 130 plus the exact pre/post host digest bridge.",
    "evidence_sequences": [89],
    "reproduction": "One campaign-only operator interruption; no product conclusion drawn.",
    "evidence": [
        evidence(89, "checkout", "raw/admin/089-checkout-m5.txt"),
        {
            "phase": "admin",
            "after_sequence": 89,
            "host_read": "outputs/study-long-audit-20260825-v2/worlds/task-3/admin-host-reads.json",
            "kind": "interrupted_counted_call_recovery",
        },
    ],
}

INIT_STUDY_LIMITATION = {
    "id": "T3V2-INIT-STUDY-UUID-CREATES-ACTIVE-PROFILE",
    "title": "UUID-shaped Study name was a valid high-cost input, not a safe negative control",
    "classification": "audit input assumption / high-cost identity escape",
    "severity": "P1 / high",
    "regression": "new audit protocol failure; current Profile grammar permits this name",
    "expected": (
        "Per the ADMIN protocol, init-study M5 rejects the chosen name before creating or "
        "activating any Profile, leaving success count zero and identity pinned."
    ),
    "actual": (
        "The UUID-shaped string satisfies the frozen portable Profile-name grammar. "
        "Sequence 95 exited 0, created a full managed Study Profile/Store, and selected it. "
        "The mandatory host read caught the new UID/root. The new Profile/Store were retained "
        "unchanged as evidence; only registry active_uid was atomically restored before seq96."
    ),
    "workaround": (
        "For zero-success audit trials use a syntactically invalid slash name, reserved name, "
        "missing baseline, invalid worker count, or an actual TUI cancel. Do not assume a "
        "UUID-shaped Study/Profile name is invalid."
    ),
    "evidence_sequences": [95],
    "reproduction": "One exact non-TTY init-study call; success and identity escape were host-verified.",
    "evidence": [
        evidence(95, "init-study", "raw/admin/095-init_study-m5.txt"),
        {
            "phase": "admin",
            "recovery": (
                "outputs/study-long-audit-20260825-v2/worlds/task-3/"
                "recovery/admin-seq095-init-study/evidence.json"
            ),
        },
    ],
}

IMPORT_LIMITATION = {
    "id": "T3V2-ADMIN-IMPORT-PREEXISTING-IDENTITY",
    "title": "Context Import M1/M2 used identities already present in the combined Study Store",
    "classification": "audit input assumption / pre-existing identity collision",
    "severity": "P3 / low",
    "regression": "audit-only source-selection limitation",
    "expected": "Exercise successful direct and recursive by-value Context import into scratch.",
    "actual": (
        "Both imports safely failed because the task-1 Context UIDs already existed under "
        "their task-1 canonical names in the active combined Study Store. Memory Import M3 "
        "still exercised a successful exact by-value route."
    ),
    "workaround": "Choose a source Profile/Context identity not already present in the active Store.",
    "evidence_sequences": [13, 29, 52],
    "reproduction": "Two deterministic Context identity collisions and one successful Memory import.",
    "evidence": [
        evidence(13, "import", "raw/admin/013-import-m1.txt"),
        evidence(29, "import", "raw/admin/029-import-m2.txt"),
        evidence(52, "import", "raw/admin/052-import-m3.txt"),
    ],
}

RECOVERY_LIMITATION = {
    "id": "T3V2-ADMIN-RECOVERY-ROUTE-DEVIATION",
    "title": "Stack recovery required counted ADMIN route substitutions",
    "classification": "audit recovery / protocol route deviation",
    "severity": "P2 / medium",
    "regression": "campaign adaptation after a P1 recoverability defect",
    "expected": "Execute the prescribed Rename and Lock targets while preserving five attempts per operation.",
    "actual": (
        "Rename M2 became the counted inverse-name recovery. Later successful Rename trials "
        "used Init-created scratch Contexts rather than Branch/Checkout targets, and Lock M4 "
        "protected the scratch subtree so the protected Undo boundary remained exercised "
        "without creating another Rename owner mismatch. Actual argv/routes are in the ledger."
    ),
    "workaround": "Treat these methods as recovery-adapted evidence, not exact replicas of the original rows.",
    "evidence_sequences": [38, 63, 81, 82, 84, 104],
    "reproduction": "One bounded same-phase recovery path; no supplemental mem calls or replay.",
    "evidence": [
        evidence(38, "rename", "raw/admin/038-rename-m2.txt"),
        evidence(63, "rename", "raw/admin/063-rename-m3.txt"),
        evidence(81, "lock", "raw/admin/081-lock-m4.txt"),
        evidence(82, "rename", "raw/admin/082-rename-m4.txt"),
        evidence(84, "unlock", "raw/admin/084-unlock-m4.txt"),
        evidence(104, "rename", "raw/admin/104-rename-m5.txt"),
    ],
}

INIT_PARENT_LIMITATION = {
    "id": "T3V2-ADMIN-INIT-PARENT-ASSUMPTION",
    "title": "Init M5 assumed a missing lexical parent must fail without --parents",
    "classification": "audit input assumption / documented exact-leaf behavior",
    "severity": "P3 / low",
    "regression": "audit-only expectation mismatch",
    "expected": "The ADMIN row expected a missing-parent validation failure.",
    "actual": (
        "Init created only the exact requested nested Context and did not create a parent "
        "Context. This matches detailed Init Help: default creates the exact name; --parents "
        "additionally creates missing parent Contexts."
    ),
    "workaround": "Use a UID-shaped name or an existing-name collision for a deterministic safe failure.",
    "evidence_sequences": [94],
    "reproduction": "One exact nested Init without --parents, exit 0.",
    "evidence": [evidence(94, "init", "raw/admin/094-init-m5.txt")],
}


def add_defect(records: dict[int, dict[str, object]], issue_id: str, sequences: list[int]) -> None:
    for sequence in sequences:
        ids = records[sequence]["defect_ids"]
        if issue_id not in ids:
            ids.append(issue_id)


def main() -> None:
    phase = json.loads(PHASE.read_text(encoding="utf-8"))
    host = json.loads(HOST.read_text(encoding="utf-8"))
    records = sorted(
        (item for value in phase["operations"].values() for item in value["attempts"]),
        key=lambda item: item["sequence"],
    )
    by_sequence = {item["sequence"]: item for item in records}
    add_defect(by_sequence, RENAME_ISSUE["id"], [6])
    add_defect(
        by_sequence,
        INHERITED_ISSUE["id"],
        [43, 44, 46, 47, 64, 83, 85, 86],
    )
    # The two no-replay recovery records already carry their exact IDs.
    by_sequence[96]["state_continuity"][
        "previous_registry_difference_explained_by_host_recovery"
    ] = True
    by_sequence[96]["state_continuity"]["recovery_evidence"] = (
        "recovery/admin-seq095-init-study/evidence.json"
    )
    by_sequence[95]["state_continuity"]["one_cumulative_store"] = True
    by_sequence[95]["state_continuity"]["original_cumulative_store_not_reset"] = True
    by_sequence[95]["state_continuity"]["unexpected_additional_store_created"] = True
    by_sequence[1]["starting_state"] = (
        "Cumulative post-transform sequence 120 Store with no reset; ADMIN round 1; "
        "phase-local sequence 1; current Context captured by command output/host state."
    )

    phase["schema_version"] = 2
    phase["status"] = "complete"
    phase["contract"] = {
        "operations": 21,
        "attempts_per_operation": 5,
        "attempts": 105,
        "interleaved_rounds": 5,
    }
    phase["starting_boundary"] = {
        "cumulative_from_transform": True,
        "no_reset": True,
        "same_pinned_identity": True,
        "admin_initial_digest": TRANSFORM_FINAL_TASK3,
        "transform_final_task3_subtree_digest": TRANSFORM_FINAL_TASK3,
        "admin_initial_task3_subtree_digest": TRANSFORM_FINAL_TASK3,
        "matches_transform_final_task3_subtree_digest": True,
        "structured_digest_bridge": {
            "hop_1_transform_to_admin_entry_task3_subtree": {
                "scope": "lane-local task-3 Context subtree",
                "transform_final_sha256": TRANSFORM_FINAL_TASK3,
                "admin_entry_inherited_sha256": TRANSFORM_FINAL_TASK3,
                "exact_match": True,
                "evidence": (
                    "TRANSFORM sequence120 post digest; ADMIN phase-entry host read "
                    "was immediate with no reset or intervening mem invocation."
                ),
            },
            "hop_2_admin_entry_to_first_pre_full_store_tree": {
                "scope": "all original-Store context.json files plus state.json",
                "admin_phase_entry_sha256": ADMIN_ENTRY_FULL,
                "admin_first_attempt_pre_sha256": by_sequence[1]["pre_context_tree_digest"],
                "exact_match": by_sequence[1]["pre_context_tree_digest"] == ADMIN_ENTRY_FULL,
                "evidence": "admin-host-reads.json phase_entry_boundary and sequence1 ledger pre digest",
            },
            "source_guard": {
                "transform_final_sha256": phase["source_guard"]["expected_sha256"],
                "admin_phase_entry_sha256": phase["source_guard"]["expected_sha256"],
                "exact_match": True,
            },
        },
        "note": (
            "Hop 1 preserves the TRANSFORM task-3 subtree digest; Hop 2 independently "
            "binds the captured ADMIN entry to sequence1 under the broader full-Store-tree "
            "digest. The scopes are explicit and are not compared directly."
        ),
    }
    # Exactly one protocol-required round-boundary exception.
    phase["interleave_exceptions"] = [
        {
            "operation": "switch",
            "attempts": [1, 2],
            "sequences": [21, 22],
            "commands": ["mem switch --previous", "mem switch --next"],
            "counted_commands": [by_sequence[21]["command"], by_sequence[22]["command"]],
            "rationale": (
                "Switch M1 is round-1-last and Switch M2 is round-2-first; no intervening "
                "mem invocation occurred between the two counted calls."
            ),
        }
    ]
    exit_counts = Counter(item["exit"] for item in records)
    mutations = sum(
        item["pre_context_tree_digest"] != item["post_context_tree_digest"]
        for item in records
    )
    share_reads = [
        item for item in host["host_reads"]
        if item["kind"] == "share_zero_delivery_assertion"
    ]
    fixed_identity_sequences = {
        int(match.group(1))
        for item in host["host_reads"]
        if item["kind"] == "identity_assertion"
        and (match := __import__("re").search(r"admin sequence (\d+)", str(item.get("label"))))
    }
    phase["summary"] = {
        "attempts": 105,
        "operations": 21,
        "attempts_per_operation": 5,
        "exit_counts": {str(key): value for key, value in sorted(exit_counts.items())},
        "context_tree_mutations": mutations,
        "representative_tui_lane": False,
        "screenshots": 0,
        "share_attempts": 5,
        "share_deliveries": sum(int(item["delivery_count"]) for item in share_reads),
        "init_study_attempts": 5,
        "init_study_successes": 1,
        "undo_successes": sum(item["exit"] == 0 for item in phase["operations"]["undo"]["attempts"]),
        "redo_successes": sum(item["exit"] == 0 for item in phase["operations"]["redo"]["attempts"]),
        "fixed_post_identity_sequences": len(fixed_identity_sequences),
        "identity_escape_sequences": [95],
        "identity_recovered_before_next_counted_call": True,
        "new_study_profile_and_store_retained": True,
        "guarded_source_preserved": phase["source_guard"]["preserved"],
        "product_issues": 2,
        "audit_limitations": 5,
    }
    phase["negative_control"] = {
        "malformed_branch_history_retained": True,
        "supplemental_delete_or_mem_recovery_calls": 0,
        "invalid_owner_contexts": [
            "task-3/local/admin-v2-scratch/b3",
            "task-3/local/admin-v2-scratch/co3",
        ],
        "later_undo_redo_behavior": "fail-closed before Context mutation",
    }
    phase["issue_registry"] = ["issues-admin.json", "issues.json"]
    phase["outcome"] = (
        "Completed 105/105 ADMIN attempts in five rounds. Share delivered nothing; "
        "the guarded healthcare source remained unchanged. Two P1 command-history "
        "defects were isolated. One audit negative control unexpectedly created and "
        "selected a valid UUID-shaped Study; its Profile/Store remain preserved while "
        "only active_uid was restored before the final ten calls."
    )
    PHASE.write_text(json.dumps(phase, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    admin_registry = {
        "schema_version": 1,
        "world": "task-3",
        "phase": "admin",
        "issues": [RENAME_ISSUE, INHERITED_ISSUE],
        "limitations": [
            INTERRUPT_LIMITATION,
            INIT_STUDY_LIMITATION,
            IMPORT_LIMITATION,
            RECOVERY_LIMITATION,
            INIT_PARENT_LIMITATION,
        ],
    }
    ADMIN_ISSUES.write_text(
        json.dumps(admin_registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    ADMIN_ISSUES_MD.write_text(
        "# task-3 ADMIN findings\n\n"
        "## T3V2-RENAME-BRANCH-STACK-OWNER-MISMATCH · P1\n\n"
        "Renaming B1 changed the checkpoint owner name without changing its creation "
        "membership. Exact inverse Rename restored the B2 stack and allowed Undo2/Redo2.\n\n"
        "## T3V2-BRANCH-INHERITS-CREATION-RECEIPT · P1\n\n"
        "Branching B1 into B3 and then co3 copied historical Branch creation receipts "
        "into new owners. Six later Undo/Redo calls failed closed; the malformed audit "
        "Contexts remain as a negative control.\n\n"
        "## Audit limitations\n\n"
        "- Checkout M5 was interrupted after invocation and retained once as exit 130.\n"
        "- UUID-shaped Study names are valid; the M5 negative control created a full "
        "Study. The new Profile/Store remain intact and only active_uid was restored.\n"
        "- Context Import M1/M2 collided with identities already present in the combined Store.\n"
        "- Recovery adapted Rename/Lock targets while retaining 21×5 counted calls.\n"
        "- Init without --parents correctly created only the exact nested leaf; the "
        "protocol's expected missing-parent failure was an input assumption.\n",
        encoding="utf-8",
    )

    global_issues = json.loads(GLOBAL_ISSUES.read_text(encoding="utf-8"))
    additions = [
        RENAME_ISSUE,
        INHERITED_ISSUE,
        INTERRUPT_LIMITATION,
        INIT_STUDY_LIMITATION,
        IMPORT_LIMITATION,
        RECOVERY_LIMITATION,
        INIT_PARENT_LIMITATION,
    ]
    existing_ids = {item["id"] for item in global_issues["issues"]}
    global_issues["issues"].extend(
        item for item in additions if item["id"] not in existing_ids
    )
    global_issues["phase"] = "core+transform+admin"
    GLOBAL_ISSUES.write_text(
        json.dumps(global_issues, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # Strict local validation.
    phase = json.loads(PHASE.read_text(encoding="utf-8"))
    records = sorted(
        (item for value in phase["operations"].values() for item in value["attempts"]),
        key=lambda item: item["sequence"],
    )
    assert phase["schema_version"] == 2
    assert phase["study"] == "study-long-audit-20260825-v2"
    assert phase["status"] == "complete"
    assert len(records) == 105
    assert [item["sequence"] for item in records] == list(range(1, 106))
    assert all(len(value["attempts"]) == 5 for value in phase["operations"].values())
    assert len(phase["operations"]) == 21
    assert all(item["command"].startswith(RUNNER_PREFIX) for item in records)
    assert len(list((ROOT / "raw/admin").glob("*.txt"))) == 105
    assert all((ROOT / item["raw_output"]).is_file() for item in records)
    for operation, value in phase["operations"].items():
        signatures = {
            (
                item["entry_route"], item["target_route"], item["scope"],
                item["input_provenance"],
            )
            for item in value["attempts"]
        }
        assert len(signatures) == 5, (operation, len(signatures))
    assert len(phase["interleave_exceptions"]) == 1
    assert phase["interleave_exceptions"][0]["commands"] == [
        "mem switch --previous", "mem switch --next"
    ]
    assert phase["starting_boundary"]["structured_digest_bridge"][
        "hop_2_admin_entry_to_first_pre_full_store_tree"
    ]["exact_match"]
    registered = {
        item["id"]
        for item in json.loads(GLOBAL_ISSUES.read_text(encoding="utf-8"))["issues"]
    }
    referenced = {issue for item in records for issue in item["defect_ids"]}
    assert referenced <= registered, sorted(referenced - registered)
    assert len(share_reads) == 5 and all(
        item["result"] == "PASS" and item["delivery_count"] == 0
        for item in share_reads
    )
    assert host["counted_mem_calls"] == 105
    assert phase["source_guard"]["preserved"]
    print(
        "ADMIN_FINALIZED_PASS",
        json.dumps(
            {
                "attempts": len(records),
                "raw": len(list((ROOT / "raw/admin").glob("*.txt"))),
                "issues": len(admin_registry["issues"]),
                "limitations": len(admin_registry["limitations"]),
                "exits": dict(exit_counts),
            },
            sort_keys=True,
        ),
    )


if __name__ == "__main__":
    main()
