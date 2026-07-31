"""Shared list/detail/comment shell for semantic resolution adapters."""
from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.application import Application
from prompt_toolkit.filters import has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.utils import get_cwidth

from memcommit.commands.tui_primitives import (
    TuiRegion,
    build_framed_multiline_input,
    build_tui_frame,
    require_interactive_terminal,
    safe_terminal_text,
)
from memcommit.resolution_workbench import (
    ResolutionNavigation,
    ResolutionWorkbenchAction,
    ResolutionWorkbenchError,
    ResolutionWorkbenchView,
)


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


def resolution_workbench_fragments(
    view: ResolutionWorkbenchView,
    navigation: ResolutionNavigation,
) -> list[tuple[str, str]]:
    """Render one complete immutable adapter view with a visible cursor."""
    navigation.sync(view)
    metric_text = " · ".join(
        f"{safe_terminal_text(metric.value)} "
        f"{safe_terminal_text(metric.label)}"
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
    fragments.append(
        ("class:section", f" {safe_terminal_text(view.list_label)}\n")
    )
    if not view.items:
        fragments.append(
            ("", f"  {safe_terminal_text(view.empty_message)}\n")
        )
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
                    "       QUESTION · "
                    f"{safe_terminal_text(item.question)}\n",
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


def run_resolution_workbench_shell(
    view_or_supplier: (
        ResolutionWorkbenchView
        | Callable[[], ResolutionWorkbenchView]
    ),
    *,
    navigation: ResolutionNavigation | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    terminal_label: str = "Interactive resolution workbench",
    snapshot_hint: str = (
        "Run the same command outside a TTY to render its saved snapshot."
    ),
    draft_loader: (
        Callable[[str], tuple[str | None, str]] | None
    ) = None,
    draft_saver: (
        Callable[[str, str | None, str], None] | None
    ) = None,
    save_draft_on_close: bool = False,
    toggle_sort: Callable[[], None] | None = None,
) -> ResolutionWorkbenchAction:
    """Collect one UID-bound semantic or close action; never call a provider."""
    if require_tty:
        require_interactive_terminal(
            terminal_label,
            snapshot_hint=snapshot_hint,
        )
    current_navigation = navigation or ResolutionNavigation()
    supplier = (
        view_or_supplier
        if callable(view_or_supplier)
        else lambda: view_or_supplier
    )

    def current_view() -> ResolutionWorkbenchView:
        view = supplier()
        current_navigation.sync(view)
        return view

    bindings = KeyBindings()
    status = {"value": ""}
    global_comment = {"value": False}

    composer = build_framed_multiline_input(
        "MESSAGE",
        prompt="› ",
        buffer_name="resolution-message",
    )
    input_area = composer.text_area
    body_control = FormattedTextControl(
        lambda: resolution_workbench_fragments(
            current_view(),
            current_navigation,
        ),
        focusable=True,
        show_cursor=False,
    )
    body = Window(
        body_control,
        wrap_lines=True,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )

    def load_draft() -> None:
        item = current_navigation.current_item(current_view())
        if item is None:
            current_navigation.selected_option_uid = None
            input_area.text = ""
            return
        if draft_loader is None:
            selected_option_uid, comment = item.selected_option_uid, ""
        else:
            selected_option_uid, comment = draft_loader(item.uid)
            if selected_option_uid is not None:
                item.option(selected_option_uid)
        current_navigation.selected_option_uid = selected_option_uid
        input_area.text = comment
        input_area.buffer.cursor_position = len(comment)

    def save_draft() -> None:
        if draft_saver is None:
            return
        item = current_navigation.current_item(current_view())
        if item is None:
            return
        draft_saver(
            item.uid,
            current_navigation.selected_option_uid,
            input_area.text,
        )

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

    def submit(event) -> None:
        active_view = current_view()
        comment = input_area.text.strip()
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
        move(1)
        event.app.invalidate()

    @bindings.add("up", filter=~has_focus(input_area))
    def _up(event) -> None:
        move(-1)
        event.app.invalidate()

    @bindings.add("right", filter=~has_focus(input_area))
    def _right(event) -> None:
        save_draft()
        current_navigation.move_item(current_view(), 1)
        load_draft()
        event.app.invalidate()

    @bindings.add("left", filter=~has_focus(input_area))
    def _left(event) -> None:
        save_draft()
        current_navigation.move_item(current_view(), -1)
        load_draft()
        event.app.invalidate()

    @bindings.add("enter", filter=~has_focus(input_area))
    def _open_or_choose(event) -> None:
        active_view = current_view()
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
            event.app.layout.focus(body_control)
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
        composer.frame.title = "MESSAGE"
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
        composer.frame.title = "WHOLE-SET COMMENT"
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
        if (
            save_draft_on_close
            and not event.app.layout.has_focus(input_area)
        ):
            save_draft()
        event.app.exit(result=ResolutionWorkbenchAction(kind="CLOSE"))

    @bindings.add("escape", eager=True)
    def _back_or_close(event) -> None:
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
        if (
            item is not None
            and current_navigation.expanded_item_uid == item.uid
            and item.options
        ):
            navigation_help = (
                " ↑/↓ option  Enter choose/clear  Esc back  Tab comment "
            )
        elif current_navigation.expanded_item_uid is not None:
            navigation_help = " Enter close  Esc back  Tab comment "
        else:
            navigation_help = " ↑/↓ item  Enter detail  Tab comment "
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
        return navigation_help + "  ".join(actions) + " "

    footer = Window(
        FormattedTextControl(footer_text),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    root = build_tui_frame(
        TuiRegion(body),
        TuiRegion(composer.container),
        TuiRegion(footer),
    )
    application: Application[ResolutionWorkbenchAction] = Application(
        layout=Layout(root, focused_element=body_control),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
    )
    load_draft()
    try:
        return application.run()
    except (EOFError, KeyboardInterrupt):
        return ResolutionWorkbenchAction(kind="CLOSE")
