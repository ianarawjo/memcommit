"""Presentation-neutral helpers shared by Fit interface adapters."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.operations.fit.ground_report import FitStatus
from memcommit.operations.fit.application import (
    FitPropositionsResult,
    FitResult,
)
from memcommit.operations.fit.coherence import FitCoherenceFinding, FitCoherenceReport
from memcommit.interfaces.console.text import display_escape_text


@dataclass(frozen=True)
class FitReceiptLine:
    """One line whose optional judgment token may receive semantic styling."""

    before_judgment: str
    judgment: str | None = None
    after_judgment: str = ""

    @property
    def text(self) -> str:
        """Return the ANSI-free public text for this receipt line."""

        return self.before_judgment + (self.judgment or "") + self.after_judgment


def _proposition_fit_receipt_line(
    result: FitPropositionsResult,
) -> FitReceiptLine:
    """Build one typed, category-grouped target line for general Fit."""

    if not isinstance(result, FitPropositionsResult):
        raise TypeError("General Fit summaries require a typed result.")
    question = result.analysis.question
    origin_by_alias = {origin.alias: origin for origin in result.input_origins}
    groups: dict[str, list[str]] = {
        "CONTEXT": [],
        "MEMORY": [],
        "PROPOSITION": [],
        "GOAL": [],
        "RULE": [],
        "EXAMPLE": [],
        "BACKGROUND": [],
    }
    for origin in result.input_origins:
        value = (
            origin.context_name if origin.kind == "CONTEXT" else origin.memory_uid[:8]
        )
        # Context expansion may yield many Memory propositions, but the compact
        # target receipt names the selected Context once. The typed result
        # still retains every expanded alias and exact Memory origin.
        if origin.kind == "MEMORY" or value not in groups[origin.kind]:
            groups[origin.kind].append(value)
    for proposition in question.propositions:
        if proposition.alias in origin_by_alias:
            continue
        groups[proposition.role].append(proposition.alias)
    groups["BACKGROUND"].extend(item.alias for item in question.background)

    target_groups = []
    for label, values in groups.items():
        if not values:
            continue
        escaped = ", ".join(display_escape_text(value) for value in values)
        target_groups.append(f"{label} {escaped}")
    targets = ", ".join(target_groups)
    assessment = result.analysis.assessment
    suffix = f" · [TARGETS: {targets}]"
    if assessment.verdict != "YES":
        suffix += f" · WHY · {display_escape_text(assessment.reason)}"
    return FitReceiptLine("FIT · ", assessment.verdict, suffix)


def proposition_fit_summary_line(result: FitPropositionsResult) -> str:
    """Return one grouped target line for the complete general Fit frame."""

    return _proposition_fit_receipt_line(result).text


def proposition_fit_receipt_lines(
    result: FitPropositionsResult,
) -> tuple[FitReceiptLine, ...]:
    """Return typed segments for one general Fit target line."""

    if not isinstance(result, FitPropositionsResult):
        raise TypeError("General Fit presentation requires a typed result.")
    return (_proposition_fit_receipt_line(result),)


def proposition_fit_result_lines(
    result: FitPropositionsResult,
) -> tuple[str, ...]:
    """Project one target line while retaining detail in the typed result."""

    if not isinstance(result, FitPropositionsResult):
        raise TypeError("General Fit presentation requires a typed result.")
    return tuple(line.text for line in proposition_fit_receipt_lines(result))


def proposition_fit_result_text(result: FitPropositionsResult) -> str:
    """Return the stable plain projection for one general Fit judgment."""

    return "\n".join(proposition_fit_result_lines(result))


def fit_mark(result: FitResult, *, status: FitStatus | None = None) -> str:
    """Project freshness and conformance into Fit's compact shared marks."""

    if not isinstance(result, FitResult):
        raise TypeError("Fit marks require a typed Fit result.")
    # A stale judgment must not look currently passing or failing. Its stored
    # classification remains in the immutable receipt, while the public mark
    # asks the person or agent to run Fit again.
    if not result.current:
        return "◷"
    if status is None:
        return {
            "YES": "✓",
            "MAY": "?",
            "NO": "!",
        }[fit_verdict(result)]
    if status == "FIT":
        return "✓"
    return fit_issue_label(status)[0]


