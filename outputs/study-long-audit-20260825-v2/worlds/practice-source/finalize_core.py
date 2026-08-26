#!/usr/bin/env python3
"""Attach reviewed findings and verification summaries to phase-core.json."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PATH = ROOT / "phase-core.json"

DEFECT_SEQUENCES = {
    "PS2-CTX-OVERLOAD": {1, 22, 43, 64, 85},
    "PS2-MULTIROOT-COVERAGE": {47, 68, 89},
    "PS2-SUMMARY-EVIDENCE-OMISSION": {28, 49, 70, 91},
    "PS2-QUERY-REFERENCE-OVERLOAD": {69, 90},
    "PS2-CHUNK-CONTEXT-LOSS": {36, 57, 61, 66, 78, 82, 87, 89, 103, 104},
    "PS2-CHUNK-RECEIPT": {36, 57, 78},
    "PS2-QUALITY-SCOPE-MISMATCH": {17, 18, 80, 81},
    "PS2-FIT-OPAQUE": {21, 42, 63, 84, 105},
    "PS2-CONFLICT-SELF-CONTRADICTION": {41},
}

ACTUAL = {
    1: "Printed 112 visible inventory rows for the entire Profile: three local practice names were followed by task-1/task-2/task-3 trees and Grants; no prefix or subtree narrowing was available.",
    17: "Checked 3 direct items in practice (one ordinary Memory, one Reference, and one Context Embed) and reported no exact duplicate groups.",
    18: "On the same practice state, reported only 1 direct memory and no redundancy groups; the receipt did not explain why the sibling quality command's direct cardinality was 3.",
    21: "Printed only `FIT · YES · [TARGETS: CONTEXT practice/source, practice]`; no source-to-target mapping, evidence, omissions, or caveats were exposed.",
    22: "Repeated the 112-row whole-Profile catalog after early scratch growth; direct-item growth was invisible and no practice-only inventory route existed.",
    28: "Returned a useful one-sentence summary of the sole ordinary scratch Memory but silently excluded the directly listed citation Reference and source Context Embed; `STATUS · DIRECT` did not define that exclusion.",
    36: "Successfully split the polishing candidate into 2 Memories. The receipt omitted both new UIDs and truncated the first preview mid-word; the second result `Change only wording that causes a problem.` lost its authorized-polishing trigger.",
    41: "Flagged 9/66 source pairs. Item 9 was labeled `CONFLICT`, yet its own reason explicitly said `There is no semantic conflict`; several other possible conflicts merely combined rules with distinct request triggers.",
    42: "Printed only `FIT · YES` and the two Context names despite the source/scratch coverage gap.",
    43: "Repeated the 112-row whole-Profile catalog after generated split Memories existed; the command still offered no practice subtree narrowing.",
    47: "A two-root Search requested practice/source and practice but returned only three source Memories and gave no disposition for the zero-result/ranked-out practice root.",
    49: "Summarized ordinary Memories in practice/description but did not disclose exclusion of its direct original-source Reference and live practice/source Embed.",
    57: "Successfully split the fixed-limit candidate into 2 Memories, omitted both UIDs, and truncated both previews. The 20-30% trigger/action was detached from the all-points and claim-strength safeguards.",
    61: "Flagged the split 20-30% candidate's percentage baseline ambiguity, demonstrating that the standalone split no longer carried its companion safeguard or enough precision for independent review.",
    63: "Printed only `FIT · YES` and Context names even though the scratch frame contained a trigger/safeguard pair damaged by sentence splitting.",
    64: "Repeated the 112-row whole-Profile catalog before boundary trials; no scoped inventory or filter was available.",
    66: "Rendered the detached all-points/claim-strength safeguard created by the prior Chunk, confirming it now stood without the fixed-limit applicability trigger.",
    68: "A two-root Search requested source and accumulated practice scratch; all 8 results came from practice/source and the zero-contribution scratch root was not reported.",
    69: "Produced a strong classification but expanded to all 12 source Memories and 12 inline References for a question centered on two defaults and their narrow override rules.",
    70: "Summarized only ordinary practice Memories and did not disclose exclusion of multiple direct References or two live Context Embeds.",
    74: "Correctly rejected a duplicate live Embed because practice already embedded the same practice/source identity; stdout was empty and stderr named the duplicate owner/target.",
    78: "Successfully split the title/italics candidate into 2 Memories, omitted both UIDs, and truncated both previews. The first result ended `preserve the intended word for.` without the protected literal object's completion/context.",
    80: "Reported 10 direct items checked in practice/description and no exact duplicate groups.",
    81: "On the same Context state, reported 8 direct memories and no redundancy groups without explaining the two-item direct-scope difference.",
    82: "Flagged the generated title half as UNDERSPECIFIED because `preserve the intended word for` had no object; this independently confirms semantic damage from sequence 78.",
    84: "Printed only `FIT · YES` and Context names despite confirmed underspecification in the compared scratch frame.",
    85: "Repeated the 112-row whole-Profile catalog at late accumulated state; practice remained only three rows amid unrelated world trees and Grants.",
    87: "Rendered the damaged title chunk `preserve the intended word for.` by its UID, confirming the incomplete object persisted into late scratch state.",
    89: "A three-root Search requested source, practice, and practice/description but returned only two damaged practice Memories. It omitted the known damaged title chunk in description, source companions, and all branch dispositions.",
    90: "Produced a semantically useful atomization proposal with all 12 source Memories as 12 long inline References (44 captured lines) but no reusable proposed-atom-to-source-UID structure.",
    91: "Summarized ordinary practice/description Memories while silently omitting its References and live Embeds, including the now cyclic practice edge; `STATUS · DIRECT` did not state the item-type boundary.",
    95: "Accepted the indirect practice/description ↔ practice live-Embed cycle, which is permitted by the documented graph model; later recursive analysis terminated finitely by Context identity.",
    103: "Again flagged the persisted title chunk as UNDERSPECIFIED because the protected word object remained incomplete.",
    104: "Flagged 3 possible conflicts among split scratch Memories, including 20-30% cutting versus preserving all points/claim strength, demonstrating why the companion safeguards cannot be reviewed independently after mechanical splitting.",
    105: "Printed only `FIT · YES` and Context names even though the target still contained a confirmed underspecified title chunk and split-induced possible conflicts.",
}


def main() -> None:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    attempts = [
        attempt
        for operation in data["operations"].values()
        for attempt in operation["attempts"]
    ]
    by_sequence = {attempt["sequence"]: attempt for attempt in attempts}
    if set(by_sequence) != set(range(1, 106)):
        raise RuntimeError("expected sequences 1..105")

    for defect_id, sequences in DEFECT_SEQUENCES.items():
        for sequence in sequences:
            by_sequence[sequence]["defect_ids"].append(defect_id)
    for sequence, actual in ACTUAL.items():
        by_sequence[sequence]["actual"] = actual

    by_sequence[36]["recovery_evidence"] = (
        "Sequence 44 List exposed both generated UIDs, and sequence 45 Show reused "
        "the trigger-bearing half; no retry or source mutation occurred."
    )
    by_sequence[57]["recovery_evidence"] = (
        "Sequence 66 Show reused the detached safeguard UID; sequences 61 and 104 "
        "demonstrated the resulting ambiguity/conflict while source stayed unchanged."
    )
    by_sequence[74]["recovery_evidence"] = (
        "Its pre/post composite target digests are identical. Sequence 86 later listed "
        "only the original source Embed in practice/description, and source remained unchanged."
    )
    by_sequence[78]["recovery_evidence"] = (
        "Sequence 86 List exposed both generated UIDs; sequences 87, 82, and 103 "
        "rendered and diagnosed the incomplete title half without touching source."
    )
    by_sequence[95]["expected"] = (
        "Persist the requested indirect live-Embed cycle because the documented graph "
        "model permits it, while recursive consumers must terminate by Context identity."
    )
    by_sequence[95]["recovery_evidence"] = (
        "Sequence 101 recursively checked exactly 3 Context identities and terminated "
        "normally, providing finite-cycle verification."
    )
    by_sequence[101]["recovery_evidence"] = (
        "The recursive traversal completed with 3 Contexts and 39 direct items despite "
        "the persisted indirect Embed cycle, confirming identity-based termination."
    )

    signatures = {}
    for operation, payload in data["operations"].items():
        values = {
            (
                attempt["entry_route"],
                attempt["target_route"],
                attempt["scope"],
                attempt["input_provenance"],
            )
            for attempt in payload["attempts"]
        }
        signatures[operation] = len(values)
    raw_count = len(list((ROOT / "raw" / "core").glob("*.txt")))
    data["verification"] = {
        "attempts": len(attempts),
        "raw_outputs": raw_count,
        "operation_attempt_counts": {
            operation: len(payload["attempts"])
            for operation, payload in data["operations"].items()
        },
        "diversity_signature_counts": signatures,
        "nonzero_exits": [
            attempt["sequence"] for attempt in attempts if attempt["exit"] != 0
        ],
        "source_digest_preserved": (
            data["execution_boundary"]["source_initial_sha256"]
            == data["execution_boundary"]["source_current_sha256"]
        ),
        "wall_seconds": round(sum(a["cost"]["wall_seconds"] for a in attempts), 6),
    }
    if raw_count != 105 or set(signatures.values()) != {5}:
        raise RuntimeError("raw-output or five-method diversity contract failed")
    data["outcome"] = (
        "Complete: 105/105 counted attempts, all 21 operations at five distinct "
        "route/provenance signatures; practice/source digest preserved."
    )
    PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
