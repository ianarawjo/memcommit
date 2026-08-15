"""Presentation-neutral helpers shared by Fit interface adapters."""

from __future__ import annotations

from memcommit.fit import FitStatus
from memcommit.fit_application import FitResult
from memcommit.interfaces.console.text import safe_terminal_text


FIT_STATUS_ORDER: tuple[FitStatus, ...] = (
    "FIT",
    "CONTRADICTS",
    "UNDERDETERMINED",
    "NOT_APPLICABLE",
)


def fit_status_counts(result: FitResult) -> tuple[tuple[FitStatus, int], ...]:
    """Count the stable Fit vocabulary without assigning interface styling."""

    if not isinstance(result, FitResult):
        raise TypeError("Fit status counts require a typed Fit result.")
    return tuple(
        (
            status,
            sum(judgment.status == status for judgment in result.report.judgments),
        )
        for status in FIT_STATUS_ORDER
    )


def fit_result_lines(result: FitResult) -> tuple[str, ...]:
    """Project the stable complete plain document from typed Fit fields."""

    if not isinstance(result, FitResult):
        raise TypeError("Fit presentation requires a typed Fit result.")
    report = result.report
    identity = report.provider_identity
    example_by_uid = {example.uid: example for example in report.examples}
    rule_alias = {rule.uid: rule.alias for rule in report.rules}
    lines = [
        f"FIT · {safe_terminal_text(report.ground_name)} · "
        f"REVISION {report.ground_revision}",
        "STATUS · READ-ONLY · " + ("CURRENT" if result.current else "STALE"),
        f"RULES {len(report.rules)} · EXAMPLES {len(report.examples)}",
        "PROVIDER · "
        + (identity.display_name() if identity is not None else "UNRECORDED"),
        "",
        "WHAT MEM UNDERSTOOD",
        safe_terminal_text(report.overview),
        "",
        "EXAMPLE FIT",
    ]
    for judgment in report.judgments:
        example = example_by_uid[judgment.example_uid]
        lines.extend(
            [
                "",
                f"{example.alias} · {judgment.status} · RULES "
                + ", ".join(rule_alias[uid] for uid in judgment.rule_uids),
                f"  {safe_terminal_text(example.statement)}",
                f"  WHY · {safe_terminal_text(judgment.reason)}",
            ]
        )
        if judgment.observed:
            lines.append(
                f"  OBSERVED · {safe_terminal_text(judgment.observed)}"
            )
    lines.extend(
        [
            "",
            "TOTALS · "
            + " · ".join(
                f"{status} {count}"
                for status, count in fit_status_counts(result)
            ),
            f"RECEIPT · {report.uid} · {report.digest}",
            "GROUND DIGEST · " + report.ground_digest,
        ]
    )
    if not result.current:
        lines.append("STALE · Ground changed after this immutable Fit receipt.")
    return tuple(lines)


def fit_result_text(result: FitResult) -> str:
    """Return the complete stable Fit document as plain text."""

    return "\n".join(fit_result_lines(result))
