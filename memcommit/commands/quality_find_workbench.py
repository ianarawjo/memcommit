"""Shared setup and process-local review UI for semantic quality finders."""

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Dimension, FormattedTextControl, Layout, Window
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

from memcommit.commands.command_progress import CommandProgress
from memcommit.commands.granted_context import (
    context_access_display_facts,
    resolve_context_access,
)
from memcommit.commands.readable_context_catalog import (
    freeze_profile_readable_context_catalog,
)
from memcommit.commands.resolution_workbench_shell import (
    run_resolution_workbench_shell,
)
from memcommit.interfaces.tui.components.focus import (
    FocusSurface,
    SurfaceFocusController,
    SurfaceMoveResult,
    bind_surface_navigation,
)
from memcommit.interfaces.console.terminal import require_interactive_terminal
from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.interfaces.tui.components.frame import (
    TuiRegion,
    build_focused_frame,
    build_tui_frame,
)
from memcommit.interfaces.tui.core.keybindings import (
    bind_case_insensitive_key,
    dispatch_tui_back,
)
from memcommit.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.context import Context
from memcommit.context_targeting.tui.selector import (
    ContextSelectorControl,
    ContextSelectorView,
)
from memcommit.quality_find_workbench import (
    QualityFindKind,
    QualityFindReport,
    QualityFindWorkbenchError,
    QualityFindWorkbenchSession,
    create_quality_find_workbench,
    quality_find_resolution_view,
    validate_quality_find_response,
)
from memcommit.resolution_workbench import ResolutionNavigation
from memcommit.session_workbench_navigation import SessionWorkbenchNavigation
from memcommit.source_projection.presentation import SourceDisplayValue
from memcommit.store import MemoryStore


@dataclass(frozen=True)
class QualityFindSetupReceipt:
    """The exact readable Context approved for one quality-finder run."""

    context_name: str

    def __post_init__(self) -> None:
        if not isinstance(self.context_name, str) or not self.context_name.strip():
            raise ValueError("Quality Find setup requires a Context name.")


QualityFindAnalyzer = Callable[[Context], QualityFindReport]
QualitySetupKind = QualityFindKind | Literal["audit"]


def interactive_quality_find_available() -> bool:
    """Return whether a flagless command can open its terminal workbench."""

    return sys.stdin.isatty() and sys.stdout.isatty()


def _operation_label(kind: QualitySetupKind) -> str:
    return "AUDIT" if kind == "audit" else f"FIND {kind.upper()}"


