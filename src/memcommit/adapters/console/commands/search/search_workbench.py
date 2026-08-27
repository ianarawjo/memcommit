"""Interactive semantic Search, multi-target, and scope surface."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import AbstractSet, Literal

from prompt_toolkit.application import Application
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.bindings.scroll import (
    scroll_page_down,
    scroll_page_up,
)
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import (
    ConditionalContainer,
    FormattedTextControl,
    Layout,
    Window,
)
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.widgets import Frame, TextArea

from memcommit.adapters.console.commands.shared.background_turn import BackgroundExecutorTurn
from memcommit.adapters.console.commands.shared.command_progress import busy_suffix
from memcommit.core.context_targeting.tui.compact_scope import (
    CompactReadableScopeControl,
)
from memcommit.adapters.console.commands.shared.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.adapters.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.adapters.interfaces.tui.components.frame import (
    TuiRegion,
    bind_focused_frame_style,
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
from memcommit.adapters.console.commands.search.result_present import (
    SearchResultViewRow,
    render_grouped_search_results,
)
from memcommit.adapters.console.commands.shared.save_location_control import SaveLocationView
from memcommit.adapters.console.commands.shared.semantic_clipboard import (
    PlainTextClipboardReceipt,
    clipboard_failure_receipt,
    copy_plain_text,
)
from memcommit.adapters.console.commands.shared.session_help import bind_session_help
from memcommit.adapters.interfaces.tui.components.focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    SurfaceMoveResult,
    bind_surface_navigation,
)
from memcommit.core.context_targeting.tui.name_editor import (
    ContextNameControl,
    suggest_fresh_context_name,
)
from memcommit.adapters.console.selection import FlatMultiSelectionState, SelectionOption
from memcommit.adapters.console.selection.tui.multiple import render_vertical_multi_choice_rows
from memcommit.application.operations.search.application import (
    FindSearchRequest,
    FindSearchResponse,
    FindSearchResult,
)
from memcommit.source_projection.model import SourceForm
from memcommit.source_projection.presentation import (
    SourceDisplayValue,
    normalize_source_display_tokens,
    source_display_text,
    source_object_label,
)


_RESULT_SOURCE_FORMS = {
    "memory": SourceForm.MEMORY,
    "ref": SourceForm.MEMORY_REF,
    "query": SourceForm.QUERY_VIEW,
}


def _find_result_kind_label(result: "FindSearchResult") -> str:
    form = _RESULT_SOURCE_FORMS.get(result.kind)
    return (
        source_object_label(form)
        if form is not None
        else result.kind.replace("_", " ").upper()
    )


def _find_result_annotation(result: "FindSearchResult") -> str:
    return "RELATED" if result.relevance == "related" else ""


def _find_result_selection_label(
    result: "FindSearchResult",
    *,
    number: int,
    context_annotation: SourceDisplayValue | None = None,
) -> str:
    """Project one complete selectable Search result as one logical row."""

    location = [result.context_name]
    annotation = source_display_text(context_annotation)
    if annotation:
        location.append(annotation)
    location.append(_find_result_kind_label(result).upper())
    related = _find_result_annotation(result)
    if related:
        location.append(related)
    content = " ".join(result.content.split())
    return f"{number} [{result.uid[:8]}] {content} [{' · '.join(location)}]"


def _has_granted_materialization_source(
    results: Sequence["FindSearchResult"],
    granted_context_names: AbstractSet[str],
) -> bool:
    """Keep authority decisions independent from presentation annotations."""

    return any(result.context_name in granted_context_names for result in results)


@dataclass(frozen=True)
class FindResultsClipboardProjection:
    """One focused Find result or the complete frozen ranked result set."""

    text: str
    scope: Literal["FOCUSED", "RESULT_SET"]
    label: str
    result_count: int


@dataclass(frozen=True)
class FindSearchWorkbenchResult:
    """Close state or one reviewed materialization request."""

    status: Literal["CLOSED", "MATERIALIZE"]
    response: FindSearchResponse | None = None
    selected_result_indices: tuple[int, ...] = ()
    materialize_as: Literal["COPY", "REFERENCE"] | None = None
    save_location: str | None = None

    def __post_init__(self) -> None:
        if self.status == "CLOSED":
            if (
                self.selected_result_indices
                or self.materialize_as is not None
                or self.save_location is not None
            ):
                raise ValueError("A closed Find workbench cannot request a save.")
            return
        if (
            self.response is None
            or not self.selected_result_indices
            or self.materialize_as not in {"COPY", "REFERENCE"}
            or not isinstance(self.save_location, str)
            or not self.save_location.strip()
        ):
            raise ValueError("Find Save As requires reviewed result choices.")
        if len(set(self.selected_result_indices)) != len(
            self.selected_result_indices
        ) or any(
            isinstance(index, bool)
            or not isinstance(index, int)
            or not 0 <= index < len(self.response.results)
            for index in self.selected_result_indices
        ):
            raise ValueError("Find Save As selected invalid result rows.")


FindSearchRunner = Callable[[FindSearchRequest], FindSearchResponse]
FindSaveLocationValidator = Callable[[str], object]


def _find_save_location_stem(context_name: str, query: str) -> str:
    """Build one editable local name suggestion without assigning identity."""

    words = "-".join(query.strip().split()) or "search"
    safe = "".join(
        "-" if character in "/\\:" or ord(character) < 32 else character
        for character in words
    ).strip("-.")
    if not safe:
        safe = "search"
    if len(safe) > 48:
        safe = safe[:48].rstrip("-.") or "search"
    return f"{context_name}/results/{safe}"


def _find_search_result_view_row(
    result: FindSearchResult,
    *,
    rank: int,
) -> SearchResultViewRow:
    return SearchResultViewRow(
        context_name=result.context_name,
        label=(
            f"[{rank} {_find_result_kind_label(result)} {result.uid[:8]}]"
            + (
                f" · {_find_result_annotation(result)}"
                if _find_result_annotation(result)
                else ""
            )
        ),
        content=result.content,
    )


def render_find_search_results(response: FindSearchResponse | None) -> str:
    """Render only rows whose request still matches the visible controls."""

    if response is None:
        return "SEARCH RESULTS\n  Enter a query to search the selected scope."
    rows = tuple(
        _find_search_result_view_row(result, rank=index)
        for index, result in enumerate(response.results, start=1)
    )
    return render_grouped_search_results(
        rows,
        related_query=response.related_query,
    )


def project_find_results_clipboard(
    response: FindSearchResponse | None,
    *,
    focused_index: int = 0,
    whole_result_set: bool = False,
) -> FindResultsClipboardProjection:
    """Project host-resolved results without checkbox or viewport wrapping."""

    if response is None or not response.results:
        raise ValueError("There are no Find results to copy.")
    count = len(response.results)
    if whole_result_set:
        suffix = "Result" if count == 1 else "Results"
        return FindResultsClipboardProjection(
            text=render_find_search_results(response),
            scope="RESULT_SET",
            label=f"complete Find result set · {count} {suffix}",
            result_count=count,
        )
    if isinstance(focused_index, bool) or not 0 <= focused_index < count:
        raise ValueError("The focused Find result is no longer available.")
    result = response.results[focused_index]
    return FindResultsClipboardProjection(
        text=render_grouped_search_results(
            (
                _find_search_result_view_row(
                    result,
                    rank=focused_index + 1,
                ),
            ),
            related_query=response.related_query,
        ),
        scope="FOCUSED",
        label=(
            f"Find result {focused_index + 1} · "
            f"{safe_terminal_text(result.context_name)} · "
            f"{safe_terminal_text(_find_result_kind_label(result))}"
        ),
        result_count=1,
    )


def _results_frame_title(turn: BackgroundExecutorTurn[FindSearchResponse]) -> str:
    if turn.busy:
        return f"RESULTS · SEARCHING {busy_suffix(turn.frame)}"
    return "RESULTS"


def _find_save_as_available(
    response: FindSearchResponse | None,
    *,
    busy: bool,
) -> bool:
    """Expose outcome controls only for one completed nonempty result set."""

    return response is not None and bool(response.results) and not busy


def run_find_search_workbench(
    names: Sequence[str],
    *,
    current: str,
    initial_target: str,
    initial_targets: Sequence[str] | None = None,
    initial_include_descendants: bool,
    initial_follow_embeds: bool,
    limit: int,
    run_search: FindSearchRunner,
    annotations: Mapping[str, SourceDisplayValue] | None = None,
    granted_context_names: AbstractSet[str] = frozenset(),
    local_context_names: Sequence[str] | None = None,
    validate_save_location: FindSaveLocationValidator | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    clipboard_writer: Callable[[str], None] | None = None,
) -> FindSearchWorkbenchResult:
    """Search repeatedly while keeping query, targets, scope, and results visible."""

    catalog = tuple(names)
    if (
        not catalog
        or len(set(catalog)) != len(catalog)
        or any(not isinstance(name, str) or not name for name in catalog)
    ):
        raise ValueError("Find requires a distinct readable Context catalog.")
    staged_initial_targets = tuple(
        dict.fromkeys(
            (initial_target,)
            if initial_targets is None
            else initial_targets
        )
    )
    if (
        current not in catalog
        or initial_target not in catalog
        or not staged_initial_targets
        or any(name not in catalog for name in staged_initial_targets)
    ):
        raise ValueError("Find's initial Context is outside the readable catalog.")
    if not callable(run_search):
        raise ValueError("Find requires a search controller.")
    if require_tty:
        require_interactive_terminal(
            "Interactive Search",
            snapshot_hint='Pass a query, for example: mem search "parking".',
        )

    labels = dict(annotations or {})
    if set(labels) - set(catalog):
        raise ValueError("Find Context annotations are outside the catalog.")
    try:
        for annotation in labels.values():
            normalize_source_display_tokens(annotation)
    except (TypeError, ValueError) as error:
        raise ValueError("Find received an invalid Context annotation.") from error
    granted_catalog = frozenset(granted_context_names)
    if not granted_catalog <= set(catalog):
        raise ValueError("Find granted Context names are outside the catalog.")
    local_catalog = tuple(
        dict.fromkeys(catalog if local_context_names is None else local_context_names)
    )
    if any(not isinstance(name, str) or not name for name in local_catalog):
        raise ValueError("Find local Context names must be nonblank text.")

    materialize_choice = HorizontalChoiceState(
        (
            HorizontalChoiceOption(
                "COPY",
                "COPY",
                "Create independent Memory values with fresh identities.",
            ),
            HorizontalChoiceOption(
                "REFERENCE",
                "REFERENCE",
                "Create read-only live pointers to locally owned Memories.",
            ),
        ),
        selected_uid="COPY",
    )
    response: FindSearchResponse | None = None
    result_selection: FlatMultiSelectionState | None = None
    status = {"value": "ENTER A QUERY"}
    copy_receipt: PlainTextClipboardReceipt | None = None
    background_turn: BackgroundExecutorTurn[FindSearchResponse] = (
        BackgroundExecutorTurn()
    )

    def scope_changed(message: str) -> None:
        nonlocal copy_receipt, response, result_selection
        response = None
        result_selection = None
        copy_receipt = None
        status["value"] = message

    def scope_status(message: str) -> None:
        status["value"] = safe_terminal_text(message).upper()

    scope = CompactReadableScopeControl(
        catalog,
        current_name=current,
        initial_targets=staged_initial_targets,
        include_descendants=initial_include_descendants,
        follow_embeds=initial_follow_embeds,
        annotations=labels,
        input_name="find-search-context",
        on_change=scope_changed,
        on_status=scope_status,
        locked=lambda: background_turn.busy,
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
    initial_save_location = suggest_fresh_context_name(
        _find_save_location_stem(initial_target, "search"),
        local_catalog,
    )
    save_location = ContextNameControl.create(
        SaveLocationView(
            value=initial_save_location,
            state="NEW CONTEXT",
            detail="Checked results create this exact new local Context.",
            validate=validate_save_location,
            context_names=local_catalog,
            current_context=current if current in local_catalog else None,
        ),
        input_name="find-save-location",
        parent_height=1,
    )
    save_location_edit = {"edited": False, "programmatic": False}

    def save_location_changed(_buffer) -> None:
        if not save_location_edit["programmatic"]:
            save_location_edit["edited"] = True

    save_location.input.buffer.on_text_changed += save_location_changed

    def render_results() -> list[tuple[str, str]]:
        if response is None or result_selection is None:
            return [("", "Enter a query to search the selected scope.")]
        if not response.results:
            return [("", "(no matching items)")]
        fragments: list[tuple[str, str]] = []
        if response.related_query:
            fragments.extend(
                [
                    ("class:heading", "RELATED RESULTS\n"),
                    (
                        "",
                        f"Broader search: {safe_terminal_text(response.related_query)}\n\n",
                    ),
                ]
            )
        # Find now follows the service-wide one-column session grammar. Result
        # rows therefore own the full frame width instead of retaining the
        # former side-by-side Save As allowance.
        width = max(24, app.output.get_size().columns - 6)
        fragments.extend(
            render_vertical_multi_choice_rows(
                result_selection,
                focused=app.layout.has_focus(results_control),
                content_width=width,
                numbered=False,
            )
        )
        return fragments

    results_control = FormattedTextControl(
        render_results,
        focusable=True,
        show_cursor=False,
    )
    results_window = Window(
        results_control,
        wrap_lines=True,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )

    def render_materialize() -> list[tuple[str, str]]:
        return render_horizontal_choice(
            materialize_choice,
            title="MODE",
            focused=app.layout.has_focus(materialize_control),
            show_description=False,
        )

    materialize_control = FormattedTextControl(
        render_materialize,
        focusable=True,
        show_cursor=False,
    )

    def render_todo() -> list[tuple[str, str]]:
        checked = len(result_selection.selected_uids) if result_selection else 0
        focused = app.layout.has_focus(todo_control)
        value = f"SAVE {checked} CHECKED AS {materialize_choice.selected_uid}"
        fragments: list[tuple[str, str]] = []
        if focused:
            fragments.append(("[SetCursorPosition]", ""))
        fragments.append(
            (
                "class:memcommit.choice.active.focused" if focused else "",
                f"{'> ' if focused else '  '}{safe_terminal_text(value)}",
            )
        )
        return fragments

    todo_control = FormattedTextControl(
        render_todo,
        focusable=True,
        show_cursor=False,
    )

    header = Window(
        FormattedTextControl(" MEM SEARCH"),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    scope_frame = Frame(
        scope.container,
        title="SCOPE",
    )
    search_frame = Frame(
        search_area,
        title="SEARCH · ENTER TO RUN",
        height=Dimension.exact(3),
    )
    results_frame = Frame(
        results_window,
        title=lambda: _results_frame_title(background_turn),
        height=Dimension(min=7, weight=2),
    )
    save_as_frame = Frame(
        Window(materialize_control, wrap_lines=True),
        title="SAVE AS",
        height=Dimension.exact(4),
    )
    todo_frame = Frame(
        Window(todo_control, wrap_lines=True),
        title="TO DO · ENTER TO SAVE",
        height=Dimension.exact(3),
    )

    def render_footer() -> str | list[tuple[str, str]]:
        if background_turn.busy:
            return (
                f" SEARCHING {busy_suffix(background_turn.frame)} · "
                "Ctrl-C closes after search"
            )
        hint = (
            "Enter search · Tab/Shift-Tab panes · Esc/Ctrl-C close"
            if app.layout.has_focus(search_area)
            else (
                "↑/↓ move/cross · Enter activate/check · ←/→ adjust · "
                "/ search · Esc back · H Help · Q close"
            )
        )
        if app.layout.has_focus(results_control):
            hint = (
                "↑/↓ move results · Enter/Space check · y copy focused · "
                "Y copy all results · / search · Esc back"
            )
        if copy_receipt is not None and app.layout.has_focus(results_control):
            return [
                (copy_receipt.style, " " + copy_receipt.message),
                ("", f" · {hint}"),
            ]
        return f" {safe_terminal_text(status['value'])} · {hint}"

    footer = Window(
        FormattedTextControl(render_footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    # SAVE AS is an outcome action, not search setup. Keep the complete group
    # out of both the canvas and keyboard topology until a successful search
    # has produced at least one result.
    save_as_panel = ConditionalContainer(
        build_tui_frame(
            TuiRegion(save_as_frame),
            TuiRegion(save_location.container),
            TuiRegion(todo_frame),
        ),
        filter=Condition(
            lambda: _find_save_as_available(
                response,
                busy=background_turn.busy,
            )
        ),
    )
    root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(scope_frame),
        TuiRegion(search_frame),
        TuiRegion(results_frame),
        TuiRegion(save_as_panel),
        TuiRegion(footer),
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
    bind_focused_frame_style(
        search_frame,
        is_focused=lambda: app.layout.has_focus(search_area),
    )
    bind_focused_frame_style(
        scope_frame,
        is_focused=lambda: any(
            app.layout.has_focus(control)
            for control in (
                scope.input,
                scope.browse_control,
                scope.range_control,
                scope.embed_control,
                scope.tree_control,
            )
        ),
    )
    bind_focused_frame_style(
        results_frame,
        is_focused=lambda: app.layout.has_focus(results_control),
    )
    bind_focused_frame_style(
        save_as_frame,
        is_focused=lambda: app.layout.has_focus(materialize_control),
    )
    bind_focused_frame_style(
        todo_frame,
        is_focused=lambda: app.layout.has_focus(todo_control),
    )

    def clear_results(message: str) -> None:
        nonlocal copy_receipt, response, result_selection
        response = None
        result_selection = None
        copy_receipt = None
        status["value"] = message

    def query_changed(_buffer) -> None:
        if response is None or background_turn.busy:
            return
        clear_results("QUERY CHANGED · PRESS ENTER TO SEARCH")
        app.invalidate()

    search_area.buffer.on_text_changed += query_changed

    def _move_search(_event, _delta: int) -> SurfaceMoveResult:
        return "BOUNDARY"

    def _enter_search(_delta: int) -> None:
        search_area.buffer.cursor_position = len(search_area.text)

    def _move_results(_event, delta: int) -> SurfaceMoveResult:
        nonlocal copy_receipt
        if result_selection is None or response is None or not response.results:
            return "BOUNDARY"
        moved = result_selection.move(delta)
        if moved:
            copy_receipt = None
        return "MOVED" if moved else "BOUNDARY"

    def _enter_results(delta: int) -> None:
        nonlocal copy_receipt
        if result_selection is not None:
            previous_uid = result_selection.cursor_uid
            result_selection.cursor_uid = (
                result_selection.options[0].uid
                if delta > 0
                else result_selection.options[-1].uid
            )
            if result_selection.cursor_uid != previous_uid:
                copy_receipt = None

    @bindings.add("pageup", filter=has_focus(results_control), eager=True)
    def _result_page_up(event) -> None:
        nonlocal copy_receipt
        if result_selection is not None:
            if result_selection.move(-5):
                copy_receipt = None
        else:
            scroll_page_up(event)
        event.app.invalidate()

    @bindings.add("pagedown", filter=has_focus(results_control), eager=True)
    def _result_page_down(event) -> None:
        nonlocal copy_receipt
        if result_selection is not None:
            if result_selection.move(5):
                copy_receipt = None
        else:
            scroll_page_down(event)
        event.app.invalidate()

    tree_focus = (
        has_focus(save_location.tree_control)
        if save_location.tree_control is not None
        else Condition(lambda: False)
    )
    scope_focus = (
        has_focus(scope.input)
        | has_focus(scope.browse_control)
        | has_focus(scope.range_control)
        | has_focus(scope.embed_control)
        | has_focus(scope.tree_control)
    )
    search_return_focus = (
        scope_focus
        | has_focus(results_control)
        | has_focus(materialize_control)
        | has_focus(todo_control)
        | tree_focus
    )
    non_search_focus = search_return_focus
    read_non_search_focus = non_search_focus & ~has_focus(scope.input)
    bind_session_help(
        bindings,
        filter=read_non_search_focus,
        app_input=app_input,
        app_output=app_output,
        study_surface="find-search",
    )

    def _focus_search(event) -> SurfaceActionResult:
        event.app.layout.focus(search_area)
        search_area.buffer.cursor_position = len(search_area.text)
        return "HANDLED"

    @bindings.add("/", filter=read_non_search_focus, eager=True)
    def _focus_search_shortcut(event) -> None:
        _focus_search(event)
        event.app.invalidate()

    def _search(event) -> SurfaceActionResult:
        nonlocal copy_receipt, response, result_selection
        if background_turn.busy:
            status["value"] = "A Search is already running."
            return "HANDLED"
        try:
            request_targets, request_descendants = scope.request_scope()
            request = FindSearchRequest(
                query=search_area.text.strip(),
                target_names=request_targets,
                include_descendants=request_descendants,
                follow_embeds=scope.follow_embeds,
                limit=limit,
            )
        except ValueError as error:
            status["value"] = str(error)
            return "HANDLED"

        def work() -> FindSearchResponse:
            next_response = run_search(request)
            if not isinstance(next_response, FindSearchResponse):
                raise ValueError("Find controller returned an invalid response.")
            if next_response.request != request:
                raise ValueError(
                    "Search inputs changed while the request was running. "
                    "Run the search again."
                )
            return next_response

        def commit(next_response: FindSearchResponse) -> None:
            nonlocal copy_receipt, response, result_selection
            response = next_response
            copy_receipt = None
            result_selection = (
                FlatMultiSelectionState(
                    tuple(
                        SelectionOption(
                            str(index),
                            _find_result_selection_label(
                                result,
                                number=index + 1,
                                context_annotation=labels.get(result.context_name),
                            ),
                        )
                        for index, result in enumerate(response.results)
                    ),
                    cursor_uid="0",
                )
                if response.results
                else None
            )
            if not save_location_edit["edited"]:
                save_location_edit["programmatic"] = True
                try:
                    save_location.set_text(
                        suggest_fresh_context_name(
                            _find_save_location_stem(
                                response.request.target_names[0],
                                response.request.query,
                            ),
                            local_catalog,
                        )
                    )
                finally:
                    save_location_edit["programmatic"] = False
            result_count = len(response.results)
            result_label = "RESULT" if result_count == 1 else "RESULTS"
            status["value"] = f"{result_count} {result_label}"

        def fail(error: Exception) -> None:
            detail = " ".join(safe_terminal_text(str(error)).split())
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
        status["value"] = "SEARCHING"
        event.app.layout.focus(results_control)
        return "HANDLED"

    def _toggle_result(event) -> SurfaceActionResult:
        nonlocal copy_receipt
        copy_receipt = None
        if background_turn.busy:
            status["value"] = "Wait for the current search to finish."
        elif result_selection is None or response is None or not response.results:
            return _focus_search(event)
        else:
            checked = result_selection.toggle_cursor()
            status["value"] = (
                f"{'CHECKED' if checked else 'UNCHECKED'} RESULT "
                f"{result_selection.cursor_index + 1} · "
                f"{len(result_selection.selected_uids)} TOTAL"
            )
        event.app.invalidate()
        return "HANDLED"

    @bindings.add(" ", filter=has_focus(results_control), eager=True)
    def _space_result(event) -> None:
        _toggle_result(event)

    def copy_results(event, *, whole_result_set: bool) -> None:
        nonlocal copy_receipt
        try:
            focused_index = (
                0
                if result_selection is None
                else int(result_selection.cursor_uid)
            )
            projection = project_find_results_clipboard(
                response,
                focused_index=focused_index,
                whole_result_set=whole_result_set,
            )
        except (TypeError, ValueError) as error:
            copy_receipt = clipboard_failure_receipt(error)
        else:
            # Ranked results may combine authority domains, so this remains a
            # plain-text OS copy and never fabricates a typed mutation stage.
            copy_receipt = copy_plain_text(
                projection.text,
                success_message=projection.label,
                writer=clipboard_writer,
            )
        event.app.invalidate()

    @bindings.add("y", filter=has_focus(results_control), eager=True)
    def _copy_focused_result(event) -> None:
        copy_results(event, whole_result_set=False)

    @bindings.add("Y", filter=has_focus(results_control), eager=True)
    def _copy_all_results(event) -> None:
        copy_results(event, whole_result_set=True)

    def _move_materialize(_event, delta: int) -> SurfaceMoveResult:
        return "MOVED" if materialize_choice.move(delta) else "BOUNDARY"

    def _activate_materialize(event) -> SurfaceActionResult:
        event.app.layout.focus(save_location.input)
        save_location.input.buffer.cursor_position = len(save_location.text)
        status["value"] = (
            f"{materialize_choice.selected_uid} · REVIEW THE EXACT SAVE LOCATION"
        )
        return "HANDLED"

    @bindings.add("right", filter=has_focus(materialize_control), eager=True)
    def _materialize_right(event) -> None:
        materialize_choice.move(1)
        event.app.invalidate()

    @bindings.add("left", filter=has_focus(materialize_control), eager=True)
    def _materialize_left(event) -> None:
        materialize_choice.move(-1)
        event.app.invalidate()

    def _move_save_location(event, delta: int) -> SurfaceMoveResult:
        if delta < 0 and save_location.tree_control is not None:
            event.app.layout.focus(save_location.tree_control)
            status["value"] = "CHOOSE A PARENT CONTEXT · ENTER TO REPARENT"
            return "CONSUMED"
        return "BOUNDARY"

    def _activate_save_location(event) -> SurfaceActionResult:
        try:
            save_location.validate_candidate()
        except (OSError, TypeError, ValueError) as error:
            status["value"] = str(error)
            return "HANDLED"
        event.app.layout.focus(todo_control)
        status["value"] = "SAVE LOCATION VALID · ENTER TO SAVE"
        return "HANDLED"

    def _apply_materialization(event) -> SurfaceActionResult:
        if background_turn.busy:
            status["value"] = "Wait for the current search to finish."
            return "HANDLED"
        if response is None or result_selection is None:
            status["value"] = "RUN SEARCH AND CHECK AT LEAST ONE RESULT"
            return "HANDLED"
        selected_indices = tuple(int(uid) for uid in result_selection.selected_uids)
        if not selected_indices:
            status["value"] = "CHECK AT LEAST ONE RESULT"
            return "HANDLED"
        selected_results = tuple(response.results[index] for index in selected_indices)
        unsupported = next(
            (
                result.kind
                for result in selected_results
                if result.kind not in {"memory", "ref"}
            ),
            None,
        )
        if unsupported is not None:
            status["value"] = f"{unsupported.upper()} RESULTS CANNOT BE SAVED"
            return "HANDLED"
        if any(result.source_memory_uid is None for result in selected_results):
            status["value"] = "A CHECKED RESULT HAS NO SOURCE MEMORY IDENTITY"
            return "HANDLED"
        if materialize_choice.selected_uid == "REFERENCE" and (
            _has_granted_materialization_source(selected_results, granted_catalog)
        ):
            status["value"] = "REFERENCE REQUIRES LOCALLY OWNED SOURCE MEMORIES"
            return "HANDLED"
        try:
            destination = save_location.validate_candidate()
        except (OSError, TypeError, ValueError) as error:
            status["value"] = str(error)
            event.app.layout.focus(save_location.input)
            return "HANDLED"
        event.app.exit(
            result=FindSearchWorkbenchResult(
                "MATERIALIZE",
                response,
                selected_indices,
                materialize_choice.selected_uid,
                destination,
            )
        )
        return "HANDLED"

    if save_location.tree_control is not None:
        parent_tree = save_location.parent_locator
        assert parent_tree is not None

        @bindings.add("up", filter=tree_focus, eager=True)
        def _save_tree_up(event) -> None:
            parent_tree.move(-1)
            event.app.invalidate()

        @bindings.add("down", filter=tree_focus, eager=True)
        def _save_tree_down(event) -> None:
            state = parent_tree.state.tree
            before = state.selected_row_index()
            parent_tree.move(1)
            if state.selected_row_index() == before:
                event.app.layout.focus(save_location.input)
            event.app.invalidate()

        @bindings.add("left", filter=tree_focus, eager=True)
        def _save_tree_left(event) -> None:
            parent_tree.collapse()
            event.app.invalidate()

        @bindings.add("right", filter=tree_focus, eager=True)
        def _save_tree_right(event) -> None:
            parent_tree.expand()
            event.app.invalidate()

        @bindings.add("enter", filter=tree_focus, eager=True)
        def _save_tree_choose(event) -> None:
            try:
                candidate = save_location.choose_cursor_as_parent()
            except (TypeError, ValueError) as error:
                status["value"] = str(error)
            else:
                event.app.layout.focus(save_location.input)
                status["value"] = f"PARENT SELECTED · REVIEW {candidate}"
            event.app.invalidate()

        @bindings.add("tab", filter=tree_focus, eager=True)
        @bindings.add("s-tab", filter=tree_focus, eager=True)
        @bindings.add("backspace", filter=tree_focus, eager=True)
        def _leave_save_tree(event) -> None:
            event.app.layout.focus(save_location.input)
            event.app.invalidate()

    @bindings.add("c-j", filter=has_focus(save_location.input), eager=True)
    def _reject_save_location_newline(event) -> None:
        status["value"] = "SAVE LOCATION STAYS ON ONE LINE"
        event.app.invalidate()

    def visible_surfaces() -> tuple[FocusSurface, ...]:
        if scope.browser_open:
            return (scope.browser_surface(uid_prefix="search-scope"),)
        surfaces = [
            *scope.normal_surfaces(uid_prefix="search-scope"),
            FocusSurface(
                "search",
                search_area,
                move_vertical=_move_search,
                activate=_search,
                on_vertical_enter=_enter_search,
            ),
            FocusSurface(
                "results",
                results_control,
                move_vertical=_move_results,
                activate=_toggle_result,
                on_vertical_enter=_enter_results,
            ),
        ]
        if response is not None and response.results:
            surfaces.extend(
                (
                    FocusSurface(
                        "materialize",
                        materialize_control,
                        move_vertical=_move_materialize,
                        activate=_activate_materialize,
                    ),
                    FocusSurface(
                        "save-location",
                        save_location.input,
                        move_vertical=_move_save_location,
                        activate=_activate_save_location,
                    ),
                    FocusSurface(
                        "todo",
                        todo_control,
                        move_vertical=lambda _event, _delta: "BOUNDARY",
                        activate=_apply_materialization,
                    ),
                )
            )
        return tuple(surfaces)

    surface_focus = SurfaceFocusController(visible_surfaces)
    bind_surface_navigation(bindings, surface_focus)
    scope.bind_keybindings(bindings)

    @bindings.add("tab", filter=has_focus(scope.tree_control), eager=True)
    @bindings.add("s-tab", filter=has_focus(scope.tree_control), eager=True)
    @bindings.add("backspace", filter=has_focus(scope.tree_control), eager=True)
    def _leave_scope_browser(event) -> None:
        scope.close_browser(event)
        event.app.invalidate()

    def close(event) -> None:
        if background_turn.request_close():
            status["value"] = "Closing after the current search finishes."
            event.app.invalidate()
            return
        event.app.exit(result=FindSearchWorkbenchResult("CLOSED", response))

    @bindings.add(
        "backspace",
        filter=(
            read_non_search_focus & ~tree_focus & ~has_focus(scope.tree_control)
        ),
        eager=True,
    )
    def _back_to_search(event) -> None:
        event.app.layout.focus(search_area)
        search_area.buffer.cursor_position = len(search_area.text)
        event.app.invalidate()

    def _return_to_search(event) -> bool:
        if save_location.tree_control is not None and event.app.layout.has_focus(
            save_location.tree_control
        ):
            event.app.layout.focus(save_location.input)
            return True
        if event.app.layout.has_focus(search_area):
            return False
        event.app.layout.focus(search_area)
        search_area.buffer.cursor_position = len(search_area.text)
        return True

    @bindings.add("escape", eager=True)
    def _escape(event) -> None:
        if not scope.close_browser(event):
            dispatch_tui_back(event, _return_to_search, close=close)
        event.app.invalidate()

    @bind_case_insensitive_key(
        bindings,
        "q",
        filter=read_non_search_focus,
        eager=True,
    )
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
