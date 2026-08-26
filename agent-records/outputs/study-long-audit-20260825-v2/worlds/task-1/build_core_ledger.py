#!/usr/bin/env python3
"""Build the task-1 core ledger from the immutable per-attempt captures."""

from __future__ import annotations

import json
import math
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw" / "core"
OPS = (
    "contexts", "list", "show", "find", "search", "query", "summarize",
    "add", "edit", "replace", "copy", "reference", "embed", "move",
    "chunk", "compare", "find-duplicates", "find-redundancies",
    "find-ambiguities", "find-conflicts", "fit",
)


ROUTES = {
    "contexts": [
        ("bare canonical command", "profile readable-Context catalog at entry", "all local and public names", "fixed initial lane snapshot", "discover task-1 sources and public targets"),
        ("bare canonical command", "profile catalog after facility publication", "all local and public names", "facility contribution receipt", "confirm the writable public namespace remained attached"),
        ("bare canonical command", "profile catalog after event publication", "all local and public names", "event contribution receipt", "re-locate access and source roots in accumulated state"),
        ("bare canonical command", "profile catalog after access publication", "all local and public names", "access contribution receipt", "verify public parking target remained visible"),
        ("bare canonical command", "final accumulated profile catalog", "all local and public names", "four published areas plus local evidence graph", "confirm no Context escaped the fixed lane"),
    ],
    "list": [
        ("canonical positional Context + --direct", "ordinary local facility source", "one direct Context", "fixed verified construction Memories", "select facility facts and UIDs"),
        ("cataloged ls alias + positional Context + --direct", "granted event wiki Context", "one direct public Context", "Contexts discovery", "inspect stale event guidance"),
        ("canonical positional Context + --recursive", "ordinary local participant root", "lexical descendants plus embeds", "facility/event evidence links and chunks", "audit accumulated working topology"),
        ("canonical positional Context + --direct", "granted parking wiki Context", "one direct public Context", "parking target selected from catalog", "inspect stale parking guidance"),
        ("canonical positional Context + --recursive", "granted campus-wiki root", "six readable public descendants", "all area contributions before shop/route finish", "verify whole public wiki composition"),
    ],
    "show": [
        ("qualified CONTEXT:UID positional", "ordinary local facility date Memory", "one exact Memory", "List M1 UID", "verify date provenance"),
        ("qualified public CONTEXT:UID positional", "granted event reservation Memory", "one exact public Memory", "public List M2 UID", "read the stale event baseline"),
        ("public Context positional", "granted building-access Context", "whole direct Context", "Contexts catalog", "inspect the full access baseline"),
        ("bare UID positional", "globally resolved ordinary local parking Memory", "one exact local Memory", "known verified fixture UID", "verify global direct-item resolution"),
        ("qualified public CONTEXT:UID positional", "granted route Memory before rewrite", "one exact public Memory", "final route baseline UID", "freeze pre-edit route evidence"),
    ],
    "find": [
        ("literal pattern + explicit Context + --context-only", "ordinary local facility source", "exact root, no descendants", "verified facility text", "locate visitor-service facts"),
        ("regex + ignore-case + explicit Context", "ordinary local event source", "exact root, regex matching", "verified event text", "collect reservation and auditorium evidence"),
        ("literal pattern + repeated --context", "local and granted access peers", "two exact roots, embeds excluded", "source and baseline pairing", "contrast rear-entrance statements"),
        ("ignore-case literal + --direct", "ordinary local parking source", "one exact root", "verified parking text", "locate Lot C evidence"),
        ("literal pattern + four repeated public Contexts + --all-results", "four contributed public areas", "multiple exact roots", "published update label", "verify prior contributions are discoverable"),
    ],
    "search": [
        ("semantic query + explicit Context + --context-only", "ordinary local facility source", "one exact root, limit 5", "verified facility frame", "rank public-impact evidence"),
        ("semantic query + two --context + --limit 8", "local and public event peers", "two exact roots", "event source plus stale wiki", "retrieve closure and relocation evidence"),
        ("semantic query + descendant-only traversal", "ordinary local construction root", "lexical descendants, embeds excluded, limit 10", "all verified construction areas", "retrieve cross-area access facts"),
        ("semantic query + --direct + --limit 3", "granted parking wiki Context", "one exact public root", "stale parking baseline", "rank ordinary access claims to replace"),
        ("semantic query + descendant traversal + --limit 20", "granted campus-wiki root", "all readable public descendants, embeds excluded", "four contributions plus stale baseline", "find remaining stale public guidance"),
    ],
    "query": [
        ("query-only Context positional + question", "opaque construction-details root", "authorized QUERY interface only", "query-only Grant", "confirm publishable date boundary"),
        ("ordinary question + two --context", "local and public event peers", "two roots, no descendants or embeds", "Search M2 candidates", "draft event update from both evidence sets"),
        ("ordinary question + public --context + --direct", "granted building-access Context", "one exact public root", "pre-update baseline", "document guidance before contribution"),
        ("query-only child positional + question", "opaque material-control child", "authorized QUERY child only", "query-policy and material-control data", "exclude internal access/material detail from public text"),
        ("ordinary question + public parent + descendants", "granted campus-wiki tree", "all readable public descendants, embeds excluded", "four published areas and stale baseline", "assess published coverage and remaining stale facts"),
    ],
    "summarize": [
        ("positional local Context + --direct", "ordinary local facility source", "one direct frame", "verified facility Memories", "form a facility contribution"),
        ("positional public Context + --direct", "granted event wiki Context", "one direct public frame", "event baseline", "understand existing event policy"),
        ("positional local parent + --recursive", "ordinary construction source tree", "six descendant frames", "all verified area sources", "check cross-area coverage"),
        ("positional local Context + --direct", "ordinary local parking source", "one direct frame", "verified parking Memories", "form a parking contribution"),
        ("positional public parent + --recursive", "granted campus-wiki tree", "six readable public descendants", "late accumulated public state", "produce whole-wiki verification summary"),
    ],
    "add": [
        ("single INFO + --to", "CREATE-granted facility wiki Context", "one new public Memory", "facility source plus query-only disclosure check", "publish consolidated facility update"),
        ("single INFO + --to", "CREATE-granted event wiki Context", "one new public Memory", "event Query M2", "publish consolidated event update"),
        ("single INFO + --to", "CREATE-granted building-access Context", "one new public Memory", "recursive source summary and access retrieval", "publish consolidated access update"),
        ("single INFO + --to", "CREATE-granted temporary-parking Context", "one new public Memory", "parking source plus material-control boundary", "publish consolidated parking update"),
        ("single INFO + --to", "CREATE-granted shop-updates Context", "one new public Memory", "verified shop source and whole-wiki gap check", "publish consolidated shop update"),
    ],
    "edit": [
        ("qualified public CONTEXT:UID + content", "new granted facility Memory", "one exact public Memory", "Add M1 receipt", "tighten public facility wording"),
        ("bare UID + --context + content", "new granted event Memory", "one exact public Memory", "Add M2 receipt", "tighten public event wording"),
        ("qualified public CONTEXT:UID + content", "new granted access Memory", "one exact public Memory", "Add M3 receipt", "separate student and staff rules"),
        ("qualified public CONTEXT:UID + content", "new granted parking Memory", "one exact public Memory", "Add M4 receipt and query-only exclusion", "tighten controlled-access wording"),
        ("qualified public CONTEXT:UID + content", "existing granted route baseline Memory", "one exact public Memory rewritten", "Show M5 pre-edit evidence and verified route source", "replace stale route claim with time-bounded detour guidance"),
    ],
    "replace": [
        ("literal pair + public --context", "granted facility Context", "one public root boundary", "Edit M1 text", "test whether bulk Replace follows visible edit authority"),
        ("literal pair + local --context", "ordinary participant scratch root", "one local root", "Copy M2 event evidence", "label copied event evidence"),
        ("literal pair + local --context", "ordinary participant scratch root", "one local root with two matches", "Copy M3 batch", "label copied access evidence atomically"),
        ("literal pair + local --context", "ordinary participant scratch root", "one local root", "granted Copy M4 result", "mark retained stale parking evidence"),
        ("literal pair + local --context", "ordinary participant scratch root", "one local root", "Copy M5 shop evidence", "label copied shop evidence"),
    ],
    "copy": [
        ("bare UID + --from + --into", "local facility source to participant scratch", "one exact Memory", "verified facility UID", "retain editable facility evidence"),
        ("qualified CONTEXT:UID + --into", "local event source to participant scratch", "one exact Memory", "verified event UID", "retain event evidence for labeling"),
        ("two positional UIDs + --from + --into", "local access source to participant scratch", "ordered two-Memory batch", "two verified access UIDs", "exercise batch evidence retention"),
        ("qualified granted CONTEXT:UID + --into", "public parking source to participant scratch", "one EXPORT-authorized public Memory", "stale public parking UID", "retain stale baseline without ownership transfer"),
        ("repeatable --memory + --into", "local shop and route sources to participant scratch", "ordered two-source batch", "verified shop and route UIDs", "prepare late evidence and placement tests"),
    ],
    "reference": [
        ("bare UID + --from + --into", "local facility Memory to participant", "one live Memory reference", "facility date UID", "preserve date provenance"),
        ("Context positional + --direct + --into", "local event Context to participant", "direct Context snapshot", "event source selected after Query", "retain event source snapshot"),
        ("public Context positional + --recursive + --into", "granted access Context to participant", "recursive granted Context snapshot attempt", "public access target", "test whole granted-Context reference route"),
        ("public UID + --from + --into", "granted parking Memory to participant", "one public Memory reference", "public parking baseline UID", "retain ownership-linked stale evidence"),
        ("--from Context + --direct + --into", "local route Context to participant", "direct Context snapshot", "verified route source", "retain final route source snapshot"),
    ],
    "embed": [
        ("local Context positional + --into", "local facility Context into participant", "one live Context embed", "facility source", "make facility evidence traversable"),
        ("qualified public CONTEXT:UID + --into", "granted event Memory into participant", "one public Memory embed", "stale event baseline UID", "retain live event baseline ownership"),
        ("local Context positional + --into", "local access Context into participant", "one live Context embed", "access source", "make access evidence traversable"),
        ("public Context positional + --into", "granted parking Context into participant", "one live granted Context embed", "public parking target", "test whole public embed route"),
        ("--from public Context + --into", "granted route Context into participant", "one live granted Context embed", "edited route target", "retain final public route view"),
    ],
    "move": [
        ("bare UID + --from + --into", "participant copy to local facility source", "one local Memory, default retarget", "Copy M1 UID", "classify facility evidence under its area"),
        ("qualified source UID + --into + --retarget-links", "participant event copy to local event source", "one local Memory, explicit retarget", "Copy/Replace M2 UID", "classify labeled event evidence"),
        ("two UIDs + --from + --to + --break-links", "participant batch to local access source", "two local Memories, explicit break policy", "Copy/Replace M3 batch", "classify access evidence and test batch policy"),
        ("public UID + --from + --into", "granted parking source to local participant", "one cross-owner boundary attempt", "public baseline after successful Copy", "verify EXPORT does not imply destructive ownership transfer"),
        ("UID + --from + --into + --after", "participant route copy to local route source", "one local Memory at exact placement", "Copy M5 route UID and prior route UID", "verify ordered late placement"),
    ],
    "chunk": [
        ("qualified UID + clauses + custom break/max", "moved local facility copy", "one Memory to two bounded chunks", "Move M1 output UID", "split operation wrapper from facility claim"),
        ("bare UID + --context + clauses/max", "moved local event copy", "one Memory to bounded clause chunks", "Move M2 output UID", "test context-qualified chunking"),
        ("qualified UID + clauses + min/max", "moved local access copy", "one Memory with lower and upper bounds", "Move M3 batch first UID", "test bounded atomic access evidence"),
        ("qualified UID + invalid min/max", "ordinary local parking source", "validation boundary before mutation", "verified parking UID", "confirm contradictory bounds fail safely"),
        ("bare UID + --context + clauses/max", "participant shop copy", "one late scratch Memory", "Copy/Replace M5 shop UID", "recover with a valid bounded split"),
    ],
    "compare": [
        ("two auto-typed public Memory positionals + --snapshot", "two Memories in one granted facility Context", "two exact Memory endpoints", "Add/Edit M1 UID plus stale public UID", "test within-Context Memory comparison"),
        ("two Context positionals + --snapshot", "local and public event peers", "two direct Context frames", "published event update", "compare verified changes with baseline"),
        ("--from/--to + asymmetric descendant flags + --snapshot", "local construction tree and public wiki tree", "both recursive descendant sets", "three contributed areas plus full sources", "assess cross-area alignment"),
        ("two auto-typed Memory positionals + --snapshot", "local and public parking peers", "one exact Memory per distinct Context", "verified closure and stale access Memory", "compare direct contradiction"),
        ("--from/--to + --direct + --ledger + --snapshot", "local and public shop peers", "complete direct relation ledger", "published shop update and stale baseline", "obtain exhaustive reconciliation evidence"),
    ],
    "find-duplicates": [
        ("positional local Context + --direct", "local facility source", "one direct frame", "post-chunk facility evidence", "detect exact chunks or copies"),
        ("--context compatibility route + --direct", "local event source", "one direct frame", "post-chunk event evidence", "detect exact event duplicates"),
        ("positional local parent + --recursive", "local construction source tree", "each descendant as an independent frame", "facility/event/access chunks", "audit duplicate propagation across areas"),
        ("positional public Context + --direct", "granted parking wiki Context", "one direct public frame", "parking contribution", "detect exact public duplicates"),
        ("positional participant root + --direct", "ordinary participant scratch root", "mixed direct item frame", "all Copy/Reference/Embed outputs", "verify direct-item duplicate accounting"),
    ],
    "find-redundancies": [
        ("positional local Context + --direct", "local facility source", "one semantic frame", "post-chunk facility evidence", "find redundant facility claims"),
        ("positional public Context default direct", "granted event wiki Context", "one semantic public frame", "event contribution and baseline", "find redundant event guidance"),
        ("positional local Context + --evidence-json", "local access source", "one semantic frame plus machine evidence", "post-chunk access evidence", "inspect canonical redundancy evidence"),
        ("--context compatibility route + --direct", "local parking source", "one semantic frame", "verified parking corpus", "find redundant parking guidance"),
        ("positional public Context + --evidence-json", "granted shop wiki Context", "one semantic public frame plus JSON", "shop contribution and baseline", "inspect late public redundancy evidence"),
    ],
    "find-ambiguities": [
        ("positional local Context + unsupported --direct", "local facility source", "CLI option boundary", "parity assumption from duplicate finders", "test explicit direct-scope discoverability"),
        ("positional local Context", "local event source", "one direct semantic frame", "post-chunk event evidence", "inspect ambiguities created by chunking"),
        ("positional local Context", "local access source", "one direct semantic frame", "post-chunk access evidence", "inspect access-language ambiguity"),
        ("positional local Context", "local parking source", "one direct semantic frame", "verified parking corpus", "inspect operational ambiguity"),
        ("positional public Context", "granted shop wiki Context", "one direct semantic public frame", "published shop update", "inspect remaining public ambiguity"),
    ],
    "find-conflicts": [
        ("positional public Context + unsupported --direct", "granted facility wiki Context", "CLI option boundary", "parity assumption from duplicate finders", "test explicit direct-scope discoverability"),
        ("positional public Context", "granted event wiki Context", "all direct Memory pairs", "published event update", "identify stale event claims"),
        ("positional public Context", "granted building-access Context", "all direct Memory pairs", "published access update", "identify stale access claims"),
        ("positional public Context", "granted parking wiki Context", "all direct Memory pairs", "published parking update", "identify stale parking claims"),
        ("positional public Context", "granted route wiki Context", "all direct Memory pairs", "rewritten route baseline", "verify residual route conflicts"),
    ],
    "fit": [
        ("two proposition positionals + --background", "process-local proposition frame", "two propositions plus one background", "facility contribution facts", "check portal guidance compatibility"),
        ("two --context", "local and public event peers", "two complete direct Context frames", "published event update", "check event-frame coexistence"),
        ("two --memory + --background", "local and public access Memories", "two exact Memories plus background", "verified closure and stale baseline", "test direct access incompatibility"),
        ("two --memory + --background", "local and public parking Memories", "two exact Memories plus background", "verified closure and stale baseline", "test direct parking incompatibility"),
        ("three --context", "local route plus public route and shop", "three complete direct frames", "late published route/shop state", "check cross-area temporal compatibility"),
    ],
}


