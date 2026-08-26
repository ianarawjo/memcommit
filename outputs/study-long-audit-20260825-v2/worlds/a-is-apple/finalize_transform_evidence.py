#!/usr/bin/env python3
"""Finalize Transform routes, recovery proofs, issue links, and verification."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re


REPOSITORY = Path("/Users/KimMunyeong/Github/memcommit")
AUDIT_ROOT = REPOSITORY / "outputs/study-long-audit-20260825-v2"
WORLD_ROOT = AUDIT_ROOT / "worlds/a-is-apple"
LEDGER_PATH = WORLD_ROOT / "phase-transform.json"


def output_for(record: dict) -> str:
    text = (AUDIT_ROOT / record["raw_output"]).read_text().split("\nOUTPUT\n", 1)[-1]
    return re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", text).replace("\r", "")


def concise(record: dict) -> str:
    lines = [line.strip() for line in output_for(record).splitlines() if line.strip()]
    if not lines:
        return "No stdout/stderr text was emitted."
    limit = 12 if record["operation"] in {
        "atomize", "audit", "check-conformance", "distill", "elaborate",
        "forget", "ground", "impact", "meld", "revert", "review",
    } else 8
    text = " | ".join(lines[:limit])
    if len(lines) > limit:
        text += f" | … ({len(lines)} non-empty lines; see raw output)"
    return text[:3200]


def issues() -> list[dict]:
    return [
        {
            "id": "AIA-V2-T-ATOMIZE-WHOLE-01",
            "title": "Whole-Context Atomize loses the complete report when final normal-form repair stalls",
            "expected": "A dirty whole Context yields a saved review session with its atomic, composite, uncertain, and unresolved items, as focused Atomize does.",
            "actual": "Both whole-frame controls failed after 43.7s and 61.6s because three items remained UNCERTAIN/COMPOSITE. No analysis was saved. All three focused-Memory controls completed, including one with two review issues, showing that unresolved items are representable when scope is narrow.",
            "workaround": "Atomize one Memory at a time and manually aggregate the saved sessions; this loses the intended whole-frame decomposition workflow.",
            "severity": "HIGH",
            "classification": "FUNCTIONAL_RELIABILITY_WHOLE_FRAME",
            "reproduction": "2/2 whole-Context attempts failed; 3/3 focused controls succeeded",
            "evidence": [
                "worlds/a-is-apple/raw/transform/001-atomize-1.txt",
                "worlds/a-is-apple/raw/transform/025-atomize-2.txt",
                "worlds/a-is-apple/raw/transform/049-atomize-3.txt",
                "worlds/a-is-apple/raw/transform/073-atomize-4.txt",
                "worlds/a-is-apple/raw/transform/097-atomize-5.txt",
            ],
        },
        {
            "id": "AIA-V2-T-AUDIT-AMBIG-DECODE-01",
            "title": "Audit inherits the Find Ambiguities NONE/question decoder failure",
            "expected": "All configured finders complete over one frozen snapshot, or the Audit saves an explicit per-check failure without losing completed checks.",
            "actual": "Four Audits failed wholesale with `Codex find_ambiguities returned a question for NONE.` No Audit artifact remained for Review. The one successful control proves the complete four-check report is otherwise representable.",
            "workaround": "Run the component finders separately and retain their outputs; retrying Audit is unreliable because 4/5 attempts failed.",
            "severity": "HIGH",
            "classification": "FUNCTIONAL_RELIABILITY_COMPOSED_PROVIDER_CONTRACT",
            "reproduction": "4/5 Audits failed",
            "evidence": [
                "worlds/a-is-apple/raw/transform/002-audit-1.txt",
                "worlds/a-is-apple/raw/transform/026-audit-2.txt",
                "worlds/a-is-apple/raw/transform/050-audit-3.txt",
                "worlds/a-is-apple/raw/transform/074-audit-4.txt",
                "worlds/a-is-apple/raw/transform/098-audit-5.txt",
            ],
        },
        {
            "id": "AIA-V2-T-CONFORMANCE-COVERAGE-01",
            "title": "Check Conformance discards the report when the provider omits a target disposition",
            "expected": "Every frozen target Memory receives a disposition, or the operation repairs the bounded response into a complete evidence report.",
            "actual": "The cross-Context round-4 call spent 10.2s and failed with `Context Conformance did not account for every target Memory.` No partial report was returned; four other methods completed.",
            "workaround": "Retry on smaller exact frames or split the target manually, then reconcile the separate reports.",
            "severity": "HIGH",
            "classification": "FUNCTIONAL_RELIABILITY_COVERAGE_VALIDATION",
            "reproduction": "1/5 attempts",
            "evidence": [
                "worlds/a-is-apple/raw/transform/076-check-conformance-4.txt",
                "worlds/a-is-apple/raw/transform/100-check-conformance-5.txt",
            ],
        },
        {
            "id": "AIA-V2-T-DIFF-CURRENT-01",
            "title": "Checkpoint Diff does not show the destructive change that occurred after the checkpoint",
            "expected": "After Checkpoint then Clear, Diff against that checkpoint shows the current empty target as removals from the recoverable snapshot.",
            "actual": "All five exact `diff CHECKPOINT --context CONTEXT` calls rendered `THIS CHECKPOINT VS PREVIOUS`, not checkpoint versus current. Rounds 1 and 2 even reported every item kept and zero removed immediately after Clear; later rounds compared the checkpoint to older recovery history. The current destructive state remained invisible until Revert.",
            "workaround": "Create another checkpoint after the destructive action and diff checkpoint history, which mutates the recovery ledger merely to inspect working state, or use a separate exact List/Show.",
            "severity": "HIGH",
            "classification": "SAFETY_RECOVERY_OBSERVABILITY",
            "reproduction": "5/5 post-Clear Diff attempts",
            "evidence": [
                "worlds/a-is-apple/raw/transform/005-clear-1.txt",
                "worlds/a-is-apple/raw/transform/007-diff-1.txt",
                "worlds/a-is-apple/raw/transform/029-clear-2.txt",
                "worlds/a-is-apple/raw/transform/031-diff-2.txt",
                "worlds/a-is-apple/raw/transform/055-diff-3.txt",
                "worlds/a-is-apple/raw/transform/079-diff-4.txt",
                "worlds/a-is-apple/raw/transform/103-diff-5.txt",
            ],
        },
        {
            "id": "AIA-V2-T-FORGET-LOSS-01",
            "title": "Forget removes a supported alternative and leaves a malformed mapping rule",
            "expected": "The instruction to remove examples introducing words absent from the Source keeps both banana and blueberry because both occur in the frozen Source rule, or leaves the rule unchanged if the criterion is ambiguous.",
            "actual": "Forget changed `Treat b as unresolved between the alternatives banana and blueberry` to `Treat b as unresolved as blueberry`, deleting the present banana alternative and producing awkward, materially different text. The same-round Revert recovered the target.",
            "workaround": "Review every Forget receipt against the frozen source and Revert when a TRANSFORM drops supported content; never trust the changed count alone.",
            "severity": "HIGH",
            "classification": "SEMANTIC_SAFETY_CONTENT_LOSS",
            "reproduction": "1 semantic corruption among 5 Forget attempts",
            "evidence": [
                "worlds/a-is-apple/raw/transform/032-distill-2.txt",
                "worlds/a-is-apple/raw/transform/037-forget-2.txt",
                "worlds/a-is-apple/raw/transform/043-revert-2.txt",
                "worlds/a-is-apple/raw/transform/044-review-2.txt",
            ],
        },
        {
            "id": "AIA-V2-T-MELD-NESTED-RESULT-01",
            "title": "A fresh Meld Result nested below a peer invalidates Meld's own source snapshot",
            "expected": "Reject a Result path inside a peer before provider work, or create/bind it without making the command invalidate its frozen peer graph.",
            "actual": "Three calls used fresh `practice/aia-meld-rN` Results while `practice` was a peer. After 18.7–38.9s they failed with `A source Context changed while Compare was analyzing it`. The lane was strictly sequential with no external writer and pre/post durable digests matched, so the most plausible cause is the command's own transient Result creation under the peer namespace.",
            "workaround": "Use a fresh Result outside both peer namespaces; the CLI should surface this placement constraint before inference.",
            "severity": "HIGH",
            "classification": "FUNCTIONAL_TOPOLOGY_SELF_INVALIDATION",
            "reproduction": "3/3 nested-Result controls",
            "evidence": [
                "worlds/a-is-apple/raw/transform/016-meld-1.txt",
                "worlds/a-is-apple/raw/transform/064-meld-3.txt",
                "worlds/a-is-apple/raw/transform/112-meld-5.txt",
            ],
        },
        {
            "id": "AIA-V2-T-MELD-PEER-01",
            "title": "Meld loses the session when Compare repair still returns invalid PEER sides",
            "expected": "Return a valid exhaustive relation set or a stable reviewable failure artifact bound to the frozen peers.",
            "actual": "The round-2 independent provider path spent 55.2s, then failed because a DISTINCT relation had invalid PEER sides. No session was saved and retry would require another complete provider turn.",
            "workaround": "Preserve exact peer snapshots and retry; there is no partial relation artifact to review or repair locally.",
            "severity": "HIGH",
            "classification": "FUNCTIONAL_RELIABILITY_PROVIDER_RELATION_SCHEMA",
            "reproduction": "1 provider-repair path; the other Meld failures had separate boundaries",
            "evidence": ["worlds/a-is-apple/raw/transform/040-meld-2.txt"],
        },
        {
            "id": "AIA-V2-T-RATIONALE-LIMIT-01",
            "title": "Rationale loses a complete trace when one length repair still exceeds 40 words",
            "expected": "Return a complete narrative within the documented 40-word bound, or fall back to a deterministic trace-based explanation.",
            "actual": "Round 3 failed after one whole-Trace repair because the provider still exceeded 40 words. Four controls over the same accumulating lineage succeeded, including later longer traces.",
            "workaround": "Use Trace directly or retry Rationale; no durable state was changed.",
            "severity": "MEDIUM",
            "classification": "FUNCTIONAL_RELIABILITY_OUTPUT_BOUND",
            "reproduction": "1/5 attempts",
            "evidence": [
                "worlds/a-is-apple/raw/transform/066-rationale-3.txt",
                "worlds/a-is-apple/raw/transform/090-rationale-4.txt",
                "worlds/a-is-apple/raw/transform/114-rationale-5.txt",
            ],
        },
    ]


def main() -> None:
    ledger = json.loads(LEDGER_PATH.read_text())
    ledger["study"] = "study-long-audit-20260825-v2"
    records = sorted(
        (record for payload in ledger["operations"].values() for record in payload["attempts"]),
        key=lambda record: record["sequence"],
    )
    by_sequence = {record["sequence"]: record for record in records}
    for index, record in enumerate(records):
        record["actual"] = concise(record)
        record["defect_ids"] = []
        if index == 0:
            prior = "the final CORE digest"
        else:
            previous = records[index - 1]
            prior = f"sequence {previous['sequence']} {previous['operation']}#{previous['attempt']} (exit {previous['exit']})"
        record["starting_state"] = (
            f"Cumulative no-reset Store at transform sequence {record['sequence']}; immediately follows {prior}. "
            f"Prior post equals this pre digest {record['pre_target_digest']}."
        )

    assignments = {
        "AIA-V2-T-ATOMIZE-WHOLE-01": (1, 73),
        "AIA-V2-T-AUDIT-AMBIG-DECODE-01": (2, 26, 50, 98),
        "AIA-V2-T-CONFORMANCE-COVERAGE-01": (76,),
        "AIA-V2-T-DIFF-CURRENT-01": (7, 31, 55, 79, 103),
        "AIA-V2-T-FORGET-LOSS-01": (37,),
        "AIA-V2-T-MELD-NESTED-RESULT-01": (16, 64, 112),
        "AIA-V2-T-MELD-PEER-01": (40,),
        "AIA-V2-T-RATIONALE-LIMIT-01": (66,),
    }
    for issue_id, sequences in assignments.items():
        for sequence in sequences:
            by_sequence[sequence]["defect_ids"].append(issue_id)

    checkpoint_records = ledger["operations"]["checkpoint"]["attempts"]
    revert_records = ledger["operations"]["revert"]["attempts"]
    recovery_verification = []
    for attempt, (checkpoint, revert) in enumerate(zip(checkpoint_records, revert_records), 1):
        checkpoint_output = output_for(checkpoint)
        match = re.search(r"\[([0-9a-f]{8})\]", checkpoint_output)
        checkpoint_uid = match.group(1) if match else "unparsed"
        restored = checkpoint["post_target_digest"] == revert["post_target_digest"]
        target = "practice/source" if attempt % 2 else "practice"
        recovery_verification.append({
            "attempt": attempt,
            "target": target,
            "checkpoint_uid_prefix": checkpoint_uid,
            "checkpoint_post_digest": checkpoint["post_target_digest"],
            "revert_post_digest": revert["post_target_digest"],
            "exact_context_tree_restored": restored,
            "checkpoint_raw": checkpoint["raw_output"],
            "revert_raw": revert["raw_output"],
        })
        recovery_text = (
            f"Round {attempt} checkpoint {checkpoint_uid} covered {target}; Revert sequence "
            f"{revert['sequence']} restored the exact checkpoint Context-tree digest "
            f"{revert['post_target_digest']} (match={restored})."
        )
        start = checkpoint["sequence"] + 1
        end = revert["sequence"]
        for sequence in range(start, end + 1):
            by_sequence[sequence]["recovery_evidence"] = recovery_text
    ledger["recovery_verification"] = recovery_verification

    issue_records = issues()
    ledger["issues"] = [item["id"] for item in issue_records]
    ledger["summary"].update({
        "expected_or_deliberate_boundary_nonzero_exits": 22,
        "unexpected_nonzero_exits": 12,
        "issue_count": len(issue_records),
        "recovery_rounds_exactly_restored": sum(item["exact_context_tree_restored"] for item in recovery_verification),
    })
    ledger["regression_notes"] = {
        "persisted_or_extended": [
            "The core Find Ambiguities NONE/question failure propagated into four of five composed Audits.",
            "Provider-relation validation still prevented Meld from saving a usable session on one independent path.",
        ],
        "new": [
            "Whole-Context Atomize failed both realistic dirty frames while all focused controls completed.",
            "Checkpoint Diff did not expose post-checkpoint working changes.",
            "Forget removed a supported alternative and malformed the remaining rule.",
            "Nested Result placement appears to make Meld invalidate its own frozen peer graph.",
        ],
        "positive_controls": [
            "All five destructive windows restored exactly to their checkpoint Context-tree digest.",
            "Ground remained unsaved in all five non-TTY requests.",
            "Translation views preserved source UIDs and made no Context changes in five languages.",
            "Resolve stopped at NEEDS INPUT rather than applying an assumption in the one uncertain case.",
        ],
    }

    # Contract and evidence validation.
    counts = Counter(record["operation"] for record in records)
    duplicates = {}
    for operation, payload in ledger["operations"].items():
        signatures = [
            (record["entry_route"], record["target_route"], record["scope"], record["input_provenance"])
            for record in payload["attempts"]
        ]
        if len(signatures) != len(set(signatures)):
            duplicates[operation] = signatures
    if len(records) != 120 or set(counts.values()) != {5}:
        raise RuntimeError(f"attempt contract mismatch: {counts}")
    if duplicates:
        raise RuntimeError(f"duplicate method signatures: {duplicates}")
    if any(not record["state_continuity"]["same_as_previous_post"] for record in records):
        raise RuntimeError("Store continuity break")
    if not all(item["exact_context_tree_restored"] for item in recovery_verification):
        raise RuntimeError("destructive recovery mismatch")
    if not all((AUDIT_ROOT / record["raw_output"]).is_file() for record in records):
        raise RuntimeError("missing raw evidence")
    if not all((AUDIT_ROOT / path).is_file() for item in issue_records for path in item["evidence"]):
        raise RuntimeError("missing issue evidence")
    ledger["verification"] = {
        "attempt_contract": "PASS",
        "five_distinct_method_signatures_per_operation": "PASS",
        "one_cumulative_store_continuity": "PASS",
        "raw_output_paths_resolve": "PASS",
        "five_checkpoint_recovery_windows": "PASS",
    }
    LEDGER_PATH.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")
    (WORLD_ROOT / "issues-transform.json").write_text(
        json.dumps({"world": "a-is-apple", "phase": "transform", "issues": issue_records}, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
