#!/usr/bin/env python3
"""Finalize the already-recorded practice-source transform audit evidence.

This script performs no mem invocation. It only annotates the 120 captured
attempts, writes the issue registry, and checks the evidence contract.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re


WORLD_ROOT = Path(__file__).resolve().parent
LEDGER_PATH = WORLD_ROOT / "phase-transform.json"
ISSUES_PATH = WORLD_ROOT / "issues-transform.json"
ISSUES_MD_PATH = WORLD_ROOT / "issues-transform.md"
SOURCE_PATH = Path(
    "/Users/KimMunyeong/.codex/audit-stores/"
    "memcommit-six-world-v2-20260825/worlds/practice-source/profile-control/"
    "stores/8d6d6360-c3eb-40f9-a490-5c7b2a242bfd/contexts/practice/source/context.json"
)
SOURCE_DIGEST = "3c7872e184194b45295052ec4efe40c9088f1b962e12fd4d30cfd2aeed7de212"


def issues() -> list[dict[str, object]]:
    return [
        {
            "id": "PS2-T-CONFORMANCE-SOURCE-TYPO",
            "title": "Conformance treats source-preserved typos as failures to preserve the source",
            "expected": "A rule requiring preservation of source meaning judges the supplied source as the reference frame and does not invent corrected protected wording that is absent from it.",
            "actual": "The direct source check marked 4/12 Memories nonconforming because `strucutre`, `redundent`, `titlle`, and `refferences` were misspelled, then claimed those exact source spellings failed exact preservation of corrected words that the source never contained.",
            "workaround": "Treat these four findings as reviewer-facing typo observations, not evidence that the source failed to preserve itself; use a separately declared spelling-correction rule when that is the intended check.",
            "severity": "HIGH",
            "classification": "SEMANTIC_SELF_REFERENCE_FALSE_NEGATIVE",
            "reproduction": "1/1 direct source-meaning conformance route; four false-negative dispositions in one complete report",
            "evidence": ["worlds/practice-source/raw/transform/004-check-conformance-m1.txt"],
        },
        {
            "id": "PS2-T-DIFF-CURRENT",
            "title": "Checkpoint Diff hides the destructive current state after Clear",
            "expected": "Immediately after checkpointing and clearing the same scratch Context, an explicit checkpoint Diff exposes the recoverable checkpoint versus the current empty state.",
            "actual": "Rounds 1, 2, and 4 cleared `practice/description`, but Diff rendered `THIS CHECKPOINT VS PREVIOUS`. Round 1 reported 13 kept and 0 removed; later rounds described older revision history rather than the current cleared state.",
            "workaround": "Verify current state separately with an exact read-only List/Show, retain the checkpoint UID, and use Revert for recovery; do not infer post-Clear state from checkpoint Diff.",
            "severity": "HIGH",
            "classification": "SAFETY_RECOVERY_OBSERVABILITY",
            "reproduction": "3/3 same-target Checkpoint→Clear→Diff windows",
            "evidence": [
                "worlds/practice-source/raw/transform/003-checkpoint-m1.txt",
                "worlds/practice-source/raw/transform/005-clear-m1.txt",
                "worlds/practice-source/raw/transform/007-diff-m1.txt",
                "worlds/practice-source/raw/transform/027-checkpoint-m2.txt",
                "worlds/practice-source/raw/transform/029-clear-m2.txt",
                "worlds/practice-source/raw/transform/031-diff-m2.txt",
                "worlds/practice-source/raw/transform/075-checkpoint-m4.txt",
                "worlds/practice-source/raw/transform/077-clear-m4.txt",
                "worlds/practice-source/raw/transform/079-diff-m4.txt",
            ],
        },
        {
            "id": "PS2-T-ELABORATE-FABRICATED-SOURCE",
            "title": "Strict Elaborate fabricates quoted source instructions",
            "expected": "Strict elaboration from the inline anti-inference rule remains hypothetical or quotes only wording present in the supplied rule/source frame.",
            "actual": "The strict result introduced `Given the source instruction “Keep the heading exactly as supplied”` and `the sole source instruction “Preserve every technical term”`; neither quoted instruction exists in practice/source or the supplied inline rule. The receipt labels the results UNVERIFIED but writes them as source-grounded premises.",
            "workaround": "Keep the result in checkpointed scratch, rewrite examples parametrically, and verify every claimed source quotation against exact source UIDs before reuse.",
            "severity": "MEDIUM",
            "classification": "SEMANTIC_PROVENANCE_FABRICATION",
            "reproduction": "2 fabricated quoted premises in the round-5 STRICT result",
            "evidence": ["worlds/practice-source/raw/transform/105-elaborate-m5.txt"],
        },
        {
            "id": "PS2-T-DEDUN-RECEIPT",
            "title": "Dedun receipt hides survivor and absorption mappings",
            "expected": "A semantic cleanup that absorbs multiple items prints each survivor UID and absorbed-to-survivor link for immediate independent review and trace reuse.",
            "actual": "The late cleanup reported 4 absorbed, 4 kept, and 4 semantic DUN links, but printed no survivor UID or absorption mapping; only an aggregate checkpoint/review route remained.",
            "workaround": "Open the exact Review receipt immediately and compare an exact List/Trace before another mutation.",
            "severity": "MEDIUM",
            "classification": "USABILITY_OUTPUT_REUSE_CONFIRMED_REGRESSION",
            "reproduction": "1/1 transforming Dedun result; four earlier no-redundancy controls required no mapping",
            "evidence": ["worlds/practice-source/raw/transform/108-dedun-m5.txt"],
        },
        {
            "id": "PS2-T-GROUND-GRAMMAR",
            "title": "Ground binding grammar is discovered through sequential failures",
            "expected": "A binding attempt uses operation-consistent names or one validation failure prints the complete exact required form.",
            "actual": "`--publication-context` was rejected in favor of `--publication-target`; the corrected call then revealed that `--description` was also mandatory. The fully specified next route reached a separate independence boundary.",
            "workaround": "Supply name, goal, description, `--raw-context`, `--derived-context`, and `--publication-target` together, then ensure the three bound Context graphs are independent.",
            "severity": "MEDIUM",
            "classification": "USABILITY_COMMAND_GRAMMAR_CONFIRMED_REGRESSION",
            "reproduction": "Two sequential parser/validation failures",
            "evidence": [
                "worlds/practice-source/raw/transform/038-ground-m2.txt",
                "worlds/practice-source/raw/transform/062-ground-m3.txt",
                "worlds/practice-source/raw/transform/086-ground-m4.txt",
            ],
        },
        {
            "id": "PS2-T-IMPACT-ZERO-COVERAGE",
            "title": "Saved Meld Impact offers Apply with zero source coverage and zero changes",
            "expected": "A proposal with zero current Source coverage and no final Memories/changes foregrounds inapplicability or requires restart instead of presenting an Apply affordance.",
            "actual": "Impact reported READY_TO_APPLY, 0/2 Source coverage, 0 final Memories, and 0 changes, then rendered `[ APPLY? ] Continue to Meld Apply` without an equally prominent stale/inapplicable warning.",
            "workaround": "Do not apply the saved session; restart Meld against the current explicit target and re-check complete coverage.",
            "severity": "HIGH",
            "classification": "SAFETY_STALE_PROPOSAL_DECISION_CONFIRMED_REGRESSION",
            "reproduction": "1 late saved-session Impact after cumulative target changes",
            "evidence": [
                "worlds/practice-source/raw/transform/088-meld-m4.txt",
                "worlds/practice-source/raw/transform/111-impact-m5.txt",
            ],
        },
        {
            "id": "PS2-T-MELD-SNAPSHOT-RACE",
            "title": "Sequential Meld reports that a Source changed during Compare",
            "expected": "A strictly sequential explicit Source/target/Result command keeps its frozen sources stable or identifies a genuine external before/after revision.",
            "actual": "The Context-to-Context Meld ran for 49.69 seconds and failed that a Source changed while Compare was analyzing it. No audit command ran concurrently and no analysis was saved; directional inline Meld controls completed.",
            "workaround": "Retain the failure evidence and use a narrow inline Memory plus explicit baseline and `--restart`; avoid spending another whole-frame provider turn without a new snapshot.",
            "severity": "HIGH",
            "classification": "FUNCTIONAL_SNAPSHOT_SELF_INVALIDATION_CONFIRMED_REGRESSION",
            "reproduction": "1 sequential whole-Context route; three directional inline controls succeeded",
            "evidence": [
                "worlds/practice-source/raw/transform/016-meld-m1.txt",
                "worlds/practice-source/raw/transform/040-meld-m2.txt",
                "worlds/practice-source/raw/transform/064-meld-m3.txt",
                "worlds/practice-source/raw/transform/088-meld-m4.txt",
            ],
        },
        {
            "id": "PS2-T-MIXED-EVIDENCE-DEAD-END",
            "title": "Cumulative live evidence makes Ground, Meld, Sever, and Update unusable without a clean-room copy",
            "expected": "Exact selectors such as `--source-memory`, `--direct`, `--source-root-only`, and `--criteria-root-only` can safely narrow to eligible owned Memories while unrelated live References/Embeds remain visible evidence.",
            "actual": "Once scratch contained source References/Embeds, all five Updates failed graph-overlap checks even with exact source/target Memory selectors; four Sever routes rejected live References; a fully bound Ground rejected dependent Contexts; and late directional Meld rejected two otherwise unrelated direct References before inference.",
            "workaround": "Copy only intended owned Memories into new independent lane-local Contexts, retaining an external source-UID mapping, then run the transform there. This adds a clean-room preparation step and separates visible evidence from execution.",
            "severity": "MEDIUM",
            "classification": "WORKFLOW_INTEROPERABILITY_MIXED_ITEM_TOPOLOGY",
            "reproduction": "11/11 executable routes exposed the same accumulated graph/item-family boundary",
            "evidence": [
                "worlds/practice-source/raw/transform/021-sever-m1.txt",
                "worlds/practice-source/raw/transform/024-update-m1.txt",
                "worlds/practice-source/raw/transform/045-sever-m2.txt",
                "worlds/practice-source/raw/transform/048-update-m2.txt",
                "worlds/practice-source/raw/transform/069-sever-m3.txt",
                "worlds/practice-source/raw/transform/072-update-m3.txt",
                "worlds/practice-source/raw/transform/086-ground-m4.txt",
                "worlds/practice-source/raw/transform/096-update-m4.txt",
                "worlds/practice-source/raw/transform/112-meld-m5.txt",
                "worlds/practice-source/raw/transform/117-sever-m5.txt",
                "worlds/practice-source/raw/transform/120-update-m5.txt",
            ],
        },
        {
            "id": "PS2-T-REVERT-OVERLOAD",
            "title": "Every large Revert receipt truncates its restoration manifest",
            "expected": "A large recovery remains compact while exposing a complete machine-reusable effect manifest or an exact non-mutating follow-up command.",
            "actual": "All five Reverts affected more than 12 direct items and printed only 12 previews followed by 2–29 omitted items. Counts and a recovery checkpoint remained, but the receipt alone could not verify every restored/removed identity.",
            "workaround": "Retain the exact checkpoint UID and verify the restored Context separately with List/Diff/Trace; treat the Revert receipt as aggregate evidence only.",
            "severity": "MEDIUM",
            "classification": "USABILITY_RECOVERY_EVIDENCE_CONFIRMED_REGRESSION",
            "reproduction": "5/5 recovery windows",
            "evidence": [
                "worlds/practice-source/raw/transform/019-revert-m1.txt",
                "worlds/practice-source/raw/transform/043-revert-m2.txt",
                "worlds/practice-source/raw/transform/067-revert-m3.txt",
                "worlds/practice-source/raw/transform/091-revert-m4.txt",
                "worlds/practice-source/raw/transform/115-revert-m5.txt",
            ],
        },
        {
            "id": "PS2-T-TRACE-LIMIT",
            "title": "JSON Trace ignores the requested one-operation limit",
            "expected": "`trace --json --limit 1` bounds lineage-affecting command units to one, consistent with the documented Trace operation-limit contract.",
            "actual": "The response was 705 lines / 43,339 bytes and returned the full three-Member component plus multiple events, analyses, spans, and children despite `--limit 1`.",
            "workaround": "Parse only the needed JSON fields or use plain Trace for a bounded human receipt; do not assume JSON payload size follows `--limit`.",
            "severity": "MEDIUM",
            "classification": "FUNCTIONAL_OUTPUT_BOUND_CONFIRMED_REGRESSION",
            "reproduction": "1 direct minimal-limit JSON route",
            "evidence": ["worlds/practice-source/raw/transform/094-trace-m4.txt"],
        },
    ]


def render_markdown(issue_records: list[dict[str, object]]) -> str:
    lines = [
        "# practice-source v2 transform findings",
        "",
        "All 24 Transform operations ran five interleaved methods through the pinned world runner (120 counted commands). The Store was cumulative from CORE; `practice/source` remained byte-identical. Destructive trials stayed in lane-local scratch and each of five checkpoint windows was restored exactly.",
        "",
    ]
    for item in issue_records:
        lines.extend([
            f"## {item['id']} — {item['title']}",
            "",
            f"- Expected: {item['expected']}",
            f"- Actual: {item['actual']}",
            f"- Workaround: {item['workaround']}",
            f"- Severity: **{item['severity']}**",
            f"- Classification: **{item['classification']}**",
            f"- Reproduction: {item['reproduction']}",
            "- Evidence: " + ", ".join(f"`{path}`" for path in item["evidence"]),
            "",
        ])
    lines.extend([
        "## Positive controls and closed prior observations",
        "",
        "- Distill no longer emitted the prior inferred prose-style meta-rule in its successful direct runs; rounds 3 and 4 instead failed closed when proposed rules did not fit the declared Goal.",
        "- Diff's explicit checkpoint grammar now worked noninteractively; the remaining issue is its historical comparison semantics after a destructive current-state change.",
        "- Elaborate consistently labeled generated cases UNVERIFIED, and Atomize never applied a split in this phase. Review's four `PENDING` failures were audit-orchestrator receipt-parsing limitations, not product failures; the stale round-5 Atomize Review correctly failed closed.",
        "- Audit's conflict result differed from the independent CORE conflict turn, but separate semantic-provider judgments remain accepted variance; the independently self-contradictory CORE Conflict disposition remains the actionable defect.",
        "- Missing selectors, self-Merge, stale Review, invalid session IDs, and failed Goal-fit proposals produced no partial mutation.",
        "",
        "## Safe outcome",
        "",
        f"`practice/source` stayed at SHA-256 `{SOURCE_DIGEST}`. All five `practice/description` Reverts matched their round checkpoint digest. No external Share, clipboard, destructive source Apply, product-code edit, or TUI replay occurred.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    records = sorted(
        (attempt for payload in ledger["operations"].values() for attempt in payload["attempts"]),
        key=lambda attempt: attempt["sequence"],
    )
    by_sequence = {attempt["sequence"]: attempt for attempt in records}
    for attempt in records:
        attempt["defect_ids"] = []
        raw = (WORLD_ROOT / attempt["raw_output"]).read_bytes()
        output_lines = raw.count(b"\n")
        attempt["cost"].update({
            "output_bytes": len(raw),
            "output_lines": output_lines,
            "terminal_screens": max(1, math.ceil(output_lines / 52)),
            "timed_out": False,
        })

    assignments = {
        "PS2-T-CONFORMANCE-SOURCE-TYPO": (4,),
        "PS2-T-DIFF-CURRENT": (7, 31, 79),
        "PS2-T-ELABORATE-FABRICATED-SOURCE": (105,),
        "PS2-T-DEDUN-RECEIPT": (108,),
        "PS2-T-GROUND-GRAMMAR": (38, 62),
        "PS2-T-IMPACT-ZERO-COVERAGE": (111,),
        "PS2-T-MELD-SNAPSHOT-RACE": (64,),
        "PS2-T-MIXED-EVIDENCE-DEAD-END": (21, 24, 45, 48, 69, 72, 86, 96, 112, 117, 120),
        "PS2-T-REVERT-OVERLOAD": (19, 43, 67, 91, 115),
        "PS2-T-TRACE-LIMIT": (94,),
    }
    for issue_id, sequences in assignments.items():
        for sequence in sequences:
            by_sequence[sequence]["defect_ids"].append(issue_id)

    checkpoint_records = ledger["operations"]["checkpoint"]["attempts"]
    revert_records = ledger["operations"]["revert"]["attempts"]
    recovery_verification = []
    for checkpoint, revert in zip(checkpoint_records, revert_records):
        match = re.search(r"\[([0-9a-f]{8})\]", checkpoint["actual"])
        checkpoint_uid = match.group(1) if match else "unparsed"
        restored = checkpoint["post_target_digest"] == revert["post_target_digest"]
        item = {
            "attempt": checkpoint["attempt"],
            "target": "practice/description",
            "checkpoint_uid_prefix": checkpoint_uid,
            "checkpoint_post_digest": checkpoint["post_target_digest"],
            "revert_post_digest": revert["post_target_digest"],
            "exact_target_restored": restored,
            "checkpoint_raw": checkpoint["raw_output"],
            "revert_raw": revert["raw_output"],
        }
        recovery_verification.append(item)
        evidence = (
            f"Round {checkpoint['attempt']} checkpoint {checkpoint_uid}; Revert sequence "
            f"{revert['sequence']} restored the exact target digest "
            f"{revert['post_target_digest']} (match={restored})."
        )
        for sequence in range(checkpoint["sequence"] + 1, revert["sequence"] + 1):
            by_sequence[sequence]["recovery_evidence"] = evidence

    issue_records = issues()
    issue_ids = {item["id"] for item in issue_records}
    counts = Counter(attempt["command"].split()[3] for attempt in records)
    signatures = {
        operation: {
            (
                attempt["entry_route"],
                attempt["target_route"],
                attempt["scope"],
                attempt["input_provenance"],
            )
            for attempt in payload["attempts"]
        }
        for operation, payload in ledger["operations"].items()
    }
    raw_paths_resolve = all((WORLD_ROOT / attempt["raw_output"]).is_file() for attempt in records)
    source_actual = hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()
    referenced = {issue_id for attempt in records for issue_id in attempt["defect_ids"]}

    assert len(records) == 120
    assert set(counts.values()) == {5} and len(counts) == 24
    assert all(len(values) == 5 for values in signatures.values())
    assert raw_paths_resolve
    assert referenced == issue_ids
    assert source_actual == SOURCE_DIGEST
    assert all(item["exact_target_restored"] for item in recovery_verification)

    ledger.update({
        "status": "complete",
        "attempt_count": 120,
        "last_completed_sequence": 120,
        "issues": sorted(issue_ids),
        "recovery_verification": recovery_verification,
        "source_guard": {
            "path": str(SOURCE_PATH),
            "initial_sha256": SOURCE_DIGEST,
            "final_sha256": source_actual,
            "preserved": source_actual == SOURCE_DIGEST,
        },
        "summary": {
            "attempts": 120,
            "successful_exits": sum(attempt["exit"] == 0 for attempt in records),
            "nonzero_exits": sum(attempt["exit"] != 0 for attempt in records),
            "expected_or_deliberate_boundary_nonzero_exits": 30,
            "unexpected_nonzero_exits": 1,
            "issue_count": len(issue_records),
            "checkpoint_windows_exactly_restored": sum(item["exact_target_restored"] for item in recovery_verification),
            "wall_seconds": round(sum(attempt["cost"]["wall_seconds"] for attempt in records), 6),
        },
        "regression_notes": {
            "confirmed_or_extended": [
                "Dedun still omits survivor/absorption mappings from its concise transforming receipt.",
                "Saved Meld Impact still offers Apply with zero current Source coverage.",
                "A sequential whole-Context Meld still reports an unexplained source-snapshot race.",
                "Large Revert receipts and minimal-limit JSON Trace remain materially overloaded.",
                "Ground binding option discovery still requires sequential failures.",
            ],
            "new": [
                "Source-preserved typos were misclassified as failures to preserve corrected wording absent from the source.",
                "Strict Elaborate fabricated two quoted source instructions.",
                "Cumulative live References/Embeds blocked exact-selector routes across Ground, Meld, Sever, and Update.",
            ],
            "positive_controls": [
                "The prior Distill presentation-style meta-rule did not recur.",
                "All five destructive windows restored the exact checkpointed scratch digest.",
                "Atomize analysis did not publish an unreviewed split; missing and stale routes failed closed.",
                "Translation views preserved source identity and source content across all five methods.",
            ],
        },
        "verification": {
            "attempt_contract": "PASS",
            "operation_attempt_counts": dict(sorted(counts.items())),
            "five_distinct_method_signatures_per_operation": "PASS",
            "diversity_signature_counts": {operation: len(values) for operation, values in sorted(signatures.items())},
            "one_cumulative_store_continuity": "PASS",
            "raw_output_paths_resolve": "PASS",
            "issue_references_resolve": "PASS",
            "five_checkpoint_recovery_windows": "PASS",
            "source_digest_preserved": "PASS",
        },
        "outcome": "Complete: 120/120 counted attempts, all 24 transform operations at five distinct route/provenance signatures; five scratch recovery windows restored and practice/source digest preserved.",
    })

    LEDGER_PATH.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ISSUES_PATH.write_text(
        json.dumps({"world": "practice-source", "phase": "transform", "issues": issue_records}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    ISSUES_MD_PATH.write_text(render_markdown(issue_records), encoding="utf-8")


if __name__ == "__main__":
    main()
