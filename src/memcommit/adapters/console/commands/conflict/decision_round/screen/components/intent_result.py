"""Intent result for the decision screen."""

from __future__ import annotations


def has_intent_result(state, intent, choice_previews) -> bool:
    item = state.current_issue()
    return bool(
        item is not None
        and intent is not None
        and intent.option_uid is not None
        and intent.option_uid(item.uid) in (choice_previews or {})
    )


def render_intent_result_diff(state, intent, choice_previews) -> list[tuple[str, str]]:
    item = state.current_issue()
    if (
        item is None
        or (intent is None or intent.option_uid is None)
        or not has_intent_result(state, intent, choice_previews)
    ):
        return []
    return list((choice_previews or {}).get(intent.option_uid(item.uid), ()))


def render_intent_result_title(state, intent) -> str:
    item = state.current_issue()
    if intent is not None and intent.pending:
        state = "PREPARING"
    elif intent is not None and item is not None and intent.response_changed(item):
        state = "NEEDS REFRESH · Press Enter in YOUR INTENT"
    else:
        state = "READY"
    return f"RESULT · {state}"
