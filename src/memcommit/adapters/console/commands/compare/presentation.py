"""Compare-owned labels around the shared peer-relation presentation."""

from __future__ import annotations

from collections import Counter
import shlex

from memcommit.adapters.console.terminal.components.peer_relations.presentation import (
    render_peer_relation_analysis,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.adapters.console.terminal.core.text_layout import (
    elide_terminal_text,
    single_line_terminal_text,
)
from memcommit.application.capabilities.authority.source_use_policy import (
    AnalysisRetention,
)
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.model import (
    MemoryRelationAnalysis,
)


def _compare_argv(analysis: MemoryRelationAnalysis) -> list[str]:
    reference, compared = analysis.frames
    argv = ["mem", "compare", reference.context_name, compared.context_name]
    if analysis.include_descendants[0]:
        argv.append("--reference-descendants")
    if analysis.include_descendants[1]:
        argv.append("--compared-descendants")
    return argv


def render_comparison(
    analysis: MemoryRelationAnalysis,
    *,
    reused: bool,
    origin: str | None = None,
    ledger: bool = False,
    durable: bool = True,
    retention: AnalysisRetention | None = None,
) -> str:
    """Render one Compare-labelled view of the shared immutable ledger."""

    argv = _compare_argv(analysis)
    return render_peer_relation_analysis(
        analysis,
        reused=reused,
        origin=origin,
        ledger=ledger,
        durable=durable,
        retention=retention,
        heading="MEM COMPARE · SYMMETRIC PEERS",
        refresh_command=shlex.join([*argv, "--refresh"]),
        inspection_command=shlex.join([*argv, "--ledger"]),
    )


def render_comparison_receipt(
    analysis: MemoryRelationAnalysis,
    *,
    durable: bool = True,
) -> str:
    """Render Compare's bounded command receipt for the shared analysis."""

    reference, compared = analysis.frames
    counts = Counter(relation.kind for relation in analysis.relations)
    understood = elide_terminal_text(
        single_line_terminal_text(display_escape_text(analysis.understanding.text)),
        280,
    )
    lines = [
        (
            "COMPARE · "
            f"{display_escape_text(reference.context_name)} ↔ "
            f"{display_escape_text(compared.context_name)}"
        ),
        "",
        "UNDERSTOOD · " + understood,
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


__all__ = ["render_comparison", "render_comparison_receipt"]
