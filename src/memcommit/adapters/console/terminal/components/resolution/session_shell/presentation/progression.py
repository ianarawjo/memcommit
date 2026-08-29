"""Progression policy and final confirmation for Resolution Sessions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from memcommit.adapters.console.coordination.command_review.model import CommandReview
from memcommit.adapters.console.terminal.components.exact_command_review.rendering import (
    format_exact_command,
)
from memcommit.adapters.console.terminal.components.report_card import boxed_lines
from memcommit.adapters.console.terminal.components.responses.model import ResponseDraft
from memcommit.adapters.console.terminal.components.responses.resolution import (
    response_draft_from_item,
)
from memcommit.adapters.console.terminal.components.save_location import (
    SaveLocationView,
)
from memcommit.adapters.console.terminal.components.semantic_viewer import (
    semantic_viewer_block_fragments,
)
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionItem,
    ResolutionWorkbenchView,
)


@dataclass(frozen=True)
class ResolutionGlobalStrategy:
    """One operation-authored whole-set shortcut; never an apply action."""

    label: str
    action_kind: str
    comment: str = ""


# Compatibility export for operation adapters that adopted the Resolution name
# before save-location presentation became a service-wide control.
ResolutionDestination = SaveLocationView


@dataclass(frozen=True)
class SessionTodoView:
    """One state-derived next action shown below a session's Items frame."""

    kind: str
    label: str
    detail: str
    unresolved_item_uids: tuple[str, ...] = ()


def _item_draft(
    item: ResolutionItem,
    drafts: dict[str, ResponseDraft],
) -> ResponseDraft:
    """Return the live draft or the adapter's durable response projection."""

    return drafts.get(
        item.uid,
        response_draft_from_item(item),
    )


def _item_is_answered(
    item: ResolutionItem,
    drafts: dict[str, ResponseDraft],
) -> bool:
    if item.response_state == "NOT_APPLICABLE":
        return True
    # A live draft is authoritative even when it deliberately clears a
    # durable answer; otherwise the To Do pane can keep reporting the item as
    # answered after its selected option is cancelled.
    if item.uid in drafts:
        return drafts[item.uid].answered
    if item.response_state == "ANSWERED":
        return True
    return _item_draft(item, drafts).answered


def _review_count_text(
    count: int,
    singular_suffix: str,
    plural_suffix: str | None = None,
) -> str:
    noun = "review" if count == 1 else "reviews"
    suffix = singular_suffix if count == 1 or plural_suffix is None else plural_suffix
    return f"{count} optional {noun} {suffix}. "


def session_review_action_view(
    view: ResolutionWorkbenchView,
    drafts: dict[str, ResponseDraft],
    *,
    whole_set_available: bool,
) -> SessionTodoView:
    """Derive the action offered inside the Review and Apply surface."""

    optional = tuple(
        item
        for item in view.items
        if item.effective_obligation == "OPTIONAL"
        and not _item_is_answered(item, drafts)
    )
    pending_comments = tuple(
        item
        for item in view.items
        if item.commentable
        and _item_draft(item, drafts).text.strip()
        and _item_draft(item, drafts).text != item.response_text
    )
    if pending_comments and whole_set_available:
        noun = "comment" if len(pending_comments) == 1 else "comments"
        return SessionTodoView(
            "INCORPORATE RESPONSES",
            "Incorporate saved responses",
            f"{len(pending_comments)} saved change {noun} will revise the complete "
            "proposal. No Context or Memory changes will be applied yet.",
        )
    if view.accept_enabled:
        if view.accept_mode == "AS_IS":
            open_reviews = tuple(
                item for item in optional if item.role == "OPTIONAL_REVIEW"
            )
            detail = ""
            if view.unresolved_at_apply_count:
                noun = "finding" if view.unresolved_at_apply_count == 1 else "findings"
                detail += (
                    f"{view.unresolved_at_apply_count} unresolved {noun} will be "
                    "recorded at apply. "
                )
            if open_reviews:
                detail += _review_count_text(
                    len(open_reviews),
                    "remains open",
                    "remain open",
                )
            return SessionTodoView(
                "APPLY AS IS",
                f"Apply {view.operation.title()} as is",
                detail + "Enter to apply the exact current proposal as is. "
                "Recovery: mem undo.",
            )
        return SessionTodoView(
            "APPLY",
            f"Apply {view.operation.title()}",
            "Enter to apply the exact current proposal shown in the report.",
        )
    if whole_set_available:
        if "INCORPORATE_AND_APPLY" in view.capabilities:
            return SessionTodoView(
                "INCORPORATE AND APPLY",
                f"Incorporate responses and apply {view.operation.title()}",
                (_review_count_text(len(optional), "remains open") if optional else "")
                + (
                    "Enter to create a revised proposal from the saved responses "
                    "and apply it after normal freshness and safety validation."
                ),
            )
        return SessionTodoView(
            "INCORPORATE RESPONSES",
            "Incorporate saved responses",
            (_review_count_text(len(optional), "may be skipped") if optional else "")
            + (
                "Enter to create a revised complete proposal. "
                "No Context or Memory changes will be applied yet."
            ),
        )
    return SessionTodoView(
        "COMPLETE",
        "Required review is complete",
        (
            _review_count_text(
                len(optional),
                "remains open",
                "remain open",
            )
            if optional
            else ""
        )
        + "No whole-set action is required; close or revisit an item.",
    )


