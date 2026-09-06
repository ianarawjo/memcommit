"""Shared console presentation for frozen peer-relation analyses."""

from __future__ import annotations

from collections import Counter

from memcommit.application.capabilities.memory_issue_analysis.peer_relations.model import (
    MemoryRelationAnalysis,
    MemoryRelationError,
    MemoryRelation,
)
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.model import (
    AnalysisRetention,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.adapters.console.terminal.core.text_layout import (
    elide_terminal_text,
    single_line_terminal_text,
)
from memcommit.source_projection.model import SourceAccess, SourceDisplayFacts
from memcommit.source_projection.presentation import source_display_text


def _single_line(value: str, *, limit: int = 110) -> str:
    normalized = single_line_terminal_text(display_escape_text(value))
    return elide_terminal_text(normalized, limit)


def _memory_provenance(memory, frame) -> str:
    source = memory.source
    if source is None or (
        source.source_form == "OWNED"
        and source.owner_context_uid == frame.context_uid
    ):
        return ""
    labels = {
        "LIVE_MEMORY_EMBED": "EMBED",
        "MEMORY_REFERENCE": "REFERENCE",
        "CONTEXT_GRAPH": "CONTEXT GRAPH",
        "CONTEXT_REFERENCE": "CONTEXT REFERENCE",
        "GRANTED_CONTEXT": "GRANTED CONTEXT",
        "OWNED": "OWNED",
    }
    return (
        " · "
        + labels[source.source_form]
        + " FROM "
        + display_escape_text(source.owner_context_name)
        + ":"
        + source.source_memory_uid[:8]
    )


def _relation_lines(
    analysis: MemoryRelationAnalysis,
    relation: MemoryRelation,
    *,
    number: int,
) -> list[str]:
    frame_by_uid = {frame.uid: frame for frame in analysis.frames}
    memory_by_key = {
        (frame.uid, memory.uid): memory
        for frame in analysis.frames
        for memory in frame.memories
    }
    marker = "?" if relation.status == "UNRESOLVED" else "✓"
    lines = [
        (f"  {marker} R{number}. {relation.kind} · {_single_line(relation.summary)}")
    ]
    for member in relation.members:
        frame = frame_by_uid[member.frame_uid]
        memory = memory_by_key[(member.frame_uid, member.memory_uid)]
        side = "REF" if frame.side == "REFERENCE" else "TO "
        lines.append(
            f"      {side} {display_escape_text(frame.context_name)} "
            f"#{memory.position + 1} [{memory.uid[:8]}] · "
            f"{display_escape_text(memory.content)}"
            f"{_memory_provenance(memory, frame)}"
        )
    lines.append(f"      WHY · {display_escape_text(relation.reason)}")
    return lines


def _relation_groups(
    analysis: MemoryRelationAnalysis,
) -> dict[str, list[MemoryRelation]]:
    reference, compared = analysis.frames
    return {
        "both": [
            relation
            for relation in analysis.relations
            if relation.kind in {"EQUIVALENT", "COMPATIBLE"}
        ],
        "differences": [
            relation
            for relation in analysis.relations
            if relation.kind in {"SCOPED", "CONFLICT", "UNCLEAR"}
        ],
        "reference_only": [
            relation
            for relation in analysis.relations
            if relation.kind == "DISTINCT"
            and all(member.frame_uid == reference.uid for member in relation.members)
        ],
        "compared_only": [
            relation
            for relation in analysis.relations
            if relation.kind == "DISTINCT"
            and all(member.frame_uid == compared.uid for member in relation.members)
        ],
    }


def _header_lines(
    analysis: MemoryRelationAnalysis,
    *,
    reused: bool,
    origin: str | None,
    durable: bool,
    retention: AnalysisRetention | None,
    heading: str,
) -> list[str]:
    reference, compared = analysis.frames
    counts = Counter(relation.kind for relation in analysis.relations)
    read_grant_label = source_display_text(
        SourceDisplayFacts(access=SourceAccess.READ_GRANT)
    )
    analysis_state = (
        "REUSED"
        if reused
        else "NEW"
    )
    return [
        heading,
        f"Reference: {display_escape_text(reference.context_name)}",
        f"Compared:  {display_escape_text(compared.context_name)}",
        (
            "SCOPE · REFERENCE "
            + (
                "SELECTED + ALL DESCENDANTS"
                if analysis.include_descendants[0]
                else "SELECTED GRAPH ONLY"
            )
            + " · COMPARED "
            + (
                "SELECTED + ALL DESCENDANTS"
                if analysis.include_descendants[1]
                else "SELECTED GRAPH ONLY"
            )
        ),
        (
            f"Analysis: {analysis.uid[:8]} · "
            + analysis_state
            + (
                " · TEMPORARY PREVIEW"
                if origin == "PROJECTED"
                else " · SAVED · RETAINED"
                if retention == "RETAINED"
                else f" · SAVED · {read_grant_label} BOUND"
                if retention == "GRANT_BOUND"
                else ""
                if durable
                else f" · TEMPORARY · {read_grant_label}"
            )
        ),
        (
            "METRICS · "
            f"MEMORIES {len(reference.memories)} + "
            f"{len(compared.memories)} · "
            f"RELATIONS {len(analysis.relations)} · "
            f"POTENTIAL CONFLICTS {len(analysis.issues)}"
        ),
        (
            f"EQUIVALENT {counts['EQUIVALENT']} · "
            f"COMPATIBLE {counts['COMPATIBLE']} · "
            f"SCOPED {counts['SCOPED']} · "
            f"CONFLICT {counts['CONFLICT']} · "
            f"DISTINCT {counts['DISTINCT']} · "
            f"UNCLEAR {counts['UNCLEAR']}"
        ),
    ]


def _potential_conflict_lines(
    analysis: MemoryRelationAnalysis,
    numbered: dict[str, int],
) -> list[str]:
    del numbered  # Stable relation numbers belong to the exhaustive ledger only.
    relation_by_uid = {relation.uid: relation for relation in analysis.relations}
    frame_by_uid = {frame.uid: frame for frame in analysis.frames}
    lines = [
        "",
        f"POTENTIAL CONFLICTS · {len(analysis.issues)}",
    ]
    if not analysis.issues:
        lines.append("  (none)")
        return lines

    for index, issue in enumerate(analysis.issues, start=1):
        source_names: list[str] = []
        relation_summaries: list[str] = []
        for relation_uid in issue.relation_uids:
            relation = relation_by_uid[relation_uid]
            relation_summaries.append(_single_line(relation.summary, limit=180))
            for member in relation.members:
                name = frame_by_uid[member.frame_uid].context_name
                if name not in source_names:
                    source_names.append(name)
        options = "; ".join(
            f"{display_escape_text(option.label)}: "
            f"{display_escape_text(option.text).rstrip(' .;')}"
            for option in issue.options
        )
        lines.extend(
            [
                "",
                (
                    f"{index}. {display_escape_text(issue.title).rstrip(' .')}. "
                    f"{' ↔ '.join(display_escape_text(name) for name in source_names)}: "
                    f"{' '.join(relation_summaries)} "
                    f"{display_escape_text(issue.why_it_matters)} "
                    f"{options}."
                ),
            ]
        )
    return lines


def render_peer_relation_analysis(
    analysis: MemoryRelationAnalysis,
    *,
    reused: bool,
    origin: str | None = None,
    ledger: bool = False,
    durable: bool = True,
    retention: AnalysisRetention | None = None,
    heading: str = "MEMORY RELATION ANALYSIS · ORDERED PEERS",
    refresh_command: str | None = None,
    inspection_command: str | None = None,
) -> str:
    """Render a compact report, optionally followed by the complete ledger."""
    reference, compared = analysis.frames
    groups = _relation_groups(analysis)
    numbered = {
        relation.uid: index
        for index, relation in enumerate(analysis.relations, start=1)
    }
    lines = _header_lines(
        analysis,
        reused=reused,
        origin=origin,
        durable=durable,
        retention=retention,
        heading=heading,
    )
    lines.append("")
    lines.extend(
        [
            "WHAT MEM UNDERSTOOD",
            display_escape_text(analysis.understanding.text),
        ]
    )

    if not ledger:
        if analysis.reports is None:
            guidance = (
                f" Run '{display_escape_text(refresh_command)}' to update it."
                if refresh_command is not None
                else ""
            )
            raise MemoryRelationError(
                "This saved relation analysis predates compact reports." + guidance
            )
        report_sections = [
            (
                f"WHAT BOTH CONTAIN · {len(groups['both'])}",
                analysis.reports.both,
                bool(groups["both"]),
            ),
            (
                f"WHAT DIFFERS · {len(groups['differences'])}",
                analysis.reports.differences,
                bool(groups["differences"]),
            ),
            (
                (
                    "ONLY IN "
                    + display_escape_text(reference.context_name)
                    + f" · {len(groups['reference_only'])}"
                    + " · not automatically a deficiency"
                ),
                analysis.reports.reference_only,
                bool(groups["reference_only"]),
            ),
            (
                (
                    "ONLY IN "
                    + display_escape_text(compared.context_name)
                    + f" · {len(groups['compared_only'])}"
                    + " · not automatically a deficiency"
                ),
                analysis.reports.compared_only,
                bool(groups["compared_only"]),
            ),
        ]
        for title, report, present in report_sections:
            if not present:
                continue
            lines.extend(["", title, display_escape_text(report)])
        if analysis.issues:
            lines.extend(_potential_conflict_lines(analysis, numbered))
        if inspection_command is not None:
            lines.extend(
                [
                    "",
                    (
                        "The complete source-linked relation ledger is saved. "
                        "Inspect it with:"
                        if durable
                        else "The complete source-linked relation ledger was not "
                        "saved. Re-run it with:"
                    ),
                    f"  {display_escape_text(inspection_command)}",
                ]
            )
        return "\n".join(lines)

    lines.extend(["", f"RELATION LEDGER · {len(analysis.relations)}"])
    sections: list[tuple[str, list[MemoryRelation]]] = [
        ("WHAT BOTH CONTAIN", groups["both"]),
        (
            "WHAT DIFFERS",
            [
                relation
                for relation in analysis.relations
                if relation.kind in {"SCOPED", "CONFLICT"}
            ],
        ),
        (
            (
                "ONLY IN "
                + display_escape_text(reference.context_name)
                + " · not automatically a deficiency"
            ),
            groups["reference_only"],
        ),
        (
            (
                "ONLY IN "
                + display_escape_text(compared.context_name)
                + " · not automatically a deficiency"
            ),
            groups["compared_only"],
        ),
        (
            "UNCLEAR",
            [relation for relation in analysis.relations if relation.kind == "UNCLEAR"],
        ),
    ]
    for title, relations in sections:
        lines.extend(["", title])
        if not relations:
            lines.append("  (none)")
            continue
        for relation in relations:
            lines.extend(
                _relation_lines(
                    analysis,
                    relation,
                    number=numbered[relation.uid],
                )
            )

    lines.extend(_potential_conflict_lines(analysis, numbered))
    return "\n".join(lines)
