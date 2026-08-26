#!/usr/bin/env python3
"""Normalize and classify the completed task-2 TRANSFORM evidence ledger."""

from __future__ import annotations

import json
from pathlib import Path


PATH = Path(__file__).with_name("phase-transform.json")

ISSUES = [
    {
        "id": "T2V2-MELD-PREWARM-SCOPE-01",
        "title": "Explicit symmetric Meld is blocked by an unrelated embedded grant",
        "expected": (
            "A direct symmetric Meld evaluates only its two explicit advisor peers and "
            "fresh Result, then stops at any equal-authority decision gate."
        ),
        "actual": (
            "All five distinct advisor-pair Melds failed before comparison because "
            "task-2/description contains an unrelated advisor1/budget Embed, even when "
            "neither that Context nor description was an endpoint."
        ),
        "workaround": (
            "Use explicit pairwise Compare/Query evidence and leave the synthesis "
            "unapplied; removing the unrelated Embed would mutate the study fixture."
        ),
        "severity": "high",
        "classification": "semantic-operation/authority-scope",
        "evidence_ids": [f"transform:meld:{number}" for number in range(1, 6)],
    },
    {
        "id": "T2V2-RATIONALE-LANGUAGE-01",
        "title": "Rationale provenance silently switches to Chinese",
        "expected": (
            "Rationale preserves the command/session language unless the person asks "
            "for translation."
        ),
        "actual": (
            "Attempt 3 rendered the English Memory normally but synthesized its entire "
            "80-character provenance sentence in Chinese."
        ),
        "workaround": "Use Trace JSON for language-neutral retained evidence and ignore the synthesized prose.",
        "severity": "medium",
        "classification": "semantic-presentation/language-drift",
        "evidence_ids": ["transform:rationale:3"],
    },
    {
        "id": "T2V2-UPDATE-TRACE-METADATA-01",
        "title": "Applied Update checkpoint cannot be correlated by Trace",
        "expected": (
            "An applied cross-Context Update writes valid command-unit metadata so "
            "later Trace can correlate its Memory changes and recovery point."
        ),
        "actual": (
            "Update attempt 1 applied one addition and created checkpoint e8f7aaa4, but "
            "Trace attempts 3 and 5 warned that this checkpoint has invalid Update "
            "command-unit metadata and its changes cannot be correlated across Contexts."
        ),
        "workaround": (
            "Correlate update receipt f451a277 and checkpoint e8f7aaa4 manually; do not "
            "treat the later Trace as a complete cross-Context lineage."
        ),
        "severity": "high",
        "classification": "provenance/command-unit-metadata",
        "evidence_ids": ["transform:update:1", "transform:trace:3", "transform:trace:5"],
    },
    {
        "id": "T2V2-HARNESS-CHECKPOINT-SELECTOR-01",
        "title": "Study harness did not consume short checkpoint receipts",
        "expected": (
            "The study harness carries each successful checkpoint selector into its "
            "subsequent Diff and Revert commands."
        ),
        "actual": (
            "Checkpoint printed an accepted eight-character selector in brackets, but "
            "the harness looked only for a full UID inside a recovery command. It sent "
            "00000000 to five Diffs and four intended Reverts, which failed safely."
        ),
        "workaround": (
            "Parse the bracketed checkpoint prefix before constructing recovery argv; "
            "the five durable checkpoints themselves remain in the isolated Store."
        ),
        "severity": "medium",
        "classification": "study-instrumentation/not-product",
        "evidence_ids": (
            [f"transform:diff:{number}" for number in range(1, 6)]
            + [f"transform:revert:{number}" for number in range(2, 6)]
        ),
    },
]


def attempt(document: dict, operation: str, number: int) -> dict:
    return document["operations"][operation]["attempts"][number - 1]


def main() -> None:
    document = json.loads(PATH.read_text())
    ordered = sorted(
        (
            candidate
            for operation in document["operations"].values()
            for candidate in operation["attempts"]
        ),
        key=lambda candidate: candidate["sequence"],
    )
    assert len(ordered) == 120
    prior_sequences = [candidate["sequence"] for candidate in ordered]
    assert prior_sequences in (list(range(106, 226)), list(range(1, 121)))

    for phase_sequence, candidate in enumerate(ordered, 1):
        raw_world_sequence = int(Path(candidate["raw_output"]).name.split("-", 1)[0])
        candidate["sequence"] = phase_sequence
        candidate["starting_state"] = (
            "same cumulative lane after core; all 105 CORE commands remain accumulated; "
            f"TRANSFORM phase-local sequence {phase_sequence} "
            f"(raw world sequence {raw_world_sequence}) with no Store reset"
        )

    checkpoint_prefixes = ("b393883c", "a475f91c", "888cdcf4", "d2e3d818", "cb95de94")
    for number, prefix in enumerate(checkpoint_prefixes, 1):
        zero_start = (number - 1) * 24
        for candidate in ordered[zero_start + 4 : zero_start + 24]:
            candidate["recovery_evidence"] = (
                f"Checkpoint prefix {prefix} was durably created earlier in round {number}; "
                "pre/post Context SHA-256 and chronological raw output are retained."
            )

    issue_attempts = {
        "T2V2-MELD-PREWARM-SCOPE-01": [("meld", number) for number in range(1, 6)],
        "T2V2-RATIONALE-LANGUAGE-01": [("rationale", 3)],
        "T2V2-UPDATE-TRACE-METADATA-01": [("update", 1), ("trace", 3), ("trace", 5)],
        "T2V2-HARNESS-CHECKPOINT-SELECTOR-01": (
            [("diff", number) for number in range(1, 6)]
            + [("revert", number) for number in range(2, 6)]
        ),
    }
    for issue_id, references in issue_attempts.items():
        for operation, number in references:
            defect_ids = attempt(document, operation, number)["defect_ids"]
            if issue_id not in defect_ids:
                defect_ids.append(issue_id)

    document["issues"] = ISSUES
    document["study"] = "study-long-audit-20260825-v2"
    document["starting_boundary"] = (
        "TRANSFORM starts after core from the exact Store accumulated by all 105 "
        "CORE commands in the same pinned Profile; no reset, replacement, or "
        "alternate Store occurred."
    )
    document["execution_summary"] = {
        "counted_actual_mem_commands": 120,
        "successful_exits": 88,
        "safe_nonzero_exits": 32,
        "provider_infrastructure_failures": 0,
        "store_resets": 0,
        "starting_phase_sequence": 1,
        "ending_phase_sequence": 120,
        "raw_world_sequence_range": [106, 225],
    }
    document["coverage"] = {operation: 5 for operation in document["operations"]}

    for operation, record in document["operations"].items():
        attempts = record["attempts"]
        assert [candidate["attempt"] for candidate in attempts] == [1, 2, 3, 4, 5]
        signatures = {
            (
                candidate["entry_route"],
                candidate["target_route"],
                candidate["scope"],
                candidate["input_provenance"],
            )
            for candidate in attempts
        }
        assert len(signatures) == 5, operation

    PATH.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
