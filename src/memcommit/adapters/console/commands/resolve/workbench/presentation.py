"""Resolve projection into the shared Resolution workbench and Viewer."""

from __future__ import annotations

from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.terminal.components.command_editor.exact_command_review import (
    CommandReview,
)
from memcommit.adapters.console.terminal.components.semantic_viewer import (
    SemanticViewerBlock,
    SemanticViewerDocument,
    SemanticViewerSection,
)
from memcommit.application.operations.resolve.application import (
    ResolveAnalysis,
    ResolveCandidate,
)
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionItem,
    ResolutionOption,
    ResolutionWorkbenchView,
)


def _effect_fragments(candidate: ResolveCandidate) -> list[tuple[str, str]]:
    fragments: list[tuple[str, str]] = []
    for effect in candidate.effects:
        style = (
            "class:impact.add"
            if effect.kind == "CREATE"
            else "class:impact.remove"
            if effect.kind == "DELETE"
            else "class:impact.edit"
        )
        fragments.extend(
            [
                (
                    style,
                    f"{effect.kind} · [{safe_terminal_text(effect.memory_uid[:8])}]\n",
                ),
                (
                    "class:memory-object",
                    (
                        "BEFORE · " + safe_terminal_text(effect.old_content) + "\n"
                        if effect.old_content is not None
                        else ""
                    )
                    + (
                        "AFTER · " + safe_terminal_text(effect.new_content) + "\n"
                        if effect.new_content is not None
                        else ""
                    ),
                ),
                (
                    "class:viewer-body",
                    "WHY · " + safe_terminal_text(effect.reason) + "\n"
                    "SOURCES · "
                    + ", ".join(uid[:8] for uid in effect.source_memory_uids)
                    + "\n\n",
                ),
            ]
        )
    return fragments


def _issue_fragments(candidate: ResolveCandidate) -> list[tuple[str, str]]:
    fragments: list[tuple[str, str]] = []
    for issue in candidate.issues:
        fragments.extend(
            [
                (
                    "class:section",
                    "ISSUE · "
                    + safe_terminal_text(issue.uid)
                    + " · "
                    + safe_terminal_text(issue.kind)
                    + "\n",
                ),
                (
                    "class:viewer-body",
                    "MEMBERS · "
                    + ", ".join(uid[:8] for uid in issue.memory_uids)
                    + "\nINTERPRETATION · "
                    + safe_terminal_text(issue.selected_interpretation)
                    + "\nBASIS · "
                    + ", ".join(uid[:8] for uid in issue.basis_memory_uids)
                    + "\n"
                    + "".join(
                        "ASSUMPTION · " + safe_terminal_text(value) + "\n"
                        for value in issue.assumptions
                    )
                    + "WHY · "
                    + safe_terminal_text(issue.reason)
                    + "\n\n",
                ),
            ]
        )
    return fragments


def project_resolve_analysis(analysis: ResolveAnalysis) -> SemanticViewerDocument:
    """Build one complete read-only report used before and without Apply."""

    fragments: list[tuple[str, str]] = [
        ("class:title", "RESOLVE · FIT REPAIR\n"),
        (
            "class:report-label",
            f"CONTEXT · {safe_terminal_text(analysis.frame.display_name)}\n"
            f"REVISION · {safe_terminal_text(analysis.frame.revision)}\n"
            f"STATUS · {safe_terminal_text(analysis.status)}\n"
            f"TARGET FIT · {safe_terminal_text(analysis.frame.request.target_fit)}\n"
            "REQUESTED · "
            + ", ".join(analysis.frame.request.requested_effects)
            + "\nALLOWED · "
            + (", ".join(analysis.frame.allowed_effects) or "NONE")
            + "\n",
        ),
    ]
    if analysis.frame.denied_effects:
        fragments.append(
            (
                "class:impact.custom",
                "DENIED · " + ", ".join(analysis.frame.denied_effects) + "\n",
            )
        )
    if analysis.initial_fit is not None:
        fragments.append(
            (
                "class:viewer-body",
                f"\nINITIAL FIT · {analysis.initial_fit.verdict}\n"
                + safe_terminal_text(analysis.initial_fit.reason)
                + "\n",
            )
        )
    if analysis.question:
        fragments.append(
            (
                "class:viewer-body",
                "\nQUESTION · " + safe_terminal_text(analysis.question) + "\n",
            )
        )
    for index, candidate in enumerate(analysis.candidates, 1):
        fragments.extend(
            [
                (
                    "class:section",
                    f"\nAUTOMATIC PLAN {index} · {safe_terminal_text(candidate.uid)}\n",
                ),
                (
                    "class:viewer-body",
                    safe_terminal_text(candidate.summary)
                    + "\nCLASSIFICATION · "
                    + safe_terminal_text(candidate.classification)
                    + "\nRESOLUTION · "
                    + candidate.resolution_level
                    + "\nRULES · "
                    + safe_terminal_text(", ".join(candidate.rule_ids))
                    + "\nGROUNDING · "
                    + ("GROUNDED" if candidate.grounded else "ASSUMED")
                    + "\nCOST · "
                    f"DELETE {candidate.cost.deletes} · "
                    f"CREATE {candidate.cost.creates} · "
                    f"UPDATE {candidate.cost.updates} · "
                    f"CHANGED UNITS {candidate.cost.changed_units}\n\n",
                ),
                *_issue_fragments(candidate),
                *_effect_fragments(candidate),
                (
                    "class:impact.keep"
                    if candidate.grounded
                    else "class:impact.custom",
                    (
                        "GROUNDING VERIFIED · "
                        if candidate.grounded
                        else "WORKING VIEW · "
                    )
                    + safe_terminal_text(candidate.verification_reason)
                    + f"\nFIT {candidate.fit.verdict} · "
                    + safe_terminal_text(candidate.fit.reason)
                    + "\n",
                ),
            ]
        )
    return SemanticViewerDocument(
        (
            SemanticViewerSection(
                uid="resolve-report",
                kind="REPORT",
                block=SemanticViewerBlock(tuple(fragments), anchor="both"),
            ),
        )
    )


