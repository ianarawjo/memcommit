"""Keep one Resolve round's choices, intents and decision previews together."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from memcommit.adapters.console.commands.resolve.decision_round.impact_diff import (
    project_semantic_choice,
)
from memcommit.adapters.console.commands.resolve.decision_round.screen.inputs import (
    CompactIntentInput,
)
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionOption,
    ResolutionWorkbenchAction,
    ResolutionWorkbenchView,
)
from memcommit.application.operations.resolve.decisions import (
    ResolveDecision,
    finalize_resolve_decisions,
)
from memcommit.application.operations.resolve.model import ResolveAnalysis, ResolveError


class DecisionRoundState:
    """Keep choices, submitted intents and previews for all issues in one round."""

    def __init__(
        self,
        analysis: ResolveAnalysis,
        view: ResolutionWorkbenchView,
        choice_previews: dict[str, tuple[tuple[str, str], ...]],
        *,
        allow_bulk: bool,
        prepare_choice,
    ) -> None:
        self.analysis = analysis
        self.view = view
        self.prepare_choice = prepare_choice
        # The renderer must see later Intent refreshes through this same mapping.
        self.choice_previews = choice_previews
        self.selected = {
            item.uid: item.selected_option_uid
            for item in view.items
            if item.selected_option_uid is not None
        }
        self.responses: dict[str, str] = {}
        self.issue_uids = {issue.uid for issue in analysis.issues}
        self.commentable = {item.uid for item in view.items if item.commentable}
        self.options_by_uid = {
            item.uid: {option.uid for option in item.options} for item in view.items
        }
        self.common_choices = (
            set.intersection(
                *(
                    set(choice.uid for choice in issue.choices)
                    for issue in analysis.issues
                )
            )
            if allow_bulk
            else set()
        )
        self.bulk_options = tuple(
            ResolutionOption(choice.uid, choice.label + " FOR ALL", choice.text)
            for choice in analysis.issues[0].choices
            if choice.uid in self.common_choices
            and choice.uid in {"KEEP_TARGET", "TAKE_SOURCE", "KEEP_BOTH"}
        )

    def selected_option(self, item_uid: str) -> str | None:
        return self.selected.get(item_uid)

    def select_choice(self, item_uid: str, option_uid: str) -> None:
        if (
            item_uid not in self.issue_uids
            or option_uid not in self.options_by_uid[item_uid]
        ):
            raise ResolveError("Resolve selected an unavailable decision.")
        self.selected[item_uid] = option_uid

    @property
    def intent(self) -> CompactIntentInput:
        return self

    def response_text(self, item_uid: str) -> str:
        return self.responses.get(item_uid, "")

    @staticmethod
    def response_option_uid(item_uid: str) -> str:
        return f"{item_uid}:intent"

    @property
    def prepare_response(self) -> Callable[[str, str], Awaitable[None]] | None:
        return self.prepare_intent_preview if self.prepare_choice is not None else None

    def submit_intent(self, item_uid: str, value: str) -> None:
        if item_uid not in self.commentable:
            raise ResolveError("Resolve response names an unavailable Audit item.")
        self.responses[item_uid] = value
        if value.strip():
            self.selected[item_uid] = f"{item_uid}:intent"
        else:
            self.choice_previews.pop(f"{item_uid}:intent", None)

    @staticmethod
    def validate_intent(value: str) -> None:
        if value and not value.strip():
            raise ValueError("YOUR INTENT cannot contain only whitespace.")

    async def prepare_intent_preview(self, item_uid: str, value: str) -> None:
        if not value.strip():
            self.choice_previews.pop(f"{item_uid}:intent", None)
            return
        choice = await asyncio.to_thread(
            self.prepare_choice, ResolveDecision(item_uid, "INTENT", value.strip())
        )
        self.choice_previews[f"{item_uid}:intent"] = project_semantic_choice(
            self.analysis,
            choice,
            include_explanation=False,
        )

    def confirm(self, _item_uid: str | None) -> ResolutionWorkbenchAction | None:
        if not self.selected:
            return None
        for issue in self.analysis.issues:
            option_uid = self.selected.get(issue.uid)
            if (
                option_uid == f"{issue.uid}:intent"
                and not self.responses.get(issue.uid, "").strip()
            ):
                return None
        return ResolutionWorkbenchAction(kind="ACCEPT")

    def select_for_all(self, choice_uid: str) -> None:
        if choice_uid not in self.common_choices:
            raise ResolveError("Resolve bulk choice is unavailable.")
        for issue in self.analysis.issues:
            self.select_choice(issue.uid, f"{issue.uid}:{choice_uid.lower()}")

    def finalize_decisions(self) -> tuple[ResolveDecision, ...]:
        decisions: list[ResolveDecision] = []
        for issue in self.analysis.issues:
            option_uid = self.selected.get(issue.uid)
            if option_uid is None:
                continue
            suffix = option_uid.rpartition(":")[2]
            if suffix == "intent":
                decisions.append(
                    ResolveDecision(
                        issue.uid, "INTENT", self.responses[issue.uid].strip()
                    )
                )
            elif suffix == "confirm":
                decisions.append(ResolveDecision(issue.uid, "CONFIRM"))
            elif issue.choices or suffix in {"keep_both", "keep_as_is"}:
                decisions.append(ResolveDecision(issue.uid, suffix.upper()))
            else:
                decisions.append(ResolveDecision(issue.uid, "FORCE"))
        finalized_decisions = tuple(decisions)
        finalize_resolve_decisions(self.analysis, finalized_decisions)
        return finalized_decisions


__all__ = ["DecisionRoundState"]
