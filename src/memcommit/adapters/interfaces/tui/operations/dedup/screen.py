"""Semantic Dedun projection into the common Resolution shell."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.application.operations.dedup.application import (
    DedupComponent,
    DedupReceipt,
    DedupSelection,
    FrozenDedupPlan,
    dedup_resolution_case,
)
from memcommit.adapters.console.text import safe_terminal_text
from memcommit.adapters.interfaces.tui.components.exact_command_review import (
    ExactCommandReview,
)
from memcommit.adapters.interfaces.tui.components.plain_text_clipboard import ClipboardWriter
from memcommit.adapters.interfaces.tui.viewers.semantic import (
    SemanticViewerBlock,
    SemanticViewerDocument,
    SemanticViewerSection,
)
from memcommit.adapters.interfaces.tui.workbenches.resolution import (
    ResolutionChoice,
    ResolutionItem,
    ResolutionOutcome,
    ResolutionWorkbenchSpec,
    run_resolution_workbench,
)
from memcommit.application.semantic.redundancy_evidence import (
    redundancy_evidence_json,
)


def _component_detail(component: DedupComponent) -> SemanticViewerDocument:
    fragments: list[tuple[str, str]] = [
        ("class:title", "REDUNDANCY GROUP · EXISTING SURVIVOR ONLY\n"),
        ("class:report-label", f"ID · {safe_terminal_text(component.uid)}\n"),
        (
            "class:viewer-body",
            "Choose one existing UID. Its wording stays unchanged; every other "
            "member UID is absorbed.\n\n",
        ),
        ("class:report-label", "MEMBERS\n"),
    ]
    for member in component.members:
        recommended = member.uid == component.recommended_survivor_uid
        fragments.extend(
            [
                (
                    "class:impact.add" if recommended else "class:report-label",
                    f"  {'RECOMMENDED · ' if recommended else ''}"
                    f"#{member.ordinal} · [{safe_terminal_text(member.uid)}]\n",
                ),
                (
                    "class:memory-object",
                    f"  {safe_terminal_text(member.content)}\n",
                ),
            ]
        )
    fragments.append(("class:report-label", "\nCONFIRMED EVIDENCE\n"))
    for evidence in component.evidence:
        fragments.extend(
            [
                (
                    "class:viewer-body",
                    f"  {safe_terminal_text(evidence.relation)} · "
                    f"[{safe_terminal_text(evidence.left_uid[:8])}] ↔ "
                    f"[{safe_terminal_text(evidence.right_uid[:8])}]\n",
                ),
                (
                    "class:viewer-body",
                    f"  WHY · {safe_terminal_text(evidence.reason)}\n",
                ),
            ]
        )
    return SemanticViewerDocument(
        (
            SemanticViewerSection(
                uid=component.uid,
                kind="COMPONENT",
                block=SemanticViewerBlock(tuple(fragments), anchor="both"),
            ),
        )
    )


def _component_compact_context(component: DedupComponent) -> str:
    """Keep the decision evidence adjacent without opening a separate Viewer."""

    lines = ["MEMBERS"]
    for member in component.members:
        lines.append(
            f"  #{member.ordinal} · [{safe_terminal_text(member.uid[:8])}] "
            f"{safe_terminal_text(member.content)}"
        )
    lines.append("CONFIRMED EVIDENCE")
    for evidence in component.evidence:
        lines.append(
            f"  {safe_terminal_text(evidence.relation)} · "
            f"[{safe_terminal_text(evidence.left_uid[:8])}] ↔ "
            f"[{safe_terminal_text(evidence.right_uid[:8])}] · "
            f"{safe_terminal_text(evidence.reason)}"
        )
    return "\n".join(lines)


def project_dedup_plan(plan: FrozenDedupPlan) -> SemanticViewerDocument:
    fragments: list[tuple[str, str]] = [
        ("class:title", "DEDUN · CONFIRMED REDUNDANCIES\n"),
        (
            "class:report-label",
            f"CONTEXT · {safe_terminal_text(plan.display_name)}\n"
            f"REVISION · {safe_terminal_text(plan.revision)}\n"
            "COMPONENTS · "
            f"{len(plan.components) + len(plan.exact_item_groups)}\n",
        ),
        (
            "class:viewer-body",
            "\nDETERMINISTIC BOUNDARY\n"
            "DUN includes same-role exact direct items plus Memory "
            "SURFACE_EQUIVALENT and SEMANTIC_EQUIVALENT evidence. Cross-role "
            "items never merge.\n",
        ),
    ]
    for index, component in enumerate(plan.components, 1):
        fragments.extend(
            [
                (
                    "class:section",
                    f"\nCOMPONENT {index} · {len(component.members)} MEMBERS\n",
                ),
                (
                    "class:impact.add",
                    "RECOMMENDED SURVIVOR · "
                    f"[{safe_terminal_text(component.recommended_survivor_uid)}]\n",
                ),
                (
                    "class:viewer-body",
                    f"CONFIRMED LINKS · {len(component.evidence)}\n",
                ),
            ]
        )
    for offset, group in enumerate(plan.exact_item_groups, 1):
        index = len(plan.components) + offset
        fragments.extend(
            [
                (
                    "class:section",
                    f"\nCOMPONENT {index} · {group.item_kind} · "
                    f"{1 + len(group.absorbed_uids)} MEMBERS\n",
                ),
                (
                    "class:impact.add",
                    "DETERMINISTIC SURVIVOR · "
                    f"[{safe_terminal_text(group.survivor_uid)}]\n",
                ),
                (
                    "class:viewer-body",
                    f"EXACT IDENTITY · {safe_terminal_text(group.summary)}\n",
                ),
            ]
        )
    fragments.append(
        (
            "class:impact.remove",
            "\nAPPLY · one checkpoint · inbound References to absorbed Memory UIDs "
            "block the complete operation.\n",
        )
    )
    return SemanticViewerDocument(
        (
            SemanticViewerSection(
                uid="dedup-report",
                kind="REPORT",
                block=SemanticViewerBlock(tuple(fragments), anchor="both"),
            ),
        )
    )


def _selections(outcome: ResolutionOutcome) -> tuple[DedupSelection, ...]:
    return tuple(
        DedupSelection(component_uid, survivor_uid)
        for component_uid, survivor_uid in outcome.decisions
    )


def dedup_exact_review(
    plan: FrozenDedupPlan,
    outcome: ResolutionOutcome,
) -> ExactCommandReview:
    selections = _selections(outcome)
    member_count = sum(len(component.members) for component in plan.components) + sum(
        1 + len(group.absorbed_uids) for group in plan.exact_item_groups
    )
    argv = ["mem", "dedun"]
    for handoff in plan.request.handoffs:
        argv.extend(("--evidence", redundancy_evidence_json(handoff)))
    for selection in selections:
        argv.extend(
            (
                "--survivor",
                f"{selection.component_uid}={selection.survivor_uid}",
            )
        )
    argv.extend(("--expected-revision", plan.revision, "--apply"))
    survivor_uids = {selection.survivor_uid for selection in selections}
    absorbed = tuple(
        member.uid
        for component in plan.components
        for member in component.members
        if member.uid not in survivor_uids
    ) + tuple(uid for group in plan.exact_item_groups for uid in group.absorbed_uids)
    return ExactCommandReview(
        argv=tuple(argv),
        effects=(
            f"Context revision · {plan.revision}.",
            "Apply will stop if the Context has changed.",
            "Keep "
            f"{len(selections) + len(plan.exact_item_groups)} unchanged existing "
            "survivor UID(s).",
            f"Absorb {len(absorbed)} of {member_count} component member UID(s): "
            + ", ".join(absorbed),
            "No replacement wording or cross-role conversion is generated; unrelated direct items stay unchanged.",
            "Inbound References to absorbed Memories block the whole Apply; "
            "recovery is mem undo.",
        ),
    )


def dedup_resolution_spec(plan: FrozenDedupPlan) -> ResolutionWorkbenchSpec:
    case = dedup_resolution_case(plan)
    placeholder = ResolutionOutcome(
        tuple(
            (component.uid, component.recommended_survivor_uid)
            for component in plan.components
        )
    )
    return ResolutionWorkbenchSpec(
        case=case,
        title="MEM DEDUN · RESOLUTION SESSION",
        subtitle="DUN EVIDENCE · EXISTING UID SURVIVOR · EXACT WHOLE-SET APPLY",
        report=project_dedup_plan(plan),
        items=tuple(
            ResolutionItem(
                uid=component.uid,
                label=f"Choose one unchanged survivor from {len(component.members)} members.",
                classification="REDUNDANCY GROUP",
                detail=_component_detail(component),
                compact_context=_component_compact_context(component),
                choices=tuple(
                    ResolutionChoice(
                        member.uid,
                        (
                            f"KEEP [{member.uid[:8]}] · RECOMMENDED"
                            if member.uid == component.recommended_survivor_uid
                            else f"KEEP [{member.uid[:8]}]"
                        ),
                        f"Keep Context item #{member.ordinal} unchanged; absorb the other UIDs.",
                    )
                    for member in component.members
                ),
                default_choice_uid=component.recommended_survivor_uid,
            )
            for component in plan.components
        ),
        exact_review=dedup_exact_review(plan, placeholder),
        detail_title="VIEWER · REDUNDANCY GROUP EVIDENCE",
        responses_title="RESPONSES · REQUIRED · EXISTING SURVIVOR",
        items_title="ITEMS · REQUIRED REDUNDANCY GROUPS",
        compact_summary=(
            f"CONTEXT · {safe_terminal_text(plan.display_name)} · "
            "GROUPS "
            f"{len(plan.components) + len(plan.exact_item_groups)} · choose one "
            "unchanged Memory survivor per semantic group; exact item groups "
            "keep their first occurrence automatically."
        ),
        show_viewer=False,
    )


def _receipt(receipt: DedupReceipt) -> str:
    return (
        f"CONTEXT · {receipt.context_name}\n"
        f"COMPONENTS · {len(receipt.selections)}\n"
        f"SURVIVORS · {len(receipt.survivor_uids)}\n"
        f"ABSORBED · {len(receipt.absorbed_uids)}\n"
        f"RECEIPT · {receipt.checkpoint_uid}\n"
        f"CHECKPOINT · {receipt.checkpoint_uid}\n"
        f"REVIEW · mem review dedun --receipt {receipt.checkpoint_uid}\n"
        "RECOVERY · mem undo"
    )


def run_dedup_tui(
    plan: FrozenDedupPlan,
    *,
    apply_selections: Callable[[tuple[DedupSelection, ...]], DedupReceipt],
    clipboard_writer: ClipboardWriter | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> DedupReceipt | None:
    return run_resolution_workbench(
        dedup_resolution_spec(plan),
        apply_outcome=lambda outcome: apply_selections(_selections(outcome)),
        receipt_text=_receipt,
        review_outcome=lambda outcome: dedup_exact_review(plan, outcome),
        clipboard_writer=clipboard_writer,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )


__all__ = [
    "dedup_exact_review",
    "dedup_resolution_spec",
    "project_dedup_plan",
    "run_dedup_tui",
]
