"""Build reviewed task-3 core ledgers from the immutable raw run record."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any


REPO = Path("/Users/KimMunyeong/Github/memcommit")
WORLD = REPO / "agent-records/outputs/study-long-audit-20260825-v2/worlds/task-3"
SOURCE = WORLD / "core-run-record.json"
PHASE = WORLD / "phase-core.json"
ISSUES_JSON = WORLD / "issues.json"
ISSUES_CORE_JSON = WORLD / "issues-core.json"
ISSUES_MD = WORLD / "issues.md"

REPRODUCTION = {
    "T3V2-CONTEXTS-OVERLOAD": "Yes — 5/5 interleaved attempts emitted the same whole-Profile catalog.",
    "T3V2-RECURSIVE-READ-OVERLOAD": "Yes across two sibling operations: one recursive List and one recursive Show of the same accumulated root.",
    "T3V2-SEARCH-DISPOSITION-GAP": "Yes across three materially different semantic searches: broad personal, multi-root, and late safety-worded fallback.",
    "T3V2-SUMMARY-CURATION": "One current-campaign privacy-sensitive month summary, consistent with the prior campaign's same behavior.",
    "T3V2-CHUNK-SAFETY-FRAME": "One isolated destructive split, independently verified by Find Ambiguities and recursive List; no second unsafe split was performed.",
    "T3V2-CHUNK-UID-OMISSION": "One actual three-chunk mutation plus a later owner List that was required to recover all created UIDs.",
    "T3V2-COMPARE-SAME-CONTEXT-MEMORIES": "One exact same-owner/two-Memory attempt; deterministic application validation rejected it before provider work.",
    "T3V2-RECURSIVE-QUALITY-OVERLOAD": "Yes across recursive exact-duplicate and semantic-redundancy sibling operations on the guardrail tree.",
    "T3V2-GRANT-EMBED-SEMANTIC-DEAD-END": "Yes across two semantic consumers after one successful granted Embed: recursive Compare and recursive Summarize both failed closed.",
    "T3V2-FIT-OPAQUE": "Yes — 4/4 successful Fit attempts across Context, direct-Memory, and granted-Source methods returned only YES plus targets.",
    "T3V2-JSON-ZERO-SILENCE": "Yes — three zero-finding structured attempts across two operations emitted nothing; a nonzero redundancy attempt emitted canonical JSON.",
}


ISSUES: list[dict[str, Any]] = [
    {
        "id": "T3V2-CONTEXTS-OVERLOAD",
        "title": "Profile-wide Context discovery has no task-root narrowing",
        "classification": "usability / information overload",
        "severity": "P2 / medium",
        "regression": "confirmed open from T3-CONTEXTS-OVERLOAD",
        "expected": "A person working on task-3 can narrow discovery to its local and granted hierarchy while retaining current, ownership, Grant, and capability annotations.",
        "actual": "Each of five `contexts` attempts printed the identical 113-line, 7,624-byte Profile catalog. The first task-3 row begins only after 61 unrelated rows; the useful task-3 SHARE, QUERY, and READ/EXPORT Grant rows are at the end.",
        "workaround": "Scan once for the `task-3` prefix, then carry exact canonical names into later commands.",
        "evidence_sequences": [1, 22, 43, 64, 85],
    },
    {
        "id": "T3V2-RECURSIVE-READ-OVERLOAD",
        "title": "Recursive List and Show expand the full embedded personal tree without a compact mode",
        "classification": "usability / information overload",
        "severity": "P2 / medium",
        "regression": "newly isolated evidence",
        "expected": "Recursive inspection gives a compact hierarchy and counts first, with a bounded way to drill into effective items when an embedded tree contains hundreds of Memories.",
        "actual": "`list task-3/local --recursive` emitted 904 lines / 68,257 bytes. `show task-3/local --recursive` reported 48 Contexts and 406 Memories, then emitted 752 lines / 62,365 bytes. The complete embedded personal history buried the few locally staged candidates and generated chunk UIDs.",
        "workaround": "Use `--direct`, inspect one exact child at a time, and carry UIDs from narrow receipts. There is no compact recursive summary switch in these attempts.",
        "evidence_sequences": [44, 45],
    },
    {
        "id": "T3V2-SEARCH-DISPOSITION-GAP",
        "title": "Semantic relevance does not produce a safe disclosure disposition",
        "classification": "semantic safety / review friction",
        "severity": "P2 / medium-high",
        "regression": "confirmed open from T3-SEARCH-CURATION",
        "expected": "A privacy-sensitive candidate workflow keeps relevance, currency, third-party status, necessity, and approval visibly separate and makes multi-root coverage explicit.",
        "actual": "The broad personal search ranked a younger brother's transport preference beside medication and accessibility candidates. A two-root top-5 search returned only privacy policy Memories without saying the personal root contributed zero results. The final safety-worded search found no exact results, broadened the query, and returned stale medication evidence and unapproved drafts; it did clearly label them RELATED and warned that they may not satisfy the original query.",
        "workaround": "Search candidate and policy roots independently, reconcile exact Memories against currency/privacy/approval rules, and never treat ranking or RELATED fallback as an include decision.",
        "evidence_sequences": [26, 47, 89],
    },
    {
        "id": "T3V2-SUMMARY-CURATION",
        "title": "Narrative summary blends facts with different disclosure dispositions",
        "classification": "semantic safety / privacy review",
        "severity": "P2 / medium-high",
        "regression": "confirmed open from T3-SUMMARY-CURATION",
        "expected": "A summary used during disclosure review keeps candidate personal facts, third-party facts, uncertainty, and approval state separately inspectable.",
        "actual": "The 2024/03 summary placed a historical medication instruction, clinic-standing/back discomfort, and the younger brother's advance-notice transport preference in one fluent paragraph. It noted medication currency uncertainty but did not mark the brother detail as a separately excluded third-party fact or emit include/exclude/verify dispositions.",
        "workaround": "Use summaries only for orientation, then return to exact Memories, quality findings, and explicit user review before materializing any outbound packet.",
        "evidence_sequences": [28],
    },
    {
        "id": "T3V2-CHUNK-SAFETY-FRAME",
        "title": "Clause Chunk splits a not-approved safety frame into independently retrievable facts",
        "classification": "functional / semantic safety",
        "severity": "P1 / high",
        "regression": "confirmed open from T3-CHUNK-SEMANTICS",
        "expected": "Chunking a disclosure draft preserves the relationship between its status, candidate fact, verification conditions, and approval boundary, or refuses a strategy that would detach them.",
        "actual": "One `DRAFT ONLY` medication candidate became three ordinary Memories: `DRAFT ONLY:`, `medication timing is a candidate;`, and a separate verification clause. Find Ambiguities then flagged the two substantive fragments as underspecified. The local review Context can now retrieve the medication claim without its not-approved marker.",
        "workaround": "Do not clause-chunk safety-gated disclosures. Keep status, fact, currency conditions, and approval in one Memory or use a typed compound structure.",
        "evidence_sequences": [36, 40, 44],
    },
    {
        "id": "T3V2-CHUNK-UID-OMISSION",
        "title": "Successful multi-Chunk receipt omits created Memory UIDs",
        "classification": "functional / output reuse",
        "severity": "P2 / medium",
        "regression": "confirmed open from T3-CHUNK-TRACEABILITY",
        "expected": "A successful split prints every created UID so Show, Edit, Move, Reference, quality checks, and audit records can consume the result directly.",
        "actual": "The receipt previewed three fragments and ended with `Done — 3 memories added`, but printed no created UID. Recursive List was needed to discover 26a4a267, eebb79a4, and d0f1069a.",
        "workaround": "Run List on the exact owner and manually match generated text to the new UIDs.",
        "evidence_sequences": [36, 44],
    },
    {
        "id": "T3V2-COMPARE-SAME-CONTEXT-MEMORIES",
        "title": "Two documented direct-Memory endpoints cannot be compared when they share an owner Context",
        "classification": "functional / operand contract",
        "severity": "P2 / medium",
        "regression": "new finding",
        "expected": "The documented auto-typed Memory endpoint form compares two distinct Memories and uses their neighbors only as non-actionable context, including when both direct Memories share an owner.",
        "actual": "Two distinct qualified Memory endpoints, 18d58666 and e6023aed in 2024/03, were both recognized but the command failed before analysis with `Compare requires two distinct Contexts.` No state changed.",
        "workaround": "Compare the whole owner Context to another Context, or copy one Memory into a separate local scratch Context before comparison; neither is equivalent to the requested evidence-level comparison.",
        "evidence_sequences": [58],
    },
    {
        "id": "T3V2-RECURSIVE-QUALITY-OVERLOAD",
        "title": "Recursive quality reports enumerate every empty child and semantic redundancy remains slow",
        "classification": "usability / latency and report density",
        "severity": "P2 / medium",
        "regression": "confirmed open but materially faster than T3-RECURSIVE-OVERLOAD",
        "expected": "Recursive quality checks foreground findings and summarize empty child frames, with drill-down evidence and bounded progress for semantic work.",
        "actual": "Recursive exact duplicate analysis printed 11 empty Context sections for zero groups. Recursive redundancy analysis checked 81 Memories in 11 frames, took 44.31 seconds, found zero groups, and printed all 11 empty sections. This is improved from the prior campaign's 176-second 46-Context example but remains expensive and noisy.",
        "workaround": "Use a broad literal/semantic retrieval pass to identify a likely child, then run quality analysis on that exact child; use JSON evidence only where a finding is expected.",
        "evidence_sequences": [59, 81],
    },
    {
        "id": "T3V2-GRANT-EMBED-SEMANTIC-DEAD-END",
        "title": "A readable granted Embed blocks recursive semantic work through its local owner",
        "classification": "workflow composition / authorization usability",
        "severity": "P2 / medium-high",
        "regression": "new finding; failure is correctly fail-closed",
        "expected": "After a readable public Context is intentionally embedded, recursive semantic operations either skip the Embed with a visible reason, expose independent Embed traversal, or accept the same granted Source through an explicit authority-bearing peer selection.",
        "actual": "Embedding the READ+EMBED+DERIVE public guidance succeeded. A recursive Compare then explicitly selected that same public guidance as its peer, yet failed because the local reference frame encountered the granted Embed through its local owner. Final recursive Summarize of `task-3/local` failed for the same reason. Both failures occurred before provider connection/publication and clearly explained the authority boundary.",
        "workaround": "Use direct local scope, summarize/compare individual local children, and select the granted Source separately. Once embedded, there is no observed recursive-local scope that includes lexical descendants while excluding only granted Embeds for these commands.",
        "evidence_sequences": [74, 79, 91],
    },
    {
        "id": "T3V2-FIT-OPAQUE",
        "title": "Positive Fit receipts expose no support, exclusions, or next action",
        "classification": "usability / decision explainability",
        "severity": "P2 / medium-high",
        "regression": "confirmed open from T3-FIT-OPAQUE",
        "expected": "A positive Fit result identifies the propositions/evidence that jointly fit, what was excluded or uncertain, and why the result is not approval for external disclosure.",
        "actual": "All four successful Context/Memory/granted-source attempts printed only `FIT · YES` and target labels. They exposed no receipt UID, source-linked rationale, mismatches, uncertainty, excluded items, or next review action. The empty direct-root attempt failed clearly and safely.",
        "workaround": "Use Compare, Query References, exact Show, and ambiguity/conflict analysis to reconstruct evidence. Treat Fit YES only as joint consistency, never disclosure approval.",
        "evidence_sequences": [42, 63, 84, 105],
    },
    {
        "id": "T3V2-JSON-ZERO-SILENCE",
        "title": "Structured evidence modes emit an empty stream for a successful zero-finding result",
        "classification": "machine-consumption / observability",
        "severity": "P3 / low-medium",
        "regression": "new finding",
        "expected": "A machine-readable zero-finding result emits a stable empty-result record or summary so callers can distinguish successful zero from accidentally lost output without relying only on process status.",
        "actual": "`find-conflicts --handoff-json` twice and `find-redundancies --evidence-json` once exited 0 with zero stdout and stderr when no findings existed. The same redundancy mode emitted canonical JSON when one finding existed, confirming the silent stream is the zero-result representation.",
        "workaround": "Capture the exit code and run the human-readable form when an explicit zero receipt is required.",
        "evidence_sequences": [62, 102, 104],
    },
]


DEFECTS_BY_SEQUENCE: dict[int, list[str]] = {}
for issue in ISSUES:
    for sequence in issue["evidence_sequences"]:
        DEFECTS_BY_SEQUENCE.setdefault(sequence, []).append(issue["id"])


def compact_actual(record: dict[str, Any]) -> str:
    output = (record["stdout"] + record["stderr"]).strip()
    if not output:
        return f"Exited {record['exit']} with no stdout or stderr."
    flattened = re.sub(r"\s+", " ", output)
    if len(flattened) > 700:
        flattened = flattened[:697].rstrip() + "..."
    return f"Exited {record['exit']}. {flattened}"


def continuity(record: dict[str, Any]) -> dict[str, Any]:
    changed = (
        record["pre_target_digest"]["sha256"]
        != record["post_target_digest"]["sha256"]
    )
    mutating = record["operation"] in {
        "add",
        "copy",
        "reference",
        "embed",
        "edit",
        "move",
        "replace",
        "chunk",
    }
    if record["exit"] != 0:
        review = (
            "task-3 Context tree remained unchanged across the rejected boundary; "
            "no partial local publication observed"
            if not changed
            else "unexpected task-3 Context-tree change across a failed command"
        )
    elif changed and mutating:
        review = "lane-local task-3 tree changed as expected for the successful mutation"
    elif not changed and mutating:
        review = "successful mutation route was an intentional no-op; task-3 tree remained unchanged"
    elif not changed:
        review = "read-only/analytic attempt left the lane-local task-3 Context tree unchanged"
    else:
        review = "unexpected task-3 Context-tree change during a read-only/analytic attempt"
    return {"task_tree_changed": changed, "review": review}


def markdown_issues() -> str:
    lines = [
        "# task-3 core audit v2 issues",
        "",
        "No external healthcare transmission was executed. Candidate material and audit records remained in lane-local scratch. The outcome is a genuine user decision gate, not a completed disclosure.",
        "",
    ]
    for issue in ISSUES:
        lines.extend(
            [
                f"## {issue['id']} — {issue['title']}",
                "",
                f"- Classification: **{issue['classification']}**",
                f"- Severity: **{issue['severity']}**",
                f"- Regression status: {issue['regression']}",
                f"- Reproduction: {REPRODUCTION[issue['id']]}",
                f"- Expected: {issue['expected']}",
                f"- Actual: {issue['actual']}",
                f"- Workaround: {issue['workaround']}",
                "- Evidence: "
                + ", ".join(
                    f"sequence {sequence} (`raw/core/{sequence:03d}-"
                    + next(
                        record["operation"]
                        for record in json.loads(SOURCE.read_text(encoding="utf-8"))["attempts"]
                        if record["sequence"] == sequence
                    )
                    + f"-a{next(record['attempt'] for record in json.loads(SOURCE.read_text(encoding='utf-8'))['attempts'] if record['sequence'] == sequence)}.txt`)"
                    for sequence in issue["evidence_sequences"]
                ),
                "",
            ]
        )
    lines.extend(
        [
            "## Regression checks that passed",
            "",
            "- **T3-QUERY-TARGETING resolved in this snapshot:** four exact QUERY-only routes (sequences 6, 27, 69, and 90) returned endpoint-specific scope and capability answers; none labeled or quoted `task-3/local/personal-memory`. Ordinary multi-root Query at sequence 48 separately returned source-linked References.",
            "- **T3-GRANT-SELECTIVE-TRANSFER resolved in this snapshot:** selective granted Memory Reference (sequence 73) and Copy (sequence 93) both succeeded and preserved the public Source owner. Whole-Context Embed also succeeded at sequence 74.",
            "- **T3-AMBIGUITY-PROVIDER did not reproduce:** all five ambiguity attempts succeeded, including the 25-Memory granted frame and 14-Memory final audit frame.",
            "- Parser and safe-boundary checks behaved correctly: invalid singular Chunk, empty direct-root Fit, and same-owner Move all failed without changing the task-3 Context tree; valid later routes recovered.",
            "",
            "## Safe world outcome",
            "",
            "The evidence supports only local candidate review. Potentially useful categories are explanation-format preferences and an accommodation/waiting experience, but both need currentness, necessity, and exact-item review. Historical medication timing is stale and lacks medication identity/current prescription. Relatives' contact, transport preferences, private reasons, and unrelated family/restaurant history remain excluded. Exact recipient/authority, purpose, items, channel, retention terms, and explicit user approval are still missing, so no Share or external transfer was attempted.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    records = source["attempts"]
    operations: dict[str, dict[str, Any]] = {}
    for record in records:
        operation = record["operation"]
        attempt = {
            key: record[key]
            for key in (
                "attempt",
                "sequence",
                "command",
                "exit",
                "starting_state",
                "entry_route",
                "target_route",
                "scope",
                "input_provenance",
                "consumer",
                "expected",
                "cost",
                "pre_target_digest",
                "post_target_digest",
                "recovery_evidence",
                "raw_output",
            )
        }
        attempt["actual"] = compact_actual(record)
        attempt["defect_ids"] = DEFECTS_BY_SEQUENCE.get(record["sequence"], [])
        attempt["state_continuity"] = continuity(record)
        operations.setdefault(operation, {"attempts": []})["attempts"].append(attempt)

    phase = {
        "schema_version": 2,
        "study": "study-long-audit-20260825-v2",
        "world": "task-3",
        "phase": "core",
        "world_goal": "Decide which personal Memories a healthcare agent should receive, exclude the rest, and transfer only the selected information.",
        "outcome": "Fail-closed at a genuine user decision gate: no external transfer was executed; useful categories remain local drafts because currentness, necessity, exact recipient/purpose/items/channel/retention, and explicit approval are unresolved.",
        "execution_identity": source["execution_identity"],
        "interleaving": "Five rounds; each round executed the complete ordered 21-operation core catalog before the next attempt for any operation.",
        "safety_boundary": {
            "external_share_or_export": "not invoked",
            "unsupported_factual_acceptance": "not performed",
            "mutations": "lane-local task-3 scratch/guardrail Contexts only",
            "clipboard": "not used",
            "tui": "not required for the observed defects; all evidence is independent non-TTY wrapper output",
            "store_reset": "none",
        },
        "coverage": {operation: len(value["attempts"]) for operation, value in operations.items()},
        "total_attempts": len(records),
        "operations": operations,
        "issue_registry": "agent-records/outputs/study-long-audit-20260825-v2/worlds/task-3/issues.json",
    }
    assert len(records) == 105
    assert set(operations) == {
        "contexts", "list", "show", "find", "search", "query", "summarize",
        "add", "copy", "reference", "embed", "edit", "move", "replace",
        "chunk", "compare", "find-duplicates", "find-redundancies",
        "find-ambiguities", "find-conflicts", "fit",
    }
    assert all(len(value["attempts"]) == 5 for value in operations.values())
    PHASE.write_text(json.dumps(phase, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    records_by_sequence = {record["sequence"]: record for record in records}
    reviewed_issues = []
    for source_issue in ISSUES:
        issue = dict(source_issue)
        issue["reproduction"] = REPRODUCTION[issue["id"]]
        issue["evidence"] = [
            {
                "sequence": sequence,
                "attempt": records_by_sequence[sequence]["attempt"],
                "operation": records_by_sequence[sequence]["operation"],
                "exit": records_by_sequence[sequence]["exit"],
                "raw_output": records_by_sequence[sequence]["raw_output"],
            }
            for sequence in issue["evidence_sequences"]
        ]
        reviewed_issues.append(issue)
    issue_registry = {
        "schema_version": 1,
        "world": "task-3",
        "phase": "core",
        "issues": reviewed_issues,
    }
    rendered_issue_registry = (
        json.dumps(issue_registry, indent=2, ensure_ascii=False) + "\n"
    )
    ISSUES_JSON.write_text(rendered_issue_registry, encoding="utf-8")
    ISSUES_CORE_JSON.write_text(rendered_issue_registry, encoding="utf-8")
    ISSUES_MD.write_text(markdown_issues(), encoding="utf-8")


if __name__ == "__main__":
    main()
