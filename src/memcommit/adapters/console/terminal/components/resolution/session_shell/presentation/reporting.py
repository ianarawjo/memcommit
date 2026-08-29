"""Whole-report, seeded-report, and Impact presentation for Resolution Sessions."""

from __future__ import annotations

from prompt_toolkit.utils import get_cwidth

from memcommit.adapters.console.terminal.components.content_row import (
    render_numbered_content_row,
)
from memcommit.adapters.console.terminal.components.impact import (
    ImpactController,
    ImpactView,
)
from memcommit.adapters.console.terminal.components.report_card import boxed_lines
from memcommit.adapters.console.terminal.components.responses.model import ResponseDraft
from memcommit.adapters.console.terminal.components.semantic_viewer import (
    semantic_viewer_block_fragments,
)
from memcommit.adapters.console.terminal.components.tree_row import (
    navigable_tree_row_prefix,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionItem,
    ResolutionWorkbenchView,
)
from memcommit.application.capabilities.reviewing.memory_diff import (
    MemoryChange,
    MemoryDiffSpan,
    memory_diff_lines,
)

from memcommit.adapters.console.terminal.components.resolution.session_shell.presentation.formatting import (
    _item_kind_label,
    _line,
    _visual_pad,
    _visual_width,
    _visual_wrap,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.presentation.progression import (
    ResolutionGlobalStrategy,
    _item_draft,
    _report_action,
    session_review_action_view,
)


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
    if (
        report_fragments is not None
        and "".join(text for _style, text in report_fragments) != report_text
    ):
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
        styled = [(style, safe_terminal_text(text)) for style, text in report_fragments]
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