ISSUES = [
    {
        "id": "T1-V2-CONTEXTS-GLOBAL-OVERLOAD",
        "title": "World-focused discovery prints every world and Grant",
        "expected": "A focused workflow should be able to narrow Context discovery to task-1 or the current subtree while preserving Grant annotations.",
        "actual": "Every bare Contexts call printed 105 catalog rows (125 raw lines), including unrelated task-2 and task-3 namespaces; no filter was available.",
        "workaround": "Use literal Find/List with an exact task-1 root after manually locating it in the global catalog.",
        "severity": "medium",
        "classification": "usability/information-overload",
        "evidence_ids": ["task-1/core/seq-001", "task-1/core/seq-022", "task-1/core/seq-043", "task-1/core/seq-064", "task-1/core/seq-085"],
    },
    {
        "id": "T1-V2-RECURSIVE-LIST-OVERLOAD",
        "title": "Recursive List becomes an unbounded terminal dump",
        "expected": "A recursive inspection should remain navigable or provide a bounded/summary handoff while retaining exact data access.",
        "actual": "The accumulated participant List occupied 904 raw lines and the public wiki List occupied 580 raw lines in plain output.",
        "workaround": "List one exact child at a time or use literal/semantic retrieval before List.",
        "severity": "medium",
        "classification": "usability/information-overload",
        "evidence_ids": ["task-1/core/seq-044", "task-1/core/seq-086"],
    },
    {
        "id": "T1-V2-COMPARE-SAME-CONTEXT-MEMORIES",
        "title": "Compare auto-types Memory endpoints but rejects peers in one Context",
        "expected": "Two explicit CONTEXT:UID endpoints should compare the selected Memories even when their owner Context is the same.",
        "actual": "The command rejected two distinct facility Memory UIDs with 'Compare requires two distinct Contexts.'",
        "workaround": "Compare Memories owned by distinct Contexts or compare their whole peer Contexts.",
        "severity": "medium",
        "classification": "functional/operand-contract",
        "evidence_ids": ["task-1/core/seq-016", "task-1/core/seq-079"],
    },
    {
        "id": "T1-V2-QUALITY-SCOPE-ASYMMETRY",
        "title": "Quality finders expose incompatible scope grammars",
        "expected": "Find Ambiguities and Find Conflicts should share the direct/recursive scope vocabulary already used by Find Duplicates and Find Redundancies, or clearly present an equivalent noninteractive range control.",
        "actual": "Both commands rejected --direct at parser level and suggested --select; positional exact Context worked on later attempts.",
        "workaround": "Use a positional exact Context for direct analysis, --all for Profile breadth, or --select only in a TTY.",
        "severity": "low",
        "classification": "usability/command-consistency",
        "evidence_ids": ["task-1/core/seq-019", "task-1/core/seq-020", "task-1/core/seq-040", "task-1/core/seq-041"],
    },
    {
        "id": "T1-V2-REFERENCE-GRANTED-CONTEXT-RESOLUTION",
        "title": "Reference cannot snapshot a readable granted Context",
        "expected": "Reference's Source Context route should resolve a readable granted public Context, as its exact granted-Memory route and Embed's whole granted-Context route do.",
        "actual": "Reference reported task-1/campus-wiki/building-access does not exist, although Contexts/List/Show resolved it and later granted Memory Reference and whole-Context Embed succeeded.",
        "workaround": "Reference an exact public Memory or Embed the public Context; use Copy when an owned snapshot is required.",
        "severity": "high",
        "classification": "functional/grant-resolution",
        "evidence_ids": ["task-1/core/seq-054", "task-1/core/seq-075", "task-1/core/seq-076", "task-1/core/seq-097"],
    },
    {
        "id": "T1-V2-CHUNK-FRAGMENTED-ATOMS",
        "title": "Hard-bounded Chunk emits semantically incomplete fragments",
        "expected": "Clause chunking should preserve independently intelligible atomic Memories or visibly warn that a hard character cap forced dependent fragments.",
        "actual": "A valid clause/max-char split produced '...during the' and 'construction period.' as separate Memories; Find Ambiguities immediately flagged both as mutually dependent underspecified fragments.",
        "workaround": "Use a larger max_chars value and immediately run Find Ambiguities before consuming chunks.",
        "severity": "high",
        "classification": "semantic-integrity/chunking",
        "evidence_ids": ["task-1/core/seq-036", "task-1/core/seq-040", "task-1/core/seq-057", "task-1/core/seq-061"],
    },
    {
        "id": "T1-V2-COMPARE-LEDGER-INVALID-REPAIR",
        "title": "Compare ledger waits 109 seconds then loses the analysis",
        "expected": "A ledger comparison should return a valid exhaustive relation ledger or fail promptly without consuming a long provider-repair cycle.",
        "actual": "After 109.62 seconds, Compare failed because provider repair assigned DISTINCT to invalid PEER sides; no usable ledger was published.",
        "workaround": "Use snapshot Compare for a summary and separate Find/Fit reports for relation evidence.",
        "severity": "high",
        "classification": "provider-schema-infrastructure/reliability",
        "evidence_ids": ["task-1/core/seq-100", "task-1/core/seq-058", "task-1/core/seq-105"],
    },
    {
        "id": "T1-V2-FIT-TEMPORAL-OVERRIDE",
        "title": "Fit treats a time-bounded exception as incompatible with usual hours",
        "expected": "A June 24–August 23 construction-specific 7 a.m.–11 p.m. schedule can coexist with a store's usual recess 9 a.m.–6 p.m. schedule as an explicit temporary override.",
        "actual": "Fit returned NO and treated the ordinary 'usual recess hours' statement as an unconditional conflict with the dated construction update.",
        "workaround": "State override precedence explicitly in the background or preserve the normal and temporary schedules in separate time-scoped Contexts.",
        "severity": "medium",
        "classification": "semantic/temporal-reasoning",
        "evidence_ids": ["task-1/core/seq-105"],
    },
]


