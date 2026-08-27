"""Read-only policy and rendering for the Resolution Session shell."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from prompt_toolkit.utils import get_cwidth

from memcommit.application.exact_command_review import ExactCommandReview
from memcommit.adapters.interfaces.tui.components.exact_command_review.rendering import (
    format_exact_command,
)
from memcommit.adapters.interfaces.tui.components.report_card import boxed_lines
from memcommit.adapters.interfaces.tui.components.tree_row import navigable_tree_row_prefix
from memcommit.adapters.interfaces.tui.core.theme import (
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.adapters.console.content_row import render_numbered_content_row
from memcommit.adapters.console.text import (
    safe_terminal_text,
)
from memcommit.adapters.interfaces.tui.core.text_layout import (
    elide_terminal_text,
    single_line_terminal_text,
    terminal_cell_width,
    wrap_terminal_text,
)
from memcommit.adapters.interfaces.tui.components.save_location import (
    SaveLocationView,
)
from memcommit.adapters.interfaces.tui.viewers.semantic.detail import (
    semantic_detail_block_fragments,
    semantic_detail_header_fragments,
    semantic_memory_row_fragments,
    semantic_trace_fragments,
)
from memcommit.adapters.interfaces.tui.viewers.semantic import (
    deactivate_semantic_viewer_fragments,
    semantic_viewer_block_fragments,
)
from memcommit.adapters.interfaces.tui.workbenches.impact import ImpactController, ImpactView
from memcommit.application.reviewing.memory_diff import MemoryChange, MemoryDiffSpan, memory_diff_lines
from memcommit.application.resolution.workbench import (
    ResolutionNavigation,
    ResolutionItem,
    ResolutionMemoryRow,
    ResolutionWorkbenchView,
)
from memcommit.adapters.console.responses.model import ResponseDraft
from memcommit.adapters.console.responses.resolution import (
    response_draft_from_item,
)
from memcommit.adapters.console.selection.model import SelectionOption
from memcommit.adapters.console.selection.state import FlatSelectionState
from memcommit.adapters.console.selection.tui import render_vertical_choice_cards
from memcommit.application.reviewing.session_navigation import (
    WorkbenchSection,
)


# Report chrome and explanatory prose stay neutral white. Lavender identifies
# an actual Memory object only; using it for whole cards blurs data and report
# structure into the same visual class.
RESOLUTION_WORKBENCH_STYLE = SEMANTIC_VIEWER_STYLE


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
    heading = (
        "APPLY CONFIRMATION"
        if todo.kind == "REVIEW AND APPLY"
        else todo.kind
    )
    return heading, f"{todo.label}. {todo.detail}", False


def _current_impact(
    controller: ImpactController | None,
    view: ResolutionWorkbenchView,
) -> ImpactView | None:
    if controller is None:
        return None
    impact = controller.view()
    if (
        impact.operation.upper() != view.operation.upper()
        or impact.artifact_uid != view.artifact_uid
        or impact.revision != view.revision
    ):
        raise ValueError(
            "Impact projection does not match the active artifact revision."
        )
    return impact


def _impact_repeats_results(
    impact: ImpactView | None,
    view: ResolutionWorkbenchView,
) -> bool:
    return impact is not None and (
        impact.replaces_results
        or (
            len(impact.entries) == len(view.results)
            and all(
                (entry.marker, entry.label, entry.text)
                == (result.marker, result.label, result.text)
                for entry, result in zip(
                    impact.entries,
                    view.results,
                    strict=True,
                )
            )
        )
    )


def _impact_entry_section_uid(entry, index: int) -> str:
    identity = entry.uid.strip() if entry.uid.strip() else str(index)
    return f"REPORT:IMPACT:{identity}"


def _impact_entry_item(
    view: ResolutionWorkbenchView,
    entry,
) -> ResolutionItem | None:
    """Locate the comment owner for one exact Impact Memory transition."""

    for item in view.items:
        if item.uid == entry.uid:
            return item
        memory_uid = next(
            (block.text for block in item.blocks if block.heading == "MEMORY UID"),
            None,
        )
        owner = next(
            (block.text for block in item.blocks if block.heading == "OWNER"),
            "",
        )
        if memory_uid == entry.uid and (
            not entry.location or owner.startswith(f"Context {entry.location} ")
        ):
            return item
    return None


def _impact_arrow_expansion(
    expanded_uid: str | None,
    focused_uid: str | None,
    *,
    expand: bool,
) -> str | None:
    """Apply ordinary tree-arrow semantics to one focused Impact row."""

    if focused_uid is None:
        return expanded_uid
    if expand:
        return focused_uid
    return None if expanded_uid == focused_uid else expanded_uid


def _stacked_horizontal_key_message(kind: str) -> str:
    """Explain the vertical path for a split frame without horizontal meaning."""

    if kind == "RESPONSES":
        return "Responses are stacked · use Up/Down for choices and Response."
    if kind == "ITEM":
        return "This detail is vertical · use Up/Down, or Tab to reach Responses."
    if kind == "REPORT":
        return "This report is vertical · use Up/Down between blocks."
    return "This frame has no Left/Right action · use Up/Down or Tab."


def _impact_lines(impact: ImpactView) -> list[str]:
    lines = [impact.title, impact.summary]
    if impact.detail:
        lines.extend(["", impact.detail])
    for index, entry in enumerate(impact.entries, start=1):
        if entry.location:
            lines.extend(
                [
                    "",
                    (
                        f"  {entry.marker} {index}. [{entry.label}] "
                        f"{entry.location} [{entry.uid}]"
                    ),
                ]
            )
            change = MemoryChange(
                marker=entry.marker,
                treatment=entry.label,
                location=entry.location,
                memory_uid=entry.uid or str(index),
                before=entry.before,
                after=entry.after,
                reason=entry.reason,
                rules=entry.rules,
            )
            lines.extend(
                f"      {line.marker} {''.join(span.text for span in line.spans)}"
                for line in memory_diff_lines(change)
            )
            if entry.reason:
                lines.append(f"      WHY · {entry.reason}")
            continue
        lines.extend(
            [
                "",
                f"  {entry.marker} {index}. [{entry.label}]",
                f"      {entry.text}",
            ]
        )
        if entry.reason:
            lines.append(f"      WHY · {entry.reason}")
    if not impact.detail and not impact.entries:
        lines.extend(["", "  (no effects)"])
    return lines


def _line(value: str, limit: int = 100) -> str:
    normalized = single_line_terminal_text(safe_terminal_text(value))
    return elide_terminal_text(normalized, limit)


def _item_kind_label(item: ResolutionItem) -> str:
    """Render the operation-owned label without leaking its storage token."""

    return safe_terminal_text(item.display_kind)


def _stable_sections(
    entries: tuple[tuple[str, str, int | None], ...],
) -> tuple[WorkbenchSection, ...]:
    """Give repeated semantic section kinds stable occurrence identities."""
    counts: dict[str, int] = {}
    sections: list[WorkbenchSection] = []
    for kind, identity, row_index in entries:
        count = counts.get(identity, 0)
        counts[identity] = count + 1
        suffix = f":{count}" if count else ""
        sections.append(
            WorkbenchSection(
                uid=f"{identity}{suffix}",
                kind=kind,
                row_index=row_index,
            )
        )
    return tuple(sections)


def _memory_row_section_uid(
    item_uid: str,
    block_index: int,
    row: ResolutionMemoryRow,
) -> str:
    return f"ITEM:{item_uid}:BLOCK:{block_index}:MEMORY:{row.ordinal}"


def _indented(value: str, indent: str = "       ") -> str:
    return "\n".join(indent + line for line in value.splitlines())


def _visual_width(value: str) -> int:
    return terminal_cell_width(value)


def _visual_pad(value: str, width: int) -> str:
    return value + (" " * max(0, width - _visual_width(value)))


def _visual_wrap(value: str, width: int) -> list[str]:
    """Wrap terminal text by display cells while retaining paragraph breaks."""
    return wrap_terminal_text(safe_terminal_text(value), width)


def _source_memory_lines(content: str, content_width: int) -> tuple[str, ...]:
    """Wrap one Memory for its nested reading viewport, not outer focus."""

    # Reserve the first-row short UID and continuation indentation. These rows
    # are presentation-only offsets inside one stable SOURCE_MEMORY section.
    return tuple(_visual_wrap(content, max(1, content_width - 16)))


def _evidence_section_count(evidence, content_width: int) -> int:
    """Count Classification, criterion, whole-Memory, and Why stops."""

    _ = content_width
    source_memory_count = sum(
        1 for claim in evidence.source_groups for source in claim.sources
    )
    return 2 + len(evidence.criterion_blocks) + source_memory_count


def _visual_wrap_diff_spans(
    spans: tuple[MemoryDiffSpan, ...],
    width: int,
) -> list[list[tuple[str, bool]]]:
    """Wrap mechanical diff spans without discarding their changed flags."""

    lines: list[list[tuple[str, bool]]] = [[]]
    current_width = 0
    for span in spans:
        for character in safe_terminal_text(span.text):
            character_width = get_cwidth(character)
            if lines[-1] and current_width + character_width > width:
                lines.append([])
                current_width = 0
            if lines[-1] and lines[-1][-1][1] == span.changed:
                prior, changed = lines[-1][-1]
                lines[-1][-1] = (prior + character, changed)
            else:
                lines[-1].append((character, span.changed))
            current_width += character_width
    if not lines[-1]:
        lines[-1].append(("", spans[0].changed))
    return lines


def _impact_treatment_style(label: str, *, focused: bool) -> str:
    # The compact marker/tag retains semantic color without tinting the whole
    # Memory or report chrome. Located mutation identity and content have their
    # own lavender/white roles; legacy result rows retain treatment focus.
    _ = focused
    token = label.strip().upper()
    key = {
        "KEEP": "keep",
        "REDACT": "redact",
        "SUMMARIZE": "summarize",
        "REFRAME": "reframe",
        "FORGET": "forget",
        "CUSTOM": "custom",
        "EDIT": "edit",
        "ADD": "add",
        "REMOVE": "remove",
    }.get(token, "other")
    return f"class:impact.{key}"


def _session_items_fragments(
    view: ResolutionWorkbenchView,
    *,
    selected_index: int,
    focused: bool,
    content_width: int,
    report_label: str,
) -> list[tuple[str, str]]:
    """Render Items with hanging wraps inside the current frame width."""
    rows = (("REPORT", report_label),) + tuple(
        (_item_kind_label(item).upper(), item.title) for item in view.items
    )
    fragments: list[tuple[str, str]] = []
    available_width = max(12, content_width)
    for index, (kind, label) in enumerate(rows):
        selected = index == selected_index
        if selected:
            fragments.append(("[SetCursorPosition]", ""))
        prefix = f"{'›' if selected else ' '} {kind:<14} "
        label_width = max(1, available_width - _visual_width(prefix))
        wrapped = _visual_wrap(label, label_width)
        style = (
            "class:memcommit.table.selected"
            if selected and focused
            else "bold"
            if selected
            else ""
        )
        for line_index, line in enumerate(wrapped):
            lead = prefix if line_index == 0 else " " * _visual_width(prefix)
            fragments.append((style, f"{lead}{line}"))
            if line_index < len(wrapped) - 1:
                fragments.append(("", "\n"))
        if index < len(rows) - 1:
            fragments.append(("", "\n"))
    return fragments
def _viewer_focus_fragments(
    fragments: list[tuple[str, str]],
    *,
    focused: bool,
) -> list[tuple[str, str]]:
    """Hide positional emphasis when the Viewer is not the active pane."""
    if focused:
        return fragments
    return deactivate_semantic_viewer_fragments(fragments)


def resolution_workbench_fragments(
    view: ResolutionWorkbenchView,
    navigation: ResolutionNavigation,
    *,
    other_direction_focused: bool = False,
) -> list[tuple[str, str]]:
    """Render one complete immutable adapter view with a visible cursor."""
    navigation.sync(view)
    metric_text = " · ".join(
        f"{safe_terminal_text(metric.value)} {safe_terminal_text(metric.label)}"
        for metric in view.metrics
    )
    status_line = f" {safe_terminal_text(view.status)}"
    if metric_text:
        status_line += f" · {metric_text}"
    fragments: list[tuple[str, str]] = [
        ("class:title", f" {safe_terminal_text(view.title)}\n"),
        ("", f" {safe_terminal_text(view.route)}\n"),
        ("", status_line + "\n\n"),
    ]
    if view.semantic_overview_sections:
        for section in view.semantic_overview_sections:
            fragments.extend(
                [
                    (
                        "class:block-heading",
                        f" {safe_terminal_text(section.heading)}\n",
                    ),
                    ("", f" {safe_terminal_text(section.text) or '(none)'}\n\n"),
                ]
            )
    fragments.append(("class:section", f" {safe_terminal_text(view.list_label)}\n"))
    if not view.items:
        fragments.append(("", f"  {safe_terminal_text(view.empty_message)}\n"))
    for index, item in enumerate(view.items, start=1):
        selected = item.uid == navigation.selected_item_uid
        expanded = selected and item.uid == navigation.expanded_item_uid
        if selected:
            fragments.append(("[SetCursorPosition]", ""))
        if item.compact_row_suffix is not None:
            fragments.append(
                (
                    "class:selected" if selected else "",
                    (
                        f" {'▾' if expanded else ('›' if selected else ' ')} "
                        + safe_terminal_text(
                            render_numbered_content_row(
                                index,
                                item.title,
                                suffix=item.compact_row_suffix,
                            )
                        )
                        + "\n"
                    ),
                )
            )
        else:
            fragments.append(
                (
                    "class:selected" if selected else "",
                    (
                        f" {'▾' if expanded else ('›' if selected else ' ')} "
                        f"{index:>2}. [{safe_terminal_text(item.priority)}] "
                        f"{_line(item.title)}\n"
                    ),
                )
            )
            fragments.append(
                (
                    "",
                    (
                        "       "
                        f"{_item_kind_label(item)} · "
                        f"{safe_terminal_text(item.status)} · "
                        f"{_line(item.summary)}\n"
                    ),
                )
            )
        if not expanded:
            continue
        if item.issue_presentation is not None:
            # Atomize still uses the compact list/detail shell.  Reuse the
            # exact actionable-issue detail contract instead of maintaining a
            # second ambiguity/conflict layout inside that compatibility UI.
            presentation = item.issue_presentation
            options_section = sum(
                _evidence_section_count(evidence, 76)
                for evidence in presentation.evidence
            )
            fragments.extend(
                resolution_viewer_fragments(
                    view,
                    navigation,
                    focused_section=options_section,
                    option_navigation_active=bool(item.options),
                    other_direction_focused=other_direction_focused,
                )
            )
            continue
        if item.question:
            fragments.append(
                (
                    "",
                    f"       QUESTION · {safe_terminal_text(item.question)}\n",
                )
            )
        if item.options:
            fragments.append(("class:section", "       OPTIONS\n"))
            option_uids = tuple(option.uid for option in item.options)
            choice_state = FlatSelectionState(
                tuple(
                    SelectionOption(option.uid, option.label, option.text)
                    for option in item.options
                ),
                cursor_uid=(
                    navigation.option_cursor_uid
                    if navigation.option_cursor_uid in option_uids
                    else option_uids[0]
                ),
                selected_uid=navigation.selected_option_uid,
            )
            fragments.extend(
                render_vertical_choice_cards(
                    choice_state,
                    focused=True,
                    content_width=68,
                    indent="       ",
                )
            )
        for block in item.blocks:
            fragments.append(
                (
                    "class:section",
                    f"       {safe_terminal_text(block.heading)}\n",
                )
            )
            fragments.append(
                (
                    "",
                    _indented(safe_terminal_text(block.text)) + "\n",
                )
            )
    if view.show_results:
        fragments.extend(
            [
                ("", "\n"),
                (
                    "class:report-label",
                    f" {safe_terminal_text(view.results_label)}\n",
                ),
            ]
        )
        if not view.results:
            fragments.append(("", "  (none)\n"))
        for index, result in enumerate(view.results, start=1):
            fragments.append(
                (
                    "",
                    (
                        f"  {safe_terminal_text(result.marker)} {index:>2}. "
                        f"[{safe_terminal_text(result.label)}] "
                        f"{_line(result.text, 120)}\n"
                    ),
                )
            )
            if result.reason:
                fragments.append(
                    (
                        "",
                        f"       WHY · {safe_terminal_text(result.reason)}\n",
                    )
                )
    return fragments


def render_resolution_workbench_snapshot(
    view: ResolutionWorkbenchView,
    *,
    navigation: ResolutionNavigation | None = None,
) -> str:
    """Render the common workbench without ANSI or terminal interaction."""
    current_navigation = navigation or ResolutionNavigation()
    return "".join(
        text
        for _style, text in resolution_workbench_fragments(
            view,
            current_navigation,
        )
    ).rstrip()


def resolution_viewer_fragments(
    view: ResolutionWorkbenchView,
    navigation: ResolutionNavigation,
    *,
    focused_section: int = 0,
    option_navigation_active: bool = False,
    other_direction_focused: bool = False,
    other_direction_editing: bool = False,
    inline_action: SessionTodoView | None = None,
    expanded_memory_section_uid: str | None = None,
    nested_source_memory_uid: str | None = None,
    nested_source_memory_line: int = 0,
    include_response_sections: bool = True,
    content_width: int = 76,
) -> list[tuple[str, str]]:
    """Render one issue as a compact, section-navigable detail surface."""
    navigation.sync(view)
    fragments: list[tuple[str, str]] = []
    item = navigation.current_item(view)
    if item is None:
        fragments.append(("[SetCursorPosition]", ""))
        fragments.append(("class:section", f" {safe_terminal_text(view.list_label)}\n"))
        fragments.append(("", f"  {safe_terminal_text(view.empty_message)}\n"))
        return fragments

    presentation = item.issue_presentation
    section_count = (
        (
            sum(
                _evidence_section_count(evidence, content_width)
                for evidence in presentation.evidence
            )
            + (bool(item.question or item.options) if include_response_sections else 0)
            + sum(len(block.memory_rows) or 1 for block in item.blocks)
            + (1 if include_response_sections else 0)
            + bool(inline_action)
        )
        if presentation is not None
        else (
            1
            + sum(len(block.memory_rows) or 1 for block in item.blocks)
            + bool(item.evidence_refs)
            + (bool(item.question) if include_response_sections else 0)
            + (bool(item.options) if include_response_sections else 0)
            + (bool(item.commentable) if include_response_sections else 0)
        )
    )
    focused_section = max(0, min(focused_section, section_count - 1))
    section_index = 0

    def report_section(
        parts: list[tuple[str, str]],
        *,
        anchor: str = "both",
        focus_indices: tuple[int, ...] | None = None,
    ) -> None:
        nonlocal section_index
        active = section_index == focused_section
        fragments.extend(
            semantic_viewer_block_fragments(
                parts,
                active=active,
                anchor=anchor,
                focus_indices=focus_indices,
            )
        )
        section_index += 1

    def options_card(
        *,
        heading: str = "OPTIONS",
        other_label: str = "Other direction",
        other_text: str = "Press Enter and write a different resolution here.",
        prompt_heading: str = "",
        prompt_text: str = "",
    ) -> None:
        nonlocal section_index
        active = section_index == focused_section
        parts: list[tuple[str, str]] = []
        if prompt_heading:
            parts.extend(
                [
                    (
                        "class:block-heading",
                        f" {safe_terminal_text(prompt_heading)}\n",
                    ),
                    ("", f" {safe_terminal_text(prompt_text)}\n"),
                ]
            )
        parts.append(("class:block-heading", f" {safe_terminal_text(heading)}\n"))
        guidance = (
            "↑/↓ move · Enter select · Esc/Backspace back"
            if option_navigation_active
            else "Enter to choose an option"
        )
        parts.append(("", f" {guidance}\n"))
        other_uid = "__memcommit_legacy_other__"
        if any(option.uid == other_uid for option in item.options):
            raise ValueError("Resolution option UID collides with the Other control.")
        options = tuple(
            SelectionOption(option.uid, option.label, option.text)
            for option in item.options
        ) + (SelectionOption(other_uid, other_label, other_text),)
        option_uids = tuple(option.uid for option in item.options)
        cursor_uid = (
            other_uid
            if other_direction_focused
            else navigation.option_cursor_uid
            if navigation.option_cursor_uid in option_uids
            else option_uids[0]
        )
        choice_state = FlatSelectionState(
            options,
            cursor_uid=cursor_uid,
            selected_uid=navigation.selected_option_uid,
        )
        parts.extend(
            render_vertical_choice_cards(
                choice_state,
                focused=active and option_navigation_active,
                content_width=max(12, content_width - 2),
                indent=" ",
            )
        )
        fragments.extend(
            semantic_viewer_block_fragments(
                parts,
                active=active,
                # Nested option cards own their viewport position once opened.
                # Before that, keep the combined question/choice section at
                # its heading rather than jumping to its bottom.
                anchor="end" if option_navigation_active else "start",
            )
        )
        fragments.append(("", "\n"))
        section_index += 1

    item_index = next(
        (
            index
            for index, candidate in enumerate(view.items, start=1)
            if candidate.uid == item.uid
        ),
        1,
    )
    if presentation is not None:
        required_count = sum(
            candidate.effective_obligation == "REQUIRED" for candidate in view.items
        )
        optional_count = sum(
            candidate.effective_obligation == "OPTIONAL" for candidate in view.items
        )
        # This identifies the opened review target; it is report chrome, not
        # an actionable section. Keep the cursor on Classification when the
        # detail opens instead of making the user move past its title.
        fragments.extend(
            [
                (
                    "class:section",
                    (f"\n {_item_kind_label(item)} {item_index}/{len(view.items)}\n"),
                ),
                ("class:case-title", f" {safe_terminal_text(item.title)}\n"),
                (
                    "",
                    (
                        f" [{safe_terminal_text(item.priority)}] "
                        f"{safe_terminal_text(item.status)}\n"
                    ),
                ),
                (
                    "",
                    (
                        f" REVIEW SET · REQUIRED {required_count} · "
                        f"OPTIONAL {optional_count}\n"
                    ),
                ),
            ]
        )
        for evidence_index, evidence in enumerate(presentation.evidence):
            classification_parts: list[tuple[str, str]] = []
            if evidence.group_heading:
                classification_parts.append(
                    (
                        "class:block-heading",
                        f" {safe_terminal_text(evidence.group_heading)}\n",
                    )
                )
            classification_heading_index = len(classification_parts)
            classification_parts.extend(
                [
                    (
                        "class:block-heading",
                        (
                            "\n CLASSIFICATION\n"
                            if evidence.group_heading
                            else " CLASSIFICATION\n"
                        ),
                    ),
                    (
                        "class:viewer-body",
                        f" {safe_terminal_text(evidence.classification)}\n",
                    ),
                ]
            )
            report_section(
                classification_parts,
                # The optional evidence-group heading is structural chrome.
                # Focus identifies Classification and its value only.
                focus_indices=(
                    classification_heading_index,
                    classification_heading_index + 1,
                ),
            )
            for criterion in evidence.criterion_blocks:
                report_section(
                    semantic_detail_block_fragments(
                        heading=criterion.heading,
                        text=criterion.text,
                        refs=criterion.refs,
                        memory_rows=criterion.memory_rows,
                    )
                )
            first_source_section = True
            for claim_index, claim in enumerate(evidence.source_groups):
                for source_index, source in enumerate(claim.sources):
                    lines = _source_memory_lines(source.content, content_width)
                    source_section_uid = (
                        f"ITEM:{item.uid}:EVIDENCE:{evidence_index}:SOURCE:"
                        f"{claim_index}:{source.memory_uid}"
                    )
                    nested_reading = nested_source_memory_uid == source_section_uid
                    source_parts: list[tuple[str, str]] = []
                    source_group_heading_index: int | None = None
                    if first_source_section:
                        source_group_heading_index = len(source_parts)
                        source_parts.append(
                            (
                                "class:block-heading",
                                (
                                    f"\n {safe_terminal_text(evidence.sources_heading)}\n"
                                ),
                            )
                        )
                        first_source_section = False
                    if source_index == 0:
                        source_parts.append(
                            (
                                "class:block-heading",
                                (
                                    f"\n {safe_terminal_text(claim.label)} · FROM "
                                    f"{safe_terminal_text(claim.context_name)}\n"
                                ),
                            )
                        )
                    for line_index, line in enumerate(lines):
                        if nested_reading and line_index == min(
                            nested_source_memory_line,
                            len(lines) - 1,
                        ):
                            source_parts.append(("[SetCursorPosition]", ""))
                        source_parts.extend(
                            [
                                (
                                    "",
                                    (
                                        "   "
                                        f"[{safe_terminal_text(source.memory_uid[:8])}] "
                                        if line_index == 0
                                        else "              "
                                    ),
                                ),
                                ("class:memory-object", f"{line}\n"),
                            ]
                        )
                    source_focus_indices = tuple(
                        index
                        for index, (style, _text) in enumerate(source_parts)
                        if style in {"class:block-heading", "class:memory-object"}
                        and index != source_group_heading_index
                    )
                    report_section(
                        source_parts,
                        anchor="start" if nested_reading else "both",
                        # SOURCE MEMORY/SOURCE CLAIMS is a non-interactive group
                        # label; the exact claim/card below it owns focus.
                        focus_indices=source_focus_indices,
                    )
            report_section(
                [
                    (
                        "class:block-heading",
                        f"\n {safe_terminal_text(evidence.reason_heading)}\n",
                    ),
                    (
                        "class:viewer-body",
                        f" {safe_terminal_text(evidence.reason)}\n",
                    ),
                ]
            )
        if include_response_sections and item.options:
            options_card(
                heading=presentation.options_heading,
                other_label=presentation.other_option_label,
                other_text=("Press Enter and write a different answer here."),
                prompt_heading=(presentation.prompt_heading if item.question else ""),
                prompt_text=item.question,
            )
        elif include_response_sections and item.question:
            report_section(
                semantic_detail_block_fragments(
                    heading=presentation.prompt_heading,
                    text=item.question,
                )
            )
        for block_index, block in enumerate(item.blocks):
            if not block.memory_rows:
                report_section(
                    semantic_detail_block_fragments(
                        heading=block.heading,
                        text=block.text,
                        refs=block.refs,
                    )
                )
                continue
            for row_index, row in enumerate(block.memory_rows):
                section_uid = _memory_row_section_uid(
                    item.uid,
                    block_index,
                    row,
                )
                parts = (
                    [("class:block-heading", f" {safe_terminal_text(block.heading)}\n")]
                    if row_index == 0
                    else []
                )
                parts.extend(
                    semantic_memory_row_fragments(
                        row,
                        expanded=expanded_memory_section_uid == section_uid,
                    )
                )
                report_section(parts)
        if include_response_sections:
            report_section(
                [
                    ("class:detail-heading", "\n RESPONSE\n"),
                    (
                        "",
                        (
                            " Editing below · Enter save · Ctrl-J newline\n"
                            if other_direction_editing
                            else " Enter to write a response.\n"
                        ),
                    ),
                ]
            )
        if inline_action is not None:
            report_section(
                [
                    (
                        "class:detail-heading",
                        f"\n {safe_terminal_text(inline_action.kind)}\n",
                    ),
                    (
                        "",
                        f" {safe_terminal_text(inline_action.detail)}\n",
                    ),
                ]
            )
        return fragments
    required_count = sum(
        candidate.effective_obligation == "REQUIRED" for candidate in view.items
    )
    optional_count = sum(
        candidate.effective_obligation == "OPTIONAL" for candidate in view.items
    )
    review_set_fragments = (
        [
            (
                "",
                (
                    f" REVIEW SET · REQUIRED {required_count} · "
                    f"OPTIONAL {optional_count}\n"
                ),
            )
        ]
        if all(
            candidate.priority in {"REQUIRED", "HELPFUL", "OPTIONAL"}
            for candidate in view.items
        )
        else []
    )
    report_section(
        semantic_detail_header_fragments(
            label=(
                f"REVIEW DETAIL · {item_index}/{len(view.items)} · "
                f"{item.priority} · {_item_kind_label(item)} · {item.status}"
            ),
            title=item.title,
            why_heading="WHY THIS NEEDS REVIEW",
            why=item.summary,
        )
        + review_set_fragments
    )
    for block_index, block in enumerate(item.blocks[: item.decision_block_index]):
        if not block.memory_rows:
            report_section(
                semantic_detail_block_fragments(
                    heading=block.heading,
                    text=block.text,
                    refs=block.refs,
                )
            )
            continue
        for row_index, row in enumerate(block.memory_rows):
            section_uid = _memory_row_section_uid(item.uid, block_index, row)
            parts = (
                [("class:block-heading", f" {safe_terminal_text(block.heading)}\n")]
                if row_index == 0
                else []
            )
            parts.extend(
                semantic_memory_row_fragments(
                    row,
                    expanded=expanded_memory_section_uid == section_uid,
                )
            )
            report_section(parts)
    if include_response_sections and item.question:
        report_section(
            semantic_detail_block_fragments(
                heading="QUESTION",
                text=item.question,
            )
        )
    if include_response_sections and item.options:
        options_card()
    for block_index, block in enumerate(
        item.blocks[item.decision_block_index :],
        start=item.decision_block_index,
    ):
        if not block.memory_rows:
            report_section(
                semantic_detail_block_fragments(
                    heading=block.heading,
                    text=block.text,
                    refs=block.refs,
                )
            )
            continue
        for row_index, row in enumerate(block.memory_rows):
            section_uid = _memory_row_section_uid(item.uid, block_index, row)
            parts = (
                [("class:block-heading", f" {safe_terminal_text(block.heading)}\n")]
                if row_index == 0
                else []
            )
            parts.extend(
                semantic_memory_row_fragments(
                    row,
                    expanded=expanded_memory_section_uid == section_uid,
                )
            )
            report_section(parts)
    if item.evidence_refs:
        report_section(
            semantic_trace_fragments(
                evidence_refs=item.evidence_refs,
                judgment_refs=item.judgment_refs,
                outcome_refs=item.outcome_refs,
                unresolved_refs=item.unresolved_refs,
            )
        )
    if include_response_sections and item.commentable:
        report_section(
            [
                ("class:detail-heading", "\n RESPONSE\n"),
                (
                    "",
                    (
                        " Editing below · Enter save · Ctrl-J newline\n"
                        if other_direction_editing
                        else " Enter to comment on this proposed change.\n"
                    ),
                ),
            ]
        )
    return fragments


def resolution_report_fragments(
    view: ResolutionWorkbenchView,
    *,
    strategies: tuple[ResolutionGlobalStrategy, ...] = (),
    drafts: dict[str, ResponseDraft] | None = None,
    focused_section: int = 0,
    review_and_apply: bool = False,
    read_only: bool = False,
    impact_controller: ImpactController | None = None,
    expanded_impact_section_uid: str | None = None,
    content_width: int = 76,
) -> list[tuple[str, str]]:
    """Render the complete Meld reading surface before any individual issue."""
    metric_text = " · ".join(
        f"{safe_terminal_text(metric.value)} {safe_terminal_text(metric.label)}"
        for metric in view.metrics
    )
    impact = _current_impact(impact_controller, view)
    # ImpactController.from_resolution projects the exact same result rows,
    # with their rationale. Rendering both copies becomes unusable for large
    # sessions, so the richer Impact block is their single report location.
    impact_repeats_results = _impact_repeats_results(impact, view)
    show_results = view.show_results and not impact_repeats_results
    review_sections = 1 if view.report_items_summary is not None else len(view.items)
    overview_sections = view.semantic_overview_sections
    section_count = (
        review_sections
        + len(overview_sections)
        + (not read_only)
        + show_results
        + (impact is not None)
        + (len(impact.entries) if impact is not None else 0)
    )
    focused_section = max(0, min(focused_section, section_count - 1))
    section_index = 0
    fragments: list[tuple[str, str]] = []
    draft_values = drafts or {}

    def heading(text: str, *, style: str = "class:section") -> None:
        nonlocal section_index
        active = section_index == focused_section
        fragments.extend(
            semantic_viewer_block_fragments(
                [(style, f" {safe_terminal_text(text)}\n")],
                active=active,
            )
        )
        section_index += 1

    def section_block(
        block_fragments: list[tuple[str, str]],
        *,
        focus_indices: tuple[int, ...] | None = None,
    ) -> None:
        """Render one report stop whose semantic content may span paragraphs."""

        nonlocal section_index
        active = section_index == focused_section
        fragments.extend(
            semantic_viewer_block_fragments(
                block_fragments,
                active=active,
                focus_indices=focus_indices,
            )
        )
        section_index += 1

    # Report identity and endpoint metadata orient the reader but are not
    # semantic inspection targets. Initial Viewer focus therefore lands on
    # the first operation-declared overview section.
    fragments.append(("class:title", f" {safe_terminal_text(view.title)}\n"))
    if view.context_locations:
        fragments.append(("class:section", " CONTEXT LOCATIONS\n"))
        for location in view.context_locations:
            fragments.append(
                (
                    "",
                    f"   {safe_terminal_text(location.role)} · "
                    f"{safe_terminal_text(location.name)}"
                    + (
                        f" · {safe_terminal_text(location.state)}"
                        if location.state
                        else ""
                    )
                    + "\n",
                )
            )
    else:
        fragments.append(("", f" {safe_terminal_text(view.route)}\n"))
    fragments.append(
        (
            "",
            f" {safe_terminal_text(view.status)}"
            + (f" · {metric_text}" if metric_text else "")
            + "\n\n",
        )
    )
    for overview_section in overview_sections:
        active = section_index == focused_section
        fragments.extend(
            semantic_viewer_block_fragments(
                [
                    (
                        "class:block-heading",
                        f" {safe_terminal_text(overview_section.heading)}\n",
                    ),
                    (
                        "class:viewer-body",
                        f" {safe_terminal_text(overview_section.text) or '(none)'}\n\n",
                    ),
                ],
                active=active,
                focus_indices=((0, 1) if overview_section.focus_body else (0,)),
            )
        )
        section_index += 1
    if view.report_items_summary is not None:
        section_block(
            [
                (
                    "class:section",
                    f" {safe_terminal_text(view.report_items_summary.heading)}\n",
                ),
                (
                    "class:viewer-body",
                    f" {safe_terminal_text(view.report_items_summary.text)}\n\n",
                ),
            ],
            focus_indices=(0, 1),
        )
    else:
        # The collection label is report chrome. Individual operation items
        # are the independently reviewable focus stops beneath it.
        fragments.append(
            (
                "class:report-label",
                f" {safe_terminal_text(view.list_label)} · {len(view.items)}\n",
            )
        )
        if not view.items:
            fragments.append(("", f"  {safe_terminal_text(view.empty_message)}\n"))
        for index, item in enumerate(view.items, start=1):
            if item.compact_row_suffix is not None:
                item_fragments = [
                    (
                        "class:memory-object",
                        " "
                        + safe_terminal_text(
                            render_numbered_content_row(
                                index,
                                item.title,
                                suffix=item.compact_row_suffix,
                            )
                        )
                        + "\n",
                    )
                ]
            else:
                item_fragments = [
                    (
                        "class:report-label",
                        " "
                        + safe_terminal_text(
                            f"{_item_kind_label(item)} {index} · {item.title}"
                        )
                        + "\n",
                    ),
                    (
                        "class:viewer-body",
                        (
                            f" [{safe_terminal_text(item.priority)}] "
                            if item.show_summary_priority
                            else " "
                        )
                        + f"{safe_terminal_text(item.summary)}\n",
                    ),
                ]
            if item.question:
                item_fragments.append(
                    (
                        "class:viewer-body",
                        f" QUESTION · {safe_terminal_text(item.question)}\n\n",
                    )
                )
            else:
                item_fragments.append(("", "\n"))
            section_block(
                item_fragments,
                focus_indices=tuple(range(len(item_fragments))),
            )
    if show_results:
        heading(
            f"{view.results_label} · {len(view.results)}",
            style="class:report-label",
        )
        if not view.results:
            fragments.append(("", "  (none)\n"))
        for index, result in enumerate(view.results, start=1):
            fragments.append(
                (
                    "",
                    f"  {safe_terminal_text(result.marker)} {index}. "
                    f"[{safe_terminal_text(result.label)}] "
                    f"{safe_terminal_text(result.text)}\n",
                )
            )
    if impact is not None:
        heading(impact.title)
        fragments.append(("", f" {safe_terminal_text(impact.summary)}\n"))
        if any(entry.reason for entry in impact.entries):
            fragments.append(
                (
                    "",
                    " Focus a Memory: → shows why, ← hides it, and Enter toggles.\n",
                )
            )
        if impact.detail:
            fragments.append(("", f"\n {safe_terminal_text(impact.detail)}\n"))
        treatment_width = max(
            (
                _visual_width(f"[{safe_terminal_text(entry.label)}]")
                for entry in impact.entries
            ),
            default=0,
        )
        for index, entry in enumerate(impact.entries, start=1):
            entry_section_uid = _impact_entry_section_uid(entry, index)
            active = section_index == focused_section
            expandable = bool(entry.rules or entry.reason)
            expanded = expandable and expanded_impact_section_uid == entry_section_uid
            disclosure = "▾" if expanded else "▸" if expandable else "·"
            prefix = navigable_tree_row_prefix(
                selected=active,
                depth=1,
                branch=f"{disclosure} {entry.marker}",
            )
            treatment = f"[{safe_terminal_text(entry.label)}]"
            treatment_field = _visual_pad(treatment, treatment_width)
            uid_field = f"[{safe_terminal_text(entry.uid[:8] or str(index))}]"
            identity = f"{treatment_field} " + (
                f"{safe_terminal_text(entry.location)} {uid_field}"
                if entry.location
                else f"{uid_field} "
            )
            content_indent = " " * (_visual_width(prefix) + 2)
            row_content_width = max(
                12,
                content_width - _visual_width(content_indent) - 3,
            )
            treatment_style = _impact_treatment_style(
                entry.label,
                focused=active,
            )
            if entry.location:
                # Located diff rationale is explanatory report prose, not a
                # Memory object. Keep it neutral while the Context/Memory
                # identity above retains the shared lavender treatment.
                expanded_detail_style = ""
                fragments.extend(
                    [
                        (treatment_style, f" {prefix}{treatment_field} "),
                        (
                            "class:memory-object",
                            f"{safe_terminal_text(entry.location)} {uid_field}\n",
                        ),
                    ]
                )
                change = MemoryChange(
                    marker=entry.marker,
                    treatment=entry.label,
                    location=entry.location,
                    memory_uid=entry.uid or str(index),
                    before=entry.before,
                    after=entry.after,
                    reason=entry.reason,
                    rules=entry.rules,
                )
                for diff_line in memory_diff_lines(change):
                    marker = diff_line.marker
                    diff_prefix = f"{content_indent}{marker} "
                    style_key = {
                        "-": "remove",
                        "+": "add",
                        "=": "equal",
                        " ": "equal",
                    }[marker]
                    for line_index, content_spans in enumerate(
                        _visual_wrap_diff_spans(diff_line.spans, row_content_width)
                    ):
                        lead = (
                            diff_prefix
                            if line_index == 0
                            else " " * _visual_width(diff_prefix)
                        )
                        fragments.append((f"class:memory-diff.{style_key}", f" {lead}"))
                        for content_text, changed in content_spans:
                            fragments.append(
                                (
                                    f"class:memory-diff.{style_key}"
                                    + (".changed" if changed else ""),
                                    content_text,
                                )
                            )
                        fragments.append(("", "\n"))
                if change.before is None or change.after is None:
                    # A one-sided ADD/REMOVE has half the visual body of an
                    # EDIT. One trailing spacer preserves comparable grouping
                    # without fabricating a missing before/after line.
                    fragments.append(("", "\n"))
            else:
                # Legacy result rows keep treatment-colored focus to bind
                # their UID, content, and expanded basis together.
                style = (
                    f"{treatment_style}.focused" if active else "class:memory-object"
                )
                expanded_detail_style = style
                legacy_indent = " " * _visual_width(prefix + identity)
                legacy_width = max(
                    12,
                    content_width - _visual_width(prefix + identity) - 1,
                )
                content_indent = legacy_indent
                for line_index, content_line in enumerate(
                    _visual_wrap(entry.text, legacy_width)
                ):
                    if line_index == 0:
                        fragments.extend(
                            [
                                (treatment_style, f" {prefix}{treatment_field} "),
                                (style, f"{uid_field} {content_line}\n"),
                            ]
                        )
                    else:
                        fragments.append((style, f" {content_indent}{content_line}\n"))
            if expanded:
                for rule in entry.rules:
                    rule_prefix = content_indent + "RULE · "
                    rule_width = max(
                        12,
                        content_width - _visual_width(rule_prefix) - 1,
                    )
                    for line_index, rule_line in enumerate(
                        _visual_wrap(rule, rule_width)
                    ):
                        lead = (
                            rule_prefix
                            if line_index == 0
                            else " " * _visual_width(rule_prefix)
                        )
                        fragments.append(
                            (expanded_detail_style, f" {lead}{rule_line}\n")
                        )
            if entry.reason and expanded:
                reason_prefix = content_indent + "WHY · "
                reason_width = max(
                    12,
                    content_width - _visual_width(reason_prefix) - 1,
                )
                for line_index, reason_line in enumerate(
                    _visual_wrap(entry.reason, reason_width)
                ):
                    lead = (
                        reason_prefix
                        if line_index == 0
                        else " " * _visual_width(reason_prefix)
                    )
                    fragments.append((expanded_detail_style, f" {lead}{reason_line}\n"))
            comment_item = _impact_entry_item(view, entry)
            if (
                expanded
                and not read_only
                and comment_item is not None
                and comment_item.commentable
            ):
                saved_comment = _item_draft(comment_item, draft_values).text
                comment_text = (
                    f"SAVED · {saved_comment.strip()}"
                    if saved_comment.strip()
                    else "Press C to comment on this proposed change."
                )
                comment_prefix = content_indent + "RESPONSE · "
                comment_width = max(
                    12,
                    content_width - _visual_width(comment_prefix) - 1,
                )
                for line_index, comment_line in enumerate(
                    _visual_wrap(comment_text, comment_width)
                ):
                    lead = (
                        comment_prefix
                        if line_index == 0
                        else " " * _visual_width(comment_prefix)
                    )
                    fragments.append(
                        (expanded_detail_style, f" {lead}{comment_line}\n")
                    )
            if active:
                # Anchor after the complete row so wrapped or expanded detail
                # remains visible as one semantic Impact Memory.
                fragments.append(("[SetCursorPosition]", ""))
            section_index += 1
    if not read_only:
        action_heading = "RESOLVE ALL · WHOLE-SET STRATEGY"
        action_detail = (
            "Choose a strategy below. It requests a revised proposal and "
            "never applies the target."
        )
        show_strategies = True
        if review_and_apply:
            action_heading, action_detail, show_strategies = _report_action(
                view,
                draft_values,
                strategies,
            )
        section_block(
            [
                ("class:section", f" {safe_terminal_text(action_heading)}\n"),
                ("class:viewer-body", f" {safe_terminal_text(action_detail)}\n"),
            ],
            focus_indices=(0, 1),
        )
        if show_strategies:
            for index, item in enumerate(strategies):
                fragments.append(
                    (
                        "class:choice",
                        f"   {index + 1}. {safe_terminal_text(item.label)}\n",
                    )
                )
    return fragments


def _seeded_report_lines(
    view: ResolutionWorkbenchView,
    report_text: str,
    strategies: tuple[ResolutionGlobalStrategy, ...],
    review_and_apply: bool = False,
    read_only: bool = False,
    impact_controller: ImpactController | None = None,
    drafts: dict[str, ResponseDraft] | None = None,
) -> list[str]:
    lines = report_text.splitlines()
    if view.context_locations:
        location_lines = ["", "CONTEXT LOCATIONS"]
        location_lines.extend(
            f"  {location.role} · {location.name}"
            + (f" · {location.state}" if location.state else "")
            for location in view.context_locations
        )
        insert_at = 1 if lines else 0
        lines[insert_at:insert_at] = location_lines
    if view.show_results:
        lines.extend(["", f"{view.results_label} · {len(view.results)}"])
        if view.results:
            for index, result in enumerate(view.results, start=1):
                lines.extend(
                    [
                        "",
                        f"  {result.marker} {index}. [{result.label}]",
                        f"      {result.text}",
                    ]
                )
                if result.reason:
                    lines.append(f"      WHY · {result.reason}")
        else:
            lines.append("  (none)")
    impact = _current_impact(impact_controller, view)
    if impact is not None:
        lines.extend(["", *_impact_lines(impact)])
    if not read_only:
        action_heading = "RESOLVE ALL · WHOLE-SET STRATEGY"
        action_detail = (
            "Choose a strategy below. It requests a revised proposal and "
            "never applies the target."
        )
        show_strategies = True
        if review_and_apply:
            action_heading, action_detail, show_strategies = _report_action(
                view,
                drafts or {},
                strategies,
            )
        lines.extend(
            [
                "",
                action_heading,
                action_detail,
            ]
        )
        if show_strategies:
            lines.extend(
                f"  {index}. {item.label}"
                for index, item in enumerate(strategies, start=1)
            )
    return lines


def _seeded_report_sections(lines: list[str]) -> tuple[tuple[int, str], ...]:
    """Map Compare headings and conflict paragraphs to Meld navigation rows."""
    headings = (
        "MEM COMPARE ·",
        "WHAT MEM UNDERSTOOD",
        "WHAT BOTH CONTAIN",
        "WHAT DIFFERS",
        "ONLY IN ",
        "POTENTIAL CONFLICTS",
        "PROPOSED TARGET MEMORIES",
        "PROPOSED BASELINE CHANGES",
        "RESOLVE ALL ·",
        "RESOLVE",
        "REVIEW AND APPLY",
        "APPLY CONFIRMATION",
        "INCORPORATE RESPONSES",
        "IMPACT ·",
        "APPLY CHANGES ·",
        "APPLY AS IS ·",
    )
    sections: list[tuple[int, str]] = []
    in_conflicts = False
    in_results = False
    conflict_index = 0
    for line_index, line in enumerate(lines):
        if line.startswith("POTENTIAL CONFLICTS"):
            in_conflicts = True
            in_results = False
        if line.startswith(("PROPOSED TARGET MEMORIES", "PROPOSED BASELINE CHANGES")):
            in_conflicts = False
            in_results = True
        if line.startswith(
            (
                "RESOLVE ALL ·",
                "RESOLVE",
                "REVIEW AND APPLY",
                "APPLY CONFIRMATION",
                "INCORPORATE RESPONSES",
                "APPLY CHANGES ·",
                "APPLY AS IS ·",
            )
        ):
            in_results = False
        if line.startswith(headings):
            key = (
                "RESOLVE_ALL"
                if line.startswith(
                    (
                        "RESOLVE ALL ·",
                        "RESOLVE",
                        "REVIEW AND APPLY",
                        "APPLY CONFIRMATION",
                        "INCORPORATE RESPONSES",
                        "APPLY CHANGES ·",
                        "APPLY AS IS ·",
                    )
                )
                else "REPORT"
            )
            sections.append((line_index, key))
            continue
        stripped = line.strip()
        result_prefix = stripped.split(".", 1)[0]
        if (
            in_results
            and len(result_prefix) > 2
            and result_prefix[0] in {"+", "~"}
            and result_prefix[1:].strip().isdigit()
        ):
            result_index = int(result_prefix[1:].strip()) - 1
            sections.append((line_index, f"RESULT:{result_index}"))
            continue
        prefix = line.split(".", 1)[0]
        if in_conflicts and prefix.isdigit():
            conflict_index += 1
            sections.append((line_index, f"ITEM:{conflict_index - 1}"))
    return tuple(sections)


def resolution_seeded_report_fragments(
    view: ResolutionWorkbenchView,
    report_text: str,
    *,
    report_fragments: tuple[tuple[str, str], ...] | None = None,
    strategies: tuple[ResolutionGlobalStrategy, ...] = (),
    drafts: dict[str, ResponseDraft] | None = None,
    report_item_badges: tuple[str, ...] = (),
    report_conflicts_remaining: int | None = None,
    selected_strategy_index: int = 0,
    focused_section: int = 0,
    review_and_apply: bool = False,
    read_only: bool = False,
    impact_controller: ImpactController | None = None,
    content_width: int = 76,
) -> list[tuple[str, str]]:
    """Render Compare and Meld report sections as nested Viewer cards."""
    if report_fragments is not None and "".join(
        text for _style, text in report_fragments
    ) != report_text:
        raise ValueError(
            "Seeded report fragments must preserve the exact plain report text."
        )
    lines = _seeded_report_lines(
        view,
        report_text,
        strategies,
        review_and_apply=review_and_apply,
        read_only=read_only,
        impact_controller=impact_controller,
        drafts=drafts,
    )
    seeded_text = "\n".join(lines)
    if report_fragments is not None and (
        seeded_text == report_text or seeded_text.startswith(report_text + "\n")
    ):
        styled = [
            (style, safe_terminal_text(text)) for style, text in report_fragments
        ]
        suffix = seeded_text[len(report_text) :]
        if suffix:
            styled.append(("", safe_terminal_text(suffix)))
        return styled
    sections = _seeded_report_sections(lines)
    if not sections:
        return [("", safe_terminal_text(seeded_text))]
    focused_section = max(0, min(focused_section, len(sections) - 1))
    draft_values = drafts or {}
    fragments: list[tuple[str, str]] = []

    section_index = 0
    while section_index < len(sections):
        start, key = sections[section_index]
        end = (
            sections[section_index + 1][0]
            if section_index + 1 < len(sections)
            else len(lines)
        )
        title = lines[start].strip()

        if title.startswith("POTENTIAL CONFLICTS"):
            original_count = sum(
                next_key.startswith("ITEM:") for _offset, next_key in sections
            )
            remaining = (
                original_count
                if report_conflicts_remaining is None
                else report_conflicts_remaining
            )
            group_title = f"POTENTIAL CONFLICTS · {original_count} → {remaining}"
            group_active = section_index == focused_section
            width = max(24, content_width - 1)
            inner_width = width - 2
            label = f"─ {_line(group_title, inner_width - 3)} "
            fragments.extend(
                semantic_viewer_block_fragments(
                    [
                        (
                            "class:detail-card",
                            f" ╭{label}{'─' * (inner_width - _visual_width(label))}╮\n",
                        )
                    ],
                    active=group_active,
                )
            )
            fragments.append(("class:detail-card", f" │{' ' * inner_width}│\n"))
            section_index += 1
            while section_index < len(sections) and sections[section_index][
                1
            ].startswith("ITEM:"):
                item_start, item_key = sections[section_index]
                item_end = (
                    sections[section_index + 1][0]
                    if section_index + 1 < len(sections)
                    else len(lines)
                )
                item_index = int(item_key.split(":", 1)[1])
                item_body = [
                    lines[item_start].strip().split(".", 1)[-1].lstrip(),
                    *lines[item_start + 1 : item_end],
                ]
                while item_body and not item_body[-1].strip():
                    item_body.pop()
                badge = ""
                if item_index < len(view.items):
                    item = view.items[item_index]
                    draft = _item_draft(item, draft_values)
                    option_uid, comment = draft.selected_choice_uid, draft.text
                    if option_uid is not None:
                        badge = f"SELECTED · {item.option(option_uid).label}"
                    elif comment.strip():
                        badge = "OTHER DIRECTION · STAGED"
                if not badge and item_index < len(report_item_badges):
                    badge = report_item_badges[item_index]
                if badge:
                    item_body = [badge, "", *item_body]
                item_active = section_index == focused_section
                conflict_heading = f"CONFLICT {item_index + 1}"
                item_fragments: list[tuple[str, str]] = [
                    ("class:section", f" │   {conflict_heading}\n")
                ]
                badge_visual_lines = (
                    _visual_wrap(badge, inner_width - 6) if badge else []
                )
                body_visual_lines = _visual_wrap(
                    "\n".join(item_body[(2 if badge else 0) :]),
                    inner_width - 6,
                )
                for badge_line in badge_visual_lines:
                    item_fragments.append(
                        (
                            "class:selection-badge",
                            f" │     {_visual_pad(badge_line, inner_width - 6)} │\n",
                        )
                    )
                if badge_visual_lines:
                    item_fragments.append(
                        ("class:detail-card", f" │{' ' * inner_width}│\n")
                    )
                for body_line in body_visual_lines:
                    item_fragments.append(
                        (
                            "class:detail-card",
                            f" │     {_visual_pad(body_line, inner_width - 6)} │\n",
                        )
                    )
                fragments.extend(
                    semantic_viewer_block_fragments(
                        item_fragments,
                        active=item_active,
                        anchor="end",
                        focus_indices=(0,),
                    )
                )
                section_index += 1
                if section_index < len(sections) and sections[section_index][
                    1
                ].startswith("ITEM:"):
                    fragments.append(("class:detail-card", f" │{' ' * inner_width}│\n"))
            fragments.append(("class:detail-card", f" ╰{'─' * inner_width}╯\n"))
            if section_index < len(sections):
                fragments.append(("", "\n"))
            continue

        if key.startswith("RESULT:"):
            active = section_index == focused_section
            result_index = int(key.split(":", 1)[1])
            result = view.results[result_index]
            prefix = navigable_tree_row_prefix(
                selected=active,
                depth=1,
                branch=result.marker,
            )
            identity = f"{result_index + 1:>3}. [{safe_terminal_text(result.label)}] "
            content_indent = " " * _visual_width(prefix + identity)
            result_content_width = max(
                12,
                content_width - _visual_width(prefix + identity) - 1,
            )
            wrapped_content = _visual_wrap(result.text, result_content_width)
            result_fragments: list[tuple[str, str]] = []
            for line_index, content_line in enumerate(wrapped_content):
                lead = prefix + identity if line_index == 0 else content_indent
                result_fragments.append(
                    ("class:memory-object", f" {lead}{content_line}\n")
                )
            if result.reason:
                reason_prefix = " " * _visual_width(prefix) + "    WHY · "
                reason_width = max(
                    12,
                    content_width - _visual_width(reason_prefix) - 1,
                )
                for line_index, reason_line in enumerate(
                    _visual_wrap(result.reason, reason_width)
                ):
                    lead = (
                        reason_prefix
                        if line_index == 0
                        else " " * _visual_width(reason_prefix)
                    )
                    result_fragments.append(
                        ("class:memory-object", f" {lead}{reason_line}\n")
                    )
            fragments.extend(
                semantic_viewer_block_fragments(
                    result_fragments,
                    active=active,
                    anchor="end",
                )
            )
            if section_index < len(sections) - 1:
                fragments.append(("", "\n"))
            section_index += 1
            continue

        if title.startswith(("PROPOSED TARGET MEMORIES", "PROPOSED BASELINE CHANGES")):
            active = section_index == focused_section
            fragments.extend(
                semantic_viewer_block_fragments(
                    [("class:report-label", f" {safe_terminal_text(title)}\n")],
                    active=active,
                )
            )
            fragments.append(("", "\n"))
            section_index += 1
            continue

        body_lines = list(lines[start + 1 : end])
        while body_lines and not body_lines[0].strip():
            body_lines.pop(0)
        while body_lines and not body_lines[-1].strip():
            body_lines.pop()

        badge = ""
        if key.startswith("ITEM:"):
            item_index = int(key.split(":", 1)[1])
            # The Compare paragraph is itself the conflict body; using it as
            # a card title would truncate the evidence-rich one-paragraph
            # summary that the report is meant to preserve.
            body_lines.insert(0, title.split(".", 1)[-1].lstrip())
            title = f"POTENTIAL CONFLICT {item_index + 1}"
            if item_index < len(view.items):
                item = view.items[item_index]
                draft = _item_draft(item, draft_values)
                option_uid, comment = draft.selected_choice_uid, draft.text
                if option_uid is not None:
                    badge = f"SELECTED · {item.option(option_uid).label}"
                elif comment.strip():
                    badge = "OTHER DIRECTION · STAGED"
        elif (
            key == "RESOLVE_ALL"
            and strategies
            and (
                not review_and_apply
                or session_review_action_view(
                    view,
                    draft_values,
                    whole_set_available=True,
                ).kind
                in {"INCORPORATE RESPONSES", "INCORPORATE AND APPLY"}
            )
        ):
            policy_index = max(0, min(selected_strategy_index, len(strategies) - 1))
            badge = f"POLICY · {strategies[policy_index].label}"
        if badge:
            # Keep the blue review state directly below the card title so a
            # long conflict paragraph cannot push the chosen reading offscreen.
            body_lines = [badge, "", *body_lines]

        active = section_index == focused_section
        card_width = max(24, content_width - 1)
        card_lines = boxed_lines(
            title,
            "\n".join(body_lines),
            width=card_width,
        )
        badge_line_count = (
            len(_visual_wrap(badge, max(1, card_width - 4))) if badge else 0
        )
        card_fragments: list[tuple[str, str]] = []
        for card_line_index, card_line in enumerate(card_lines):
            style = "class:detail-card"
            if badge and 1 <= card_line_index <= badge_line_count:
                style = "class:selection-badge"
            card_fragments.append((style, f" {safe_terminal_text(card_line)}\n"))
        fragments.extend(
            semantic_viewer_block_fragments(
                card_fragments,
                active=active,
                anchor="end",
                focus_indices=(0,),
            )
        )
        if section_index < len(sections) - 1:
            fragments.append(("", "\n"))
        section_index += 1
    return fragments


def resolution_review_fragments(
    view: ResolutionWorkbenchView,
    drafts: dict[str, ResponseDraft],
    strategies: tuple[ResolutionGlobalStrategy, ...],
    strategy_index: int,
    action: SessionTodoView,
    focused_section: int = 0,
    content_width: int = 76,
    review_title: str = "APPLY CONFIRMATION",
    command_review: ExactCommandReview | None = None,
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

    ready_without_open_reviews = (
        reviewable == 0 and action.kind in {"APPLY", "APPLY AS IS"}
    )
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
