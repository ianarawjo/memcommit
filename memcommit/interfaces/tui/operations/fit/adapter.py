"""Project typed Fit results into the compact semantic Viewer."""

from __future__ import annotations

from memcommit.fit_application import FitResult
from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.interfaces.fit import fit_mark, fit_result_text, fit_summary_line
from memcommit.interfaces.tui.operations.fit.model import FitClipboardProjection
from memcommit.interfaces.tui.viewers.semantic import (
    SemanticViewerBlock,
    SemanticViewerDocument,
    SemanticViewerSection,
)


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
        text = "\n\n".join(
            (
                fit_result_text(result),
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
    for judgment in report.judgments:
        example = example_by_uid[judgment.example_uid]
        mark = fit_mark(result, status=judgment.status)
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
