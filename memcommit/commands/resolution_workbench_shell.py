"""Shared list/detail/comment shell for semantic resolution adapters."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import (
    ConditionalContainer,
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

from memcommit.commands.tui_primitives import (
    MEMCOMMIT_TUI_STYLE,
    NavigationAccelerator,
    SEMANTIC_VIEWER_STYLE,
    TuiRegion,
    WrappedScrollbarMargin,
    bind_focused_frame_style,
    build_framed_multiline_input,
    build_tui_frame,
    focused_control_style,
    navigable_tree_row_prefix,
    require_interactive_terminal,
    safe_terminal_text,
)
from memcommit.commands.semantic_detail_renderer import (
    semantic_detail_block_fragments,
    semantic_detail_header_fragments,
    semantic_memory_row_fragments,
    semantic_trace_fragments,
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
from memcommit.session_workbench_navigation import (
    SessionWorkbenchNavigation,
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


@dataclass(frozen=True)
class ResolutionDestination:
    """One operation-owned local materialization name shown before Apply."""

    value: str
    label: str = "SAVE LOCATION"
    detail: str = "Press Enter to edit the exact local Context name."
    validate: Callable[[str], None] | None = None


@dataclass(frozen=True)
class SessionTodoView:
    """One state-derived next action shown below a session's Items frame."""

    kind: str
    label: str
    detail: str
    unresolved_item_uids: tuple[str, ...] = ()


def _item_draft(
    item: ResolutionItem,
    drafts: dict[str, tuple[str | None, str]],
) -> tuple[str | None, str]:
    """Return the live draft or the adapter's durable response projection."""

    return drafts.get(
        item.uid,
        (item.selected_option_uid, item.response_text),
    )


