"""Interface-neutral plain-text presentation for frozen Compare analyses."""

from __future__ import annotations

from collections import Counter
import shlex

from memcommit.comparison import (
    ComparisonAnalysis,
    ComparisonError,
    ComparisonRelation,
)
from memcommit.derived_policy import AnalysisRetention
from memcommit.interfaces.console.text import display_escape_text
from memcommit.interfaces.tui.core.text_layout import (
    elide_terminal_text,
    single_line_terminal_text,
)
from memcommit.interfaces.understanding import understanding_lines
from memcommit.source_projection.model import SourceAccess, SourceDisplayFacts
from memcommit.source_projection.presentation import source_display_text


def _single_line(value: str, *, limit: int = 110) -> str:
    normalized = single_line_terminal_text(display_escape_text(value))
    return elide_terminal_text(normalized, limit)


def _relation_lines(
    analysis: ComparisonAnalysis,
    relation: ComparisonRelation,
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
        )
    lines.append(f"      WHY · {display_escape_text(relation.reason)}")
    return lines


def _relation_groups(
    analysis: ComparisonAnalysis,
) -> dict[str, list[ComparisonRelation]]:
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
    analysis: ComparisonAnalysis,
    *,
    reused: bool,
    origin: str | None,
    durable: bool,
    retention: AnalysisRetention | None,
) -> list[str]:
    reference, compared = analysis.frames
    counts = Counter(relation.kind for relation in analysis.relations)
    read_grant_label = source_display_text(
        SourceDisplayFacts(access=SourceAccess.READ_GRANT)
    )
    analysis_state = (
        "EXACT PREWARM"
        if origin == "EXACT_PREWARM"
        else "EQUIVALENT SCOPE PREWARM"
        if origin == "EQUIVALENT_SCOPE_PREWARM"
        else "PROJECTED"
        if origin == "PROJECTED"
        else "REUSED"
        if reused
        else "NEW"
    )
    return [
        "MEM COMPARE · SYMMETRIC PEERS",
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
    analysis: ComparisonAnalysis,
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


def render_comparison(
    analysis: ComparisonAnalysis,
    *,
    reused: bool,
    origin: str | None = None,
    ledger: bool = False,
    durable: bool = True,
    retention: AnalysisRetention | None = None,
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
    )
    lines.append("")
    lines.extend(understanding_lines(analysis.understanding))

    if not ledger:
        if analysis.reports is None:
            refresh_command = display_escape_text(
                shlex.join(
                    [
                        "mem",
                        "compare",
                        reference.context_name,
                        compared.context_name,
                        "--refresh",
                    ]
                )
            )
            raise ComparisonError(
                "This saved comparison predates compact reports. "
                f"Run '{refresh_command}' to update it."
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
        # A saved or projected report can be reopened while the global current
        # Context points elsewhere. Preserve both canonical endpoints so the
        # displayed ledger command cannot silently change its reference side.
        compare_argv = [
            "mem",
            "compare",
            reference.context_name,
            compared.context_name,
        ]
        if analysis.include_descendants[0]:
            compare_argv.append("--reference-descendants")
        if analysis.include_descendants[1]:
            compare_argv.append("--compared-descendants")
        ledger_command = display_escape_text(shlex.join([*compare_argv, "--ledger"]))
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
                f"  {ledger_command}",
            ]
        )
        return "\n".join(lines)

    lines.extend(["", f"RELATION LEDGER · {len(analysis.relations)}"])
    sections: list[tuple[str, list[ComparisonRelation]]] = [
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


def render_comparison_receipt(
    analysis: ComparisonAnalysis,
    *,
    durable: bool = True,
) -> str:
    """Render the bounded default result while retaining the complete report."""

    reference, compared = analysis.frames
    counts = Counter(relation.kind for relation in analysis.relations)
    lines = [
        (
            "COMPARE · "
            f"{display_escape_text(reference.context_name)} ↔ "
            f"{display_escape_text(compared.context_name)}"
        ),
        "",
        "UNDERSTOOD · " + _single_line(analysis.understanding.text, limit=280),
        (
            "RELATIONS · "
            f"SAME {counts['EQUIVALENT'] + counts['COMPATIBLE']} · "
            f"DIFFERENT {counts['SCOPED'] + counts['DISTINCT']} · "
            f"UNCLEAR {counts['UNCLEAR']}"
        ),
        f"ATTENTION · {len(analysis.issues)} potential conflicts",
        f"ANALYSIS · {analysis.uid}",
    ]
    if durable:
        lines.append(f"REVIEW · mem review compare --session {analysis.uid}")
    else:
        lines.append("REVIEW · unavailable for this temporary projection")
    return "\n".join(lines)
