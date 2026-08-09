"""Interactive search, multi-target, and scope surface for ``mem find``."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from prompt_toolkit.application import Application
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.bindings.scroll import (
    scroll_page_down,
    scroll_page_up,
)
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import FormattedTextControl, HSplit, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.widgets import Frame, TextArea

from memcommit.commands.background_turn import BackgroundExecutorTurn
from memcommit.commands.command_progress import busy_suffix
from memcommit.context_targeting.tui.rendering import (
    ContextTreeRowDecoration,
    render_context_tree_rows,
)
from memcommit.context_targeting.tui.selection import (
    ContextSelectionState,
    ContextTargetModeState,
    render_context_target_mode,
)
from memcommit.context_targeting.tui.tree import (
    ContextTreeState,
    build_context_tree,
    context_subtree_names,
)
from memcommit.selection.tui import tree_choice_marker, tree_choice_styles
from memcommit.commands.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.commands.tui_primitives import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
    bind_focused_frame_style,
    require_interactive_terminal,
    safe_terminal_text,
)
from memcommit.commands.search_result_present import (
    SearchResultViewRow,
    render_grouped_search_results,
)


FindSearchMode = Literal["CURRENT", "HISTORY"]
FindSearchResultKind = Literal[
    "memory",
    "ref",
    "query",
    "artifact",
    "memory_version",
    "memory_transition",
    "checkpoint",
]
FindSearchRelevance = Literal["primary", "related"]


@dataclass(frozen=True)
class FindSearchRequest:
    """One exact process-local query and readable location scope."""

    query: str
    target_names: tuple[str, ...]
    include_descendants: bool = True
    follow_embeds: bool = True
    limit: int = 5

    def __post_init__(self) -> None:
        if not isinstance(self.query, str) or not self.query.strip():
            raise ValueError("Enter a nonblank Find query.")
        if (
            not self.target_names
            or any(not isinstance(name, str) or not name for name in self.target_names)
            or len(set(self.target_names)) != len(self.target_names)
        ):
            raise ValueError("Select at least one distinct readable Context.")
        if not isinstance(self.include_descendants, bool) or not isinstance(
            self.follow_embeds, bool
        ):
            raise ValueError("Find scope choices must be explicit booleans.")
        if isinstance(self.limit, bool) or not 1 <= self.limit <= 20:
            raise ValueError("Find limit must be between 1 and 20.")


@dataclass(frozen=True)
class FindSearchResult:
    """One host-resolved row rendered below the frozen search controls."""

    context_name: str
    kind: FindSearchResultKind
    uid: str
    content: str
    relevance: FindSearchRelevance = "primary"

    def __post_init__(self) -> None:
        if not isinstance(self.context_name, str) or not self.context_name.strip():
            raise ValueError("Find results require a Context name.")
        if self.kind not in {
            "memory",
            "ref",
            "query",
            "artifact",
            "memory_version",
            "memory_transition",
            "checkpoint",
        }:
            raise ValueError("Find returned an unsupported result kind.")
        if not isinstance(self.uid, str) or not self.uid.strip():
            raise ValueError("Find results require a local identity.")
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("Find results require nonblank content.")
        if self.relevance not in {"primary", "related"}:
            raise ValueError("Find returned invalid relevance.")


@dataclass(frozen=True)
class FindSearchResponse:
    """Results tied to the exact request that produced them."""

    request: FindSearchRequest
    mode: FindSearchMode
    results: tuple[FindSearchResult, ...]
    related_query: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.request, FindSearchRequest):
            raise ValueError("Find responses require the frozen request.")
        if self.mode not in {"CURRENT", "HISTORY"}:
            raise ValueError("Find returned an invalid search mode.")
        if not isinstance(self.results, tuple) or any(
            not isinstance(result, FindSearchResult) for result in self.results
        ):
            raise ValueError("Find returned invalid result rows.")
        if not isinstance(self.related_query, str):
            raise ValueError("Find returned an invalid broader query.")
        related = [result for result in self.results if result.relevance == "related"]
        primary = [result for result in self.results if result.relevance == "primary"]
        if related and (primary or not self.related_query.strip()):
            raise ValueError("Related Find results require one separate broader query.")
        if not related and self.related_query:
            raise ValueError("A broader Find query requires related results.")


@dataclass(frozen=True)
class FindSearchWorkbenchResult:
    """The last committed read-only result when the workbench closes."""

    status: Literal["CLOSED"]
    response: FindSearchResponse | None = None


FindSearchRunner = Callable[[FindSearchRequest], FindSearchResponse]


def render_find_search_results(response: FindSearchResponse | None) -> str:
    """Render only rows whose request still matches the visible controls."""

    if response is None:
        return "SEARCH RESULTS\n  Enter a query to search the selected scope."
    rows = tuple(
        SearchResultViewRow(
            context_name=result.context_name,
            label=(
                f"[{index} "
                f"{'related ' if result.relevance == 'related' else ''}"
                f"{result.kind} {result.uid[:8]}]"
            ),
            content=result.content,
        )
        for index, result in enumerate(response.results, start=1)
    )
    return render_grouped_search_results(
        rows,
        related_query=response.related_query,
    )


def _scope_summary(
    *,
    target_count: int,
    follow_embeds: bool,
) -> str:
    embeds = "FOLLOW EMBEDS" if follow_embeds else "EXCLUDE EMBEDS"
    return f"EXACT CHECKED TARGETS {target_count} · {embeds}"


def run_find_search_workbench(
    names: Sequence[str],
    *,
    current: str,
    initial_target: str,
    initial_include_descendants: bool,
    initial_follow_embeds: bool,
    limit: int,
    run_search: FindSearchRunner,
    annotations: Mapping[str, str] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> FindSearchWorkbenchResult:
    """Search repeatedly while keeping query, targets, scope, and results visible."""

    catalog = tuple(names)
    if (
        not catalog
        or len(set(catalog)) != len(catalog)
        or any(not isinstance(name, str) or not name for name in catalog)
    ):
        raise ValueError("Find requires a distinct readable Context catalog.")
    if current not in catalog or initial_target not in catalog:
        raise ValueError("Find's initial Context is outside the readable catalog.")
    if not callable(run_search):
        raise ValueError("Find requires a search controller.")
    if require_tty:
        require_interactive_terminal(
            "Interactive Find",
            snapshot_hint='Pass a query, for example: mem find "parking".',
        )

    labels = dict(annotations or {})
    if set(labels) - set(catalog):
        raise ValueError("Find Context annotations are outside the catalog.")

    tree = build_context_tree(catalog)
    tree_state = ContextTreeState.create(tree, selected=initial_target)
    initial_group = context_subtree_names(tree, initial_target)
    initial_checked = (
        tuple(name for name in initial_group if name != initial_target)
        + (initial_target,)
        if initial_include_descendants
        else (initial_target,)
    )
    target_selection = ContextSelectionState.create(
        catalog,
        selected=initial_checked,
        # Multiple remains the initial mode so the existing fast path—Tab to
        # Targets and check peers—does not acquire a setup detour.
        mode="MULTIPLE",
    )
    target_mode = ContextTargetModeState.create(multiple=True)
    embed_choice = HorizontalChoiceState(
        (
            HorizontalChoiceOption("EXCLUDE", "EXCLUDE"),
            HorizontalChoiceOption("FOLLOW", "FOLLOW"),
        ),
        selected_uid="FOLLOW" if initial_follow_embeds else "EXCLUDE",
    )
    scope_row = {"value": 0}
    response: FindSearchResponse | None = None
    status = {"value": "READY · ENTER A QUERY"}
    background_turn: BackgroundExecutorTurn[FindSearchResponse] = (
        BackgroundExecutorTurn()
    )

    bindings = KeyBindings()
    search_area = TextArea(
        multiline=False,
        prompt="› ",
        wrap_lines=False,
        height=Dimension.exact(1),
        read_only=Condition(lambda: background_turn.busy),
        name="find-search-query",
    )

    def render_targets() -> list[tuple[str, str]]:
        focused = app.layout.has_focus(target_control)

        def decorate(row, cursor: bool) -> ContextTreeRowDecoration:
            chosen = row.name in target_selection.selected_set
            cursor_style, value_style = tree_choice_styles(
                cursor=cursor,
                selected=chosen,
                focused=focused,
            )
            return ContextTreeRowDecoration(
                marker=tree_choice_marker(selected=chosen),
                active="*" if row.name == current else " ",
                annotation=labels.get(row.name, ""),
                cursor_style=cursor_style,
                value_style=value_style,
            )

        return render_context_tree_rows(tree_state, decorate)

    target_control = FormattedTextControl(
        render_targets,
        focusable=True,
        show_cursor=False,
    )
    target_window = Window(
        target_control,
        wrap_lines=False,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )

    def render_scope() -> list[tuple[str, str]]:
        focused = app.layout.has_focus(scope_control)
        fragments = render_context_target_mode(
            target_mode,
            focused=focused and scope_row["value"] == 0,
        )
        fragments.append(("", "\n"))
        fragments.extend(
            render_horizontal_choice(
                embed_choice,
                title="EMBEDDED CONTEXTS",
                focused=focused and scope_row["value"] == 1,
            )
        )
        return fragments

    scope_control = FormattedTextControl(
        render_scope,
        focusable=True,
        show_cursor=False,
    )
    results_area = TextArea(
        text=render_find_search_results(None),
        multiline=True,
        read_only=True,
        focusable=True,
        wrap_lines=True,
        scrollbar=True,
        name="find-search-results",
    )
    results_control = results_area.control

    def render_header() -> str:
        summary = _scope_summary(
            target_count=len(target_selection.selected_names),
            follow_embeds=embed_choice.selected_uid == "FOLLOW",
        )
        mode = response.mode if response is not None else "AUTO FROM QUERY"
        return f" MEM FIND · INTERACTIVE · {mode}\n {summary}"

    header = Window(
        FormattedTextControl(render_header),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )
    search_frame = Frame(
        search_area,
        title="SEARCH · ENTER TO RUN",
        height=Dimension.exact(3),
    )
    target_frame = Frame(
        target_window,
        title="TARGETS · * CURRENT · ENTER/SPACE TO SELECT",
        height=Dimension(min=5, preferred=8, max=12, weight=1),
    )
    scope_frame = Frame(
        Window(scope_control, height=Dimension.exact(2), wrap_lines=False),
        title="SCOPE",
        height=Dimension.exact(4),
    )
    results_frame = Frame(
        results_area,
        title="RESULTS",
        height=Dimension(min=5, weight=2),
    )

    def render_footer() -> str:
        if background_turn.busy:
            return (
                f" SEARCHING {busy_suffix(background_turn.frame)} · "
                "scope frozen · Ctrl-C closes after search"
            )
        hint = (
            "Enter search · Tab/Shift-Tab panes · Ctrl-C close"
            if app.layout.has_focus(search_area)
            else ("Enter/Space target · ←/→ scope/tree · / returns to search · Q close")
        )
        return f" {safe_terminal_text(status['value'])} · {hint}"

    footer = Window(
        FormattedTextControl(render_footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    root = HSplit(
        [
            header,
            search_frame,
            target_frame,
            scope_frame,
            results_frame,
            footer,
        ]
    )
    app: Application[FindSearchWorkbenchResult] = Application(
        layout=Layout(root, focused_element=search_area),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )
    controls = (search_area, target_control, scope_control, results_control)

    bind_focused_frame_style(
        search_frame,
        is_focused=lambda: app.layout.has_focus(search_area),
    )
    bind_focused_frame_style(
        target_frame,
        is_focused=lambda: app.layout.has_focus(target_control),
    )
    bind_focused_frame_style(
        scope_frame,
        is_focused=lambda: app.layout.has_focus(scope_control),
    )
    bind_focused_frame_style(
        results_frame,
        is_focused=lambda: app.layout.has_focus(results_control),
    )

    def clear_results(message: str) -> None:
        nonlocal response
        response = None
        status["value"] = message
        text = render_find_search_results(None)
        results_area.buffer.set_document(
            Document(text, cursor_position=0),
            bypass_readonly=True,
        )

    def query_changed(_buffer) -> None:
        if response is None or background_turn.busy:
            return
        clear_results("QUERY CHANGED · PRESS ENTER TO SEARCH")
        app.invalidate()

    search_area.buffer.on_text_changed += query_changed

    @bindings.add("tab", eager=True)
    def _next_pane(event) -> None:
        index = next(
            index
            for index, control in enumerate(controls)
            if event.app.layout.has_focus(control)
        )
        event.app.layout.focus(controls[(index + 1) % len(controls)])
        event.app.invalidate()

    @bindings.add("s-tab", eager=True)
    def _previous_pane(event) -> None:
        index = next(
            index
            for index, control in enumerate(controls)
            if event.app.layout.has_focus(control)
        )
        event.app.layout.focus(controls[(index - 1) % len(controls)])
        event.app.invalidate()

    @bindings.add("down", filter=has_focus(target_control), eager=True)
    def _target_down(event) -> None:
        tree_state.move(1)
        event.app.invalidate()

    @bindings.add("up", filter=has_focus(target_control), eager=True)
    def _target_up(event) -> None:
        tree_state.move(-1)
        event.app.invalidate()

    @bindings.add("right", filter=has_focus(target_control), eager=True)
    def _target_right(event) -> None:
        tree_state.expand_selected()
        event.app.invalidate()

    @bindings.add("left", filter=has_focus(target_control), eager=True)
    def _target_left(event) -> None:
        tree_state.collapse_selected()
        event.app.invalidate()

    @bindings.add("a", filter=has_focus(target_control), eager=True)
    @bindings.add("A", filter=has_focus(target_control), eager=True)
    def _target_expand_all(event) -> None:
        tree_state.toggle_expand_all()
        event.app.invalidate()

    @bindings.add(" ", filter=has_focus(target_control), eager=True)
    @bindings.add("enter", filter=has_focus(target_control), eager=True)
    def _toggle_target(event) -> None:
        if background_turn.busy:
            status["value"] = "Wait for the current search before changing scope."
        else:
            name = tree_state.selected_name
            try:
                changed = target_selection.toggle_group(
                    context_subtree_names(tree, name),
                    anchor_name=name,
                )
            except ValueError as error:
                status["value"] = str(error)
            else:
                if changed:
                    clear_results("TARGETS CHANGED · PRESS ENTER TO SEARCH")
                else:
                    status["value"] = "TARGET ALREADY SELECTED"
        event.app.invalidate()

    @bindings.add("down", filter=has_focus(scope_control), eager=True)
    def _scope_down(event) -> None:
        scope_row["value"] = min(1, scope_row["value"] + 1)
        event.app.invalidate()

    @bindings.add("up", filter=has_focus(scope_control), eager=True)
    def _scope_up(event) -> None:
        scope_row["value"] = max(0, scope_row["value"] - 1)
        event.app.invalidate()

    def move_scope(delta: int) -> None:
        if background_turn.busy:
            status["value"] = "Wait for the current search before changing scope."
            return
        row = scope_row["value"]
        if row == 0:
            if not target_mode.move(delta):
                return
            selection_changed = target_selection.set_multiple(
                target_mode.multiple,
                fallback_name=tree_state.selected_name,
            )
            if selection_changed:
                clear_results("TARGETS CHANGED · PRESS ENTER TO SEARCH")
            else:
                status["value"] = (
                    "MULTIPLE TARGET SELECTION"
                    if target_mode.multiple
                    else "SINGLE TARGET SELECTION"
                )
            return
        if embed_choice.move(delta):
            clear_results("SCOPE CHANGED · PRESS ENTER TO SEARCH")

    @bindings.add("right", filter=has_focus(scope_control), eager=True)
    def _scope_right(event) -> None:
        move_scope(1)
        event.app.invalidate()

    @bindings.add("left", filter=has_focus(scope_control), eager=True)
    def _scope_left(event) -> None:
        move_scope(-1)
        event.app.invalidate()

    @bindings.add("down", filter=has_focus(results_control), eager=True)
    def _result_down(event) -> None:
        results_area.buffer.cursor_down()
        event.app.invalidate()

    @bindings.add("up", filter=has_focus(results_control), eager=True)
    def _result_up(event) -> None:
        results_area.buffer.cursor_up()
        event.app.invalidate()

    @bindings.add("pageup", filter=has_focus(results_control), eager=True)
    def _result_page_up(event) -> None:
        scroll_page_up(event)
        event.app.invalidate()

    @bindings.add("pagedown", filter=has_focus(results_control), eager=True)
    def _result_page_down(event) -> None:
        scroll_page_down(event)
        event.app.invalidate()

    search_return_focus = has_focus(scope_control) | has_focus(results_control)
    non_search_focus = has_focus(target_control) | search_return_focus

    @bindings.add("enter", filter=search_return_focus, eager=True)
    @bindings.add("/", filter=non_search_focus, eager=True)
    def _focus_search(event) -> None:
        event.app.layout.focus(search_area)
        search_area.buffer.cursor_position = len(search_area.text)
        event.app.invalidate()

    @bindings.add("enter", filter=has_focus(search_area), eager=True)
    def _search(event) -> None:
        nonlocal response
        if background_turn.busy:
            status["value"] = "A Find search is already running."
            event.app.invalidate()
            return
        try:
            request = FindSearchRequest(
                query=search_area.text.strip(),
                target_names=target_selection.selected_names,
                # Find materializes lexical descendants as visible checkmarks;
                # re-expanding here would make a manually unchecked child lie.
                include_descendants=False,
                follow_embeds=embed_choice.selected_uid == "FOLLOW",
                limit=limit,
            )
        except ValueError as error:
            status["value"] = str(error)
            event.app.invalidate()
            return

        def work() -> FindSearchResponse:
            next_response = run_search(request)
            if not isinstance(next_response, FindSearchResponse):
                raise ValueError("Find controller returned an invalid response.")
            if next_response.request != request:
                raise ValueError("Find controller changed the frozen request.")
            return next_response

        def commit(next_response: FindSearchResponse) -> None:
            nonlocal response
            response = next_response
            result_text = render_find_search_results(response)
            results_area.buffer.set_document(
                Document(result_text, cursor_position=0),
                bypass_readonly=True,
            )
            status["value"] = (
                f"{response.mode} · {len(response.results)} RESULT(S) · SCOPE FROZEN"
            )

        def fail(error: Exception) -> None:
            detail = " ".join(safe_terminal_text(str(error)).split())
            if len(detail) > 240:
                detail = detail[:239].rstrip() + "…"
            status["value"] = f"SEARCH FAILED · {type(error).__name__}: {detail}"

        def return_to_surface() -> None:
            app.layout.focus(results_control if response is not None else search_area)

        def close_after_search() -> None:
            app.exit(result=FindSearchWorkbenchResult("CLOSED", response))

        background_turn.start(
            event.app,
            work=work,
            on_success=commit,
            on_error=fail,
            on_idle=return_to_surface,
            on_close=close_after_search,
        )
        status["value"] = "SEARCHING · SCOPE FROZEN"
        event.app.layout.focus(results_control)
        event.app.invalidate()

    def close(event) -> None:
        if background_turn.request_close():
            status["value"] = "Closing after the current search finishes."
            event.app.invalidate()
            return
        event.app.exit(result=FindSearchWorkbenchResult("CLOSED", response))

    @bindings.add("escape", filter=non_search_focus, eager=True)
    @bindings.add("backspace", filter=non_search_focus, eager=True)
    def _back_to_search(event) -> None:
        event.app.layout.focus(search_area)
        search_area.buffer.cursor_position = len(search_area.text)
        event.app.invalidate()

    @bindings.add("q", filter=non_search_focus, eager=True)
    def _close_from_read_surface(event) -> None:
        close(event)

    @bindings.add("c-c", eager=True)
    @bindings.add(Keys.SIGINT, eager=True)
    @bindings.add("c-d", eager=True)
    def _close_anywhere(event) -> None:
        close(event)

    try:
        result = app.run()
    except (EOFError, KeyboardInterrupt):
        return FindSearchWorkbenchResult("CLOSED", response)
    if not isinstance(result, FindSearchWorkbenchResult):
        raise ValueError("Find workbench returned an invalid result.")
    return result
