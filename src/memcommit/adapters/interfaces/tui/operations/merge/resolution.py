"""Merge projection into the shared deterministic Resolution workbench."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.adapters.interfaces.console.text import safe_terminal_text
from memcommit.adapters.interfaces.tui.components.exact_command_review import (
    ExactCommandReview,
)
from memcommit.adapters.interfaces.tui.components.plain_text_clipboard import ClipboardWriter
from memcommit.adapters.interfaces.tui.operations.merge.screen import (
    merge_plan_exact_command_review,
    project_merge_plan,
)
from memcommit.adapters.interfaces.tui.viewers.semantic import (
    SemanticViewerBlock,
    SemanticViewerDocument,
    SemanticViewerSection,
)
from memcommit.adapters.interfaces.tui.workbenches.resolution import (
    ResolutionBulkStrategy,
    ResolutionChoice,
    ResolutionInlineChoice,
    ResolutionItem,
    ResolutionOutcome,
    ResolutionWorkbenchSpec,
    run_resolution_workbench,
)
from memcommit.application.reviewing.memory_diff import MemoryChange, memory_diff_lines
from memcommit.application.operations.merge.application import (
    FrozenMergePlan,
    MergeConflict,
    MergeDecision,
    MergeItemKind,
    MergeReach,
    MergeResolution,
    MergeResult,
    merge_resolution_case,
)


def _conflict_detail(conflict: MergeConflict) -> SemanticViewerDocument:
    fragments: list[tuple[str, str]] = [
        (
            "class:title",
            f"MERGE CONFLICT · {safe_terminal_text(conflict.kind.value)}\n",
        ),
        (
            "class:report-label",
            f"ID · {safe_terminal_text(conflict.uid)}\n"
            f"MAPPING · {safe_terminal_text(conflict.source_name)} → "
            f"{safe_terminal_text(conflict.target_name)}\n",
        ),
        ("class:viewer-body", f"WHY · {safe_terminal_text(conflict.reason)}\n\n"),
        ("class:report-label", "TARGET\n"),
    ]
    for target in conflict.targets:
        fragments.append(
            (
                "class:memory-object"
                if target.content is not None
                else "class:viewer-body",
                f"  {safe_terminal_text(target.description)}\n"
                + (
                    f"  {safe_terminal_text(target.content)}\n"
                    if target.content is not None
                    else ""
                ),
            )
        )
    fragments.extend(
        [
            ("class:report-label", "\nSOURCE\n"),
            (
                "class:memory-object"
                if conflict.source.content is not None
                else "class:viewer-body",
                f"  {safe_terminal_text(conflict.source.description)}\n"
                + (
                    f"  {safe_terminal_text(conflict.source.content)}\n"
                    if conflict.source.content is not None
                    else ""
                ),
            ),
        ]
    )
    if (
        conflict.source.content is not None
        and len(conflict.targets) == 1
        and conflict.targets[0].content is not None
    ):
        fragments.append(("class:report-label", "\nDETERMINISTIC DIFF\n"))
        change = MemoryChange(
            marker="~",
            treatment="TAKE SOURCE",
            location=conflict.target_name,
            memory_uid=conflict.source.uid,
            before=conflict.targets[0].content,
            after=conflict.source.content,
        )
        for line in memory_diff_lines(change):
            style = (
                "class:impact.remove"
                if line.marker == "-"
                else "class:impact.add"
                if line.marker == "+"
                else "class:viewer-body"
            )
            fragments.append(
                (
                    style,
                    line.marker
                    + " "
                    + "".join(span.text for span in line.spans)
                    + "\n",
                )
            )
    return SemanticViewerDocument(
        (
            SemanticViewerSection(
                uid=conflict.uid,
                kind="CONFLICT",
                block=SemanticViewerBlock(tuple(fragments), anchor="both"),
            ),
        )
    )


def _argv_for(plan: FrozenMergePlan, outcome: ResolutionOutcome) -> tuple[str, ...]:
    argv = [
        "mem",
        "merge",
        plan.source_name,
        plan.target_name,
        "--recursive" if plan.request.reach is MergeReach.DESCENDANTS else "--direct",
    ]
    if outcome.bulk_uid == MergeDecision.KEEP_TARGET.value:
        argv.append("--keep-target-all")
    elif outcome.bulk_uid == MergeDecision.TAKE_SOURCE.value:
        argv.append("--take-source-all")
    else:
        for conflict_uid, choice_uid in outcome.decisions:
            argv.extend(
                (
                    "--resolve",
                    f"{conflict_uid}={choice_uid.lower().replace('_', '-')}",
                )
            )
    return tuple(argv)


def merge_resolution_exact_review(
    plan: FrozenMergePlan,
    outcome: ResolutionOutcome,
) -> ExactCommandReview:
    """Bind the exact frozen conflict decisions to one reviewed command."""

    take_count = sum(
        choice_uid == MergeDecision.TAKE_SOURCE.value
        for _item_uid, choice_uid in outcome.decisions
    )
    keep_count = len(outcome.decisions) - take_count
    base = merge_plan_exact_command_review(plan)
    return ExactCommandReview(
        argv=_argv_for(plan, outcome),
        effects=(
            *base.effects,
            f"Required decisions · KEEP TARGET {keep_count} · TAKE SOURCE {take_count}.",
            "Existing Target-only items remain; no custom or semantic rewrite is allowed.",
            "Recovery is one operation-level mem undo, including created descendants.",
        ),
    )


def merge_resolution_spec(plan: FrozenMergePlan) -> ResolutionWorkbenchSpec:
    """Project a conflict-bearing frozen plan without live Context objects."""

    if not plan.conflicts:
        raise ValueError("Merge Resolution requires at least one conflict.")
    case = merge_resolution_case(plan)
    all_choices = (
        ResolutionChoice(
            MergeDecision.KEEP_TARGET.value,
            "KEEP TARGET",
            "Retain the conflicting Target item or placement.",
        ),
        ResolutionChoice(
            MergeDecision.TAKE_SOURCE.value,
            "TAKE SOURCE",
            "Replace the conflicting Target member(s) with the exact Source item.",
        ),
    )
    def visible_value(conflict: MergeConflict, *, source: bool) -> tuple[str, bool]:
        snapshots = (conflict.source,) if source else conflict.targets
        if len(snapshots) == 1:
            snapshot = snapshots[0]
            return (
                snapshot.content
                if snapshot.content is not None
                else snapshot.description,
                snapshot.kind is MergeItemKind.MEMORY,
            )
        return (
            "\n\n".join(
                snapshot.description
                + (f"\n{snapshot.content}" if snapshot.content is not None else "")
                for snapshot in snapshots
            ),
            False,
        )

    items = []
    for conflict in plan.conflicts:
        legal = case.requirement(conflict.uid).choice_uids
        source_content, source_is_memory = visible_value(conflict, source=True)
        target_content, target_is_memory = visible_value(conflict, source=False)
        items.append(
            ResolutionItem(
                uid=conflict.uid,
                label=f"[{conflict.source.uid[:8]}]",
                classification=conflict.kind.value,
                detail=_conflict_detail(conflict),
                choices=tuple(choice for choice in all_choices if choice.uid in legal),
                inline_choices=(
                    ResolutionInlineChoice(
                        MergeDecision.TAKE_SOURCE.value,
                        "SOURCE",
                        source_content,
                        selectable=MergeDecision.TAKE_SOURCE.value in legal,
                        memory_content=source_is_memory,
                    ),
                    ResolutionInlineChoice(
                        MergeDecision.KEEP_TARGET.value,
                        "TARGET",
                        target_content,
                        selectable=True,
                        memory_content=target_is_memory,
                    ),
                ),
                default_choice_uid=MergeDecision.KEEP_TARGET.value,
            )
        )
    items = tuple(items)
    keep_outcome = ResolutionOutcome(
        tuple(
            (conflict.uid, MergeDecision.KEEP_TARGET.value)
            for conflict in plan.conflicts
        ),
        bulk_uid=MergeDecision.KEEP_TARGET.value,
    )
    take_outcome = ResolutionOutcome(
        tuple(
            (conflict.uid, MergeDecision.TAKE_SOURCE.value)
            for conflict in plan.conflicts
        ),
        bulk_uid=MergeDecision.TAKE_SOURCE.value,
    )
    return ResolutionWorkbenchSpec(
        case=case,
        title=(
            f"MERGE REVIEW · {len(plan.conflicts)} "
            f"{'conflict' if len(plan.conflicts) == 1 else 'conflicts'}"
        ),
        subtitle="CHOOSE EACH",
        report=project_merge_plan(plan),
        items=items,
        exact_review=merge_resolution_exact_review(plan, keep_outcome),
        bulk_strategies=(
            ResolutionBulkStrategy(
                key="k",
                choice_uid=MergeDecision.KEEP_TARGET.value,
                label="KEEP ALL TARGET",
                review=merge_resolution_exact_review(plan, keep_outcome),
            ),
            *(
                (
                    ResolutionBulkStrategy(
                        key="s",
                        choice_uid=MergeDecision.TAKE_SOURCE.value,
                        label="TAKE ALL SOURCE",
                        review=merge_resolution_exact_review(plan, take_outcome),
                    ),
                )
                if all(
                    MergeDecision.TAKE_SOURCE.value in requirement.choice_uids
                    for requirement in case.requirements
                )
                else ()
            ),
        ),
        show_viewer=False,
        inline_choice_layout=True,
        responses_title="DECISION · REQUIRED · DETERMINISTIC ONLY",
        items_title="CONFLICTS · REQUIRED DECISIONS",
    )


def _outcome_resolutions(outcome: ResolutionOutcome) -> tuple[MergeResolution, ...]:
    return tuple(
        MergeResolution(
            conflict_uid=conflict_uid,
            decision=MergeDecision(choice_uid),
        )
        for conflict_uid, choice_uid in outcome.decisions
    )


def _receipt(result: MergeResult) -> str:
    created = sum(context.target_created for context in result.contexts)
    take_count = sum(
        resolution.decision is MergeDecision.TAKE_SOURCE
        for resolution in result.resolutions
    )
    keep_count = len(result.resolutions) - take_count
    target_changed = bool(result.additions or take_count or created)
    return (
        f"SOURCE · {result.source_name}\n"
        f"TARGET · {result.target_name}\n"
        f"RANGE · {result.reach.value}\n"
        f"CONTEXTS · {len(result.contexts)} · CREATED {created}\n"
        f"NEW · {len(result.additions)}\n"
        f"ALREADY PRESENT · {len(result.unchanged)}\n"
        f"KEPT TARGET · {keep_count}\n"
        f"TOOK SOURCE · {take_count}\n"
        f"TARGET CHANGED · {'YES' if target_changed else 'NO'}\n"
        f"CHECKPOINTS · {len(result.checkpoint_uids)} · RECOVERY · mem undo"
    )


def run_merge_conflict_review(
    plan: FrozenMergePlan,
    *,
    apply_plan: Callable[[FrozenMergePlan, tuple[MergeResolution, ...]], MergeResult],
    clipboard_writer: ClipboardWriter | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> MergeResult | None:
    """Resolve and apply one conflict-bearing Merge through the shared shell."""

    return run_resolution_workbench(
        merge_resolution_spec(plan),
        apply_outcome=lambda outcome: apply_plan(
            plan,
            _outcome_resolutions(outcome),
        ),
        receipt_text=_receipt,
        review_outcome=lambda outcome: merge_resolution_exact_review(plan, outcome),
        clipboard_writer=clipboard_writer,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
