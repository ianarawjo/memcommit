"""Project typed Fit results into the shared semantic Viewer."""

from __future__ import annotations

from memcommit.fit_application import FitResult
from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.interfaces.fit import fit_result_text, fit_status_counts
from memcommit.interfaces.tui.operations.fit.model import FitClipboardProjection
from memcommit.interfaces.tui.viewers.semantic import (
    SemanticViewerBlock,
    SemanticViewerDocument,
    SemanticViewerSection,
)


def _example_text(result: FitResult, example_uid: str) -> str:
    report = result.report
    example_by_uid = {example.uid: example for example in report.examples}
    rule_alias = {rule.uid: rule.alias for rule in report.rules}
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
    lines = [
        f"{example.alias} · {judgment.status} · RULES "
        + ", ".join(rule_alias[uid] for uid in judgment.rule_uids),
        safe_terminal_text(example.statement),
        "WHY · " + safe_terminal_text(judgment.reason),
    ]
    if judgment.observed:
        lines.append("OBSERVED · " + safe_terminal_text(judgment.observed))
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
        return FitClipboardProjection(fit_result_text(result), "complete Fit report")
    if focused_uid == "FIT:TITLE":
        text = (
            f"FIT · {safe_terminal_text(report.ground_name)} · "
            f"REVISION {report.ground_revision}"
        )
        label = "Fit title"
    elif focused_uid == "FIT:STATUS":
        identity = report.provider_identity
        text = "\n".join(
            (
                "STATUS · READ-ONLY · "
                + ("CURRENT" if result.current else "STALE"),
                f"RULES {len(report.rules)} · EXAMPLES {len(report.examples)}",
                "PROVIDER · "
                + (
                    identity.display_name()
                    if identity is not None
                    else "UNRECORDED"
                ),
            )
        )
        label = "Fit status"
    elif focused_uid == "FIT:OVERVIEW":
        text = "WHAT MEM UNDERSTOOD\n" + safe_terminal_text(report.overview)
        label = "Fit overview"
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
    elif focused_uid == "FIT:TOTALS":
        text = "TOTALS · " + " · ".join(
            f"{status} {count}"
            for status, count in fit_status_counts(result)
        )
        label = "Fit totals"
    elif focused_uid == "FIT:RECEIPT":
        lines = [
            f"RECEIPT · {report.uid} · {report.digest}",
            "GROUND DIGEST · " + report.ground_digest,
        ]
        if not result.current:
            lines.append(
                "STALE · Ground changed after this immutable Fit receipt."
            )
        text = "\n".join(lines)
        label = "Fit receipt"
    else:
        raise ValueError("The focused Fit section is unavailable.")
    return FitClipboardProjection(text, label)


def project_fit_result(result: FitResult) -> SemanticViewerDocument:
    """Build a typed Viewer document without parsing the plain renderer."""

    if not isinstance(result, FitResult):
        raise TypeError("Fit TUI requires a typed result.")
    report = result.report
    identity = report.provider_identity
    rule_alias = {rule.uid: rule.alias for rule in report.rules}
    example_by_uid = {example.uid: example for example in report.examples}
    sections: list[SemanticViewerSection] = [
        SemanticViewerSection(
            "FIT:TITLE",
            "TITLE",
            SemanticViewerBlock(
                (
                    (
                        "class:title",
                        f" FIT · {safe_terminal_text(report.ground_name)} · "
                        f"REVISION {report.ground_revision}\n",
                    ),
                )
            ),
        ),
        SemanticViewerSection(
            "FIT:STATUS",
            "STATUS",
            SemanticViewerBlock(
                (
                    (
                        "class:report-label",
                        " STATUS · READ-ONLY · "
                        + ("CURRENT" if result.current else "STALE")
                        + "\n",
                    ),
                    (
                        "class:viewer-body",
                        f" RULES {len(report.rules)} · "
                        f"EXAMPLES {len(report.examples)}\n",
                    ),
                    (
                        "class:viewer-body",
                        " PROVIDER · "
                        + (
                            identity.display_name()
                            if identity is not None
                            else "UNRECORDED"
                        )
                        + "\n",
                    ),
                ),
                focus_indices=(0, 1, 2),
            ),
        ),
        SemanticViewerSection(
            "FIT:OVERVIEW",
            "OVERVIEW",
            SemanticViewerBlock(
                (
                    ("class:section", "\n WHAT MEM UNDERSTOOD\n"),
                    (
                        "class:viewer-body",
                        " " + safe_terminal_text(report.overview) + "\n",
                    ),
                    ("class:section", "\n EXAMPLE FIT\n"),
                ),
                focus_indices=(0, 1),
            ),
        ),
    ]
    for judgment in report.judgments:
        example = example_by_uid[judgment.example_uid]
        fragments: list[tuple[str, str]] = [
            (
                "class:detail-card",
                f"\n {example.alias} · {judgment.status} · RULES "
                + ", ".join(rule_alias[uid] for uid in judgment.rule_uids)
                + "\n",
            ),
            (
                "class:viewer-body",
                " " + safe_terminal_text(example.statement) + "\n",
            ),
            (
                "class:viewer-body",
                " WHY · " + safe_terminal_text(judgment.reason) + "\n",
            ),
        ]
        if judgment.observed:
            fragments.append(
                (
                    "class:viewer-body",
                    " OBSERVED · "
                    + safe_terminal_text(judgment.observed)
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
    receipt_fragments: list[tuple[str, str]] = [
        (
            "class:viewer-body",
            f" RECEIPT · {report.uid} · {report.digest}\n",
        ),
        (
            "class:viewer-body",
            " GROUND DIGEST · " + report.ground_digest + "\n",
        ),
    ]
    if not result.current:
        receipt_fragments.append(
            (
                "class:report-label",
                " STALE · Ground changed after this immutable Fit receipt.\n",
            )
        )
    sections.extend(
        (
            SemanticViewerSection(
                "FIT:TOTALS",
                "TOTALS",
                SemanticViewerBlock(
                    (
                        (
                            "class:report-label",
                            "\n TOTALS · "
                            + " · ".join(
                                f"{status} {count}"
                                for status, count in fit_status_counts(result)
                            )
                            + "\n",
                        ),
                    )
                ),
            ),
            SemanticViewerSection(
                "FIT:RECEIPT",
                "RECEIPT",
                SemanticViewerBlock(
                    tuple(receipt_fragments),
                    focus_indices=tuple(range(len(receipt_fragments))),
                ),
            ),
        )
    )
    return SemanticViewerDocument(tuple(sections))