def fit_verdict(result: FitResult) -> str:
    """Return the current Ground receipt's compact YES/MAY/NO label."""

    if not isinstance(result, FitResult):
        raise TypeError("Fit verdicts require a typed Fit result.")
    if not result.current:
        return "STALE"
    statuses = [judgment.status for judgment in result.report.judgments]
    if result.report.coherence is not None:
        statuses.extend(finding.status for finding in result.report.coherence.findings)
    if "CONTRADICTS" in statuses:
        return "NO"
    if any(status in {"UNDERDETERMINED", "NOT_APPLICABLE"} for status in statuses):
        return "MAY"
    return "YES"


def fit_issue_label(status: FitStatus) -> tuple[str, str]:
    """Translate an internal non-Fit status into Fit's public receipt terms."""

    if status == "UNDERDETERMINED":
        return "?", "MAY"
    if status == "CONTRADICTS":
        return "!", "NO"
    if status == "NOT_APPLICABLE":
        return "·", "N/A"
    raise ValueError("A fitting check has no issue receipt line.")


def fit_fraction(result: FitResult) -> str:
    """Return the passing count across the receipt's complete public frame."""

    if not isinstance(result, FitResult):
        raise TypeError("Fit fractions require a typed Fit result.")
    fitted_examples = sum(
        judgment.status == "FIT" for judgment in result.report.judgments
    )
    coherence = result.report.coherence
    if coherence is None:
        return f"{fitted_examples}/{len(result.report.judgments)}"
    fitted = fitted_examples + sum(
        finding.status == "FIT" for finding in coherence.findings
    )
    total = len(result.report.judgments) + len(coherence.findings)
    return f"{fitted}/{total} checks"


def fit_axis_issue_counts(result: FitResult) -> tuple[tuple[str, int], ...]:
    """Count unified Context, vertical, and peer issues for presentation."""

    if not isinstance(result, FitResult):
        raise TypeError("Fit axis counts require a typed Fit result.")
    coherence = result.report.coherence
    if coherence is None:
        return ()
    return (
        (
            "CONTEXT",
            sum(
                item.axis == "CONTEXT" and item.status != "FIT"
                for item in coherence.findings
            ),
        ),
        (
            "VERTICAL",
            sum(item.status != "FIT" for item in result.report.judgments)
            + sum(
                item.axis == "VERTICAL" and item.status != "FIT"
                for item in coherence.findings
            ),
        ),
        (
            "PEER",
            sum(
                item.axis == "PEER" and item.status != "FIT"
                for item in coherence.findings
            ),
        ),
    )


def _fit_summary_receipt_line(result: FitResult) -> FitReceiptLine:
    """Build the typed first line of Fit's compact Ground receipt."""

    if not isinstance(result, FitResult):
        raise TypeError("Fit summaries require a typed Fit result.")
    verdict = fit_verdict(result)
    suffix = (
        f" · [TARGETS: GROUND {display_escape_text(result.report.ground_name)}]"
        f" · {fit_fraction(result)}"
    )
    axis_counts = fit_axis_issue_counts(result)
    if axis_counts:
        suffix += " · " + " · ".join(f"{axis} {count}" for axis, count in axis_counts)
    return FitReceiptLine("FIT · ", verdict, suffix)


def fit_summary_line(result: FitResult) -> str:
    """Return the stable first line of Fit's compact receipt."""

    return _fit_summary_receipt_line(result).text


def _ground_judgment_lines(result: FitResult) -> tuple[FitReceiptLine, ...]:
    """Show each non-fitting Example and its Rule side in one receipt line."""

    rule_by_uid = {rule.uid: rule for rule in result.report.rules}
    example_by_uid = {example.uid: example for example in result.report.examples}
    lines: list[FitReceiptLine] = []
    for judgment in result.report.judgments:
        if judgment.status == "FIT":
            continue
        mark, label = fit_issue_label(judgment.status)
        rules = tuple(rule_by_uid[uid] for uid in judgment.rule_uids)
        example = example_by_uid[judgment.example_uid]
        rule_side = " + ".join(
            f"[RULE {display_escape_text(rule.alias)}] "
            f"[MEMORY {rule.uid[:8]}] {display_escape_text(rule.statement)}"
            for rule in rules
        )
        lines.append(
            FitReceiptLine(
                f"{mark} ",
                label,
                f" · {rule_side} ↔ "
                f"[EXAMPLE {display_escape_text(example.alias)}] "
                f"[MEMORY {example.uid[:8]}] "
                f"{display_escape_text(example.statement)} · WHY · "
                f"{display_escape_text(judgment.reason)}",
            )
        )
    return tuple(lines)


