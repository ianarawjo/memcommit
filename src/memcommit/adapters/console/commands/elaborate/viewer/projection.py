"""Project Elaborate proposals into shared semantic Viewer mechanics."""

from __future__ import annotations

from memcommit.application.operations.elaborate.model import ElaborateMode
from memcommit.application.operations.elaborate.application import ElaborateResult
from memcommit.adapters.console.commands.elaborate.proposal import elaborate_result_text
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.commands.elaborate.viewer.model import (
    ElaborateClipboardProjection,
)
from memcommit.adapters.console.terminal.components.semantic_viewer import (
    SemanticViewerBlock,
    SemanticViewerDocument,
    SemanticViewerSection,
)


def _proposal_text(result: ElaborateResult, kind: str, index: int) -> str:
    if kind == "RULE":
        rule = result.analysis.rules[index]
        lines = [
                f"[Suggested] [Unverified] {rule.content}",
                f"WHY · {rule.rationale}",
            ]
        if result.analysis.target_context is not None:
            lines.append(
                "TARGET USED · "
                + (", ".join(rule.target_context_refs) or "NONE")
            )
        return "\n".join(lines)
    case = result.analysis.cases[index]
    lines = [
            f"[{case.case_role}] [Suggested] [Unverified] {case.proposition}",
            f"RULE COVERAGE · ALL {len(case.rule_checks)}",
            *(
                f"RULE {check.source_rule_index} · {check.evidence}"
                for check in case.rule_checks
            ),
            f"EXPECTED · {case.expected or '(open)'}",
            f"WHY · {case.rationale}",
        ]
    if result.analysis.target_context is not None:
        lines.append(
            "TARGET USED · "
            + (", ".join(case.target_context_refs) or "NONE")
        )
    return "\n".join(lines)


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
            "PROPOSAL OVERVIEW\n" + result.analysis.overview,
            "Elaborate proposal overview",
        )
    if focused_uid == "ELABORATE:TARGET" and result.analysis.target_context is not None:
        target = result.analysis.target_context
        lines = [f"TARGET AMBIENT · {target.context_name} · {len(target.items)} ITEMS"]
        for item in target.items:
            if item.kind == "MEMORY":
                lines.extend(
                    (
                        f"{item.alias} · MEMORY · {item.context_name}",
                        item.content or "",
                    )
                )
            else:
                lines.append(
                    f"{item.alias} · QUERY ONLY · {item.context_name} · NAME ONLY"
                )
        return ElaborateClipboardProjection(
            "\n".join(lines),
            "Elaborate Target ambient context",
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
            "PROPOSAL OVERVIEW",
            SemanticViewerBlock(
                (
                    ("class:section", "\n PROPOSAL OVERVIEW\n"),
                    ("class:viewer-body", f" {safe_terminal_text(analysis.overview)}\n"),
                ),
                focus_indices=(0, 1),
            ),
        ),
    ]
    if analysis.target_context is not None:
        target_fragments: list[tuple[str, str]] = [
            (
                "class:section",
                "\n TARGET AMBIENT · "
                f"{safe_terminal_text(analysis.target_context.context_name)} · "
                f"{len(analysis.target_context.items)} ITEMS\n",
            )
        ]
        for item in analysis.target_context.items:
            if item.kind == "MEMORY":
                target_fragments.extend(
                    (
                        (
                            "class:viewer-body",
                            f" {item.alias} · MEMORY · "
                            f"{safe_terminal_text(item.context_name)}\n",
                        ),
                        (
                            "class:memory-object",
                            f" {safe_terminal_text(item.content or '')}\n",
                        ),
                    )
                )
            else:
                target_fragments.append(
                    (
                        "class:viewer-body",
                        f" {item.alias} · QUERY ONLY · "
                        f"{safe_terminal_text(item.context_name)} · NAME ONLY\n",
                    )
                )
        sections.append(
            SemanticViewerSection(
                "ELABORATE:TARGET",
                "TARGET AMBIENT",
                SemanticViewerBlock(
                    tuple(target_fragments),
                    focus_indices=tuple(range(len(target_fragments))),
                ),
            )
        )
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
                        *(
                            (
                                (
                                    "class:viewer-body",
                                    " TARGET USED · "
                                    + (", ".join(rule.target_context_refs) or "NONE")
                                    + "\n",
                                ),
                            )
                            if analysis.target_context is not None
                            else ()
                        ),
                    ),
                    anchor="end",
                    focus_indices=tuple(
                        range(3 + (analysis.target_context is not None))
                    ),
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
                        *(
                            (
                                (
                                    "class:viewer-body",
                                    " TARGET USED · "
                                    + (", ".join(case.target_context_refs) or "NONE")
                                    + "\n",
                                ),
                            )
                            if analysis.target_context is not None
                            else ()
                        ),
                    ),
                    anchor="end",
                    focus_indices=tuple(
                        range(
                            5
                            + len(case.rule_checks)
                            + (analysis.target_context is not None)
                        )
                    ),
                ),
            )
        )
    return SemanticViewerDocument(tuple(sections))
