#!/usr/bin/env python3
"""Enrich task-2 CORE evidence with the actual method distinctions observed."""

from __future__ import annotations

import json
from pathlib import Path


PATH = Path(__file__).with_name("phase-core.json")

CATEGORIES = ("style", "budget", "methods", "ethics", "evaluation")

METHODS = {
    "contexts": [
        ("zero-operand Profile inventory at baseline", "entire Profile-readable namespace", "owned and granted Context names before task-2 mutation", "frozen Study catalog before local synthesis"),
        ("zero-operand Profile inventory after first synthesis cycle", "entire Profile-readable namespace", "catalog after advisor1/style live Embed and first local policy split", "cumulative graph after sequences 8-15"),
        ("zero-operand Profile inventory after duplicate cycle", "entire Profile-readable namespace", "catalog after advisor2/style Embed and exact duplicate introduction", "cumulative graph containing the first detected exact duplicate"),
        ("zero-operand Profile inventory after budget cycle", "entire Profile-readable namespace", "catalog after local description Embed and budget policy split", "cumulative graph after three source-balanced category cycles"),
        ("zero-operand final Profile inventory", "entire Profile-readable namespace", "final catalog after query-only Embed rejection and fifth synthesis cycle", "final cumulative graph with all local task-2 mutations retained"),
    ],
    "list": [
        ("explicit positional Context plus --direct", "local task-2/participant", "exact root inventory with descendant summary", "baseline participant Context before authored policy Memories"),
        ("explicit positional Context plus --direct", "local task-2 root", "exact root item ordering after style cycle", "copied, moved, and sentence-chunked style synthesis"),
        ("explicit positional Context plus --direct", "local task-2/description", "exact root including immutable snapshot References", "task description plus first two retained source snapshots"),
        ("explicit positional Context plus --recursive", "local task-2/participant", "descendants and embedded Context traversal", "participant graph after two granted and one local Embed attempt"),
        ("explicit positional Context plus --direct", "READ-granted task-2/advisor2/evaluation", "exact granted Memory frame with authority annotation", "frozen advisor2 evaluation fixture at final validation"),
    ],
    "show": [
        ("explicit --context with --direct", "local task-2/description", "one exact local Context", "unaltered task goal description before synthesis"),
        ("explicit --context with --direct", "READ-granted task-2/advisor1/style", "one exact granted Context", "advisor1 style fixture after local style policy was authored"),
        ("explicit --context with --direct", "READ-granted task-2/advisor2/budget", "one exact granted Context", "advisor2 budget fixture before budget reconciliation was authored"),
        ("explicit --context with --recursive", "local task-2/participant", "lexical descendants plus local/granted Embed traversal", "participant graph after advisor style and local description Embeds"),
        ("explicit --context with --direct", "local task-2 root", "final exact local synthesis items", "five cumulative policy cycles after copy/edit/move/replace/chunk"),
    ],
    "find": [
        ("case-sensitive literal Find with explicit --direct", "local task-2/description", "one exact local root", "task description phrase establishing equal authority"),
        ("case-sensitive literal Find with repeated --context", "advisor1/style plus advisor2/style grants", "two exact granted roots excluding Embeds", "cross-advisor style vocabulary probe for concise wording"),
        ("case-insensitive regex Find with repeated --context", "advisor1/budget plus advisor2/budget grants", "two exact granted roots matching budget or appendix", "cross-advisor budget-placement vocabulary"),
        ("case-sensitive literal Find with repeated --context", "advisor1/methods plus advisor2/methods grants", "two exact granted roots for participant wording", "cross-advisor recruitment policy evidence"),
        ("recursive literal Find with --all-results", "local task-2/participant", "descendants and followed Embeds", "final cumulative provenance references after five moves"),
    ],
    "search": [
        ("provider-backed Search with two explicit grant roots and limit 6", "advisor1/style plus advisor2/style", "exact multi-root semantic retrieval", "style commonality/difference question over frozen co-advisor evidence"),
        ("provider-backed Search with two explicit grant roots and limit 7", "advisor1/budget plus advisor2/budget", "exact multi-root semantic retrieval", "budget auditability/two-page placement question"),
        ("provider-backed Search with two explicit grant roots and limit 8", "advisor1/methods plus advisor2/methods", "exact multi-root semantic retrieval", "exact-count versus bounded-range recruitment question"),
        ("provider-backed Search with two explicit grant roots and limit 9", "advisor1/ethics plus advisor2/ethics", "exact multi-root search followed by visible RELATED fallback", "duplicate/conditional/conflict ethics question that produced no exact matches"),
        ("provider-backed Search with two explicit grant roots and limit 10", "advisor1/evaluation plus advisor2/evaluation", "exact multi-root semantic retrieval", "final evaluation consolidation question"),
    ],
    "query": [
        ("ordinary Query with repeated explicit --context", "advisor1/style plus advisor2/style", "two exact granted source frames", "neutral style synthesis requiring citations from both advisors"),
        ("ordinary Query with repeated explicit --context", "advisor1/budget plus advisor2/budget", "two exact granted source frames", "budget reconciliation after FIT-sensitive placement differences"),
        ("ordinary Query with repeated explicit --context", "advisor1/methods plus advisor2/methods", "two exact granted source frames", "conditional exact-target/range reconciliation"),
        ("ordinary Query with repeated explicit --context", "advisor1/ethics plus advisor2/ethics", "two exact granted source frames", "duplicate consolidation and true-conflict preservation question"),
        ("ordinary Query with repeated explicit --context", "advisor1/evaluation plus advisor2/evaluation", "two exact granted source frames", "final source-grounded evaluation policy request"),
    ],
    "summarize": [
        ("explicit granted Context positional plus --plain", "task-2/advisor1/style", "one exact granted frame", "advisor1 style fixture before pairwise comparison"),
        ("explicit granted Context positional plus --plain", "task-2/advisor2/style", "one exact granted frame", "advisor2 style fixture after its live Embed was persisted elsewhere"),
        ("explicit granted Context positional plus --plain", "task-2/advisor1/budget", "one exact granted frame", "advisor1 budget fixture before local layered synthesis"),
        ("explicit granted Context positional plus --plain", "task-2/advisor2/methods", "one exact granted frame", "advisor2 bounded-range methods fixture after recruitment synthesis"),
        ("local Context positional plus --recursive --plain", "task-2/participant", "recursive local graph containing granted live Embeds", "final cumulative participant graph; authority boundary intentionally exercised"),
    ],
    "add": [
        ("one INFO operand with explicit --context", "local task-2/participant", "single direct Memory append", "new equal-authority synthesis invariant authored from style review"),
        ("one INFO operand with explicit --context", "local task-2/participant", "single direct Memory append intentionally duplicating prior wording", "deliberate exact repeat of attempt 1 to exercise downstream duplicate discovery"),
        ("one INFO operand with explicit --context", "local task-2/participant", "single direct Memory append", "new layered budget reconciliation derived from both budget frames"),
        ("one INFO operand with explicit --context", "local task-2/participant", "single direct Memory append", "new conditional recruitment reconciliation derived from both methods frames"),
        ("one INFO operand with explicit --context", "local task-2/participant", "single direct Memory append", "new final neutral policy carrying provenance and unresolved-conflict ownership"),
    ],
    "copy": [
        ("qualified local Memory locator plus --into", "task-2/participant to task-2", "one equal-authority Memory copied with new UID", "Add attempt 1 UID 41debba1"),
        ("qualified local Memory locator plus --into", "task-2/participant to task-2", "one deliberate duplicate copied with new UID", "Add attempt 2 UID 2ba58f39 matching prior policy content"),
        ("qualified local Memory locator plus --into", "task-2/participant to task-2", "one budget policy copied with new UID", "Add attempt 3 UID b2e2dea7"),
        ("qualified local Memory locator plus --into", "task-2/participant to task-2", "one recruitment policy copied with new UID", "Add attempt 4 UID 93582936"),
        ("qualified local Memory locator plus --into", "task-2/participant to task-2", "one final neutral policy copied with new UID", "Add attempt 5 UID a42d04c0"),
    ],
    "reference": [
        ("qualified local Memory locator plus --into", "participant policy snapshot into description", "one immutable style-policy Reference", "pre-edit Add attempt 1 UID 41debba1"),
        ("qualified local Memory locator plus --into", "participant duplicate snapshot into description", "second immutable equal-policy Reference", "pre-edit deliberate duplicate UID 2ba58f39"),
        ("qualified local Memory locator plus --into", "participant budget snapshot into description", "one immutable budget-policy Reference", "pre-edit budget UID b2e2dea7"),
        ("qualified local Memory locator plus --into", "participant recruitment snapshot into description", "one immutable recruitment-policy Reference", "pre-edit recruitment UID 93582936"),
        ("qualified local Memory locator plus --into", "participant final-policy snapshot into description", "one immutable final-policy Reference", "pre-edit final policy UID a42d04c0"),
    ],
    "embed": [
        ("granted Context operand plus --into", "advisor1/style into local participant", "one authorized READ+EMBED live granted Context pointer", "advisor1 style grant selected after pairwise style synthesis"),
        ("granted Context operand plus --into", "advisor2/style into local task-2 root", "one authorized READ+EMBED live granted Context pointer", "advisor2 style grant selected as equal peer on a different local owner"),
        ("local Context operand plus --into", "task-2/description into local participant", "one local live Context pointer", "description with three retained snapshot References"),
        ("QUERY-only grant operand plus --into", "proposal-submission-guidelines into local participant", "authorization-negative Embed attempt; no durable mutation", "query-only guideline grant lacking EMBED authority"),
        ("granted Context operand plus --into", "advisor1/budget into local description", "one authorized READ+EMBED live granted Context pointer", "advisor1 budget grant attached beside five snapshot References"),
    ],
    "edit": [
        ("qualified direct Memory locator plus replacement body", "task-2/participant UID 41debba1", "one exact style-synthesis Memory", "Add attempt 1 followed by snapshot Reference and grant Embed"),
        ("qualified direct Memory locator plus replacement body", "task-2/participant UID 2ba58f39", "one exact deliberate-duplicate source Memory", "Add attempt 2 after a separate unchanged Copy preserved exact duplication"),
        ("qualified direct Memory locator plus replacement body", "task-2/participant UID b2e2dea7", "one exact budget Memory", "Add attempt 3 before Move and clause Chunk"),
        ("qualified direct Memory locator plus replacement body", "task-2/participant UID 93582936", "one exact recruitment Memory", "Add attempt 4 with explicit transition-condition clarification"),
        ("qualified direct Memory locator plus replacement body", "task-2/participant UID a42d04c0", "one exact final-policy Memory", "Add attempt 5 with equal-authority tie-break clarification"),
    ],
    "move": [
        ("qualified local Memory locator plus --into", "task-2/participant to task-2", "move edited style policy while retargeting links", "edited UID 41debba1 with one existing snapshot Reference"),
        ("qualified local Memory locator plus --into", "task-2/participant to task-2", "move edited duplicate-policy variant while retargeting links", "edited UID 2ba58f39 after unchanged duplicate Copy remained"),
        ("qualified local Memory locator plus --into", "task-2/participant to task-2", "move edited budget policy while retargeting links", "edited UID b2e2dea7 with budget snapshot retained"),
        ("qualified local Memory locator plus --into", "task-2/participant to task-2", "move edited recruitment policy while retargeting links", "edited UID 93582936 after failed QUERY-only Embed"),
        ("qualified local Memory locator plus --into", "task-2/participant to task-2", "move edited final neutral policy while retargeting links", "edited UID a42d04c0 at final cumulative stage"),
    ],
    "replace": [
        ("literal old/new text plus --direct --plain", "local task-2 root", "exact no-match replacement probe", "absent token nonexistent-policy-token over three direct Memories"),
        ("different literal old/new text plus --direct --plain", "local task-2 root", "exact no-match duplicate-cycle probe", "absent token nonexistent-duplicate-token over eight direct items"),
        ("literal old/new text plus --direct --plain", "local task-2 root", "successful two-Memory budget terminology rewrite", "main text wording in copied and moved budget policies"),
        ("literal old/new text plus --direct --plain", "local task-2 root", "successful two-Memory recruitment terminology rewrite", "participant target wording in copied and moved recruitment policies"),
        ("literal old/new text plus --direct --plain", "local task-2 root", "successful five-Memory conflict-ownership rewrite", "unresolved conflicts wording across accumulated exact copies and fragments"),
    ],
    "chunk": [
        ("qualified Memory locator with sentence method and max 100", "moved style UID 41debba1 in task-2", "one long sentence split into two stored Memories", "edited attempt-1 style synthesis after Move"),
        ("qualified Memory locator with clause method and max 105", "moved duplicate-policy UID 2ba58f39 in task-2", "one compound policy split into three stored Memories", "edited attempt-2 duplicate variant after Move"),
        ("qualified Memory locator with clause method and max 110", "moved budget UID b2e2dea7 in task-2", "one compound budget policy split into three stored Memories", "edited and terminology-normalized budget reconciliation"),
        ("qualified Memory locator with clause method and max 115", "moved recruitment UID 93582936 in task-2", "one conditional recruitment policy split into three stored Memories", "edited and terminology-normalized recruitment reconciliation"),
        ("qualified Memory locator with clause method and max 120", "moved final-policy UID a42d04c0 in task-2", "one final neutral policy split into three stored Memories", "edited final synthesis after conflict-ownership replacement"),
    ],
    "compare": [
        ("two explicit Context operands plus --snapshot", "advisor1/style versus advisor2/style", "exact pairwise granted comparison", "frozen style frames after first local synthesis"),
        ("two explicit Context operands plus --snapshot", "advisor1/budget versus advisor2/budget", "exact pairwise granted comparison", "frozen budget frames before local budget synthesis"),
        ("two explicit Context operands plus --snapshot", "advisor1/methods versus advisor2/methods", "exact pairwise granted comparison", "frozen methods frames exposing exact/range difference"),
        ("two explicit Context operands plus --snapshot", "advisor1/ethics versus advisor2/ethics", "exact pairwise granted comparison", "frozen ethics frames after semantic Search fallback"),
        ("two explicit Context operands plus --snapshot", "advisor1/evaluation versus advisor2/evaluation", "exact pairwise granted comparison", "frozen final evaluation frames"),
    ],
    "find-duplicates": [
        ("explicit Context positional plus --direct", "local task-2 root at 3 items", "exact duplicate scan before deliberate repeat", "sentence-chunked first policy and its unchanged Copy"),
        ("explicit Context positional plus --direct", "local task-2 root at 8 items", "exact duplicate scan after deliberate repeat", "two unchanged equal-authority Copies plus clause fragments"),
        ("explicit Context positional plus --direct", "local task-2 root at 12 items", "exact duplicate scan after budget synthesis", "retained exact group plus budget copy/fragments"),
        ("explicit Context positional plus --direct", "local task-2 root at 16 items", "exact duplicate scan after recruitment synthesis", "retained exact group plus recruitment copy/fragments"),
        ("explicit Context positional plus --direct", "local task-2 root at 20 items", "final exact duplicate scan after ownership rewrite", "final cumulative corpus with the exact group transformed consistently"),
    ],
    "find-redundancies": [
        ("explicit Context positional plus --direct semantic DUN scan", "local task-2 root at 3 direct Memories", "complete redundancy frame before deliberate duplicate", "first copied policy plus sentence fragments"),
        ("explicit Context positional plus --direct semantic DUN scan", "local task-2 root at 7 direct Memories", "complete frame containing one exact redundancy", "deliberate second policy Copy and clause fragments"),
        ("explicit Context positional plus --direct semantic DUN scan", "local task-2 root at 11 direct Memories", "complete frame after budget addition", "retained exact group plus budget evidence"),
        ("explicit Context positional plus --direct semantic DUN scan", "local task-2 root at 15 direct Memories", "complete frame after recruitment addition", "retained exact group plus conditional recruitment evidence"),
        ("explicit Context positional plus --direct semantic DUN scan", "local task-2 root at 19 direct Memories", "final complete redundancy frame", "ownership-normalized exact group plus final fragments"),
    ],
    "find-ambiguities": [
        ("explicit Context positional ambiguity analysis", "local task-2 root at 3 direct Memories", "whole direct semantic frame", "first sentence split baseline"),
        ("explicit Context positional ambiguity analysis", "local task-2 root at 7 direct Memories", "whole direct semantic frame", "two policy cycles including clause fragments"),
        ("explicit Context positional ambiguity analysis", "local task-2 root at 11 direct Memories", "whole direct semantic frame", "three cycles including budget fragments"),
        ("explicit Context positional ambiguity analysis", "local task-2 root at 15 direct Memories", "whole direct semantic frame", "four cycles including recruitment fragments"),
        ("explicit Context positional ambiguity analysis", "local task-2 root at 19 direct Memories", "final whole direct semantic frame", "five cycles; eleven dependent Chunk fragments flagged"),
    ],
    "find-conflicts": [
        ("explicit Context positional exhaustive conflict scan", "local task-2 root at 3 Memories", "3 complete pairs", "first sentence-split synthesis frame"),
        ("explicit Context positional exhaustive conflict scan", "local task-2 root at 7 Memories", "21 complete pairs", "duplicate-cycle synthesis frame"),
        ("explicit Context positional exhaustive conflict scan", "local task-2 root at 11 Memories", "55 complete pairs", "budget-cycle synthesis frame"),
        ("explicit Context positional exhaustive conflict scan", "local task-2 root at 15 Memories", "105 complete pairs", "recruitment-cycle synthesis frame"),
        ("explicit Context positional exhaustive conflict scan", "local task-2 root at 19 Memories", "171 complete pairs", "final cumulative synthesis frame"),
    ],
    "fit": [
        ("repeatable explicit --context proposition sources", "advisor1/style plus advisor2/style", "joint satisfiability of two exact granted frames", "style policies with sentence-length conditions"),
        ("repeatable explicit --context proposition sources", "advisor1/budget plus advisor2/budget", "joint satisfiability of two exact granted frames", "budget-detail placement policies"),
        ("repeatable explicit --context proposition sources", "advisor1/methods plus advisor2/methods", "joint satisfiability of two exact granted frames", "exact-count versus bounded-range recruitment policies"),
        ("repeatable explicit --context proposition sources", "advisor1/ethics plus advisor2/ethics", "joint satisfiability of two exact granted frames", "prototype and field-study ethics policies"),
        ("repeatable explicit --context proposition sources", "advisor1/evaluation plus advisor2/evaluation", "joint satisfiability of two exact granted frames", "design-comparison and deployment-evaluation policies"),
    ],
}


