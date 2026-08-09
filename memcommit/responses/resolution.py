"""Project Resolution workbench Items into the shared response contract."""

from __future__ import annotations

from memcommit.resolution_workbench import ResolutionItem, ResolutionWorkbenchView
from memcommit.responses.model import ResponseChoice, ResponseDraft, ResponseTarget


def response_draft_from_item(item: ResolutionItem) -> ResponseDraft:
    """Return the adapter-projected durable response without changing it."""

    return ResponseDraft(item.selected_option_uid, item.response_text)


def response_target_from_item(
    view: ResolutionWorkbenchView,
    item: ResolutionItem,
    *,
    read_only: bool,
    stage_locally: bool = False,
) -> ResponseTarget | None:
    """Return a common response target for a decision or commentable change."""

    presentation = item.issue_presentation
    accepts_response = (
        presentation is not None
        or item.commentable
        or bool(item.question)
        or bool(item.options)
    )
    if not accepts_response:
        return None
    if presentation is None:
        prompt_heading = "QUESTION" if item.question else ""
        options_heading = "OPTIONS"
        other_label = "Different response"
        mode = "DECISION" if item.question or item.options else "COMMENT"
    else:
        prompt_heading = presentation.prompt_heading
        options_heading = presentation.options_heading
        other_label = presentation.other_option_label
        mode = "DECISION"
    return ResponseTarget(
        item_uid=item.uid,
        item_label=item.title,
        obligation=item.effective_obligation,
        state=item.response_state,
        mode=mode,
        prompt_heading=prompt_heading if item.question else "",
        prompt=item.question,
        choices_heading=options_heading,
        choices=tuple(
            ResponseChoice(option.uid, option.label, option.text)
            for option in item.options
        ),
        other_choice_label=other_label,
        editable=(
            not read_only
            and not view.input_locked
            and ("SUBMIT_ITEM" in view.capabilities or stage_locally)
        ),
    )
