"""Resolve projection into the shared Resolution workbench and Viewer."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.interfaces.tui.components.exact_command_review import (
    ExactCommandReview,
)
from memcommit.interfaces.tui.components.plain_text_clipboard import ClipboardWriter
from memcommit.interfaces.tui.viewers.semantic import (
    SemanticViewerBlock,
    SemanticViewerDocument,
    SemanticViewerSection,
    run_semantic_viewer,
)
from memcommit.interfaces.tui.workbenches.resolution import (
    ResolutionChoice,
    ResolutionItem,
    ResolutionOutcome,
    ResolutionWorkbenchSpec,
    run_resolution_workbench,
)
from memcommit.resolve_application import (
    ResolveAnalysis,
    ResolveCandidate,
    ResolveReceipt,
    resolve_case,
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


def project_resolve_analysis(analysis: ResolveAnalysis) -> SemanticViewerDocument:
    """Build one complete read-only report used before and without Apply."""

    fragments: list[tuple[str, str]] = [
        ("class:title", "RESOLVE · FIT REPAIR\n"),
        (
            "class:report-label",
            f"CONTEXT · {safe_terminal_text(analysis.frame.display_name)}\n"
            f"REVISION · {safe_terminal_text(analysis.frame.revision)}\n"
            f"STATUS · {safe_terminal_text(analysis.status)}\n"
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
                    f"\nCANDIDATE {index} · {safe_terminal_text(candidate.uid)}\n",
                ),
                (
                    "class:viewer-body",
                    safe_terminal_text(candidate.summary)
                    + "\nCOST · "
                    f"DELETE {candidate.cost.deletes} · "
                    f"CREATE {candidate.cost.creates} · "
                    f"UPDATE {candidate.cost.updates} · "
                    f"CHANGED UNITS {candidate.cost.changed_units}\n\n",
                ),
                *_effect_fragments(candidate),
                (
                    "class:impact.keep",
                    "GROUNDING VERIFIED · "
                    + safe_terminal_text(candidate.verification_reason)
                    + "\nFIT YES · "
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


def _candidate_detail(candidate: ResolveCandidate) -> SemanticViewerDocument:
    fragments: list[tuple[str, str]] = [
        ("class:title", "VERIFIED RESOLVE CANDIDATE\n"),
        ("class:report-label", safe_terminal_text(candidate.uid) + "\n"),
        ("class:viewer-body", safe_terminal_text(candidate.summary) + "\n\n"),
        *_effect_fragments(candidate),
        (
            "class:impact.keep",
            "GROUNDING VERIFIED · "
            + safe_terminal_text(candidate.verification_reason)
            + "\nFIT YES · "
            + safe_terminal_text(candidate.fit.reason)
            + "\n",
        ),
    ]
    return SemanticViewerDocument(
        (
            SemanticViewerSection(
                uid=candidate.uid,
                kind="CANDIDATE",
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
    if analysis.frame.request.allow_create:
        argv.append("--allow-create")
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
) -> ExactCommandReview:
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
    return ExactCommandReview(
        argv=_candidate_argv(analysis, candidate),
        effects=(
            f"Frozen Context revision · {analysis.frame.revision}.",
            f"Verified candidate · {candidate.uid}.",
            *effect_lines,
            "The complete post-image independently Fits as YES.",
            "Apply creates one checkpoint; recovery is mem undo.",
        ),
    )


def _spec(analysis: ResolveAnalysis) -> ResolutionWorkbenchSpec:
    if not analysis.candidates:
        raise ValueError("Resolve workbench requires verified candidates.")
    first = analysis.candidates[0]
    return ResolutionWorkbenchSpec(
        case=resolve_case(analysis),
        title="MEM RESOLVE · RESOLUTION SESSION",
        subtitle="SEMANTIC CANDIDATES · INDEPENDENTLY VERIFIED · EXACT APPLY",
        report=project_resolve_analysis(analysis),
        items=(
            ResolutionItem(
                uid="resolve-plan",
                label="Choose one verified minimum-change post-image.",
                classification="FIT REPAIR",
                detail=SemanticViewerDocument(
                    tuple(
                        section
                        for candidate in analysis.candidates
                        for section in _candidate_detail(candidate).sections
                    )
                ),
                choices=tuple(
                    ResolutionChoice(
                        candidate.uid,
                        f"CANDIDATE {index}",
                        candidate.summary,
                    )
                    for index, candidate in enumerate(analysis.candidates, 1)
                ),
            ),
        ),
        exact_review=resolve_candidate_exact_review(analysis, first),
        detail_title="VIEWER · VERIFIED CANDIDATE DETAILS",
        responses_title="RESPONSES · REQUIRED · VERIFIED CANDIDATES",
        items_title="ITEMS · REQUIRED RESOLVE PLAN",
    )


def _selected_candidate(
    analysis: ResolveAnalysis,
    outcome: ResolutionOutcome,
) -> ResolveCandidate:
    if outcome.decisions[0][0] != "resolve-plan":
        raise ValueError("Resolve workbench returned an unknown item.")
    selected_uid = outcome.decisions[0][1]
    return next(
        candidate for candidate in analysis.candidates if candidate.uid == selected_uid
    )


def _receipt(receipt: ResolveReceipt) -> str:
    return (
        f"CONTEXT · {receipt.context_name}\n"
        f"CANDIDATE · {receipt.candidate_uid}\n"
        f"CREATED · {len(receipt.created_uids)}\n"
        f"UPDATED · {len(receipt.updated_uids)}\n"
        f"DELETED · {len(receipt.deleted_uids)}\n"
        f"CHECKPOINT · {receipt.checkpoint_uid}\n"
        "RECOVERY · mem undo"
    )


def run_resolve_tui(
    analysis: ResolveAnalysis,
    *,
    apply_candidate: Callable[[str], ResolveReceipt],
    clipboard_writer: ClipboardWriter | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> ResolveReceipt | None:
    """Inspect terminal outcomes or choose and apply one verified candidate."""

    if not isinstance(analysis, ResolveAnalysis):
        raise TypeError("Resolve TUI requires a typed analysis.")
    if not analysis.candidates:
        run_semantic_viewer(
            project_resolve_analysis(analysis),
            title="RESOLVE · READ-ONLY OUTCOME",
            clipboard_writer=clipboard_writer,
            app_input=app_input,
            app_output=app_output,
            require_tty=require_tty,
        )
        return None
    return run_resolution_workbench(
        _spec(analysis),
        apply_outcome=lambda outcome: apply_candidate(
            _selected_candidate(analysis, outcome).uid
        ),
        receipt_text=_receipt,
        review_outcome=lambda outcome: resolve_candidate_exact_review(
            analysis,
            _selected_candidate(analysis, outcome),
        ),
        clipboard_writer=clipboard_writer,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )


__all__ = [
    "project_resolve_analysis",
    "resolve_candidate_exact_review",
    "run_resolve_tui",
]
