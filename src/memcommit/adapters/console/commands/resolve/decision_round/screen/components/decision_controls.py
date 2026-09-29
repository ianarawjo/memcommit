"""Decision controls for the decision screen."""

from __future__ import annotations


from memcommit.adapters.console.terminal.components.action import render_action_button
from memcommit.application.capabilities.resolution.workbench import ResolutionItem


def decision_progress(state, intent=None) -> str:
    required = tuple(
        item for item in state.items if item.effective_obligation == "REQUIRED"
    )
    if not required:
        return ""

    def is_answered(item: ResolutionItem) -> bool:
        selected_uid = state.selected_for(item)
        if (
            intent is not None
            and intent.option_uid is not None
            and intent.read_text is not None
            and selected_uid == intent.option_uid(item.uid)
        ):
            return bool(
                intent.read_text(item.uid).strip()
            ) and not intent.response_changed(item)
        return selected_uid is not None or item.response_state == "ANSWERED"

    answered_count = sum(1 for item in required if is_answered(item))
    if not state.require_all_decisions:
        return (
            f"  {answered_count} selected · {len(required) - answered_count} unanswered"
        )
    readiness = " READY" if answered_count == len(required) else ""
    return f"  {answered_count}/{len(required)}{readiness}"


def render_decision_controls(
    state, *, intent=None, is_focused
) -> list[tuple[str, str]]:
    fragments: list[tuple[str, str]] = []
    item = state.current_issue()
    action_offset = len(item.options) if item is not None else 0
    if (
        intent is not None
        and intent.option_uid is None
        and intent.response_available(item)
    ):
        action_offset += 1
    for option in state.bulk_options:
        focused = state.focused_row_index == action_offset and is_focused("actions")
        fragments.extend(render_action_button(option.label, focused=focused))
        fragments.append(("", "\n"))
        action_offset += 1
    focused = state.focused_row_index == action_offset and is_focused("actions")
    label = state.continue_label().strip().upper()
    if label == "APPLY":
        label = "APPLY ALL"
    fragments.extend(render_action_button(label, focused=focused))
    fragments.append(("class:report-neutral", decision_progress(state, intent)))
    return fragments
