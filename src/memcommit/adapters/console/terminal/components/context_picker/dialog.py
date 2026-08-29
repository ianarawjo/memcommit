"""Full-screen prompt-toolkit application for the terminal Context picker."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from typing import AbstractSet, Mapping, TypeVar

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.filters import Condition
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
from prompt_toolkit.output import Output

from memcommit.adapters.console.terminal.components.focus import (
    FocusSurface,
    SurfaceFocusController,
    bind_surface_navigation,
)
from memcommit.adapters.console.terminal.components.frame import (
    TuiRegion,
    build_focused_frame,
    build_tui_frame,
)
from memcommit.adapters.console.terminal.core.keybindings import (
    NavigationAccelerator,
    bind_case_insensitive_key,
)
from memcommit.adapters.console.terminal.components.scrollable_pane import (
    WrappedScrollbarMargin,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.adapters.console.terminal.components.plain_text_clipboard import (
    PlainTextClipboardReceipt,
    clipboard_failure_receipt,
    copy_plain_text,
)
from memcommit.core.context_targeting.tui.tree import (
    ContextTree,
    ContextTreeState,
    build_context_tree,
    expandable_context_subtree,
)
from memcommit.core.context_targeting.tui.reach import (
    ContextReachState,
    render_context_reach,
)
from memcommit.core.context_targeting.model import DirectMemoryTarget
from memcommit.source_projection.presentation import (
    SourceDisplayValue,
    normalize_source_display_tokens,
)
from memcommit.adapters.console.terminal.components.context_picker.model import (
    ContextMemoryRow,
    ContextMemorySelection,
    ContextPickerActionReceipt,
    ContextPickerNavigationUnit,
    ContextSubtreeSelection,
)
from memcommit.adapters.console.terminal.components.context_picker.preview import (
    context_picker_navigation_units,
)
from memcommit.adapters.console.terminal.components.context_picker.projection import (
    project_context_picker_clipboard,
)
from memcommit.adapters.console.terminal.components.context_picker.rendering import (
    _CONTEXT_NAVIGATION_HINT,
    _CONTEXT_PICKER_STYLE,
    context_option_continuation_prefixes,
    memory_visibility_key_hint,
    render_context_memory_detail,
    render_context_options,
    render_context_roots,
)


_NestedSelectionT = TypeVar("_NestedSelectionT")


def choose_context(
    names: Sequence[str],
    *,
    current: str | None,
    initial_target: str | DirectMemoryTarget | None = None,
    local_annotations: Mapping[str, SourceDisplayValue] | None = None,
    virtual_names: Sequence[str] = (),
    selectable_virtual_names: AbstractSet[str] = frozenset(),
    virtual_annotations: Mapping[str, SourceDisplayValue] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    clipboard_writer: Callable[[str], None] | None = None,
    require_tty: bool = True,
    title: str = "Select a Context",
    accept_label: str = "select",
    nested_accept_label: str | None = None,
    exit_label: str | None = None,
    memory_loader: Callable[[str], Sequence[ContextMemoryRow]] | None = None,
    browse_only: bool = False,
    initially_expand_selected: bool = False,
    initially_expand_all: bool = False,
    initially_expand_subtree_root: str | None = None,
    initially_show_memories: bool = False,
    initially_show_memory_contexts: AbstractSet[str] = frozenset(),
    tree_override: ContextTree | None = None,
    display_names: Mapping[str, str] | None = None,
    descendant_scope_names: AbstractSet[str] = frozenset(),
    selectable_memories: bool = False,
    nested_selection_factory: (Callable[[str, str], _NestedSelectionT] | None) = None,
    nested_accept_handler: (
        Callable[[str, str], ContextPickerActionReceipt] | None
    ) = None,
    context_accept_handler: (
        Callable[[str], ContextPickerActionReceipt] | None
    ) = None,
    memory_scope_root: str | None = None,
    memory_reach_state: ContextReachState | None = None,
) -> str | ContextSubtreeSelection | ContextMemorySelection | _NestedSelectionT | None:
    """Return one caller-authorized Context or exact nested-item receipt."""
    options = tuple(names)
    virtual = tuple(virtual_names)
    if not options:
        raise ValueError("No contexts are available to select.")
    if any(not isinstance(name, str) or not name for name in options) or len(
        set(options)
    ) != len(options):
        raise ValueError("Context selection received invalid names.")
    if (
        any(not isinstance(name, str) or not name for name in virtual)
        or len(set(virtual)) != len(virtual)
        or set(options).intersection(virtual)
    ):
        raise ValueError("Virtual Context selection received invalid names.")
    catalog = (*options, *virtual)
    local_labels = dict(local_annotations or {})
    annotations = {**local_labels, **dict(virtual_annotations or {})}
    selectable_virtual = frozenset(selectable_virtual_names)
    if not selectable_virtual <= set(virtual):
        raise ValueError("Selectable virtual Contexts are invalid.")
    if set(local_labels) - set(options):
        raise ValueError("Local Context annotations are invalid.")
    try:
        annotations_are_valid = all(
            bool(normalize_source_display_tokens(value))
            for value in annotations.values()
        )
    except (TypeError, ValueError):
        annotations_are_valid = False
    if set(virtual_annotations or {}) - set(virtual) or not annotations_are_valid:
        raise ValueError("Virtual Context annotations are invalid.")
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError(
            "Interactive context selection requires a terminal. "
            "Pass a Context name explicitly."
        )
    if selectable_memories and memory_loader is None:
        raise ValueError("Selectable Memories require a Memory loader.")
    if nested_selection_factory is not None and memory_loader is None:
        raise ValueError("Selectable nested items require an item loader.")
    if selectable_memories and nested_selection_factory is not None:
        raise ValueError(
            "Nested rows cannot return both Memory and operation selections."
        )
    if nested_accept_handler is not None and (
        not callable(nested_accept_handler)
        or memory_loader is None
        or nested_selection_factory is not None
    ):
        raise ValueError(
            "An in-place nested action requires an item loader and no "
            "selection factory."
        )
    if isinstance(initial_target, DirectMemoryTarget):
        if (
            memory_loader is None
            or initial_target.context_name
            not in (frozenset(options) | selectable_virtual)
        ):
            raise ValueError(
                "An initial direct-item target requires its Context in the catalog."
            )
        initial_context_name = initial_target.context_name
    elif initial_target is not None:
        if not isinstance(initial_target, str) or initial_target not in catalog:
            raise ValueError("The initial Context target is outside the catalog.")
        initial_context_name = initial_target
    else:
        initial_context_name = current if current in catalog else options[0]
    if (memory_scope_root is None) != (memory_reach_state is None):
        raise ValueError(
            "A scoped Memory picker requires both its root and reach state."
        )

    subtree_names = frozenset(descendant_scope_names)
    if not subtree_names <= set(catalog):
        raise ValueError("Descendant-scope Contexts are outside the catalog.")
    labels = dict(display_names or {})
    if set(labels) - set(catalog) or any(
        not isinstance(label, str) or not label for label in labels.values()
    ):
        raise ValueError("Context display names are invalid.")
    if memory_scope_root is not None and memory_scope_root not in catalog:
        raise ValueError("The Memory scope root is outside the Context catalog.")
    initial_memory_contexts = frozenset(initially_show_memory_contexts)
    materialized_names = frozenset(options) | selectable_virtual
    if not initial_memory_contexts <= materialized_names:
        raise ValueError("Initial Memory rows require materialized Contexts.")
    if initially_show_memories and initial_memory_contexts:
        raise ValueError(
            "Initial global and per-Context Memory display cannot both be requested."
        )
    if initially_expand_subtree_root is not None:
        if initially_expand_subtree_root not in catalog:
            raise ValueError("Initial expansion root is outside the Context catalog.")
        if initially_expand_all:
            raise ValueError(
                "Initial full-tree and subtree expansion cannot both be requested."
            )
    if (
        not isinstance(title, str)
        or not title.strip()
        or any(character in title for character in "\r\n")
        or not isinstance(accept_label, str)
        or not accept_label.strip()
        or any(character in accept_label for character in "\r\n")
        or (
            exit_label is not None
            and (
                not isinstance(exit_label, str)
                or not exit_label.strip()
                or any(character in exit_label for character in "\r\n")
            )
        )
        or (
            nested_accept_label is not None
            and (
                not isinstance(nested_accept_label, str)
                or not nested_accept_label.strip()
                or any(character in nested_accept_label for character in "\r\n")
            )
        )
    ):
        raise ValueError("Context selection labels must be nonempty single lines.")

    if tree_override is None:
        tree = build_context_tree(
            catalog,
            materialized_names=frozenset(options) | selectable_virtual,
        )
    else:
        tree = tree_override
        if (
            set(tree.parent_by_name) != set(catalog)
            or tree.materialized_names != frozenset(options) | selectable_virtual
        ):
            raise ValueError("Context tree override does not match its catalog.")
    state = ContextTreeState.create(
        tree,
        selected=initial_context_name,
    )
    if initially_expand_selected and state.selected_name in tree.expandable_names:
        state.expanded.add(state.selected_name)
    if initially_expand_all:
        state.expanded.update(tree.expandable_names)
        state.all_expanded = True
        state._before_expand_all = set()
    if initially_expand_subtree_root is not None:
        # Recursive operation scope may open one subtree while the surrounding
        # Profile remains visible for orientation. Expanding every Profile row
        # here would silently turn a selected scope into a global read surface.
        state.expanded.update(
            expandable_context_subtree(tree, initially_expand_subtree_root)
        )
    state.show_memories = initially_show_memories and memory_loader is not None
    if memory_loader is not None:
        state.memory_visibility_overrides.update(
            {name: True for name in initial_memory_contexts}
        )
    if isinstance(initial_target, DirectMemoryTarget):
        # An exact initial row is also an explicit request to reveal its local
        # Memory layer; callers need not coordinate a second visibility flag.
        state.memory_visibility_overrides[initial_target.context_name] = True
    memory_cache: dict[str, tuple[ContextMemoryRow, ...]] = {}
    memory_anchor: tuple[str, int] | None = None
    copy_status: PlainTextClipboardReceipt | None = None
    action_status: ContextPickerActionReceipt | None = None
    navigation_accelerator = NavigationAccelerator()
    nested_items_selectable = (
        selectable_memories
        or nested_selection_factory is not None
        or nested_accept_handler is not None
    )

    def memory_name_is_in_reach(name: str) -> bool:
        if memory_scope_root is None or memory_reach_state is None:
            return True
        return name == memory_scope_root or (
            memory_reach_state.include_descendants
            and name.startswith(memory_scope_root + "/")
        )

    def visible_memory_contexts() -> frozenset[str]:
        return frozenset(
            row.name
            for row in state.visible_rows()
            if state.memories_visible_for(row.name)
            and memory_name_is_in_reach(row.name)
        )

    def clear_footer_status() -> None:
        nonlocal action_status, copy_status
        action_status = None
        copy_status = None

    def load_visible_memories() -> None:
        if memory_loader is None:
            return
        for row in state.visible_rows():
            if (
                not row.materialized
                or not state.memories_visible_for(row.name)
                or not memory_name_is_in_reach(row.name)
                or row.name in memory_cache
            ):
                continue
            try:
                memory_cache[row.name] = tuple(memory_loader(row.name))
            except (OSError, RuntimeError, ValueError):
                # Navigation is a read-only aid. A concurrent disappearance
                # must not turn it into an authority or persistence boundary.
                memory_cache[row.name] = (
                    ContextMemoryRow("unavailable", "Memory preview changed"),
                )

    load_visible_memories()
    if isinstance(initial_target, DirectMemoryTarget):
        initial_rows = memory_cache.get(initial_target.context_name, ())
        initial_memory_index = next(
            (
                index
                for index, row in enumerate(initial_rows)
                if row.selector == initial_target.selector
            ),
            None,
        )
        if initial_memory_index is not None:
            # This is a focus hint, not a selection receipt. If the row changed
            # concurrently, retaining its Context is safer than targeting a
            # different item at the same index.
            memory_anchor = (
                initial_target.context_name,
                initial_memory_index,
            )
    # Expansion is deliberately process-local. Opening the picker must never
    # turn a navigation preference into Context, Profile, or current-state data.
    bindings = KeyBindings()

    def render_options():
        wrap_width = max(1, get_app().output.get_size().columns - 1)
        return render_context_options(
            state.visible_rows(),
            selected=state.selected_name,
            current=current,
            annotations=annotations,
            memories_by_context=memory_cache,
            visible_memory_contexts=visible_memory_contexts(),
            display_names=labels,
            wrap_width=wrap_width,
            memory_anchor=memory_anchor,
            selectable_memories=nested_items_selectable,
        )

    def navigation_units() -> tuple[ContextPickerNavigationUnit, ...]:
        return context_picker_navigation_units(
            state.visible_rows(),
            memories_by_context=memory_cache,
            visible_memory_contexts=visible_memory_contexts(),
        )

    def current_navigation_unit() -> ContextPickerNavigationUnit:
        units = navigation_units()
        if memory_anchor is not None:
            candidate = ContextPickerNavigationUnit(
                "MEMORY",
                memory_anchor[0],
                memory_anchor[1],
            )
            if candidate in units:
                return candidate
        return ContextPickerNavigationUnit("CONTEXT", state.selected_name)

    def focused_nested_row() -> ContextMemoryRow | None:
        if memory_anchor is None:
            return None
        context_name, memory_index = memory_anchor
        memories = memory_cache.get(context_name, ())
        if not 0 <= memory_index < len(memories):
            return None
        return memories[memory_index]

    def move_navigation_unit(direction: int) -> bool:
        nonlocal memory_anchor
        clear_footer_status()
        units = navigation_units()
        current = current_navigation_unit()
        index = units.index(current)
        target_index = max(0, min(index + direction, len(units) - 1))
        if target_index == index:
            return False
        target = units[target_index]
        state.selected_name = target.context_name
        memory_anchor = (
            (target.context_name, target.memory_index)
            if target.kind == "MEMORY" and target.memory_index is not None
            else None
        )
        return True

    def continuation_prefix(line_number: int, wrap_count: int):
        if wrap_count == 0:
            return ""
        wrap_width = max(1, get_app().output.get_size().columns - 1)
        prefixes = context_option_continuation_prefixes(
            state.visible_rows(),
            memories_by_context=memory_cache,
            visible_memory_contexts=visible_memory_contexts(),
            wrap_width=wrap_width,
        )
        return prefixes[line_number] if line_number < len(prefixes) else ""

    control = FormattedTextControl(
        text=render_options,
        focusable=True,
        show_cursor=False,
    )
    reach_control = (
        FormattedTextControl(
            lambda: render_context_reach(
                memory_reach_state,
                focused=get_app().layout.has_focus(reach_control),
                title="",
            ),
            focusable=True,
            show_cursor=False,
        )
        if memory_reach_state is not None
        else None
    )
    reach_focus = Condition(
        lambda: reach_control is not None and get_app().layout.has_focus(reach_control)
    )
    tree_focus = ~reach_focus
    focus_controller: SurfaceFocusController | None = None
    unframed_tree_focus = tree_focus & Condition(lambda: focus_controller is None)

    @bindings.add("down", filter=unframed_tree_focus)
    def _next_context(event) -> None:
        navigation_accelerator.move(
            1,
            app=event.app,
            move_one=move_navigation_unit,
        )

    @bindings.add("up", filter=unframed_tree_focus)
    def _previous_context(event) -> None:
        navigation_accelerator.move(
            -1,
            app=event.app,
            move_one=move_navigation_unit,
        )

    @bindings.add("right", filter=tree_focus)
    def _expand_or_enter_context(event) -> None:
        nonlocal memory_anchor
        navigation_accelerator.reset()
        clear_footer_status()
        if memory_anchor is not None:
            return
        state.expand_selected(include_leaf_memories=memory_loader is not None)
        load_visible_memories()
        event.app.invalidate()

    @bindings.add("left", filter=tree_focus)
    def _collapse_or_leave_context(event) -> None:
        nonlocal memory_anchor
        navigation_accelerator.reset()
        clear_footer_status()
        if memory_anchor is not None:
            memory_anchor = None
            event.app.invalidate()
            return
        state.collapse_selected(include_leaf_memories=memory_loader is not None)
        event.app.invalidate()

    @bindings.add("a", filter=tree_focus)
    @bindings.add("A", filter=tree_focus)
    def _toggle_expand_all(event) -> None:
        nonlocal memory_anchor
        navigation_accelerator.reset()
        clear_footer_status()
        memory_anchor = None
        state.toggle_expand_all()
        load_visible_memories()
        event.app.invalidate()

    @bindings.add("M", filter=tree_focus)
    def _toggle_memories(event) -> None:
        nonlocal memory_anchor
        navigation_accelerator.reset()
        clear_footer_status()
        if memory_loader is not None:
            state.toggle_memories()
            load_visible_memories()
            if not state.memories_visible_for(state.selected_name):
                memory_anchor = None
        event.app.invalidate()

    @bindings.add("m", filter=tree_focus)
    def _toggle_selected_memories(event) -> None:
        nonlocal memory_anchor
        navigation_accelerator.reset()
        clear_footer_status()
        if memory_loader is not None:
            state.toggle_selected_memories()
            load_visible_memories()
            if not state.memories_visible_for(state.selected_name):
                memory_anchor = None
        event.app.invalidate()

    def copy_focused(event, *, visible_branch: bool) -> None:
        nonlocal copy_status
        navigation_accelerator.reset()
        clear_footer_status()
        try:
            projection = project_context_picker_clipboard(
                state.visible_rows(),
                selected=state.selected_name,
                current=current,
                annotations=annotations,
                memories_by_context=(
                    memory_cache if memory_loader is not None else None
                ),
                visible_memory_contexts=visible_memory_contexts(),
                display_names=labels,
                memory_anchor=memory_anchor,
                visible_branch=visible_branch,
            )
        except ValueError as error:
            copy_status = clipboard_failure_receipt(error)
        else:
            if projection.scope == "VISIBLE_BRANCH":
                context_label = f"{projection.context_count} Context" + (
                    "s" if projection.context_count != 1 else ""
                )
                item_label = f"{projection.item_count} Item" + (
                    "" if projection.item_count == 1 else "s"
                )
                success_message = (
                    f"visible branch {projection.label} · "
                    f"{context_label} · {item_label}"
                )
            elif projection.memory_count:
                success_message = projection.label
            else:
                success_message = f"Context {projection.label}"
            # This is deliberately only the operating-system text clipboard.
            # A visible branch may combine local and granted rows, so it must
            # not fabricate the single-source typed stage used by `mem ls`.
            copy_status = copy_plain_text(
                projection.text,
                success_message=success_message,
                writer=clipboard_writer,
            )
        event.app.invalidate()

    @bindings.add("y", filter=tree_focus)
    def _copy_focused_item(event) -> None:
        copy_focused(event, visible_branch=False)

    @bindings.add("Y", filter=tree_focus)
    def _copy_focused_scope(event) -> None:
        copy_focused(event, visible_branch=True)

    @bindings.add("enter", filter=unframed_tree_focus)
    def _accept_context(event) -> None:
        nonlocal action_status, memory_anchor
        navigation_accelerator.reset()
        clear_footer_status()
        if memory_anchor is not None:
            if nested_items_selectable:
                context_name, memory_index = memory_anchor
                memory = memory_cache[context_name][memory_index]
                if memory.selector is not None:
                    if nested_accept_handler is not None:
                        receipt = nested_accept_handler(
                            context_name,
                            memory.selector,
                        )
                        if not isinstance(receipt, ContextPickerActionReceipt):
                            raise TypeError(
                                "A nested action must return a picker receipt."
                            )
                        action_status = receipt
                        assert memory_loader is not None
                        try:
                            refreshed_rows = tuple(memory_loader(context_name))
                        except (OSError, RuntimeError, ValueError):
                            refreshed_rows = (
                                ContextMemoryRow(
                                    "unavailable",
                                    "Memory preview changed",
                                ),
                            )
                        memory_cache[context_name] = refreshed_rows
                        state.selected_name = context_name
                        same_item_index = next(
                            (
                                index
                                for index, row in enumerate(refreshed_rows)
                                if row.selector == memory.selector
                            ),
                            None,
                        )
                        next_index = (
                            same_item_index
                            if same_item_index is not None
                            else (
                                min(memory_index, len(refreshed_rows) - 1)
                                if refreshed_rows
                                else None
                            )
                        )
                        memory_anchor = (
                            (context_name, next_index)
                            if next_index is not None
                            and refreshed_rows[next_index].selector is not None
                            else None
                        )
                        event.app.invalidate()
                        return
                    event.app.exit(
                        result=(
                            nested_selection_factory(
                                context_name,
                                memory.selector,
                            )
                            if nested_selection_factory is not None
                            else ContextMemorySelection(
                                context_name=context_name,
                                selector=memory.selector,
                            )
                        )
                    )
                    return
            # By default a Memory remains a viewport stop only. Enter never
            # changes selection or turns its parent into an implicit receipt.
            event.app.invalidate()
            return
        name = state.selected_name
        if context_accept_handler is not None:
            # Some consumers use Context rows strictly as navigation around
            # exact nested targets. Keep their rejection meaning in the
            # consumer while this shared surface owns the inline receipt.
            receipt = context_accept_handler(name)
            if not isinstance(receipt, ContextPickerActionReceipt):
                raise TypeError("A Context action must return a picker receipt.")
            action_status = receipt
            event.app.invalidate()
            return
        if name in subtree_names and name not in tree.materialized_names:
            # A catalog-only parent has no exact history of its own. Enter can
            # therefore open the frozen changed descendants without competing
            # with an exact-Context action; arrows retain tree expansion.
            event.app.exit(result=ContextSubtreeSelection(name))
            return
        if browse_only:
            if not tree.children_by_name[name] and memory_loader is not None:
                state.toggle_selected_memories()
                load_visible_memories()
            elif name in state.expanded:
                state.collapse_selected()
            else:
                state.expand_selected()
                load_visible_memories()
            event.app.invalidate()
            return
        if name in tree.materialized_names:
            event.app.exit(result=name)
            return
        if name in state.expanded:
            state.collapse_selected()
        else:
            state.expand_selected()
        event.app.invalidate()

    def set_memory_reach(include_descendants: bool, event) -> None:
        nonlocal memory_anchor
        if memory_reach_state is None:
            return
        memory_reach_state.choice.choose("SUBTREE" if include_descendants else "EXACT")
        if memory_anchor is not None and not memory_name_is_in_reach(memory_anchor[0]):
            memory_anchor = None
        load_visible_memories()
        clear_footer_status()
        event.app.invalidate()

    @bindings.add("left", filter=reach_focus, eager=True)
    def _exact_memory_reach(event) -> None:
        set_memory_reach(False, event)

    @bindings.add("right", filter=reach_focus, eager=True)
    def _descendant_memory_reach(event) -> None:
        set_memory_reach(True, event)

    @bindings.add(" ", filter=reach_focus, eager=True)
    def _toggle_memory_reach(event) -> None:
        if memory_reach_state is not None:
            set_memory_reach(not memory_reach_state.include_descendants, event)

    if reach_control is not None:

        def move_range_surface(event, direction):
            del event, direction
            return "BOUNDARY"

        def move_tree_surface(event, direction):
            units = navigation_units()
            index = units.index(current_navigation_unit())
            if (direction < 0 and index == 0) or (
                direction > 0 and index == len(units) - 1
            ):
                navigation_accelerator.reset()
                return "BOUNDARY"
            navigation_accelerator.move(
                direction,
                app=event.app,
                move_one=move_navigation_unit,
            )
            return "MOVED"

        def activate_range_surface(event):
            _toggle_memory_reach(event)
            return "HANDLED"

        def activate_tree_surface(event):
            _accept_context(event)
            return "HANDLED"

        focus_controller = SurfaceFocusController(
            (
                FocusSurface(
                    "range",
                    reach_control,
                    move_vertical=move_range_surface,
                    activate=activate_range_surface,
                ),
                FocusSurface(
                    "contexts-and-memories",
                    control,
                    move_vertical=move_tree_surface,
                    activate=activate_tree_surface,
                ),
            )
        )
        bind_surface_navigation(
            bindings,
            focus_controller,
            tab=True,
            vertical=True,
            activate=True,
        )

    @bind_case_insensitive_key(bindings, "q", eager=True)
    @bindings.add("escape")
    @bindings.add("c-c", eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=None)

    header = Window(
        FormattedTextControl(
            f" {display_escape_text(title)}\n"
            + render_context_roots(tree, display_names=labels)
        ),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )
    options_window = Window(
        control,
        wrap_lines=True,
        get_line_prefix=continuation_prefix,
        right_margins=[WrappedScrollbarMargin(display_arrows=True)],
    )
    detail_control = FormattedTextControl(
        lambda: render_context_memory_detail(focused_nested_row()),
        focusable=False,
        show_cursor=False,
    )
    detail_visible = Condition(
        lambda: bool(focused_nested_row() is not None and focused_nested_row().details)
    )
    detail_region = ConditionalContainer(
        HSplit(
            [
                Window(height=1, char="─", dont_extend_height=True),
                Window(
                    detail_control,
                    wrap_lines=True,
                    height=Dimension(min=3, max=9, preferred=7),
                    dont_extend_height=True,
                ),
            ]
        ),
        filter=detail_visible,
    )

    def render_footer():
        if reach_control is not None and get_app().layout.has_focus(reach_control):
            return (
                " RANGE · ← this Context only  → include descendants  "
                "Enter/Space toggle  ↓/Tab items  q cancel"
            )
        units = navigation_units()
        navigation_index = units.index(current_navigation_unit())
        expansion_action = "A restore tree" if state.all_expanded else "A expand all"
        name = state.selected_name
        if memory_anchor is not None:
            memory = memory_cache[memory_anchor[0]][memory_anchor[1]]
            enter_action = (
                "Enter " + display_escape_text(nested_accept_label or accept_label)
                if nested_items_selectable and memory.selector is not None
                else "Enter preview only"
            )
        elif context_accept_handler is not None:
            enter_action = "Enter unavailable"
        elif name in tree.materialized_names:
            enter_action = (
                "Enter open/collapse"
                if browse_only
                else f"Enter {display_escape_text(accept_label)}"
            )
        elif name in subtree_names:
            enter_action = "Enter open changed descendants"
        elif name in annotations:
            enter_action = "Enter unavailable"
        elif name in state.expanded:
            enter_action = "Enter collapse"
        else:
            enter_action = "Enter open"
        memory_action = ""
        if memory_loader is not None:
            memory_action = memory_visibility_key_hint(state) + "  "
        copy_action = (
            "y/Y copy item  "
            if memory_anchor is not None
            else "y copy Context  Y copy visible branch  "
        )
        close_action = (
            "Esc/q " + display_escape_text(exit_label)
            if exit_label is not None
            else ("q close" if browse_only else "q cancel")
        )
        catalog_label = (
            "Contexts"
            if context_accept_handler is not None
            else "selectable"
        )
        normal_footer = (
            _CONTEXT_NAVIGATION_HINT
            + f"{expansion_action}  {memory_action}{copy_action}"
            + f"{enter_action}  {close_action}"
            f" · {navigation_index + 1}/{len(units)}"
            f" · {len(tree.materialized_names)} {catalog_label}"
        )
        if action_status is not None:
            return [
                (
                    action_status.label_style,
                    " " + display_escape_text(action_status.label),
                ),
                (
                    action_status.detail_style,
                    " · "
                    + display_escape_text(action_status.detail),
                ),
                ("", f"  {close_action}"),
            ]
        if copy_status is None:
            return normal_footer
        return [
            (copy_status.style, " " + copy_status.message),
            ("", f"  {copy_action}{close_action}"),
        ]

    footer = Window(
        FormattedTextControl(render_footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    if reach_control is not None:
        reach_frame = build_focused_frame(
            Window(
                reach_control,
                height=Dimension.exact(1),
                dont_extend_height=True,
            ),
            title="RANGE",
            is_focused=lambda: get_app().layout.has_focus(reach_control),
            height=Dimension.exact(3),
        )
        targets_frame = build_focused_frame(
            options_window,
            title="CONTEXTS & MEMORIES",
            is_focused=lambda: get_app().layout.has_focus(control),
        )
        body = build_tui_frame(
            TuiRegion(header),
            TuiRegion(reach_frame),
            TuiRegion(targets_frame),
            TuiRegion(footer),
        )
    else:
        body = HSplit(
            [
                header,
                Window(height=1, char="─"),
                options_window,
                detail_region,
                Window(height=1, char="─", dont_extend_height=True),
                footer,
            ]
        )
    app: Application[
        str
        | ContextSubtreeSelection
        | ContextMemorySelection
        | _NestedSelectionT
        | None
    ] = Application(
        layout=Layout(
            body,
            focused_element=(reach_control or control),
        ),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        style=_CONTEXT_PICKER_STYLE,
    )
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None