DEFECTS_BY_SEQUENCE = {
    **{seq: ["T1-V2-CONTEXTS-GLOBAL-OVERLOAD"] for seq in (1, 22, 43, 64, 85)},
    44: ["T1-V2-RECURSIVE-LIST-OVERLOAD"],
    86: ["T1-V2-RECURSIVE-LIST-OVERLOAD"],
    16: ["T1-V2-COMPARE-SAME-CONTEXT-MEMORIES"],
    19: ["T1-V2-QUALITY-SCOPE-ASYMMETRY"],
    20: ["T1-V2-QUALITY-SCOPE-ASYMMETRY"],
    36: ["T1-V2-CHUNK-FRAGMENTED-ATOMS"],
    40: ["T1-V2-CHUNK-FRAGMENTED-ATOMS"],
    54: ["T1-V2-REFERENCE-GRANTED-CONTEXT-RESOLUTION"],
    57: ["T1-V2-CHUNK-FRAGMENTED-ATOMS"],
    61: ["T1-V2-CHUNK-FRAGMENTED-ATOMS"],
    100: ["T1-V2-COMPARE-LEDGER-INVALID-REPAIR"],
    105: ["T1-V2-FIT-TEMPORAL-OVERRIDE"],
}


RECOVERY = {
    10: "Expected ordinary-local boundary; the exact public Memory remained editable through Edit sequence 9, and later Replace attempts used owned participant copies.",
    16: "No state was reset; distinct-Context Compare sequence 37 and exact cross-Context Memory Compare sequence 79 both succeeded.",
    19: "Parser failure published no finding; positional exact-Context recovery succeeded at sequence 40.",
    20: "Parser failure published no finding; positional exact-Context recovery succeeded at sequence 41.",
    54: "No snapshot was added; exact granted-Memory Reference sequence 75 and whole granted-Context Embed sequences 76/97 proved narrower adjacent routes.",
    77: "Expected ownership boundary; Copy sequence 73 retained the public Memory locally without deleting or transferring public ownership.",
    78: "Contradictory bounds were rejected before chunking; a valid late scratch Chunk succeeded at sequence 99.",
    100: "No usable ledger or partial application was published; snapshot Compare sequence 58 and Fit sequence 105 remained available as read-only evidence.",
}