ISSUES = [
    {
        "id": "T2V2-CONTEXTS-01",
        "title": "Whole-Profile Context inventory obscures the active world",
        "expected": "A task-2 user can narrow Context discovery to the task-2 owned and granted subtree while retaining access annotations.",
        "actual": "All five zero-operand invocations printed 112 non-empty lines spanning every Study world; the task-2 slice had to be found manually each time.",
        "workaround": "Search captured output for the task-2 prefix, then use explicit Context operands on later commands.",
        "severity": "medium",
        "classification": "usability/information-overload",
        "evidence_ids": ["core:contexts:1", "core:contexts:2", "core:contexts:3", "core:contexts:4", "core:contexts:5"],
    },
    {
        "id": "T2V2-RECURSIVE-VOLUME-01",
        "title": "Recursive reads bury the synthesis target in hundreds of rows",
        "expected": "A recursive view makes source balance and the next useful synthesis action visible without requiring a full-corpus reread.",
        "actual": "Recursive List produced 696 non-empty lines and recursive Show produced 527, traversing 37 Contexts and 301 Memories after live Embeds.",
        "workaround": "Use exact category reads, pairwise Compare, and targeted Find/Search after one completeness check.",
        "severity": "medium",
        "classification": "usability/information-overload",
        "evidence_ids": ["core:list:4", "core:show:4"],
    },
    {
        "id": "T2V2-CHUNK-UIDS-01",
        "title": "Chunk receipts omit the UIDs of created Memories",
        "expected": "A mutating receipt identifies every created Memory so downstream edit, move, reference, and review operations can consume the result directly.",
        "actual": "All five receipts reported only the count of added Memories and clipped previews; none mapped the removed UID to the new UIDs.",
        "workaround": "Run a scoped List/Show/Find and recover each created UID by content and order.",
        "severity": "medium",
        "classification": "workflow/provenance-handoff",
        "evidence_ids": ["core:chunk:1", "core:chunk:2", "core:chunk:3", "core:chunk:4", "core:chunk:5"],
    },
    {
        "id": "T2V2-CHUNK-SEMANTICS-01",
        "title": "Sentence/clause chunking creates dependent policy fragments",
        "expected": "Stored chunks remain independently actionable policy Memories or retain a typed relationship that downstream quality checks understand.",
        "actual": "Five compound policies became dependent headings, conditions, and continuations; ambiguity stayed 0 through 15 items, then the final check flagged 11 of 19 direct Memories, primarily Chunk-created fragments.",
        "workaround": "Keep conditional policies whole or immediately reconstruct every dependent fragment; UID omission makes that recovery manual.",
        "severity": "high",
        "classification": "semantic-safety/workflow",
        "evidence_ids": ["core:chunk:1", "core:chunk:2", "core:chunk:3", "core:chunk:4", "core:chunk:5", "core:find-ambiguities:5"],
    },
    {
        "id": "T2V2-SEARCH-DRIFT-01",
        "title": "Search fallback broadens an ethics classification question",
        "expected": "When exact semantic retrieval is empty, preserve the requested duplicate/conditional/conflict classification or clearly stop before substituting a different task.",
        "actual": "Attempt 4 visibly changed the query to 'ethics policies for user studies' and returned RELATED items; the label was honest, but the results did not answer the requested classification.",
        "workaround": "Treat RELATED as a suggestion only and use exact Show/Compare/Query on the two ethics categories.",
        "severity": "medium",
        "classification": "semantic-retrieval/usability",
        "evidence_ids": ["core:search:4", "core:compare:4", "core:query:4"],
    },
]


