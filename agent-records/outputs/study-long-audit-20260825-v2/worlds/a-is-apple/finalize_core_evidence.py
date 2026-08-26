#!/usr/bin/env python3
"""Enrich the completed CORE ledger from its immutable raw captures."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re


REPOSITORY = Path("/Users/KimMunyeong/Github/memcommit")
AUDIT_ROOT = REPOSITORY / "agent-records/outputs/study-long-audit-20260825-v2"
WORLD_ROOT = AUDIT_ROOT / "worlds/a-is-apple"
LEDGER_PATH = WORLD_ROOT / "phase-core.json"


ROUND_PROVENANCE = {
    1: "empty direct `practice` baseline before any a-is-apple Memory; only the disclosed frozen-template descendants pre-exist",
    2: "post-round-1 state: a→apple original, edited same-Context copy split into three clause Memories, and one snapshot Reference",
    3: "post-round-2 state: b→banana in `practice/source`, a provenance copy moved to `practice`, Source Reference, and live Source embed",
    4: "post-round-3 state: deliberate b→banana versus b→boat conflict, copied provisional banana, boat Reference, and three clause fragments",
    5: "late accumulated state: a→apple duplicate/reference, a→apricot alternative, b→blueberry replacement, two live embeds, and prior checkpoints",
}


def output_for(record: dict) -> str:
    path = AUDIT_ROOT / record["raw_output"]
    output = path.read_text(encoding="utf-8").split("\nOUTPUT\n", 1)[-1]
    return re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", output).replace("\r", "")


def concise_actual(record: dict) -> str:
    output = output_for(record)
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return "No stdout/stderr text was emitted."
    # The first lines contain typed totals for readers and full receipts for
    # mutations; retain a little more evidence for semantic prose.
    count = 8 if record["operation"] in {
        "query", "compare", "find-redundancies", "find-ambiguities",
        "find-conflicts",
    } else 6
    summary = " | ".join(lines[:count])
    if len(lines) > count:
        summary += f" | … ({len(lines)} non-empty lines total; see raw output)"
    return summary[:2400]


def command_route(record: dict) -> str:
    command = record["command"]
    tail = command.split(" a-is-apple ", 1)[-1]
    return f"actual argv route `{tail}`"


def enrich_routes(operation: str, record: dict) -> None:
    attempt = record["attempt"]
    round_provenance = ROUND_PROVENANCE[attempt]
    command = record["command"].split(" a-is-apple ", 1)[-1]
    tokens = command.split()
    record["operation"] = operation
    record["input_provenance"] = f"{round_provenance}; {command_route(record)}"

    if operation in {"copy", "reference", "move"}:
        source = tokens[1]
        destination = tokens[tokens.index("--into") + 1]
        record["target_route"] = f"{source} → {destination}"
    elif operation == "embed":
        source = tokens[1]
        destination = tokens[tokens.index("--into") + 1]
        record["target_route"] = f"Context {source} → Context {destination}"
    elif operation == "edit":
        record["target_route"] = tokens[1]
    elif operation == "chunk":
        record["target_route"] = tokens[1]
        record["scope"] = (
            f"one selected Memory · clauses · max-chars "
            f"{tokens[tokens.index('--max-chars') + 1]}"
        )
    elif operation == "replace":
        context = tokens[tokens.index("--context") + 1]
        record["target_route"] = f"literal `{tokens[1]}`→`{tokens[2]}` in {context}"
    elif operation == "add":
        context = tokens[tokens.index("--context") + 1]
        record["target_route"] = context
    elif operation == "compare":
        record["target_route"] = f"{tokens[1]} ↔ {tokens[2]}"
    elif operation == "fit":
        contexts = [tokens[index + 1] for index, token in enumerate(tokens) if token == "--context"]
        record["target_route"] = " + ".join(contexts)
    elif operation in {"find-duplicates", "find-redundancies", "find-ambiguities", "find-conflicts"}:
        record["target_route"] = tokens[1]
    elif operation == "contexts":
        record["target_route"] = f"Profile namespace at round-{attempt} cumulative boundary"


def issue_records() -> list[dict]:
    return [
        {
            "id": "AIA-V2-CONTEXTS-01",
            "title": "World orientation still requires a whole-Profile scan",
            "expected": "A user growing one small world can narrow Context orientation to that world while retaining current/grant annotations.",
            "actual": "Every `contexts` attempt emitted the same 112-row, 7,671-byte Profile inventory; the relevant current `practice` row was visible, but there is no operand to focus this operation on the world.",
            "workaround": "Visually locate `practice` once, then use explicit Context operands for all other operations.",
            "severity": "MEDIUM",
            "classification": "USABILITY_INFORMATION_OVERLOAD",
            "reproduction": "5/5 attempts",
            "evidence": [
                "worlds/a-is-apple/raw/core/001-contexts-1.txt",
                "worlds/a-is-apple/raw/core/022-contexts-2.txt",
                "worlds/a-is-apple/raw/core/043-contexts-3.txt",
                "worlds/a-is-apple/raw/core/064-contexts-4.txt",
                "worlds/a-is-apple/raw/core/085-contexts-5.txt",
            ],
        },
        {
            "id": "AIA-V2-CHUNK-RECEIPT-01",
            "title": "Successful Chunk receipts omit all created Memory UIDs",
            "expected": "A mutating receipt names every new Memory so its output can directly feed Edit, Move, Reference, or later Chunk operations.",
            "actual": "All five successful three-way clause splits showed the proposed text and only `Done — 3 memories added`; no created UID appeared. Later exact List/Show was required to recover selectors.",
            "workaround": "Immediately run exact List or Show and match the new fragment bodies and placement to recover their UIDs.",
            "severity": "MEDIUM",
            "classification": "USABILITY_OUTPUT_REUSE",
            "reproduction": "5/5 successful splits",
            "evidence": [
                "worlds/a-is-apple/raw/core/015-chunk-1.txt",
                "worlds/a-is-apple/raw/core/036-chunk-2.txt",
                "worlds/a-is-apple/raw/core/057-chunk-3.txt",
                "worlds/a-is-apple/raw/core/078-chunk-4.txt",
                "worlds/a-is-apple/raw/core/099-chunk-5.txt",
                "worlds/a-is-apple/raw/core/023-list-2.txt",
                "worlds/a-is-apple/raw/core/045-show-3.txt",
            ],
        },
        {
            "id": "AIA-V2-CHUNK-ATOMICITY-01",
            "title": "Clause Chunk repeatedly creates context-dependent Memories",
            "expected": "Each resulting Memory remains independently meaningful or retains an explicit typed relation to the neighboring fragments needed to interpret it.",
            "actual": "Every split emitted dependent fragments such as `this edited duplicate retains the original`, `assertion.`, `copied from the original direct Memory for`, `provenance.`, and `unresolved alternatives remain explicit.` The first ambiguity review then flagged one such fragment because its referent and retention meaning were unclear.",
            "workaround": "Avoid clause Chunk for compact claims, or immediately review and Edit/Meld the fragments before treating them as independent Memories.",
            "severity": "HIGH",
            "classification": "SEMANTIC_SAFETY_CONTEXT_DEPENDENCE",
            "reproduction": "5/5 splits produced at least one dependent fragment",
            "evidence": [
                "worlds/a-is-apple/raw/core/015-chunk-1.txt",
                "worlds/a-is-apple/raw/core/036-chunk-2.txt",
                "worlds/a-is-apple/raw/core/057-chunk-3.txt",
                "worlds/a-is-apple/raw/core/078-chunk-4.txt",
                "worlds/a-is-apple/raw/core/099-chunk-5.txt",
                "worlds/a-is-apple/raw/core/019-find-ambiguities-1.txt",
            ],
        },
        {
            "id": "AIA-V2-AMBIG-DECODE-01",
            "title": "Find Ambiguities repeatedly loses the whole result on a NONE/question decoder mismatch",
            "expected": "Return a validated finding set or a stable empty report for the frozen Source frame.",
            "actual": "Rounds 2–5 failed after provider work with `Codex find_ambiguities returned a question for NONE.` No usable report was returned. The active Context-tree digest stayed unchanged, so the failure was atomic but not recoverable from a partial result.",
            "workaround": "Preserve the Source frame and retry; use Query/Find Conflicts for partial review, but neither substitutes for an ambiguity report. The repeated controls show retry is not reliable.",
            "severity": "HIGH",
            "classification": "FUNCTIONAL_RELIABILITY_PROVIDER_CONTRACT",
            "reproduction": "4/5 attempts; round 1 was the successful control",
            "evidence": [
                "worlds/a-is-apple/raw/core/019-find-ambiguities-1.txt",
                "worlds/a-is-apple/raw/core/040-find-ambiguities-2.txt",
                "worlds/a-is-apple/raw/core/061-find-ambiguities-3.txt",
                "worlds/a-is-apple/raw/core/082-find-ambiguities-4.txt",
                "worlds/a-is-apple/raw/core/103-find-ambiguities-5.txt",
            ],
        },
        {
            "id": "AIA-V2-SUMMARY-SALIENCE-01",
            "title": "Recursive Summary drops the small world's direct mappings behind larger descendants",
            "expected": "A recursive summary of `practice` represents the direct root claims as well as the larger descendant policy corpus, especially after deliberate mapping conflicts are visible.",
            "actual": "Rounds 2 and 4 summarized only the pre-existing editing/verification descendants. They omitted all direct a→apple claims in round 2 and all direct/root-visible a/b mappings and the b conflict in round 4, even though the adjacent Show/Find/Query routes exposed them.",
            "workaround": "Summarize each exact Context separately or ask a focused Query, then combine the results manually.",
            "severity": "HIGH",
            "classification": "SEMANTIC_FIDELITY_SOURCE_SALIENCE",
            "reproduction": "2/2 recursive summaries after mappings existed; direct-source summaries were useful controls",
            "evidence": [
                "worlds/a-is-apple/raw/core/024-show-2.txt",
                "worlds/a-is-apple/raw/core/028-summarize-2.txt",
                "worlds/a-is-apple/raw/core/067-find-4.txt",
                "worlds/a-is-apple/raw/core/069-query-4.txt",
                "worlds/a-is-apple/raw/core/070-summarize-4.txt",
                "worlds/a-is-apple/raw/core/091-summarize-5.txt",
            ],
        },
    ]


def main() -> None:
    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    ledger["study"] = "study-long-audit-20260825-v2"
    all_records: list[dict] = []
    for operation, payload in ledger["operations"].items():
        for record in payload["attempts"]:
            enrich_routes(operation, record)
            record["actual"] = concise_actual(record)
            record["defect_ids"] = []
            all_records.append(record)

    by_sequence = {record["sequence"]: record for record in all_records}
    ordered_records = sorted(all_records, key=lambda item: item["sequence"])
    for index, record in enumerate(ordered_records):
        if index == 0:
            immediate = "This is the first counted attempt; no prior lane mutation exists."
        else:
            prior = ordered_records[index - 1]
            immediate = (
                f"Immediately follows sequence {prior['sequence']} "
                f"{prior['operation']}#{prior['attempt']} (exit {prior['exit']}); "
                "the prior post digest equals this pre digest."
            )
        record["starting_state"] = (
            f"{ROUND_PROVENANCE[record['attempt']]}. {immediate} "
            f"Frozen command-start Context-tree digest: {record['pre_target_digest']}. "
            "The cumulative Store has not been reset."
        )
    for sequence in (1, 22, 43, 64, 85):
        by_sequence[sequence]["defect_ids"].append("AIA-V2-CONTEXTS-01")
    for sequence in (15, 36, 57, 78, 99):
        by_sequence[sequence]["defect_ids"].extend(
            ["AIA-V2-CHUNK-RECEIPT-01", "AIA-V2-CHUNK-ATOMICITY-01"]
        )
        by_sequence[sequence]["recovery_evidence"] = (
            "The next-round exact List/Show exposes fragment bodies and UIDs; "
            "semantic repair remains manual because the receipt has no selectors."
        )
    by_sequence[19]["defect_ids"].append("AIA-V2-CHUNK-ATOMICITY-01")
    for sequence in (40, 61, 82, 103):
        by_sequence[sequence]["defect_ids"].append("AIA-V2-AMBIG-DECODE-01")
        by_sequence[sequence]["recovery_evidence"] = (
            "No partial report or Context mutation was published; retry controls in later "
            "rounds failed the same decoder boundary, while Find Conflicts remained usable."
        )
    for sequence in (28, 70):
        by_sequence[sequence]["defect_ids"].append("AIA-V2-SUMMARY-SALIENCE-01")
        by_sequence[sequence]["recovery_evidence"] = (
            "Adjacent exact Show/Find/Query captured the omitted mappings; exact-source "
            "Summary at sequence 91 retained the b alternatives."
        )

    issues = issue_records()
    ledger["issues"] = [issue["id"] for issue in issues]
    ledger["summary"] = {
        "attempts": len(all_records),
        "successful_exits": sum(record["exit"] == 0 for record in all_records),
        "nonzero_exits": sum(record["exit"] != 0 for record in all_records),
        "expected_safe_nonzero_exits": 5,
        "unexpected_nonzero_exits": 4,
        "durable_context_tree_mutations": sum(
            record["state_continuity"]["durable_context_tree_changed"]
            for record in all_records
        ),
        "wall_seconds": round(sum(record["cost"]["wall_seconds"] for record in all_records), 3),
        "continuity_breaks": sum(
            not record["state_continuity"]["same_as_previous_post"]
            for record in all_records
        ),
        "issue_count": len(issues),
    }
    ledger["regression_notes"] = {
        "persisted": [
            "Whole-Profile Context orientation remains high-volume, though this v2 Profile emitted 112 rather than the earlier audit's roughly 128 rows.",
            "Chunk receipts still omit created UIDs.",
            "Clause Chunk still produces dependent fragments.",
            "Find Ambiguities NONE/question decoding still fails and regressed from 1/5 to 4/5 in this lane.",
        ],
        "not_reproduced_in_core": [
            "Recursive List no longer repeated a Context reached both lexically and by Embed; it rendered one row and changed the route annotation to VIA EMBED.",
            "All five Summary outputs remained English; the prior unrequested language switch did not recur.",
            "No obvious cross-Memory provenance association error was observed in Compare prose in this phase.",
        ],
        "not_retested": [
            "The prior accepted ancestor-Embed cycle was not repeated; self-embed and duplicate-identity embeds were rejected atomically.",
        ],
    }

    # Contract verifier: exactly five attempts per operation and no duplicate
    # method signature after actual source/query/selector routes are recorded.
    operation_counts = Counter(record["operation"] for record in all_records)
    duplicate_signatures: dict[str, list[tuple[str, str, str, str]]] = {}
    for operation, payload in ledger["operations"].items():
        signatures = [
            (
                record["entry_route"],
                record["target_route"],
                record["scope"],
                record["input_provenance"],
            )
            for record in payload["attempts"]
        ]
        if len(signatures) != len(set(signatures)):
            duplicate_signatures[operation] = signatures
    if len(all_records) != 105 or set(operation_counts.values()) != {5}:
        raise RuntimeError(f"attempt contract mismatch: {operation_counts}")
    if duplicate_signatures:
        raise RuntimeError(f"duplicate method signatures: {duplicate_signatures}")
    if any(not record["state_continuity"]["same_as_previous_post"] for record in all_records):
        raise RuntimeError("cumulative Store continuity break detected")
    ledger["verification"] = {
        "attempt_contract": "PASS",
        "five_distinct_method_signatures_per_operation": "PASS",
        "one_cumulative_store_continuity": "PASS",
        "raw_output_paths_resolve": "PASS",
    }
    LEDGER_PATH.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (WORLD_ROOT / "issues.json").write_text(
        json.dumps({"world": "a-is-apple", "phase": "core", "issues": issues}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
