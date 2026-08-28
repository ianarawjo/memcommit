"""Shared setup and compact read-only UI for semantic quality finders."""

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
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

from memcommit.adapters.console.shared.command_progress import CommandProgress
from memcommit.persistence.command_ledger.attempts import annotate_read_report_attempt
from memcommit.adapters.interfaces.tui.components.operation_launcher.location import (
    operation_launcher_orientation,
)
from memcommit.application.authority.access import (
    context_access_display_facts,
    resolve_context_access,
)
from memcommit.adapters.console.shared.readable_context_catalog import (
    freeze_profile_readable_context_catalog,
)
from memcommit.adapters.interfaces.tui.components.focus import (
    FocusSurface,
    SurfaceFocusController,
    SurfaceMoveResult,
    bind_surface_navigation,
)
from memcommit.adapters.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.adapters.interfaces.tui.components.frame import (
    TuiRegion,
    build_focused_frame,
    build_tui_frame,
)
from memcommit.adapters.interfaces.tui.core.keybindings import (
    bind_case_insensitive_key,
    dispatch_tui_back,
)
from memcommit.adapters.console.terminal import (
    require_interactive_terminal,
)
from memcommit.adapters.console.text import (
    safe_terminal_text,
)
from memcommit.adapters.interfaces.tui.workbenches.read_report import (
    ReadReportSelectTarget,
    choose_read_report_recent,
)
from memcommit.adapters.interfaces.tui.workbenches.findings import run_quality_find_browser
from memcommit.core.context import Context
from memcommit.core.context_targeting.tui.range_selection import (
    ContextRangeSelectionState,
)
from memcommit.core.context_targeting.tui.reach import render_context_reach
from memcommit.core.context_targeting.tui.selection import render_context_target_mode
from memcommit.core.context_targeting.tui.selector import (
    ContextSelectorControl,
    ContextSelectorView,
)
from memcommit.application.authority.derived_policy import authorize_combination
from memcommit.application.reviewing.quality.workbench import (
    QualityFindKind,
    QualityFindReport,
    QualityFindSourceFrame,
    QualityFindWorkbenchError,
    QualityFindWorkbenchSession,
    create_quality_find_workbench,
    quality_find_report_view,
)
from memcommit.application.reviewing.quality.handoff import (
    QualityFindingHandoff,
    quality_finding_handoff,
    quality_finding_handoffs,
)
from memcommit.application.operations.dedun.application import DEDUN_ELIGIBLE_RELATIONS
from memcommit.source_projection.presentation import SourceDisplayValue
from memcommit.persistence.store import MemoryStore
from memcommit.application.reviewing.read_report import (
    ReadReportError,
    ReadReportOperation,
    ReadReportTarget,
)
from memcommit.application.reviewing.read_report_recents import (
    read_report_recents,
    revalidate_read_report_recent,
)


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


def freeze_all_readable_quality_find_source(
    store: MemoryStore,
    *,
    current_name: str | None,
) -> QualityFindSourceFrame:
    """Freeze PROFILE as one exact direct-Memory quality-analysis frame."""

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
    accesses = tuple(catalog.access_for(name) for name in names)
    # A Profile-wide semantic frame derives from every frozen contributor.
    # READ grants therefore need the applicable DERIVE/COMBINE authority
    # before any Source is disclosed to a provider.
    authorize_combination(accesses)
    contexts = tuple(catalog.load_direct(name) for name in names)
    return QualityFindSourceFrame.create(
        contexts,
        context_names=names,
        target_names=(),
        selection_mode="MULTIPLE",
        include_descendants=False,
        profile_selected=True,
    )


QualityFindAnalyzer = Callable[[QualityFindSourceFrame], QualityFindReport]
QualitySetupKind = QualityFindKind | Literal["audit"]


def interactive_quality_find_available() -> bool:
    """Return whether a flagless command can open its terminal workbench."""

    return sys.stdin.isatty() and sys.stdout.isatty()


def _read_report_operation(
    kind: QualityFindKind,
    operation_name: ReadReportOperation | None = None,
) -> ReadReportOperation:
    if kind == "duplicates":
        default: ReadReportOperation = "dedun"
    elif kind == "ambiguities":
        default = "find-ambiguities"
    else:
        default = "find-conflicts"
    operation = default if operation_name is None else operation_name
    expected = (
        {"dedun", "find-redundancies"}
        if kind == "duplicates"
        else {f"find-{kind}"}
    )
    if operation not in expected:
        raise ValueError(
            f"Quality finder {kind!r} cannot publish {operation!r} report identity."
        )
    return operation


def _operation_label(
    kind: QualitySetupKind,
    operation_name: ReadReportOperation | None = None,
) -> str:
    if kind == "audit":
        if operation_name is not None:
            raise ValueError("Audit does not accept a quality-finder operation name.")
        return "AUDIT"
    if kind == "duplicates":
        operation = _read_report_operation(kind, operation_name)
        return "DEDUN" if operation == "dedun" else "FIND REDUNDANCIES"
    return f"FIND {kind.upper()}"