def choose_quality_find_setup(
    names: Sequence[str],
    *,
    current: str,
    kind: QualitySetupKind,
    annotations: Mapping[str, SourceDisplayValue] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> QualityFindSetupReceipt | None:
    """Choose one exact Source and approve execution in a two-surface TUI."""

    catalog = tuple(names)
    if (
        not catalog
        or len(set(catalog)) != len(catalog)
        or any(not isinstance(name, str) or not name for name in catalog)
    ):
        raise ValueError("Quality Find requires a distinct readable catalog.")
    if current not in catalog:
        raise ValueError("Quality Find current Context is outside the catalog.")
    if kind not in {"duplicates", "ambiguities", "conflicts", "audit"}:
        raise ValueError("Unsupported quality finder kind.")
    if require_tty:
        require_interactive_terminal(
            f"Interactive {_operation_label(kind).title()}",
            snapshot_hint="Pass --context NAME for one-shot terminal output.",
        )

    selector = ContextSelectorControl(
        ContextSelectorView(
            names=catalog,
            selected=(current,),
            mode="SINGLE",
            label="SOURCE · ALL READABLE CONTEXTS · * CURRENT",
            current_context=current,
            annotations=tuple((annotations or {}).items()),
        ),
        height=min(9, max(3, len(catalog))),
    )
    operation = _operation_label(kind)
    error_message = {"value": ""}
    bindings = KeyBindings()

    def render_todo() -> list[tuple[str, str]]:
        focused = get_app().layout.has_focus(todo_control)
        selected = safe_terminal_text(selector.selection.selected_name)
        if focused:
            cursor = [("[SetCursorPosition]", "")]
        else:
            cursor = []
        style = "class:memcommit.choice.active.focused" if focused else ""
        pointer = "›" if focused else " "
        description = (
            "Run Duplicate, Ambiguity, and Conflict finders over the same "
            "frozen direct Source."
            if kind == "audit"
            else f"Analyze direct Memories in {selected}; Source unchanged."
        )
        return [
            *cursor,
            (style, f"{pointer} RUN {operation}\n"),
            ("", f"  {description}"),
        ]

    todo_control = FormattedTextControl(
        render_todo,
        focusable=True,
        show_cursor=False,
    )
    todo_frame = build_focused_frame(
        Window(todo_control, wrap_lines=True),
        title="TO DO · ENTER TO RUN",
        is_focused=lambda: get_app().layout.has_focus(todo_control),
        height=Dimension.exact(4),
    )

    header = Window(
        FormattedTextControl(
            f" MEM {operation} · SETUP\n ONE DIRECT CONTEXT · SOURCE UNCHANGED"
        ),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )

    def render_footer() -> str:
        if error_message["value"]:
            return f" {safe_terminal_text(error_message['value'])}"
        if get_app().layout.has_focus(todo_control):
            return " Enter run · ↑ Source · Tab/Shift-Tab pane · Esc/Q cancel"
        expansion = "A restore tree" if selector.tree.all_expanded else "A expand all"
        return (
            " ↑/↓ move/cross · ←/→ collapse/expand · Enter/Space select · "
            f"{expansion} · Tab/Shift-Tab pane · Esc/Q cancel"
        )

    footer = Window(
        FormattedTextControl(render_footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(selector.frame),
        TuiRegion(todo_frame),
        TuiRegion(footer),
    )
    app: Application[QualityFindSetupReceipt | None] = Application(
        layout=Layout(root, focused_element=selector.control),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )

    def move_context(_event, delta: int) -> SurfaceMoveResult:
        before = selector.tree.selected_name
        selector.move(delta)
        return "MOVED" if selector.tree.selected_name != before else "BOUNDARY"

    def choose_context(_event) -> str:
        try:
            selector.choose_cursor()
        except ValueError as error:
            error_message["value"] = str(error)
        else:
            error_message["value"] = ""
        return "HANDLED"

    def enter_context(delta: int) -> None:
        rows = selector.tree.visible_rows()
        selector.tree.selected_name = rows[0 if delta > 0 else -1].name

    def run_selected(event) -> str:
        event.app.exit(result=QualityFindSetupReceipt(selector.selection.selected_name))
        return "HANDLED"

    surfaces = SurfaceFocusController(
        (
            FocusSurface(
                "SOURCE",
                selector.control,
                move_vertical=move_context,
                activate=choose_context,
                on_vertical_enter=enter_context,
            ),
            FocusSurface(
                "TO_DO",
                todo_control,
                move_vertical=lambda _event, _delta: "BOUNDARY",
                activate=run_selected,
            ),
        )
    )
    bind_surface_navigation(bindings, surfaces)

    @bindings.add("left", filter=has_focus(selector.control), eager=True)
    def _collapse(event) -> None:
        selector.collapse()
        error_message["value"] = ""
        event.app.invalidate()

    @bindings.add("right", filter=has_focus(selector.control), eager=True)
    def _expand(event) -> None:
        selector.expand()
        error_message["value"] = ""
        event.app.invalidate()

    @bindings.add(" ", filter=has_focus(selector.control), eager=True)
    def _choose(event) -> None:
        choose_context(event)
        event.app.invalidate()

    @bind_case_insensitive_key(bindings, "a", filter=has_focus(selector.control))
    def _toggle_expand_all(event) -> None:
        selector.toggle_expand_all()
        error_message["value"] = ""
        event.app.invalidate()

    def close(event) -> None:
        event.app.exit(result=None)

    @bindings.add("escape", eager=True)
    @bindings.add("backspace", eager=True)
    def _back(event) -> None:
        dispatch_tui_back(event, close=close)

    @bindings.add("c-c", eager=True)
    @bind_case_insensitive_key(bindings, "q")
    def _cancel(event) -> None:
        close(event)

    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None


def run_quality_find_resolution_workbench(
    session: QualityFindWorkbenchSession,
    ctx: Context,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> QualityFindWorkbenchSession:
    """Inspect and answer one process-local report in the common workbench."""

    navigation = ResolutionNavigation()
    workbench_navigation = SessionWorkbenchNavigation()

    def load_draft(item_uid: str) -> tuple[str | None, str]:
        response = session.response_for(item_uid)
        return response.selected_option_uid, response.text

    def save_draft(item_uid: str, option_uid: str | None, text: str) -> None:
        validate_quality_find_response(text)
        item = quality_find_resolution_view(session, ctx).item(item_uid)
        if option_uid is not None:
            item.option(option_uid)
        response = session.response_for(item_uid)
        response.selected_option_uid = option_uid
        response.text = text

    while True:
        action = run_resolution_workbench_shell(
            lambda: quality_find_resolution_view(session, ctx),
            navigation=navigation,
            workbench_navigation=workbench_navigation,
            app_input=app_input,
            app_output=app_output,
            require_tty=require_tty,
            terminal_label=f"Interactive {_operation_label(session.kind).title()}",
            snapshot_hint="Pass --context NAME for one-shot terminal output.",
            draft_loader=load_draft,
            draft_saver=save_draft,
            response_validator=validate_quality_find_response,
            save_draft_on_close=True,
            split_viewer_items=True,
        )
        if action.kind == "CLOSE":
            return session
        if action.kind != "SUBMIT_ITEM" or action.item_uid is None:
            raise QualityFindWorkbenchError(
                f"Unsupported process-local Quality Find action '{action.kind}'."
            )
        save_draft(action.item_uid, action.option_uid, action.comment)


def run_interactive_quality_find(
    store: MemoryStore,
    *,
    current_name: str | None,
    kind: QualityFindKind,
    analyze: QualityFindAnalyzer,
) -> bool:
    """Select, analyze, and inspect one flagless quality-finder invocation."""

    access = resolve_context_access(
        store,
        None,
        current_name=current_name,
        required_permission="READ",
    )
    catalog = freeze_profile_readable_context_catalog(
        store,
        access,
        include_query_routes=False,
    )
    names = tuple(catalog.list_context_names())
    initial = access.display_name
    if initial not in names:
        raise RuntimeError("The current Context is outside the readable catalog.")
    annotations = {
        name: context_access_display_facts(catalog.access_for(name))
        for name in names
        if catalog.access_for(name).is_granted
    }
    receipt = choose_quality_find_setup(
        names,
        current=initial,
        kind=kind,
        annotations=annotations,
    )
    if receipt is None:
        return False
    # Resolve through the same frozen catalog used by the selector. A cursor
    # cannot smuggle a raw locator or a different Grant into execution.
    catalog.access_for(receipt.context_name)
    ctx = catalog.load_direct(receipt.context_name)
    with CommandProgress(
        _operation_label(kind),
        "analyzing direct memories",
        total=1,
    ):
        report = analyze(ctx)
    session = create_quality_find_workbench(kind, ctx, report)
    run_quality_find_resolution_workbench(session, ctx)
    return True