EXPECTED_BY_OP = {
    "contexts": "Return the stable readable catalog and Grant annotations without mutating Context content.",
    "list": "Render the selected direct or recursive item scope with usable names and UIDs.",
    "show": "Resolve the requested Context or exact Memory and render its stored content.",
    "find": "Return all literal matches within the explicitly frozen scope without provider access or mutation.",
    "search": "Rank relevant Memories from exactly the selected readable scope and preserve source identity.",
    "query": "Answer only from the authorized selected sources with explicit References and no disclosure outside scope.",
    "summarize": "Produce a bounded source-grounded summary for the requested exact or recursive frame.",
    "add": "Create the exact public update Memory under the CREATE-granted target and emit its UID.",
    "edit": "Atomically replace the selected exact Memory content and checkpoint its granted owner.",
    "replace": "Apply literal replacement atomically when the target is an ordinary local Context; reject nonlocal targets before mutation.",
    "copy": "Retain owned copies with new UIDs while leaving every Source unchanged.",
    "reference": "Retain a snapshot or Memory reference in the local target while preserving Source ownership.",
    "embed": "Add the requested live Context or Memory relationship to the local target without copying content.",
    "move": "Move only ordinary local Memories, preserve or explicitly break links, and reject granted ownership transfer.",
    "chunk": "Validate bounds before mutation and replace only the selected local Memory with ordered bounded chunks.",
    "compare": "Compare only the frozen peer endpoints; snapshot or ledger output must remain read-only and schema-valid.",
    "find-duplicates": "Report complete exact duplicate groups in the selected direct or recursive scope without mutation.",
    "find-redundancies": "Report complete semantic absorption evidence for the selected frame without applying it.",
    "find-ambiguities": "Report ambiguous or underspecified Memories from the requested readable source without applying decisions.",
    "find-conflicts": "Report conflicting Memory pairs and questions without reconciling them.",
    "fit": "Judge whether every selected proposition/Memory/Context can coexist under the supplied background.",
}


