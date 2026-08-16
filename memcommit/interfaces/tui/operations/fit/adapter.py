"""Project typed Fit results into the compact semantic Viewer."""

from __future__ import annotations

from memcommit.fit_application import FitPropositionsResult, FitResult
from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.interfaces.fit import (
    fit_mark,
    fit_result_text,
    fit_summary_line,
    proposition_fit_mark,
    proposition_fit_result_text,
)
from memcommit.interfaces.tui.operations.fit.model import FitClipboardProjection
from memcommit.interfaces.tui.viewers.semantic import (
    SemanticViewerBlock,
    SemanticViewerDocument,
    SemanticViewerSection,
)


def _proposition_fit_inputs_text(result: FitPropositionsResult) -> str:
    question = result.analysis.question
    lines: list[str] = []
    for item in question.background:
        lines.append(
            f"BACKGROUND · {item.alias} · {item.role}\n{safe_terminal_text(item.content)}"
        )
    for item in question.propositions:
        lines.append(
            f"PROPOSITION · {item.alias} · {item.role}\n{safe_terminal_text(item.content)}"
        )
    return "\n\n".join(lines)


def _proposition_fit_readings_text(result: FitPropositionsResult) -> str:
    assessment = result.analysis.assessment
    if assessment.verdict != "MAY":
        raise ValueError("Only MAY Fit results have split ordinary readings.")
    return (
        "CONSISTENT READING\n"
        + safe_terminal_text(assessment.consistent_reading)
        + "\n\nINCONSISTENT READING\n"
        + safe_terminal_text(assessment.inconsistent_reading)
    )


def project_proposition_fit_clipboard(
    result: FitPropositionsResult,
    *,
    focused_uid: str | None = None,
    whole_document: bool = True,
) -> FitClipboardProjection:
    """Project one focused section or the complete general Fit document."""

    if not isinstance(result, FitPropositionsResult):
        raise TypeError("General Fit clipboard requires a typed result.")
    sections = [
        ("FIT:JUDGMENT", proposition_fit_result_text(result), "Fit judgment"),
        ("FIT:INPUTS", _proposition_fit_inputs_text(result), "Fit inputs"),
    ]
    if result.analysis.assessment.verdict == "MAY":
        sections.append(
            (
                "FIT:READINGS",
                _proposition_fit_readings_text(result),
                "Fit ordinary readings",
            )
        )
    if whole_document:
        return FitClipboardProjection(
            "\n\n".join(text for _uid, text, _label in sections),
            "complete Fit result",
        )
    for uid, text, label in sections:
        if focused_uid == uid:
            return FitClipboardProjection(text, label)
    raise ValueError("The focused Fit section is unavailable.")


def project_proposition_fit_result(
    result: FitPropositionsResult,
) -> SemanticViewerDocument:
    """Build the general Fit Viewer without re-parsing plain output."""

    if not isinstance(result, FitPropositionsResult):
        raise TypeError("General Fit TUI requires a typed result.")
    assessment = result.analysis.assessment
    verdict_style = {
        "YES": "class:impact.keep",
        "MAY": "class:impact.custom",
        "NO": "class:impact.remove",
    }[assessment.verdict]
    sections: list[SemanticViewerSection] = [
        SemanticViewerSection(
            "FIT:JUDGMENT",
            "JUDGMENT",
            SemanticViewerBlock(
                (
                    (
                        verdict_style,
                        f" {proposition_fit_mark(result)} {assessment.verdict}\n",
                    ),
                    (
                        "class:viewer-body",
                        " " + safe_terminal_text(assessment.reason) + "\n",
                    ),
                )
            ),
        )
    ]
    input_fragments: list[tuple[str, str]] = []
    for prefix, items in (
        ("BACKGROUND", result.analysis.question.background),
        ("PROPOSITION", result.analysis.question.propositions),
    ):
        for item in items:
            input_fragments.extend(
                (
                    (
                        "class:viewer-label",
                        f"\n {prefix} · {item.alias} · {item.role}\n ",
                    ),
                    (
                        "class:memory-object"
                        if item.role == "MEMORY"
                        else "class:viewer-body",
                        safe_terminal_text(item.content) + "\n",
                    ),
                )
            )
    sections.append(
        SemanticViewerSection(
            "FIT:INPUTS",
            "COMPLETE FROZEN INPUT",
            SemanticViewerBlock(tuple(input_fragments), anchor="end"),
        )
    )
    if assessment.verdict == "MAY":
        sections.append(
            SemanticViewerSection(
                "FIT:READINGS",
                "ORDINARY READINGS",
                SemanticViewerBlock(
                    (
                        (
                            "class:viewer-label",
                            "\n CONSISTENT\n ",
                        ),
                        (
                            "class:viewer-body",
                            safe_terminal_text(assessment.consistent_reading) + "\n",
                        ),
                        (
                            "class:viewer-label",
                            "\n INCONSISTENT\n ",
                        ),
                        (
                            "class:viewer-body",
                            safe_terminal_text(assessment.inconsistent_reading) + "\n",
                        ),
                    ),
                    anchor="end",
                ),
            )
        )
    return SemanticViewerDocument(tuple(sections))


