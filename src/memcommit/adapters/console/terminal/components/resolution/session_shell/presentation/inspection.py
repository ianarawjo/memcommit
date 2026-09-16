"""Item navigation and detail inspection for Resolution Sessions."""

from __future__ import annotations

from memcommit.adapters.console.terminal.components.content_row import (
    render_numbered_content_row,
)
from memcommit.adapters.console.terminal.components.selection import (
    render_vertical_choice_cards,
)
from memcommit.adapters.console.terminal.components.selection.model import (
    SelectionOption,
)
from memcommit.adapters.console.terminal.components.selection.state import (
    FlatSelectionState,
)
from memcommit.adapters.console.terminal.components.semantic_viewer import (
    deactivate_semantic_viewer_fragments,
    semantic_viewer_block_fragments,
)
from memcommit.adapters.console.terminal.components.semantic_viewer.detail import (
    semantic_detail_block_fragments,
    semantic_detail_header_fragments,
    semantic_memory_row_fragments,
    semantic_trace_fragments,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionMemoryRow,
    ResolutionNavigation,
    ResolutionWorkbenchView,
)
from memcommit.application.capabilities.reviewing.session_navigation import (
    WorkbenchSection,
)

from memcommit.adapters.console.terminal.components.resolution.session_shell.presentation.formatting import (
    _indented,
    _item_kind_label,
    _line,
    _source_memory_lines,
    _visual_width,
    _visual_wrap,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.presentation.progression import (
    SessionTodoView,
)


def _stacked_horizontal_key_message(kind: str) -> str:
    """Explain the vertical path for a split frame without horizontal meaning."""

    if kind == "RESPONSES":
        return "Responses are stacked · use Up/Down for choices and Response."
    if kind == "ITEM":
        return "This detail is vertical · use Up/Down, or Tab to reach Responses."
    if kind == "REPORT":
        return "This report is vertical · use Up/Down between blocks."
    return "This frame has no Left/Right action · use Up/Down or Tab."


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


def _evidence_section_count(evidence, content_width: int) -> int:
    """Count Classification, criterion, whole-Memory, and Why stops."""

    _ = content_width
    source_memory_count = sum(
        1 for claim in evidence.source_groups for source in claim.sources
    )
    return 2 + len(evidence.criterion_blocks) + source_memory_count


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
