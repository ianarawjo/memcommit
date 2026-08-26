#!/usr/bin/env python3
"""Finalize task-3 transform metadata and extend the world issue registry."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path("/Users/KimMunyeong/Github/memcommit/agent-records/outputs/study-long-audit-20260825-v2")
WORLD = ROOT / "worlds/task-3"
PHASE = WORLD / "phase-transform.json"
ISSUES = WORLD / "issues.json"


def evidence(sequence: int, attempt: int, operation: str, exit_code: int) -> dict:
    path = next((WORLD / "raw/transform").glob(f"{sequence:03d}-{operation}-a{attempt}.txt"))
    return {
        "phase": "transform",
        "sequence": sequence,
        "attempt": attempt,
        "operation": operation,
        "exit": exit_code,
        "raw_output": str(path.relative_to(ROOT)),
    }


TRANSFORM_ISSUES = [
    {
        "id": "T3V2-ELABORATE-UNVERIFIED-ORDINARY-MEMORY",
        "title": "Elaborate persists invented healthcare examples as ordinary factual-looking Memories",
        "classification": "semantic safety / unsupported generation",
        "severity": "P1 / high",
        "regression": "confirmed open from the prior task-3 Elaborate hallucination finding",
        "expected": "Generated Cases remain visibly hypothetical and unverified in their durable content, especially when the Source supplies no recipient, clinician, prescription, vendor, or employee facts.",
        "actual": "A one-Rule healthcare run invented Dr. Chen, a confirmed current prescription-adjustment purpose, and current medication name/dosage, then added the sentence as an ordinary Memory. A minimization run similarly added concrete benefits-vendor and employee incident stories. `VERIFICATION · UNVERIFIED` appeared only in the transient receipt; the first stored Memory did not label itself as a suggested example.",
        "workaround": "Checkpoint the Target first, inspect the full Elaborate receipt immediately, and undo/revert every output whose stored text is not self-labelled hypothetical and source-grounded.",
        "reproduction": "Yes — 2/5 materially different Elaborate attempts persisted invented concrete scenarios; strict round 4 improved this by including `Suggested Example Memory` in the content.",
        "evidence": [evidence(9, 1, "elaborate", 0), evidence(33, 2, "elaborate", 0), evidence(81, 4, "elaborate", 0)],
    },
    {
        "id": "T3V2-FORGET-SAFETY-GATE-LOSS",
        "title": "Forget removes or weakens the exact safety boundary it was told to preserve",
        "classification": "semantic safety / destructive curation",
        "severity": "P1 / high",
        "regression": "newly isolated transform evidence",
        "expected": "Whole-frame curation preserves explicit uncertainty and human decision gates while dropping only items that actually imply approval, unsupported currentness, or forbidden third-party disclosure.",
        "actual": "Round 1 deleted a Memory that explicitly said the candidate was `not yet approved` under an instruction to remove only items implying approval. Round 3 deleted both an uncertainty-preserving medication rule and a draft accommodation candidate that required verification. Round 5 rewrote the exact recipient/purpose/item/channel/retention checklist into the vague phrase `decision before any transfer` despite an explicit preserve-the-human-decision-gate instruction.",
        "workaround": "Always checkpoint before Forget, inspect the complete DIFF rather than trusting the instruction echo, and revert if a negative gate, uncertainty statement, or enumerated approval field is removed or generalized.",
        "reproduction": "Yes — harmful disposition drift appeared in 3/5 different curation frames and was recovered by same-round Revert.",
        "evidence": [evidence(13, 1, "forget", 0), evidence(61, 3, "forget", 0), evidence(109, 5, "forget", 0)],
    },
    {
        "id": "T3V2-UPDATE-AUTO-APPLY-OPAQUE",
        "title": "Update applies semantic edits before showing the changed text",
        "classification": "semantic mutation / review safety",
        "severity": "P1 / high",
        "regression": "confirmed open from the prior task-3 Update stale-stage/review finding",
        "expected": "A high-stakes semantic Update presents the exact ADD/EDIT/REMOVE proposal for review before materialization, or at minimum prints every changed Memory in its Apply receipt.",
        "actual": "Three Update attempts immediately printed `UPDATE APPLIED` and changed the local audit scratch with no `--accept` step. Receipts showed only aggregate counts. The final run edited five Memories, including appending possible recipient retention/internal-forwarding behavior to a minimization record, but none of the five before/after texts appeared in the receipt.",
        "workaround": "Checkpoint the Target, run Update only in disposable local scratch, open `mem review update --session RECEIPT` immediately, and undo if any exact edit was not already approved.",
        "reproduction": "Yes — 3 successful local Update routes auto-applied; two other attempts failed closed on an embedded Grant before mutation.",
        "evidence": [evidence(48, 2, "update", 0), evidence(72, 3, "update", 0), evidence(120, 5, "update", 0)],
    },
    {
        "id": "T3V2-SEVER-OPAQUE-READY",
        "title": "Sever declares personal-Memory curation ready without showing kept, transformed, or dropped items",
        "classification": "privacy review / output opacity",
        "severity": "P1 / high",
        "regression": "confirmed open from the prior task-3 Sever presentation finding",
        "expected": "Before a fresh Result can be accepted, the line-oriented receipt exposes the exact selected/excluded/transformed Memories and their reasons, with every unresolved healthcare meaning decision required.",
        "actual": "Four personal-history Sever runs returned `SEVER READY`, `JUDGMENTS · REQUIRED 0`, and `READY TO CREATE` with only Source/Result/session identifiers. No kept, dropped, transformed, third-party, stale, or unapproved items were visible in the receipt, so readiness could not be checked from the command that produced it.",
        "workaround": "Do not accept from the READY receipt. Open the exact saved session through Impact/Review, inspect every disposition, and require explicit human approval of the final item list.",
        "reproduction": "Yes — 4 successful Sever variants had the same opaque READY receipt; the fifth failed provider-result validation and changed nothing.",
        "evidence": [evidence(21, 1, "sever", 0), evidence(69, 3, "sever", 0), evidence(93, 4, "sever", 0), evidence(117, 5, "sever", 0)],
    },
    {
        "id": "T3V2-MELD-EAGER-EMPTY-RESULT",
        "title": "Meld creates an empty Result Context while semantic choices still need input",
        "classification": "workflow state / premature materialization",
        "severity": "P2 / medium",
        "regression": "newly isolated state-continuity evidence",
        "expected": "A fresh symmetric Result remains a plan until required/optional meaning review is complete, or the receipt clearly identifies any intentionally materialized placeholder and its cleanup route.",
        "actual": "Rounds 1 and 5 returned `MELD NEEDS INPUT` with optional judgments and no `--accept`, but each invocation created a durable empty local Result Context. Source remained unchanged, yet the Result creation survived restoration of the separately checkpointed scratch Target.",
        "workaround": "Use directional Meld when possible; otherwise treat the fresh Result name as reserved scratch and remove the empty placeholder only through a separately authorized cleanup after the review is abandoned.",
        "reproduction": "Yes — both symmetric fresh-Result NEEDS INPUT attempts created zero-item Contexts; directional attempts did not.",
        "evidence": [evidence(16, 1, "meld", 0), evidence(112, 5, "meld", 0)],
    },
    {
        "id": "T3V2-GRANTED-TRANSFORM-ROUTE-INCONSISTENCY",
        "title": "Granted Context works in Audit, Meld, and Merge but is reported absent by Atomize and Impact Atomize",
        "classification": "authorization routing / operation consistency",
        "severity": "P2 / medium-high",
        "regression": "new transform route evidence",
        "expected": "Every readable/DERIVE-authorized operation resolves the same public Context through the grant-aware catalog, or fails with the exact missing capability rather than claiming the Context is not local/not found.",
        "actual": "Atomize said the public guidance `does not exist locally`, and Impact Atomize said it was `not found`. In the same cumulative lane, Audit analyzed all 25 granted Memories, directional Meld accepted the public Source, and structural Merge copied all 25 into checkpointed local scratch. Distill separately gave a clear not-authorized boundary.",
        "workaround": "Use the operations that explicitly resolve readable Grants, or copy/merge only when inward EXPORT authority and local recovery are appropriate; do not interpret `not found` as evidence that the Grant disappeared.",
        "reproduction": "Yes across two failing Atomize adapters and three successful peer adapters over the identical public name.",
        "evidence": [evidence(73, 4, "atomize", 1), evidence(74, 4, "audit", 0), evidence(80, 4, "distill", 1), evidence(87, 4, "impact", 1), evidence(88, 4, "meld", 0), evidence(89, 4, "merge", 0)],
    },
    {
        "id": "T3V2-RESOLVE-OPAQUE-NOCHANGE",
        "title": "Resolve reports FIT YES / NO CHANGE without evidence or candidate disposition",
        "classification": "usability / semantic explainability",
        "severity": "P2 / medium",
        "regression": "confirmed open from the prior task-3 Resolve opacity finding",
        "expected": "A no-change Resolve receipt explains what was examined, why no repair is needed, and how the stated guidance and Fit check support that result.",
        "actual": "All five varied Resolve invocations returned only the Context name and `FIT · YES · NO CHANGE`. No selected Memory, assessed issue, evidence, guidance effect, or reusable session was shown, including focused and allow-delete routes.",
        "workaround": "Treat NO CHANGE as an opaque model outcome, inspect the Source and saved quality findings separately, and do not interpret FIT YES as healthcare approval.",
        "reproduction": "Yes — 5/5 interleaved Resolve routes produced the same evidence-free shape.",
        "evidence": [evidence(10, 1, "resolve", 0), evidence(34, 2, "resolve", 0), evidence(58, 3, "resolve", 0), evidence(82, 4, "resolve", 0), evidence(106, 5, "resolve", 0)],
    },
    {
        "id": "T3V2-ATOMIZE-PROVIDER-TIMEOUT",
        "title": "One whole-Context Atomize provider call exceeded the isolated 360-second audit bound",
        "classification": "infrastructure / provider latency",
        "severity": "P2 / medium campaign impact; not classified as a product semantic defect",
        "regression": "one current-campaign infrastructure failure",
        "expected": "The bounded provider call finishes or fails with a native timeout before the audit's six-minute outer isolation limit, publishing no partial result.",
        "actual": "The first whole-Context Atomize call emitted no application output and was terminated by the world-local audit harness after 360 seconds. The task-3 tree digest was unchanged. Four later focused/smaller Atomize attempts returned in 7–9 seconds or failed immediately at a route boundary.",
        "workaround": "Use a focused Memory/Context frame, retain the outer timeout, and retry only in a new counted campaign rather than silently duplicating this invocation.",
        "reproduction": "1/5 Atomize attempts; isolated as provider/infrastructure because later Atomize calls completed normally.",
        "evidence": [evidence(1, 1, "atomize", 124)],
    },
    {
        "id": "T3V2-TRANSFORM-HARNESS-ARTIFACT-ROUTING",
        "title": "Audit harness failed to reuse saved artifact UIDs and used unsupported replay modifiers",
        "classification": "audit infrastructure / methodology limitation",
        "severity": "P2 / coverage limitation; not a product defect",
        "regression": "current harness defect discovered from raw evidence",
        "expected": "The audit extracts `SESSION [uid]` from snapshot receipts, binds round-local dynamic selectors eagerly, and uses only supported replay syntax so Review/Impact evidence exercises real saved artifacts.",
        "actual": "The harness initially recognized only `mem review audit --session uid`, not Audit snapshot's `SESSION [uid]`, so Review attempts 1, 2, 4, and 5 passed `deadbeef`. Review 3 used an unsupported Context-only saved-Audit route. Impact 5 requested the current round's Meld artifact before Meld 5 existed. All five Dedun attempts also combined hidden `--plain` replay state with exact discovery and were rejected. Late-bound source selectors caused Rationale/Trace/Translate and Update 3 to use the final round's approval Source; ledger routes are corrected to the actual argv rather than the intended Sources.",
        "workaround": "The harness source now recognizes bracketed Audit sessions. For a new campaign, bind every lambda default eagerly, use prior-round artifacts when Impact precedes creation, omit hidden `--plain` from exact Dedun discovery, and validate generated argv before the first counted call.",
        "reproduction": "Deterministic from the recorded argv/raw output; no extra mem calls were made because the 120-command contract forbids replacement attempts.",
        "evidence": [
            evidence(12, 1, "dedun", 1), evidence(20, 1, "review", 1),
            evidence(44, 2, "review", 1), evidence(68, 3, "review", 1),
            evidence(92, 4, "review", 1), evidence(108, 5, "dedun", 1),
            evidence(111, 5, "impact", 1), evidence(116, 5, "review", 1),
        ],
    },
    {
        "id": "T3V2-SEVER-PROVIDER-CONTRACT-FAILURE",
        "title": "One Sever result failed complete-output validation",
        "classification": "provider output / infrastructure failure",
        "severity": "P2 / medium campaign impact; fail-closed",
        "regression": "one current-campaign provider contract failure",
        "expected": "Sever returns exactly one validated disposition per Source Memory with an application summary citing only Criteria related to a change.",
        "actual": "Round 2 failed with `The application summary cites Criteria unrelated to a change.` No Source or Result Context was changed. Four other Sever variants produced saved READY sessions.",
        "workaround": "Keep the failure fail-closed, retain the exact Source/Criteria frame, and retry only as a separately counted operation while checking the full session contract.",
        "reproduction": "1/5 Sever attempts; validation correctly prevented publication.",
        "evidence": [evidence(45, 2, "sever", 1)],
    },
]


DEFECTS = {
    1: ["T3V2-ATOMIZE-PROVIDER-TIMEOUT"],
    9: ["T3V2-ELABORATE-UNVERIFIED-ORDINARY-MEMORY"],
    12: ["T3V2-TRANSFORM-HARNESS-ARTIFACT-ROUTING"],
    13: ["T3V2-FORGET-SAFETY-GATE-LOSS"],
    16: ["T3V2-MELD-EAGER-EMPTY-RESULT"],
    20: ["T3V2-TRANSFORM-HARNESS-ARTIFACT-ROUTING"],
    21: ["T3V2-SEVER-OPAQUE-READY"],
    24: ["T3V2-GRANT-EMBED-SEMANTIC-DEAD-END"],
    33: ["T3V2-ELABORATE-UNVERIFIED-ORDINARY-MEMORY"],
    34: ["T3V2-RESOLVE-OPAQUE-NOCHANGE"],
    36: ["T3V2-TRANSFORM-HARNESS-ARTIFACT-ROUTING"],
    44: ["T3V2-TRANSFORM-HARNESS-ARTIFACT-ROUTING"],
    45: ["T3V2-SEVER-PROVIDER-CONTRACT-FAILURE"],
    48: ["T3V2-UPDATE-AUTO-APPLY-OPAQUE"],
    58: ["T3V2-RESOLVE-OPAQUE-NOCHANGE"],
    60: ["T3V2-TRANSFORM-HARNESS-ARTIFACT-ROUTING"],
    61: ["T3V2-FORGET-SAFETY-GATE-LOSS"],
    68: ["T3V2-TRANSFORM-HARNESS-ARTIFACT-ROUTING"],
    69: ["T3V2-SEVER-OPAQUE-READY"],
    72: ["T3V2-UPDATE-AUTO-APPLY-OPAQUE"],
    73: ["T3V2-GRANTED-TRANSFORM-ROUTE-INCONSISTENCY"],
    82: ["T3V2-RESOLVE-OPAQUE-NOCHANGE"],
    84: ["T3V2-TRANSFORM-HARNESS-ARTIFACT-ROUTING"],
    87: ["T3V2-GRANTED-TRANSFORM-ROUTE-INCONSISTENCY"],
    92: ["T3V2-TRANSFORM-HARNESS-ARTIFACT-ROUTING"],
    93: ["T3V2-SEVER-OPAQUE-READY"],
    96: ["T3V2-GRANT-EMBED-SEMANTIC-DEAD-END"],
    106: ["T3V2-RESOLVE-OPAQUE-NOCHANGE"],
    108: ["T3V2-TRANSFORM-HARNESS-ARTIFACT-ROUTING"],
    109: ["T3V2-FORGET-SAFETY-GATE-LOSS"],
    111: ["T3V2-TRANSFORM-HARNESS-ARTIFACT-ROUTING"],
    112: ["T3V2-MELD-EAGER-EMPTY-RESULT"],
    116: ["T3V2-TRANSFORM-HARNESS-ARTIFACT-ROUTING"],
    117: ["T3V2-SEVER-OPAQUE-READY"],
    120: ["T3V2-UPDATE-AUTO-APPLY-OPAQUE"],
}


def main() -> None:
    phase = json.loads(PHASE.read_text())
    phase["study"] = "study-long-audit-20260825-v2"
    records = sorted(
        (record for payload in phase["operations"].values() for record in payload["attempts"]),
        key=lambda record: record["sequence"],
    )
    core_digest = phase["starting_boundary"]["core_final_digest"]
    first_pre = records[0]["pre_target_digest"]["sha256"]
    phase["cumulative_bridge"] = {
        "from_phase": "core",
        "to_phase": "transform",
        "core_final_post_target_digest_sha256": core_digest,
        "transform_first_pre_target_digest_sha256": first_pre,
        "exact_match": core_digest == first_pre,
        "store_reset_between_phases": False,
        "evidence": {
            "core_final_sequence": 105,
            "transform_first_sequence": 1,
            "scope": "lane-local task-3 Context subtree",
        },
    }
    phase["outcome"] = {
        "external_transfer": "none — Share/export/clipboard/external targets were never invoked",
        "selected_information": "none approved; candidate accessibility/communication needs and current medication facts remain unverified",
        "excluded_information": "third-party transport preference, unrelated personal history, and stale/underspecified medication facts remain excluded",
        "decision_gate": (
            "Exact recipient, purpose, selected Memory units, channel, retention expectations, "
            "currentness/necessity verification, and explicit user approval are still required."
        ),
        "local_only_effects": (
            "Checkpointed destructive trials were restored. Two symmetric Meld NEEDS INPUT calls "
            "left empty local Result Contexts. Post-Revert Updates changed only local audit scratch "
            "and printed Undo recovery receipts; no external disclosure occurred."
        ),
    }
    for record in records:
        record["defect_ids"] = DEFECTS.get(record["sequence"], [])
        if record["operation"] in {"rationale", "trace", "translate"}:
            record["target_route"] = APPROVAL_ROUTE = "task-3/local/guardrails/approval-and-delivery exact Memory"
            record["input_provenance"] += (
                "; corrected to actual argv: late-bound harness selector used the approval-and-delivery "
                "Memory in every round"
            )
        if record["sequence"] == 72:
            record["target_route"] = (
                "task-3/local/guardrails/approval-and-delivery → "
                "task-3/local/guardrails/audit-and-recovery"
            )
            record["input_provenance"] += "; corrected to actual late-bound Source shown in argv/output"
        if record["operation"] == "revert":
            same = {1: False, 2: True, 3: True, 4: True, 5: False}[record["attempt"]]
            record["recovery_evidence"] = (
                "Revert exit 0 restored the named direct target from the same-round manual checkpoint. "
                + (
                    "The full task-tree digest returned exactly to the round checkpoint boundary."
                    if same
                    else "The full tree digest differs only because symmetric Meld created a separate empty local Result Context outside the direct checkpoint target."
                )
            )
    phase["status"] = "complete"
    phase["issue_registry"] = {
        "path": "agent-records/outputs/study-long-audit-20260825-v2/worlds/task-3/issues.json",
        "transform_issue_ids": [issue["id"] for issue in TRANSFORM_ISSUES],
        "referenced_issue_ids": sorted({item for record in records for item in record["defect_ids"]}),
    }
    PHASE.write_text(json.dumps(phase, ensure_ascii=False, indent=2) + "\n")

    registry = json.loads(ISSUES.read_text())
    registry["phase"] = "core+transform"
    existing = {issue["id"]: issue for issue in registry["issues"]}
    grant = existing["T3V2-GRANT-EMBED-SEMANTIC-DEAD-END"]
    grant["actual"] += (
        " Transform Update reproduced the same fail-closed blockage twice even with explicit direct "
        "Source/Target routes: the local Target's granted Embed prevented semantic work through its local owner."
    )
    grant["additional_transform_evidence"] = [
        evidence(24, 1, "update", 1), evidence(96, 4, "update", 1)
    ]
    for issue in TRANSFORM_ISSUES:
        issue["evidence_sequences"] = [item["sequence"] for item in issue["evidence"]]
        existing[issue["id"]] = issue
    # Preserve authored CORE order, then append TRANSFORM issues in the order above.
    core_ids = [issue["id"] for issue in registry["issues"]]
    registry["issues"] = [existing[issue_id] for issue_id in core_ids] + TRANSFORM_ISSUES
    ISSUES.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n")

    lines = [
        "# task-3 TRANSFORM issues",
        "",
        "120 counted commands completed through the pinned runner. No external transfer occurred.",
        "",
    ]
    for issue in TRANSFORM_ISSUES:
        lines.extend([
            f"## {issue['id']} — {issue['title']}",
            "",
            f"- Severity: {issue['severity']}",
            f"- Classification: {issue['classification']}",
            f"- Expected: {issue['expected']}",
            f"- Actual: {issue['actual']}",
            f"- Workaround: {issue['workaround']}",
            f"- Reproduction: {issue['reproduction']}",
            "",
        ])
    (WORLD / "issues-transform.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
