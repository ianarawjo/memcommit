"""Project typed Distill proposals into the shared semantic Viewer."""

from __future__ import annotations

from memcommit.adapters.console.commands.distill.proposal import distill_result_text
from memcommit.adapters.console.commands.distill.workbench.model import (
    DistillClipboardProjection,
)
from memcommit.adapters.console.text import safe_terminal_text
from memcommit.adapters.interfaces.tui.viewers.semantic import (
    SemanticViewerBlock,
    SemanticViewerDocument,
    SemanticViewerSection,
)
from memcommit.application.operations.distill.application import DistillResult


def _rule_text(result: DistillResult, index: int) -> str:
    rule = result.analysis.rules[index]
    support = ", ".join(uid[:8] for uid in rule.support_memory_uids)
    boundary = ", ".join(uid[:8] for uid in rule.boundary_memory_uids) or "none"
    return "\n".join(
        (
            f"RULE {index + 1} · {safe_terminal_text(rule.content)}",
            f"SUPPORT · {support}",
            f"BOUNDARY · {boundary}",
            f"WHY · {safe_terminal_text(rule.rationale)}",
        )
    )


def project_distill_clipboard(
    result: DistillResult,
    *,
    focused_uid: str | None = None,
    whole_document: bool = True,
) -> DistillClipboardProjection:
    """Copy either one typed section or the complete proposal."""

    if not isinstance(result, DistillResult):
        raise TypeError("Distill clipboard requires a typed result.")
    if whole_document or focused_uid in {
        None,
        "DISTILL:TITLE",
        "DISTILL:STATUS",
    }:
        detail = "\n\n".join(
            _rule_text(result, index)
            for index in range(len(result.analysis.rules))
        )
        return DistillClipboardProjection(
            distill_result_text(result)
            + (f"\n\nRULE DETAILS\n\n{detail}" if detail else ""),
            "complete Distill proposal",
        )
    if focused_uid == "DISTILL:GOAL":
        return DistillClipboardProjection(
            "GOAL · RELEVANCE FOCUS ONLY\n" + (result.analysis.goal or "(none)"),
            "Distill Goal focus",
        )
    if focused_uid == "DISTILL:OVERVIEW":
        return DistillClipboardProjection(
            "SOURCE OVERVIEW\n" + result.analysis.overview,
            "Distill Source overview",
        )
    if focused_uid.startswith("DISTILL:RULE:"):
        try:
            index = int(focused_uid.rsplit(":", 1)[1])
            text = _rule_text(result, index)
        except (IndexError, ValueError) as error:
            raise ValueError("The focused Distill Rule is unavailable.") from error
        return DistillClipboardProjection(text, f"Distill Rule {index + 1}")
    if focused_uid == "DISTILL:OUTSIDE":
        return DistillClipboardProjection(
            f"OUTSIDE PROPOSED RULES · {len(result.analysis.outside_memory_uids)} Memories",
            "Distill outside-evidence count",
        )
    raise ValueError("The focused Distill section is unavailable.")


def project_distill_result(result: DistillResult) -> SemanticViewerDocument:
    """Build one operation-owned document over shared Viewer mechanics."""

    if not isinstance(result, DistillResult):
        raise TypeError("Distill TUI requires a typed result.")
    analysis = result.analysis
    sections: list[SemanticViewerSection] = [
        SemanticViewerSection(
            "DISTILL:TITLE",
            "TITLE",
            SemanticViewerBlock(
                (("class:title", f" DISTILL · {safe_terminal_text(analysis.source.context_name)}\n"),)
            ),
        ),
        SemanticViewerSection(
            "DISTILL:STATUS",
            "STATUS",
            SemanticViewerBlock(
                ((
                    "class:report-label",
                    " STATUS · PROPOSAL · "
                    + ("RECURSIVE" if analysis.source.include_descendants else "DIRECT")
                    + f" · {result.origin.replace('_', ' ')}\n",
                ),)
            ),
        ),
        SemanticViewerSection(
            "DISTILL:GOAL",
            "GOAL",
            SemanticViewerBlock(
                (
                    ("class:section", "\n GOAL · RELEVANCE FOCUS ONLY\n"),
                    ("class:viewer-body", f" {safe_terminal_text(analysis.goal or '(none)')}\n"),
                ),
                focus_indices=(0, 1),
            ),
        ),
        SemanticViewerSection(
            "DISTILL:OVERVIEW",
            "SOURCE OVERVIEW",
            SemanticViewerBlock(
                (
                    ("class:section", "\n SOURCE OVERVIEW\n"),
                    ("class:viewer-body", f" {safe_terminal_text(analysis.overview)}\n"),
                ),
                focus_indices=(0, 1),
            ),
        ),
    ]
    for index, rule in enumerate(analysis.rules):
        support = ", ".join(uid[:8] for uid in rule.support_memory_uids)
        boundary = ", ".join(uid[:8] for uid in rule.boundary_memory_uids) or "none"
        sections.append(
            SemanticViewerSection(
                f"DISTILL:RULE:{index}",
                "RULE",
                SemanticViewerBlock(
                    (
                        ("class:section", f"\n RULE {index + 1}\n"),
                        ("class:memory-object", f" {safe_terminal_text(rule.content)}\n"),
                        ("class:viewer-body", f" SUPPORT · {support}\n"),
                        ("class:viewer-body", f" BOUNDARY · {boundary}\n"),
                        ("class:viewer-body", f" WHY · {safe_terminal_text(rule.rationale)}\n"),
                    ),
                    anchor="end",
                    focus_indices=(0, 1, 2, 3, 4),
                ),
            )
        )
    sections.append(
        SemanticViewerSection(
            "DISTILL:OUTSIDE",
            "OUTSIDE",
            SemanticViewerBlock(
                ((
                    "class:report-label",
                    f"\n OUTSIDE PROPOSED RULES · {len(analysis.outside_memory_uids)} Memories\n"
                    " No Result Context or checkpoint has been created.\n",
                ),)
            ),
        )
    )
    return SemanticViewerDocument(tuple(sections))
