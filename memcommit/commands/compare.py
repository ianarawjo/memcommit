"""Create or resume one targetless ordered peer-Context comparison."""
from __future__ import annotations

from collections import Counter
import shlex
from typing import Annotated
import unicodedata

import typer

from memcommit.comparison import (
    COMPARISON_RULESET_VERSION,
    ComparisonAnalysis,
    ComparisonError,
    ComparisonInput,
    ComparisonRelation,
)
from memcommit.comparison_provider import (
    ComparisonProviderError,
    analyze_comparison,
)
from memcommit.comparison_store import (
    ConcurrentComparisonUpdateError,
    load_comparison_analysis,
    save_comparison_analysis,
)
from memcommit.context_locator import resolve_context_locator
from memcommit.query_provider import (
    CodexChatGPTProvider,
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.store import MemoryStore


COMPARE_AGGREGATE_TIMEOUT_SECONDS = 300


class CompareCommandError(RuntimeError):
    """Safe user-facing Compare orchestration failure."""


def display_escape_text(value: str) -> str:
    """Render untrusted semantic text as one unambiguous terminal line."""
    escaped: list[str] = []
    named_controls = {
        "\n": r"\n",
        "\t": r"\t",
        "\r": r"\r",
        "\b": r"\b",
        "\f": r"\f",
        "\v": r"\v",
    }
    for character in value:
        if character == "\\":
            escaped.append(r"\\")
        elif character in named_controls:
            escaped.append(named_controls[character])
        elif (
            unicodedata.category(character).startswith("C")
            or unicodedata.category(character) in {"Zl", "Zp"}
        ):
            codepoint = ord(character)
            escaped.append(
                f"\\u{codepoint:04x}"
                if codepoint <= 0xFFFF
                else f"\\U{codepoint:08x}"
            )
        else:
            escaped.append(character)
    return "".join(escaped)


def _single_line(value: str, *, limit: int = 110) -> str:
    normalized = " ".join(display_escape_text(value).split())
    return (
        normalized
        if len(normalized) <= limit
        else normalized[: limit - 1].rstrip() + "…"
    )


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
        (
            f"  {marker} R{number}. {relation.kind} · "
            f"{_single_line(relation.summary)}"
        )
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
    lines.append(
        f"      WHY · {display_escape_text(relation.reason)}"
    )
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
            and all(
                member.frame_uid == reference.uid
                for member in relation.members
            )
        ],
        "compared_only": [
            relation
            for relation in analysis.relations
            if relation.kind == "DISTINCT"
            and all(
                member.frame_uid == compared.uid
                for member in relation.members
            )
        ],
    }