def _example_text(result: FitResult, example_uid: str) -> str:
    report = result.report
    example_by_uid = {example.uid: example for example in report.examples}
    judgment = next(
        (
            item
            for item in report.judgments
            if item.example_uid == example_uid
        ),
        None,
    )
    if judgment is None:
        raise ValueError("The focused Fit Example is unavailable.")
    example = example_by_uid[judgment.example_uid]
    mark = fit_mark(result, status=judgment.status)
    lines = [
        f"{mark} {example.alias} · {safe_terminal_text(example.statement)}",
    ]
    if result.current and judgment.status != "FIT":
        lines.append(
            f"{judgment.status} · {safe_terminal_text(judgment.reason)}"
        )
    coherence = report.coherence
    if result.current and coherence is not None:
        subject = next(
            (
                item
                for item in coherence.subjects
                if item.uid == example_uid and item.layer == "EXAMPLE"
            ),
            None,
        )
        if subject is not None:
            lines.extend(_finding_issue_lines(result, subject.alias))
    return "\n".join(lines)


def _finding_applies_to_alias(finding, alias: str) -> bool:
    """Project set findings only onto the subjects material to an issue."""

    if alias not in finding.subject_aliases:
        return False
    if finding.status == "FIT" or not finding.material_aliases:
        return True
    return alias in finding.material_aliases


def _finding_issue_lines(result: FitResult, alias: str) -> list[str]:
    coherence = result.report.coherence
    if coherence is None:
        return []
    return [
        (
            f"{finding.axis} · {finding.status} · "
            f"{safe_terminal_text(finding.reason)}"
        )
        for finding in coherence.findings
        if finding.status != "FIT"
        and _finding_applies_to_alias(finding, alias)
    ]


def _subject_mark(result: FitResult, alias: str) -> str:
    if not result.current:
        return "◷"
    coherence = result.report.coherence
    if coherence is None:
        return "·"
    relevant = tuple(
        item
        for item in coherence.findings
        if _finding_applies_to_alias(item, alias)
    )
    return "!" if any(item.status != "FIT" for item in relevant) else "✓"


def _context_text(result: FitResult) -> str:
    coherence = result.report.coherence
    if coherence is None:
        raise ValueError("This Fit receipt has no Context projection.")
    lines = [
        (
            f"{context.alias} · {context.role} · "
            f"{safe_terminal_text(context.name)} · "
            f"{len(context.memories)} direct Memories"
        )
        for context in coherence.contexts
    ]
    if coherence.requirements:
        lines.extend(
            [
                "",
                "TARGET REQUIREMENTS",
                *(safe_terminal_text(item) for item in coherence.requirements),
            ]
        )
    return "\n".join(lines)


def _subject_text(result: FitResult, subject) -> str:
    mark = _subject_mark(result, subject.alias)
    lines = [
        f"{mark} {subject.alias} · {safe_terminal_text(subject.statement or '(not yet stated)')}"
    ]
    if result.current:
        lines.extend(_finding_issue_lines(result, subject.alias))
    return "\n".join(lines)


def project_fit_clipboard(
    result: FitResult,
    *,
    focused_uid: str | None = None,
    whole_document: bool = True,
) -> FitClipboardProjection:
    """Project the focused Fit section or the complete typed report."""

    if not isinstance(result, FitResult):
        raise TypeError("Fit clipboard requires a typed result.")
    report = result.report
    if whole_document:
        coherence_sections: list[str] = []
        if report.coherence is not None:
            coherence_sections = [
                _context_text(result),
                *(
                    _subject_text(result, subject)
                    for subject in report.coherence.subjects
                    if subject.layer in {"GOAL", "RULE"}
                ),
            ]
        text = "\n\n".join(
            (
                fit_result_text(result),
                *coherence_sections,
                *(
                    _example_text(result, judgment.example_uid)
                    for judgment in report.judgments
                ),
            )
        )
        return FitClipboardProjection(text, "complete Fit result")
    if focused_uid == "FIT:SUMMARY":
        text = fit_summary_line(result)
        label = "Fit summary"
    elif focused_uid == "FIT:CONTEXT" and report.coherence is not None:
        text = _context_text(result)
        label = "Fit Context K"
    elif focused_uid and focused_uid.startswith("FIT:SUBJECT:"):
        subject_uid = focused_uid.removeprefix("FIT:SUBJECT:")
        subject = next(
            (
                item
                for item in (report.coherence.subjects if report.coherence else ())
                if item.uid == subject_uid
            ),
            None,
        )
        if subject is None:
            raise ValueError("The focused Fit subject is unavailable.")
        text = _subject_text(result, subject)
        label = f"Fit {subject.layer.title()} {subject.alias}"
    elif focused_uid and focused_uid.startswith("FIT:EXAMPLE:"):
        example_uid = focused_uid.removeprefix("FIT:EXAMPLE:")
        text = _example_text(result, example_uid)
        example = next(
            (
                item
                for item in report.examples
                if item.uid == example_uid
            ),
            None,
        )
        if example is None:
            raise ValueError("The focused Fit Example is unavailable.")
        label = f"Fit Example {example.alias}"
    else:
        raise ValueError("The focused Fit section is unavailable.")
    return FitClipboardProjection(text, label)


