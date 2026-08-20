"""Project Elaborate proposals into shared semantic Viewer mechanics."""

from __future__ import annotations

from memcommit.elaborate import ElaborateMode
from memcommit.elaborate_application import ElaborateResult
from memcommit.interfaces.cli.elaborate import elaborate_result_text
from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.interfaces.tui.operations.elaborate.model import (
    ElaborateClipboardProjection,
)
from memcommit.interfaces.tui.viewers.semantic import (
    SemanticViewerBlock,
    SemanticViewerDocument,
    SemanticViewerSection,
)


def _proposal_text(result: ElaborateResult, kind: str, index: int) -> str:
    if kind == "RULE":
        rule = result.analysis.rules[index]
        return "\n".join(
            (
                f"[Suggested] [Unverified] {rule.content}",
                f"WHY · {rule.rationale}",
            )
        )
    case = result.analysis.cases[index]
    return "\n".join(
        (
            f"[{case.case_role}] [Suggested] [Unverified] {case.proposition}",
            f"RULE COVERAGE · ALL {len(case.rule_checks)}",
            *(
                f"RULE {check.source_rule_index} · {check.evidence}"
                for check in case.rule_checks
            ),
            f"EXPECTED · {case.expected or '(open)'}",
            f"WHY · {case.rationale}",
        )
    )


def project_elaborate_clipboard(
    result: ElaborateResult,
    *,
    focused_uid: str | None = None,
    whole_document: bool = True,
) -> ElaborateClipboardProjection:
    if not isinstance(result, ElaborateResult):
        raise TypeError("Elaborate clipboard requires a typed result.")
    if whole_document or focused_uid in {
        None,
        "ELABORATE:TITLE",
        "ELABORATE:STATUS",
    }:
        kind = "RULE" if result.analysis.rules else "CASE"
        count = len(result.analysis.rules or result.analysis.cases)
        detail = "\n\n".join(
            _proposal_text(result, kind, index)
            for index in range(count)
        )
        return ElaborateClipboardProjection(
            elaborate_result_text(result)
            + (f"\n\nPROPOSAL DETAILS\n\n{detail}" if detail else ""),
            "complete Elaborate proposal",
        )
    if focused_uid == "ELABORATE:OVERVIEW":
        return ElaborateClipboardProjection(
            "WHAT MEM UNDERSTOOD\n" + result.analysis.overview,
            "Elaborate understanding",
        )
    for kind in ("RULE", "CASE"):
        prefix = f"ELABORATE:{kind}:"
        if focused_uid.startswith(prefix):
            try:
                index = int(focused_uid.removeprefix(prefix))
                text = _proposal_text(result, kind, index)
            except (IndexError, ValueError) as error:
                raise ValueError("The focused Elaborate proposal is unavailable.") from error
            return ElaborateClipboardProjection(
                text,
                f"Elaborate {kind.title()} {index + 1}",
            )
    raise ValueError("The focused Elaborate section is unavailable.")


def project_elaborate_result(result: ElaborateResult) -> SemanticViewerDocument:
    if not isinstance(result, ElaborateResult):
        raise TypeError("Elaborate TUI requires a typed result.")
    analysis = result.analysis
    direction = (
        "GOAL → RULES"
        if analysis.mode is ElaborateMode.GOAL_TO_RULES
        else "RULES → CASES"
    )
    sections: list[SemanticViewerSection] = [
        SemanticViewerSection(
            "ELABORATE:TITLE",
            "TITLE",
            SemanticViewerBlock((("class:title", f" ELABORATE · {direction}\n"),)),
        ),
        SemanticViewerSection(
            "ELABORATE:STATUS",
            "STATUS",
            SemanticViewerBlock(
                ((
                    "class:report-label",
                    " STATUS · REVIEW ONLY · SUGGESTED · UNVERIFIED · "
                    f"{result.origin.replace('_', ' ')}\n",
                ),)
            ),
        ),
        SemanticViewerSection(
            "ELABORATE:OVERVIEW",
            "UNDERSTANDING",
            SemanticViewerBlock(
                (
                    ("class:section", "\n WHAT MEM UNDERSTOOD\n"),
                    ("class:viewer-body", f" {safe_terminal_text(analysis.overview)}\n"),
                ),
                focus_indices=(0, 1),
            ),
        ),
    ]
    for index, rule in enumerate(analysis.rules):
        sections.append(
            SemanticViewerSection(
                f"ELABORATE:RULE:{index}",
                "RULE",
                SemanticViewerBlock(
                    (
                        ("class:section", f"\n RULE {index + 1} · [Suggested] [Unverified]\n"),
                        ("class:memory-object", f" {safe_terminal_text(rule.content)}\n"),
                        ("class:viewer-body", f" WHY · {safe_terminal_text(rule.rationale)}\n"),
                    ),
                    anchor="end",
                    focus_indices=(0, 1, 2),
                ),
            )
        )
    for index, case in enumerate(analysis.cases):
        sections.append(
            SemanticViewerSection(
                f"ELABORATE:CASE:{index}",
                "CASE",
                SemanticViewerBlock(
                    (
                        (
                            "class:section",
                            f"\n CASE {index + 1} · {case.case_role} · "
                            "[Suggested] [Unverified]\n",
                        ),
                        ("class:memory-object", f" {safe_terminal_text(case.proposition)}\n"),
                        (
                            "class:viewer-body",
                            f" RULE COVERAGE · ALL {len(case.rule_checks)}\n",
                        ),
                        *(
                            (
                                "class:viewer-body",
                                " RULE "
                                f"{check.source_rule_index} · "
                                f"{safe_terminal_text(check.evidence)}\n",
                            )
                            for check in case.rule_checks
                        ),
                        ("class:viewer-body", f" EXPECTED · {safe_terminal_text(case.expected or '(open)')}\n"),
                        ("class:viewer-body", f" WHY · {safe_terminal_text(case.rationale)}\n"),
                    ),
                    anchor="end",
                    focus_indices=tuple(range(5 + len(case.rule_checks))),
                ),
            )
        )
    return SemanticViewerDocument(tuple(sections))
