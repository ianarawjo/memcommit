"""Project a Summarize result into the shared semantic Viewer contract."""

from __future__ import annotations

from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.interfaces.summarize import summarize_scope_label
from memcommit.interfaces.tui.operations.summarize.model import (
    SummarizeClipboardProjection,
    SummarizeTuiOutcome,
)
from memcommit.interfaces.tui.viewers.semantic import (
    SemanticViewerBlock,
    SemanticViewerDocument,
    SemanticViewerSection,
)
from memcommit.interfaces.understanding import understanding_lines
from memcommit.summarize_application import SummarizeResult


def _clipboard_scope_label(result: SummarizeResult) -> str:
    return (
        "[CURRENT + DESCENDANTS]"
        if result.include_descendants
        else "[CURRENT ONLY]"
    )


def _clipboard_text(
    results: tuple[SummarizeResult, ...],
    *,
    include_scope_labels: bool,
) -> str:
    lines: list[str] = []
    for index, result in enumerate(results):
        if index:
            lines.append("")
        if include_scope_labels:
            lines.append(_clipboard_scope_label(result))
        lines.extend(understanding_lines(result.understanding))
    return "\n".join(lines)


def project_summarize_clipboard(
    source: SummarizeResult | SummarizeTuiOutcome,
    *,
    focused_uid: str | None = None,
    whole_document: bool = True,
) -> SummarizeClipboardProjection:
    """Project the focused scope or complete typed Summary as plain text."""

    if isinstance(source, SummarizeResult):
        return SummarizeClipboardProjection(
            _clipboard_text((source,), include_scope_labels=False),
            "complete summary",
        )
    if not isinstance(source, SummarizeTuiOutcome):
        raise TypeError("Summarize clipboard requires a typed result.")

    results = source.results
    if not whole_document and len(results) == 2:
        # Only a section inside an explicitly labelled scope narrows `y`.
        # The shared title/status describes the whole document, so `y` there
        # must agree with `Y` instead of silently choosing the first scope.
        include_descendants: bool | None = None
        if focused_uid and ":DIRECT:" in focused_uid:
            include_descendants = False
        elif focused_uid and ":RECURSIVE:" in focused_uid:
            include_descendants = True
        if include_descendants is not None:
            focused = source.result_for(
                include_descendants=include_descendants
            )
            if focused is None:
                raise ValueError("The focused Summary scope is unavailable.")
            results = (focused,)

    label = (
        "complete summary"
        if whole_document or len(results) == len(source.results)
        else (
            "current + descendants summary"
            if results[0].include_descendants
            else "current-only summary"
        )
    )
    return SummarizeClipboardProjection(
        _clipboard_text(results, include_scope_labels=True),
        label,
    )


def project_summarize_result(result: SummarizeResult) -> SemanticViewerDocument:
    """Return a typed read-only document without reparsing CLI output."""

    if not isinstance(result, SummarizeResult):
        raise TypeError("Summarize TUI requires a SummarizeResult.")
    return SemanticViewerDocument(
        (
            SemanticViewerSection(
                "SUMMARY:TITLE",
                "TITLE",
                SemanticViewerBlock(
                    (
                        (
                            "class:title",
                            f" SUMMARY · {safe_terminal_text(result.context_name)}\n",
                        ),
                    )
                ),
            ),
            SemanticViewerSection(
                "SUMMARY:STATUS",
                "STATUS",
                SemanticViewerBlock(
                    (
                        (
                            "class:report-label",
                            " STATUS · READ-ONLY · "
                            f"{summarize_scope_label(result)} · "
                            f"SOURCES {result.source_count:,}\n",
                        ),
                    )
                ),
            ),
            SemanticViewerSection(
                "SUMMARY:UNDERSTANDING",
                "UNDERSTANDING",
                SemanticViewerBlock(
                    (
                        ("class:section", "\n WHAT MEM UNDERSTOOD\n"),
                        (
                            "class:viewer-body",
                            f" {safe_terminal_text(result.understanding.text)}\n",
                        ),
                    ),
                    focus_indices=(0, 1),
                ),
            ),
        )
    )


def project_summarize_outcome(
    outcome: SummarizeTuiOutcome,
) -> SemanticViewerDocument:
    """Project one scope normally or keep both independent views visible."""

    if not isinstance(outcome, SummarizeTuiOutcome):
        raise TypeError("Summarize TUI requires a typed outcome.")
    if len(outcome.results) == 1:
        return project_summarize_result(outcome.results[0])

    direct = outcome.result_for(include_descendants=False)
    recursive = outcome.result_for(include_descendants=True)
    if direct is None or recursive is None:
        raise ValueError("Both Summary views require direct and recursive results.")

    sections: list[SemanticViewerSection] = [
        SemanticViewerSection(
            "SUMMARY:TITLE",
            "TITLE",
            SemanticViewerBlock(
                (
                    (
                        "class:title",
                        f" SUMMARY · {safe_terminal_text(direct.context_name)}\n",
                    ),
                )
            ),
        ),
        SemanticViewerSection(
            "SUMMARY:STATUS",
            "STATUS",
            SemanticViewerBlock(
                (("class:report-label", " STATUS · READ-ONLY · BOTH VIEWS\n"),)
            ),
        ),
    ]
    for uid, label, result in (
        ("DIRECT", "[CURRENT ONLY]", direct),
        ("RECURSIVE", "[CURRENT + DESCENDANTS]", recursive),
    ):
        sections.extend(
            (
                SemanticViewerSection(
                    f"SUMMARY:{uid}:SCOPE",
                    "SCOPE",
                    SemanticViewerBlock(
                        (("class:section", f"\n {label}\n"),)
                    ),
                ),
                SemanticViewerSection(
                    f"SUMMARY:{uid}:STATUS",
                    "STATUS",
                    SemanticViewerBlock(
                        (
                            (
                                "class:report-label",
                                f" STATUS · {summarize_scope_label(result)} · "
                                f"SOURCES {result.source_count:,}\n",
                            ),
                        )
                    ),
                ),
                SemanticViewerSection(
                    f"SUMMARY:{uid}:UNDERSTANDING",
                    "UNDERSTANDING",
                    SemanticViewerBlock(
                        (
                            ("class:section", " WHAT MEM UNDERSTOOD\n"),
                            (
                                "class:viewer-body",
                                " "
                                f"{safe_terminal_text(result.understanding.text)}\n",
                            ),
                        ),
                        focus_indices=(0, 1),
                    ),
                ),
            )
        )
    return SemanticViewerDocument(tuple(sections))
