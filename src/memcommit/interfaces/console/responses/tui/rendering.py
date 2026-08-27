"""Render the independent RESPONSES frame without operation semantics."""

from __future__ import annotations

from memcommit.interfaces.tui.viewers.semantic import (
    semantic_viewer_block_fragments,
)
from memcommit.interfaces.console.text import (
    safe_terminal_text,
)
from memcommit.interfaces.tui.core.text_layout import (
    wrap_terminal_text,
)
from memcommit.interfaces.console.responses.model import ResponseDraft, ResponseTarget
from memcommit.interfaces.console.responses.state import ResponseFrameState
from memcommit.interfaces.console.selection.tui import render_vertical_choice_rows


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
            decision_parts.append(
                ("", " ↑/↓ move through choices and Response · Enter select\n")
            )
            choice_state = state.choice_state
            if choice_state is None:
                raise ValueError(
                    "Response choices require synchronized selection state."
                )
            decision_parts.extend(
                render_vertical_choice_rows(
                    choice_state,
                    focused=(focused and state.section == "DECISION"),
                    content_width=body_width,
                )
            )
        if target.choices:
            # The common choice-row renderer owns the only focus treatment and
            # viewport anchor here. Wrapping the entire Decision as an active
            # semantic block would also light the explanatory question.
            fragments.extend(decision_parts)
        else:
            fragments.extend(
                semantic_viewer_block_fragments(
                    decision_parts,
                    active=focused and state.section == "DECISION",
                    anchor="start",
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
