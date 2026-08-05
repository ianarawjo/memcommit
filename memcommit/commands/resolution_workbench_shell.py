"""Shared list/detail/comment shell for semantic resolution adapters."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
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
from prompt_toolkit.styles import Style, merge_styles
from prompt_toolkit.widgets import Frame
from prompt_toolkit.utils import get_cwidth

from memcommit.commands.tui_primitives import (
    MEMCOMMIT_TUI_STYLE,
    TuiRegion,
    bind_focused_frame_style,
    build_framed_multiline_input,
    build_tui_frame,
    navigable_tree_row_prefix,
    require_interactive_terminal,
    safe_terminal_text,
)
from memcommit.resolution_workbench import (
    ResolutionNavigation,
    ResolutionWorkbenchAction,
    ResolutionWorkbenchError,
    ResolutionWorkbenchView,
)


@dataclass(frozen=True)
class ResolutionGlobalStrategy:
    """One operation-authored whole-set shortcut; never an apply action."""

    label: str
    action_kind: str
    comment: str = ""


@dataclass
class _NavigationAccelerator:
    """Increase held-arrow travel while keeping deliberate taps precise."""

    direction: int = 0
    streak: int = 0
    last_at: float | None = None

    def reset(self) -> None:
        self.direction = 0
        self.streak = 0
        self.last_at = None

    def step(self, direction: int, *, now: float | None = None) -> int:
        if direction not in {-1, 1}:
            raise ValueError("Navigation direction must be -1 or 1.")
        observed_at = monotonic() if now is None else now
        if (
            self.last_at is None
            or direction != self.direction
            or observed_at - self.last_at > 0.4
        ):
            self.streak = 1
        else:
            self.streak += 1
        self.direction = direction
        self.last_at = observed_at
        if self.streak >= 13:
            return 10
        if self.streak >= 8:
            return 5
        if self.streak >= 4:
            return 2
        return 1


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
        "class:option-card.focused": "class:option-card",
        "class:option-card.other": "class:option-card",
        "class:choice": "",
    }
    return [(inactive_style.get(style, style), text) for style, text in fragments]


def resolution_workbench_fragments(
    view: ResolutionWorkbenchView,
    navigation: ResolutionNavigation,
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
                    f"{safe_terminal_text(item.kind)} · "
                    f"{safe_terminal_text(item.status)} · "
                    f"{_line(item.summary)}\n"
                ),
            )
        )
        if not expanded:
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
    other_direction_focused: bool = False,
    other_direction_editing: bool = False,
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

    if other_direction_editing:
        fragments.append(("[SetCursorPosition]", ""))
        for line in _boxed_lines(
            "◇ OTHER DIRECTION",
            "Write the alternative resolution directly below.",
        ):
            fragments.append(("class:option-card.other", f" {line}\n"))
        return fragments

    section_count = 1 + bool(item.question) + bool(item.options) + len(item.blocks)
    focused_section = max(0, min(focused_section, section_count - 1))
    section_index = 0

    def card(title: str, body: str, *, indent_body: bool = False) -> None:
        nonlocal section_index
        active = section_index == focused_section
        if active:
            fragments.append(("[SetCursorPosition]", ""))
        if indent_body:
            body = "\n".join(f"  {line}" if line else "" for line in body.splitlines())
        style = "class:detail-card.focused" if active else "class:detail-card"
        for line in _boxed_lines(title, body):
            fragments.append((style, f" {line}\n"))
        fragments.append(("", "\n"))
        section_index += 1

    def options_card() -> None:
        nonlocal section_index
        active = section_index == focused_section
        if active:
            fragments.append(("[SetCursorPosition]", ""))
        outer_style = "class:detail-card.focused" if active else "class:detail-card"
        outer_width = 72
        inner_width = outer_width - 6
        outer_body_width = outer_width - 4
        top, bottom = _boxed_lines("OPTIONS", "", width=outer_width)[::2]
        fragments.append((outer_style, f" {top}\n"))

        choices = [
            (
                index,
                option.label,
                option.text,
                (
                    not other_direction_focused
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
                "Other direction",
                "Press Enter and write a different resolution here.",
                other_direction_focused,
                False,
                True,
            )
        )
        for choice_index, label, text, cursor, chosen, is_other in choices:
            marker = "●" if chosen else ("◇" if is_other else "○")
            choice_lines = _boxed_lines(
                f"{'› ' if cursor else ''}{marker} {choice_index}. {label}",
                text,
                width=inner_width,
            )
            if cursor and is_other:
                choice_style = "class:option-card.other"
            elif cursor:
                choice_style = "class:option-card.focused"
            elif chosen:
                choice_style = "class:option-card.selected"
            else:
                choice_style = "class:option-card"
            if cursor:
                # Keep the active nested choice visible when the inline Other
                # direction editor reduces the Viewer height.
                fragments.append(("[SetCursorPosition]", ""))
            for choice_line in choice_lines:
                fragments.extend(
                    [
                        (outer_style, " │ "),
                        (choice_style, choice_line),
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
    card(
        f"CONFLICT {item_index}/{len(view.items)} · {item.title}",
        f"[{item.priority}] {item.kind} · {item.status}\n{item.summary}",
    )
    if item.question:
        card("QUESTION", item.question)
    if item.options:
        options_card()
    for block in item.blocks:
        card(block.heading, block.text, indent_body=True)
    return fragments


def resolution_report_fragments(
    view: ResolutionWorkbenchView,
    *,
    strategies: tuple[ResolutionGlobalStrategy, ...] = (),
    focused_section: int = 0,
    review_and_apply: bool = False,
    read_only: bool = False,
) -> list[tuple[str, str]]:
    """Render the complete Meld reading surface before any individual issue."""
    metric_text = " · ".join(
        f"{safe_terminal_text(metric.value)} {safe_terminal_text(metric.label)}"
        for metric in view.metrics
    )
    section_count = len(view.items) + (3 if read_only else 4)
    focused_section = max(0, min(focused_section, section_count - 1))
    section_index = 0
    fragments: list[tuple[str, str]] = []

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
    if not view.items:
        fragments.append(("", f"  {safe_terminal_text(view.empty_message)}\n"))
    for index, item in enumerate(view.items, start=1):
        heading(f"CONFLICT {index} · {item.title}")
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
    if not read_only:
        heading(
            ("REVIEW & APPLY MELD" if view.accept_enabled else "MATERIALIZE REVIEW")
            if review_and_apply
            else "RESOLVE ALL · WHOLE-SET STRATEGY"
        )
        fragments.append(
            (
                "",
                (
                    (
                        " The exact proposed Memories are shown above. Press Enter "
                        "to apply them.\n"
                        if view.accept_enabled
                        else " Review the choices and policy already shown in this "
                        "report, then press Enter to materialize the proposal.\n"
                    )
                    if review_and_apply
                    else " Choose a strategy below. It requests a revised proposal "
                    "and never applies the target.\n"
                ),
            )
        )
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
    if not read_only:
        lines.extend(
            [
                "",
                (
                    (
                        "REVIEW & APPLY MELD"
                        if view.accept_enabled
                        else "MATERIALIZE REVIEW"
                    )
                    if review_and_apply
                    else "RESOLVE ALL · WHOLE-SET STRATEGY"
                ),
                (
                    (
                        "The exact proposed Memories are shown above. Press Enter "
                        "to apply them."
                        if view.accept_enabled
                        else "Review the choices and policy already shown in this "
                        "report, then press Enter to materialize the proposal."
                    )
                    if review_and_apply
                    else "Choose a strategy below. It requests a revised proposal "
                    "and never applies the target."
                ),
            ]
        )
        if not (review_and_apply and view.accept_enabled):
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
        "MATERIALIZE REVIEW",
        "REVIEW & APPLY MELD",
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
            ("RESOLVE ALL ·", "MATERIALIZE REVIEW", "REVIEW & APPLY MELD")
        ):
            in_results = False
        if line.startswith(headings):
            key = (
                "RESOLVE_ALL"
                if line.startswith(
                    (
                        "RESOLVE ALL ·",
                        "MATERIALIZE REVIEW",
                        "REVIEW & APPLY MELD",
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
    strategies: tuple[ResolutionGlobalStrategy, ...] = (),
    drafts: dict[str, tuple[str | None, str]] | None = None,
    report_item_badges: tuple[str, ...] = (),
    report_conflicts_remaining: int | None = None,
    selected_strategy_index: int = 0,
    focused_section: int = 0,
    review_and_apply: bool = False,
    read_only: bool = False,
) -> list[tuple[str, str]]:
    """Render Compare and Meld report sections as nested Viewer cards."""
    lines = _seeded_report_lines(
        view,
        report_text,
        strategies,
        review_and_apply,
        read_only,
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
            width = 76
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
                    option_uid, comment = draft_values.get(
                        item.uid,
                        (item.selected_option_uid, ""),
                    )
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
            style = "class:viewer-section" if active else "class:detail-card"
            prefix = navigable_tree_row_prefix(
                selected=active,
                depth=1,
                branch=result.marker,
            )
            identity = f"{result_index + 1:>3}. [{safe_terminal_text(result.label)}] "
            content_indent = " " * _visual_width(prefix + identity)
            content_width = max(12, 76 - _visual_width(prefix + identity))
            wrapped_content = _visual_wrap(result.text, content_width)
            for line_index, content_line in enumerate(wrapped_content):
                lead = prefix + identity if line_index == 0 else content_indent
                fragments.append((style, f" {lead}{content_line}\n"))
            if result.reason:
                reason_prefix = " " * _visual_width(prefix) + "    WHY · "
                reason_width = max(12, 76 - _visual_width(reason_prefix))
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
                option_uid, comment = draft_values.get(
                    item.uid,
                    (item.selected_option_uid, ""),
                )
                if option_uid is not None:
                    badge = f"SELECTED · {item.option(option_uid).label}"
                elif comment.strip():
                    badge = "OTHER DIRECTION · STAGED"
        elif (
            key == "RESOLVE_ALL"
            and strategies
            and not (review_and_apply and view.accept_enabled)
        ):
            policy_index = max(0, min(selected_strategy_index, len(strategies) - 1))
            badge = f"POLICY · {strategies[policy_index].label}"
        if badge:
            # Keep the blue review state directly below the card title so a
            # long conflict paragraph cannot push the chosen reading offscreen.
            body_lines = [badge, "", *body_lines]

        active = section_index == focused_section
        card_lines = _boxed_lines(title, "\n".join(body_lines))
        anchor_at_end = active
        badge_line_count = len(_visual_wrap(badge, 68)) if badge else 0
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
    focused_section: int = 0,
) -> list[tuple[str, str]]:
    """Render the staged issue responses and unresolved-item policy."""
    focused_section = max(0, min(focused_section, 2))
    fragments: list[tuple[str, str]] = []
    answered = 0
    response_lines: list[str] = []
    unresolved_counts: dict[str, int] = {}
    unresolved_required: list[str] = []
    for index, item in enumerate(view.items, start=1):
        option_uid, comment = drafts.get(
            item.uid,
            (item.selected_option_uid, ""),
        )
        if option_uid is not None:
            option = item.option(option_uid)
            answer = f"SELECTED · {option.label}"
            answered += 1
        elif comment.strip():
            answer = f"OTHER DIRECTION · {comment.strip()}"
            answered += 1
        else:
            answer = "UNRESOLVED"
        if answer == "UNRESOLVED":
            unresolved_counts[item.priority] = (
                unresolved_counts.get(item.priority, 0) + 1
            )
            if item.priority == "REQUIRED":
                unresolved_required.append(item.title)
            continue
        response_lines.extend([f"{index}. {item.title}", f"   {answer}"])

    if not response_lines:
        response_lines.append("No staged issue responses yet.")
    remaining_summary = (
        " · ".join(
            f"{priority} {count}"
            for priority, count in (
                ("REQUIRED", unresolved_counts.get("REQUIRED", 0)),
                ("HELPFUL", unresolved_counts.get("HELPFUL", 0)),
            )
            if count
        )
        or "NONE"
    )
    response_lines.append(f"REMAINING · {remaining_summary}")
    if unresolved_required:
        response_lines.append("REQUIRED NEXT · " + "; ".join(unresolved_required))

    if focused_section == 0:
        fragments.append(("[SetCursorPosition]", ""))
    for line in _boxed_lines(
        f"REVIEW & APPLY MELD · {answered}/{len(view.items)} RESOLVED",
        "\n".join(response_lines).rstrip(),
    ):
        fragments.append(("class:detail-card.focused", f" {line}\n"))
    fragments.append(("", "\n"))

    policy_lines: list[str] = []
    for index, policy in enumerate(strategies):
        selected = index == strategy_index
        marker = "›" if selected else " "
        policy_lines.append(f"{marker} {index + 1}. {policy.label}")
    policy_box = _boxed_lines(
        "REMAINING-ITEM POLICY",
        "\n".join(policy_lines) or "No unresolved-conflict policies are available.",
    )
    for index, line in enumerate(policy_box):
        if focused_section == 1 and index == len(policy_box) - 1:
            fragments.append(("[SetCursorPosition]", ""))
        fragments.append(("class:option-card.focused", f" {line}\n"))
    fragments.append(("", "\n"))

    next_text = (
        "This Meld is ready. Press A to apply the reviewed target changes."
        if view.accept_enabled
        else (
            "Press Enter to resolve the staged choices and remaining-item policy. "
            "Mem will show the resulting target Memories for final application."
        )
    )
    next_box = _boxed_lines("NEXT", next_text)
    for index, line in enumerate(next_box):
        if focused_section == 2 and index == len(next_box) - 1:
            fragments.append(("[SetCursorPosition]", ""))
        fragments.append(("class:detail-card", f" {line}\n"))
    return fragments


def run_resolution_workbench_shell(
    view_or_supplier: (ResolutionWorkbenchView | Callable[[], ResolutionWorkbenchView]),
    *,
    navigation: ResolutionNavigation | None = None,
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

    def split_kind() -> str:
        if split_row["index"] == 0:
            return "REPORT"
        if split_row["index"] <= len(current_view().items):
            return "ITEM"
        return "RESOLVE_ALL"

    def split_view_fragments():
        active_view = current_view()
        if viewer_content["kind"] == "REVIEW":
            return _viewer_focus_fragments(
                resolution_review_fragments(
                    active_view,
                    local_drafts,
                    global_strategies,
                    strategy["index"],
                    viewer_section["index"],
                ),
                focused=pane_focus["value"] == "viewer",
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
                        focused_section=viewer_section["index"],
                        review_and_apply=review_and_apply,
                        read_only=read_only,
                    ),
                    focused=pane_focus["value"] == "viewer",
                )
            return _viewer_focus_fragments(
                resolution_report_fragments(
                    active_view,
                    strategies=global_strategies,
                    focused_section=viewer_section["index"],
                    review_and_apply=review_and_apply,
                    read_only=read_only,
                ),
                focused=pane_focus["value"] == "viewer",
            )
        return _viewer_focus_fragments(
            resolution_viewer_fragments(
                active_view,
                current_navigation,
                focused_section=viewer_section["index"],
                other_direction_focused=other_direction["focused"],
                other_direction_editing=other_direction_editor["open"],
            ),
            focused=pane_focus["value"] == "viewer",
        )

    bindings = KeyBindings()
    status = {"value": ""}
    global_comment = {"value": False}
    pane_focus = {"value": "items" if split_viewer_items else "viewer"}
    split_row = {"index": 0}
    strategy = {"index": 0}
    viewer_content = {"kind": "REPORT"}
    viewer_section = {"index": 0}
    navigation_accelerator = _NavigationAccelerator()
    other_direction = {"focused": False}
    other_direction_editor = {"open": False}
    input_heading = {"value": "COMMENT ON SELECTED CONFLICT"}
    local_drafts: dict[str, tuple[str | None, str]] = {}

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
            )
        ),
        focusable=True,
        show_cursor=False,
    )
    body = Window(
        body_control,
        wrap_lines=True,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )

    def item_fragments():
        active_view = current_view()
        fragments: list[tuple[str, str]] = []
        rows = (
            (
                (
                    "REPORT",
                    (
                        "Complete Compare report"
                        if split_report_text is not None
                        else "Complete Meld report"
                    ),
                ),
            )
            + tuple(("CONFLICT", item.title) for item in active_view.items)
            + (
                ()
                if read_only
                else (
                    (
                        (
                            (
                                "REVIEW & APPLY"
                                if active_view.accept_enabled
                                else "MATERIALIZE"
                            ),
                            (
                                "Apply the exact reviewed proposal"
                                if active_view.accept_enabled
                                else "Materialize choices shown in Report"
                            ),
                        )
                        if review_and_apply
                        else ("RESOLVE ALL", "Whole-set resolution strategy")
                    ),
                )
            )
        )
        for index, (kind, label) in enumerate(rows):
            selected = index == split_row["index"]
            if selected:
                fragments.append(("[SetCursorPosition]", ""))
            fragments.append(
                (
                    (
                        "class:memcommit.table.selected"
                        if selected and pane_focus["value"] == "items"
                        else "bold"
                        if selected
                        else ""
                    ),
                    (f"{'›' if selected else ' '} {kind:<14} {_line(label)}"),
                )
            )
            if index < len(rows) - 1:
                fragments.append(("", "\n"))
        return fragments

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

    def load_draft() -> None:
        item = current_navigation.current_item(current_view())
        if item is None:
            current_navigation.selected_option_uid = None
            input_area.text = ""
            return
        if draft_loader is None:
            selected_option_uid, comment = local_drafts.get(
                item.uid,
                (item.selected_option_uid, ""),
            )
        else:
            selected_option_uid, comment = draft_loader(item.uid)
            if selected_option_uid is not None:
                item.option(selected_option_uid)
        current_navigation.selected_option_uid = selected_option_uid
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

    def move(delta: int) -> None:
        active_view = current_view()
        if split_viewer_items:
            if pane_focus["value"] == "viewer":
                if viewer_content["kind"] == "REVIEW":
                    viewer_section["index"] = max(
                        0,
                        min(viewer_section["index"] + delta, 2),
                    )
                elif viewer_content["kind"] == "REPORT":
                    if split_report_text is not None:
                        report_lines = _seeded_report_lines(
                            active_view,
                            split_report_text,
                            global_strategies,
                            review_and_apply,
                            read_only,
                        )
                        sections = _seeded_report_sections(report_lines)
                        last_section = len(sections) - 1
                    else:
                        sections = ()
                        last_section = len(active_view.items) + (2 if read_only else 3)
                    viewer_section["index"] = max(
                        0,
                        min(viewer_section["index"] + delta, last_section),
                    )
                    section = viewer_section["index"]
                    if sections:
                        key = sections[section][1]
                        if key.startswith("ITEM:"):
                            item_index = int(key.split(":", 1)[1])
                            if item_index < len(active_view.items):
                                split_row["index"] = item_index + 1
                                current_navigation.selected_item_uid = (
                                    active_view.items[item_index].uid
                                )
                        elif key == "RESOLVE_ALL":
                            split_row["index"] = len(active_view.items) + 1
                        else:
                            split_row["index"] = 0
                    elif 2 <= section <= len(active_view.items) + 1:
                        split_row["index"] = section - 1
                        item = active_view.items[section - 2]
                        current_navigation.selected_item_uid = item.uid
                    elif section == last_section and not read_only:
                        split_row["index"] = len(active_view.items) + 1
                    else:
                        split_row["index"] = 0
                else:
                    item = current_navigation.current_item(active_view)
                    last_section = (
                        bool(item and item.question)
                        + bool(item and item.options)
                        + len(item.blocks if item is not None else ())
                    )
                    viewer_section["index"] = max(
                        0,
                        min(viewer_section["index"] + delta, last_section),
                    )
                set_status("")
                return
            total_rows = len(active_view.items) + (1 if read_only else 2)
            split_row["index"] = max(
                0,
                min(split_row["index"] + delta, total_rows - 1),
            )
            if split_kind() == "ITEM":
                item = active_view.items[split_row["index"] - 1]
                current_navigation.selected_item_uid = item.uid
                current_navigation.expanded_item_uid = item.uid
                current_navigation.option_cursor_uid = (
                    item.options[0].uid if item.options else None
                )
                current_navigation.selected_option_uid = item.selected_option_uid
                other_direction["focused"] = False
                load_draft()
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
            save_draft()
            current_navigation.move_item(active_view, delta)
            load_draft()
        global_comment["value"] = False
        composer.frame.title = "MESSAGE"
        set_status("")

    def arrow_delta(direction: int) -> int:
        """Accelerate only inside long proposed-result runs."""
        if not (
            split_viewer_items
            and pane_focus["value"] == "viewer"
            and viewer_content["kind"] == "REPORT"
            and split_report_text is not None
        ):
            navigation_accelerator.reset()
            return direction
        sections = _seeded_report_sections(
            _seeded_report_lines(
                current_view(),
                split_report_text,
                global_strategies,
                review_and_apply,
                read_only,
            )
        )
        section_index = max(0, min(viewer_section["index"], len(sections) - 1))
        if not sections[section_index][1].startswith("RESULT:"):
            navigation_accelerator.reset()
            return direction
        return direction * navigation_accelerator.step(direction)

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
        global_comment["value"] = False
        composer.frame.title = title
        input_heading["value"] = title
        if clear:
            input_area.text = ""
        pane_focus["value"] = "viewer"
        get_app().layout.focus(input_area)

    def submit(event) -> None:
        active_view = current_view()
        comment = input_area.text.strip()
        if review_and_apply and not global_comment["value"]:
            item = current_navigation.current_item(active_view)
            save_draft()
            other_direction_editor["open"] = False
            pane_focus["value"] = "viewer"
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
        move(arrow_delta(1))
        event.app.invalidate()

    @bindings.add("up", filter=~has_focus(input_area))
    def _up(event) -> None:
        move(arrow_delta(-1))
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
            elif split_kind() == "ITEM":
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
            elif split_kind() == "ITEM":
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
                other_direction_editor["open"] = False
                viewer_content["kind"] = "REPORT"
                viewer_section["index"] = 0
                pane_focus["value"] = "viewer"
                event.app.layout.focus(body_control)
                set_status("")
            elif kind == "ITEM":
                if viewer_content["kind"] != "ITEM":
                    other_direction_editor["open"] = False
                    viewer_content["kind"] = "ITEM"
                    viewer_section["index"] = 0
                    current_navigation.expanded_item_uid = (
                        current_navigation.selected_item_uid
                    )
                    item = current_navigation.current_item(active_view)
                    current_navigation.option_cursor_uid = (
                        item.options[0].uid
                        if item is not None and item.options
                        else None
                    )
                    other_direction["focused"] = False
                    set_status("")
                elif read_only:
                    set_status("Applied Melds are read-only.")
                elif other_direction["focused"]:
                    current_navigation.selected_option_uid = None
                    other_direction_editor["open"] = True
                    open_item_input(title="OTHER DIRECTION", clear=True)
                else:
                    current_navigation.toggle_option(active_view)
                    save_draft()
                    selected_uid = current_navigation.selected_option_uid
                    if selected_uid is None:
                        set_status("Selection cleared.")
                    else:
                        selected_option = active_view.item(
                            current_navigation.selected_item_uid
                        ).option(selected_uid)
                        set_status(f"Selected · {selected_option.label}")
            elif not global_strategies:
                set_status("No whole-set strategies are available.")
            elif review_and_apply:
                save_draft()
                if active_view.accept_enabled:
                    action = semantic_action("ACCEPT")
                    if action is not None:
                        event.app.exit(result=action)
                    event.app.invalidate()
                    return
                selected_strategy = global_strategies[strategy["index"]]
                lines = ["Use these reviewed issue resolutions:"]
                unresolved_counts: dict[str, int] = {}
                unresolved_required: list[str] = []
                for item in active_view.items:
                    option_uid, comment = local_drafts.get(
                        item.uid,
                        (item.selected_option_uid, ""),
                    )
                    if option_uid is not None:
                        option = item.option(option_uid)
                        response = f"Choose this reading: {option.text}"
                        if comment.strip():
                            response += f" Additional guidance: {comment.strip()}"
                        lines.append(f"- {item.title}: {response}")
                    elif comment.strip():
                        lines.append(
                            f"- {item.title}: Other direction: {comment.strip()}"
                        )
                    else:
                        unresolved_counts[item.priority] = (
                            unresolved_counts.get(item.priority, 0) + 1
                        )
                        if item.priority == "REQUIRED":
                            unresolved_required.append(item.title)
                if unresolved_counts:
                    counts = ", ".join(
                        f"{priority} {count}"
                        for priority, count in (
                            ("REQUIRED", unresolved_counts.get("REQUIRED", 0)),
                            ("HELPFUL", unresolved_counts.get("HELPFUL", 0)),
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
                action = semantic_action("SUBMIT_ALL", comment="\n".join(lines))
                if action is not None:
                    event.app.exit(result=action)
            elif viewer_content["kind"] != "REPORT" or viewer_section["index"] != (
                len(
                    _seeded_report_sections(
                        _seeded_report_lines(
                            active_view,
                            split_report_text,
                            global_strategies,
                            review_and_apply,
                            read_only,
                        )
                    )
                )
                - 1
                if split_report_text is not None
                else len(active_view.items) + (2 if read_only else 3)
            ):
                viewer_content["kind"] = "REPORT"
                viewer_section["index"] = (
                    len(
                        _seeded_report_sections(
                            _seeded_report_lines(
                                active_view,
                                split_report_text,
                                global_strategies,
                                review_and_apply,
                                read_only,
                            )
                        )
                    )
                    - 1
                    if split_report_text is not None
                    else len(active_view.items) + (2 if read_only else 3)
                )
                set_status("")
            else:
                selected_strategy = global_strategies[strategy["index"]]
                if selected_strategy.action_kind == "CUSTOM":
                    global_comment["value"] = True
                    input_heading["value"] = "WHOLE-SET GUIDANCE"
                    input_area.text = ""
                    pane_focus["value"] = "viewer"
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
            set_status("")
        elif item.options:
            current_navigation.toggle_option(active_view)
            save_draft()
            set_status("")
        else:
            current_navigation.toggle_detail(active_view)
            set_status("")
        event.app.invalidate()

    @bindings.add("tab")
    def _focus_input(event) -> None:
        if event.app.layout.has_focus(input_area):
            save_draft()
            other_direction_editor["open"] = False
            if split_viewer_items:
                pane_focus["value"] = "viewer"
                event.app.layout.focus(body_control)
            else:
                event.app.layout.focus(body_control)
            event.app.invalidate()
            return
        if split_viewer_items:
            pane_focus["value"] = (
                "viewer" if pane_focus["value"] == "items" else "items"
            )
            event.app.layout.focus(
                body_control if pane_focus["value"] == "viewer" else items_control
            )
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
        composer.frame.title = "COMMENT ON SELECTED CONFLICT"
        input_heading["value"] = "COMMENT ON SELECTED CONFLICT"
        if split_viewer_items:
            pane_focus["value"] = "viewer"
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
            pane_focus["value"] = "viewer"
            event.app.layout.focus(input_area)
            return
        if split_kind() != "ITEM":
            set_status("Choose one conflict or RESOLVE ALL first.")
            event.app.invalidate()
            return
        if viewer_content["kind"] != "ITEM":
            set_status("Press Enter to open the selected conflict first.")
            event.app.invalidate()
            return
        if active_view.input_locked or "SUBMIT_ITEM" not in active_view.capabilities:
            set_status("Item comments are unavailable here.")
            event.app.invalidate()
            return
        global_comment["value"] = False
        other_direction_editor["open"] = False
        composer.frame.title = "MESSAGE"
        input_heading["value"] = "COMMENT ON SELECTED CONFLICT"
        pane_focus["value"] = "viewer"
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
            pane_focus["value"] = "viewer"
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
        if current_navigation.expanded_item_uid is None:
            return False
        current_navigation.close_detail()
        return True

    def _close(event) -> None:
        if save_draft_on_close and not event.app.layout.has_focus(input_area):
            save_draft()
        event.app.exit(result=ResolutionWorkbenchAction(kind="CLOSE"))

    @bindings.add("escape", eager=True)
    def _back_or_close(event) -> None:
        if (
            split_viewer_items
            and not event.app.layout.has_focus(input_area)
            and split_row["index"] != 0
        ):
            split_row["index"] = 0
            viewer_content["kind"] = "REPORT"
            viewer_section["index"] = 0
            current_navigation.close_detail()
            pane_focus["value"] = "items"
            event.app.layout.focus(items_control)
            event.app.invalidate()
            return
        # Keep the shared shell independent of operation-specific back
        # dispatchers: its only presentation layer is the expanded detail.
        if _collapse_detail(event):
            event.app.invalidate()
            return
        _close(event)

    @bindings.add("backspace", filter=~has_focus(input_area))
    def _backspace(event) -> None:
        if not _collapse_detail(event):
            set_status("Use Q or Escape to close the workbench.")
        event.app.invalidate()

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
                "Enter inspect  Esc close "
                if read_only
                else " ↑/↓ block (hold accelerates)  PgUp/PgDn page  End last  Tab switch  "
                "Enter open  Esc/Q close "
            )
        elif split_viewer_items and split_kind() == "RESOLVE_ALL":
            navigation_help = (
                (
                    " ↑/↓ section/item  Tab switch  Enter apply  Esc report "
                    if active_view.accept_enabled
                    else " ↑/↓ section/item  Tab switch  ←/→ policy  "
                    "Enter materialize  Esc report "
                )
                if review_and_apply
                else " ↑/↓ section/item  Tab switch  ←/→ strategy  "
                "Enter open/run  C custom  Esc report "
            )
        elif split_viewer_items:
            navigation_help = (
                " ↑/↓ section/item  Tab switch  ←/→ option  "
                "Enter choose/other  C send/comment  Esc report "
            )
        elif (
            item is not None
            and current_navigation.expanded_item_uid == item.uid
            and item.options
        ):
            navigation_help = " ↑/↓ option  Enter choose/clear  Esc back  Tab comment "
        elif current_navigation.expanded_item_uid is not None:
            navigation_help = " Enter close  Esc back  Tab comment "
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
            actions.append("A accept")
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
    if split_viewer_items:
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
        viewer_frame = Frame(HSplit([body, inline_input]), title="VIEWER")
        items_frame = Frame(items_window, title="ITEMS")
        root = HSplit(
            [
                viewer_frame,
                items_frame,
                footer,
            ]
        )
        bind_focused_frame_style(
            viewer_frame,
            is_focused=lambda: pane_focus["value"] == "viewer",
        )
        bind_focused_frame_style(
            items_frame,
            is_focused=lambda: pane_focus["value"] == "items",
        )
        focused_element = items_control
    else:
        root = build_tui_frame(
            TuiRegion(body),
            TuiRegion(composer.container),
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
        style=(
            merge_styles(
                [
                    MEMCOMMIT_TUI_STYLE,
                    Style.from_dict(
                        {
                            "viewer-section": "fg:#8bd5ff bold",
                            "detail-card": "fg:#cad3f5",
                            "detail-card.focused": "fg:#8bd5ff bold",
                            "option-card": "fg:#a5adcb",
                            "option-card.focused": "fg:#8bd5ff bold",
                            "option-card.selected": "fg:#a6da95 bold",
                            "option-card.other": "fg:#c6a0f6 bold",
                            "selection-badge": "fg:#8bd5ff bold",
                        }
                    ),
                ]
            )
            if split_viewer_items
            else None
        ),
    )
    load_draft()
    try:
        return application.run()
    except (EOFError, KeyboardInterrupt):
        return ResolutionWorkbenchAction(kind="CLOSE")
