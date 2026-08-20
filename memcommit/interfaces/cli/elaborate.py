"""Plain projection for typed Elaborate proposals."""

from __future__ import annotations

import typer

from memcommit.elaborate import ElaborateMode
from memcommit.elaborate_application import ElaborateResult
from memcommit.interfaces.console.text import safe_terminal_text


def elaborate_result_lines(result: ElaborateResult) -> tuple[str, ...]:
    if not isinstance(result, ElaborateResult):
        raise TypeError("Elaborate rendering requires a typed result.")
    analysis = result.analysis
    direction = (
        "GOAL → RULES"
        if analysis.mode is ElaborateMode.GOAL_TO_RULES
        else "RULES → CASES"
    )
    lines = [
        f"ELABORATE · {direction}",
        f"STATUS · REVIEW ONLY · SUGGESTED · UNVERIFIED · {result.origin.replace('_', ' ')}",
        "",
        "WHAT MEM UNDERSTOOD",
        safe_terminal_text(analysis.overview),
    ]
    if analysis.mode is ElaborateMode.GOAL_TO_RULES:
        lines.extend(("", f"PROPOSED RULES · {len(analysis.rules)}"))
        for index, rule in enumerate(analysis.rules, 1):
            lines.extend(
                (
                    "",
                    f"{index}. [Suggested] [Unverified] {safe_terminal_text(rule.content)}",
                    f"   WHY · {safe_terminal_text(rule.rationale)}",
                )
            )
    else:
        lines.extend(("", f"PROPOSED CASES · {len(analysis.cases)}"))
        for index, case in enumerate(analysis.cases, 1):
            lines.extend(
                (
                    "",
                    f"{index}. [{case.case_role}] [Suggested] [Unverified] "
                    f"{safe_terminal_text(case.proposition)}",
                    f"   SOURCE RULE · {case.source_rule_index}",
                    f"   EXPECTED · {safe_terminal_text(case.expected or '(open)')}",
                    f"   WHY · {safe_terminal_text(case.rationale)}",
                )
            )
    lines.extend(("", "PROPOSALS · SUGGESTED · UNVERIFIED"))
    return tuple(lines)


def elaborate_result_text(result: ElaborateResult) -> str:
    return "\n".join(elaborate_result_lines(result))


def render_elaborate_plain(result: ElaborateResult) -> None:
    typer.echo(elaborate_result_text(result))


__all__ = [
    "elaborate_result_lines",
    "elaborate_result_text",
    "render_elaborate_plain",
]
