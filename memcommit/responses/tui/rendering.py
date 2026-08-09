"""Render the independent RESPONSES frame without operation semantics."""

from __future__ import annotations

from memcommit.commands.semantic_viewer import semantic_viewer_block_fragments
from memcommit.commands.tui_primitives import safe_terminal_text
from memcommit.commands.tui_text_layout import wrap_terminal_text
from memcommit.responses.model import ResponseDraft, ResponseTarget
from memcommit.responses.state import ResponseFrameState
from memcommit.selection.tui import render_vertical_choice_cards


def _wrap(value: str, width: int) -> tuple[str, ...]:
    return tuple(wrap_terminal_text(safe_terminal_text(value), max(1, width)))


def response_frame_fragments(
    target: ResponseTarget,
    draft: ResponseDraft,
    state: ResponseFrameState,
    *,
    focused: bool,
    content_width: int,
) -> list[tuple[str, str]]:
    """Render one current Item's decision and free-form response state."""

    fragments: list[tuple[str, str]] = []
    body_width = max(16, content_width - 2)
    status = "ANSWERED" if draft.answered else target.state
    fragments.extend(
        [
            ("class:case-title", f" {safe_terminal_text(target.item_label)}\n"),
            (
                "class:detail-heading",
                (
                    f" {safe_terminal_text(target.obligation)} · "
                    f"{safe_terminal_text(status)}\n"
                ),
            ),
        ]
    )

    if target.has_decision:
        decision_parts: list[tuple[str, str]] = []
        if target.prompt_heading:
            decision_parts.append(
                (
                    "class:block-heading",
                    f" {safe_terminal_text(target.prompt_heading)}\n",
                )
            )
        for line in _wrap(target.prompt, body_width):
            decision_parts.append(("class:viewer-body", f" {line}\n"))
        if target.choices:
            decision_parts.append(
                (
                    "class:block-heading",
                    f" {safe_terminal_text(target.choices_heading)}\n",
                )
            )
            guidance = (
                "↑/↓ move · Enter select · Esc/Backspace back"
                if state.option_navigation_active
                else "Enter to choose an option"
            )
            decision_parts.append(("", f" {guidance}\n"))
            choice_state = state.choice_state
            if choice_state is None:
                raise ValueError(
                    "Response choices require synchronized selection state."
                )
            decision_parts.extend(
                render_vertical_choice_cards(
                    choice_state,
                    focused=(
                        focused
                        and state.section == "DECISION"
                        and state.option_navigation_active
                    ),
                    content_width=body_width,
                )
            )
        fragments.extend(
            semantic_viewer_block_fragments(
                decision_parts,
                active=focused and state.section == "DECISION",
                anchor="both",
            )
        )

    response_parts: list[tuple[str, str]] = [
        ("class:block-heading", " RESPONSE\n"),
    ]
    if state.editing:
        response_parts.append(("", " Editing below · Enter save · Ctrl-J newline\n"))
    elif draft.text.strip():
        response_parts.append(("", " SAVED\n"))
        for line in _wrap(draft.text, body_width):
            response_parts.append(("class:viewer-body", f" {line}\n"))
        if target.editable:
            response_parts.append(("", " Enter to edit this response.\n"))
    elif target.editable:
        response_parts.append(("", " Enter to write a response.\n"))
    else:
        response_parts.append(("", " No saved response.\n"))
    fragments.extend(
        semantic_viewer_block_fragments(
            response_parts,
            active=focused and state.section == "RESPONSE",
            anchor="both",
        )
    )
    return fragments


def response_snapshot_lines(
    target: ResponseTarget,
    draft: ResponseDraft,
    *,
    indent: str = "",
) -> list[str]:
    """Render the same response contract in a stable non-interactive form."""

    lines = [f"{indent}RESPONSES"]
    child = indent + "  "
    value = child + "  "
    if target.has_decision:
        if target.prompt_heading:
            lines.append(f"{child}{safe_terminal_text(target.prompt_heading)}")
        lines.extend(
            f"{value}{line}" for line in safe_terminal_text(target.prompt).splitlines()
        )
        if target.choices:
            lines.append(f"{child}{safe_terminal_text(target.choices_heading)}")
            for index, choice in enumerate(target.choices, start=1):
                marker = "✓" if choice.uid == draft.selected_choice_uid else " "
                lines.append(
                    f"{value}{marker} {index}. {safe_terminal_text(choice.label)}"
                )
                lines.extend(
                    f"{value}   {line}"
                    for line in safe_terminal_text(choice.text).splitlines()
                )
    lines.append(f"{child}RESPONSE")
    if draft.text.strip():
        lines.append(f"{child}Comment:")
        lines.extend(
            f"{value}{line}" for line in safe_terminal_text(draft.text).splitlines()
        )
    else:
        lines.append(f"{value}(none)")
    return lines