def annotate_quality_find_attempt(
    kind: QualityFindKind,
    source: QualityFindSourceFrame,
    *,
    operation_name: ReadReportOperation | None = None,
) -> None:
    """Record only the reviewed target/range identity, never report content."""

    annotate_read_report_attempt(
        ReadReportTarget(
            operation=_read_report_operation(kind, operation_name),
            context_names=source.context_names,
            target_names=source.target_names,
            selection_mode=source.selection_mode,
            ranges=("RECURSIVE",) if source.include_descendants else ("DIRECT",),
            profile_selected=source.profile_selected,
        )
    )


def choose_quality_find_setup(
    names: Sequence[str],
    *,
    current: str,
    kind: QualitySetupKind,
    operation_name: ReadReportOperation | None = None,
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
            f"Interactive {_operation_label(kind, operation_name).title()}",
            snapshot_hint="Pass --context NAME for one-shot terminal output.",
        )

    operation = _operation_label(kind, operation_name)
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
    regions = [TuiRegion(header), TuiRegion(target_frame)]
    if scope_frame is not None:
        regions.append(TuiRegion(scope_frame))
    regions.extend((TuiRegion(todo_frame), TuiRegion(footer)))
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
    handoff_handler: Callable[[QualityFindingHandoff], None] | None = None,
    duplicate_handoff_handler: (
        Callable[[tuple[QualityFindingHandoff, ...]], None] | None
    ) = None,
    operation_name: ReadReportOperation | None = None,
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

    conflict_handoff_available = (
        handoff_handler is not None
        and session.kind == "conflicts"
        and len(session.source.contexts) == 1
        and bool(session.report.findings)
    )
    duplicate_handoffs = eligible_duplicate_handoffs()
    duplicate_handoff_available = (
        duplicate_handoff_handler is not None and bool(duplicate_handoffs)
    )
    action = run_quality_find_browser(
        quality_find_report_view(
            session,
            source,
            operation_label=_operation_label(session.kind, operation_name),
            handoff_available=(
                conflict_handoff_available or duplicate_handoff_available
            ),
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
    if (
        session.kind != "conflicts"
        or handoff_handler is None
        or action.item_uid is None
    ):
        raise QualityFindWorkbenchError(
            "Quality finding handoff is unavailable in this adapter."
        )
    handoff_handler(quality_finding_handoff(session, action.item_uid))
    return session


def run_interactive_quality_find(
    store: MemoryStore,
    *,
    current_name: str | None,
    kind: QualityFindKind,
    analyze: QualityFindAnalyzer,
    handoff_handler: Callable[[QualityFindingHandoff], None] | None = None,
    duplicate_handoff_handler: (
        Callable[[tuple[QualityFindingHandoff, ...]], None] | None
    ) = None,
    operation_name: ReadReportOperation | None = None,
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
    operation = _read_report_operation(kind, operation_name)
    recents = read_report_recents(store, operation=operation)
    launch = choose_read_report_recent(
        recents,
        operation=operation,
        orientation=operation_launcher_orientation(store),
    )
    if isinstance(launch, ReadReportTarget):
        matching = next(
            (recent for recent in recents if recent.target == launch),
            None,
        )
        if matching is None:
            raise ReadReportError(
                "Quality Find launcher returned an unknown recent target."
            )
        target = revalidate_read_report_recent(store, matching)
        # A Profile recent records what was readable during the old run for
        # provenance only. PROFILE itself means all readable Contexts at this
        # invocation, so expand it against the newly frozen catalog. Ordinary
        # checked ranges remain exact and must not acquire new descendants.
        replay_context_names = names if target.profile_selected else target.context_names
        receipt = QualityFindSetupReceipt(
            target_names=target.target_names,
            context_names=replay_context_names,
            selection_mode=target.selection_mode,
            include_descendants=target.include_descendants,
            profile_selected=target.profile_selected,
        )
    elif isinstance(launch, ReadReportSelectTarget):
        receipt = choose_quality_find_setup(
            names,
            current=initial,
            kind=kind,
            operation_name=operation,
            annotations=annotations,
        )
    elif launch is None:
        return False
    else:
        raise ReadReportError("Quality Find launcher returned an invalid action.")
    if receipt is None:
        return False
    # Resolve every effective checked row through the same frozen catalog used
    # by setup. Descendant projection has already happened in the visible tree,
    # so execution must not apply a second hidden expansion.
    accesses = tuple(catalog.access_for(name) for name in receipt.context_names)
    if len(accesses) > 1:
        authorize_combination(accesses)
    contexts = tuple(catalog.load_direct(name) for name in receipt.context_names)
    source = QualityFindSourceFrame.create(
        contexts,
        context_names=receipt.context_names,
        target_names=receipt.target_names,
        selection_mode=receipt.selection_mode,
        include_descendants=receipt.include_descendants,
        profile_selected=receipt.profile_selected,
    )
    with CommandProgress(
        _operation_label(kind, operation),
        (
            f"analyzing {source.memory_count} direct memories across "
            f"{len(source.contexts)} contexts"
        ),
        total=1,
    ):
        report = analyze(source)
    annotate_quality_find_attempt(kind, source, operation_name=operation)
    session = create_quality_find_workbench(kind, source, report)
    run_quality_find_resolution_workbench(
        session,
        source,
        handoff_handler=handoff_handler,
        duplicate_handoff_handler=duplicate_handoff_handler,
        operation_name=operation,
    )
    return True
