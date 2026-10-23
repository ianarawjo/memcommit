"""Show every conflicting Memory change as its own selectable card."""

from __future__ import annotations


from memcommit.adapters.console.commands.resolve.decision_round.screen.inputs import (
    CompactScreenPresentation,
)
from memcommit.adapters.console.commands.resolve.decision_round.screen.screen import (
    run_compact_resolution_decisions,
)
from memcommit.adapters.console.terminal.components.inline_diff import (
    render_inline_memory_change,
)
from memcommit.application.capabilities.reviewing.memory_diff import MemoryChange
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionDetailBlock,
    ResolutionItem,
    ResolutionOption,
    ResolutionWorkbenchAction,
    ResolutionWorkbenchView,
)
from memcommit.application.operations.resolve.review_round.in_round_change_review.find_conflicting_changes import (
    ConflictingMemoryChanges,
)


QUESTION = (
    "Your selected choices propose different changes to this Memory. "
    "Choose one to apply."
)


def _change_preview(conflict, candidate):
    operation = candidate.operation
    before = getattr(operation, "old_content", None)
    after = getattr(operation, "new_content", None)
    treatment = {"add": "ADD", "edit": "EDIT", "remove": "REMOVE"}[operation.operation]
    return tuple(
        render_inline_memory_change(
            MemoryChange(
                marker={"ADD": "+", "EDIT": "~", "REMOVE": "-"}[treatment],
                treatment=treatment,
                location=conflict.owner_context_name,
                memory_uid=conflict.memory_uid,
                before=before,
                after=after,
            )
        )
    )


class InRoundChangeReview:
    """Keep screen selections separate from immutable application candidates."""

    def __init__(self, analysis, conflicts: tuple[ConflictingMemoryChanges, ...]):
        self.conflicts = conflicts
        self.selected: dict[str, str] = {}
        self.by_item_uid = {
            f"{item.owner_context_uid}:{item.memory_uid}": item for item in conflicts
        }
        issue_number = {
            issue.uid: index for index, issue in enumerate(analysis.issues, 1)
        }
        issue_kind = {issue.uid: issue.kind for issue in analysis.issues}
        self.choice_previews = {}
        items = []
        for conflict in conflicts:
            display_conflict = conflict
            item_uid = f"{conflict.owner_context_uid}:{conflict.memory_uid}"
            before = getattr(
                conflict.candidates[0].operation, "old_content", "(new Memory)"
            )
            options = []
            for candidate in conflict.candidates:
                decision = candidate.decision
                label = (
                    ("YOUR INTENT" if decision.kind == "INTENT" else "USE SUGGESTION")
                    + f" · {issue_kind[decision.issue_uid]} {issue_number[decision.issue_uid]}"
                )
                options.append(
                    ResolutionOption(
                        candidate.uid,
                        label,
                        "Proposed change to this Memory.",
                    )
                )
                self.choice_previews[candidate.uid] = _change_preview(
                    display_conflict, candidate
                )
            items.append(
                ResolutionItem(
                    uid=item_uid,
                    kind="OVERLAPPING_CHANGES",
                    kind_label="OVERLAPPING CHANGES",
                    status="OPEN",
                    priority="REQUIRED",
                    title="Changes to the same Memory",
                    summary=QUESTION,
                    obligation="REQUIRED",
                    question=QUESTION,
                    blocks=(
                        ResolutionDetailBlock(
                            heading=f"[{display_conflict.owner_context_name}:{display_conflict.memory_uid[:8]}]",
                            text=before,
                        ),
                    ),
                    options=tuple(options),
                    selected_option_uid=conflict.priority_intent_candidate_uid,
                )
            )
        self.view = ResolutionWorkbenchView(
            operation="RESOLVE",
            artifact_uid=analysis.frame.source.context_uid,
            revision=analysis.frame.revision,
            title="Review changes to the same Memory",
            route=analysis.frame.display_name,
            status="NEEDS CHOICE",
            metrics=(),
            overview="",
            list_label="MEMORIES",
            items=tuple(items),
            empty_message="No conflicting changes remain.",
            results_label="CHOSEN CHANGES",
            results=(),
            capabilities=frozenset({"ACCEPT"}),
            accept_enabled=False,
            show_results=False,
        )
        self.bulk_options = ()
        self.intent = None

    def selected_option(self, item_uid: str) -> str | None:
        return self.selected.get(item_uid)

    def select_choice(self, item_uid: str, option_uid: str) -> None:
        conflict = self.by_item_uid[item_uid]
        if option_uid not in {item.uid for item in conflict.candidates}:
            raise ValueError("That change is unavailable for this Memory.")
        self.selected[item_uid] = option_uid

    def select_for_all(self, choice_uid: str) -> None:
        raise ValueError("Change review has no bulk choice.")

    def confirm(self, _item_uid: str | None) -> ResolutionWorkbenchAction | None:
        if any(
            item.uid not in self.selected and item.selected_option_uid is None
            for item in self.view.items
        ):
            return None
        return ResolutionWorkbenchAction(kind="ACCEPT")

    def chosen_candidate_uids(self) -> dict[tuple[str, str], str]:
        return {
            self.by_item_uid[item_uid].memory_key: candidate_uid
            for item_uid, candidate_uid in self.selected.items()
        }


def run_in_round_change_review(
    analysis,
    conflicts: tuple[ConflictingMemoryChanges, ...],
    *,
    header_label: str,
    **terminal_options,
) -> dict[tuple[str, str], str] | None:
    """Return explicit selections; a close returns to the round's choices."""
    review = InRoundChangeReview(analysis, conflicts)
    action = run_compact_resolution_decisions(
        review.view,
        decisions=review,
        presentation=CompactScreenPresentation(
            continue_label="Review combined changes",
            activation_hint="select/review",
            show_item_navigation=True,
            require_all_decisions=True,
            back_label="Back to choices",
        ),
        header_label=f"{header_label} · OVERLAPPING CHANGES",
        **terminal_options,
    )
    return review.chosen_candidate_uids() if action.kind == "ACCEPT" else None
