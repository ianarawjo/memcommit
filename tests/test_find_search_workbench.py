"""Interactive Find search, target, scope, and result contracts."""

import threading
import time

import pytest
from prompt_toolkit.data_structures import Size
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.commands.background_turn import BackgroundExecutorTurn
from memcommit.commands.find_search_workbench import (
    FindSearchRequest,
    FindSearchResponse,
    FindSearchResult,
    _find_save_as_available,
    _find_result_selection_label,
    _results_frame_title,
    project_find_results_clipboard,
    render_find_search_results,
    run_find_search_workbench,
)


class Terminal80x24(DummyOutput):
    def get_size(self) -> Size:
        return Size(rows=24, columns=80)


_SHIFT_TAB = "\x1b[Z"


def test_blank_workbench_does_not_search_before_the_person_submits():
    requests: list[FindSearchRequest] = []

    def search(request: FindSearchRequest) -> FindSearchResponse:
        requests.append(request)
        return FindSearchResponse(request, "CURRENT", ())

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x03")
        result = run_find_search_workbench(
            ("task-1", "task-1/source"),
            current="task-1",
            initial_target="task-1",
            initial_include_descendants=True,
            initial_follow_embeds=True,
            limit=5,
            run_search=search,
            app_input=pipe_input,
            app_output=Terminal80x24(),
            require_tty=False,
        )

    assert result.status == "CLOSED"
    assert result.response is None
    assert requests == []


def test_results_title_repeats_animated_search_progress_above_results():
    turn: BackgroundExecutorTurn[FindSearchResponse] = BackgroundExecutorTurn()

    assert _results_frame_title(turn) == "RESULTS"

    turn.busy = True
    turn.frame = 2

    assert _results_frame_title(turn) == "RESULTS · SEARCHING …"


def test_save_as_is_available_only_after_a_completed_nonempty_search():
    request = FindSearchRequest("needle", ("task-1",))
    empty = FindSearchResponse(request, "CURRENT", ())
    found = FindSearchResponse(
        request,
        "CURRENT",
        (
            FindSearchResult(
                context_name="task-1",
                kind="memory",
                uid="memory-one",
                content="Matched content",
            ),
        ),
    )

    assert not _find_save_as_available(None, busy=False)
    assert not _find_save_as_available(empty, busy=False)
    assert not _find_save_as_available(found, busy=True)
    assert _find_save_as_available(found, busy=False)


