"""Interactive Find search, target, scope, and result contracts."""

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.commands.find_search_workbench import (
    FindSearchRequest,
    FindSearchResponse,
    FindSearchResult,
    render_find_search_results,
    run_find_search_workbench,
)


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
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CLOSED"
    assert result.response is None
    assert requests == []


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
        # Search -> Targets; expand task-1; select its child; Scope: exclude
        # embeds; Results -> Search; submit and close after completion.
        pipe_input.send_text("\t\x1b[C\x1b[B \t\x1b[B\x1b[D\t\tneedle\r\x03")
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
        # Enter checks the child. Slash is then the explicit return to Search;
        # if Enter had already returned, slash would become part of the query.
        pipe_input.send_text("\t\x1b[C\x1b[B\r/needle\r\x03")
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
        # Enter a query, clear the only checked target, return to Search, and
        # submit. The target interaction succeeds; request construction blocks.
        pipe_input.send_text("needle\t\r/\r\x03")
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


def test_scope_can_collapse_multiple_targets_to_the_most_recent_choice():
    requests: list[FindSearchRequest] = []

    def search(request: FindSearchRequest) -> FindSearchResponse:
        requests.append(request)
        return FindSearchResponse(request, "CURRENT", ())

    with create_pipe_input() as pipe_input:
        # Select child, move to Scope, and change MULTIPLE to SINGLE. The most
        # recent explicit target remains checked before returning to Search.
        pipe_input.send_text("\t\x1b[C\x1b[B\r\t\x1b[D/needle\r\x03")
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
            ("task-1/source",),
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


def test_selecting_a_collapsed_parent_checks_its_hidden_descendants():
    requests: list[FindSearchRequest] = []

    def search(request: FindSearchRequest) -> FindSearchResponse:
        requests.append(request)
        return FindSearchResponse(request, "CURRENT", ())

    with create_pipe_input() as pipe_input:
        # The initial cursor is the second collapsed root. Select the first root
        # without expanding it, then remove the initial target and search.
        pipe_input.send_text("needle\t\x1b[A\r\x1b[B\r/\r\x03")
        run_find_search_workbench(
            ("task", "task/a", "task/a/deep", "task/b", "other"),
            current="other",
            initial_target="other",
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
            ("task", "task/a", "task/a/deep", "task/b"),
            include_descendants=False,
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
    assert "[1 related memory memory-o] Clinic appointment" in rendered