def main() -> None:
    document = json.loads(PATH.read_text())
    for operation, variants in METHODS.items():
        attempts = document["operations"][operation]["attempts"]
        assert len(attempts) == len(variants) == 5
        for attempt, fields in zip(attempts, variants, strict=True):
            attempt["entry_route"], attempt["target_route"], attempt["scope"], attempt["input_provenance"] = fields

    issue_attempts = {
        "T2V2-CONTEXTS-01": [("contexts", n) for n in range(1, 6)],
        "T2V2-RECURSIVE-VOLUME-01": [("list", 4), ("show", 4)],
        "T2V2-CHUNK-UIDS-01": [("chunk", n) for n in range(1, 6)],
        "T2V2-CHUNK-SEMANTICS-01": [("chunk", n) for n in range(1, 6)] + [("find-ambiguities", 5)],
        "T2V2-SEARCH-DRIFT-01": [("search", 4)],
    }
    for issue_id, refs in issue_attempts.items():
        for operation, number in refs:
            defects = document["operations"][operation]["attempts"][number - 1]["defect_ids"]
            if issue_id not in defects:
                defects.append(issue_id)
    document["issues"] = ISSUES
    document["coverage"] = {operation: 5 for operation in METHODS}
    document["execution_summary"] = {
        "counted_actual_mem_commands": 105,
        "successful_exits": 103,
        "expected_authority_rejections": 1,
        "safe_authority_boundary_failures": 1,
        "provider_infrastructure_failures": 0,
        "store_resets": 0,
    }
    PATH.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
