"""Run the prompt-toolkit Help inventory browser."""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Literal

from prompt_toolkit.application import Application
from prompt_toolkit.filters import has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, HSplit, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import Style, merge_styles
from prompt_toolkit.widgets import Frame

from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.adapters.console.terminal.core.keybindings import (
    NavigationAccelerator,
    bind_case_insensitive_key,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.adapters.console.terminal.components.frame import (
    bind_focused_frame_style,
    horizontal_rule,
)
from memcommit.adapters.console.terminal.components.focus import (
    FocusSurface,
    SurfaceFocusController,
)
from memcommit.adapters.console.terminal.components.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.adapters.console.commands.help.inventory import (
    HELP_CATEGORY_BY_COMMAND,
    HELP_CORE_CONCEPTS,
    CommandEntry,
    HelpSelection,
    _selectable_form_line,
)
from memcommit.adapters.console.commands.help.localized_copy import (
    HELP_LANGUAGES,
    HelpLanguage,
)
from memcommit.adapters.console.commands.help.rendering import (
    _help_group_fragments,
    _help_group_width,
    _help_information_box_fragments,
    _help_list_viewport_height,
    _help_section_heading_fragments,
    _ordered_help_entries,
)

def run_help_selector(
    entries: list[CommandEntry],
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    mode: Literal["SELECT", "EXPLORE"] = "SELECT",
    status_supplier: Callable[[], str] | None = None,
    on_explore_action: Callable[[str, str | None], None] | None = None,
    on_ready: Callable[[], None] | None = None,
    explore_title: str = "mem help · explore while work continues",
    explore_return_label: str = "waiting",
) -> HelpSelection | None:
    """Select a command, or browse the same inventory without shell effects."""
    if not entries:
        return None
    if mode not in {"SELECT", "EXPLORE"}:
        raise ValueError("Help mode must be SELECT or EXPLORE.")
    if not explore_title.strip() or not explore_return_label.strip():
        raise ValueError("Help exploration labels must be nonblank.")
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError("Interactive help requires a terminal.")
    language_state = HorizontalChoiceState(
        tuple(
            HorizontalChoiceOption(language, language) for language in HELP_LANGUAGES
        ),
        selected_uid="EN",
    )
    view_state = HorizontalChoiceState(
        (
            HorizontalChoiceOption("CATEGORY", "BY KIND"),
            HorizontalChoiceOption("A_Z", "A–Z"),
        ),
        selected_uid="CATEGORY",
    )

    def ordered_entries() -> list[CommandEntry]:
        return _ordered_help_entries(
            entries,
            by_kind=view_state.selected_uid == "CATEGORY",
        )

    visible_entries = {"value": ordered_entries()}
    selected_index = {"value": 0}
    selected_concept_index: dict[str, int | None] = {"value": None}
    expanded_index: dict[str, int | None] = {"value": None}
    selected_form: dict[str, int | None] = {"value": None}
    category_cursors: dict[str, int] = {}
    bindings = KeyBindings()
    navigation_accelerator = NavigationAccelerator()
    app_ref: dict[str, Application[HelpSelection | None]] = {}

    def emit_explore_action(action: str, command_name: str | None = None) -> None:
        if mode == "EXPLORE" and on_explore_action is not None:
            on_explore_action(action, command_name)

    def selected_language() -> HelpLanguage:
        return language_state.selected_uid  # type: ignore[return-value]

    def select_language(delta: int) -> None:
        """Change only process-local Help prose; never mutate study data."""

        if language_state.move(delta):
            emit_explore_action("LANGUAGE", language_state.selected_uid)

    def select_view(delta: int) -> None:
        selected_name = visible_entries["value"][selected_index["value"]].name
        if not view_state.move(delta):
            return
        visible_entries["value"] = ordered_entries()
        selected_index["value"] = next(
            index
            for index, entry in enumerate(visible_entries["value"])
            if entry.name == selected_name
        )
        expanded_index["value"] = None
        selected_form["value"] = None
        selected_concept_index["value"] = None

    def concept_focus_active() -> bool:
        return (
            view_state.selected_uid == "CATEGORY"
            and selected_concept_index["value"] is not None
        )

    def visible_groups() -> list[tuple[str, list[tuple[int, CommandEntry]]]]:
        """Project the current rows into the same boxes the renderer shows."""

        indexed_entries = list(enumerate(visible_entries["value"]))
        if view_state.selected_uid != "CATEGORY":
            return [("A–Z", indexed_entries)]
        groups: list[tuple[str, list[tuple[int, CommandEntry]]]] = []
        for index, entry in indexed_entries:
            category = HELP_CATEGORY_BY_COMMAND.get(entry.name, "OTHER")
            if not groups or groups[-1][0] != category:
                groups.append((category, []))
            groups[-1][1].append((index, entry))
        return groups

    def selected_group_index(
        groups: list[tuple[str, list[tuple[int, CommandEntry]]]],
    ) -> int | None:
        if concept_focus_active():
            return None
        selected = selected_index["value"]
        return next(
            (
                group_index
                for group_index, (_title, rows) in enumerate(groups)
                if any(index == selected for index, _entry in rows)
            ),
            None,
        )

    def focus_group(
        group: tuple[str, list[tuple[int, CommandEntry]]],
    ) -> None:
        """Enter one visible kind at its last retained command cursor."""

        title, rows = group
        row_indexes = {index for index, _entry in rows}
        retained = category_cursors.get(title)
        selected_index["value"] = retained if retained in row_indexes else rows[0][0]
        selected_concept_index["value"] = None
        expanded_index["value"] = None
        selected_form["value"] = None

    def move_tab(event, direction: int) -> None:
        """Traverse VIEW and every visible BY KIND box in screen order."""

        navigation_accelerator.reset()
        if view_state.selected_uid != "CATEGORY":
            surface_focus.focus_relative(event.app, direction, wrap=True)
            event.app.invalidate()
            return

        groups = visible_groups()
        if event.app.layout.has_focus(language_control):
            if direction > 0:
                event.app.layout.focus(view_control)
            else:
                focus_group(groups[-1])
                event.app.layout.focus(list_control)
            event.app.invalidate()
            return
        if event.app.layout.has_focus(view_control):
            if direction < 0:
                event.app.layout.focus(language_control)
            else:
                focus_group(groups[0])
                event.app.layout.focus(list_control)
            event.app.invalidate()
            return

        group_index = selected_group_index(groups)
        if group_index is not None:
            title, _rows = groups[group_index]
            category_cursors[title] = selected_index["value"]
        target_index = (
            0
            if group_index is None and direction > 0
            else group_index + direction
            if group_index is not None
            else -1
        )
        if 0 <= target_index < len(groups):
            focus_group(groups[target_index])
        else:
            expanded_index["value"] = None
            selected_form["value"] = None
            surface_focus.focus_relative(
                event.app,
                direction,
                # VIEW is declared before the scrolling list, so moving
                # forward from the final kind crosses the layout boundary by
                # wrapping once; reverse movement reaches VIEW directly.
                wrap=True,
            )
        event.app.invalidate()

    def render_entries():
        fragments: list[tuple[str, str]] = []
        app = app_ref.get("app")
        list_focused = app is not None and app.layout.has_focus(list_control)
        terminal_columns = app.output.get_size().columns if app is not None else 80
        terminal_rows = app.output.get_size().rows if app is not None else 24
        card_width = _help_group_width(terminal_columns)
        by_kind = view_state.selected_uid == "CATEGORY"
        fragments.extend(
            _help_information_box_fragments(
                width=card_width,
                by_kind=by_kind,
                focused_concept_index=selected_concept_index["value"],
                focused=list_focused,
                language=selected_language(),
            )
        )
        if fragments:
            fragments.append(("", "\n"))
        fragments.extend(
            _help_section_heading_fragments(
                title="OPERATIONS",
                width=card_width,
            )
        )
        groups = visible_groups()
        for group_index, (title, group_entries) in enumerate(groups):
            group_focused = (
                list_focused
                and any(
                    index == selected_index["value"] for index, _entry in group_entries
                )
                and not concept_focus_active()
            )
            fragments.extend(
                _help_group_fragments(
                    group_entries,
                    title=title,
                    width=card_width,
                    focused=group_focused,
                    selected_index=selected_index["value"],
                    expanded_index=expanded_index["value"],
                    selected_form=selected_form["value"],
                    viewport_height=(
                        None if by_kind else _help_list_viewport_height(terminal_rows)
                    ),
                    language=selected_language(),
                )
            )
            if group_index < len(groups) - 1:
                fragments.append(("", "\n"))
        return fragments

    list_control = FormattedTextControl(
        text=render_entries,
        focusable=True,
        show_cursor=False,
    )
    language_control = FormattedTextControl(
        lambda: render_horizontal_choice(
            language_state,
            title="LANGUAGE",
            focused=(
                app_ref.get("app") is not None
                and app_ref["app"].layout.has_focus(language_control)
            ),
            inline_boxed=True,
        ),
        focusable=True,
        show_cursor=False,
    )
    view_control = FormattedTextControl(
        lambda: render_horizontal_choice(
            view_state,
            title="VIEW",
            focused=(
                app_ref.get("app") is not None
                and app_ref["app"].layout.has_focus(view_control)
            ),
            inline_boxed=True,
        ),
        focusable=True,
        show_cursor=False,
    )
    surface_focus = SurfaceFocusController(
        (
            FocusSurface("language", language_control),
            FocusSurface("view", view_control),
            FocusSurface("commands", list_control),
        )
    )

    def move_one(direction: int) -> None:
        concept_index = selected_concept_index["value"]
        if concept_focus_active() and concept_index is not None:
            candidate = concept_index + direction
            if candidate >= len(HELP_CORE_CONCEPTS):
                selected_concept_index["value"] = None
                selected_index["value"] = 0
            else:
                selected_concept_index["value"] = max(0, candidate)
            return
        form_index = selected_form["value"]
        if form_index is not None:
            forms = visible_entries["value"][selected_index["value"]].forms
            candidate = form_index + direction
            if candidate < 0:
                selected_form["value"] = None
            elif candidate < len(forms):
                selected_form["value"] = candidate
            else:
                selected_form["value"] = None
                expanded_index["value"] = None
                selected_index["value"] = min(
                    selected_index["value"] + 1,
                    len(visible_entries["value"]) - 1,
                )
            return
        if (
            direction < 0
            and selected_index["value"] == 0
            and view_state.selected_uid == "CATEGORY"
        ):
            expanded_index["value"] = None
            selected_concept_index["value"] = len(HELP_CORE_CONCEPTS) - 1
            return
        previous = selected_index["value"]
        selected_index["value"] = max(
            0,
            min(
                selected_index["value"] + direction,
                len(visible_entries["value"]) - 1,
            ),
        )
        if selected_index["value"] != previous:
            expanded_index["value"] = None

    @bindings.add("down", filter=has_focus(list_control))
    def _next_command(event) -> None:
        navigation_accelerator.move(
            1,
            app=event.app,
            move_one=move_one,
        )

    @bindings.add("up", filter=has_focus(list_control))
    def _previous_command(event) -> None:
        if concept_focus_active() and selected_concept_index["value"] == 0:
            navigation_accelerator.reset()
            surface_focus.focus_relative(
                event.app,
                -1,
                wrap=False,
            )
            event.app.invalidate()
            return
        if (
            selected_index["value"] == 0
            and selected_form["value"] is None
            and view_state.selected_uid != "CATEGORY"
        ):
            navigation_accelerator.reset()
            surface_focus.focus_relative(
                event.app,
                -1,
                wrap=False,
            )
            event.app.invalidate()
            return
        navigation_accelerator.move(
            -1,
            app=event.app,
            move_one=move_one,
        )

    @bindings.add("pagedown", filter=has_focus(list_control))
    def _next_page(event) -> None:
        navigation_accelerator.reset()
        selected_form["value"] = None
        expanded_index["value"] = None
        concept_count = (
            len(HELP_CORE_CONCEPTS) if view_state.selected_uid == "CATEGORY" else 0
        )
        position = (
            selected_concept_index["value"]
            if concept_focus_active()
            else concept_count + selected_index["value"]
        )
        target = min(
            int(position) + 10,
            concept_count + len(visible_entries["value"]) - 1,
        )
        if target < concept_count:
            selected_concept_index["value"] = target
        else:
            selected_concept_index["value"] = None
            selected_index["value"] = target - concept_count
        event.app.invalidate()

    @bindings.add("pageup", filter=has_focus(list_control))
    def _previous_page(event) -> None:
        navigation_accelerator.reset()
        selected_form["value"] = None
        expanded_index["value"] = None
        concept_count = (
            len(HELP_CORE_CONCEPTS) if view_state.selected_uid == "CATEGORY" else 0
        )
        position = (
            selected_concept_index["value"]
            if concept_focus_active()
            else concept_count + selected_index["value"]
        )
        target = max(int(position) - 10, 0)
        if target < concept_count:
            selected_concept_index["value"] = target
        else:
            selected_concept_index["value"] = None
            selected_index["value"] = target - concept_count
        event.app.invalidate()

    @bindings.add("home", filter=has_focus(list_control))
    def _first_command(event) -> None:
        navigation_accelerator.reset()
        selected_form["value"] = None
        expanded_index["value"] = None
        if view_state.selected_uid == "CATEGORY":
            selected_concept_index["value"] = 0
        else:
            selected_index["value"] = 0
        event.app.invalidate()

    @bindings.add("end", filter=has_focus(list_control))
    def _last_command(event) -> None:
        navigation_accelerator.reset()
        selected_form["value"] = None
        expanded_index["value"] = None
        selected_concept_index["value"] = None
        selected_index["value"] = len(visible_entries["value"]) - 1
        event.app.invalidate()

    @bindings.add("enter", filter=has_focus(list_control))
    def _select_row(event) -> None:
        navigation_accelerator.reset()
        if concept_focus_active():
            return
        index = selected_index["value"]
        form_index = selected_form["value"]
        if form_index is None:
            # Keep the first Enter inside the browser. If it returned to zsh,
            # a user's second confirmation Enter could execute a placeholder
            # template before they had a chance to edit it.
            expanded_index["value"] = index
            selected_form["value"] = 0
            emit_explore_action(
                "EXPAND",
                visible_entries["value"][index].name,
            )
            event.app.invalidate()
            return
        entry = visible_entries["value"][index]
        if mode == "EXPLORE":
            # A waiting Help session is a read-only learning surface. Enter
            # may inspect a form, but it must never return a shell template or
            # execute a second command while the frozen operation is running.
            emit_explore_action("FORM", entry.name)
            event.app.invalidate()
            return
        command_line = _selectable_form_line(entry.forms[form_index])
        event.app.exit(
            result=HelpSelection(
                command_name=entry.name,
                command_line=command_line,
            )
        )

    @bindings.add("right", filter=has_focus(list_control))
    def _expand(event) -> None:
        navigation_accelerator.reset()
        if concept_focus_active():
            return
        index = selected_index["value"]
        if expanded_index["value"] != index:
            expanded_index["value"] = index
            selected_form["value"] = 0
            emit_explore_action(
                "EXPAND",
                visible_entries["value"][index].name,
            )
        elif selected_form["value"] is None:
            selected_form["value"] = 0
        event.app.invalidate()

    @bindings.add("left", filter=has_focus(list_control))
    def _collapse(event) -> None:
        navigation_accelerator.reset()
        if concept_focus_active():
            return
        if selected_form["value"] is not None:
            selected_form["value"] = None
        elif expanded_index["value"] == selected_index["value"]:
            expanded_index["value"] = None
        event.app.invalidate()

    def _handle_help_key(event) -> None:
        navigation_accelerator.reset()
        if mode == "EXPLORE":
            # The command-wait shell presents Help by default. H therefore
            # means the same thing on both sides of that shell: hide the
            # visible inventory here, and reopen it from the waiting surface.
            emit_explore_action("HIDE")
            event.app.exit(result=None)
            return
        if concept_focus_active():
            return
        entry = visible_entries["value"][selected_index["value"]]
        event.app.exit(
            result=HelpSelection(
                command_name=entry.name,
                command_line=f"mem {entry.name}",
                show_help=True,
            )
        )

    if mode == "EXPLORE":
        bind_case_insensitive_key(
            bindings,
            "h",
            eager=True,
        )(_handle_help_key)
    else:
        bind_case_insensitive_key(
            bindings,
            "h",
            filter=has_focus(list_control),
        )(_handle_help_key)

    @bindings.add("left", filter=has_focus(view_control), eager=True)
    def _previous_view(event) -> None:
        navigation_accelerator.reset()
        select_view(-1)
        event.app.invalidate()

    @bindings.add("left", filter=has_focus(language_control), eager=True)
    def _previous_language(event) -> None:
        navigation_accelerator.reset()
        select_language(-1)
        event.app.invalidate()

    @bindings.add("right", filter=has_focus(language_control), eager=True)
    def _next_language(event) -> None:
        navigation_accelerator.reset()
        select_language(1)
        event.app.invalidate()

    @bindings.add("down", filter=has_focus(language_control), eager=True)
    def _leave_language(event) -> None:
        surface_focus.focus_relative(
            event.app,
            1,
            wrap=False,
        )
        event.app.invalidate()

    @bindings.add("up", filter=has_focus(view_control), eager=True)
    def _enter_language(event) -> None:
        surface_focus.focus_relative(
            event.app,
            -1,
            wrap=False,
        )
        event.app.invalidate()

    @bindings.add("right", filter=has_focus(view_control), eager=True)
    def _next_view(event) -> None:
        navigation_accelerator.reset()
        select_view(1)
        event.app.invalidate()

    @bindings.add("down", filter=has_focus(view_control), eager=True)
    def _leave_view(event) -> None:
        surface_focus.focus_relative(
            event.app,
            1,
            wrap=False,
        )
        event.app.invalidate()

    @bindings.add("tab")
    def _next_surface(event) -> None:
        move_tab(event, 1)

    @bindings.add("s-tab")
    def _previous_surface(event) -> None:
        move_tab(event, -1)

    @bind_case_insensitive_key(bindings, "q", eager=True)
    @bindings.add("escape", eager=True)
    @bindings.add("c-c", eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=None)

    def header_fragments() -> list[tuple[str, str]]:
        title = (
            " " + explore_title
            if mode == "EXPLORE"
            else " mem help · command inventory"
        )
        status = status_supplier() if status_supplier is not None else ""
        fragments = [("class:title", title)]
        if status:
            fragments.append(("", f" · {display_escape_text(status)}"))
        return fragments

    header = Window(
        FormattedTextControl(header_fragments),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    body = Window(
        list_control,
        wrap_lines=False,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )
    view = Window(
        view_control,
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    language = Window(
        language_control,
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    language_frame = Frame(language, title="HELP LANGUAGE")
    bind_focused_frame_style(
        language_frame,
        is_focused=lambda: (
            app_ref.get("app") is not None
            and app_ref["app"].layout.has_focus(language_control)
        ),
    )
    view_frame = Frame(view, title="INVENTORY VIEW")
    bind_focused_frame_style(
        view_frame,
        is_focused=lambda: (
            app_ref.get("app") is not None
            and app_ref["app"].layout.has_focus(view_control)
        ),
    )

    def footer_text() -> str:
        return_label = (
            f"return to {explore_return_label}" if mode == "EXPLORE" else "cancel"
        )
        if app_ref.get("app") is not None and app_ref["app"].layout.has_focus(
            language_control
        ):
            return " LANGUAGE: ←/→ choose · ↓ view · Tab next · Q " + return_label
        if app_ref.get("app") is not None and app_ref["app"].layout.has_focus(
            view_control
        ):
            toggle = " · H hide Help" if mode == "EXPLORE" else ""
            tab_hint = (
                "Tab first kind"
                if view_state.selected_uid == "CATEGORY"
                else "Tab list"
            )
            return f" VIEW: ←/→ choose · ↓ list · {tab_hint}{toggle} · Q {return_label}"
        if concept_focus_active():
            toggle = (
                f" H hide Help · Q return to {explore_return_label}"
                if mode == "EXPLORE"
                else ""
            )
            return f" ↑/↓ move (hold accelerates)  Tab first kind {toggle}"
        enter_action = (
            "Enter open forms"
            if selected_form["value"] is None
            else ("Enter inspect form" if mode == "EXPLORE" else "Enter edit command")
        )
        detail_action = (
            f"H hide Help  Q return to {explore_return_label}"
            if mode == "EXPLORE"
            else "H full help  Q/Esc close"
        )
        tab_hint = (
            "Tab next kind" if view_state.selected_uid == "CATEGORY" else "Tab surface"
        )
        return (
            " ↑/↓ move (hold accelerates)  → expand/forms  ← back  "
            f"{enter_action}  {tab_hint}  {detail_action} "
        )

    footer = Window(
        FormattedTextControl(footer_text),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    application: Application[HelpSelection | None] = Application(
        layout=Layout(
            HSplit(
                [
                    header,
                    language_frame,
                    view_frame,
                    body,
                    horizontal_rule(right_gutter=1),
                    footer,
                ]
            ),
            focused_element=list_control,
        ),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        refresh_interval=(0.35 if status_supplier is not None else None),
        style=merge_styles(
            [
                MEMCOMMIT_TUI_STYLE,
                SEMANTIC_VIEWER_STYLE,
                Style.from_dict(
                    {
                        "title": "bold",
                        "selected": "fg:#10242f bg:#8bd5ff bold",
                        "help-command.selected": "fg:#10242f bg:#8bd5ff",
                        "help-connector": "fg:#6e738d",
                        "form": "fg:#cad3f5",
                        "category": "bold",
                        "help-command": "bold",
                        "help-group": "",
                        "help-group.focused": "fg:#8bd5ff bold",
                        "help-guide.border": "",
                        "help-guide.border.focused": "fg:#8bd5ff bold",
                        "help-guide.label": "bold",
                    }
                ),
            ]
        ),
    )
    app_ref["app"] = application
    try:
        return application.run(pre_run=on_ready)
    except (EOFError, KeyboardInterrupt):
        return None