def parse_raw(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    stdout = text.split("\nSTDOUT\n", 1)[1].split("\n\nSTDERR\n", 1)[0]
    stderr = text.split("\n\nSTDERR\n", 1)[1]
    return stdout.strip(), stderr.strip()


def concise_actual(meta: dict, stdout: str, stderr: str) -> str:
    seq = meta["sequence"]
    if seq in (1, 22, 43, 64, 85):
        return "Exited 0 and printed 105 Context/Grant rows spanning practice and all three task worlds; current remained practice."
    if seq == 44:
        return "Exited 0 and emitted a 904-line recursive participant rendering containing Memories, snapshots, references, and live embeds."
    if seq == 86:
        return "Exited 0 and emitted a 580-line recursive public campus-wiki rendering across all readable area descendants."
    if stderr:
        body = re.sub(r"\s+", " ", stderr)
        return f"Exited {meta['exit']}. {body[:900]}"
    body = re.sub(r"\s+", " ", stdout)
    if not body:
        return f"Exited {meta['exit']} with no stdout or stderr."
    return f"Exited {meta['exit']}. {body[:900]}"


def main() -> None:
    metas = [json.loads(path.read_text()) for path in sorted(RAW.glob("*.json"))]
    if len(metas) != 105 or [item["sequence"] for item in metas] != list(range(1, 106)):
        raise SystemExit("expected exactly sequences 1..105")
    for left, right in zip(metas, metas[1:]):
        if left["post_target_digest"] != right["pre_target_digest"]:
            raise SystemExit(f"lane continuity break after sequence {left['sequence']}")

    operations = {op: {"attempts": []} for op in OPS}
    for meta in metas:
        op = meta["operation"]
        attempt = meta["attempt"]
        route = ROUTES[op][attempt - 1]
        raw_path = ROOT / meta["raw_output"]
        stdout, stderr = parse_raw(raw_path)
        pinned_lane = (
            "no reset; same pinned Profile UID "
            "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd and lane Store "
            "/Users/KimMunyeong/.codex/audit-stores/memcommit-six-world-v2-20260825/"
            "worlds/task-1/profile-control/stores/8d6d6360-c3eb-40f9-a490-5c7b2a242bfd"
        )
        continuity = (
            f"{pinned_lane}; fixed snapshot entry digest"
            if meta["sequence"] == 1
            else f"{pinned_lane}; pre digest equals sequence {meta['sequence'] - 1} post digest"
        )
        if meta["exit"]:
            continuity += "; failed attempt was retained in command evidence without resetting the Store"
        recovery = RECOVERY.get(
            meta["sequence"],
            "No recovery required; this post digest became the next counted attempt's pre digest."
        )
        start_stage = (
            "fixed initial snapshot"
            if attempt == 1
            else f"round {attempt} accumulated lane state after {attempt - 1} area workflow(s)"
        )
        record = {
            "attempt": attempt,
            "sequence": meta["sequence"],
            "command": meta["command"],
            "exit": meta["exit"],
            "starting_state": start_stage,
            "entry_route": route[0],
            "target_route": route[1],
            "scope": route[2],
            "input_provenance": route[3],
            "consumer": route[4],
            "expected": EXPECTED_BY_OP[op],
            "actual": concise_actual(meta, stdout, stderr),
            "defect_ids": DEFECTS_BY_SEQUENCE.get(meta["sequence"], []),
            "cost": {
                "wall_seconds": meta["wall_seconds"],
                "terminal_screens": max(1, math.ceil((stdout.count("\n") + stderr.count("\n") + 1) / 52)),
                "extra_manual_steps": 0,
                "tui": False,
            },
            "pre_target_digest": meta["pre_target_digest"],
            "post_target_digest": meta["post_target_digest"],
            "recovery_evidence": recovery,
            "state_continuity": continuity,
            "evidence_id": f"task-1/core/seq-{meta['sequence']:03d}",
            "raw_output": meta["raw_output"],
        }
        operations[op]["attempts"].append(record)

    for op in OPS:
        attempts = operations[op]["attempts"]
        if [item["attempt"] for item in attempts] != [1, 2, 3, 4, 5]:
            raise SystemExit(f"bad attempt coverage for {op}")
        operations[op]["coverage"] = 5
        operations[op]["diversity_signatures"] = [
            {
                "entry_route": item["entry_route"],
                "target_route": item["target_route"],
                "scope": item["scope"],
                "input_provenance": item["input_provenance"],
            }
            for item in attempts
        ]
        if op == "contexts":
            operations[op]["unsupported_dimension_note"] = (
                "Contexts exposes only one noninteractive argv route. Its five counted uses "
                "therefore test the operation-specific temporal function of re-discovering "
                "the same frozen Profile catalog after distinct public mutations; target "
                "stage, provenance, and consumer differ, while command spelling intentionally does not."
            )

    ledger = {
        "schema_version": 2,
        "study": "study-long-audit-20260825-v2",
        "world": "task-1",
        "phase": "core",
        "status": "complete",
        "world_goal": "Update every affected campus-wiki area from verified construction Memories and contribute the completed update.",
        "execution_identity": {
            "code_sha": "a004fd87545e012a191cc2b1d06af99cd54d40049d304e292694788e01b09f84",
            "code_sha256": "a004fd87545e012a191cc2b1d06af99cd54d40049d304e292694788e01b09f84",
            "catalog_sha": "3799baa25d2d5d2d3526a7afaed915d323aa7885ddac1b5cd666347a7fad93d5",
            "catalog_sha256": "3799baa25d2d5d2d3526a7afaed915d323aa7885ddac1b5cd666347a7fad93d5",
            "profile_uid": "8d6d6360-c3eb-40f9-a490-5c7b2a242bfd",
            "profile_control_root": "/Users/KimMunyeong/.codex/audit-stores/memcommit-six-world-v2-20260825/worlds/task-1/profile-control",
            "lane_store_root": "/Users/KimMunyeong/.codex/audit-stores/memcommit-six-world-v2-20260825/worlds/task-1/profile-control/stores/8d6d6360-c3eb-40f9-a490-5c7b2a242bfd",
            "store_root": "/Users/KimMunyeong/.codex/audit-stores/memcommit-six-world-v2-20260825/worlds/task-1/profile-control/stores/8d6d6360-c3eb-40f9-a490-5c7b2a242bfd",
            "provider_digest": "b549e05b6930fdacbe9dbaec09543390840a2689cd4b4ef1fa6470ca71a5f1ca",
            "provider_policy_sha256": "b549e05b6930fdacbe9dbaec09543390840a2689cd4b4ef1fa6470ca71a5f1ca",
            "runner": "/Users/KimMunyeong/Github/memcommit/agent-records/outputs/study-long-audit-20260825-v2/run_world_mem.py",
        },
        "coverage": {
            "operations": 21,
            "attempts_per_operation": 5,
            "counted_actual_mem_commands": 105,
            "exit_zero": sum(meta["exit"] == 0 for meta in metas),
            "nonzero_boundary_or_failure": sum(meta["exit"] != 0 for meta in metas),
            "wall_seconds": round(sum(meta["wall_seconds"] for meta in metas), 6),
            "tui_attempts": 0,
        },
        "goal_progress": {
            "affected_public_areas_touched": [
                "building-access", "event-relocations", "facility-updates",
                "route-changes", "shop-updates", "temporary-parking",
            ],
            "publication_method": (
                "Added consolidated time-bounded update Memories to five public areas "
                "and rewrote the stale route baseline Memory in the sixth."
            ),
            "remaining_work_for_later_phases": (
                "Normal-period baseline Memories intentionally remain alongside the temporary "
                "overrides; conflict reports identify them for reviewed transform/application work."
            ),
            "final_public_state_read_only_verification": {
                "building-access": {"memory_uid_prefix": "ab8dfc9d", "direct_items": 51},
                "event-relocations": {"memory_uid_prefix": "86484518", "direct_items": 51},
                "facility-updates": {"memory_uid_prefix": "0c6f3171", "direct_items": 51},
                "route-changes": {"memory_uid_prefix": "ee271f65", "direct_items": 50, "rewritten_existing_memory": True},
                "shop-updates": {"memory_uid_prefix": "09ace28a", "direct_items": 51},
                "temporary-parking": {"memory_uid_prefix": "1ab28435", "direct_items": 51},
            },
        },
        "safety": {
            "cumulative_store_reset": False,
            "product_code_edited": False,
            "external_share_or_disclosure": False,
            "unsupported_fact_approval": False,
            "ambiguous_semantic_apply": False,
            "clipboard_used": False,
            "writes_outside_lane_and_owned_output": False,
        },
        "operations": operations,
        "issues": ISSUES,
    }
    (ROOT / "phase-core.json").write_text(json.dumps(ledger, indent=2) + "\n")
    (ROOT / "issues.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "study": "study-long-audit-20260825-v2",
                "world": "task-1",
                "issues": ISSUES,
            },
            indent=2,
        )
        + "\n"
    )

    lines = [
        "# task-1 core issues", "",
        "105 counted commands completed against one cumulative frozen lane. "
        "The issue list distinguishes product/interaction findings from the "
        "provider-schema infrastructure failure.", "",
    ]
    for issue in ISSUES:
        lines.extend(
            [
                f"## {issue['id']} · {issue['title']}", "",
                f"- Severity: `{issue['severity']}`",
                f"- Classification: `{issue['classification']}`",
                f"- Expected: {issue['expected']}",
                f"- Actual: {issue['actual']}",
                f"- Workaround: {issue['workaround']}",
                f"- Evidence: {', '.join(issue['evidence_ids'])}", "",
            ]
        )
    (ROOT / "issues-core.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