def test_blank_workbench_initial_focus_accepts_the_query_immediately():
    requests: list[FindSearchRequest] = []

    def search(request: FindSearchRequest) -> FindSearchResponse:
        requests.append(request)
        return FindSearchResponse(request, "CURRENT", ())

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("needle\r\x03")
        run_find_search_workbench(
            ("task-1",),
            current="task-1",
            initial_target="task-1",
            initial_include_descendants=True,
            initial_follow_embeds=True,
            limit=5,
            run_search=search,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert requests == [
        FindSearchRequest(
            "needle",
            ("task-1",),
            include_descendants=False,
        )
    ]


def test_workbench_submits_multiple_targets_and_independent_scope_choices():
    requests: list[FindSearchRequest] = []

    def search(request: FindSearchRequest) -> FindSearchResponse:
        requests.append(request)
        return FindSearchResponse(
            request=request,
            mode="CURRENT",
            results=(
                FindSearchResult(
                    context_name="task-1/source",
                    kind="memory",
                    uid="memory-one",
                    content="Matched content",
                ),
            ),
        )

    with create_pipe_input() as pipe_input:
        # Search -> Browse; check the child and close the transient tree. Move
        # through Range to Embeds, exclude embeds, then return and search.
        pipe_input.send_text(
            _SHIFT_TAB * 3
            + "\r\x1b[B\r\t\t\t\x1b[D/needle\r\x03"
        )
        result = run_find_search_workbench(
            ("task-1", "task-1/source", "other"),
            current="task-1",
            initial_target="task-1",
            initial_include_descendants=False,
            initial_follow_embeds=True,
            limit=7,
            run_search=search,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert requests == [
        FindSearchRequest(
            query="needle",
            target_names=("task-1", "task-1/source"),
            include_descendants=False,
            follow_embeds=False,
            limit=7,
        )
    ]
    assert result.response is not None
    assert result.response.request == requests[0]


def test_enter_checks_target_and_stays_in_targets_until_explicit_return():
    requests: list[FindSearchRequest] = []

    def search(request: FindSearchRequest) -> FindSearchResponse:
        requests.append(request)
        return FindSearchResponse(request, "CURRENT", ())

    with create_pipe_input() as pipe_input:
        # Enter checks the child and leaves Browse open. Tab explicitly closes
        # the transient tree; Slash then returns from Browse to Search.
        pipe_input.send_text(
            _SHIFT_TAB * 3 + "\r\x1b[B\r\t/needle\r\x03"
        )
        run_find_search_workbench(
            ("task-1", "task-1/source"),
            current="task-1",
            initial_target="task-1",
            initial_include_descendants=False,
            initial_follow_embeds=True,
            limit=5,
            run_search=search,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert requests == [
        FindSearchRequest(
            "needle",
            ("task-1", "task-1/source"),
            include_descendants=False,
        )
    ]


def test_empty_target_selection_is_staged_but_rejected_when_search_runs():
    requests: list[FindSearchRequest] = []

    def search(request: FindSearchRequest) -> FindSearchResponse:
        requests.append(request)
        return FindSearchResponse(request, "CURRENT", ())

    with create_pipe_input() as pipe_input:
        # Enter a query, open Browse, clear the only checked target, close the
        # tree, and submit. Request construction rejects the staged empty set.
        pipe_input.send_text(
            "needle" + _SHIFT_TAB * 3 + "\r\r\t/\r\x03"
        )
        result = run_find_search_workbench(
            ("task-1",),
            current="task-1",
            initial_target="task-1",
            initial_include_descendants=False,
            initial_follow_embeds=True,
            limit=5,
            run_search=search,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert requests == []
    assert result.response is None


def test_direct_context_input_collapses_multiple_targets_to_one_exact_choice():
    requests: list[FindSearchRequest] = []

    def search(request: FindSearchRequest) -> FindSearchResponse:
        requests.append(request)
        return FindSearchResponse(request, "CURRENT", ())

    with create_pipe_input() as pipe_input:
        # Repeated CLI operands seed a multi-target range. Confirming the exact
        # direct-input value replaces that richer Browse selection with one.
        pipe_input.send_text(
            "needle" + _SHIFT_TAB * 4 + "\r" + "\t" * 4 + "\r\x03"
        )
        run_find_search_workbench(
            ("task-1", "task-1/source"),
            current="task-1",
            initial_target="task-1",
            initial_targets=("task-1", "task-1/source"),
            initial_include_descendants=False,
            initial_follow_embeds=True,
            limit=5,
            run_search=search,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert requests == [
        FindSearchRequest(
            "needle",
            ("task-1/source",),
            include_descendants=False,
        )
    ]


def test_direct_context_input_accepts_slashes_without_triggering_search_shortcuts():
    requests: list[FindSearchRequest] = []

    def search(request: FindSearchRequest) -> FindSearchResponse:
        requests.append(request)
        return FindSearchResponse(request, "CURRENT", ())

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(
            "needle"
            + _SHIFT_TAB * 4
            + "\x15task-1/queue\r"
            + "\t" * 4
            + "\r\x03"
        )
        run_find_search_workbench(
            ("task-1", "task-1/queue"),
            current="task-1",
            initial_target="task-1",
            initial_include_descendants=False,
            initial_follow_embeds=True,
            limit=5,
            run_search=search,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert requests == [
        FindSearchRequest(
            "needle",
            ("task-1/queue",),
            include_descendants=False,
        )
    ]


@pytest.mark.parametrize("back_key", ["\x1b", "\x7f"])
def test_escape_and_backspace_return_read_only_scope_to_the_search(back_key):
    requests: list[FindSearchRequest] = []

    def search(request: FindSearchRequest) -> FindSearchResponse:
        requests.append(request)
        return FindSearchResponse(request, "CURRENT", ())

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(f"\t{back_key}needle\r\x03")
        run_find_search_workbench(
            ("task-1",),
            current="task-1",
            initial_target="task-1",
            initial_include_descendants=True,
            initial_follow_embeds=True,
            limit=5,
            run_search=search,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert requests == [
        FindSearchRequest(
            "needle",
            ("task-1",),
            include_descendants=False,
        )
    ]


def test_escape_closes_the_root_search_without_running_find():
    requests: list[FindSearchRequest] = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        result = run_find_search_workbench(
            ("task-1",),
            current="task-1",
            initial_target="task-1",
            initial_include_descendants=True,
            initial_follow_embeds=True,
            limit=5,
            run_search=lambda request: requests.append(request),  # type: ignore[arg-type,return-value]
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CLOSED"
    assert result.response is None
    assert requests == []


def test_initial_descendant_reach_is_materialized_as_exact_checked_targets():
    requests: list[FindSearchRequest] = []

    def search(request: FindSearchRequest) -> FindSearchResponse:
        requests.append(request)
        return FindSearchResponse(request, "CURRENT", ())

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("needle\r\x03")
        run_find_search_workbench(
            ("task", "task/a", "task/a/deep", "task/b", "other"),
            current="task",
            initial_target="task",
            initial_include_descendants=True,
            initial_follow_embeds=True,
            limit=5,
            run_search=search,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert requests == [
        FindSearchRequest(
            "needle",
            ("task", "task/a", "task/a/deep", "task/b"),
            include_descendants=False,
        )
    ]


def test_profile_target_freezes_the_whole_readable_catalog_without_leaking_a_locator():
    requests: list[FindSearchRequest] = []

    def search(request: FindSearchRequest) -> FindSearchResponse:
        requests.append(request)
        return FindSearchResponse(request, "CURRENT", ())

    with create_pipe_input() as pipe_input:
        # Browse exposes the virtual Profile row above the Context namespace.
        pipe_input.send_text(
            "needle" + _SHIFT_TAB * 3 + "\r\x1b[A\r\t/\r\x03"
        )
        run_find_search_workbench(
            ("task", "task/source", "other"),
            current="task",
            initial_target="task",
            initial_include_descendants=False,
            initial_follow_embeds=True,
            limit=5,
            run_search=search,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert requests == [
        FindSearchRequest(
            "needle",
            ("task", "task/source", "other"),
            include_descendants=False,
        )
    ]


def test_context_range_can_expand_one_checked_root_to_its_visible_subtree():
    requests: list[FindSearchRequest] = []

    def search(request: FindSearchRequest) -> FindSearchResponse:
        requests.append(request)
        return FindSearchResponse(request, "CURRENT", ())

    with create_pipe_input() as pipe_input:
        # Range is the second surface above Search; Right includes descendants.
        pipe_input.send_text("needle" + _SHIFT_TAB * 2 + "\x1b[C/\r\x03")
        run_find_search_workbench(
            ("task", "task/source", "task/source/deep", "other"),
            current="task",
            initial_target="task",
            initial_include_descendants=False,
            initial_follow_embeds=True,
            limit=5,
            run_search=search,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert requests == [
        FindSearchRequest(
            "needle",
            ("task", "task/source", "task/source/deep"),
            include_descendants=False,
        )
    ]


def test_unchecked_descendant_range_is_not_reintroduced_at_search_time():
    requests: list[FindSearchRequest] = []

    def search(request: FindSearchRequest) -> FindSearchResponse:
        requests.append(request)
        return FindSearchResponse(request, "CURRENT", ())

    with create_pipe_input() as pipe_input:
        # The initial root includes descendants. Browse starts expanded; moving
        # to task/a and clearing it removes that complete visible subtree.
        pipe_input.send_text(
            "needle" + _SHIFT_TAB * 3 + "\r\x1b[B\r\t/\r\x03"
        )
        run_find_search_workbench(
            ("task", "task/a", "task/a/deep", "task/b"),
            current="task",
            initial_target="task",
            initial_include_descendants=True,
            initial_follow_embeds=True,
            limit=5,
            run_search=search,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert requests == [
        FindSearchRequest(
            "needle",
            ("task", "task/b"),
            include_descendants=False,
        )
    ]


def test_selecting_a_parent_checks_its_descendants_in_the_expanded_browser():
    requests: list[FindSearchRequest] = []

    def search(request: FindSearchRequest) -> FindSearchResponse:
        requests.append(request)
        return FindSearchResponse(request, "CURRENT", ())

    with create_pipe_input() as pipe_input:
        # Browse starts fully expanded. Move from the second root to task, check
        # its subtree, return to other, remove it, then freeze the visible set.
        pipe_input.send_text(
            "needle"
            + _SHIFT_TAB * 3
            + "\r"
            + "\x1b[A" * 4
            + "\r"
            + "\x1b[B" * 4
            + "\r\t/\r\x03"
        )
        run_find_search_workbench(
            ("task", "task/a", "task/a/deep", "task/b", "other"),
            current="other",
            initial_target="other",
            initial_include_descendants=True,
            initial_follow_embeds=True,
            limit=5,
            run_search=search,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert requests == [
        FindSearchRequest(
            "needle",
            ("task", "task/a", "task/a/deep", "task/b"),
            include_descendants=False,
        )
    ]


def test_browser_arrows_move_between_contexts_and_enter_activates_the_row():
    requests: list[FindSearchRequest] = []

    def search(request: FindSearchRequest) -> FindSearchResponse:
        requests.append(request)
        return FindSearchResponse(request, "CURRENT", ())

    with create_pipe_input() as pipe_input:
        # Open Browse, add second, then remove first; the exact checked set is
        # frozen when the search runs.
        pipe_input.send_text(
            "needle"
            + _SHIFT_TAB * 3
            + "\r\x1b[B\r\x1b[A\r\t/\r\x03"
        )
        run_find_search_workbench(
            ("first", "second"),
            current="first",
            initial_target="first",
            initial_include_descendants=False,
            initial_follow_embeds=True,
            limit=5,
            run_search=search,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert requests == [
        FindSearchRequest(
            "needle",
            ("second",),
            include_descendants=False,
        )
    ]


def test_embeds_choice_is_independent_and_slash_returns_to_search():
    requests: list[FindSearchRequest] = []

    def search(request: FindSearchRequest) -> FindSearchResponse:
        requests.append(request)
        return FindSearchResponse(request, "CURRENT", ())

    with create_pipe_input() as pipe_input:
        # Embeds is immediately above Search. Left excludes it; Slash returns
        # to Search without changing the query and Enter runs it.
        pipe_input.send_text("needle" + _SHIFT_TAB + "\x1b[D/\r\x03")
        run_find_search_workbench(
            ("task",),
            current="task",
            initial_target="task",
            initial_include_descendants=False,
            initial_follow_embeds=True,
            limit=5,
            run_search=search,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert requests == [
        FindSearchRequest(
            "needle",
            ("task",),
            include_descendants=False,
            follow_embeds=False,
        )
    ]


def test_result_renderer_keeps_related_results_separate_from_primary_matches():
    request = FindSearchRequest("health insurance", ("task-3",))
    response = FindSearchResponse(
        request=request,
        mode="CURRENT",
        results=(
            FindSearchResult(
                context_name="task-3",
                kind="memory",
                uid="memory-one",
                content="Clinic appointment",
                relevance="related",
            ),
        ),
        related_query="healthcare",
    )

    rendered = render_find_search_results(response)

    assert "PRIMARY MATCHES\n  (none)" in rendered
    assert "RELATED RESULTS" in rendered
    assert "Broader search: healthcare" in rendered
    assert "[1 memory memory-o] · RELATED Clinic appointment" in rendered


def test_search_selection_row_keeps_complete_content_without_ellipsis():
    content = "A complete first line.\nA complete second line with its suffix."
    label = _find_result_selection_label(
        FindSearchResult(
            context_name="task/source",
            kind="memory",
            uid="memory-one",
            content=content,
            relevance="related",
        ),
        number=3,
    )

    assert label == (
        "3 [memory-o] A complete first line. A complete second line with its "
        "suffix. [task/source · MEMORY · RELATED]"
    )
    assert "…" not in label


def test_find_clipboard_projects_focused_result_and_complete_ranked_set():
    request = FindSearchRequest("parking", ("task",))
    response = FindSearchResponse(
        request,
        "CURRENT",
        (
            FindSearchResult(
                context_name="task/a",
                kind="memory",
                uid="memory-one",
                content="Lot A is closed.",
            ),
            FindSearchResult(
                context_name="task/b",
                kind="ref",
                uid="reference-two",
                content="Use the east garage.",
            ),
        ),
    )

    focused = project_find_results_clipboard(response, focused_index=1)
    assert focused.scope == "FOCUSED"
    assert focused.result_count == 1
    assert "[2 memory ref referenc] Use the east garage." in focused.text
    assert "Lot A is closed." not in focused.text

    complete = project_find_results_clipboard(response, whole_result_set=True)
    assert complete.scope == "RESULT_SET"
    assert complete.result_count == 2
    assert complete.text == render_find_search_results(response)
    assert "Lot A is closed." in complete.text
    assert "Use the east garage." in complete.text


def test_find_y_and_uppercase_y_copy_focused_results_then_complete_set():
    copied: list[str] = []
    search_started = threading.Event()

    def search(request: FindSearchRequest) -> FindSearchResponse:
        search_started.set()
        return FindSearchResponse(
            request,
            "CURRENT",
            (
                FindSearchResult(
                    context_name="task/a",
                    kind="memory",
                    uid="memory-one",
                    content="Lot A is closed.",
                ),
                FindSearchResult(
                    context_name="task/b",
                    kind="memory",
                    uid="memory-two",
                    content="Use the east garage.",
                ),
            ),
        )

    with create_pipe_input() as pipe_input:

        def drive() -> None:
            pipe_input.send_text("parking\r")
            assert search_started.wait(3)
            time.sleep(0.1)
            pipe_input.send_text("y\x1b[ByY\x03")

        driver = threading.Thread(target=drive, daemon=True)
        driver.start()
        result = run_find_search_workbench(
            ("task", "task/a", "task/b"),
            current="task",
            initial_target="task",
            initial_include_descendants=True,
            initial_follow_embeds=True,
            limit=5,
            run_search=search,
            clipboard_writer=copied.append,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
        driver.join(timeout=3)

    assert result.status == "CLOSED"
    assert not driver.is_alive()
    assert "[1 memory memory-o] Lot A is closed." in copied[0]
    assert "Use the east garage." not in copied[0]
    assert "[2 memory memory-t] Use the east garage." in copied[1]
    assert "Lot A is closed." not in copied[1]
    assert "Lot A is closed." in copied[2]
    assert "Use the east garage." in copied[2]


def test_find_search_keeps_lower_and_upper_y_as_text():
    requests: list[FindSearchRequest] = []

    def search(request: FindSearchRequest) -> FindSearchResponse:
        requests.append(request)
        return FindSearchResponse(request, "CURRENT", ())

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("yY parking\r\x03")
        run_find_search_workbench(
            ("task",),
            current="task",
            initial_target="task",
            initial_include_descendants=False,
            initial_follow_embeds=True,
            limit=5,
            run_search=search,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert requests[0].query == "yY parking"


def test_checked_result_copy_returns_exact_materialization_request():
    def search(request: FindSearchRequest) -> FindSearchResponse:
        return FindSearchResponse(
            request,
            "CURRENT",
            (
                FindSearchResult(
                    context_name="task",
                    kind="memory",
                    uid="memory-one",
                    content="Accessible entrance",
                    source_context_name="task",
                    source_context_uid="context-one",
                    source_memory_uid="memory-one",
                ),
            ),
        )

    with create_pipe_input() as pipe_input:

        def send_after_search() -> None:
            pipe_input.send_text("accessibility\r")
            time.sleep(0.15)
            # Check result, visit COPY, replace the exact Save Location, then
            # activate the reviewed To Do row.
            pipe_input.send_text("\r\t\t\x15task/results/accessibility\t\r")

        sender = threading.Thread(target=send_after_search)
        sender.start()
        result = run_find_search_workbench(
            ("task",),
            current="task",
            initial_target="task",
            initial_include_descendants=False,
            initial_follow_embeds=True,
            limit=5,
            run_search=search,
            validate_save_location=lambda value: value,
            app_input=pipe_input,
            app_output=Terminal80x24(),
            require_tty=False,
        )
        sender.join()

    assert result.status == "MATERIALIZE"
    assert result.selected_result_indices == (0,)
    assert result.materialize_as == "COPY"
    assert result.save_location == "task/results/accessibility"
