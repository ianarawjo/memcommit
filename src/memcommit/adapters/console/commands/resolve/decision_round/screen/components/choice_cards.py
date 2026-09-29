"""Choice cards for the decision screen."""

from __future__ import annotations


from memcommit.adapters.console.terminal.components.selection import (
    FlatSelectionState,
    SelectionOption,
    render_vertical_choice_cards,
)


def render_choice_cards(
    state,
    *,
    intent=None,
    choice_previews=None,
    is_focused,
    content_width,
    after_response=False,
) -> list[tuple[str, str]]:
    item = state.current_issue()
    if item is None:
        return []
    response_index = intent.response_choice_index(item) if intent is not None else None
    if response_index is None:
        indexes = range(len(item.options)) if not after_response else range(0)
    elif after_response:
        indexes = range(response_index + 1, len(item.options))
    else:
        indexes = range(0, response_index)
    fragments: list[tuple[str, str]] = []
    selected_uid = state.selected_for(item)
    content_width = content_width()
    for index in indexes:
        option = item.options[index]
        row = SelectionOption(f"choice:{option.uid}", option.label, option.text)
        if state.focused_row_index == index:
            fragments.append(("[SetCursorPosition]", ""))
        card_selection = FlatSelectionState(
            (row,),
            cursor_uid=row.uid,
            selected_uid=(row.uid if selected_uid == option.uid else None),
            allow_empty=True,
        )
        focused = state.focused_row_index == index and is_focused("choices")
        fragments.extend(
            render_vertical_choice_cards(
                card_selection,
                focused=focused,
                content_width=content_width,
                numbered=False,
                anchor_cursor=False,
                label_in_border=True,
                descriptions={row.uid: choice_previews[option.uid]}
                if choice_previews is not None and option.uid in choice_previews
                else None,
            )
        )
    # Adjacent containers own the newline between cards and the intent field.
    for fragment_index in range(len(fragments) - 1, -1, -1):
        style, text = fragments[fragment_index]
        if text:
            if text.endswith("\n"):
                fragments[fragment_index] = (style, text[:-1])
            break
    return fragments


def has_trailing_choices(state, intent=None) -> bool:
    item = state.current_issue()
    response_index = intent.response_choice_index(item) if intent is not None else None
    return (
        item is not None
        and response_index is not None
        and response_index + 1 < len(item.options)
    )
