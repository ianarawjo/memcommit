"""Shared list/detail/comment shell for semantic resolution adapters."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import (
    ConditionalContainer,
    DynamicContainer,
    FormattedTextControl,
    HSplit,
    Layout,
    Window,
)
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.widgets import Frame
from prompt_toolkit.utils import get_cwidth

from memcommit.application_review_policy import DecisionFreeBehavior
from memcommit.exact_command_review import ExactCommandReview
from memcommit.interfaces.tui.components.exact_command_review.rendering import (
    format_exact_command,
)
from memcommit.interfaces.tui.components.exact_name import (
    ExactNameFieldView,
    ExactNameInputControl,
)
from memcommit.interfaces.tui.components.report_card import boxed_lines
from memcommit.interfaces.tui.components.tree_row import navigable_tree_row_prefix
from memcommit.interfaces.tui.components.multiline_input import (
    build_framed_multiline_input,
)
from memcommit.interfaces.tui.components.plain_text_clipboard import (
    copy_plain_text,
    plain_text_from_fragments,
)
from memcommit.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
    focused_control_style,
)
from memcommit.interfaces.tui.core.keybindings import (
    NavigationAccelerator,
    bind_case_insensitive_key,
)
from memcommit.interfaces.tui.components.frame import (
    TuiRegion,
    bind_focused_frame_style,
    build_tui_frame,
)
from memcommit.interfaces.tui.components.scrollable_pane import (
    WrappedScrollbarMargin,
)
from memcommit.interfaces.console.content_row import render_numbered_content_row
from memcommit.interfaces.console.terminal import (
    require_interactive_terminal,
)
from memcommit.interfaces.console.text import (
    safe_terminal_text,
)
from memcommit.interfaces.tui.core.text_layout import (
    elide_terminal_text,
    single_line_terminal_text,
    terminal_cell_width,
    wrap_terminal_text,
)
from memcommit.interfaces.tui.components.save_location import (
    SaveLocationEditorState,
    SaveLocationView,
    save_location_row_fragments,
    save_location_tree_fragments,
)
from memcommit.interfaces.tui.components.session_help import bind_session_help
from memcommit.interfaces.tui.workbenches.resolution.compact_shell import (
    run_compact_resolution_decisions,
)
from memcommit.interfaces.tui.viewers.semantic.detail import (
    semantic_detail_block_fragments,
    semantic_detail_header_fragments,
    semantic_memory_row_fragments,
    semantic_trace_fragments,
)
from memcommit.interfaces.tui.viewers.semantic import (
    SemanticViewerController,
    deactivate_semantic_viewer_fragments,
    semantic_viewer_block_fragments,
)
from memcommit.interfaces.tui.components.focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    SurfaceMoveResult,
    bind_surface_navigation,
)
from memcommit.impact_controller import ImpactController, ImpactView
from memcommit.memory_diff import MemoryChange, MemoryDiffSpan, memory_diff_lines
from memcommit.resolution_workbench import (
    ResolutionNavigation,
    ResolutionWorkbenchAction,
    ResolutionWorkbenchError,
    ResolutionItem,
    ResolutionMemoryRow,
    ResolutionWorkbenchView,
)
from memcommit.responses.model import ResponseDraft, ResponseTarget
from memcommit.responses.resolution import (
    response_draft_from_item,
    response_target_from_item,
)
from memcommit.study_action_log import record_study_action
from memcommit.responses.state import ResponseFrameState
from memcommit.responses.tui import response_frame_fragments
from memcommit.selection.model import SelectionOption
from memcommit.selection.state import FlatSelectionState
from memcommit.selection.tui import render_vertical_choice_cards
from memcommit.session_workbench_navigation import (
    SessionWorkbenchNavigation,
    WorkbenchSection,
    WorkbenchPane,
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


@dataclass(frozen=True)
class _FinalReviewOrigin:
    """Exact process-local focus state to restore after final review."""

    viewer_kind: str
    pane: WorkbenchPane
    row_index: int
    viewer_row_index: int
    section_uid: str | None


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
        if item.commentable and _item_draft(item, drafts).text.strip()
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
        fragments.append(("class:section", " WHAT MEM UNDERSTOOD\n"))
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
    fragments.append(("class:section", " WHAT MEM UNDERSTOOD\n"))
    if not overview_sections:
        fragments.append(("", " (none)\n\n"))
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


def run_resolution_workbench_shell(
    view_or_supplier: (ResolutionWorkbenchView | Callable[[], ResolutionWorkbenchView]),
    *,
    navigation: ResolutionNavigation | None = None,
    workbench_navigation: SessionWorkbenchNavigation | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    terminal_label: str = "Interactive resolution workbench",
    snapshot_hint: str = (
        "Run the same command outside a TTY to render its saved snapshot."
    ),
    draft_loader: (Callable[[str], tuple[str | None, str]] | None) = None,
    draft_saver: (Callable[[str, str | None, str], None] | None) = None,
    response_validator: Callable[[str], None] | None = None,
    save_draft_on_close: bool = False,
    toggle_sort: Callable[[], None] | None = None,
    split_viewer_items: bool = False,
    global_strategies: tuple[ResolutionGlobalStrategy, ...] = (),
    split_report_text: str | None = None,
    split_report_fragments: tuple[tuple[str, str], ...] | None = None,
    split_report_item_badges: tuple[str, ...] = (),
    split_report_conflicts_remaining: int | None = None,
    review_and_apply: bool = False,
    start_final_review_when_no_required: bool = False,
    decision_free_behavior: DecisionFreeBehavior | None = None,
    read_only: bool = False,
    read_only_handoff: SessionTodoView | None = None,
    item_handoff: SessionTodoView | None = None,
    impact_controller: ImpactController | None = None,
    destination: ResolutionDestination | None = None,
    turn_command_review: (
        Callable[[ResolutionWorkbenchAction], ExactCommandReview | None] | None
    ) = None,
    compact_decisions: bool = False,
) -> ResolutionWorkbenchAction:
    """Collect one UID-bound semantic or close action; never call a provider.

    A workflow may begin at its exact final approval, or return its exact
    Accept action without rendering, when no unanswered REQUIRED decision
    remains. The operation chooses that behavior from its mutation authority
    and recovery boundary.
    """
    if require_tty:
        require_interactive_terminal(
            terminal_label,
            snapshot_hint=snapshot_hint,
        )
    if split_report_fragments is not None and split_report_text is None:
        raise ValueError("Styled split reports require matching plain report text.")
    if decision_free_behavior is None:
        # Keep legacy callers on their published final-review topology while
        # each operation adopts the ownership-aware policy explicitly.
        decision_free_behavior = (
            "FINAL_REVIEW"
            if start_final_review_when_no_required
            else "REPORT_FIRST"
        )
    elif start_final_review_when_no_required:
        raise ValueError(
            "Use either the legacy final-review flag or decision-free behavior."
        )
    if decision_free_behavior not in {
        "REPORT_FIRST",
        "FINAL_REVIEW",
        "AUTO_ACCEPT",
    }:
        raise ValueError("Unsupported decision-free application behavior.")
    current_navigation = navigation or ResolutionNavigation()
    supplier = (
        view_or_supplier if callable(view_or_supplier) else lambda: view_or_supplier
    )

    def current_view() -> ResolutionWorkbenchView:
        view = supplier()
        current_navigation.sync(view)
        return view

    def current_item_handoff() -> SessionTodoView | None:
        """Resolve operation-owned dynamic handoffs from current draft state."""

        return item_handoff() if callable(item_handoff) else item_handoff

    session_navigation = workbench_navigation or SessionWorkbenchNavigation()
    viewer_controller = SemanticViewerController(session_navigation)
    destination_available = (
        split_viewer_items and destination is not None and not read_only
    )
    if destination is not None and not split_viewer_items:
        raise ValueError("Editable save locations require the split session workbench.")
    if split_viewer_items:
        # A caller may reuse process-local navigation, but a composer cannot be
        # the initial target before the shell has opened an input surface.
        if session_navigation.pane in {"composer", "responses"} or (
            session_navigation.pane == "save_location" and not destination_available
        ):
            session_navigation.focus("viewer")
    else:
        session_navigation.focus("viewer")

    def report_sections() -> tuple[WorkbenchSection, ...]:
        active_view = current_view()
        if split_report_text is not None:
            lines = _seeded_report_lines(
                active_view,
                split_report_text,
                global_strategies,
                review_and_apply=review_and_apply,
                read_only=read_only,
                impact_controller=impact_controller,
                drafts=local_drafts,
            )
            entries = tuple(
                (
                    key.split(":", 1)[0],
                    f"SEEDED:{line_index}:{key}",
                    (
                        int(key.split(":", 1)[1]) + 1
                        if key.startswith("ITEM:")
                        else None
                        if key == "RESOLVE_ALL"
                        else 0
                    ),
                )
                for line_index, key in _seeded_report_sections(lines)
            )
            if not entries:
                # A read-only operation may seed a complete trusted report
                # without the common ITEM:/IMPACT markers. The report is still
                # one navigable Viewer surface; keeping an explicit fallback
                # section prevents focus/help projection from indexing an
                # empty semantic topology merely because no child stop exists.
                entries = (("REPORT", "SEEDED:REPORT", 0),)
            return _stable_sections(entries)
        entries: list[tuple[str, str, int | None]] = [
            (
                "OVERVIEW",
                f"REPORT:OVERVIEW:{section.uid}",
                0,
            )
            for section in active_view.semantic_overview_sections
        ]
        if active_view.report_items_summary is not None:
            entries.append(("REVIEW_ITEMS", "REPORT:REVIEW_ITEMS", 0))
        else:
            entries.extend(
                ("ITEM", f"ITEM:{item.uid}", index)
                for index, item in enumerate(active_view.items, start=1)
            )
        active_impact = _current_impact(impact_controller, active_view)
        impact_repeats_results = _impact_repeats_results(
            active_impact,
            active_view,
        )
        if active_view.show_results and not impact_repeats_results:
            entries.append(("RESULTS", "REPORT:RESULTS", 0))
        if active_impact is not None:
            entries.append(("IMPACT", "REPORT:IMPACT", 0))
            entries.extend(
                (
                    "IMPACT_ENTRY",
                    _impact_entry_section_uid(entry, index),
                    0,
                )
                for index, entry in enumerate(active_impact.entries, start=1)
            )
        if not read_only:
            entries.append(
                (
                    "REVIEW_AND_APPLY" if review_and_apply else "RESOLVE_ALL",
                    "REPORT:ACTION",
                    None,
                )
            )
        return _stable_sections(tuple(entries))

    def item_sections() -> tuple[WorkbenchSection, ...]:
        item = current_navigation.current_item(current_view())
        if item is None:
            return _stable_sections((("SUMMARY", "ITEM:SUMMARY", None),))
        entries: list[tuple[str, str, int | None]] = []

        def append_block_sections(blocks, *, start: int = 0) -> None:
            for block_index, block in enumerate(blocks, start=start):
                if block.memory_rows:
                    entries.extend(
                        (
                            "MEMORY_ROW",
                            _memory_row_section_uid(item.uid, block_index, row),
                            None,
                        )
                        for row in block.memory_rows
                    )
                else:
                    entries.append(
                        (
                            "BLOCK",
                            f"ITEM:{item.uid}:BLOCK:{block_index}:{block.heading}",
                            None,
                        )
                    )

        if item.issue_presentation is not None:
            for evidence_index, evidence in enumerate(item.issue_presentation.evidence):
                evidence_prefix = f"ITEM:{item.uid}:EVIDENCE:{evidence_index}"
                entries.append(
                    (
                        "EVIDENCE_CLASSIFICATION",
                        f"{evidence_prefix}:CLASSIFICATION",
                        None,
                    )
                )
                entries.extend(
                    (
                        "EVIDENCE_CRITERION",
                        f"{evidence_prefix}:CRITERION:{criterion_index}",
                        None,
                    )
                    for criterion_index, _criterion in enumerate(
                        evidence.criterion_blocks
                    )
                )
                for claim_index, claim in enumerate(evidence.source_groups):
                    for source in claim.sources:
                        entries.append(
                            (
                                "SOURCE_MEMORY",
                                (
                                    f"{evidence_prefix}:SOURCE:{claim_index}:"
                                    f"{source.memory_uid}"
                                ),
                                None,
                            )
                        )
                entries.append(
                    (
                        "EVIDENCE_REASON",
                        f"{evidence_prefix}:REASON",
                        None,
                    )
                )
            append_block_sections(item.blocks)
            return _stable_sections(tuple(entries))
        entries.append(("SUMMARY", f"ITEM:{item.uid}:SUMMARY", None))
        append_block_sections(item.blocks[: item.decision_block_index])
        append_block_sections(
            item.blocks[item.decision_block_index :],
            start=item.decision_block_index,
        )
        if item.evidence_refs:
            entries.append(("TRACE", f"ITEM:{item.uid}:TRACE", None))
        return _stable_sections(tuple(entries))

    def active_viewer_sections() -> tuple[WorkbenchSection, ...]:
        if viewer_content["kind"] == "REPORT":
            return report_sections()
        if viewer_content["kind"] == "REVIEW":
            entries: list[tuple[str, str, int | None]] = [
                ("SUMMARY", "REVIEW:SUMMARY", None)
            ]
            if review_action().kind in {
                "INCORPORATE RESPONSES",
                "INCORPORATE AND APPLY",
            }:
                entries.append(("POLICY", "REVIEW:POLICY", None))
            if final_command_review["value"] is not None:
                entries.append(("COMMAND", "REVIEW:COMMAND", None))
            entries.append(("ACTION", "REVIEW:ACTION", None))
            return _stable_sections(tuple(entries))
        return item_sections()

    def viewer_section_index() -> int:
        return viewer_controller.index(active_viewer_sections())

    def reset_viewer_section() -> None:
        viewer_controller.close_nested()
        sections = active_viewer_sections()
        session_navigation.section_uid = sections[0].uid if sections else None

    def focused_source_memory():
        """Resolve the exact typed Memory owned by the current Viewer stop."""

        section = viewer_controller.current(active_viewer_sections())
        item = current_navigation.current_item(current_view())
        if (
            section is None
            or section.kind != "SOURCE_MEMORY"
            or item is None
            or item.issue_presentation is None
        ):
            return None
        for evidence_index, evidence in enumerate(item.issue_presentation.evidence):
            for claim_index, claim in enumerate(evidence.source_groups):
                for source in claim.sources:
                    uid = (
                        f"ITEM:{item.uid}:EVIDENCE:{evidence_index}:SOURCE:"
                        f"{claim_index}:{source.memory_uid}"
                    )
                    if uid == section.uid:
                        return source
        return None

    def pane_content_width() -> int:
        """Track the live inner frame width, including terminal resizes."""
        try:
            columns = get_app().output.get_size().columns
        except (AttributeError, RuntimeError):
            return 76
        # Frame borders consume two cells and the scroll margin consumes one.
        return max(20, columns - 3)

    def split_kind() -> str:
        if session_navigation.pane == "save_location":
            return "SAVE_LOCATION"
        if session_navigation.pane == "responses":
            return "RESPONSES"
        if session_navigation.pane == "todo":
            return "TODO"
        if session_navigation.pane == "viewer" and viewer_content["kind"] == "REVIEW":
            return "RESOLVE_ALL"
        if session_navigation.row_index == 0:
            return "REPORT"
        if session_navigation.row_index <= len(current_view().items):
            return "ITEM"
        return "RESOLVE_ALL"

    def focused_impact_entry_uid() -> str | None:
        if not (
            split_viewer_items
            and session_navigation.pane == "viewer"
            and viewer_content["kind"] == "REPORT"
            and split_kind() == "REPORT"
        ):
            return None
        section = active_viewer_sections()[viewer_section_index()]
        if section.kind != "IMPACT_ENTRY":
            return None
        impact = _current_impact(impact_controller, current_view())
        if impact is None:
            return None
        for index, entry in enumerate(impact.entries, start=1):
            if _impact_entry_section_uid(entry, index) == section.uid and (
                entry.rules or entry.reason
            ):
                return section.uid
        return None

    def focused_impact_comment_item() -> ResolutionItem | None:
        if not (
            split_viewer_items
            and session_navigation.pane == "viewer"
            and viewer_content["kind"] == "REPORT"
            and split_kind() == "REPORT"
        ):
            return None
        section = active_viewer_sections()[viewer_section_index()]
        if section.kind != "IMPACT_ENTRY":
            return None
        active_view = current_view()
        impact = _current_impact(impact_controller, active_view)
        if impact is None:
            return None
        for index, entry in enumerate(impact.entries, start=1):
            if _impact_entry_section_uid(entry, index) != section.uid:
                continue
            item = _impact_entry_item(active_view, entry)
            return item if item is not None and item.commentable else None
        return None

    def review_action() -> SessionTodoView:
        if final_review_title["value"] == "RESOLVE ALL":
            if not global_strategies:
                return SessionTodoView(
                    "COMPLETE",
                    "No whole-set strategy available",
                    "Return and review an individual item.",
                )
            selected_strategy = global_strategies[strategy["index"]]
            return SessionTodoView(
                "RESOLVE ALL",
                selected_strategy.label,
                selected_strategy.comment
                or "Enter to run the selected whole-set strategy.",
            )
        return session_review_action_view(
            current_view(),
            local_drafts,
            whole_set_available=bool(global_strategies),
        )

    def displayed_todo() -> SessionTodoView:
        """Describe review entry before opening and confirmation after it."""

        active_view = current_view()
        if viewer_content["kind"] == "REVIEW":
            action = review_action()
            return SessionTodoView(
                final_review_title["value"],
                f"Confirm final {active_view.operation.title()} action",
                (f"{action.kind} is ready. Enter to {action.kind.lower()} now."),
            )
        return session_todo_view(
            active_view,
            local_drafts,
            review_and_apply=review_and_apply,
            read_only=read_only,
            whole_set_available=bool(global_strategies),
            read_only_handoff=read_only_handoff,
            item_handoff=current_item_handoff(),
        )

    def split_view_fragments():
        active_view = current_view()
        if viewer_content["kind"] == "REVIEW":
            return _viewer_focus_fragments(
                resolution_review_fragments(
                    active_view,
                    local_drafts,
                    global_strategies,
                    strategy["index"],
                    review_action(),
                    viewer_section_index(),
                    content_width=pane_content_width(),
                    review_title=final_review_title["value"],
                    command_review=final_command_review["value"],
                ),
                focused=session_navigation.pane == "viewer",
            )
        if viewer_content["kind"] == "REPORT":
            if split_report_text is not None:
                return _viewer_focus_fragments(
                    resolution_seeded_report_fragments(
                        active_view,
                        split_report_text,
                        report_fragments=split_report_fragments,
                        strategies=global_strategies,
                        drafts=local_drafts,
                        report_item_badges=split_report_item_badges,
                        report_conflicts_remaining=split_report_conflicts_remaining,
                        selected_strategy_index=strategy["index"],
                        focused_section=viewer_section_index(),
                        review_and_apply=review_and_apply,
                        read_only=read_only,
                        impact_controller=impact_controller,
                        content_width=pane_content_width(),
                    ),
                    focused=session_navigation.pane == "viewer",
                )
            return _viewer_focus_fragments(
                resolution_report_fragments(
                    active_view,
                    strategies=global_strategies,
                    drafts=local_drafts,
                    focused_section=viewer_section_index(),
                    review_and_apply=review_and_apply,
                    read_only=read_only,
                    impact_controller=impact_controller,
                    expanded_impact_section_uid=impact_reason_expanded["uid"],
                    content_width=pane_content_width(),
                ),
                focused=session_navigation.pane == "viewer",
            )
        return _viewer_focus_fragments(
            resolution_viewer_fragments(
                active_view,
                current_navigation,
                focused_section=viewer_section_index(),
                other_direction_editing=other_direction_editor["open"],
                expanded_memory_section_uid=expanded_memory_section_uid["uid"],
                nested_source_memory_uid=viewer_controller.nested_uid,
                nested_source_memory_line=viewer_controller.nested_index,
                include_response_sections=False,
                content_width=pane_content_width(),
            ),
            focused=session_navigation.pane == "viewer",
        )

    bindings = KeyBindings()
    status = {"value": ""}
    global_comment = {"value": False}
    strategy = {"index": 0}
    viewer_content = {"kind": "REPORT"}
    final_review_title = {"value": "APPLY CONFIRMATION"}
    final_review_origin: dict[str, _FinalReviewOrigin | None] = {"value": None}
    final_command_review: dict[str, ExactCommandReview | None] = {"value": None}
    impact_reason_expanded: dict[str, str | None] = {"uid": None}
    navigation_accelerator = NavigationAccelerator()
    other_direction = {"focused": False}
    other_direction_editor = {"open": False}
    response_state = ResponseFrameState()
    global_response_draft = {"value": ResponseDraft()}
    expanded_memory_section_uid: dict[str, str | None] = {"uid": None}
    destination_editing = {"value": False}
    destination_editor_state = {
        "value": (
            SaveLocationEditorState.create(destination)
            if destination is not None
            else None
        )
    }
    input_heading = {"value": "COMMENT ON SELECTED ITEM"}
    local_drafts: dict[str, ResponseDraft] = {}

    def current_response_target() -> ResponseTarget | None:
        """Project only the response context currently visible to the person."""

        active_view = current_view()
        if global_comment["value"]:
            return ResponseTarget(
                item_uid="WHOLE_SET",
                item_label=f"Complete {active_view.operation.title()} proposal",
                obligation="NONE",
                state=(
                    "ANSWERED" if global_response_draft["value"].answered else "OPEN"
                ),
                mode="COMMENT",
                editable=(
                    not read_only
                    and not active_view.input_locked
                    and "SUBMIT_ALL" in active_view.capabilities
                ),
            )
        if viewer_content["kind"] != "ITEM" and not response_state.editing:
            return None
        item = current_navigation.current_item(active_view)
        if item is None:
            return None
        return response_target_from_item(
            active_view,
            item,
            read_only=read_only,
            stage_locally=review_and_apply or draft_saver is not None,
        )

    def current_response_draft(target: ResponseTarget) -> ResponseDraft:
        if target.item_uid == "WHOLE_SET":
            return global_response_draft["value"]
        item = current_navigation.current_item(current_view())
        if item is None or item.uid != target.item_uid:
            return ResponseDraft()
        return _item_draft(item, local_drafts)

    def sync_response_state() -> ResponseTarget | None:
        target = current_response_target()
        if target is None:
            return None
        response_state.sync(
            target,
            current_response_draft(target),
            frame_focused=session_navigation.pane == "responses",
        )
        return target

    def response_visible() -> bool:
        target = current_response_target()
        if not split_viewer_items or target is None:
            return False
        # Read-only review retains an answered choice/comment as evidence, but
        # an empty response target is not a semantic surface. Hiding that blank
        # frame also prevents inactive controls from suggesting that an
        # applied session can still be edited.
        return not read_only or current_response_draft(target).answered

    def set_viewer_content(kind: str) -> None:
        """Keep the outer frame label aligned with its semantic surface."""

        viewer_content["kind"] = kind
        # A final whole-set confirmation is a distinct surface, not
        # another report/detail Viewer. Removing the label also avoids two
        # competing headings such as VIEWER and APPLY CONFIRMATION.
        viewer_frame.title = "" if kind == "REVIEW" else "VIEWER"

    # To Do summarizes the whole session before any individual row is opened,
    # so seed it from the adapter's durable response projection or the
    # operation-owned loader instead of treating unvisited rows as unresolved.
    for item in current_view().items:
        if draft_loader is None:
            option_uid, comment = item.selected_option_uid, item.response_text
        else:
            option_uid, comment = draft_loader(item.uid)
        if option_uid is not None:
            item.option(option_uid)
        local_drafts[item.uid] = ResponseDraft(option_uid, comment)

    composer = build_framed_multiline_input(
        "RESPONSE",
        prompt="› ",
        buffer_name="resolution-message",
        height=Dimension(min=4, preferred=5, max=7),
        # The outer Responses frame may be focused while a choice row owns the
        # keyboard. Reset inherited focus styling until this inner box itself
        # becomes the active stop.
        frame_style="fg:#f4f5f7 nobold",
    )
    input_area = composer.text_area
    body_control = FormattedTextControl(
        lambda: (
            split_view_fragments()
            if split_viewer_items
            else resolution_workbench_fragments(
                current_view(),
                current_navigation,
                other_direction_focused=other_direction["focused"],
            )
        ),
        focusable=True,
        show_cursor=False,
    )
    body = Window(
        body_control,
        wrap_lines=True,
        # Resolution details contain long logical lines (source Memories,
        # evidence, and proposed children). Use the shared visual-row-aware
        # margin so the thumb and ^/v arrows follow what is actually visible.
        right_margins=[WrappedScrollbarMargin(display_arrows=True)],
    )

    def current_viewer_plain_text(*, whole_document: bool) -> str:
        """Project current rendered Viewer chrome to the shared y/Y contract."""

        fragments = (
            split_view_fragments()
            if split_viewer_items
            else resolution_workbench_fragments(
                current_view(),
                current_navigation,
                other_direction_focused=other_direction["focused"],
            )
        )
        return plain_text_from_fragments(
            fragments,
            whole_document=whole_document,
        )

    def responses_fragments() -> list[tuple[str, str]]:
        target = sync_response_state()
        if target is None:
            return [("", " No response target is open.\n")]
        return response_frame_fragments(
            target,
            current_response_draft(target),
            response_state,
            focused=session_navigation.pane == "responses",
            content_width=pane_content_width(),
        )

    responses_control = FormattedTextControl(
        responses_fragments,
        focusable=True,
        show_cursor=False,
    )
    responses_window = Window(
        responses_control,
        height=Dimension(min=4, preferred=9, max=13, weight=4),
        wrap_lines=True,
        right_margins=[WrappedScrollbarMargin(display_arrows=True)],
    )

    def item_fragments():
        active_view = current_view()
        return _session_items_fragments(
            active_view,
            selected_index=session_navigation.row_index,
            focused=session_navigation.pane == "items",
            content_width=pane_content_width(),
            report_label=f"Complete {active_view.operation.title()} report",
        )

    items_control = FormattedTextControl(
        item_fragments,
        focusable=True,
        show_cursor=False,
    )
    items_window = Window(
        items_control,
        height=Dimension(min=4, preferred=6, max=8, weight=3),
        wrap_lines=False,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )

    def todo_fragments() -> list[tuple[str, str]]:
        todo = displayed_todo()
        focused = session_navigation.pane == "todo"
        display_kind = (
            "APPLY CONFIRMATION"
            if todo.kind == "REVIEW AND APPLY"
            else todo.kind
        )
        return [
            ("[SetCursorPosition]", "") if focused else ("", ""),
            (
                focused_control_style(focused=focused),
                f"[ {safe_terminal_text(display_kind)} ]",
            ),
            (
                "",
                "  "
                + _line(
                    f"{safe_terminal_text(todo.label)} · "
                    f"{safe_terminal_text(todo.detail)}",
                    max(10, pane_content_width() - len(display_kind) - 8),
                ),
            ),
        ]

    todo_control = FormattedTextControl(
        todo_fragments,
        focusable=True,
        show_cursor=False,
    )
    todo_window = Window(
        todo_control,
        height=Dimension.exact(1),
        dont_extend_height=True,
        wrap_lines=False,
    )

    def destination_fragments() -> list[tuple[str, str]]:
        if destination is None:
            return []
        return save_location_row_fragments(
            destination,
            focused=session_navigation.pane == "save_location",
            content_width=pane_content_width(),
        )

    destination_control = FormattedTextControl(
        destination_fragments,
        focusable=True,
        show_cursor=False,
    )
    destination_window = Window(
        destination_control,
        height=Dimension.exact(1),
        dont_extend_height=True,
        wrap_lines=False,
    )
    destination_name_field = ExactNameInputControl.create(
        destination
        if destination is not None
        else ExactNameFieldView(value="", label="SAVE LOCATION"),
        input_name="resolution-save-location",
    )
    destination_input = destination_name_field.input

    def destination_tree_fragments() -> list[tuple[str, str]]:
        state = destination_editor_state["value"]
        if state is None:
            return []
        return save_location_tree_fragments(
            state,
            focused=get_app().layout.has_focus(destination_tree_control),
        )

    destination_tree_control = FormattedTextControl(
        destination_tree_fragments,
        focusable=True,
        show_cursor=False,
    )
    destination_tree_window = Window(
        destination_tree_control,
        height=Dimension(min=3, preferred=6, max=9, weight=1),
        wrap_lines=False,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )
    destination_editor_with_tree = HSplit(
        [
            Window(
                FormattedTextControl(
                    " PARENT CONTEXT · ↑/↓ MOVE · ←/→ EXPAND · ENTER USE"
                ),
                height=Dimension.exact(1),
                dont_extend_height=True,
            ),
            destination_tree_window,
            Window(
                FormattedTextControl(" EDIT DIRECTLY · ENTER SAVES EXACT NAME"),
                height=Dimension.exact(1),
                dont_extend_height=True,
            ),
            destination_input,
        ]
    )

    def destination_frame_content():
        if not destination_editing["value"]:
            return destination_window
        if destination_editor_state["value"] is None:
            return destination_input
        return destination_editor_with_tree

    destination_frame = Frame(
        DynamicContainer(destination_frame_content),
        title=(
            safe_terminal_text(destination.label)
            if destination is not None
            else "SAVE LOCATION"
        ),
    )
    writable_input_focused = has_focus(input_area) | has_focus(destination_input)

    def destination_tree_is_focused() -> bool:
        return (
            destination_editing["value"]
            and destination_editor_state["value"] is not None
            and get_app().layout.has_focus(destination_tree_control)
        )

    def load_draft() -> None:
        item = current_navigation.current_item(current_view())
        if item is None:
            current_navigation.selected_option_uid = None
            input_area.text = ""
            return
        if draft_loader is None:
            draft = _item_draft(item, local_drafts)
            selected_option_uid, comment = draft.selected_choice_uid, draft.text
        else:
            selected_option_uid, comment = draft_loader(item.uid)
            if selected_option_uid is not None:
                item.option(selected_option_uid)
        current_navigation.selected_option_uid = selected_option_uid
        if selected_option_uid is not None:
            # Reopening a durable draft must put the navigation cursor on the
            # same option that carries the visible checkmark. Otherwise Enter
            # silently changes a different row instead of toggling the staged
            # choice the person is looking at.
            current_navigation.option_cursor_uid = selected_option_uid
        input_area.text = comment
        input_area.buffer.cursor_position = len(comment)
        target = current_response_target()
        if target is not None:
            response_state.sync(target, ResponseDraft(selected_option_uid, comment))

    def save_draft() -> bool:
        item = current_navigation.current_item(current_view())
        if item is None:
            return True
        if response_validator is not None:
            try:
                response_validator(input_area.text)
            except (TypeError, ValueError) as error:
                set_status(str(error))
                return False
        draft = ResponseDraft(
            current_navigation.selected_option_uid,
            input_area.text,
        )
        local_drafts[item.uid] = draft
        target = current_response_target()
        if target is not None and target.item_uid == item.uid:
            response_state.sync(target, draft)
        if draft_saver is not None:
            draft_saver(item.uid, draft.selected_choice_uid, draft.text)
        return True

    def set_status(message: str) -> None:
        status["value"] = message

    def semantic_action(
        kind: str,
        *,
        item_uid: str | None = None,
        option_uid: str | None = None,
        comment: str = "",
    ) -> ResolutionWorkbenchAction | None:
        try:
            action = ResolutionWorkbenchAction(
                kind=kind,  # type: ignore[arg-type]
                item_uid=item_uid,
                option_uid=option_uid,
                comment=comment,
            )
            return current_view().validate_action(action)
        except ResolutionWorkbenchError as error:
            set_status(str(error))
            return None

    def incorporate_responses_action(
        active_view: ResolutionWorkbenchView,
        *,
        action_kind: str = "SUBMIT_ALL",
    ) -> ResolutionWorkbenchAction | None:
        """Build the one complete reviewed-response turn used by both surfaces."""

        if not global_strategies:
            set_status("No remaining-item policies are available.")
            return None
        selected_strategy = global_strategies[strategy["index"]]
        lines = ["Use these reviewed issue resolutions:"]
        unresolved_counts: dict[str, int] = {}
        unresolved_required: list[str] = []
        for item in active_view.items:
            obligation = item.effective_obligation
            draft = _item_draft(item, local_drafts)
            option_uid, comment = draft.selected_choice_uid, draft.text
            if obligation == "NONE" and not (item.commentable and comment.strip()):
                continue
            if option_uid is not None:
                option = item.option(option_uid)
                response = f"Choose this reading: {option.text}"
                if comment.strip():
                    response += f" Additional guidance: {comment.strip()}"
                lines.append(f"- {item.title}: {response}")
            elif comment.strip():
                lines.append(f"- {item.title}: Response: {comment.strip()}")
            elif item.response_state == "ANSWERED":
                lines.append(f"- {item.title}: Keep the saved response.")
            else:
                unresolved_counts[obligation] = unresolved_counts.get(obligation, 0) + 1
                if obligation == "REQUIRED":
                    unresolved_required.append(item.title)
        if unresolved_counts:
            counts = ", ".join(
                f"{priority} {count}"
                for priority, count in (
                    ("REQUIRED", unresolved_counts.get("REQUIRED", 0)),
                    ("OPTIONAL", unresolved_counts.get("OPTIONAL", 0)),
                )
                if count
            )
            lines.append(
                "For remaining items ("
                + counts
                + "), apply this policy: "
                + selected_strategy.comment
            )
        if unresolved_required:
            lines.append(
                "Still-required issue titles: " + "; ".join(unresolved_required)
            )
        return semantic_action(action_kind, comment="\n".join(lines))

    def destination_action(value: str) -> ResolutionWorkbenchAction | None:
        if destination is None:
            set_status("Save-location editing is unavailable here.")
            return None
        try:
            destination.validate_value(value)
            return ResolutionWorkbenchAction(
                kind="CHANGE_DESTINATION",
                destination=value,
            )
        except (OSError, TypeError, ValueError) as error:
            set_status(str(error))
            return None

    def project_previewed_items_row(active_view: ResolutionWorkbenchView) -> None:
        """Project the already-aligned shared Items row into operation state."""

        other_direction["focused"] = False
        other_direction_editor["open"] = False
        response_state.editing = False
        expanded_memory_section_uid["uid"] = None
        viewer_controller.close_nested()
        if session_navigation.row_index == 0:
            set_viewer_content("REPORT")
            current_navigation.close_detail()
            reset_viewer_section()
            return
        item = active_view.items[session_navigation.row_index - 1]
        set_viewer_content("ITEM")
        current_navigation.selected_item_uid = item.uid
        current_navigation.sync(active_view)
        current_navigation.close_detail()
        current_navigation.toggle_detail(active_view)
        reset_viewer_section()
        load_draft()
        sync_response_state()

    def preview_items_row(active_view: ResolutionWorkbenchView) -> None:
        """Align and project one explicitly selected Items row."""

        session_navigation.preview_selected_row()
        project_previewed_items_row(active_view)

    def move(delta: int) -> None:
        active_view = current_view()
        if split_viewer_items:
            if session_navigation.pane == "responses":
                target = sync_response_state()
                if target is None:
                    set_status("No response target is open.")
                    return
                response_state.move_focus(target, delta)
                set_status("")
                return
            if session_navigation.pane == "viewer":
                if viewer_controller.nested_uid is not None:
                    source = focused_source_memory()
                    if source is not None:
                        viewer_controller.move_nested(
                            len(
                                _source_memory_lines(
                                    source.content,
                                    pane_content_width(),
                                )
                            ),
                            delta,
                        )
                    set_status("")
                    return
                section = viewer_controller.move(active_viewer_sections(), delta)
                if viewer_content["kind"] == "REPORT" and section is not None:
                    session_navigation.row_index = section.row_index or 0
                    if section.kind == "ITEM" and section.row_index is not None:
                        item = active_view.items[section.row_index - 1]
                        current_navigation.selected_item_uid = item.uid
                set_status("")
                return
            if session_navigation.pane == "todo":
                set_status("")
                return
            if session_navigation.pane == "save_location":
                state = destination_editor_state["value"]
                if destination_tree_is_focused() and state is not None:
                    state.tree.move(delta)
                set_status("")
                return
            total_rows = len(active_view.items) + 1
            session_navigation.move_and_preview_row(total_rows, delta)
            project_previewed_items_row(active_view)
            set_status("")
            return
        item = current_navigation.current_item(active_view)
        if (
            item is not None
            and current_navigation.expanded_item_uid == item.uid
            and item.options
        ):
            current_navigation.move_option(active_view, delta)
        else:
            if not save_draft():
                return
            current_navigation.move_item(active_view, delta)
            load_draft()
        global_comment["value"] = False
        composer.frame.title = "RESPONSE" if split_viewer_items else "MESSAGE"
        set_status("")

    def open_item_input(*, title: str, clear: bool = False) -> None:
        destination_editing["value"] = False
        global_comment["value"] = False
        response_state.editing = True
        response_state.focus_response()
        composer.frame.title = title
        input_heading["value"] = title
        if clear:
            input_area.text = ""
        session_navigation.focus("composer")
        get_app().layout.focus(input_area)

    def open_global_input(*, clear: bool = False) -> None:
        destination_editing["value"] = False
        global_comment["value"] = True
        response_state.editing = True
        response_state.focus_response()
        other_direction_editor["open"] = False
        composer.frame.title = "WHOLE-SET COMMENT"
        input_heading["value"] = "WHOLE-SET GUIDANCE"
        if clear:
            global_response_draft["value"] = ResponseDraft()
        input_area.text = global_response_draft["value"].text
        input_area.buffer.cursor_position = len(input_area.text)
        sync_response_state()
        session_navigation.focus("composer")
        get_app().layout.focus(input_area)

    def open_destination_input() -> None:
        if destination is None or not destination_available:
            set_status("Save-location editing is unavailable here.")
            return
        destination_editing["value"] = True
        destination_editor_state["value"] = SaveLocationEditorState.create(destination)
        global_comment["value"] = False
        other_direction_editor["open"] = False
        response_state.editing = False
        destination_frame.title = safe_terminal_text(
            f"{destination.label} · CHOOSE PARENT OR EDIT DIRECTLY"
        )
        destination_name_field.set_text(destination.value)
        session_navigation.focus("save_location")
        get_app().layout.focus(destination_input)
        set_status("")

    def use_destination_parent() -> None:
        state = destination_editor_state["value"]
        if state is None:
            set_status("No parent Context catalog is available here.")
            return
        try:
            candidate = state.choose_cursor_as_parent(destination_input.text)
        except (TypeError, ValueError) as error:
            set_status(str(error))
            return
        destination_name_field.set_text(candidate)
        get_app().layout.focus(destination_input)
        set_status(
            f"Parent selected · {state.selected_parent} · edit the exact name or Enter."
        )

    def current_response_heading() -> str:
        item = current_navigation.current_item(current_view())
        if item is not None and item.issue_presentation is not None:
            return "RESPONSE"
        return "COMMENT ON SELECTED ITEM"

    def open_split_item(item_uid: str) -> None:
        """Open one selected item from Items or the state-derived To Do."""

        active_view = current_view()
        item_index = next(
            index
            for index, item in enumerate(active_view.items)
            if item.uid == item_uid
        )
        session_navigation.row_index = item_index + 1
        preview_items_row(active_view)
        session_navigation.open_selected(item_sections())
        event_app = get_app()
        event_app.layout.focus(body_control)
        set_status("")

    def close_final_review() -> None:
        """Return from final review to the exact process-local entry surface."""

        origin = final_review_origin["value"]
        final_review_origin["value"] = None
        final_command_review["value"] = None
        if origin is None:
            # Compatibility fallback for navigation state created before this
            # shell began tracking review entry. The report action is the
            # closest stable semantic parent of the confirmation surface.
            session_navigation.row_index = 0
            session_navigation.viewer_row_index = 0
            set_viewer_content("REPORT")
            sections = report_sections()
            action_section = next(
                (section for section in sections if section.uid == "REPORT:ACTION"),
                sections[0] if sections else None,
            )
            session_navigation.section_uid = (
                action_section.uid if action_section is not None else None
            )
            pane: WorkbenchPane = "viewer"
        else:
            session_navigation.row_index = origin.row_index
            session_navigation.viewer_row_index = origin.viewer_row_index
            set_viewer_content(origin.viewer_kind)
            session_navigation.section_uid = origin.section_uid
            viewer_controller.index(active_viewer_sections())
            pane = origin.pane

        if pane == "responses" and not response_visible():
            pane = "viewer"
        if pane == "save_location" and not destination_available:
            pane = "viewer"
        if pane == "composer":
            pane = "viewer"
        controls = {
            "viewer": body_control,
            "responses": responses_control,
            "items": items_control,
            "save_location": destination_control,
            "todo": todo_control,
        }
        _focus_surface_pane(pane)
        get_app().layout.focus(controls[pane])
        set_status("")

    def open_final_review() -> None:
        """Open the non-mutating review before a whole-set or apply action."""

        # A split report has no open response editor. Saving there would copy
        # the navigation sentinel (no selected option) over the first item's
        # already-staged durable choice after its detail was closed.
        if not split_viewer_items or response_visible():
            save_draft()
        active_view = current_view()
        todo = session_todo_view(
            active_view,
            local_drafts,
            review_and_apply=review_and_apply,
            read_only=read_only,
            whole_set_available=bool(global_strategies),
            read_only_handoff=read_only_handoff,
            item_handoff=current_item_handoff(),
        )
        if todo.kind not in {"REVIEW AND APPLY", "RESOLVE ALL"}:
            if todo.unresolved_item_uids:
                open_split_item(todo.unresolved_item_uids[0])
            else:
                set_status(todo.detail)
            return
        final_review_title["value"] = (
            "APPLY CONFIRMATION"
            if todo.kind == "REVIEW AND APPLY"
            else todo.kind
        )
        proposed_action = final_review_action(active_view, open_custom=False)
        final_command_review["value"] = (
            turn_command_review(proposed_action)
            if turn_command_review is not None and proposed_action is not None
            else None
        )
        if viewer_content["kind"] != "REVIEW":
            # This is a temporary confirmation layer. Preserve the exact
            # semantic stop and visible frame so both Enter on its summary and
            # the shared back keys can unwind without guessing a destination.
            final_review_origin["value"] = _FinalReviewOrigin(
                viewer_kind=viewer_content["kind"],
                pane=session_navigation.pane,
                row_index=session_navigation.row_index,
                viewer_row_index=session_navigation.viewer_row_index,
                section_uid=session_navigation.section_uid,
            )
        session_navigation.row_index = len(active_view.items) + 1
        session_navigation.viewer_row_index = session_navigation.row_index
        set_viewer_content("REVIEW")
        session_navigation.focus_section(
            active_viewer_sections(),
            kind="SUMMARY",
        )
        # Entering final review starts at its visible top, not at the To Do
        # handoff below the Viewer. This keeps the summary in view and makes
        # moving down to the exact Apply action an explicit review step.
        session_navigation.focus("viewer")
        get_app().layout.focus(body_control)
        set_status("")
        record_study_action(
            "APPROVAL_PRESENTED",
            surface="resolution",
            action=todo.kind,
        )

    def final_review_action(
        active_view: ResolutionWorkbenchView,
        *,
        open_custom: bool = True,
    ) -> ResolutionWorkbenchAction | None:
        final_action = review_action()
        if final_action.kind in {"APPLY", "APPLY AS IS"}:
            return semantic_action("ACCEPT")
        if final_action.kind == "INCORPORATE AND APPLY":
            return incorporate_responses_action(
                active_view,
                action_kind="INCORPORATE_AND_APPLY",
            )
        if final_action.kind == "INCORPORATE RESPONSES":
            return incorporate_responses_action(active_view)
        if final_action.kind == "RESOLVE ALL":
            selected_strategy = global_strategies[strategy["index"]]
            if selected_strategy.action_kind == "CUSTOM":
                if open_custom:
                    open_global_input(clear=True)
                return None
            return semantic_action(
                selected_strategy.action_kind,
                comment=selected_strategy.comment,
            )
        set_status("No final action is available.")
        return None

    def approved_final_review_action(
        active_view: ResolutionWorkbenchView,
    ) -> ResolutionWorkbenchAction | None:
        """Rebuild the final action and its command before returning either."""

        action = final_review_action(active_view)
        if action is None or turn_command_review is None:
            return action
        rebuilt = turn_command_review(action)
        if rebuilt != final_command_review["value"]:
            set_status(
                "The semantic turn changed after review. Reopen the final review."
            )
            return None
        return action

    def submit(event) -> None:
        active_view = current_view()
        comment = input_area.text.strip()
        if (review_and_apply or draft_saver is not None) and not global_comment[
            "value"
        ]:
            item = current_navigation.current_item(active_view)
            if not save_draft():
                event.app.invalidate()
                return
            other_direction_editor["open"] = False
            response_state.editing = False
            if split_viewer_items:
                session_navigation.focus("responses")
                event.app.layout.focus(responses_control)
            else:
                session_navigation.focus("viewer")
                event.app.layout.focus(body_control)
            if item is not None:
                draft = local_drafts.get(item.uid, ResponseDraft())
                option_uid, saved_comment = draft.selected_choice_uid, draft.text
                if option_uid is not None:
                    label = item.option(option_uid).label
                    set_status(f"Selected · {label}")
                elif saved_comment.strip():
                    set_status("Saved · Response")
            event.app.invalidate()
            return
        if global_comment["value"]:
            action = semantic_action("SUBMIT_ALL", comment=comment)
        else:
            item = current_navigation.current_item(active_view)
            action = semantic_action(
                "SUBMIT_ITEM",
                item_uid=item.uid if item is not None else None,
                option_uid=current_navigation.selected_option_uid,
                comment=comment,
            )
        if action is not None:
            event.app.exit(result=action)

    @bindings.add("pagedown", filter=~writable_input_focused)
    def _page_down(event) -> None:
        # Once results are independent sections, a page step advances several
        # short result blocks instead of trying to display one 234-result
        # monolith. Down still advances one block at a time.
        navigation_accelerator.reset()
        move(8)
        event.app.invalidate()

    @bindings.add("pageup", filter=~writable_input_focused)
    def _page_up(event) -> None:
        navigation_accelerator.reset()
        move(-8)
        event.app.invalidate()

    @bindings.add("end", filter=~writable_input_focused)
    def _end(event) -> None:
        navigation_accelerator.reset()
        move(1_000_000)
        event.app.invalidate()

    @bindings.add("home", filter=~writable_input_focused)
    def _home(event) -> None:
        navigation_accelerator.reset()
        move(-1_000_000)
        event.app.invalidate()

    def copy_current_viewer(event, *, whole_document: bool) -> None:
        copied = copy_plain_text(
            current_viewer_plain_text(whole_document=whole_document),
            success_message=(
                "complete current document"
                if whole_document
                else "focused semantic unit"
            ),
        )
        set_status(copied.message)
        event.app.invalidate()

    @bindings.add("y", filter=has_focus(body_control), eager=True)
    def _copy_focused_viewer(event) -> None:
        copy_current_viewer(event, whole_document=False)

    @bindings.add("Y", filter=has_focus(body_control), eager=True)
    def _copy_complete_viewer(event) -> None:
        copy_current_viewer(event, whole_document=True)

    def explain_unused_split_horizontal_key() -> None:
        """Make stacked-frame horizontal no-ops explicit instead of silent."""

        set_status(_stacked_horizontal_key_message(split_kind()))

    @bindings.add("right", filter=~writable_input_focused)
    def _right(event) -> None:
        state = destination_editor_state["value"]
        if destination_tree_is_focused() and state is not None:
            state.tree.expand_selected()
            set_status("")
            event.app.invalidate()
            return
        if split_viewer_items:
            impact_uid = focused_impact_entry_uid()
            if impact_uid is not None:
                impact_reason_expanded["uid"] = _impact_arrow_expansion(
                    impact_reason_expanded["uid"],
                    impact_uid,
                    expand=True,
                )
                set_status("Impact rationale shown.")
            elif split_kind() == "RESOLVE_ALL" and global_strategies:
                strategy["index"] = min(
                    strategy["index"] + 1,
                    len(global_strategies) - 1,
                )
            else:
                explain_unused_split_horizontal_key()
            event.app.invalidate()
            return
        save_draft()
        current_navigation.move_item(current_view(), 1)
        load_draft()
        event.app.invalidate()

    @bindings.add("left", filter=~writable_input_focused)
    def _left(event) -> None:
        state = destination_editor_state["value"]
        if destination_tree_is_focused() and state is not None:
            state.tree.collapse_selected()
            set_status("")
            event.app.invalidate()
            return
        if split_viewer_items:
            impact_uid = focused_impact_entry_uid()
            if impact_uid is not None:
                collapsed = _impact_arrow_expansion(
                    impact_reason_expanded["uid"],
                    impact_uid,
                    expand=False,
                )
                if collapsed != impact_reason_expanded["uid"]:
                    set_status("Impact rationale hidden.")
                impact_reason_expanded["uid"] = collapsed
            elif split_kind() == "RESOLVE_ALL" and global_strategies:
                strategy["index"] = max(strategy["index"] - 1, 0)
            else:
                explain_unused_split_horizontal_key()
            event.app.invalidate()
            return
        save_draft()
        current_navigation.move_item(current_view(), -1)
        load_draft()
        event.app.invalidate()

    def _open_or_choose(event) -> None:
        active_view = current_view()
        if split_viewer_items:
            kind = split_kind()
            if kind == "RESPONSES":
                target = sync_response_state()
                item = current_navigation.current_item(active_view)
                if target is not None and target.item_uid == "WHOLE_SET":
                    if not target.editable:
                        set_status("Whole-set guidance is read-only.")
                    else:
                        open_global_input()
                elif target is None or item is None or target.item_uid != item.uid:
                    set_status("No item response is available here.")
                elif response_state.option_navigation_active and not target.editable:
                    set_status("This response is read-only.")
                elif response_state.option_navigation_active:
                    draft = response_state.toggle_current_choice(target)
                    local_drafts[item.uid] = draft
                    current_navigation.selected_option_uid = draft.selected_choice_uid
                    if draft_saver is not None:
                        draft_saver(
                            item.uid,
                            draft.selected_choice_uid,
                            draft.text,
                        )
                    if draft.selected_choice_uid is None:
                        set_status("Selection cleared.")
                    else:
                        set_status(
                            "Selected · ✓ "
                            + target.choice(draft.selected_choice_uid).label
                        )
                elif response_state.section == "DECISION":
                    # A choice-bearing Decision is always directly focusable.
                    # This fallback is only reachable for a prompt-only target.
                    response_state.focus_response()
                    set_status("Move to Response and press Enter to answer.")
                elif not target.editable:
                    set_status("This response is read-only.")
                else:
                    open_item_input(title=current_response_heading())
                event.app.invalidate()
                return
            if kind == "REPORT":
                if (
                    session_navigation.pane == "viewer"
                    and viewer_content["kind"] == "REPORT"
                ):
                    sections = active_viewer_sections()
                    section = sections[viewer_section_index()]
                    if section.kind == "IMPACT_ENTRY":
                        impact_reason_expanded["uid"] = (
                            None
                            if impact_reason_expanded["uid"] == section.uid
                            else section.uid
                        )
                        set_status(
                            "Impact rationale hidden."
                            if impact_reason_expanded["uid"] is None
                            else "Impact rationale shown."
                        )
                        event.app.invalidate()
                        return
                    if section.kind in {"REVIEW_AND_APPLY", "RESOLVE_ALL"}:
                        open_final_review()
                        event.app.invalidate()
                        return
                other_direction_editor["open"] = False
                set_viewer_content("REPORT")
                reset_viewer_section()
                session_navigation.open_selected(report_sections())
                event.app.layout.focus(body_control)
                set_status("")
            elif kind == "SAVE_LOCATION":
                if destination_tree_is_focused():
                    use_destination_parent()
                else:
                    open_destination_input()
            elif kind == "ITEM":
                if (
                    session_navigation.pane != "viewer"
                    or viewer_content["kind"] != "ITEM"
                    or session_navigation.viewer_row_index
                    != session_navigation.row_index
                ):
                    item = active_view.items[session_navigation.row_index - 1]
                    open_split_item(item.uid)
                elif (
                    session_navigation.pane == "viewer"
                    and active_viewer_sections()[viewer_section_index()].kind
                    == "SOURCE_MEMORY"
                ):
                    section = active_viewer_sections()[viewer_section_index()]
                    if viewer_controller.nested_uid == section.uid:
                        viewer_controller.close_nested()
                        set_status("Memory reading closed.")
                    else:
                        viewer_controller.open_nested(section.uid)
                        set_status(
                            "Reading this Memory · ↑/↓ scroll · Enter/Escape back."
                        )
                    event.app.invalidate()
                    return
                elif read_only:
                    set_status("Applied Melds are read-only.")
                else:
                    section = active_viewer_sections()[viewer_section_index()]
                    item = current_navigation.current_item(active_view)
                    if section.kind == "MEMORY_ROW":
                        expanded_memory_section_uid["uid"] = (
                            None
                            if expanded_memory_section_uid["uid"] == section.uid
                            else section.uid
                        )
                        set_status(
                            "Evidence hidden."
                            if expanded_memory_section_uid["uid"] is None
                            else "Evidence shown."
                        )
                        event.app.invalidate()
                        return
                    set_status(
                        "This Viewer section is read-only; use the Responses frame "
                        "to answer."
                    )
            elif kind == "RESOLVE_ALL" and viewer_content["kind"] == "REVIEW":
                section = active_viewer_sections()[viewer_section_index()]
                if section.kind == "SUMMARY":
                    close_final_review()
                elif section.kind != "ACTION":
                    set_status("Move to the final action and press Enter.")
                else:
                    action = approved_final_review_action(active_view)
                    if action is not None:
                        record_study_action(
                            "APPROVAL_ACCEPTED",
                            surface="resolution",
                            action=action.kind,
                        )
                        event.app.exit(result=action)
                        return
            elif kind == "TODO" and viewer_content["kind"] == "REVIEW":
                action = approved_final_review_action(active_view)
                if action is not None:
                    record_study_action(
                        "APPROVAL_ACCEPTED",
                        surface="resolution",
                        action=action.kind,
                    )
                    event.app.exit(result=action)
                    return
            elif (
                kind == "TODO"
                and session_todo_view(
                    active_view,
                    local_drafts,
                    review_and_apply=review_and_apply,
                    read_only=read_only,
                    whole_set_available=bool(global_strategies),
                    read_only_handoff=read_only_handoff,
                    item_handoff=current_item_handoff(),
                ).unresolved_item_uids
            ):
                todo = session_todo_view(
                    active_view,
                    local_drafts,
                    review_and_apply=review_and_apply,
                    read_only=read_only,
                    whole_set_available=bool(global_strategies),
                    read_only_handoff=read_only_handoff,
                    item_handoff=current_item_handoff(),
                )
                open_split_item(todo.unresolved_item_uids[0])
            elif kind == "TODO" and current_item_handoff() is not None:
                item = current_navigation.current_item(active_view)
                if item is None:
                    set_status("There is no finding to hand off.")
                else:
                    # The operation receives the exact item identity and owns
                    # conversion, authority, provider use, and any Apply step.
                    event.app.exit(
                        result=ResolutionWorkbenchAction(
                            kind="HANDOFF",
                            item_uid=item.uid,
                        )
                    )
                    return
            elif kind == "TODO" and read_only:
                if read_only_handoff is None:
                    set_status("This saved session can only be inspected.")
                else:
                    # A standalone result remains immutable here. The handoff
                    # opens the owning operation, which must independently
                    # revalidate and obtain its normal Apply confirmation.
                    event.app.exit(result=ResolutionWorkbenchAction(kind="HANDOFF"))
                    return
            elif (
                kind == "TODO"
                and session_todo_view(
                    active_view,
                    local_drafts,
                    review_and_apply=review_and_apply,
                    read_only=read_only,
                    whole_set_available=bool(global_strategies),
                    read_only_handoff=read_only_handoff,
                    item_handoff=current_item_handoff(),
                ).kind
                == "COMPLETE"
            ):
                set_status(
                    "Required review is complete; close or revisit an optional review."
                )
            elif kind == "TODO" and review_and_apply:
                open_final_review()
            elif kind == "TODO" and not global_strategies:
                set_status("No whole-set strategies are available.")
            elif kind == "TODO":
                open_final_review()
            event.app.invalidate()
            return
        item = current_navigation.current_item(active_view)
        if item is None:
            set_status("There is no item to inspect.")
        elif current_navigation.expanded_item_uid != item.uid:
            current_navigation.toggle_detail(active_view)
            other_direction["focused"] = False
            set_status("")
        elif item.options:
            if item.issue_presentation is not None and other_direction["focused"]:
                current_navigation.selected_option_uid = None
                other_direction_editor["open"] = True
                open_item_input(
                    title=current_response_heading(),
                    clear=True,
                )
            else:
                current_navigation.toggle_option(active_view)
                if not save_draft():
                    event.app.invalidate()
                    return
                set_status("")
        else:
            current_navigation.toggle_detail(active_view)
            set_status("")
        event.app.invalidate()

    def _focus_surface_pane(pane: WorkbenchPane) -> None:
        """Keep semantic frame state aligned with prompt-toolkit focus."""

        if pane != "viewer":
            navigation_accelerator.reset()
            viewer_controller.close_nested()
        if pane == "items" and viewer_content["kind"] == "REVIEW":
            # Final review is not an Items row. Both Tab and vertical entry
            # expose the ordinary Report selection while leaving the reviewed
            # confirmation visible until the person moves or activates it.
            session_navigation.row_index = 0
        session_navigation.focus(pane)
        set_status("")

    def _move_viewer_surface(event, delta: int) -> SurfaceMoveResult:
        sections = active_viewer_sections()
        if viewer_controller.nested_uid is not None:
            # Nested Memory reading deliberately keeps its own Escape boundary;
            # reaching the last wrapped line must not silently leave the reader.
            navigation_accelerator.move(delta, app=event.app, move_one=move)
            return "CONSUMED"
        index = viewer_section_index()
        if (delta < 0 and index == 0) or (
            delta > 0 and index == len(sections) - 1
        ):
            navigation_accelerator.reset()
            return "BOUNDARY"
        navigation_accelerator.move(delta, app=event.app, move_one=move)
        return "MOVED"

    def _enter_viewer_surface(delta: int) -> None:
        sections = active_viewer_sections()
        if sections:
            session_navigation.section_uid = sections[0 if delta > 0 else -1].uid

    def _move_responses_surface(_event, delta: int) -> SurfaceMoveResult:
        target = sync_response_state()
        if target is None:
            return "BOUNDARY"
        before = (
            response_state.section,
            response_state.option_cursor_uid,
        )
        response_state.move_focus(target, delta)
        after = (
            response_state.section,
            response_state.option_cursor_uid,
        )
        set_status("")
        return "MOVED" if after != before else "BOUNDARY"

    def _enter_responses_surface(delta: int) -> None:
        target = sync_response_state()
        if target is None:
            return
        if delta < 0 or not target.choices:
            response_state.focus_response()
            return
        response_state.open_options(target)
        choices = response_state.choice_state
        if choices is not None:
            choices.cursor_uid = choices.options[0].uid

    def _move_items_surface(_event, delta: int) -> SurfaceMoveResult:
        active_view = current_view()
        total_rows = len(active_view.items) + 1
        before = session_navigation.row_index
        if (delta < 0 and before == 0) or (
            delta > 0 and before == total_rows - 1
        ):
            return "BOUNDARY"
        move(delta)
        return (
            "MOVED" if session_navigation.row_index != before else "BOUNDARY"
        )

    def _enter_items_surface(delta: int) -> None:
        # Entering a frame chooses its nearest edge without opening that row.
        # In particular, crossing out of final review must not close the review
        # until the person actually moves or activates an Items selection.
        session_navigation.row_index = (
            0 if delta > 0 else len(current_view().items)
        )

    def _single_row_surface_move(
        _event,
        _delta: int,
    ) -> SurfaceMoveResult:
        return "BOUNDARY"

    def _activate_surface(event) -> SurfaceActionResult:
        _open_or_choose(event)
        return "HANDLED"

    if split_viewer_items:

        def visible_focus_surfaces() -> tuple[FocusSurface, ...]:
            surfaces = [
                FocusSurface(
                    "viewer",
                    body_control,
                    move_vertical=_move_viewer_surface,
                    activate=_activate_surface,
                    on_focus=lambda: _focus_surface_pane("viewer"),
                    on_vertical_enter=_enter_viewer_surface,
                )
            ]
            if response_visible():
                surfaces.append(
                    FocusSurface(
                        "responses",
                        responses_control,
                        move_vertical=_move_responses_surface,
                        activate=_activate_surface,
                        on_focus=lambda: _focus_surface_pane("responses"),
                        on_vertical_enter=_enter_responses_surface,
                    )
                )
            surfaces.append(
                FocusSurface(
                    "items",
                    items_control,
                    move_vertical=_move_items_surface,
                    activate=_activate_surface,
                    on_focus=lambda: _focus_surface_pane("items"),
                    on_vertical_enter=_enter_items_surface,
                )
            )
            if destination_available:
                surfaces.append(
                    FocusSurface(
                        "save-location",
                        destination_control,
                        move_vertical=_single_row_surface_move,
                        activate=_activate_surface,
                        on_focus=lambda: _focus_surface_pane("save_location"),
                    )
                )
            surfaces.append(
                FocusSurface(
                    "todo",
                    todo_control,
                    move_vertical=_single_row_surface_move,
                    activate=_activate_surface,
                    on_focus=lambda: _focus_surface_pane("todo"),
                )
            )
            return tuple(surfaces)

        surface_focus = SurfaceFocusController(visible_focus_surfaces)
        bind_surface_navigation(bindings, surface_focus)
    else:

        @bindings.add("down", filter=~writable_input_focused)
        def _legacy_down(event) -> None:
            move(1)
            event.app.invalidate()

        @bindings.add("up", filter=~writable_input_focused)
        def _legacy_up(event) -> None:
            move(-1)
            event.app.invalidate()

        @bindings.add("enter", filter=~writable_input_focused)
        def _legacy_open_or_choose(event) -> None:
            _open_or_choose(event)

        @bindings.add("tab", filter=has_focus(body_control), eager=True)
        @bindings.add("s-tab", filter=has_focus(body_control), eager=True)
        def _legacy_focus_input(event) -> None:
            active_view = current_view()
            if active_view.input_locked:
                set_status("Resolution input is locked while analysis is pending.")
                event.app.invalidate()
                return
            if "SUBMIT_ITEM" not in active_view.capabilities:
                set_status("Item comments are unavailable here.")
                event.app.invalidate()
                return
            global_comment["value"] = False
            heading = current_response_heading()
            other_direction_editor["open"] = True
            composer.frame.title = heading
            input_heading["value"] = heading
            event.app.layout.focus(input_area)
            event.app.invalidate()

    editor_tab_focused = (
        has_focus(input_area)
        | has_focus(destination_input)
        | has_focus(destination_tree_control)
    )

    @bindings.add("tab", filter=editor_tab_focused, eager=True)
    @bindings.add("s-tab", filter=editor_tab_focused, eager=True)
    def _focus_input(event) -> None:
        if event.app.layout.has_focus(destination_input):
            if destination_editor_state["value"] is not None:
                event.app.layout.focus(destination_tree_control)
                set_status("Choose a parent Context with arrows, then press Enter.")
            else:
                set_status("Press Enter to save this location or Escape to cancel.")
            event.app.invalidate()
            return
        if destination_tree_is_focused():
            event.app.layout.focus(destination_input)
            set_status("Edit the exact Context name, then press Enter to save.")
            event.app.invalidate()
            return
        if event.app.layout.has_focus(input_area):
            if global_comment["value"]:
                if response_validator is not None:
                    try:
                        response_validator(input_area.text)
                    except (TypeError, ValueError) as error:
                        set_status(str(error))
                        event.app.invalidate()
                        return
                global_response_draft["value"] = ResponseDraft(None, input_area.text)
            else:
                if not save_draft():
                    event.app.invalidate()
                    return
            other_direction_editor["open"] = False
            response_state.editing = False
            if split_viewer_items:
                session_navigation.focus("responses")
                event.app.layout.focus(responses_control)
            else:
                event.app.layout.focus(body_control)
            event.app.invalidate()
            return
    @bindings.add("c", filter=~writable_input_focused)
    def _comment_item(event) -> None:
        if not split_viewer_items:
            return
        active_view = current_view()
        impact_item = focused_impact_comment_item()
        if impact_item is not None:
            if (
                active_view.input_locked
                or "SUBMIT_ITEM" not in active_view.capabilities
            ):
                set_status("Item comments are unavailable here.")
                event.app.invalidate()
                return
            current_navigation.selected_item_uid = impact_item.uid
            current_navigation.sync(active_view)
            open_split_item(impact_item.uid)
            open_item_input(title="COMMENT ON THIS CHANGE")
            event.app.invalidate()
            return
        if split_kind() == "RESOLVE_ALL":
            if active_view.input_locked or "SUBMIT_ALL" not in active_view.capabilities:
                set_status("Whole-set guidance is unavailable here.")
                event.app.invalidate()
                return
            open_global_input(clear=True)
            return
        if split_kind() != "ITEM":
            set_status("Choose one review item or RESOLVE ALL first.")
            event.app.invalidate()
            return
        if viewer_content["kind"] != "ITEM":
            set_status("Press Enter to open the selected review item first.")
            event.app.invalidate()
            return
        if active_view.input_locked or "SUBMIT_ITEM" not in active_view.capabilities:
            set_status("Item comments are unavailable here.")
            event.app.invalidate()
            return
        other_direction_editor["open"] = True
        open_item_input(title=current_response_heading())

    @bindings.add("g", filter=~writable_input_focused)
    def _global_comment(event) -> None:
        active_view = current_view()
        if "SUBMIT_ALL" not in active_view.capabilities:
            set_status("Whole-set comments are unavailable here.")
            event.app.invalidate()
            return
        if active_view.input_locked:
            set_status("Resolution input is locked while analysis is pending.")
            event.app.invalidate()
            return
        if split_viewer_items:
            open_global_input(clear=True)
        else:
            global_comment["value"] = True
            other_direction_editor["open"] = False
            composer.frame.title = "WHOLE-SET COMMENT"
            input_heading["value"] = "WHOLE-SET GUIDANCE"
            input_area.text = ""
            event.app.layout.focus(input_area)

    @bindings.add("enter", filter=has_focus(input_area), eager=True)
    @bindings.add("c-s", filter=has_focus(input_area), eager=True)
    @bindings.add("f2", filter=has_focus(input_area), eager=True)
    def _submit_input(event) -> None:
        submit(event)

    @bindings.add("c-j", filter=has_focus(input_area), eager=True)
    def _insert_newline(event) -> None:
        input_area.buffer.insert_text("\n")
        event.app.invalidate()

    @bindings.add("enter", filter=has_focus(destination_input), eager=True)
    def _submit_destination(event) -> None:
        action = destination_action(destination_input.text.strip())
        if action is not None:
            event.app.exit(result=action)
        else:
            event.app.invalidate()

    @bindings.add("up", filter=has_focus(destination_input), eager=True)
    def _browse_destination_parents(event) -> None:
        if destination_editor_state["value"] is None:
            set_status("No parent Context catalog is available here.")
        else:
            event.app.layout.focus(destination_tree_control)
            set_status("Choose a parent Context with arrows, then press Enter.")
        event.app.invalidate()

    @bindings.add("down", filter=has_focus(destination_tree_control), eager=True)
    @bindings.add("up", filter=has_focus(destination_tree_control), eager=True)
    def _move_destination_parent(event) -> None:
        state = destination_editor_state["value"]
        if state is not None:
            delta = -1 if event.key_sequence[0].key == Keys.Up else 1
            state.tree.move(delta)
            set_status("")
        event.app.invalidate()

    @bindings.add("enter", filter=has_focus(destination_tree_control), eager=True)
    def _use_destination_parent(event) -> None:
        use_destination_parent()
        event.app.invalidate()

    @bindings.add("c-j", filter=has_focus(destination_input), eager=True)
    def _reject_destination_newline(event) -> None:
        set_status("A Context name must stay on one line.")
        event.app.invalidate()

    def exit_simple(event, kind: str) -> None:
        action = semantic_action(kind)
        if action is not None:
            event.app.exit(result=action)
        else:
            event.app.invalidate()

    @bindings.add("p", filter=~writable_input_focused)
    def _preserve(event) -> None:
        exit_simple(event, "PRESERVE_ALL")

    @bindings.add("d", filter=~writable_input_focused)
    def _defer(event) -> None:
        exit_simple(event, "DEFER")

    @bindings.add("a", filter=~writable_input_focused)
    def _accept(event) -> None:
        if split_viewer_items and review_and_apply:
            open_final_review()
            event.app.invalidate()
            return
        exit_simple(event, "ACCEPT")

    @bindings.add("s", filter=~writable_input_focused)
    def _sort(event) -> None:
        if toggle_sort is None:
            set_status("Sorting is unavailable here.")
        else:
            save_draft()
            toggle_sort()
            current_navigation.sync(current_view())
            load_draft()
            set_status("")
        event.app.invalidate()

    def _collapse_detail(event) -> bool:
        if event.app.layout.has_focus(input_area):
            return False
        if (
            split_viewer_items
            and session_navigation.pane == "responses"
            and response_state.close_nested()
        ):
            set_status("")
            return True
        if viewer_controller.close_nested():
            set_status("")
            return True
        if expanded_memory_section_uid["uid"] is not None:
            expanded_memory_section_uid["uid"] = None
            set_status("")
            return True
        if current_navigation.expanded_item_uid is None:
            return False
        current_navigation.close_detail()
        return True

    def _close(event) -> None:
        if (
            save_draft_on_close
            and not event.app.layout.has_focus(input_area)
            and not save_draft()
        ):
            event.app.invalidate()
            return
        event.app.exit(result=ResolutionWorkbenchAction(kind="CLOSE"))

    @bindings.add("escape", filter=has_focus(destination_input), eager=True)
    def _cancel_destination_edit(event) -> None:
        destination_editing["value"] = False
        destination_editor_state["value"] = (
            SaveLocationEditorState.create(destination)
            if destination is not None
            else None
        )
        if destination is not None:
            destination_frame.title = safe_terminal_text(destination.label)
        session_navigation.focus("save_location")
        event.app.layout.focus(destination_control)
        set_status("")
        event.app.invalidate()

    @bindings.add("escape", filter=has_focus(input_area), eager=True)
    def _cancel_response_edit(event) -> None:
        if not split_viewer_items:
            _close(event)
            return
        if global_comment["value"]:
            input_area.text = global_response_draft["value"].text
        else:
            load_draft()
        response_state.editing = False
        other_direction_editor["open"] = False
        if split_viewer_items and response_visible():
            session_navigation.focus("responses")
            event.app.layout.focus(responses_control)
        else:
            session_navigation.focus("viewer")
            event.app.layout.focus(body_control)
        set_status("Response edit cancelled.")
        event.app.invalidate()

    @bindings.add("escape", filter=~writable_input_focused, eager=True)
    @bindings.add("backspace", filter=~writable_input_focused, eager=True)
    def _back_or_close(event) -> None:
        if destination_tree_is_focused():
            _cancel_destination_edit(event)
            return
        if (
            split_viewer_items
            and session_navigation.pane == "responses"
            and response_state.close_nested()
        ):
            set_status("")
            event.app.invalidate()
            return
        if viewer_controller.close_nested():
            set_status("")
            event.app.invalidate()
            return
        if expanded_memory_section_uid["uid"] is not None:
            expanded_memory_section_uid["uid"] = None
            set_status("")
            event.app.invalidate()
            return
        if split_viewer_items and viewer_content["kind"] == "REVIEW":
            close_final_review()
            event.app.invalidate()
            return
        if (
            split_viewer_items
            and not event.app.layout.has_focus(input_area)
            and session_navigation.row_index != 0
        ):
            session_navigation.row_index = 0
            set_viewer_content("REPORT")
            reset_viewer_section()
            current_navigation.close_detail()
            session_navigation.focus("items")
            event.app.layout.focus(items_control)
            event.app.invalidate()
            return
        # Keep the shared shell independent of operation-specific back
        # dispatchers: its only presentation layer is the expanded detail.
        if _collapse_detail(event):
            event.app.invalidate()
            return
        _close(event)

    @bind_case_insensitive_key(
        bindings, "q", filter=~writable_input_focused, eager=True
    )
    @bindings.add("c-c", eager=True)
    def _quit(event) -> None:
        _close(event)

    bind_session_help(
        bindings,
        filter=~writable_input_focused,
        app_input=app_input,
        app_output=app_output,
        study_surface="resolution",
    )

    def footer_text() -> str:
        if status["value"]:
            return f" {status['value']}"
        active_view = current_view()
        item = current_navigation.current_item(active_view)
        if get_app().layout.has_focus(destination_input):
            navigation_help = (
                " ↑/Tab browse parents  Enter save exact location  Esc cancel "
            )
        elif destination_tree_is_focused():
            navigation_help = (
                " ↑/↓ parent  ←/→ expand  Enter use  Tab edit directly  "
                "Esc/Backspace cancel "
            )
        elif split_viewer_items and split_kind() == "SAVE_LOCATION":
            navigation_help = " Enter change location  Tab switch  Q close "
        elif split_viewer_items and split_kind() == "RESPONSES":
            if read_only:
                navigation_help = (
                    " ↑/↓ saved response  Tab switch  Esc/Backspace report "
                )
            elif response_state.option_navigation_active:
                navigation_help = (
                    " ↑/↓ choice/Response  Enter select  "
                    "Esc/Backspace report  Tab switch "
                )
            else:
                navigation_help = (
                    " ↑/↓ choice/Response  Enter write response  Tab switch  "
                    "Esc/Backspace report "
                )
        elif split_viewer_items and split_kind() == "REPORT":
            if focused_impact_entry_uid() is not None:
                navigation_help = (
                    " ↑/↓ Memory  → show  ← hide  Enter toggle  "
                    "Tab switch  Esc/Backspace close "
                )
            else:
                navigation_help = (
                    " ↑/↓ block (hold accelerates)  PgUp/PgDn page  End last  Tab switch  "
                    "Enter inspect  Esc/Backspace close "
                    if read_only
                    else " ↑/↓ block (hold accelerates)  PgUp/PgDn page  End last  Tab switch  "
                    "Enter open  Esc/Backspace/Q close "
                )
        elif split_viewer_items and split_kind() == "TODO":
            todo = displayed_todo()
            if viewer_content["kind"] == "REVIEW":
                final_action = review_action()
                navigation_help = (
                    f" Enter {final_action.kind.lower()}  "
                    "Tab inspect review  Esc/Backspace return "
                )
            else:
                todo_hint = (
                    "apply confirmation"
                    if todo.kind == "REVIEW AND APPLY"
                    else todo.kind.lower()
                )
                navigation_help = (
                    " Tab switch  Q close "
                    if todo.kind == "COMPLETE"
                    else f" Enter {todo_hint}  Tab switch  Esc/Backspace back "
                )
        elif split_viewer_items and split_kind() == "RESOLVE_ALL":
            if viewer_content["kind"] == "REVIEW":
                final_action = review_action()
                review_section = active_viewer_sections()[viewer_section_index()]
                enter_hint = (
                    "Enter return"
                    if review_section.kind == "SUMMARY"
                    else f"Enter {final_action.kind.lower()}"
                    if review_section.kind == "ACTION"
                    else "←/→ policy"
                )
                navigation_help = (
                    f" ↑/↓ review  Tab switch  {enter_hint}  "
                    "Esc/Backspace return "
                )
            else:
                navigation_help = (
                    " ↑/↓ section/item  Tab switch  ←/→ strategy  "
                    "Enter open/run  C custom  Esc/Backspace report "
                )
        elif viewer_controller.nested_uid is not None:
            navigation_help = (
                " ↑/↓ scroll Memory  Enter/Esc/Backspace back  Tab switch "
            )
        elif (
            split_viewer_items
            and viewer_content["kind"] == "ITEM"
            and session_navigation.pane == "viewer"
            and active_viewer_sections()[viewer_section_index()].kind == "SOURCE_MEMORY"
        ):
            navigation_help = (
                " Enter read Memory  ↑/↓ section  Esc/Backspace back  Tab switch "
            )
        elif (
            split_viewer_items
            and viewer_content["kind"] == "ITEM"
            and session_navigation.pane == "viewer"
            and active_viewer_sections()[viewer_section_index()].kind == "MEMORY_ROW"
        ):
            navigation_help = (
                " Enter show/hide evidence  ↑/↓ Memory  Esc/Backspace back  Tab switch "
            )
        elif split_viewer_items and read_only:
            navigation_help = (
                " ↑/↓ section/item  Tab switch  Enter inspect  "
                "Esc/Backspace report "
            )
        elif split_viewer_items:
            navigation_help = (
                " ↑/↓ section  Tab Responses/Items  C response/comment  "
                "Esc/Backspace report "
            )
        elif (
            item is not None
            and current_navigation.expanded_item_uid == item.uid
            and item.options
        ):
            navigation_help = (
                " ↑/↓ option  Enter choose/clear  Esc/Backspace back  Tab comment "
            )
        elif current_navigation.expanded_item_uid is not None:
            navigation_help = " Enter close  Esc/Backspace back  Tab comment "
        else:
            navigation_help = (
                " ↑/↓ item  Enter detail  Shift-Tab switch  Tab/C comment "
                if split_viewer_items
                else " ↑/↓ item  Enter detail  Tab comment "
            )
        actions: list[str] = []
        if "SUBMIT_ALL" in active_view.capabilities:
            actions.append("G comment all")
        if "PRESERVE_ALL" in active_view.capabilities:
            actions.append("P preserve all")
        if "DEFER" in active_view.capabilities:
            actions.append("D defer")
        if "ACCEPT" in active_view.capabilities:
            actions.append("A review & apply" if review_and_apply else "A accept")
        if toggle_sort is not None:
            actions.append("S sort")
        if not (
            get_app().layout.has_focus(input_area)
            or get_app().layout.has_focus(destination_input)
        ):
            actions.append("H Help")
        if get_app().layout.has_focus(body_control):
            actions.append("y/Y copy")
        actions.append("Q close")
        state_label = (
            f" READ ONLY · {safe_terminal_text(active_view.status)} ·"
            if read_only
            else ""
        )
        return state_label + navigation_help + "  ".join(actions) + " "

    footer = Window(
        FormattedTextControl(footer_text),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    legacy_inline_input = ConditionalContainer(
        HSplit(
            [
                Window(
                    FormattedTextControl(lambda: input_heading["value"]),
                    height=Dimension.exact(1),
                    char="─",
                ),
                input_area,
            ],
            height=Dimension.exact(5),
        ),
        filter=has_focus(input_area),
    )
    if split_viewer_items:
        viewer_frame = Frame(body, title="VIEWER")
        decision_container = ConditionalContainer(
            responses_window,
            filter=Condition(
                lambda: (
                    (target := current_response_target()) is not None
                    and target.has_decision
                )
            ),
        )
        responses_frame = Frame(
            HSplit([decision_container, composer.frame]),
            title="RESPONSES",
        )
        responses_container = ConditionalContainer(
            responses_frame,
            filter=Condition(response_visible),
        )
        items_frame = Frame(items_window, title="ITEMS")
        todo_frame = Frame(todo_window, title="TO DO")
        session_frames = [viewer_frame, responses_container, items_frame]
        if destination_available:
            session_frames.append(destination_frame)
        session_frames.extend([todo_frame, footer])
        # ``split_viewer_items`` separates semantic surfaces, not columns.
        # Compose those peer frames through the same one-column rule used by
        # Find and every other session workbench.
        root = build_tui_frame(*(TuiRegion(frame) for frame in session_frames))
        bind_focused_frame_style(
            viewer_frame,
            is_focused=lambda: session_navigation.pane == "viewer",
        )
        # Bind the nested box first. Its border glyphs become dynamic, so the
        # later outer-frame binding cannot accidentally make both surfaces
        # look focused at once.
        bind_focused_frame_style(
            composer.frame,
            is_focused=lambda: (
                session_navigation.pane == "composer"
                or (
                    session_navigation.pane == "responses"
                    and response_state.section == "RESPONSE"
                )
            ),
        )
        bind_focused_frame_style(
            responses_frame,
            is_focused=lambda: session_navigation.pane in {"responses", "composer"},
        )
        bind_focused_frame_style(
            items_frame,
            is_focused=lambda: session_navigation.pane == "items",
        )
        if destination_available:
            bind_focused_frame_style(
                destination_frame,
                is_focused=lambda: session_navigation.pane == "save_location",
            )
        bind_focused_frame_style(
            todo_frame,
            is_focused=lambda: session_navigation.pane == "todo",
        )
        focused_element = {
            "viewer": body_control,
            "responses": responses_control,
            "items": items_control,
            "save_location": destination_control,
            "todo": todo_control,
        }[session_navigation.pane]
    else:
        viewer_frame = Frame(HSplit([body, legacy_inline_input]), title="VIEWER")
        bind_focused_frame_style(
            viewer_frame,
            is_focused=lambda: True,
        )
        root = build_tui_frame(
            TuiRegion(viewer_frame),
            TuiRegion(footer),
        )
        focused_element = body_control
    application: Application[ResolutionWorkbenchAction] = Application(
        layout=Layout(root, focused_element=focused_element),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles(
            [
                MEMCOMMIT_TUI_STYLE,
                RESOLUTION_WORKBENCH_STYLE,
            ]
        ),
    )
    load_draft()

    def decision_free_apply_available() -> bool:
        if read_only or not review_and_apply:
            return False
        active_view = current_view()
        unresolved_required = any(
            item.effective_obligation == "REQUIRED"
            and not _item_is_answered(item, local_drafts)
            for item in active_view.items
        )
        if unresolved_required:
            return False
        todo = session_todo_view(
            active_view,
            local_drafts,
            review_and_apply=review_and_apply,
            read_only=read_only,
            whole_set_available=bool(global_strategies),
            read_only_handoff=read_only_handoff,
            item_handoff=current_item_handoff(),
        )
        if todo.kind != "REVIEW AND APPLY":
            return False
        review_action = session_review_action_view(
            active_view,
            local_drafts,
            whole_set_available=bool(global_strategies),
        )
        return review_action.kind in {"APPLY", "APPLY AS IS"}

    if (
        decision_free_behavior == "AUTO_ACCEPT"
        and decision_free_apply_available()
    ):
        automatic = semantic_action("ACCEPT")
        if automatic is not None:
            record_study_action(
                "DECISION_FREE_AUTO_ACCEPT",
                surface="resolution",
                action=automatic.kind,
            )
            record_study_action(
                "TUI_ACTION",
                surface="resolution",
                action=automatic.kind,
            )
            return automatic

    if compact_decisions:

        def selected_compact_option(item_uid: str) -> str | None:
            item = current_view().item(item_uid)
            return _item_draft(item, local_drafts).selected_choice_uid

        def stage_compact_option(item_uid: str, option_uid: str) -> None:
            item = current_view().item(item_uid)
            item.option(option_uid)
            existing = _item_draft(item, local_drafts)
            draft = ResponseDraft(option_uid, existing.text)
            local_drafts[item_uid] = draft
            if draft_saver is not None:
                draft_saver(item_uid, option_uid, draft.text)

        def compact_continue_action(
            focused_item_uid: str | None,
        ) -> ResolutionWorkbenchAction | None:
            active_view = current_view()
            action = final_review_action(active_view, open_custom=False)
            if action is not None:
                return action
            if focused_item_uid is None:
                return None
            draft = _item_draft(active_view.item(focused_item_uid), local_drafts)
            if draft.selected_choice_uid is None and not draft.text.strip():
                return None
            return semantic_action(
                "SUBMIT_ITEM",
                item_uid=focused_item_uid,
                option_uid=draft.selected_choice_uid,
                comment=draft.text,
            )

        def compact_continue_label() -> str:
            todo = session_todo_view(
                current_view(),
                local_drafts,
                review_and_apply=review_and_apply,
                read_only=read_only,
                whole_set_available=bool(global_strategies),
                read_only_handoff=read_only_handoff,
                item_handoff=current_item_handoff(),
            )
            return {
                "REVIEW AND APPLY": "Apply",
                "RESOLVE ALL": "Continue",
                "COMPLETE": "Close",
            }.get(todo.kind, "Submit selected")

        return run_compact_resolution_decisions(
            current_view,
            selected_option=selected_compact_option,
            stage_option=stage_compact_option,
            build_continue_action=compact_continue_action,
            build_simple_action=lambda kind: semantic_action(kind),
            continue_label=compact_continue_label,
            turn_command_review=turn_command_review,
            app_input=app_input,
            app_output=app_output,
        )

    def open_initial_final_review() -> None:
        if (
            decision_free_behavior == "FINAL_REVIEW"
            and decision_free_apply_available()
        ):
            open_final_review()

    try:
        result = application.run(pre_run=open_initial_final_review)
    except (EOFError, KeyboardInterrupt):
        result = ResolutionWorkbenchAction(kind="CLOSE")
    record_study_action(
        "TUI_ACTION",
        surface="resolution",
        action=result.kind,
    )
    return result
