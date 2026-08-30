"""Interactive, operation-neutral waiting for one blocking command stage.

The semantic operation remains one frozen blocking unit. In a TTY it runs in
an executor so the foreground terminal can offer the shared read-only Help
inventory; outside a TTY the existing stable one-line progress contract is
preserved.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import sys
import threading
import time
from typing import AbstractSet, Protocol, TypeVar

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, HSplit, Layout, Window
from prompt_toolkit.layout.containers import DynamicContainer
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.widgets import Frame

from memcommit.adapters.console.terminal.components.background_turn import BackgroundExecutorTurn
from memcommit.adapters.console.terminal.components.progress import (
    BUSY_INTERVAL_SECONDS,
    CommandProgress,
    render_progress_line,
)
from memcommit.adapters.console.terminal.components.context_picker import (
    CONTEXT_PICKER_STYLE,
    ContextMemoryRow,
    ContextPickerNavigationUnit,
    context_memory_rows,
    context_option_continuation_prefixes,
    context_picker_navigation_units,
    memory_visibility_key_hint,
    render_context_options,
    render_context_roots,
)
from memcommit.application.capabilities.authority.context_access import (
    context_access_display_facts,
    resolve_context_access,
)
from memcommit.application.capabilities.authority.readable_contexts import (
    freeze_profile_readable_context_catalog,
)
from memcommit.adapters.console.terminal.components.session_help import (
    SessionHelpController,
    current_help_entries,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.adapters.console.terminal.components.scrollable_pane import (
    WrappedScrollbarMargin,
    build_scrollable_formatted_text_pane,
    move_wrapped_read_cursor,
    scroll_wrapped_page,
)
from memcommit.adapters.console.terminal.core.keybindings import (
    bind_case_insensitive_key,
)
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
)
from memcommit.core.context_targeting.tui.tree import (
    ContextTreeState,
    build_context_tree,
)
from memcommit.application.capabilities.authority.granted_context_navigation import (
    freeze_granted_context_navigation,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.source_projection.model import SourceDisplayFacts, SourceState
from memcommit.source_projection.presentation import (
    SourceDisplayValue,
    combine_source_display_tokens,
)
from memcommit.persistence.store import MemoryStore
from memcommit.persistence.command_ledger.study_actions import record_study_action


T = TypeVar("T")


class CommandWaitProgress(Protocol):
    """The real stage boundary exposed to one frozen blocking operation."""

    def update(self, stage: str, *, step: int) -> None: ...


@dataclass(frozen=True)
class CommandWaitView:
    """Frozen reviewed screen restored while a replacement turn runs.

    Initial analysis deliberately has no view: it stays on the shared one-line
    progress contract until a complete result exists. The waiting shell owns
    only read-only display and navigation for a previously completed report;
    callers own its semantic text and the visibly unincorporated review turn.
    """

    title: str
    text: str | StyleAndTextTuples
    frame_renderer: (
        Callable[[int], str | StyleAndTextTuples] | None
    ) = None

    def render(self, frame_index: int) -> str | StyleAndTextTuples:
        """Render one animation frame while preserving static-view callers."""

        if self.frame_renderer is None:
            return self.text
        return self.frame_renderer(frame_index)


@dataclass(frozen=True)
class CommandWaitContextBrowser:
    """One frozen Profile namespace inventory shown like ``mem switch``.

    The catalog and current marker are captured before background work starts.
    ``readable_names`` is the independent ordinary-load boundary; opaque Grant
    routes may remain visible outside it. Tree expansion and cursor movement
    remain process-local and cannot produce a switch receipt or change the
    global current Context.
    """

    names: tuple[str, ...]
    current_name: str | None
    annotations: Mapping[str, SourceDisplayValue]
    readable_names: frozenset[str]
    memory_loader: Callable[[str], Sequence[ContextMemoryRow]] | None = None

    @classmethod
    def create(
        cls,
        names: Sequence[str],
        *,
        current_name: str | None,
        annotations: Mapping[str, SourceDisplayValue] | None = None,
        readable_names: AbstractSet[str] | None = None,
        memory_loader: Callable[[str], Sequence[ContextMemoryRow]] | None = None,
    ) -> "CommandWaitContextBrowser":
        frozen_names = tuple(names)
        if not frozen_names or any(not name for name in frozen_names):
            raise ValueError("A command-wait Context browser requires names.")
        if len(set(frozen_names)) != len(frozen_names):
            raise ValueError("Command-wait Context browser names must be unique.")
        frozen_annotations = dict(annotations or {})
        if set(frozen_annotations) - set(frozen_names):
            raise ValueError("Context browser annotations are outside the catalog.")
        frozen_readable_names = frozenset(
            frozen_names if readable_names is None else readable_names
        )
        if not frozen_readable_names <= set(frozen_names):
            raise ValueError("Readable Context browser names are outside the catalog.")
        return cls(
            names=frozen_names,
            current_name=current_name,
            annotations=frozen_annotations,
            readable_names=frozen_readable_names,
            memory_loader=memory_loader,
        )


def _freeze_default_context_browser() -> CommandWaitContextBrowser | None:
    """Freeze readable Contexts plus visible opaque public Grant routes."""

    try:
        store = MemoryStore(create=False)
        local_names = tuple(store.list_context_names())
        if not local_names:
            return None
        current_name = store.current_context_name()
    except (OSError, RuntimeError, ValueError):
        return None

    local_browser = CommandWaitContextBrowser.create(
        local_names,
        current_name=current_name,
        memory_loader=lambda name: context_memory_rows(store.load(name)),
    )
    try:
        anchor_name = current_name or local_names[0]
        anchor_access = resolve_context_access(
            store,
            anchor_name,
            current_name=current_name,
            required_permission="READ",
        )
        catalog = freeze_profile_readable_context_catalog(
            store,
            anchor_access,
            include_query_routes=False,
        )
        readable_names = frozenset(catalog.list_context_names())
        granted_navigation = freeze_granted_context_navigation(store)
        names = tuple(sorted(readable_names | set(granted_navigation.names)))
        annotations = {
            name: context_access_display_facts(catalog.access_for(name))
            for name in readable_names
            if catalog.access_for(name).is_granted
        }
        for name in set(granted_navigation.names) - readable_names:
            # Opaque Grant roots belong in the namespace inventory, not in the
            # ordinary Context loader. UNAVAILABLE makes that independent
            # authority boundary explicit even when its permissions include
            # QUERY or another non-READ capability.
            annotations[name] = combine_source_display_tokens(
                granted_navigation.annotations[name],
                SourceDisplayFacts(states=(SourceState.UNAVAILABLE,)),
            )

        def load_context_memories(name: str) -> tuple[ContextMemoryRow, ...]:
            if name not in readable_names:
                raise ValueError("Opaque Grant routes cannot be opened as Contexts.")
            return context_memory_rows(catalog.load(name))

        return CommandWaitContextBrowser.create(
            names,
            current_name=current_name,
            annotations=annotations,
            readable_names=readable_names,
            memory_loader=load_context_memories,
        )
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ):
        # Isolated stores and stale Profile metadata can still expose their
        # ordinary local namespace, exactly as the local part of `mem switch`.
        # The optional browser must not fail or restart the frozen operation.
        return local_browser


class _InteractiveProgress:
    def __init__(
        self,
        operation: str,
        stage: str,
        *,
        step: int,
        total: int,
        started_at: float,
    ) -> None:
        self.operation = operation
        self._stage = stage
        self._step = step
        self.total = total
        self.started_at = started_at
        self._finished_at: float | None = None
        self._lock = threading.Lock()
        self._application: Application[None] | None = None
        render_progress_line(
            operation,
            stage,
            step=step,
            total=total,
            elapsed_seconds=0,
            frame_index=0,
        )

    def bind(self, application: Application[None]) -> None:
        self._application = application

    def update(self, stage: str, *, step: int) -> None:
        render_progress_line(
            self.operation,
            stage,
            step=step,
            total=self.total,
            elapsed_seconds=0,
            frame_index=0,
        )
        with self._lock:
            self._stage = stage
            self._step = step
        application = self._application
        if application is not None:
            application.invalidate()

    def mark_ready(self) -> None:
        """Freeze elapsed work time before optional continued Help browsing."""

        with self._lock:
            if self._finished_at is None:
                self._finished_at = time.monotonic()

    def render(self, *, frame_index: int) -> str:
        with self._lock:
            stage = self._stage
            step = self._step
            finished_at = self._finished_at
        return render_progress_line(
            self.operation,
            stage,
            step=step,
            total=self.total,
            elapsed_seconds=(
                finished_at if finished_at is not None else time.monotonic()
            )
            - self.started_at,
            frame_index=frame_index,
        )


def _study_help_action(action: str, command_name: str | None) -> None:
    detail = f"HELP {action}"
    if command_name is not None:
        detail += f" {command_name}"
    record_study_action(
        "TUI_ACTION",
        surface="command-wait",
        action=detail,
    )


def run_command_wait(
    operation: str,
    stage: str,
    *,
    total: int,
    work: Callable[[CommandWaitProgress], T],
    step: int = 1,
    help_entries: Sequence[object] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    interactive: bool | None = None,
    interval: float = BUSY_INTERVAL_SECONDS,
    on_help_action: Callable[[str, str | None], None] | None = None,
    return_view: CommandWaitView | None = None,
    context_view: CommandWaitView | None = None,
    context_browser: CommandWaitContextBrowser | None = None,
) -> T:
    """Run one blocking turn with inline progress or a prior-review wait UI.

    Initial analysis remains on the shared transient progress line because no
    result exists to review. A caller may supply ``return_view`` only when a
    completed report already exists and a submitted review turn is producing
    its replacement; that TTY path keeps the prior report and read-only Help
    available without restarting the frozen work.
    """

    # ``context_view`` is the long-standing API name for the operation-owned
    # confirmed-input copy. The user-facing key is now I/i; C/c belongs to the
    # separate switch-style Context namespace browser.
    input_view = context_view
    if input_view is not None and return_view is None:
        raise ValueError("A confirmed-input view requires a primary return view.")

    enabled = (
        sys.stdin.isatty() and sys.stdout.isatty()
        if interactive is None
        else interactive
    )
    if not enabled or return_view is None:
        with CommandProgress(
            operation,
            stage,
            total=total,
            step=step,
            enabled=True if enabled else None,
            interval=interval,
        ) as progress:
            return work(progress)

    frozen_help_entries = tuple(
        current_help_entries() if help_entries is None else help_entries
    )
    started_at = time.monotonic()
    progress = _InteractiveProgress(
        operation,
        stage,
        step=step,
        total=total,
        started_at=started_at,
    )
    background: BackgroundExecutorTurn[T] = BackgroundExecutorTurn(
        interval_seconds=interval
    )
    bindings = KeyBindings()
    result: dict[str, T] = {}
    error: dict[str, Exception] = {}
    ready = {"value": False}
    close_requested = {"value": False}
    status_message = {"value": ""}
    active_surface = {"value": "REPORT"}
    last_destination = {"surface": None, "origin": "REPORT"}

    def emit_help_action(action: str, command_name: str | None = None) -> None:
        _study_help_action(action, command_name)
        if on_help_action is not None:
            on_help_action(action, command_name)

    def help_status() -> str:
        if ready["value"]:
            return (
                f"MEM {operation.upper()} · "
                + ("ERROR READY" if error else "RESULT READY")
                + " · H / Q RETURN"
            )
        return progress.render(frame_index=background.frame)

    def wait_fragments() -> list[tuple[str, str]]:
        line = progress.render(frame_index=background.frame)
        fragments: list[tuple[str, str]] = [
            ("[SetCursorPosition]", ""),
            ("class:title", f"\n  {line}\n\n"),
            (
                "",
                "  This operation continues while the shared Help inventory "
                "is open.\n\n",
            ),
        ]
        if frozen_help_entries:
            fragments.append(
                (
                    "class:selected",
                    "  H / ?  REOPEN MEM HELP  ",
                )
            )
            fragments.append(("", "\n"))
        else:
            fragments.append(("", "  Help inventory unavailable.\n"))
        if status_message["value"]:
            fragments.append(
                (
                    "class:warning",
                    "\n  " + display_escape_text(status_message["value"]),
                )
            )
        return fragments

    return_pane = (
        build_scrollable_formatted_text_pane(
            return_view.title,
            return_view.render(0),
            height=Dimension(min=4, weight=1),
        )
        if return_view is not None
        else None
    )
    input_pane = (
        build_scrollable_formatted_text_pane(
            input_view.title,
            input_view.text,
            height=Dimension(min=4, weight=1),
        )
        if input_view is not None
        else None
    )
    frozen_context_browser = (
        context_browser
        if context_browser is not None
        else _freeze_default_context_browser()
        if return_pane is not None
        else None
    )
    context_tree_state: ContextTreeState | None = None
    context_control: FormattedTextControl | None = None
    context_container = None
    context_memory_cache: dict[str, tuple[ContextMemoryRow, ...]] = {}
    context_memory_anchor: tuple[str, int] | None = None
    if frozen_context_browser is not None:
        context_tree = build_context_tree(
            frozen_context_browser.names,
            materialized_names=frozen_context_browser.readable_names,
        )
        initial_name = (
            frozen_context_browser.current_name
            if frozen_context_browser.current_name in frozen_context_browser.names
            else frozen_context_browser.names[0]
        )
        context_tree_state = ContextTreeState.create(
            context_tree,
            selected=initial_name,
        )

        def visible_memory_contexts() -> frozenset[str]:
            assert context_tree_state is not None
            return frozenset(
                row.name
                for row in context_tree_state.visible_rows()
                if context_tree_state.memories_visible_for(row.name)
            )

        def load_visible_context_memories() -> None:
            assert context_tree_state is not None
            memory_loader = frozen_context_browser.memory_loader
            if memory_loader is None:
                return
            for row in context_tree_state.visible_rows():
                if (
                    not row.materialized
                    or not context_tree_state.memories_visible_for(row.name)
                    or row.name in context_memory_cache
                ):
                    continue
                try:
                    context_memory_cache[row.name] = tuple(memory_loader(row.name))
                except (OSError, RuntimeError, ValueError):
                    # This is a read-only aid, not a new authority boundary.
                    # A concurrent disappearance stays inside the browser.
                    context_memory_cache[row.name] = (
                        ContextMemoryRow("unavailable", "Memory preview changed"),
                    )

        def context_navigation_units() -> tuple[ContextPickerNavigationUnit, ...]:
            assert context_tree_state is not None
            return context_picker_navigation_units(
                context_tree_state.visible_rows(),
                memories_by_context=context_memory_cache,
                visible_memory_contexts=visible_memory_contexts(),
            )

        def current_context_navigation_unit() -> ContextPickerNavigationUnit:
            assert context_tree_state is not None
            units = context_navigation_units()
            if context_memory_anchor is not None:
                candidate = ContextPickerNavigationUnit(
                    "MEMORY",
                    context_memory_anchor[0],
                    context_memory_anchor[1],
                )
                if candidate in units:
                    return candidate
            return ContextPickerNavigationUnit(
                "CONTEXT",
                context_tree_state.selected_name,
            )

        def move_context_navigation(direction: int) -> None:
            nonlocal context_memory_anchor
            assert context_tree_state is not None
            units = context_navigation_units()
            current = current_context_navigation_unit()
            index = units.index(current)
            target = units[max(0, min(index + direction, len(units) - 1))]
            context_tree_state.selected_name = target.context_name
            context_memory_anchor = (
                (target.context_name, target.memory_index)
                if target.kind == "MEMORY" and target.memory_index is not None
                else None
            )

        def jump_context_navigation(to_end: bool) -> None:
            nonlocal context_memory_anchor
            assert context_tree_state is not None
            units = context_navigation_units()
            target = units[-1] if to_end else units[0]
            context_tree_state.selected_name = target.context_name
            context_memory_anchor = (
                (target.context_name, target.memory_index)
                if target.kind == "MEMORY" and target.memory_index is not None
                else None
            )

        def context_continuation_prefix(line_number: int, wrap_count: int):
            if wrap_count == 0:
                return ""
            assert context_tree_state is not None
            wrap_width = max(1, get_app().output.get_size().columns - 1)
            prefixes = context_option_continuation_prefixes(
                context_tree_state.visible_rows(),
                memories_by_context=context_memory_cache,
                visible_memory_contexts=visible_memory_contexts(),
                wrap_width=wrap_width,
            )
            return prefixes[line_number] if line_number < len(prefixes) else ""

        def render_context_browser() -> StyleAndTextTuples:
            assert context_tree_state is not None
            wrap_width = max(1, get_app().output.get_size().columns - 1)
            fragments: StyleAndTextTuples = [
                (
                    "class:report-neutral",
                    render_context_roots(context_tree) + "\n\n",
                )
            ]
            fragments.extend(
                render_context_options(
                    context_tree_state.visible_rows(),
                    selected=context_tree_state.selected_name,
                    current=frozen_context_browser.current_name,
                    annotations=frozen_context_browser.annotations,
                    memories_by_context=context_memory_cache,
                    visible_memory_contexts=visible_memory_contexts(),
                    wrap_width=wrap_width,
                    memory_anchor=context_memory_anchor,
                )
            )
            return fragments

        context_control = FormattedTextControl(
            render_context_browser,
            focusable=True,
            show_cursor=False,
        )
        context_container = Frame(
            Window(
                context_control,
                wrap_lines=True,
                get_line_prefix=context_continuation_prefix,
                right_margins=[WrappedScrollbarMargin(display_arrows=True)],
            ),
            title="CONTEXTS · SWITCH BROWSER · READ-ONLY · * CURRENT",
        )
    body_control = (
        return_pane.text_area
        if return_pane is not None
        else FormattedTextControl(
            wait_fragments,
            focusable=True,
            show_cursor=False,
        )
    )

    def return_from_help(application: Application) -> None:
        if ready["value"]:
            application.exit()
        else:
            application.invalidate()

    def help_unavailable(application: Application) -> None:
        if not frozen_help_entries:
            status_message["value"] = "Help inventory is unavailable here."
            application.invalidate()

    help_controller = SessionHelpController(
        entries=frozen_help_entries,
        app_input=app_input,
        app_output=app_output,
        title="mem help · explore while work continues",
        return_label="waiting",
        status_supplier=help_status,
        on_action=emit_help_action,
        on_closed=return_from_help,
        on_unavailable=help_unavailable,
    )
    help_controller.bind(bindings, additional_keys=("?",))

    def show_surface(event, requested_surface: str) -> None:
        origin = active_surface["value"]
        returning = (
            origin == requested_surface
            and last_destination["surface"] == requested_surface
        )
        surface = last_destination["origin"] if returning else requested_surface

        if surface == "CONTEXTS":
            if context_control is None:
                status_message["value"] = "Context browser is unavailable here."
                event.app.invalidate()
                return
            target = context_control
            open_action = "CONTEXT BROWSER OPEN"
        elif surface == "INPUTS":
            if input_pane is None:
                status_message["value"] = "Confirmed inputs are unavailable here."
                event.app.invalidate()
                return
            target = input_pane.text_area
            open_action = "CONFIRMED INPUTS OPEN"
        else:
            if return_pane is None:
                return
            target = return_pane.text_area
            open_action = "REPORT OPEN"

        if returning:
            action_prefix = {
                "CONTEXTS": "CONTEXT BROWSER",
                "INPUTS": "CONFIRMED INPUTS",
                "REPORT": "REPORT",
            }[requested_surface]
            action = f"{action_prefix} RETURN {surface}"
        else:
            last_destination["surface"] = requested_surface
            last_destination["origin"] = origin
            action = open_action
        status_message["value"] = ""
        active_surface["value"] = surface
        event.app.layout.focus(target)
        record_study_action(
            "TUI_ACTION",
            surface="command-wait",
            action=action,
        )
        event.app.invalidate()

    if return_pane is not None:

        if context_control is not None:

            @bind_case_insensitive_key(bindings, "c", eager=True)
            def _show_contexts(event) -> None:
                show_surface(event, "CONTEXTS")

        if input_pane is not None:

            @bind_case_insensitive_key(bindings, "i", eager=True)
            def _show_inputs(event) -> None:
                show_surface(event, "INPUTS")

        @bind_case_insensitive_key(bindings, "r", eager=True)
        def _show_report(event) -> None:
            show_surface(event, "REPORT")

    if context_tree_state is not None:

        @bindings.add("left")
        def _collapse_context(event) -> None:
            nonlocal context_memory_anchor
            if active_surface["value"] != "CONTEXTS":
                return
            if context_memory_anchor is not None:
                context_memory_anchor = None
            else:
                context_tree_state.collapse_selected(
                    include_leaf_memories=(
                        frozen_context_browser.memory_loader is not None
                    )
                )
            record_study_action(
                "TUI_ACTION",
                surface="command-wait",
                action="CONTEXT BROWSER COLLAPSE",
            )
            event.app.invalidate()

        @bindings.add("right")
        def _expand_context(event) -> None:
            if active_surface["value"] != "CONTEXTS":
                return
            if context_memory_anchor is not None:
                return
            context_tree_state.expand_selected(
                include_leaf_memories=(
                    frozen_context_browser.memory_loader is not None
                )
            )
            load_visible_context_memories()
            record_study_action(
                "TUI_ACTION",
                surface="command-wait",
                action="CONTEXT BROWSER EXPAND",
            )
            event.app.invalidate()

        @bindings.add("enter")
        def _toggle_context(event) -> None:
            if active_surface["value"] != "CONTEXTS":
                return
            if context_memory_anchor is not None:
                # Memory rows are viewport anchors only. In particular, Enter
                # cannot turn one into a switch or selection receipt.
                action = "CONTEXT BROWSER MEMORY PREVIEW"
            elif (
                not context_tree.children_by_name[context_tree_state.selected_name]
                and frozen_context_browser.memory_loader is not None
            ):
                context_tree_state.toggle_selected_memories()
                load_visible_context_memories()
                action = "CONTEXT BROWSER MEMORIES HERE"
            elif context_tree_state.selected_name in context_tree_state.expanded:
                context_tree_state.collapse_selected()
                action = "CONTEXT BROWSER COLLAPSE"
            else:
                context_tree_state.expand_selected()
                load_visible_context_memories()
                action = "CONTEXT BROWSER EXPAND"
            record_study_action(
                "TUI_ACTION",
                surface="command-wait",
                action=action,
            )
            event.app.invalidate()

        @bind_case_insensitive_key(bindings, "a", eager=True)
        def _toggle_all_contexts(event) -> None:
            nonlocal context_memory_anchor
            if active_surface["value"] != "CONTEXTS":
                return
            context_memory_anchor = None
            context_tree_state.toggle_expand_all()
            load_visible_context_memories()
            record_study_action(
                "TUI_ACTION",
                surface="command-wait",
                action="CONTEXT BROWSER TOGGLE ALL",
            )
            event.app.invalidate()

        @bindings.add("m", eager=True)
        def _toggle_selected_context_memories(event) -> None:
            nonlocal context_memory_anchor
            if active_surface["value"] != "CONTEXTS":
                return
            if frozen_context_browser.memory_loader is not None:
                context_tree_state.toggle_selected_memories()
                load_visible_context_memories()
                if not context_tree_state.memories_visible_for(
                    context_tree_state.selected_name
                ):
                    context_memory_anchor = None
            record_study_action(
                "TUI_ACTION",
                surface="command-wait",
                action="CONTEXT BROWSER MEMORIES HERE",
            )
            event.app.invalidate()

        @bindings.add("M", eager=True)
        def _toggle_all_context_memories(event) -> None:
            nonlocal context_memory_anchor
            if active_surface["value"] != "CONTEXTS":
                return
            if frozen_context_browser.memory_loader is not None:
                context_tree_state.toggle_memories()
                load_visible_context_memories()
                if not context_tree_state.memories_visible_for(
                    context_tree_state.selected_name
                ):
                    context_memory_anchor = None
            record_study_action(
                "TUI_ACTION",
                surface="command-wait",
                action="CONTEXT BROWSER MEMORIES ALL",
            )
            event.app.invalidate()

    if return_pane is not None:

        def record_return_view_action(action: str) -> None:
            record_study_action(
                "TUI_ACTION",
                surface="command-wait",
                action=f"RETURN VIEW {action}",
            )

        @bindings.add("up")
        def _scroll_return_view_up(event) -> None:
            if active_surface["value"] == "CONTEXTS":
                assert context_tree_state is not None
                move_context_navigation(-1)
                record_return_view_action("CONTEXT UP")
                event.app.invalidate()
                return
            move_wrapped_read_cursor(event, direction=-1)
            record_return_view_action("UP")

        @bindings.add("down")
        def _scroll_return_view_down(event) -> None:
            if active_surface["value"] == "CONTEXTS":
                assert context_tree_state is not None
                move_context_navigation(1)
                record_return_view_action("CONTEXT DOWN")
                event.app.invalidate()
                return
            move_wrapped_read_cursor(event, direction=1)
            record_return_view_action("DOWN")

        @bindings.add("pageup")
        def _page_return_view_up(event) -> None:
            if active_surface["value"] == "CONTEXTS":
                assert context_tree_state is not None
                for _ in range(10):
                    move_context_navigation(-1)
                record_return_view_action("CONTEXT PAGE UP")
                event.app.invalidate()
                return
            scroll_wrapped_page(event, direction=-1)
            record_return_view_action("PAGE UP")

        @bindings.add("pagedown")
        def _page_return_view_down(event) -> None:
            if active_surface["value"] == "CONTEXTS":
                assert context_tree_state is not None
                for _ in range(10):
                    move_context_navigation(1)
                record_return_view_action("CONTEXT PAGE DOWN")
                event.app.invalidate()
                return
            scroll_wrapped_page(event, direction=1)
            record_return_view_action("PAGE DOWN")

        @bindings.add("home")
        def _return_view_home(event) -> None:
            if active_surface["value"] == "CONTEXTS":
                assert context_tree_state is not None
                jump_context_navigation(False)
                record_return_view_action("CONTEXT HOME")
                event.app.invalidate()
                return
            event.current_buffer.cursor_position = 0
            record_return_view_action("HOME")

        @bindings.add("end")
        def _return_view_end(event) -> None:
            if active_surface["value"] == "CONTEXTS":
                assert context_tree_state is not None
                jump_context_navigation(True)
                record_return_view_action("CONTEXT END")
                event.app.invalidate()
                return
            event.current_buffer.cursor_position = len(event.current_buffer.text)
            record_return_view_action("END")

    def request_close(event) -> None:
        if background.request_close():
            close_requested["value"] = True
            status_message["value"] = (
                "Close requested; waiting for the current operation to finish."
            )
            record_study_action(
                "TUI_ACTION",
                surface="command-wait",
                action="CLOSE REQUESTED",
            )
            event.app.invalidate()
            return
        close_requested["value"] = True
        event.app.exit()

    @bind_case_insensitive_key(bindings, "q", eager=True)
    @bindings.add("c-c", eager=True)
    def _close(event) -> None:
        request_close(event)

    header = Window(
        FormattedTextControl(
            lambda: [("class:title", " " + help_status())]
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    if return_pane is not None:
        body = DynamicContainer(
            lambda: (
                context_container
                if active_surface["value"] == "CONTEXTS"
                and context_container is not None
                else input_pane.container
                if active_surface["value"] == "INPUTS" and input_pane is not None
                else return_pane.container
            )
        )
    else:
        body = Frame(Window(body_control), title="BACKGROUND WORK")

    def footer_text() -> str:
        if status_message["value"]:
            return " " + display_escape_text(status_message["value"])
        if return_pane is not None:
            help_hint = "H/h/? Help · " if frozen_help_entries else ""
            context_hint = (
                (
                    "C/c back · "
                    if active_surface["value"] == "CONTEXTS"
                    and last_destination["surface"] == "CONTEXTS"
                    and last_destination["origin"] != "CONTEXTS"
                    else "C/c Contexts · "
                )
                if frozen_context_browser is not None
                else ""
            )
            input_hint = (
                (
                    "I/i back · "
                    if active_surface["value"] == "INPUTS"
                    and last_destination["surface"] == "INPUTS"
                    and last_destination["origin"] != "INPUTS"
                    else "I/i inputs · "
                )
                if input_pane is not None
                else ""
            )
            report_hint = (
                "R/r back · "
                if active_surface["value"] == "REPORT"
                and last_destination["surface"] == "REPORT"
                and last_destination["origin"] != "REPORT"
                else "R/r report · "
            )
            if active_surface["value"] == "CONTEXTS":
                memory_hint = (
                    memory_visibility_key_hint(context_tree_state) + " · "
                    if frozen_context_browser is not None
                    and frozen_context_browser.memory_loader is not None
                    else ""
                )
                return (
                    f" {context_hint}{input_hint}{report_hint}{help_hint}"
                    f"{memory_hint}"
                    "↑/↓ move · ←/→ expand · Enter browse · "
                    "A/a all · "
                    "Q/q close · read-only"
                )
            return (
                f" {context_hint}{input_hint}{report_hint}{help_hint}↑/↓ scroll · "
                "PgUp/PgDn page · Home/End · "
                "Q/q request close · read-only"
            )
        return (
            " H/h/? Help · Q/q request close"
            if frozen_help_entries
            else " Q/q request close"
        )

    footer = Window(
        FormattedTextControl(footer_text),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    application: Application[None] = Application(
        layout=Layout(HSplit([header, body, footer]), focused_element=body_control),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles(
            [MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE, CONTEXT_PICKER_STYLE]
        ),
    )

    if (
        return_view is not None
        and return_view.frame_renderer is not None
        and return_pane is not None
    ):
        rendered_frame = {"value": 0}

        def refresh_animated_return_view(_application: Application) -> None:
            frame_index = background.frame
            if rendered_frame["value"] == frame_index:
                return
            return_pane.set_formatted_text(
                return_view.render(frame_index),
                anchor="preserve",
            )
            rendered_frame["value"] = frame_index

        application.before_render.add_handler(refresh_animated_return_view)

    progress.bind(application)

    def on_success(value: T) -> None:
        result["value"] = value
        progress.mark_ready()
        ready["value"] = True
        emit_help_action("RESULT_READY")

    def on_error(value: Exception) -> None:
        error["value"] = value
        progress.mark_ready()
        ready["value"] = True
        emit_help_action("ERROR_READY")

    def on_idle() -> None:
        if help_controller.is_open:
            application.invalidate()
        else:
            application.exit()

    def on_close() -> None:
        close_requested["value"] = True
        application.exit()

    def start_work() -> None:
        # A prior reviewed report remains the stable default surface. Initial
        # analysis never enters this full-screen path.
        background.start(
            application,
            work=lambda: work(progress),
            on_success=on_success,
            on_error=on_error,
            on_idle=on_idle,
            on_close=on_close,
        )

    try:
        application.run(pre_run=start_work)
    except (EOFError, KeyboardInterrupt):
        close_requested["value"] = True
    if close_requested["value"]:
        raise KeyboardInterrupt()
    if error:
        raise error["value"]
    return result["value"]