def _coherence_participant_label(finding: FitCoherenceFinding) -> str:
    """Preserve the two semantic sides of a frozen coherence check."""

    subjects = " + ".join(
        display_escape_text(alias) for alias in finding.subject_aliases
    )
    contexts = " + ".join(
        display_escape_text(alias) for alias in finding.context_aliases
    )
    if subjects and contexts:
        return f"{subjects} ↔ {contexts}"
    if (
        finding.relation in {"GOAL_RULES", "GOAL_EXAMPLES"}
        and len(finding.subject_aliases) >= 2
    ):
        return f"{display_escape_text(finding.subject_aliases[0])} ↔ " + " + ".join(
            display_escape_text(alias) for alias in finding.subject_aliases[1:]
        )
    if len(finding.subject_aliases) == 2:
        return " ↔ ".join(
            display_escape_text(alias) for alias in finding.subject_aliases
        )
    return "SUBJECTS · " + subjects


def _coherence_issue_lines(
    report: FitCoherenceReport,
    finding: FitCoherenceFinding,
) -> tuple[FitReceiptLine, ...]:
    """Project relation participants, material evidence, and reason together."""

    mark, label = fit_issue_label(finding.status)
    subject_by_alias = {subject.alias: subject for subject in report.subjects}
    context_by_alias = {context.alias: context for context in report.contexts}
    memory_by_alias = {
        memory.alias: memory
        for context in report.contexts
        for memory in context.memories
    }
    aliases = tuple(
        dict.fromkeys(
            (
                *finding.subject_aliases,
                *finding.context_aliases,
                *finding.material_aliases,
            )
        )
    )
    evidence: list[str] = []
    for alias in aliases:
        if alias in subject_by_alias:
            subject = subject_by_alias[alias]
            statement = subject.statement or report.brief
            evidence.append(
                f"[{subject.layer} {display_escape_text(alias)}] "
                f"{display_escape_text(statement)}"
            )
        elif alias in context_by_alias:
            context = context_by_alias[alias]
            evidence.append(
                f"[CONTEXT {display_escape_text(alias)}] "
                f"{display_escape_text(context.name)} · {context.role}"
            )
        else:
            memory = memory_by_alias[alias]
            evidence.append(
                f"[MEMORY {display_escape_text(alias)}] "
                f"{display_escape_text(memory.content)}"
            )
    suffix = f" · {finding.axis} · {_coherence_participant_label(finding)}"
    if evidence:
        suffix += " · " + " · ".join(evidence)
    suffix += f" · WHY · {display_escape_text(finding.reason)}"
    return (FitReceiptLine(f"{mark} ", label, suffix),)


def fit_receipt_lines(result: FitResult) -> tuple[FitReceiptLine, ...]:
    """Project typed compact lines without losing the plain-text contract."""

    if not isinstance(result, FitResult):
        raise TypeError("Fit presentation requires a typed Fit result.")
    lines = [_fit_summary_receipt_line(result)]
    if not result.current:
        return tuple(lines)

    lines.extend(_ground_judgment_lines(result))

    coherence = result.report.coherence
    if coherence is not None:
        for finding in coherence.findings:
            if finding.status == "FIT":
                continue
            lines.extend(_coherence_issue_lines(coherence, finding))
    return tuple(lines)


def fit_result_lines(result: FitResult) -> tuple[str, ...]:
    """Project one summary plus current issue relationship blocks."""

    if not isinstance(result, FitResult):
        raise TypeError("Fit presentation requires a typed Fit result.")
    return tuple(line.text for line in fit_receipt_lines(result))


def fit_result_text(result: FitResult) -> str:
    """Return Fit's stable compact receipt text."""

    return "\n".join(fit_result_lines(result))
