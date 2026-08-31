"""Render plain and interactive projections of the console Help inventory."""

from __future__ import annotations

import textwrap

import typer

from memcommit.adapters.console.terminal.core.text_layout import (
    pad_terminal_text,
    terminal_cell_width,
    wrap_terminal_text,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.operation_catalog import (
    OperationComparisonDetail,
    OperationTextDetail,
)
from memcommit.operation_catalog.localization import (
    localized_operation_copy,
)
from memcommit.application.operations.help.composer import compose_operation_help
from memcommit.adapters.console.commands.help.inventory import (
    HELP_CATEGORY_BY_COMMAND,
    HELP_CATEGORY_DESCRIPTIONS,
    HELP_CATEGORY_ORDER,
    HELP_COMMAND_ORDER,
    HELP_COMMON_KEYS,
    HELP_COMMON_LOCATORS,
    HELP_CORE_CONCEPTS,
    HELP_CORE_CONCEPT_STYLES,
    CommandEntry,
)
from memcommit.adapters.console.commands.help.localized_copy import (
    HelpLanguage,
    category_description,
    common_key_description,
    common_locator_description,
    core_concept_description,
)

def _entry_label(entry: CommandEntry) -> str:
    label = entry.name
    if entry.aliases:
        label += f" ({', '.join(entry.aliases)})"
    if entry.annotation:
        label += f" ({entry.annotation})"
    if entry.maturity:
        label += f" [{entry.maturity}]"
    return label


_HELP_SPLIT_COMMAND_LABEL_MIN = 14


def _entry_label_lines(entry: CommandEntry) -> tuple[str, ...]:
    """Project one exact command label into at most two display-only rows."""

    suffixes: list[str] = []
    if entry.aliases:
        suffixes.append(f"({', '.join(entry.aliases)})")
    if entry.annotation:
        suffixes.append(f"({entry.annotation})")
    if entry.maturity:
        suffixes.append(f"[{entry.maturity}]")
    if suffixes:
        return entry.name, " ".join(suffixes)
    if len(entry.name) >= _HELP_SPLIT_COMMAND_LABEL_MIN and "-" in entry.name:
        head, tail = entry.name.rsplit("-", 1)
        if head and tail:
            return head + "-", tail
    return (entry.name,)


def _entry_line(
    entry: CommandEntry,
    *,
    name_width: int,
) -> str:
    label = _entry_label(entry)
    return f"{label:<{name_width}} - {entry.description}"


_HELP_USE_WHEN_LABEL = "WHEN"
_HELP_USE_WHEN_PREFIX = _HELP_USE_WHEN_LABEL + " · "


def _wrap_prefixed_terminal_text(
    prefix: str,
    value: str,
    *,
    width: int,
) -> list[str]:
    """Wrap translated prose after one stable terminal-cell prefix."""

    prefix_width = terminal_cell_width(prefix)
    value_width = max(1, width - prefix_width)
    value_lines = wrap_terminal_text(display_escape_text(value), value_width)
    continuation = " " * prefix_width
    return [
        (prefix if index == 0 else continuation) + line
        for index, line in enumerate(value_lines)
    ]


def _help_command_rows(
    entry: CommandEntry,
    *,
    command_prefixes: tuple[str, ...],
    content_width: int,
    language: HelpLanguage = "EN",
) -> list[tuple[str, str, str, int | None]]:
    """Project one command as a connected Description/When record."""

    prefix_width = terminal_cell_width(command_prefixes[0])
    if any(terminal_cell_width(prefix) != prefix_width for prefix in command_prefixes):
        raise ValueError("Help command prefixes must share one display width.")
    # The two-cell connector belongs to the record rather than either text
    # column. This preserves the previous row count while making the command,
    # description, and use case read as one connected unit.
    connector_width = 2
    body_width = max(1, content_width - prefix_width - connector_width)
    if entry.operation_help is None:
        localized_summary = entry.description
        localized_best_for = ""
    else:
        localized = localized_operation_copy(language, entry.name)
        localized_summary = localized.summary
        localized_best_for = localized.best_for
    summary_lines = wrap_terminal_text(
        display_escape_text(localized_summary),
        body_width,
    )
    body_rows: list[tuple[str, int | None, bool]] = [
        (pad_terminal_text(line, body_width), None, False) for line in summary_lines
    ]
    if not localized_best_for:
        best_for_lines: list[str] = []
    else:
        best_for_lines = _wrap_prefixed_terminal_text(
            _HELP_USE_WHEN_PREFIX,
            localized_best_for,
            width=body_width,
        )
        body_rows.extend(
            (
                pad_terminal_text(line, body_width),
                0 if index == 0 else None,
                True,
            )
            for index, line in enumerate(best_for_lines)
        )

    row_count = max(len(body_rows), len(command_prefixes))
    semantic_row_count = len(body_rows)
    has_when = any(is_when for _body, _offset, is_when in body_rows)

    def connector(index: int) -> str:
        if index >= semantic_row_count:
            return " " * connector_width
        if not has_when:
            return "─ " if index == 0 else " " * connector_width
        if index == 0:
            return "┬ "
        if body_rows[index][2] and not body_rows[index - 1][2]:
            return "└ "
        if body_rows[index][2]:
            return " " * connector_width
        return "│ "

    return [
        (
            (
                command_prefixes[index]
                if index < len(command_prefixes)
                else " " * prefix_width
            ),
            connector(index),
            body_rows[index][0] if index < semantic_row_count else " " * body_width,
            body_rows[index][1] if index < semantic_row_count else None,
        )
        for index in range(row_count)
    ]


def _render_plain_inventory(entries: list[CommandEntry]) -> None:
    typer.secho("mem command inventory", bold=True)
    typer.echo()

    name_width = max(len(_entry_label(entry)) for entry in entries)
    for entry in entries:
        typer.echo(
            _entry_line(
                entry,
                name_width=name_width,
            )
        )


def render_help_lookup_entries(
    entries: list[CommandEntry],
    *,
    content_width: int = 100,
    language: HelpLanguage = "EN",
) -> str:
    """Render only matched operations as their existing collapsed Help rows."""

    if not entries:
        return "No Help candidates available."
    width = max(40, content_width)
    rendered: list[str] = []
    for entry in entries:
        rows = _help_command_rows(
            entry,
            command_prefixes=(f"mem {entry.name} ",),
            content_width=width,
            language=language,
        )
        rendered.append(
            "\n".join(
                (prefix + connector + body).rstrip()
                for prefix, connector, body, _label_offset in rows
            )
        )
    return "\n\n".join(rendered)


def _help_group_fragments(
    entries: list[tuple[int, CommandEntry]],
    *,
    title: str,
    width: int,
    focused: bool,
    selected_index: int,
    expanded_index: int | None,
    selected_form: int | None,
    viewport_height: int | None = None,
    language: HelpLanguage = "EN",
) -> list[tuple[str, str]]:
    """Render one discovery kind and its command records in a single box."""
    if not entries:
        return []
    width = max(36, width)
    inner_width = width - 2
    content_width = inner_width - 2
    title_label = f" {display_escape_text(title)} "[:inner_width]
    border_style = "class:help-group.focused" if focused else "class:help-group"
    horizontal = "━" if focused else "─"
    fragments: list[tuple[str, str]] = [
        (border_style, "┏" if focused else "┌"),
        (border_style + " bold", title_label),
        (
            border_style,
            horizontal * max(0, inner_width - len(title_label))
            + ("┓" if focused else "┐")
            + "\n",
        ),
    ]
    vertical = "┃" if focused else "│"
    category_copy = HELP_CATEGORY_DESCRIPTIONS.get(title)
    if category_copy is not None:
        classification, _description = category_copy
        prefix = f"{classification} · " if classification is not None else ""
        lines = _wrap_prefixed_terminal_text(
            prefix,
            category_description(
                language,
                title,
            ),
            width=content_width,
        )
        for line in lines:
            fragments.extend([(border_style, vertical), ("", " ")])
            fragments.append(("class:help-category-description bold", line))
            fragments.extend(
                [
                    (
                        "",
                        " " * (content_width - terminal_cell_width(line) + 1),
                    ),
                    (border_style, vertical + "\n"),
                ]
            )
    label_lines = {
        index: tuple(display_escape_text(line) for line in _entry_label_lines(entry))
        for index, entry in entries
    }
    for index, entry in entries:
        expanded = index == expanded_index
        owns_selection = index == selected_index
        command_focused = focused and owns_selection and selected_form is None
        marker = "▾" if expanded else "▸"
        first_label = label_lines[index][0]
        # Each operation owns its junction. Keeping it next to that operation
        # prevents a category-wide prose column from visually overpowering the
        # command list. A display-only continuation still reserves enough
        # left-side width, but the branch always begins on the first row.
        connector_name_width = max(len(line) for line in label_lines[index])
        first_command_prefix = f"{marker} mem {first_label} " + "─" * (
            connector_name_width - len(first_label) + 1
        )
        # Four cells keeps a continuation visibly subordinate while pulling it
        # two cells left of the old post-"mem " alignment. Pad on the right so
        # every label row still reaches the first-row junction.
        continuation_indent = " " * 4
        command_prefixes = (
            first_command_prefix,
            *(
                pad_terminal_text(
                    continuation_indent + line,
                    terminal_cell_width(first_command_prefix),
                )
                for line in label_lines[index][1:]
            ),
        )
        for prefix, connector, body, label_offset in _help_command_rows(
            entry,
            command_prefixes=command_prefixes,
            content_width=content_width,
            language=language,
        ):
            fragments.append((border_style, vertical))
            body_style = "class:help-command.selected" if command_focused else ""
            prefix_style = (
                "class:help-command.selected bold"
                if command_focused
                else "class:help-command"
            )
            fragments.append((prefix_style, f" {prefix}"))
            connector_style = body_style if command_focused else "class:help-connector"
            fragments.append((connector_style, connector))
            if label_offset is None:
                fragments.append((body_style, f"{body} "))
            else:
                label = _HELP_USE_WHEN_LABEL
                label_end = label_offset + len(label)
                fragments.extend(
                    [
                        (body_style, body[:label_offset]),
                        (body_style, body[label_offset:label_end]),
                        (body_style, body[label_end:] + " "),
                    ]
                )
            fragments.append((border_style, vertical + "\n"))
        if command_focused:
            # Anchor after the complete connected record. Prompt-toolkit only
            # guarantees visibility through the cursor row; anchoring before
            # a two-line record let the final WHEN row (and the closing border
            # after `mem eval`) fall below the viewport at the end of Help.
            fragments.append(("[SetCursorPosition]", ""))
        if expanded:
            if entry.operation_help is not None:
                composed = compose_operation_help(
                    entry.operation_help,
                    cli_forms=entry.forms,
                )
                detail_label_width = max(len(row.label) for row in composed.overview)
                for row in composed.overview:
                    # The use case is already visible in every command row,
                    # even before expansion; do not duplicate it in the detail.
                    if row.label == "BEST FOR":
                        continue
                    prefix = f"  {row.label:<{detail_label_width}} · "
                    lines = textwrap.wrap(
                        display_escape_text(row.value),
                        width=content_width,
                        initial_indent=prefix,
                        subsequent_indent=" " * len(prefix),
                        break_long_words=True,
                        break_on_hyphens=False,
                    ) or [prefix]
                    for line in lines:
                        fragments.extend(
                            [
                                (border_style, vertical),
                                (
                                    "",
                                    f" {line:<{content_width}} ",
                                ),
                                (border_style, vertical + "\n"),
                            ]
                        )
            details = (
                () if entry.operation_help is None else entry.operation_help.details
            )
            for detail in details:
                detail_lines: list[tuple[str, str]] = []
                title_prefix = "  "
                for line in textwrap.wrap(
                    display_escape_text(detail.title),
                    width=content_width,
                    initial_indent=title_prefix,
                    subsequent_indent=title_prefix,
                    break_long_words=True,
                    break_on_hyphens=False,
                ) or [title_prefix]:
                    detail_lines.append(("bold", line))
                if isinstance(detail, OperationComparisonDetail):
                    for line in textwrap.wrap(
                        display_escape_text(detail.explanation),
                        width=content_width,
                        initial_indent="  ",
                        subsequent_indent="  ",
                        break_long_words=True,
                        break_on_hyphens=False,
                    ) or ["  "]:
                        detail_lines.append(("", line))
                    for option in detail.options:
                        # Terminal Help uses a literal hyphen rather than relying on
                        # renderer-specific Markdown bullet projection.
                        value = f"{option.label} · {option.guidance}"
                        for line in textwrap.wrap(
                            display_escape_text(value),
                            width=content_width,
                            initial_indent="  - ",
                            subsequent_indent="    ",
                            break_long_words=True,
                            break_on_hyphens=False,
                        ) or ["  -"]:
                            detail_lines.append(("", line))
                elif isinstance(detail, OperationTextDetail):
                    for line in textwrap.wrap(
                        display_escape_text(detail.body),
                        width=content_width,
                        initial_indent="  ",
                        subsequent_indent="  ",
                        break_long_words=True,
                        break_on_hyphens=False,
                    ) or ["  "]:
                        detail_lines.append(("", line))
                else:  # pragma: no cover - catalog validation closes the union
                    raise TypeError("Unsupported Operation Help detail type.")
                for style, line in detail_lines:
                    fragments.extend(
                        [
                            (border_style, vertical),
                            (style, f" {line:<{content_width}} "),
                            (border_style, vertical + "\n"),
                        ]
                    )
            for form_index, form in enumerate(entry.forms):
                form_focused = (
                    focused and owns_selection and selected_form == form_index
                )
                prefix = f"  FORM {form_index + 1} · "
                lines = textwrap.wrap(
                    display_escape_text(form),
                    width=content_width,
                    initial_indent=prefix,
                    subsequent_indent=" " * len(prefix),
                    break_long_words=True,
                    break_on_hyphens=False,
                ) or [prefix]
                for line in lines:
                    fragments.extend(
                        [
                            (border_style, vertical),
                            (
                                "class:selected" if form_focused else "class:form",
                                f" {line:<{content_width}} ",
                            ),
                            (border_style, vertical + "\n"),
                        ]
                    )
                if form_focused:
                    # Wrapped Forms follow the same whole-record visibility
                    # rule as collapsed commands.
                    fragments.append(("[SetCursorPosition]", ""))
    if viewport_height is not None:
        # A–Z owns one box, so keep spare viewport rows inside that box instead
        # of implying that more unboxed content exists below the final command.
        rendered_rows = sum(text.count("\n") for _style, text in fragments)
        blank_rows = max(0, viewport_height - rendered_rows - 1)
        for _row in range(blank_rows):
            fragments.extend(
                [
                    (border_style, vertical),
                    ("", " " * inner_width),
                    (border_style, vertical + "\n"),
                ]
            )
    fragments.append(
        (
            border_style,
            ("┗" if focused else "└")
            + horizontal * inner_width
            + ("┛" if focused else "┘")
            + ("" if viewport_height is not None else "\n"),
        )
    )
    return fragments


def _help_group_width(terminal_columns: int) -> int:
    """Use the complete Help viewport except its one-column scrollbar."""
    return max(36, terminal_columns - 1)


def _help_list_viewport_height(terminal_rows: int) -> int:
    """Return rows left after Help's fixed header, controls, rule, and footer."""

    return max(2, terminal_rows - 9)


def _help_information_box_fragments(
    *,
    width: int,
    by_kind: bool,
    focused_concept_index: int | None = None,
    focused: bool = False,
    language: HelpLanguage = "EN",
) -> list[tuple[str, str]]:
    """Render the BY KIND primer as focusable concepts plus key reference."""
    if not by_kind:
        return []
    width = max(36, width)
    inner_width = width - 2
    content_width = inner_width - 2
    guide_focused = focused and focused_concept_index is not None
    border_style = (
        "class:help-guide.border.focused"
        if guide_focused
        else "class:help-guide.border"
    )
    label_style = "class:help-guide.label"
    fragments: list[tuple[str, str]] = []

    def border(title: str, *, middle: bool) -> None:
        title_label = f" {title} "[:inner_width]
        if guide_focused:
            left, right = ("┣", "┫") if middle else ("┏", "┓")
        else:
            left, right = ("├", "┤") if middle else ("┌", "┐")
        horizontal = "━" if guide_focused else "─"
        fragments.append(
            (
                border_style,
                left
                + title_label
                + horizontal * max(0, inner_width - len(title_label))
                + right
                + "\n",
            )
        )

    def rows(
        items: tuple[tuple[str, str], ...],
        *,
        selectable: bool,
        label_styles: dict[str, str] | None = None,
    ) -> None:
        label_width = max(terminal_cell_width(label) for label, _description in items)
        for item_index, (label, description) in enumerate(items):
            row_focused = selectable and focused and focused_concept_index == item_index
            prefix = pad_terminal_text(label, label_width) + "  "
            lines = wrap_terminal_text(
                display_escape_text(description),
                max(1, content_width - terminal_cell_width(prefix)),
            )
            for line_index, line in enumerate(lines):
                if row_focused and line_index == 0:
                    fragments.append(("[SetCursorPosition]", ""))
                row_prefix = prefix if line_index == 0 else " " * len(prefix)
                padding = " " * max(
                    0,
                    content_width
                    - terminal_cell_width(row_prefix)
                    - terminal_cell_width(line),
                )
                fragments.extend(
                    [
                        (border_style, "┃" if guide_focused else "│"),
                        (
                            (
                                "class:selected" if row_focused else "",
                                " " + row_prefix + line + padding + " ",
                            )
                            if row_focused
                            else ("", " ")
                        ),
                    ]
                )
                if not row_focused:
                    fragments.extend(
                        [
                            (
                                (
                                    (label_styles or {}).get(label, label_style)
                                    if line_index == 0
                                    else ""
                                ),
                                row_prefix,
                            ),
                            ("", line + padding + " "),
                        ]
                    )
                fragments.append((border_style, ("┃" if guide_focused else "│") + "\n"))

    border("CORE CONCEPTS", middle=False)
    rows(
        tuple(
            (
                label,
                core_concept_description(language, label, description),
            )
            for label, description in HELP_CORE_CONCEPTS
        ),
        selectable=True,
        label_styles=HELP_CORE_CONCEPT_STYLES,
    )
    border("COMMON LOCATORS", middle=True)
    rows(
        tuple(
            (
                locator,
                common_locator_description(language, locator, description),
            )
            for locator, description in HELP_COMMON_LOCATORS
        ),
        selectable=False,
    )
    border("COMMON KEYS", middle=True)
    rows(
        tuple(
            (
                key,
                common_key_description(language, key, description),
            )
            for key, description in HELP_COMMON_KEYS
        ),
        selectable=False,
    )
    fragments.append(
        (
            border_style,
            ("┗" if guide_focused else "└")
            + ("━" if guide_focused else "─") * inner_width
            + ("┛" if guide_focused else "┘")
            + "\n",
        )
    )
    return fragments


def _ordered_help_entries(
    entries: list[CommandEntry],
    *,
    by_kind: bool,
) -> list[CommandEntry]:
    """Keep workflow order for kinds and reserve lexical order for A–Z."""
    if not by_kind:
        return sorted(entries, key=lambda entry: (entry.name.casefold(), entry.name))
    return sorted(
        entries,
        key=lambda entry: (
            HELP_CATEGORY_ORDER.get(
                HELP_CATEGORY_BY_COMMAND.get(entry.name, "OTHER"),
                len(HELP_CATEGORY_ORDER),
            ),
            HELP_COMMAND_ORDER.get(entry.name, 0),
            entry.name.casefold(),
            entry.name,
        ),
    )


def _help_section_heading_fragments(
    *,
    title: str,
    width: int,
) -> list[tuple[str, str]]:
    """Mark a semantic section without nesting the category frames below it."""

    width = max(36, width)
    displayed = display_escape_text(title)[:width]
    return [("class:category", displayed + " " * (width - len(displayed)) + "\n")]