def session_todo_view(
    view: ResolutionWorkbenchView,
    drafts: dict[str, ResponseDraft],
    *,
    review_and_apply: bool,
    read_only: bool,
    whole_set_available: bool = True,
    read_only_handoff: SessionTodoView | None = None,
    item_handoff: (
        SessionTodoView | Callable[[], SessionTodoView | None] | None
    ) = None,
) -> SessionTodoView:
    """Derive one honest next action without creating semantic authority."""

    unresolved = [
        item
        for item in view.items
        if item.effective_obligation != "NONE" and not _item_is_answered(item, drafts)
    ]
    if read_only:
        if read_only_handoff is not None:
            return read_only_handoff
        return SessionTodoView(
            "READ ONLY",
            "No action available",
            "This saved session can only be inspected.",
        )
    if unresolved:
        required = tuple(
            item for item in unresolved if item.effective_obligation == "REQUIRED"
        )
        optional = tuple(
            item for item in unresolved if item.effective_obligation == "OPTIONAL"
        )
        pending = required
    else:
        required = ()
        optional = ()
        pending = ()
    if pending:
        conflicts = all("CONFLICT" in item.kind.upper() for item in pending)
        noun = "conflict" if conflicts else "item"
        if len(pending) != 1:
            noun += "s"
        qualifier = "required " if required else ""
        optional_note = (
            _review_count_text(len(optional), "may be skipped") if optional else ""
        )
        return SessionTodoView(
            "RESOLVE",
            f"Resolve {len(pending)} {qualifier}{noun}",
            optional_note + "Enter to open the first unresolved item.",
            tuple(item.uid for item in pending),
        )
    if item_handoff is not None and view.items:
        return item_handoff
    if review_and_apply and (view.accept_enabled or whole_set_available):
        action = session_review_action_view(
            view,
            drafts,
            whole_set_available=whole_set_available,
        )
        return SessionTodoView(
            "REVIEW AND APPLY",
            f"Confirm final {view.operation.title()} Apply",
            f"{action.kind} is available. Enter to confirm the decided state.",
        )
    if not whole_set_available:
        return SessionTodoView(
            "COMPLETE",
            "Required review is complete",
            (
                _review_count_text(
                    len(optional),
                    "remains open",
                    "remain open",
                )
                if optional
                else ""
            )
            + "No whole-set action is required; close or revisit an item.",
        )
    return SessionTodoView(
        "RESOLVE ALL",
        "Review the whole-set resolution",
        "Enter to open the whole-set strategy.",
    )


def _report_action(
    view: ResolutionWorkbenchView,
    drafts: dict[str, ResponseDraft],
    strategies: tuple[ResolutionGlobalStrategy, ...],
) -> tuple[str, str, bool]:
    """Project the same next action into Report that To Do already exposes."""

    todo = session_todo_view(
        view,
        drafts,
        review_and_apply=True,
        read_only=False,
        whole_set_available=bool(strategies),
    )
    heading = "APPLY CONFIRMATION" if todo.kind == "REVIEW AND APPLY" else todo.kind
    return heading, f"{todo.label}. {todo.detail}", False