def _item_is_answered(
    item: ResolutionItem,
    drafts: dict[str, tuple[str | None, str]],
) -> bool:
    if item.response_state == "NOT_APPLICABLE":
        return True
    # A live draft is authoritative even when it deliberately clears a
    # durable answer; otherwise the To Do pane can keep reporting the item as
    # answered after its selected option is cancelled.
    if item.uid in drafts:
        option_uid, comment = drafts[item.uid]
        return bool(option_uid or comment.strip())
    if item.response_state == "ANSWERED":
        return True
    option_uid, comment = _item_draft(item, drafts)
    return bool(option_uid or comment.strip())


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
    drafts: dict[str, tuple[str | None, str]],
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
    drafts: dict[str, tuple[str | None, str]],
    *,
    review_and_apply: bool,
    read_only: bool,
    whole_set_available: bool = True,
    read_only_handoff: SessionTodoView | None = None,
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
    if review_and_apply and (view.accept_enabled or whole_set_available):
        action = session_review_action_view(
            view,
            drafts,
            whole_set_available=whole_set_available,
        )
        return SessionTodoView(
            "REVIEW AND APPLY",
            f"Review final {view.operation.title()} action",
            f"{action.kind} is available. Enter to review before anything changes.",
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
    drafts: dict[str, tuple[str | None, str]],
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
    return todo.kind, todo.detail, False


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
    normalized = " ".join(safe_terminal_text(value).split())
    if sum(get_cwidth(character) for character in normalized) <= limit:
        return normalized
    kept: list[str] = []
    width = 0
    for character in normalized:
        character_width = get_cwidth(character)
        if width + character_width > limit - 1:
            break
        kept.append(character)
        width += character_width
    return "".join(kept).rstrip() + "…"


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
    return sum(get_cwidth(character) for character in value)


def _visual_pad(value: str, width: int) -> str:
    return value + (" " * max(0, width - _visual_width(value)))


def _visual_wrap(value: str, width: int) -> list[str]:
    """Wrap terminal text by display cells while retaining paragraph breaks."""
    wrapped: list[str] = []
    for source_line in safe_terminal_text(value).splitlines() or [""]:
        if not source_line.strip():
            wrapped.append("")
            continue
        leading = source_line[: len(source_line) - len(source_line.lstrip(" "))]
        content_width = max(1, width - _visual_width(leading))
        current = ""
        for word in source_line.strip().split():
            candidate = word if not current else f"{current} {word}"
            if _visual_width(candidate) <= content_width:
                current = candidate
                continue
            if current:
                wrapped.append(leading + current)
                current = ""
            chunk = ""
            for character in word:
                if chunk and _visual_width(chunk + character) > content_width:
                    wrapped.append(leading + chunk)
                    chunk = ""
                chunk += character
            current = chunk
        if current:
            wrapped.append(leading + current)
    return wrapped or [""]


def _source_memory_lines(content: str, content_width: int) -> tuple[str, ...]:
    """Wrap one source Memory into independently navigable display rows."""

    # Reserve the first-row short UID and continuation indentation. The
    # returned rows remain presentation-only slices of one Memory object.
    return tuple(_visual_wrap(content, max(1, content_width - 16)))


def _evidence_section_count(evidence, content_width: int) -> int:
    """Count Classification, criterion, source-line, and Why stops."""

    source_line_count = sum(
        len(_source_memory_lines(source.content, content_width))
        for claim in evidence.source_groups
        for source in claim.sources
    )
    return 2 + len(evidence.criterion_blocks) + source_line_count


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


def _boxed_lines(title: str, body: str, *, width: int = 72) -> list[str]:
    """Return a fixed-width terminal card small enough for the Viewer pane."""
    inner_width = width - 2
    body_width = width - 4
    label = f"─ {_line(title, inner_width - 3)} "
    lines = [f"╭{label}{'─' * (inner_width - _visual_width(label))}╮"]
    lines.extend(
        f"│ {_visual_pad(line, body_width)} │"
        for line in _visual_wrap(body, body_width)
    )
    lines.append(f"╰{'─' * inner_width}╯")
    return lines


def _viewer_focus_fragments(
    fragments: list[tuple[str, str]],
    *,
    focused: bool,
) -> list[tuple[str, str]]:
    """Hide positional emphasis when the Viewer is not the active pane."""
    if focused:
        return fragments
    inactive_style = {
        "class:viewer-section": "class:section",
        "class:detail-card.focused": "class:detail-card",
        "class:memory-object.focused": "class:memory-object",
        "class:impact.keep.focused": "class:memory-object",
        "class:impact.redact.focused": "class:memory-object",
        "class:impact.summarize.focused": "class:memory-object",
        "class:impact.reframe.focused": "class:memory-object",
        "class:impact.forget.focused": "class:memory-object",
        "class:impact.custom.focused": "class:memory-object",
        "class:impact.other.focused": "class:memory-object",
        "class:option-card.focused": "class:option-card",
        "class:option-card.other": "class:option-card",
        "class:choice": "",
    }
    return [(inactive_style.get(style, style), text) for style, text in fragments]


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
    if view.overview:
        fragments.extend(
            [
                ("class:section", " WHAT MEM UNDERSTOOD\n"),
                ("", f" {safe_terminal_text(view.overview)}\n\n"),
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
        for option in item.options:
            cursor = option.uid == navigation.option_cursor_uid
            chosen = option.uid == navigation.selected_option_uid
            if cursor:
                fragments.append(("[SetCursorPosition]", ""))
            fragments.append(
                (
                    "class:choice" if cursor else "",
                    (
                        f"       {'›' if cursor else ' '} "
                        f"{'●' if chosen else '○'} "
                        f"{safe_terminal_text(option.label)}\n"
                    ),
                )
            )
            if option.text != option.label:
                fragments.append(
                    (
                        "",
                        f"          {safe_terminal_text(option.text)}\n",
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
    fragments.extend(
        [
            ("", "\n"),
            (
                "class:section",
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
            + bool(item.question or item.options)
            + sum(len(block.memory_rows) or 1 for block in item.blocks)
            + 1
            + bool(inline_action)
        )
        if presentation is not None
        else (
            1
            + sum(len(block.memory_rows) or 1 for block in item.blocks)
            + bool(item.evidence_refs)
            + bool(item.question)
            + bool(item.options)
        )
    )
    focused_section = max(0, min(focused_section, section_count - 1))
    section_index = 0

    def report_section(parts: list[tuple[str, str]]) -> None:
        nonlocal section_index
        active = section_index == focused_section
        if active:
            fragments.append(("[SetCursorPosition]", ""))
        for style, text in parts:
            focused_style = (
                "class:viewer-section"
                if active
                and style
                in {
                    "class:section",
                    "class:case-title",
                    "class:detail-heading",
                    "class:block-heading",
                }
                else "class:detail-card.focused"
                if active and style == ""
                else "class:memory-object.focused"
                if active and style == "class:memory-object"
                else style
            )
            fragments.append((focused_style, text))
        if active:
            # As in Result Workbench, keep the complete semantic block visible
            # rather than anchoring only its heading at the viewport edge.
            fragments.append(("[SetCursorPosition]", ""))
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
        if active:
            fragments.append(("[SetCursorPosition]", ""))
        outer_style = "class:detail-card.focused" if active else "class:detail-card"
        if prompt_heading:
            fragments.extend(
                [
                    (
                        "class:viewer-section" if active else "class:block-heading",
                        f" {safe_terminal_text(prompt_heading)}\n",
                    ),
                    (
                        "class:detail-card.focused" if active else "",
                        f" {safe_terminal_text(prompt_text)}\n",
                    ),
                ]
            )
        outer_width = max(20, content_width - 1)
        outer_body_width = outer_width - 4
        top, bottom = _boxed_lines(heading, "", width=outer_width)[::2]
        fragments.append((outer_style, f" {top}\n"))
        guidance = (
            "↑/↓ move · Enter select · Esc/Backspace back"
            if option_navigation_active
            else "Enter to choose an option"
        )
        for guidance_line in _visual_wrap(guidance, outer_body_width):
            fragments.append(
                (
                    outer_style,
                    f" │ {_visual_pad(guidance_line, outer_body_width)} │\n",
                )
            )
        fragments.append((outer_style, f" │{' ' * outer_body_width}│\n"))

        choices = [
            (
                index,
                option.label,
                option.text,
                (
                    active
                    and option_navigation_active
                    and not other_direction_focused
                    and option.uid == navigation.option_cursor_uid
                ),
                option.uid == navigation.selected_option_uid,
                False,
            )
            for index, option in enumerate(item.options, start=1)
        ]
        choices.append(
            (
                len(item.options) + 1,
                other_label,
                other_text,
                active and option_navigation_active and other_direction_focused,
                False,
                True,
            )
        )
        for choice_index, label, text, cursor, chosen, is_other in choices:
            marker = "✓" if chosen else ("◇" if is_other else "○")
            if cursor and is_other:
                choice_style = "class:option-card.other"
            elif cursor:
                choice_style = "class:option-card.focused"
            elif chosen:
                choice_style = "class:option-card.selected"
            else:
                choice_style = "class:option-card"
            if cursor:
                # Keep the whole active row visible when the inline Other
                # direction editor reduces the Viewer height.
                fragments.append(("[SetCursorPosition]", ""))
            pointer = "›" if cursor else " "
            choice_heading = (
                f"{pointer} {marker} {choice_index}. {safe_terminal_text(label)}"
            )
            heading_width = max(1, outer_body_width - 2)
            for heading_line in _visual_wrap(choice_heading, heading_width):
                fragments.extend(
                    [
                        (outer_style, " │ "),
                        (
                            choice_style,
                            _visual_pad(
                                heading_line,
                                heading_width,
                            ),
                        ),
                        (outer_style, " │\n"),
                    ]
                )
            description_width = max(1, outer_body_width - 6)
            for description_line in _visual_wrap(text, description_width):
                fragments.extend(
                    [
                        (outer_style, " │     "),
                        (
                            choice_style,
                            _visual_pad(description_line, description_width),
                        ),
                        (outer_style, " │\n"),
                    ]
                )
            if choice_index < len(choices):
                fragments.append((outer_style, f" │{' ' * outer_body_width}│\n"))
        fragments.append((outer_style, f" {bottom}\n"))
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
        for evidence in presentation.evidence:
            report_section(
                [
                    (
                        "class:block-heading",
                        f" {safe_terminal_text(evidence.heading)}\n",
                    ),
                    ("class:block-heading", "\n CLASSIFICATION\n"),
                    ("", f" {safe_terminal_text(evidence.classification)}\n"),
                ]
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
            for claim in evidence.source_groups:
                for source_index, source in enumerate(claim.sources):
                    lines = _source_memory_lines(source.content, content_width)
                    for line_index, line in enumerate(lines):
                        source_parts: list[tuple[str, str]] = []
                        if source_index == 0 and line_index == 0:
                            source_parts.append(
                                (
                                    "class:block-heading",
                                    (
                                        f"\n {safe_terminal_text(claim.label)} · FROM "
                                        f"{safe_terminal_text(claim.context_name)}\n"
                                    ),
                                )
                            )
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
                        report_section(source_parts)
            report_section(
                [
                    (
                        "class:block-heading",
                        f"\n {safe_terminal_text(evidence.reason_heading)}\n",
                    ),
                    ("", f" {safe_terminal_text(evidence.reason)}\n"),
                ]
            )
        if item.options:
            options_card(
                heading=presentation.options_heading,
                other_label=presentation.other_option_label,
                other_text=("Press Enter and write a different answer here."),
                prompt_heading=(presentation.prompt_heading if item.question else ""),
                prompt_text=item.question,
            )
        elif item.question:
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
    if item.question:
        report_section(
            semantic_detail_block_fragments(
                heading="QUESTION",
                text=item.question,
            )
        )
    if item.options:
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
    return fragments


def resolution_report_fragments(
    view: ResolutionWorkbenchView,
    *,
    strategies: tuple[ResolutionGlobalStrategy, ...] = (),
    drafts: dict[str, tuple[str | None, str]] | None = None,
    focused_section: int = 0,
    review_and_apply: bool = False,
    read_only: bool = False,
    impact_controller: ImpactController | None = None,
    expanded_impact_section_uid: str | None = None,
    destination: ResolutionDestination | None = None,
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
    show_results = not impact_repeats_results
    report_item_sections = (
        0 if view.report_items_summary is not None else len(view.items)
    )
    section_count = (
        report_item_sections
        + 3
        + (not read_only)
        + show_results
        + (impact is not None)
        + (len(impact.entries) if impact is not None else 0)
        + (destination is not None and not read_only)
    )
    focused_section = max(0, min(focused_section, section_count - 1))
    section_index = 0
    fragments: list[tuple[str, str]] = []
    draft_values = drafts or {}

    def heading(text: str, *, style: str = "class:section") -> None:
        nonlocal section_index
        active = section_index == focused_section
        if active:
            fragments.append(("[SetCursorPosition]", ""))
        fragments.append(
            (
                "class:viewer-section" if active else style,
                f" ── {safe_terminal_text(text)} ──\n"
                if active
                else f" {safe_terminal_text(text)}\n",
            )
        )
        section_index += 1

    heading(view.title, style="class:title")
    fragments.extend(
        [
            ("", f" {safe_terminal_text(view.route)}\n"),
            (
                "",
                f" {safe_terminal_text(view.status)}"
                + (f" · {metric_text}" if metric_text else "")
                + "\n\n",
            ),
        ]
    )
    heading("WHAT MEM UNDERSTOOD")
    fragments.append(("", f" {safe_terminal_text(view.overview) or '(none)'}\n\n"))
    if view.report_items_summary is not None:
        heading(view.report_items_summary.heading)
        fragments.append(
            ("", f" {safe_terminal_text(view.report_items_summary.text)}\n\n")
        )
    else:
        heading(f"{view.list_label} · {len(view.items)}")
        if not view.items:
            fragments.append(("", f"  {safe_terminal_text(view.empty_message)}\n"))
        for index, item in enumerate(view.items, start=1):
            heading(f"{_item_kind_label(item)} {index} · {item.title}")
            fragments.extend(
                [
                    (
                        "",
                        f" [{safe_terminal_text(item.priority)}] {safe_terminal_text(item.summary)}\n",
                    ),
                    (
                        "",
                        (
                            f" QUESTION · {safe_terminal_text(item.question)}\n\n"
                            if item.question
                            else "\n"
                        ),
                    ),
                ]
            )
    if show_results:
        heading(f"{view.results_label} · {len(view.results)}")
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
            fragments.append(("", " Focus a Memory and press Enter to show why.\n"))
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
            prefix = navigable_tree_row_prefix(
                selected=active,
                depth=1,
                branch=entry.marker,
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
            expanded = expanded_impact_section_uid == entry_section_uid
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
            if active:
                # Anchor after the complete row so wrapped or expanded detail
                # remains visible as one semantic Impact Memory.
                fragments.append(("[SetCursorPosition]", ""))
            section_index += 1
    if destination is not None and not read_only:
        heading(destination.label)
        fragments.append(
            (
                "",
                f" {safe_terminal_text(destination.value)}\n"
                f" {safe_terminal_text(destination.detail)}\n\n",
            )
        )
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
        heading(action_heading)
        fragments.append(
            (
                "",
                f" {action_detail}\n",
            )
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
    destination: ResolutionDestination | None = None,
    drafts: dict[str, tuple[str | None, str]] | None = None,
) -> list[str]:
    lines = report_text.splitlines()
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
    if destination is not None and not read_only:
        lines.extend(
            [
                "",
                destination.label,
                destination.value,
                destination.detail,
            ]
        )
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
        "INCORPORATE RESPONSES",
        "IMPACT ·",
        "APPLY CHANGES ·",
        "APPLY AS IS ·",
        "SAVE LOCATION",
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
                "INCORPORATE RESPONSES",
                "APPLY CHANGES ·",
                "APPLY AS IS ·",
                "SAVE LOCATION",
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
                        "INCORPORATE RESPONSES",
                        "APPLY CHANGES ·",
                        "APPLY AS IS ·",
                    )
                )
                else "DESTINATION"
                if line.startswith("SAVE LOCATION")
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
    strategies: tuple[ResolutionGlobalStrategy, ...] = (),
    drafts: dict[str, tuple[str | None, str]] | None = None,
    report_item_badges: tuple[str, ...] = (),
    report_conflicts_remaining: int | None = None,
    selected_strategy_index: int = 0,
    focused_section: int = 0,
    review_and_apply: bool = False,
    read_only: bool = False,
    impact_controller: ImpactController | None = None,
    destination: ResolutionDestination | None = None,
    content_width: int = 76,
) -> list[tuple[str, str]]:
    """Render Compare and Meld report sections as nested Viewer cards."""
    lines = _seeded_report_lines(
        view,
        report_text,
        strategies,
        review_and_apply=review_and_apply,
        read_only=read_only,
        impact_controller=impact_controller,
        destination=destination,
        drafts=drafts,
    )
    sections = _seeded_report_sections(lines)
    if not sections:
        return [("", safe_terminal_text("\n".join(lines)))]
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
            if group_active:
                fragments.append(("[SetCursorPosition]", ""))
            fragments.append(
                (
                    "class:detail-card.focused"
                    if group_active
                    else "class:detail-card",
                    f" ╭{label}{'─' * (inner_width - _visual_width(label))}╮\n",
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
                    option_uid, comment = _item_draft(item, draft_values)
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
                heading_style = (
                    "class:viewer-section" if item_active else "class:section"
                )
                fragments.append(
                    (
                        heading_style,
                        f" │   {conflict_heading}\n",
                    )
                )
                badge_visual_lines = (
                    _visual_wrap(badge, inner_width - 6) if badge else []
                )
                body_visual_lines = _visual_wrap(
                    "\n".join(item_body[(2 if badge else 0) :]),
                    inner_width - 6,
                )
                for badge_line in badge_visual_lines:
                    fragments.append(
                        (
                            "class:selection-badge",
                            f" │     {_visual_pad(badge_line, inner_width - 6)} │\n",
                        )
                    )
                if badge_visual_lines:
                    fragments.append(("class:detail-card", f" │{' ' * inner_width}│\n"))
                for body_line in body_visual_lines:
                    fragments.append(
                        (
                            (
                                "class:detail-card.focused"
                                if item_active
                                else "class:detail-card"
                            ),
                            f" │     {_visual_pad(body_line, inner_width - 6)} │\n",
                        )
                    )
                if item_active:
                    # Anchor after the complete conflict so prompt-toolkit
                    # scrolls its body into view, not merely its first line.
                    fragments.append(("[SetCursorPosition]", ""))
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
            style = "class:memory-object.focused" if active else "class:memory-object"
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
            for line_index, content_line in enumerate(wrapped_content):
                lead = prefix + identity if line_index == 0 else content_indent
                fragments.append((style, f" {lead}{content_line}\n"))
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
                    fragments.append((style, f" {lead}{reason_line}\n"))
            if active:
                # A trailing anchor keeps the complete wrapped Memory and WHY
                # visible whenever this independently focusable block fits.
                fragments.append(("[SetCursorPosition]", ""))
            if section_index < len(sections) - 1:
                fragments.append(("", "\n"))
            section_index += 1
            continue

        if title.startswith(("PROPOSED TARGET MEMORIES", "PROPOSED BASELINE CHANGES")):
            active = section_index == focused_section
            if active:
                fragments.append(("[SetCursorPosition]", ""))
            fragments.append(
                (
                    "class:viewer-section" if active else "class:section",
                    f" {safe_terminal_text(title)}\n",
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
                option_uid, comment = _item_draft(item, draft_values)
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
        card_lines = _boxed_lines(
            title,
            "\n".join(body_lines),
            width=card_width,
        )
        anchor_at_end = active
        badge_line_count = (
            len(_visual_wrap(badge, max(1, card_width - 4))) if badge else 0
        )
        for card_line_index, card_line in enumerate(card_lines):
            style = "class:detail-card.focused" if active else "class:detail-card"
            if badge and 1 <= card_line_index <= badge_line_count:
                style = "class:selection-badge"
            fragments.append((style, f" {safe_terminal_text(card_line)}\n"))
        if anchor_at_end:
            # A block-end anchor exposes the complete card when it fits. This
            # is especially important for the terminal apply boundary after a
            # long result list, but applies equally to ordinary report cards.
            fragments.append(("[SetCursorPosition]", ""))
        if section_index < len(sections) - 1:
            fragments.append(("", "\n"))
        section_index += 1
    return fragments


def resolution_review_fragments(
    view: ResolutionWorkbenchView,
    drafts: dict[str, tuple[str | None, str]],
    strategies: tuple[ResolutionGlobalStrategy, ...],
    strategy_index: int,
    action: SessionTodoView,
    focused_section: int = 0,
    content_width: int = 76,
) -> list[tuple[str, str]]:
    """Render the explicit final review without performing its action."""

    show_policy = action.kind in {
        "INCORPORATE RESPONSES",
        "INCORPORATE AND APPLY",
    }
    section_count = 3 if show_policy else 2
    focused_section = max(0, min(focused_section, section_count - 1))
    fragments: list[tuple[str, str]] = []
    answered = 0
    response_lines: list[str] = []
    unresolved_counts: dict[str, int] = {}
    reviewable = 0
    for index, item in enumerate(view.items, start=1):
        obligation = item.effective_obligation
        if obligation == "NONE":
            continue
        reviewable += 1
        option_uid, comment = _item_draft(item, drafts)
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

    if not response_lines:
        response_lines.append("No staged issue responses yet.")
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
    response_lines.extend(
        [
            f"RESPONSES · {answered}/{reviewable} ANSWERED",
            f"OPEN REVIEWS · {remaining_summary}",
            "Nothing changes until the final action below is confirmed.",
        ]
    )

    if focused_section == 0:
        fragments.append(("[SetCursorPosition]", ""))
    for line in _boxed_lines(
        "REVIEW AND APPLY",
        "\n".join(response_lines).rstrip(),
        width=max(24, content_width - 1),
    ):
        fragments.append(
            (
                "class:detail-card.focused"
                if focused_section == 0
                else "class:detail-card",
                f" {line}\n",
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
        policy_box = _boxed_lines(
            "REMAINING-ITEM POLICY",
            "\n".join(policy_lines) or "No unresolved-conflict policies are available.",
            width=max(24, content_width - 1),
        )
        for index, line in enumerate(policy_box):
            if focused_section == 1 and index == len(policy_box) - 1:
                fragments.append(("[SetCursorPosition]", ""))
            fragments.append(
                (
                    "class:option-card.focused"
                    if focused_section == 1
                    else "class:detail-card",
                    f" {line}\n",
                )
            )
        fragments.append(("", "\n"))
        action_section = 2

    action_box = _boxed_lines(
        action.kind,
        f"{action.label}\n{action.detail}\nEsc/Backspace returns without applying.",
        width=max(24, content_width - 1),
    )
    for index, line in enumerate(action_box):
        if focused_section == action_section and index == len(action_box) - 1:
            fragments.append(("[SetCursorPosition]", ""))
        fragments.append(
            (
                "class:detail-card.focused"
                if focused_section == action_section
                else "class:detail-card",
                f" {line}\n",
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
    save_draft_on_close: bool = False,
    toggle_sort: Callable[[], None] | None = None,
    split_viewer_items: bool = False,
    global_strategies: tuple[ResolutionGlobalStrategy, ...] = (),
    split_report_text: str | None = None,
    split_report_item_badges: tuple[str, ...] = (),
    split_report_conflicts_remaining: int | None = None,
    review_and_apply: bool = False,
    read_only: bool = False,
    read_only_handoff: SessionTodoView | None = None,
    impact_controller: ImpactController | None = None,
    destination: ResolutionDestination | None = None,
) -> ResolutionWorkbenchAction:
    """Collect one UID-bound semantic or close action; never call a provider."""
    if require_tty:
        require_interactive_terminal(
            terminal_label,
            snapshot_hint=snapshot_hint,
        )
    current_navigation = navigation or ResolutionNavigation()
    supplier = (
        view_or_supplier if callable(view_or_supplier) else lambda: view_or_supplier
    )

    def current_view() -> ResolutionWorkbenchView:
        view = supplier()
        current_navigation.sync(view)
        return view

    session_navigation = workbench_navigation or SessionWorkbenchNavigation(
        pane="items" if split_viewer_items else "viewer"
    )
    if not split_viewer_items:
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
                destination=destination,
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
            return _stable_sections(entries)
        entries: list[tuple[str, str, int | None]] = [
            ("TITLE", "REPORT:TITLE", 0),
            ("UNDERSTANDING", "REPORT:UNDERSTANDING", 0),
            ("REVIEW_ITEMS", "REPORT:REVIEW_ITEMS", 0),
        ]
        if active_view.report_items_summary is None:
            entries.extend(
                ("ITEM", f"ITEM:{item.uid}", index)
                for index, item in enumerate(active_view.items, start=1)
            )
        active_impact = _current_impact(impact_controller, active_view)
        impact_repeats_results = _impact_repeats_results(
            active_impact,
            active_view,
        )
        if not impact_repeats_results:
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
        if destination is not None and not read_only:
            entries.append(("DESTINATION", "REPORT:DESTINATION", None))
        if not read_only:
            entries.append(
                (
                    "REVIEW_AND_APPLY" if review_and_apply else "RESOLVE_ALL",
                    "REPORT:ACTION",
                    None,
                )
            )
        return _stable_sections(tuple(entries))

    def inline_item_action() -> SessionTodoView | None:
        """Mirror the existing batch-incorporation boundary below Response."""

        if not review_and_apply or read_only or not global_strategies:
            return None
        action = session_review_action_view(
            current_view(),
            local_drafts,
            whole_set_available=True,
        )
        if action.kind not in {"INCORPORATE RESPONSES", "INCORPORATE AND APPLY"}:
            return None
        # The inline item route retains the narrower incorporation boundary;
        # only the dedicated final-review surface can authorize the compound
        # incorporate-and-apply action.
        return SessionTodoView(
            "INCORPORATE RESPONSES",
            "Incorporate saved responses",
            "Enter to create a revised proposal without applying it yet.",
        )

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
                        entries.extend(
                            (
                                "SOURCE_MEMORY_LINE",
                                (
                                    f"{evidence_prefix}:SOURCE:{claim_index}:"
                                    f"{source.memory_uid}:LINE:{line_index}"
                                ),
                                None,
                            )
                            for line_index, _line in enumerate(
                                _source_memory_lines(
                                    source.content,
                                    pane_content_width(),
                                )
                            )
                        )
                entries.append(
                    (
                        "EVIDENCE_REASON",
                        f"{evidence_prefix}:REASON",
                        None,
                    )
                )
            if item.question or item.options:
                entries.append(("OPTIONS", f"ITEM:{item.uid}:DECISION", None))
            append_block_sections(item.blocks)
            entries.append(("RESPONSE", f"ITEM:{item.uid}:RESPONSE", None))
            if inline_item_action() is not None:
                entries.append(
                    (
                        "INCORPORATE",
                        f"ITEM:{item.uid}:INCORPORATE_RESPONSES",
                        None,
                    )
                )
            return _stable_sections(tuple(entries))
        entries.append(("SUMMARY", f"ITEM:{item.uid}:SUMMARY", None))
        append_block_sections(item.blocks[: item.decision_block_index])
        if item.question:
            entries.append(("QUESTION", f"ITEM:{item.uid}:QUESTION", None))
        if item.options:
            entries.append(("OPTIONS", f"ITEM:{item.uid}:OPTIONS", None))
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
            entries.append(("ACTION", "REVIEW:ACTION", None))
            return _stable_sections(tuple(entries))
        return item_sections()

    def viewer_section_index() -> int:
        return session_navigation.section_index(active_viewer_sections())

    def reset_viewer_section() -> None:
        sections = active_viewer_sections()
        session_navigation.section_uid = sections[0].uid if sections else None

    def pane_content_width() -> int:
        """Track the live inner frame width, including terminal resizes."""
        try:
            columns = get_app().output.get_size().columns
        except (AttributeError, RuntimeError):
            return 76
        # Frame borders consume two cells and the scroll margin consumes one.
        return max(20, columns - 3)

    def split_kind() -> str:
        if session_navigation.pane == "todo":
            return "TODO"
        if session_navigation.row_index == 0:
            return "REPORT"
        if session_navigation.row_index <= len(current_view().items):
            return "ITEM"
        return "RESOLVE_ALL"

    def review_action() -> SessionTodoView:
        return session_review_action_view(
            current_view(),
            local_drafts,
            whole_set_available=bool(global_strategies),
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
                ),
                focused=session_navigation.pane == "viewer",
            )
        if viewer_content["kind"] == "REPORT":
            if split_report_text is not None:
                return _viewer_focus_fragments(
                    resolution_seeded_report_fragments(
                        active_view,
                        split_report_text,
                        strategies=global_strategies,
                        drafts=local_drafts,
                        report_item_badges=split_report_item_badges,
                        report_conflicts_remaining=split_report_conflicts_remaining,
                        selected_strategy_index=strategy["index"],
                        focused_section=viewer_section_index(),
                        review_and_apply=review_and_apply,
                        read_only=read_only,
                        impact_controller=impact_controller,
                        destination=destination,
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
                    destination=destination,
                    content_width=pane_content_width(),
                ),
                focused=session_navigation.pane == "viewer",
            )
        return _viewer_focus_fragments(
            resolution_viewer_fragments(
                active_view,
                current_navigation,
                focused_section=viewer_section_index(),
                option_navigation_active=option_navigation["active"],
                other_direction_focused=other_direction["focused"],
                other_direction_editing=other_direction_editor["open"],
                inline_action=inline_item_action(),
                expanded_memory_section_uid=expanded_memory_section_uid["uid"],
                content_width=pane_content_width(),
            ),
            focused=session_navigation.pane == "viewer",
        )

    bindings = KeyBindings()
    status = {"value": ""}
    global_comment = {"value": False}
    strategy = {"index": 0}
    viewer_content = {"kind": "REPORT"}
    impact_reason_expanded: dict[str, str | None] = {"uid": None}
    navigation_accelerator = NavigationAccelerator()
    option_navigation = {"active": False}
    other_direction = {"focused": False}
    other_direction_editor = {"open": False}
    expanded_memory_section_uid: dict[str, str | None] = {"uid": None}
    destination_editing = {"value": False}
    visible_pane_cycle_started = {"value": False}
    input_heading = {"value": "COMMENT ON SELECTED ITEM"}
    local_drafts: dict[str, tuple[str | None, str]] = {}
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
        local_drafts[item.uid] = (option_uid, comment)

    composer = build_framed_multiline_input(
        "MESSAGE",
        prompt="› ",
        buffer_name="resolution-message",
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

    def item_fragments():
        active_view = current_view()
        return _session_items_fragments(
            active_view,
            selected_index=session_navigation.row_index,
            focused=session_navigation.pane == "items",
            content_width=pane_content_width(),
            report_label=(
                "Complete Compare report"
                if split_report_text is not None
                else f"Complete {active_view.operation.title()} report"
            ),
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
        todo = session_todo_view(
            current_view(),
            local_drafts,
            review_and_apply=review_and_apply,
            read_only=read_only,
            whole_set_available=bool(global_strategies),
            read_only_handoff=read_only_handoff,
        )
        focused = session_navigation.pane == "todo"
        return [
            ("[SetCursorPosition]", "") if focused else ("", ""),
            (
                focused_control_style(focused=focused),
                f"[ {safe_terminal_text(todo.kind)} ]",
            ),
            (
                "",
                "  "
                + _line(
                    f"{safe_terminal_text(todo.label)} · "
                    f"{safe_terminal_text(todo.detail)}",
                    max(10, pane_content_width() - len(todo.kind) - 8),
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

    def load_draft() -> None:
        item = current_navigation.current_item(current_view())
        if item is None:
            current_navigation.selected_option_uid = None
            input_area.text = ""
            return
        if draft_loader is None:
            selected_option_uid, comment = _item_draft(item, local_drafts)
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

    def save_draft() -> None:
        item = current_navigation.current_item(current_view())
        if item is None:
            return
        draft = (
            current_navigation.selected_option_uid,
            input_area.text,
        )
        local_drafts[item.uid] = draft
        if draft_saver is not None:
            draft_saver(item.uid, *draft)

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
            if obligation == "NONE":
                continue
            option_uid, comment = _item_draft(item, local_drafts)
            if option_uid is not None:
                option = item.option(option_uid)
                response = f"Choose this reading: {option.text}"
                if comment.strip():
                    response += f" Additional guidance: {comment.strip()}"
                lines.append(f"- {item.title}: {response}")
            elif comment.strip():
                lines.append(f"- {item.title}: Other direction: {comment.strip()}")
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
            if destination.validate is not None:
                destination.validate(value)
            return ResolutionWorkbenchAction(
                kind="CHANGE_DESTINATION",
                destination=value,
            )
        except (OSError, TypeError, ValueError) as error:
            set_status(str(error))
            return None

    def preview_items_row(active_view: ResolutionWorkbenchView) -> None:
        """Keep Viewer aligned with Items while Items retains keyboard focus."""

        session_navigation.preview_selected_row()
        option_navigation["active"] = False
        other_direction["focused"] = False
        other_direction_editor["open"] = False
        expanded_memory_section_uid["uid"] = None
        if session_navigation.row_index == 0:
            viewer_content["kind"] = "REPORT"
            current_navigation.close_detail()
            reset_viewer_section()
            return
        item = active_view.items[session_navigation.row_index - 1]
        viewer_content["kind"] = "ITEM"
        current_navigation.selected_item_uid = item.uid
        current_navigation.sync(active_view)
        current_navigation.close_detail()
        current_navigation.toggle_detail(active_view)
        reset_viewer_section()
        load_draft()

    def move(delta: int) -> None:
        active_view = current_view()
        if split_viewer_items:
            if session_navigation.pane == "viewer":
                if option_navigation["active"]:
                    move_split_option(delta)
                    set_status("")
                    return
                section = session_navigation.move_section(
                    active_viewer_sections(),
                    delta,
                )
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
            total_rows = len(active_view.items) + 1
            session_navigation.move_row(total_rows, delta)
            preview_items_row(active_view)
            set_status("")
            return
        item = current_navigation.current_item(active_view)
        if (
            item is not None
            and current_navigation.expanded_item_uid == item.uid
            and item.options
        ):
            if item.issue_presentation is not None:
                move_split_option(delta)
            else:
                current_navigation.move_option(active_view, delta)
        else:
            save_draft()
            current_navigation.move_item(active_view, delta)
            load_draft()
        global_comment["value"] = False
        composer.frame.title = "MESSAGE"
        set_status("")

    def viewer_navigation_accelerates() -> bool:
        """Use the shared held-arrow movement throughout the active Viewer."""
        if not (split_viewer_items and session_navigation.pane == "viewer"):
            navigation_accelerator.reset()
            return False
        return True

    def move_split_option(delta: int) -> None:
        item = current_navigation.current_item(current_view())
        if item is None or not item.options:
            return
        option_uids = tuple(option.uid for option in item.options)
        if other_direction["focused"]:
            index = len(option_uids)
        elif current_navigation.option_cursor_uid in option_uids:
            index = option_uids.index(current_navigation.option_cursor_uid)
        else:
            index = 0
        next_index = min(max(index + delta, 0), len(option_uids))
        other_direction["focused"] = next_index == len(option_uids)
        if not other_direction["focused"]:
            current_navigation.option_cursor_uid = option_uids[next_index]

    def open_item_input(*, title: str, clear: bool = False) -> None:
        destination_editing["value"] = False
        global_comment["value"] = False
        composer.frame.title = title
        input_heading["value"] = title
        if clear:
            input_area.text = ""
        session_navigation.focus("composer")
        get_app().layout.focus(input_area)

    def open_destination_input() -> None:
        if destination is None:
            set_status("Save-location editing is unavailable here.")
            return
        destination_editing["value"] = True
        global_comment["value"] = False
        other_direction_editor["open"] = False
        title = f"{destination.label} · EDIT DIRECTLY"
        composer.frame.title = title
        input_heading["value"] = title
        input_area.text = destination.value
        input_area.buffer.cursor_position = len(destination.value)
        session_navigation.focus("composer")
        get_app().layout.focus(input_area)

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

    def open_review_and_apply() -> None:
        """Open the non-mutating final review before any apply action."""

        save_draft()
        active_view = current_view()
        todo = session_todo_view(
            active_view,
            local_drafts,
            review_and_apply=review_and_apply,
            read_only=read_only,
            whole_set_available=bool(global_strategies),
            read_only_handoff=read_only_handoff,
        )
        if todo.kind != "REVIEW AND APPLY":
            if todo.unresolved_item_uids:
                open_split_item(todo.unresolved_item_uids[0])
            else:
                set_status(todo.detail)
            return
        session_navigation.row_index = len(active_view.items) + 1
        session_navigation.viewer_row_index = session_navigation.row_index
        viewer_content["kind"] = "REVIEW"
        reset_viewer_section()
        session_navigation.focus("viewer")
        get_app().layout.focus(body_control)
        set_status("")

    def submit(event) -> None:
        active_view = current_view()
        comment = input_area.text.strip()
        if destination_editing["value"]:
            action = destination_action(comment)
            if action is not None:
                event.app.exit(result=action)
            else:
                event.app.invalidate()
            return
        if (review_and_apply or draft_saver is not None) and not global_comment[
            "value"
        ]:
            item = current_navigation.current_item(active_view)
            save_draft()
            other_direction_editor["open"] = False
            session_navigation.focus("viewer")
            event.app.layout.focus(body_control)
            if item is not None:
                option_uid, saved_comment = local_drafts.get(item.uid, (None, ""))
                if option_uid is not None:
                    label = item.option(option_uid).label
                    set_status(f"Selected · {label}")
                elif saved_comment.strip():
                    set_status("Saved · Other direction")
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

    @bindings.add("down", filter=~has_focus(input_area))
    def _down(event) -> None:
        if viewer_navigation_accelerates():
            navigation_accelerator.move(1, app=event.app, move_one=move)
        else:
            move(1)
            event.app.invalidate()

    @bindings.add("up", filter=~has_focus(input_area))
    def _up(event) -> None:
        if viewer_navigation_accelerates():
            navigation_accelerator.move(-1, app=event.app, move_one=move)
        else:
            move(-1)
            event.app.invalidate()

    @bindings.add("pagedown", filter=~has_focus(input_area))
    def _page_down(event) -> None:
        # Once results are independent sections, a page step advances several
        # short result blocks instead of trying to display one 234-result
        # monolith. Down still advances one block at a time.
        navigation_accelerator.reset()
        move(8)
        event.app.invalidate()

    @bindings.add("pageup", filter=~has_focus(input_area))
    def _page_up(event) -> None:
        navigation_accelerator.reset()
        move(-8)
        event.app.invalidate()

    @bindings.add("end", filter=~has_focus(input_area))
    def _end(event) -> None:
        navigation_accelerator.reset()
        move(1_000_000)
        event.app.invalidate()

    @bindings.add("home", filter=~has_focus(input_area))
    def _home(event) -> None:
        navigation_accelerator.reset()
        move(-1_000_000)
        event.app.invalidate()

    @bindings.add("right", filter=~has_focus(input_area))
    def _right(event) -> None:
        if split_viewer_items:
            if split_kind() == "RESOLVE_ALL" and global_strategies:
                strategy["index"] = min(
                    strategy["index"] + 1,
                    len(global_strategies) - 1,
                )
            elif (
                split_kind() == "ITEM"
                and session_navigation.pane == "viewer"
                and session_navigation.viewer_row_index == session_navigation.row_index
                and option_navigation["active"]
            ):
                move_split_option(1)
            event.app.invalidate()
            return
        save_draft()
        current_navigation.move_item(current_view(), 1)
        load_draft()
        event.app.invalidate()

    @bindings.add("left", filter=~has_focus(input_area))
    def _left(event) -> None:
        if split_viewer_items:
            if split_kind() == "RESOLVE_ALL" and global_strategies:
                strategy["index"] = max(strategy["index"] - 1, 0)
            elif (
                split_kind() == "ITEM"
                and session_navigation.pane == "viewer"
                and session_navigation.viewer_row_index == session_navigation.row_index
                and option_navigation["active"]
            ):
                move_split_option(-1)
            event.app.invalidate()
            return
        save_draft()
        current_navigation.move_item(current_view(), -1)
        load_draft()
        event.app.invalidate()

    @bindings.add("enter", filter=~has_focus(input_area))
    def _open_or_choose(event) -> None:
        active_view = current_view()
        if split_viewer_items:
            kind = split_kind()
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
                    if section.kind == "DESTINATION":
                        open_destination_input()
                        event.app.invalidate()
                        return
                    if section.kind == "REVIEW_AND_APPLY" or (
                        review_and_apply and section.kind == "RESOLVE_ALL"
                    ):
                        open_review_and_apply()
                        event.app.invalidate()
                        return
                other_direction_editor["open"] = False
                viewer_content["kind"] = "REPORT"
                reset_viewer_section()
                session_navigation.open_selected(report_sections())
                event.app.layout.focus(body_control)
                set_status("")
            elif kind == "ITEM":
                if (
                    session_navigation.pane != "viewer"
                    or viewer_content["kind"] != "ITEM"
                    or session_navigation.viewer_row_index
                    != session_navigation.row_index
                ):
                    item = active_view.items[session_navigation.row_index - 1]
                    open_split_item(item.uid)
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
                    if section.kind == "INCORPORATE":
                        save_draft()
                        action = incorporate_responses_action(active_view)
                        if action is not None:
                            event.app.exit(result=action)
                            return
                    elif (
                        not option_navigation["active"]
                        and section.kind == "OPTIONS"
                        and item is not None
                        and item.options
                    ):
                        option_navigation["active"] = True
                        other_direction["focused"] = False
                        if current_navigation.option_cursor_uid is None:
                            current_navigation.option_cursor_uid = item.options[0].uid
                        set_status("Choose an option with ↑/↓, then press Enter.")
                    elif option_navigation["active"] and other_direction["focused"]:
                        current_navigation.selected_option_uid = None
                        option_navigation["active"] = False
                        other_direction_editor["open"] = True
                        open_item_input(
                            title=current_response_heading(),
                            clear=True,
                        )
                    elif option_navigation["active"]:
                        current_navigation.toggle_option(active_view)
                        save_draft()
                        selected_uid = current_navigation.selected_option_uid
                        if selected_uid is None:
                            set_status("Selection cleared.")
                        else:
                            selected_option = item.option(selected_uid)
                            set_status(f"Selected · ✓ {selected_option.label}")
                    elif section.kind == "RESPONSE":
                        other_direction_editor["open"] = True
                        open_item_input(
                            title=current_response_heading(),
                        )
                    else:
                        set_status(
                            "Move to the Decision or Response section and press Enter."
                        )
            elif kind == "RESOLVE_ALL" and viewer_content["kind"] == "REVIEW":
                section = active_viewer_sections()[viewer_section_index()]
                if section.kind != "ACTION":
                    set_status("Move to the final action and press Enter.")
                else:
                    final_action = review_action()
                    if final_action.kind in {"APPLY", "APPLY AS IS"}:
                        action = semantic_action("ACCEPT")
                    elif final_action.kind == "INCORPORATE AND APPLY":
                        action = incorporate_responses_action(
                            active_view,
                            action_kind="INCORPORATE_AND_APPLY",
                        )
                    elif final_action.kind == "INCORPORATE RESPONSES":
                        action = incorporate_responses_action(active_view)
                    else:
                        action = None
                        set_status("No final action is available.")
                    if action is not None:
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
                ).unresolved_item_uids
            ):
                todo = session_todo_view(
                    active_view,
                    local_drafts,
                    review_and_apply=review_and_apply,
                    read_only=read_only,
                    whole_set_available=bool(global_strategies),
                    read_only_handoff=read_only_handoff,
                )
                open_split_item(todo.unresolved_item_uids[0])
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
                ).kind
                == "COMPLETE"
            ):
                set_status(
                    "Required review is complete; close or revisit an optional review."
                )
            elif kind == "TODO" and review_and_apply:
                open_review_and_apply()
            elif kind == "TODO" and not global_strategies:
                set_status("No whole-set strategies are available.")
            elif kind == "TODO" and (
                viewer_content["kind"] != "REPORT"
                or session_navigation.section_uid
                != next(
                    section.uid
                    for section in report_sections()
                    if section.kind == "RESOLVE_ALL"
                )
            ):
                viewer_content["kind"] = "REPORT"
                session_navigation.focus_section(
                    report_sections(),
                    kind="RESOLVE_ALL",
                    last=True,
                )
                set_status("")
            elif kind == "TODO":
                selected_strategy = global_strategies[strategy["index"]]
                if selected_strategy.action_kind == "CUSTOM":
                    global_comment["value"] = True
                    input_heading["value"] = "WHOLE-SET GUIDANCE"
                    input_area.text = ""
                    session_navigation.focus("composer")
                    event.app.layout.focus(input_area)
                else:
                    action = semantic_action(
                        selected_strategy.action_kind,
                        comment=selected_strategy.comment,
                    )
                    if action is not None:
                        event.app.exit(result=action)
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
                save_draft()
                set_status("")
        else:
            current_navigation.toggle_detail(active_view)
            set_status("")
        event.app.invalidate()

    @bindings.add("tab")
    @bindings.add("s-tab")
    def _focus_input(event) -> None:
        if event.app.layout.has_focus(input_area):
            save_draft()
            other_direction_editor["open"] = False
            if split_viewer_items:
                session_navigation.focus("viewer")
                event.app.layout.focus(body_control)
            else:
                event.app.layout.focus(body_control)
            event.app.invalidate()
            return
        if split_viewer_items:
            option_navigation["active"] = False
            delta = -1 if event.key_sequence[0].key == Keys.BackTab else 1
            if not visible_pane_cycle_started["value"]:
                # Items is the initial hub: forward opens Viewer, backward
                # reaches To Do. If Enter already opened Viewer, either Tab
                # direction returns to the adjacent Items frame first.
                initial_targets = {
                    ("items", 1): "viewer",
                    ("items", -1): "todo",
                    ("viewer", 1): "items",
                    ("viewer", -1): "items",
                    ("todo", 1): "viewer",
                    ("todo", -1): "items",
                }
                pane = initial_targets[(session_navigation.pane, delta)]
                session_navigation.focus(pane)
                visible_pane_cycle_started["value"] = True
            else:
                pane = session_navigation.cycle_panes(
                    # After the initial hub transition, follow the visible
                    # top-to-bottom frame order in either direction.
                    ("viewer", "items", "todo"),
                    delta,
                )
            if pane == "items" and viewer_content["kind"] == "REVIEW":
                # The final review is not an Items row. Leaving it for Items
                # returns to the report instead of leaving an impossible
                # sentinel row selected in the visible list.
                session_navigation.row_index = 0
                session_navigation.viewer_row_index = 0
                viewer_content["kind"] = "REPORT"
                reset_viewer_section()
            controls = {
                "viewer": body_control,
                "items": items_control,
                "todo": todo_control,
            }
            event.app.layout.focus(controls[pane])
            event.app.invalidate()
            return
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
        if split_viewer_items:
            session_navigation.focus("composer")
        event.app.layout.focus(input_area)

    @bindings.add("c", filter=~has_focus(input_area))
    def _comment_item(event) -> None:
        if not split_viewer_items:
            return
        active_view = current_view()
        if split_kind() == "RESOLVE_ALL":
            if active_view.input_locked or "SUBMIT_ALL" not in active_view.capabilities:
                set_status("Whole-set guidance is unavailable here.")
                event.app.invalidate()
                return
            global_comment["value"] = True
            other_direction_editor["open"] = False
            input_heading["value"] = "WHOLE-SET GUIDANCE"
            input_area.text = ""
            session_navigation.focus("composer")
            event.app.layout.focus(input_area)
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
        global_comment["value"] = False
        other_direction_editor["open"] = True
        composer.frame.title = "MESSAGE"
        input_heading["value"] = current_response_heading()
        session_navigation.focus("composer")
        event.app.layout.focus(input_area)

    @bindings.add("g", filter=~has_focus(input_area))
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
        global_comment["value"] = True
        other_direction_editor["open"] = False
        composer.frame.title = "WHOLE-SET COMMENT"
        input_heading["value"] = "WHOLE-SET GUIDANCE"
        input_area.text = ""
        if split_viewer_items:
            session_navigation.focus("composer")
        event.app.layout.focus(input_area)

    @bindings.add("enter", filter=has_focus(input_area), eager=True)
    @bindings.add("c-s", filter=has_focus(input_area), eager=True)
    @bindings.add("f2", filter=has_focus(input_area), eager=True)
    def _submit_input(event) -> None:
        submit(event)

    @bindings.add("c-j", filter=has_focus(input_area), eager=True)
    def _insert_newline(event) -> None:
        if destination_editing["value"]:
            set_status("A Context name must stay on one line.")
            event.app.invalidate()
            return
        input_area.buffer.insert_text("\n")
        event.app.invalidate()

    def exit_simple(event, kind: str) -> None:
        action = semantic_action(kind)
        if action is not None:
            event.app.exit(result=action)
        else:
            event.app.invalidate()

    @bindings.add("p", filter=~has_focus(input_area))
    def _preserve(event) -> None:
        exit_simple(event, "PRESERVE_ALL")

    @bindings.add("d", filter=~has_focus(input_area))
    def _defer(event) -> None:
        exit_simple(event, "DEFER")

    @bindings.add("a", filter=~has_focus(input_area))
    def _accept(event) -> None:
        if split_viewer_items and review_and_apply:
            open_review_and_apply()
            event.app.invalidate()
            return
        exit_simple(event, "ACCEPT")

    @bindings.add("s", filter=~has_focus(input_area))
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
        if option_navigation["active"]:
            option_navigation["active"] = False
            other_direction["focused"] = False
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
        if save_draft_on_close and not event.app.layout.has_focus(input_area):
            save_draft()
        event.app.exit(result=ResolutionWorkbenchAction(kind="CLOSE"))

    @bindings.add("escape", eager=True)
    @bindings.add("backspace", filter=~has_focus(input_area), eager=True)
    def _back_or_close(event) -> None:
        if event.app.layout.has_focus(input_area) and destination_editing["value"]:
            destination_editing["value"] = False
            session_navigation.focus("viewer")
            event.app.layout.focus(body_control)
            set_status("")
            event.app.invalidate()
            return
        if option_navigation["active"]:
            option_navigation["active"] = False
            other_direction["focused"] = False
            set_status("")
            event.app.invalidate()
            return
        if expanded_memory_section_uid["uid"] is not None:
            expanded_memory_section_uid["uid"] = None
            set_status("")
            event.app.invalidate()
            return
        if (
            split_viewer_items
            and not event.app.layout.has_focus(input_area)
            and session_navigation.row_index != 0
        ):
            session_navigation.row_index = 0
            viewer_content["kind"] = "REPORT"
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

    @bindings.add("q", filter=~has_focus(input_area), eager=True)
    @bindings.add("c-c", eager=True)
    def _quit(event) -> None:
        _close(event)

    def footer_text() -> str:
        if status["value"]:
            return f" {status['value']}"
        active_view = current_view()
        item = current_navigation.current_item(active_view)
        if split_viewer_items and split_kind() == "REPORT":
            navigation_help = (
                " ↑/↓ block (hold accelerates)  PgUp/PgDn page  End last  Tab switch  "
                "Enter inspect  Esc/Backspace close "
                if read_only
                else " ↑/↓ block (hold accelerates)  PgUp/PgDn page  End last  Tab switch  "
                "Enter open  Esc/Backspace/Q close "
            )
        elif split_viewer_items and split_kind() == "TODO":
            todo = session_todo_view(
                active_view,
                local_drafts,
                review_and_apply=review_and_apply,
                read_only=read_only,
                whole_set_available=bool(global_strategies),
                read_only_handoff=read_only_handoff,
            )
            navigation_help = (
                " Tab switch  Q close "
                if todo.kind == "COMPLETE"
                else f" Enter {todo.kind.lower()}  Tab switch  Esc/Backspace back "
            )
        elif split_viewer_items and split_kind() == "RESOLVE_ALL":
            if review_and_apply and viewer_content["kind"] == "REVIEW":
                final_action = review_action()
                navigation_help = (
                    " ↑/↓ review  Tab switch  "
                    f"Enter {final_action.kind.lower()}  "
                    "Esc/Backspace return "
                )
            else:
                navigation_help = (
                    " ↑/↓ section/item  Tab switch  ←/→ strategy  "
                    "Enter open/run  C custom  Esc/Backspace report "
                )
        elif split_viewer_items and option_navigation["active"]:
            navigation_help = (
                " ↑/↓ option  Enter select  Esc/Backspace back  Tab switch "
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
        elif (
            split_viewer_items
            and viewer_content["kind"] == "ITEM"
            and session_navigation.pane == "viewer"
            and active_viewer_sections()[viewer_section_index()].kind == "INCORPORATE"
        ):
            navigation_help = (
                " Enter incorporate responses  ↑/↓ section  "
                "Esc/Backspace report  Tab switch "
            )
        elif (
            split_viewer_items
            and viewer_content["kind"] == "ITEM"
            and session_navigation.pane == "viewer"
            and active_viewer_sections()[viewer_section_index()].kind == "RESPONSE"
        ):
            navigation_help = (
                " Enter write response  ↑/↓ section  Esc/Backspace report  Tab switch "
            )
        elif (
            split_viewer_items
            and viewer_content["kind"] == "ITEM"
            and session_navigation.pane == "viewer"
            and active_viewer_sections()[viewer_section_index()].kind == "OPTIONS"
        ):
            navigation_help = (
                " Enter choose options  ↑/↓ section  Esc/Backspace report  Tab switch "
            )
        elif split_viewer_items:
            navigation_help = (
                " ↑/↓ section/item  Tab switch  ←/→ option  "
                "Enter choose/other  C send/comment  Esc/Backspace report "
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
    inline_input = ConditionalContainer(
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
        viewer_frame = Frame(HSplit([body, inline_input]), title="VIEWER")
        items_frame = Frame(items_window, title="ITEMS")
        todo_frame = Frame(todo_window, title="TO DO")
        root = HSplit(
            [
                viewer_frame,
                items_frame,
                todo_frame,
                footer,
            ]
        )
        bind_focused_frame_style(
            viewer_frame,
            is_focused=lambda: session_navigation.pane == "viewer",
        )
        bind_focused_frame_style(
            items_frame,
            is_focused=lambda: session_navigation.pane == "items",
        )
        bind_focused_frame_style(
            todo_frame,
            is_focused=lambda: session_navigation.pane == "todo",
        )
        focused_element = items_control
    else:
        viewer_frame = Frame(HSplit([body, inline_input]), title="VIEWER")
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
    try:
        return application.run()
    except (EOFError, KeyboardInterrupt):
        return ResolutionWorkbenchAction(kind="CLOSE")