def _header_lines(
    analysis: ComparisonAnalysis,
    *,
    reused: bool,
) -> list[str]:
    reference, compared = analysis.frames
    counts = Counter(relation.kind for relation in analysis.relations)
    return [
        "MEM COMPARE · SYMMETRIC PEERS",
        (
            f"Reference: {display_escape_text(reference.context_name)} "
            "(layout only; no authority)"
        ),
        f"Compared:  {display_escape_text(compared.context_name)}",
        (
            f"Analysis: {analysis.uid[:8]} · "
            f"{'REUSED' if reused else 'NEW'}"
        ),
        (
            "METRICS · "
            f"MEMORIES {len(reference.memories)} + "
            f"{len(compared.memories)} · "
            f"RELATIONS {len(analysis.relations)} · "
            f"GROUNDING {len(analysis.issues)}"
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


def _grounding_candidate_lines(
    analysis: ComparisonAnalysis,
    numbered: dict[str, int],
) -> list[str]:
    relation_by_uid = {
        relation.uid: relation for relation in analysis.relations
    }
    lines = [
        "",
        f"GROUNDING CANDIDATES · {len(analysis.issues)}",
    ]
    if not analysis.issues:
        lines.append("  (none)")
        return lines

    for index, issue in enumerate(analysis.issues, start=1):
        lines.append(
            (
                f"  {index}. [{issue.priority}] "
                f"{display_escape_text(issue.title)}"
            )
        )
        for relation_uid in issue.relation_uids:
            relation = relation_by_uid[relation_uid]
            lines.append(
                (
                    f"     RELATED · R{numbered[relation_uid]} · "
                    f"{relation.kind} · {_single_line(relation.summary)}"
                )
            )
        lines.extend(
            [
                (
                    "     WHY · "
                    f"{display_escape_text(issue.why_it_matters)}"
                ),
                f"     ASK · {display_escape_text(issue.question)}",
            ]
        )
        for option_index, option in enumerate(issue.options, start=1):
            lines.append(
                f"     ↳ {option_index}. "
                f"{display_escape_text(option.label)} · "
                f"{display_escape_text(option.text)}"
            )
    return lines


def render_comparison(
    analysis: ComparisonAnalysis,
    *,
    reused: bool,
    ledger: bool = False,
) -> str:
    """Render a compact report, optionally followed by the complete ledger."""
    reference, compared = analysis.frames
    groups = _relation_groups(analysis)
    numbered = {
        relation.uid: index
        for index, relation in enumerate(analysis.relations, start=1)
    }
    lines = _header_lines(analysis, reused=reused)
    lines.extend(
        [
            "",
            "WHAT MEM UNDERSTOOD",
            display_escape_text(analysis.overview),
        ]
    )

    if not ledger:
        if analysis.reports is None:
            raise ComparisonError(
                "This saved comparison predates compact reports. "
                "Run 'mem compare --refresh --to NAME' to update it."
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
            lines.extend(
                [
                    "",
                    title,
                    display_escape_text(report),
                ]
            )
        if analysis.issues:
            lines.extend(_grounding_candidate_lines(analysis, numbered))
        ledger_command = display_escape_text(
            shlex.join(
                [
                    "mem",
                    "compare",
                    "--to",
                    compared.context_name,
                    "--ledger",
                ]
            )
        )
        lines.extend(
            [
                "",
                (
                    "The complete source-linked relation ledger is saved. "
                    "Inspect it with:"
                ),
                f"  {ledger_command}",
            ]
        )
        return "\n".join(lines)

    lines.extend(
        [
            "",
            f"RELATION LEDGER · {len(analysis.relations)}",
        ]
    )
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
            [
                relation
                for relation in analysis.relations
                if relation.kind == "UNCLEAR"
            ],
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

    lines.extend(_grounding_candidate_lines(analysis, numbered))
    return "\n".join(lines)


def _connect_compare_provider(provider_factory):
    provider = provider_factory()
    if isinstance(provider, CodexChatGPTProvider):
        provider.timeout = max(
            provider.timeout,
            COMPARE_AGGREGATE_TIMEOUT_SECONDS,
        )
    return provider


def cmd(
    to: Annotated[
        str,
        typer.Option(
            "--to",
            help=(
                "Existing PEER Context locator; canonical or explicitly "
                "relative to the active reference Context"
            ),
        ),
    ],
    refresh: Annotated[
        bool,
        typer.Option(
            "--refresh",
            help="Run a fresh aggregate analysis even when sources match",
        ),
    ] = False,
    ledger: Annotated[
        bool,
        typer.Option(
            "--ledger",
            help="Show every exact source-linked relation and explanation",
        ),
    ] = False,
) -> None:
    """Compare the active Context with one equal-authority PEER Context."""
    store = MemoryStore(create=False)
    try:
        reference_name = store.current_context_name()
        if not reference_name:
            raise CompareCommandError(
                "No current reference Context. Run 'mem switch NAME' first."
            )
        compared_name = resolve_context_locator(
            to,
            current=reference_name,
        )
        if not store.context_exists(compared_name):
            resolution = (
                ""
                if compared_name == to
                else f" (resolved to '{compared_name}')"
            )
            raise CompareCommandError(
                f"Compared Context '{to}'{resolution} does not exist."
            )
        reference = store.load_direct(reference_name)
        compared = store.load_direct(compared_name)
        if (
            reference.uid == compared.uid
            or reference.name == compared.name
        ):
            raise CompareCommandError(
                "Compare requires two distinct Contexts."
            )

        existing = load_comparison_analysis(
            reference.uid,
            compared.uid,
        )
        if (
            existing is not None
            and existing.matches(reference, compared)
            and existing.ruleset_version == COMPARISON_RULESET_VERSION
            and not refresh
        ):
            typer.echo(
                render_comparison(
                    existing,
                    reused=True,
                    ledger=ledger,
                )
            )
            return

        comparison_input = ComparisonInput.from_contexts(
            reference,
            compared,
        )
        provider = _connect_compare_provider(
            connect_codex_chatgpt_provider
        )
        analysis = analyze_comparison(comparison_input, provider)
        save_comparison_analysis(
            store,
            analysis,
            expected_analysis_uid=(
                existing.uid if existing is not None else None
            ),
        )
        typer.echo(
            render_comparison(
                analysis,
                reused=False,
                ledger=ledger,
            )
        )
    except (
        CompareCommandError,
        ComparisonError,
        ComparisonProviderError,
        ConcurrentComparisonUpdateError,
        FileNotFoundError,
        OSError,
        QueryProviderError,
        ValueError,
    ) as error:
        typer.secho(
            f"Compare error: {error}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