def _candidate_argv(
    analysis: ResolveAnalysis,
    candidate: ResolveCandidate,
) -> tuple[str, ...]:
    argv = ["mem", "resolve"]
    if analysis.frame.request.memory_selectors:
        argv.extend(analysis.frame.actionable_uids)
    argv.extend(("--context", analysis.frame.display_name))
    if not analysis.frame.request.allow_create:
        argv.append("--no-create")
    if analysis.frame.request.allow_delete:
        argv.append("--allow-delete")
    if analysis.frame.request.guidance:
        argv.extend(("--guidance", analysis.frame.request.guidance))
    argv.extend(
        (
            "--candidate",
            candidate.uid,
            "--expected-revision",
            analysis.frame.revision,
            "--apply",
        )
    )
    return tuple(argv)


def resolve_candidate_exact_review(
    analysis: ResolveAnalysis,
    candidate: ResolveCandidate,
) -> CommandReview:
    """Describe the exact candidate hash, effects, and recovery boundary."""

    effect_lines = tuple(
        (
            f"{effect.kind} [{effect.memory_uid}] · "
            + (
                f"{effect.old_content!r} -> {effect.new_content!r}"
                if effect.kind == "UPDATE"
                else f"create {effect.new_content!r}"
                if effect.kind == "CREATE"
                else f"delete {effect.old_content!r}"
            )
        )
        for effect in candidate.effects
    )
    return CommandReview(
        argv=_candidate_argv(analysis, candidate),
        effects=(
            f"Context revision · {analysis.frame.revision}.",
            "Apply will stop if the Context has changed.",
            f"Verified automatic plan · {candidate.uid}.",
            *effect_lines,
            "The proposed result independently Fits as YES.",
            "Apply creates one checkpoint; recovery is mem undo.",
        ),
    )


def compact_resolve_view(analysis: ResolveAnalysis) -> ResolutionWorkbenchView:
    """Project the one verified repair into the shared execution decision shell."""

    candidate = analysis.candidates[0]
    effects = " · ".join(
        f"{kind} {sum(effect.kind == kind for effect in candidate.effects)}"
        for kind in ("CREATE", "UPDATE", "DELETE")
        if any(effect.kind == kind for effect in candidate.effects)
    )
    return ResolutionWorkbenchView(
        operation="RESOLVE",
        artifact_uid=analysis.frame.context_uid,
        revision=analysis.frame.revision,
        title="Verified Fit repair",
        route=analysis.frame.display_name,
        status="READY TO APPLY",
        metrics=(),
        overview="",
        list_label="VERIFIED PLAN",
        items=(
            ResolutionItem(
                uid="resolve-plan",
                kind="VERIFIED PLAN",
                status="ANSWERED",
                priority="REQUIRED",
                title=f"Fit repair for {analysis.frame.display_name}",
                summary=candidate.summary,
                obligation="REQUIRED",
                response_state="ANSWERED",
                options=(
                    ResolutionOption(
                        candidate.uid,
                        "Verified automatic plan",
                        f"{candidate.summary} · {effects}",
                    ),
                ),
                selected_option_uid=candidate.uid,
            ),
        ),
        empty_message="No verified repair is available.",
        results_label="EFFECTS",
        results=(),
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=True,
        show_results=False,
    )


__all__ = [
    "compact_resolve_view",
    "project_resolve_analysis",
    "resolve_candidate_exact_review",
]
