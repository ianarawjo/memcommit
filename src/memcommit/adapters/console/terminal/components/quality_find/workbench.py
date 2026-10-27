"""Shared setup and compact read-only UI for semantic quality finders."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Dimension, FormattedTextControl, Layout, Window
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

from memcommit.adapters.console.terminal.components.focus.controller import (
    FocusSurface,
    SurfaceFocusController,
    SurfaceMoveResult,
    bind_surface_navigation,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.adapters.console.terminal.components.frame import (
    build_focused_frame,
    build_tui_frame,
)
from memcommit.adapters.console.terminal.core.keybindings import (
    bind_case_insensitive_key,
    dispatch_tui_back,
)
from memcommit.adapters.console.terminal.core.capabilities import (
    require_interactive_terminal,
)
from memcommit.adapters.console.terminal.core.text import (
    safe_terminal_text,
)
from memcommit.adapters.console.terminal.components.findings import (
    run_quality_find_browser,
)
from memcommit.models.context import Context
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.state.range_selection import (
    ContextRangeSelectionState,
)
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.state.reach import (
    render_context_reach,
)
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.state.selection import (
    render_context_target_mode,
)
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.existing_context_selector import (
    ContextSelectorControl,
    ContextSelectorView,
)
from memcommit.application.capabilities.memory_issue_analysis.source import (
    QualityFindSourceFrame,
)
from memcommit.application.capabilities.memory_issue_analysis.workbench import (
    QualityFindKind,
    QualityFindWorkbenchError,
    QualityFindWorkbenchSession,
    quality_find_report_view,
)
from memcommit.application.capabilities.memory_issue_analysis.handoff import (
    QualityFindingHandoff,
    quality_finding_handoffs,
)
from memcommit.application.operations.duplicates.dedun.application import (
    DEDUN_ELIGIBLE_RELATIONS,
)
from memcommit.source_projection.presentation import SourceDisplayValue


@dataclass(frozen=True)
class QualityFindSetupReceipt:
    """The exact visible Context set and range settings approved for execution."""

    target_names: tuple[str, ...]
    context_names: tuple[str, ...]
    selection_mode: Literal["SINGLE", "MULTIPLE"]
    include_descendants: bool
    profile_selected: bool = False

    def __post_init__(self) -> None:
        if (
            not self.context_names
            or len(set(self.context_names)) != len(self.context_names)
            or any(not isinstance(name, str) or not name for name in self.context_names)
            or len(set(self.target_names)) != len(self.target_names)
            or any(not isinstance(name, str) or not name for name in self.target_names)
            or not set(self.target_names) <= set(self.context_names)
            or (self.profile_selected and self.target_names)
            or (not self.profile_selected and not self.target_names)
            or (
                self.selection_mode == "SINGLE"
                and not self.profile_selected
                and len(self.target_names) != 1
            )
            or self.selection_mode not in {"SINGLE", "MULTIPLE"}
            or type(self.include_descendants) is not bool
            or type(self.profile_selected) is not bool
        ):
            raise ValueError("Quality Find setup requires a valid Context range.")

    @property
    def context_name(self) -> str:
        """Return the sole exact Context for fixed-cardinality Audit callers."""

        if len(self.context_names) != 1:
            raise ValueError("This Quality Find receipt contains multiple Contexts.")
        return self.context_names[0]


QualitySetupKind = QualityFindKind | Literal["audit"]


def _operation_label(kind: QualitySetupKind) -> str:
    if kind == "audit":
        return "AUDIT"
    if kind == "duplicates":
        return "DEDUN"
    return f"FIND {kind.upper()}"


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
    """Choose a frozen readable Context range and explicitly approve execution."""

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

    operation = _operation_label(kind)
    error_message = {"value": ""}
    bindings = KeyBindings()
    labels = dict(annotations or {})
    if set(labels) - set(catalog):
        raise ValueError("Quality Find annotations are outside the catalog.")

    # Durable Audit deliberately retains its existing one-direct-Context
    # contract. The three process-local finders expose the shared range family
    # and execute the exact visible checked set as one semantic frame.
    selector: ContextSelectorControl | None = None
    target_state: ContextRangeSelectionState | None = None
    scope_control: FormattedTextControl | None = None
    scope_frame = None
    scope_row = {"value": 0}
    if kind == "audit":
        selector = ContextSelectorControl(
            ContextSelectorView(
                names=catalog,
                selected=(current,),
                mode="SINGLE",
                label="SOURCE · ALL READABLE CONTEXTS · * CURRENT",
                current_context=current,
                annotations=tuple(labels.items()),
            ),
            height=min(9, max(3, len(catalog))),
        )
        target_control = selector.control
        target_frame = selector.frame
    else:
        target_state = ContextRangeSelectionState.create(
            catalog,
            current_name=current,
            initial_target=current,
            multiple=True,
            include_descendants=False,
        )

        def render_targets() -> list[tuple[str, str]]:
            assert target_state is not None
            return target_state.render_rows(
                focused=get_app().layout.has_focus(target_control),
                annotations=labels,
            )

        target_control = FormattedTextControl(
            render_targets,
            focusable=True,
            show_cursor=False,
        )
        target_frame = build_focused_frame(
            Window(
                target_control,
                wrap_lines=False,
                right_margins=[ScrollbarMargin(display_arrows=True)],
            ),
            title="TARGETS · PROFILE/CONTEXT · * CURRENT · ENTER/SPACE TO SELECT",
            is_focused=lambda: get_app().layout.has_focus(target_control),
            height=Dimension.exact(min(11, max(5, len(catalog) + 3))),
        )

        def render_scope() -> list[tuple[str, str]]:
            assert target_state is not None and scope_control is not None
            focused = get_app().layout.has_focus(scope_control)
            fragments = render_context_target_mode(
                target_state.target_mode,
                focused=focused and scope_row["value"] == 0,
            )
            fragments.append(("", "\n"))
            fragments.extend(
                render_context_reach(
                    target_state.reach,
                    title="CONTEXT RANGE",
                    focused=focused and scope_row["value"] == 1,
                )
            )
            return fragments

        scope_control = FormattedTextControl(
            render_scope,
            focusable=True,
            show_cursor=False,
        )
        scope_frame = build_focused_frame(
            Window(scope_control, height=Dimension.exact(2), wrap_lines=False),
            title="SCOPE",
            is_focused=lambda: get_app().layout.has_focus(scope_control),
            height=Dimension.exact(4),
        )

    def selected_context_names() -> tuple[str, ...]:
        if selector is not None:
            return (selector.selection.selected_name,)
        assert target_state is not None
        return target_state.effective_names

    def render_todo() -> list[tuple[str, str]]:
        focused = get_app().layout.has_focus(todo_control)
        selected = selected_context_names()
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
            else (
                f"Analyze direct Memories across {len(selected)} selected "
                f"{'Context' if len(selected) == 1 else 'Contexts'} as one frame."
                if selected
                else "Select at least one readable Context before running."
            )
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

    def render_header() -> str:
        if target_state is None:
            return f" MEM {operation} · SETUP\n ONE DIRECT CONTEXT"
        target_label = (
            "PROFILE"
            if target_state.profile_selected
            else (
                "MULTIPLE TARGETS"
                if target_state.target_mode.multiple
                else "SINGLE TARGET"
            )
        )
        reach = (
            "INCLUDE DESCENDANTS"
            if target_state.reach.include_descendants
            else "THIS CONTEXT ONLY"
        )
        return (
            f" MEM {operation} · SETUP\n {target_label} · {reach} · "
            f"{len(target_state.effective_names)} CONTEXT(S)"
        )

    header = Window(
        FormattedTextControl(render_header),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )

    def render_footer() -> str:
        if error_message["value"]:
            return f" {safe_terminal_text(error_message['value'])}"
        if get_app().layout.has_focus(todo_control):
            return " Enter run · ↑ setup · Tab/Shift-Tab pane · Esc/Q cancel"
        if scope_control is not None and get_app().layout.has_focus(scope_control):
            return " ↑/↓ setting/cross · ←/→ choose · Tab/Shift-Tab pane · Esc/Q cancel"
        tree = selector.tree if selector is not None else target_state.tree
        expansion = "A restore tree" if tree.all_expanded else "A expand all"
        return (
            " ↑/↓ move/cross · ←/→ collapse/expand · Enter/Space select · "
            f"{expansion} · Tab/Shift-Tab pane · Esc/Q cancel"
        )

    footer = Window(
        FormattedTextControl(render_footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    regions = [header, target_frame]
    if scope_frame is not None:
        regions.append(scope_frame)
    regions.extend((todo_frame, footer))
    root = build_tui_frame(*regions)
    app: Application[QualityFindSetupReceipt | None] = Application(
        layout=Layout(root, focused_element=target_control),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )

    def move_context(_event, delta: int) -> SurfaceMoveResult:
        if selector is not None:
            before = selector.tree.selected_name
            selector.move(delta)
            return "MOVED" if selector.tree.selected_name != before else "BOUNDARY"
        assert target_state is not None
        return "MOVED" if target_state.move_cursor(delta) else "BOUNDARY"

    def choose_context(_event) -> str:
        try:
            if selector is not None:
                selector.choose_cursor()
            else:
                assert target_state is not None
                target_state.toggle_cursor()
        except ValueError as error:
            error_message["value"] = str(error)
        else:
            error_message["value"] = ""
        return "HANDLED"

    def enter_context(delta: int) -> None:
        if selector is not None:
            rows = selector.tree.visible_rows()
            selector.tree.selected_name = rows[0 if delta > 0 else -1].name
        else:
            assert target_state is not None
            target_state.enter_from_boundary(delta)

    def move_scope(_event, delta: int) -> SurfaceMoveResult:
        previous = scope_row["value"]
        scope_row["value"] = max(0, min(previous + delta, 1))
        return "MOVED" if scope_row["value"] != previous else "BOUNDARY"

    def enter_scope(delta: int) -> None:
        scope_row["value"] = 0 if delta > 0 else 1

    def adjust_scope(delta: int) -> None:
        assert target_state is not None
        if scope_row["value"] == 0:
            target_state.move_target_mode(delta)
        else:
            target_state.move_reach(delta)
        error_message["value"] = ""

    def run_selected(event) -> str:
        effective = selected_context_names()
        if not effective:
            error_message["value"] = (
                "Select at least one readable Context before running."
            )
            event.app.invalidate()
            return "HANDLED"
        if selector is not None:
            receipt = QualityFindSetupReceipt(
                target_names=effective,
                context_names=effective,
                selection_mode="SINGLE",
                include_descendants=False,
            )
        else:
            assert target_state is not None
            receipt = QualityFindSetupReceipt(
                target_names=target_state.explicit_context_names,
                context_names=effective,
                selection_mode=(
                    "MULTIPLE" if target_state.target_mode.multiple else "SINGLE"
                ),
                include_descendants=target_state.reach.include_descendants,
                profile_selected=target_state.profile_selected,
            )
        event.app.exit(result=receipt)
        return "HANDLED"

    surface_values = [
        FocusSurface(
            "TARGETS",
            target_control,
            move_vertical=move_context,
            activate=choose_context,
            on_vertical_enter=enter_context,
        )
    ]
    if scope_control is not None:
        surface_values.append(
            FocusSurface(
                "SCOPE",
                scope_control,
                move_vertical=move_scope,
                activate=lambda _event: "HANDLED",
                on_vertical_enter=enter_scope,
            )
        )
    surface_values.append(
        FocusSurface(
            "TO_DO",
            todo_control,
            move_vertical=lambda _event, _delta: "BOUNDARY",
            activate=run_selected,
        )
    )
    surfaces = SurfaceFocusController(tuple(surface_values))
    bind_surface_navigation(bindings, surfaces)

    @bindings.add("left", filter=has_focus(target_control), eager=True)
    def _collapse(event) -> None:
        if selector is not None:
            selector.collapse()
        else:
            assert target_state is not None
            target_state.collapse_cursor()
        error_message["value"] = ""
        event.app.invalidate()

    @bindings.add("right", filter=has_focus(target_control), eager=True)
    def _expand(event) -> None:
        if selector is not None:
            selector.expand()
        else:
            assert target_state is not None
            target_state.expand_cursor()
        error_message["value"] = ""
        event.app.invalidate()

    @bindings.add(" ", filter=has_focus(target_control), eager=True)
    def _choose(event) -> None:
        choose_context(event)
        event.app.invalidate()

    @bind_case_insensitive_key(bindings, "a", filter=has_focus(target_control))
    def _toggle_expand_all(event) -> None:
        if selector is not None:
            selector.toggle_expand_all()
        else:
            assert target_state is not None
            target_state.toggle_expand_all()
        error_message["value"] = ""
        event.app.invalidate()

    if scope_control is not None:

        @bindings.add("left", filter=has_focus(scope_control), eager=True)
        def _scope_left(event) -> None:
            adjust_scope(-1)
            event.app.invalidate()

        @bindings.add("right", filter=has_focus(scope_control), eager=True)
        def _scope_right(event) -> None:
            adjust_scope(1)
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
    source: Context | QualityFindSourceFrame,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    duplicate_handoff_handler: (
        Callable[[tuple[QualityFindingHandoff, ...]], None] | None
    ) = None,
) -> QualityFindWorkbenchSession:
    """Inspect one process-local report without creating answer state."""

    def eligible_duplicate_handoffs() -> tuple[QualityFindingHandoff, ...]:
        if session.kind != "duplicates":
            return ()
        return tuple(
            handoff
            for handoff in quality_finding_handoffs(session)
            if handoff.classification in DEDUN_ELIGIBLE_RELATIONS
        )

    duplicate_handoffs = eligible_duplicate_handoffs()
    duplicate_handoff_available = duplicate_handoff_handler is not None and bool(
        duplicate_handoffs
    )
    action = run_quality_find_browser(
        quality_find_report_view(
            session,
            source,
            operation_label=_operation_label(session.kind),
            handoff_available=duplicate_handoff_available,
        ),
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if action.action == "CLOSE":
        return session
    if session.kind == "duplicates":
        if duplicate_handoff_handler is None or not duplicate_handoffs:
            raise QualityFindWorkbenchError(
                "Eligible redundancy evidence is unavailable in this adapter."
            )
        duplicate_handoff_handler(duplicate_handoffs)
        return session
    raise QualityFindWorkbenchError(
        "Quality finding handoff is unavailable in this adapter."
    )
