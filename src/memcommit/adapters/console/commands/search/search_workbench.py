"""Interactive semantic Search, multi-target, and scope surface."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, cast

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

from memcommit.adapters.console.terminal.components.background_turn import (
    BackgroundExecutorTurn,
)
from memcommit.adapters.console.terminal.components.progress import busy_suffix
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.readable_scope_editor import (
    CompactReadableScopeControl,
)
from memcommit.adapters.console.terminal.components.horizontal_choice import (
    HorizontalChoiceOption,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.adapters.console.terminal.components.frame import (
    TuiRegion,
    bind_focused_frame_style,
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
from memcommit.adapters.console.commands.search.result_present import (
    SearchResultViewRow,
    render_grouped_search_results,
)
from memcommit.adapters.console.terminal.components.retrieve_answer_save import (
    RetrieveAnswerSavePanel,
)
from memcommit.adapters.console.terminal.components.plain_text_clipboard import (
    PlainTextClipboardReceipt,
    clipboard_failure_receipt,
    copy_plain_text,
)
from memcommit.adapters.console.terminal.components.session_help import bind_session_help
from memcommit.adapters.console.terminal.components.focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    SurfaceMoveResult,
    bind_surface_navigation,
)
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.new_context_editor import suggest_fresh_context_name
from memcommit.adapters.console.terminal.components.selection import (
    FlatMultiSelectionState,
    SelectionOption,
)
from memcommit.adapters.console.terminal.components.selection.multiple import (
    render_vertical_multi_choice_rows,
)
from memcommit.application.operations.search.application import (
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from memcommit.application.capabilities.save_context_from_selection.application import (
    SaveContextMode,
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


def _search_result_kind_label(result: "SearchResult") -> str:
    form = _RESULT_SOURCE_FORMS.get(result.kind)
    return (
        source_object_label(form)
        if form is not None
        else result.kind.replace("_", " ").upper()
    )


def _search_result_annotation(result: "SearchResult") -> str:
    return "RELATED" if result.relevance == "related" else ""


def _search_result_selection_label(
    result: "SearchResult",
    *,
    number: int,
    context_annotation: SourceDisplayValue | None = None,
) -> str:
    """Project one complete selectable Search result as one logical row."""

    location = [result.context_name]
    annotation = source_display_text(context_annotation)
    if annotation:
        location.append(annotation)
    location.append(_search_result_kind_label(result).upper())
    related = _search_result_annotation(result)
    if related:
        location.append(related)
    content = " ".join(result.content.split())
    return f"{number} [{result.uid[:8]}] {content} [{' · '.join(location)}]"


@dataclass(frozen=True)
class SearchResultsClipboardProjection:
    """One focused Search result or the complete frozen ranked result set."""

    text: str
    scope: Literal["FOCUSED", "RESULT_SET"]
    label: str
    result_count: int


@dataclass(frozen=True)
class SearchWorkbenchResult:
    """Close state or one reviewed Save request."""

    status: Literal["CLOSED", "SAVE"]
    response: SearchResponse | None = None
    selected_result_indices: tuple[int, ...] = ()
    save_as: SaveContextMode | None = None
    save_location: str | None = None

    def __post_init__(self) -> None:
        if self.status == "CLOSED":
            if (
                self.selected_result_indices
                or self.save_as is not None
                or self.save_location is not None
            ):
                raise ValueError("A closed Search workbench cannot request a save.")
            return
        if (
            self.response is None
            or not self.selected_result_indices
            or self.save_as not in {"COPY", "REFERENCE", "EMBED"}
            or not isinstance(self.save_location, str)
            or not self.save_location.strip()
        ):
            raise ValueError("Search Save As requires reviewed result choices.")
        if len(set(self.selected_result_indices)) != len(
            self.selected_result_indices
        ) or any(
            isinstance(index, bool)
            or not isinstance(index, int)
            or not 0 <= index < len(self.response.results)
            for index in self.selected_result_indices
        ):
            raise ValueError("Search Save As selected invalid result rows.")


SearchRunner = Callable[[SearchRequest], SearchResponse]
SearchSaveLocationValidator = Callable[[str], object]


def _search_save_location_stem(context_name: str, query: str) -> str:
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


def _search_result_view_row(
    result: SearchResult,
    *,
    rank: int,
) -> SearchResultViewRow:
    return SearchResultViewRow(
        context_name=result.context_name,
        label=(
            f"[{rank} {_search_result_kind_label(result)} {result.uid[:8]}]"
            + (
                f" · {_search_result_annotation(result)}"
                if _search_result_annotation(result)
                else ""
            )
        ),
        content=result.content,
    )


def render_search_results(response: SearchResponse | None) -> str:
    """Render only rows whose request still matches the visible controls."""

    if response is None:
        return "SEARCH RESULTS\n  Enter a query to search the selected scope."
    rows = tuple(
        _search_result_view_row(result, rank=index)
        for index, result in enumerate(response.results, start=1)
    )
    return render_grouped_search_results(
        rows,
        related_query=response.related_query,
    )


def project_search_results_clipboard(
    response: SearchResponse | None,
    *,
    focused_index: int = 0,
    whole_result_set: bool = False,
) -> SearchResultsClipboardProjection:
    """Project host-resolved results without checkbox or viewport wrapping."""

    if response is None or not response.results:
        raise ValueError("There are no Search results to copy.")
    count = len(response.results)
    if whole_result_set:
        suffix = "Result" if count == 1 else "Results"
        return SearchResultsClipboardProjection(
            text=render_search_results(response),
            scope="RESULT_SET",
            label=f"complete Search result set · {count} {suffix}",
            result_count=count,
        )
    if isinstance(focused_index, bool) or not 0 <= focused_index < count:
        raise ValueError("The focused Search result is no longer available.")
    result = response.results[focused_index]
    return SearchResultsClipboardProjection(
        text=render_grouped_search_results(
            (
                _search_result_view_row(
                    result,
                    rank=focused_index + 1,
                ),
            ),
            related_query=response.related_query,
        ),
        scope="FOCUSED",
        label=(
            f"Search result {focused_index + 1} · "
            f"{safe_terminal_text(result.context_name)} · "
            f"{safe_terminal_text(_search_result_kind_label(result))}"
        ),
        result_count=1,
    )


def _results_frame_title(turn: BackgroundExecutorTurn[SearchResponse]) -> str:
    if turn.busy:
        return f"RESULTS · SEARCHING {busy_suffix(turn.frame)}"
    return "RESULTS"


def _search_save_as_available(
    response: SearchResponse | None,
    *,
    busy: bool,
) -> bool:
    """Expose outcome controls only for one completed nonempty result set."""

    return response is not None and bool(response.results) and not busy


def run_search_workbench(
    names: Sequence[str],
    *,
    current: str,
    initial_target: str,
    initial_targets: Sequence[str] | None = None,
    initial_include_descendants: bool,
    initial_follow_embeds: bool,
    limit: int,
    run_search: SearchRunner,
    annotations: Mapping[str, SourceDisplayValue] | None = None,
    local_context_names: Sequence[str] | None = None,
    validate_save_location: SearchSaveLocationValidator | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    clipboard_writer: Callable[[str], None] | None = None,
) -> SearchWorkbenchResult:
    """Search repeatedly while keeping query, targets, scope, and results visible."""

    catalog = tuple(names)
    if (
        not catalog
        or len(set(catalog)) != len(catalog)
        or any(not isinstance(name, str) or not name for name in catalog)
    ):
        raise ValueError("Search requires a distinct readable Context catalog.")
    staged_initial_targets = tuple(
        dict.fromkeys((initial_target,) if initial_targets is None else initial_targets)
    )
    if (
        current not in catalog
        or initial_target not in catalog
        or not staged_initial_targets
        or any(name not in catalog for name in staged_initial_targets)
    ):
        raise ValueError("Search's initial Context is outside the readable catalog.")
    if not callable(run_search):
        raise ValueError("Search requires a search controller.")
    if require_tty:
        require_interactive_terminal(
            "Interactive Search",
            snapshot_hint='Pass a query, for example: mem search "parking".',
        )

    labels = dict(annotations or {})
    if set(labels) - set(catalog):
        raise ValueError("Search Context annotations are outside the catalog.")
    try:
        for annotation in labels.values():
            normalize_source_display_tokens(annotation)
    except (TypeError, ValueError) as error:
        raise ValueError("Search received an invalid Context annotation.") from error
    local_catalog = tuple(
        dict.fromkeys(catalog if local_context_names is None else local_context_names)
    )
    if any(not isinstance(name, str) or not name for name in local_catalog):
        raise ValueError("Search local Context names must be nonblank text.")

    response: SearchResponse | None = None
    result_selection: FlatMultiSelectionState | None = None
    status = {"value": "ENTER A QUERY"}
    copy_receipt: PlainTextClipboardReceipt | None = None
    background_turn: BackgroundExecutorTurn[SearchResponse] = BackgroundExecutorTurn()

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
        input_name="search-context",
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
        name="search-query",
    )
    initial_save_location = suggest_fresh_context_name(
        _search_save_location_stem(initial_target, "search"),
        local_catalog,
    )
    save_panel = RetrieveAnswerSavePanel(
        content_summary=lambda: (
            f"{len(result_selection.selected_uids)} CHECKED SEARCH RESULT(S)"
            if result_selection is not None
            else "CHECK SEARCH RESULTS TO SAVE"
        ),
        action_label=lambda mode: (
            f"SAVE {len(result_selection.selected_uids)} CHECKED AS {mode}"
            if result_selection is not None
            else "SAVE CHECKED SEARCH RESULTS"
        ),
        initial_location=initial_save_location,
        context_names=local_catalog,
        current_context=current if current in local_catalog else None,
        validate_location=validate_save_location,
        input_name="search-save-location",
        on_status=scope_status,
        mode_options=(
            HorizontalChoiceOption(
                "COPY",
                "COPY",
                "Create independent Memory values with fresh identities.",
            ),
            HorizontalChoiceOption(
                "REFERENCE",
                "REFERENCE",
                "Retain immutable read-only snapshots of the selected values.",
            ),
            HorizontalChoiceOption(
                "EMBED",
                "EMBED",
                "Create read-only live links that follow their Source Memories.",
            ),
        ),
        initial_mode="COPY",
    )
    save_mode_control = save_panel.mode_control
    assert save_mode_control is not None
    save_location_edit = {"edited": False, "programmatic": False}

    def save_location_changed(_buffer) -> None:
        if not save_location_edit["programmatic"]:
            save_location_edit["edited"] = True

    save_panel.name.input.buffer.on_text_changed += save_location_changed

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
        # Search now follows the service-wide one-column session grammar. Result
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
    # SAVE is an outcome action, not search setup. Keep it out of the canvas
    # and keyboard topology until a completed search has a nonempty result.
    save_container = ConditionalContainer(
        save_panel.container,
        filter=Condition(
            lambda: _search_save_as_available(
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
        TuiRegion(save_container),
        TuiRegion(footer),
    )
    app: Application[SearchWorkbenchResult] = Application(
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

    save_tree_focus = has_focus(save_panel.tree_control)
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
        | has_focus(save_mode_control)
        | has_focus(save_panel.name.input)
        | has_focus(save_panel.browse_control)
        | has_focus(save_panel.action_control)
        | save_tree_focus
    )
    non_search_focus = search_return_focus
    read_non_search_focus = (
        non_search_focus
        & ~has_focus(scope.input)
        & ~has_focus(save_panel.name.input)
    )
    bind_session_help(
        bindings,
        filter=read_non_search_focus,
        app_input=app_input,
        app_output=app_output,
        study_surface="search",
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
            request = SearchRequest(
                query=search_area.text.strip(),
                target_names=request_targets,
                include_descendants=request_descendants,
                follow_embeds=scope.follow_embeds,
                limit=limit,
            )
        except ValueError as error:
            status["value"] = str(error)
            return "HANDLED"

        def work() -> SearchResponse:
            next_response = run_search(request)
            if not isinstance(next_response, SearchResponse):
                raise ValueError("Search controller returned an invalid response.")
            if next_response.request != request:
                raise ValueError(
                    "Search inputs changed while the request was running. "
                    "Run the search again."
                )
            return next_response

        def commit(next_response: SearchResponse) -> None:
            nonlocal copy_receipt, response, result_selection
            response = next_response
            copy_receipt = None
            result_selection = (
                FlatMultiSelectionState(
                    tuple(
                        SelectionOption(
                            str(index),
                            _search_result_selection_label(
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
                    save_panel.set_location(
                        suggest_fresh_context_name(
                            _search_save_location_stem(
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
            app.exit(result=SearchWorkbenchResult("CLOSED", response))

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
                0 if result_selection is None else int(result_selection.cursor_uid)
            )
            projection = project_search_results_clipboard(
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

    def _apply_save(event) -> SurfaceActionResult:
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
        try:
            destination = save_panel.validate_candidate()
        except (OSError, TypeError, ValueError) as error:
            status["value"] = str(error)
            event.app.layout.focus(save_panel.name.input)
            return "HANDLED"
        mode = save_panel.selected_mode
        assert mode is not None
        event.app.exit(
            result=SearchWorkbenchResult(
                "SAVE",
                response,
                selected_indices,
                cast(SaveContextMode, mode),
                destination,
            )
        )
        return "HANDLED"

    def visible_surfaces() -> tuple[FocusSurface, ...]:
        if scope.browser_open:
            return (scope.browser_surface(uid_prefix="search-scope"),)
        if save_panel.browser_open:
            return (save_panel.browser_surface(uid_prefix="search-save"),)
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
                save_panel.normal_surfaces(
                    activate_action=_apply_save,
                    uid_prefix="search-save",
                )
            )
        return tuple(surfaces)

    surface_focus = SurfaceFocusController(visible_surfaces)
    bind_surface_navigation(bindings, surface_focus)
    scope.bind_keybindings(bindings)
    save_panel.bind_keybindings(bindings)

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
        event.app.exit(result=SearchWorkbenchResult("CLOSED", response))

    @bindings.add(
        "backspace",
        filter=(
            read_non_search_focus
            & ~save_tree_focus
            & ~has_focus(scope.tree_control)
        ),
        eager=True,
    )
    def _back_to_search(event) -> None:
        event.app.layout.focus(search_area)
        search_area.buffer.cursor_position = len(search_area.text)
        event.app.invalidate()

    def _return_to_search(event) -> bool:
        if event.app.layout.has_focus(search_area):
            return False
        event.app.layout.focus(search_area)
        search_area.buffer.cursor_position = len(search_area.text)
        return True

    @bindings.add("escape", eager=True)
    def _escape(event) -> None:
        if not scope.close_browser(event) and not save_panel.close_browser(event):
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
        return SearchWorkbenchResult("CLOSED", response)
    if not isinstance(result, SearchWorkbenchResult):
        raise ValueError("Search workbench returned an invalid result.")
    return result
