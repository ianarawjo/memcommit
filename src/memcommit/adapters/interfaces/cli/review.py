"""Deterministic non-interactive presentation for semantic Review sessions."""

from __future__ import annotations

from memcommit.core.context import Context, Memory
from memcommit.adapters.console.text import safe_terminal_text
from memcommit.adapters.interfaces.tui.workbenches.review import (
    ATOMIZE_RESPONSE_LABEL,
    RESPONSE_LABEL,
)
from memcommit.application.operations.review.model import ReviewItem, ReviewSession


def visible_ordinal_index(selector: str, item_count: int) -> int | None:
    """Resolve only the canonical spelling of a visible 1-based ordinal."""
    if not selector.isdecimal():
        return None
    ordinal = int(selector)
    if selector != str(ordinal) or not 1 <= ordinal <= item_count:
        return None
    return ordinal - 1


def _direct_memory_map(ctx: Context) -> dict[str, Memory]:
    return {
        item.uid: item
        for item in ctx.iter_items()
        if isinstance(item, Memory)
    }


def _item_number(session: ReviewSession, item: ReviewItem) -> int:
    return next(
        index
        for index, candidate in enumerate(session.ordered_items(), start=1)
        if candidate.uid == item.uid
    )


def _status_marker(session: ReviewSession, item: ReviewItem) -> str:
    response = session.responses.get(item.uid)
    return "✓" if response is not None and response.answered else "·"


def _response_label(session: ReviewSession) -> str:
    return ATOMIZE_RESPONSE_LABEL if session.kind == "atomize" else RESPONSE_LABEL


def _empty_finding_label(session: ReviewSession) -> str:
    return (
        "no uncertain atomize items"
        if session.kind == "atomize"
        else "no actionable ambiguity findings"
    )


def _render_list_text(session: ReviewSession) -> str:
    current = session.current_item()
    lines = ["ISSUES"]
    for index, item in enumerate(session.ordered_items(), start=1):
        pointer = "›" if current is not None and item.uid == current.uid else " "
        lines.append(
            f"{pointer} {index:>2}. {_status_marker(session, item)} "
            f"{item.interpretation}/{item.clarification} "
            f"[{safe_terminal_text(item.uid[:8])}]"
        )
    if len(lines) == 1:
        lines.append(f"  ({_empty_finding_label(session)})")
    return "\n".join(lines)


def _render_detail_text(
    session: ReviewSession,
    memories: dict[str, Memory],
) -> str:
    item = session.current_item()
    if item is None:
        return (
            f"{_empty_finding_label(session).capitalize()}.\n\n"
            "The review session is still saved as a read-only record."
        )
    source = memories.get(item.source_uids[0])
    source_text = (
        safe_terminal_text(source.content)
        if source is not None
        else "[source Memory unavailable]"
    )
    selected_index = session.selected_choice_index(item)
    issue_label = "ATOMIZE UNCERTAINTY" if session.kind == "atomize" else "AMBIGUITY"
    lines = [
        f"{issue_label} {_item_number(session, item)}/{len(session.items)}",
        "",
        f"SOURCE [{safe_terminal_text(item.source_uids[0][:8])}]",
        source_text,
        "",
        "CLASSIFICATION",
        f"{item.interpretation} · {item.clarification}",
        "",
        (
            "WHY ATOMIZE IS BLOCKED"
            if session.kind == "atomize"
            else "WHY THIS IS UNCLEAR"
        ),
        safe_terminal_text(item.reason),
    ]
    if item.question:
        lines.extend(("", "CLARIFICATION PROMPT", safe_terminal_text(item.question)))
    if item.choices:
        lines.extend(("", "READING OPTIONS"))
        for index, choice in enumerate(item.choices, start=1):
            pointer = "›" if selected_index == index - 1 else " "
            lines.append(
                f"{pointer} {index}. [{safe_terminal_text(choice.label)}] "
                f"{safe_terminal_text(choice.text)}"
            )
    return "\n".join(lines)


def render_review_snapshot(session: ReviewSession, ctx: Context) -> str:
    """Render one stable Review frame without ANSI or durable mutation."""
    memories = _direct_memory_map(ctx)
    item = session.current_item()
    response = session.response_for(item.uid) if item is not None else None
    response_text = (
        safe_terminal_text(response.text)
        if response is not None and response.text
        else ""
    )
    return "\n".join(
        (
            (
                f"REVIEW · {session.kind} · Context: "
                f"{safe_terminal_text(session.context_name)}"
            ),
            (
                f"Order: {session.sort_mode} · "
                f"Answered: {session.answered_count}/{len(session.items)}"
            ),
            "",
            _render_list_text(session),
            "",
            _render_detail_text(session, memories),
            "",
            _response_label(session),
            f"> {response_text}",
            "",
            (
                "SOURCE means canonical Context order; Memory creation "
                "timestamps are not recorded."
            ),
            "No Memory changes have been applied.",
        )
    )


__all__ = ["render_review_snapshot", "visible_ordinal_index"]