def project_fit_result(result: FitResult) -> SemanticViewerDocument:
    """Build a typed Viewer document without parsing the plain renderer."""

    if not isinstance(result, FitResult):
        raise TypeError("Fit TUI requires a typed result.")
    report = result.report
    example_by_uid = {example.uid: example for example in report.examples}
    sections: list[SemanticViewerSection] = [
        SemanticViewerSection(
            "FIT:SUMMARY",
            "SUMMARY",
            SemanticViewerBlock(
                (
                    (
                        "class:title",
                        " " + fit_summary_line(result) + "\n",
                    ),
                )
            ),
        ),
    ]
    coherence = report.coherence
    if coherence is not None:
        context_fragments: list[tuple[str, str]] = []
        for context in coherence.contexts:
            context_fragments.extend(
                (
                    (
                        "class:viewer-label",
                        f"\n {context.alias} · {context.role}\n ",
                    ),
                    (
                        "class:viewer-body",
                        f"{safe_terminal_text(context.name)} · "
                        f"{len(context.memories)} direct Memories\n",
                    ),
                )
            )
        sections.append(
            SemanticViewerSection(
                "FIT:CONTEXT",
                "CONTEXT K",
                SemanticViewerBlock(tuple(context_fragments), anchor="end"),
            )
        )
        for subject in coherence.subjects:
            if subject.layer == "EXAMPLE":
                continue
            mark = _subject_mark(result, subject.alias)
            mark_style = (
                "class:impact.custom"
                if not result.current
                else "class:impact.keep"
                if mark == "✓"
                else "class:impact.remove"
            )
            fragments: list[tuple[str, str]] = [
                (mark_style, f"\n {mark} "),
                (
                    "class:viewer-body",
                    f"{subject.alias} · "
                    f"{safe_terminal_text(subject.statement or '(not yet stated)')}\n",
                ),
            ]
            if result.current:
                fragments.extend(
                    (
                        "class:viewer-body",
                        "   " + safe_terminal_text(line) + "\n",
                    )
                    for line in _finding_issue_lines(result, subject.alias)
                )
            sections.append(
                SemanticViewerSection(
                    f"FIT:SUBJECT:{subject.uid}",
                    subject.layer,
                    SemanticViewerBlock(
                        tuple(fragments),
                        anchor="end",
                        focus_indices=tuple(range(len(fragments))),
                    ),
                )
            )
    for judgment in report.judgments:
        example = example_by_uid[judgment.example_uid]
        subject = next(
            (
                item
                for item in (coherence.subjects if coherence else ())
                if item.uid == example.uid and item.layer == "EXAMPLE"
            ),
            None,
        )
        coherence_issue = subject is not None and _subject_mark(
            result, subject.alias
        ) == "!"
        mark = (
            "◷"
            if not result.current
            else "!"
            if judgment.status != "FIT" or coherence_issue
            else "✓"
        )
        mark_style = (
            "class:impact.custom"
            if not result.current
            else "class:impact.keep"
            if judgment.status == "FIT"
            else "class:impact.remove"
        )
        fragments: list[tuple[str, str]] = [
            (
                mark_style,
                f"\n {mark} ",
            ),
            (
                "class:memory-object",
                f"{example.alias} · {safe_terminal_text(example.statement)}\n",
            ),
        ]
        if result.current and judgment.status != "FIT":
            fragments.append(
                (
                    "class:viewer-body",
                    f"   {judgment.status} · "
                    + safe_terminal_text(judgment.reason)
                    + "\n",
                )
            )
        if result.current and subject is not None:
            fragments.extend(
                (
                    "class:viewer-body",
                    "   " + safe_terminal_text(line) + "\n",
                )
                for line in _finding_issue_lines(result, subject.alias)
            )
        sections.append(
            SemanticViewerSection(
                f"FIT:EXAMPLE:{example.uid}",
                "EXAMPLE",
                SemanticViewerBlock(
                    tuple(fragments),
                    anchor="end",
                    focus_indices=tuple(range(len(fragments))),
                ),
            )
        )
    return SemanticViewerDocument(tuple(sections))