def resolution_review_fragments(
    view: ResolutionWorkbenchView,
    drafts: dict[str, ResponseDraft],
    strategies: tuple[ResolutionGlobalStrategy, ...],
    strategy_index: int,
    action: SessionTodoView,
    focused_section: int = 0,
    content_width: int = 76,
    review_title: str = "APPLY CONFIRMATION",
    command_review: CommandReview | None = None,
) -> list[tuple[str, str]]:
    """Render the exact Apply confirmation without performing its action."""

    show_policy = action.kind in {
        "INCORPORATE RESPONSES",
        "INCORPORATE AND APPLY",
        "RESOLVE ALL",
    }
    section_count = 2 + int(show_policy) + int(command_review is not None)
    focused_section = max(0, min(focused_section, section_count - 1))
    fragments: list[tuple[str, str]] = []
    answered = 0
    response_lines: list[str] = []
    unresolved_counts: dict[str, int] = {}
    reviewable = 0
    for index, item in enumerate(view.items, start=1):
        obligation = item.effective_obligation
        draft = _item_draft(item, drafts)
        option_uid, comment = draft.selected_choice_uid, draft.text
        if obligation == "NONE":
            if item.commentable and comment.strip():
                response_lines.extend(
                    [f"{index}. {item.title}", f"   CHANGE COMMENT · {comment.strip()}"]
                )
            continue
        reviewable += 1
        if option_uid is not None:
            option = item.option(option_uid)
            answer = f"SELECTED · {option.label}"
            answered += 1
        elif comment.strip():
            answer = f"OTHER DIRECTION · {comment.strip()}"
            answered += 1
        elif item.response_state == "ANSWERED":
            answer = "ANSWERED"
            answered += 1
        else:
            answer = "UNRESOLVED"
        if answer == "UNRESOLVED":
            unresolved_counts[obligation] = unresolved_counts.get(obligation, 0) + 1
            continue
        response_lines.extend([f"{index}. {item.title}", f"   {answer}"])

    ready_without_open_reviews = reviewable == 0 and action.kind in {
        "APPLY",
        "APPLY AS IS",
    }
    if not response_lines:
        response_lines.append(
            "No open issue responses remain in the current proposal."
            if ready_without_open_reviews
            else "No staged issue responses yet."
        )
    remaining_summary = (
        " · ".join(
            f"{priority} {count}"
            for priority, count in (
                ("REQUIRED", unresolved_counts.get("REQUIRED", 0)),
                ("OPTIONAL", unresolved_counts.get("OPTIONAL", 0)),
            )
            if count
        )
        or "NONE"
    )
    if not ready_without_open_reviews:
        response_lines.append(f"RESPONSES · {answered}/{reviewable} ANSWERED")
    response_lines.extend(
        [
            f"OPEN REVIEWS · {remaining_summary}",
            "Nothing changes until the final action below is confirmed.",
        ]
    )

    summary_fragments = [
        ("class:detail-card", f" {line}\n")
        for line in boxed_lines(
            review_title,
            "\n".join(response_lines).rstrip(),
            width=max(24, content_width - 1),
        )
    ]
    fragments.extend(
        semantic_viewer_block_fragments(
            summary_fragments,
            active=focused_section == 0,
            anchor="end",
        )
    )
    fragments.append(("", "\n"))

    action_section = 1
    if show_policy:
        policy_lines: list[str] = []
        for index, policy in enumerate(strategies):
            selected = index == strategy_index
            marker = "›" if selected else " "
            policy_lines.append(f"{marker} {index + 1}. {policy.label}")
        policy_box = boxed_lines(
            "REMAINING-ITEM POLICY",
            "\n".join(policy_lines) or "No unresolved-conflict policies are available.",
            width=max(24, content_width - 1),
        )
        policy_fragments = [("class:detail-card", f" {line}\n") for line in policy_box]
        fragments.extend(
            semantic_viewer_block_fragments(
                policy_fragments,
                active=focused_section == 1,
                anchor="end",
            )
        )
        fragments.append(("", "\n"))
        action_section = 2

    if command_review is not None:
        command_box = boxed_lines(
            "COMMAND · RUNNABLE",
            "\n".join(
                (
                    format_exact_command(command_review),
                    "",
                    *command_review.effects,
                )
            ),
            width=max(24, content_width - 1),
        )
        command_fragments = [
            ("class:detail-card", f" {line}\n") for line in command_box
        ]
        fragments.extend(
            semantic_viewer_block_fragments(
                command_fragments,
                active=focused_section == action_section,
                anchor="end",
            )
        )
        fragments.append(("", "\n"))
        action_section += 1

    return_note = (
        "Esc/Backspace returns without applying."
        if "APPLY" in action.kind
        else "Esc/Backspace returns without resolving."
    )
    action_box = boxed_lines(
        action.kind,
        f"{action.label}\n{action.detail}\n{return_note}",
        width=max(24, content_width - 1),
    )
    action_fragments = [("class:detail-card", f" {line}\n") for line in action_box]
    fragments.extend(
        semantic_viewer_block_fragments(
            action_fragments,
            active=focused_section == action_section,
            anchor="end",
        )
    )
    return fragments
