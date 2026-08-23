"""Semantic find traversal, validation, privacy, and CLI contracts."""

import json
import subprocess
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.commands.find import (
    FIND_OUTSIDE_CANCELLATION,
    FIND_OUTSIDE_CONFIRMATION,
    _apply_show_result,
    _handle_find_turn,
    _initial_chat_state,
    _load_find_scope_roots,
    _run_find_search_request,
    _run_read_only_find_command,
    _show_result_proposal,
    _supplement_namespace_branch_coverage,
)
from memcommit.authority.access import resolve_context_access
from memcommit.commands.readable_context_catalog import (
    freeze_readable_context_catalog,
)
from memcommit.commands.find_chat_shell import (
    FindChatMessage,
)
from memcommit.commands.find_search_workbench import (
    FindSearchRequest,
    FindSearchResponse,
)
from memcommit.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.find_turn_dialogue import FindTurnAction
from memcommit.search import (
    FindError,
    SearchCandidate,
    SearchMatch,
    collect_candidates,
    collect_candidates_from_roots,
    rank_candidates,
)
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)
HIDDEN_SECRET = "The confidential contract ceiling is 4.2 million dollars."


class KeywordProvider:
    """Test provider that selects candidates by local payload substring."""

    def __init__(self):
        self.calls = []

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls.append((prompt, operation, output_schema))
        payload = json.loads(prompt.split("FIND PAYLOAD:\n", 1)[1])
        query = payload["query"].casefold()
        matches = []
        for candidate in payload["candidates"]:
            searchable = " ".join(
                str(value) for key, value in candidate.items() if key != "candidate_id"
            ).casefold()
            if query in searchable:
                matches.append({"candidate_id": candidate["candidate_id"]})
        return json.dumps(
            {
                "matches": matches[: payload["limit"]],
                "related_query": "",
                "related_matches": [],
            }
        )


def _candidate(
    candidate_id: str = "c000001",
    *,
    content: str = "local canonical content",
) -> SearchCandidate:
    item = Memory(uid="memory-one", content=content)
    return SearchCandidate(
        candidate_id=candidate_id,
        kind="memory",
        context_uid="context-one",
        context_names=("owner",),
        item=item,
        search_text=content,
    )


def test_collect_candidates_is_recursive_by_default_and_direct_when_requested():
    root = ops.init("root")
    root_memory = ops.add(root, "root fact")
    child = ops.init("namespace/child")
    child_memory = ops.add(child, "nested fact")
    ops.embed(child, root)

    recursive = collect_candidates(root)
    direct = collect_candidates(root, recursive=False)

    assert [candidate.item for candidate in recursive] == [
        root_memory,
        child_memory,
    ]
    assert [candidate.item for candidate in direct] == [root_memory]


def test_collect_candidates_from_roots_deduplicates_namespace_and_embed():
    root = ops.init("task-3")
    child = ops.init("task-3/personal-memory")
    memory = ops.add(child, "Healthcare preparation detail")
    ops.embed(child, root)

    candidates = collect_candidates_from_roots((root, child))

    assert [candidate.item for candidate in candidates] == [memory]


def test_interactive_scope_separates_namespace_descendants_from_embeds(
    isolated_store,
):
    store = MemoryStore()
    root = ops.init("scope")
    root_memory = ops.add(root, "root fact")
    child = ops.init("scope/child")
    child_memory = ops.add(child, "child fact")
    embedded = ops.init("outside")
    embedded_memory = ops.add(embedded, "embedded fact")
    ops.embed(embedded, root)
    for context in (root, child, embedded):
        store.save(context)
    store.set_current(root.name)
    access = resolve_context_access(
        store,
        root.name,
        current_name=root.name,
        required_permission="READ",
    )
    catalog = freeze_readable_context_catalog(store, access)

    exact_roots = _load_find_scope_roots(
        catalog,
        (root.name,),
        include_descendants=False,
        follow_embeds=False,
    )
    below_roots = _load_find_scope_roots(
        catalog,
        (root.name,),
        include_descendants=True,
        follow_embeds=False,
    )
    embedded_roots = _load_find_scope_roots(
        catalog,
        (root.name,),
        include_descendants=False,
        follow_embeds=True,
    )

    assert [
        candidate.item.uid
        for candidate in collect_candidates_from_roots(
            exact_roots,
            recursive=False,
        )
    ] == [root_memory.uid]
    assert {
        candidate.item.uid
        for candidate in collect_candidates_from_roots(
            below_roots,
            recursive=False,
        )
    } == {root_memory.uid, child_memory.uid}
    assert {
        candidate.item.uid
        for candidate in collect_candidates_from_roots(
            embedded_roots,
            recursive=True,
        )
    } == {root_memory.uid, embedded_memory.uid}


def test_interactive_find_searches_multiple_exact_targets_in_one_provider_turn(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    first = ops.init("first")
    first_memory = ops.add(first, "shared needle from first")
    second = ops.init("second")
    second_memory = ops.add(second, "shared needle from second")
    omitted = ops.init("omitted")
    omitted_memory = ops.add(omitted, "shared needle outside scope")
    for context in (first, second, omitted):
        store.save(context)
    store.set_current(first.name)
    access = resolve_context_access(
        store,
        first.name,
        current_name=first.name,
        required_permission="READ",
    )
    catalog = freeze_readable_context_catalog(store, access)
    provider = KeywordProvider()
    monkeypatch.setattr(
        "memcommit.commands.find.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    request = FindSearchRequest(
        query="shared needle",
        target_names=(first.name, second.name),
        include_descendants=False,
        follow_embeds=False,
        limit=5,
    )

    response = _run_find_search_request(store, catalog, request)

    assert response.request == request
    assert response.mode == "CURRENT"
    assert {result.uid for result in response.results} == {
        first_memory.uid,
        second_memory.uid,
    }
    payload = json.loads(provider.calls[0][0].split("FIND PAYLOAD:\n", 1)[1])
    sent_content = {candidate.get("content", "") for candidate in payload["candidates"]}
    assert first_memory.content in sent_content
    assert second_memory.content in sent_content
    assert omitted_memory.content not in sent_content


def test_explicit_find_repeats_context_for_the_same_multi_root_request(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    first = ops.init("first")
    second = ops.init("second")
    for context in (first, second):
        store.save(context)
    store.set_current(first.name)
    observed: list[FindSearchRequest] = []

    def run_request(_store, _catalog, request):
        observed.append(request)
        return FindSearchResponse(request=request, mode="CURRENT", results=())

    monkeypatch.setattr(
        "memcommit.commands.find._run_find_search_request",
        run_request,
    )
    result = runner.invoke(
        app,
        [
            "search",
            "--context",
            first.name,
            "--context",
            second.name,
            "shared detail",
        ],
    )

    assert result.exit_code == 0, result.output
    assert observed == [
            FindSearchRequest(
                query="shared detail",
                target_names=(first.name, second.name),
                include_descendants=False,
                follow_embeds=False,
                limit=5,
        )
    ]


def test_search_all_and_short_alias_freeze_every_readable_context(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    first = ops.init("first")
    second = ops.init("second")
    for context in (first, second):
        store.save(context)
    store.set_current(first.name)
    observed: list[FindSearchRequest] = []
    authorized: list[tuple[str, ...]] = []

    def run_request(_store, _catalog, request):
        observed.append(request)
        return FindSearchResponse(request=request, mode="CURRENT", results=())

    monkeypatch.setattr(
        "memcommit.commands.find._run_find_search_request",
        run_request,
    )
    monkeypatch.setattr(
        "memcommit.commands.find.authorize_combination",
        lambda accesses: authorized.append(
            tuple(access.display_name for access in accesses)
        ),
    )

    for option in ("--all", "-a"):
        result = runner.invoke(app, ["search", option, "shared detail"])
        assert result.exit_code == 0, result.output + result.stderr
        assert result.output == "ALL READABLE CONTEXTS\n  (no matching items)\n"

    assert observed == [
        FindSearchRequest(
            query="shared detail",
            target_names=(first.name, second.name),
            include_descendants=False,
            follow_embeds=False,
            limit=5,
        ),
        FindSearchRequest(
            query="shared detail",
            target_names=(first.name, second.name),
            include_descendants=False,
            follow_embeds=False,
            limit=5,
        ),
    ]
    assert authorized == [
        (first.name, second.name),
        (first.name, second.name),
    ]


def test_search_all_rejects_explicit_context(isolated_store, monkeypatch):
    store = MemoryStore()
    context = ops.init("first")
    store.save(context)
    store.set_current(context.name)
    monkeypatch.setattr(
        "memcommit.commands.find._run_find_search_request",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("invalid Search scope must not execute")
        ),
    )

    result = runner.invoke(
        app,
        ["search", "--all", "--context", context.name, "shared detail"],
    )

    assert result.exit_code == 1
    assert "--all/-a cannot be combined with --context/-c" in result.stderr


def test_find_cli_multi_roots_keep_descendants_and_embeds_independent(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    frames = {}
    for name, content in (
        ("multi/a", "ROOT_A_SCOPE"),
        ("multi/a/child", "CHILD_A_SCOPE"),
        ("multi/b", "ROOT_B_SCOPE"),
        ("multi/b/child", "CHILD_B_SCOPE"),
        ("embedded", "EMBEDDED_SCOPE"),
    ):
        context = ops.init(name)
        ops.add(context, content)
        frames[name] = context
    ops.embed(frames["embedded"], frames["multi/a"])
    for context in frames.values():
        store.save(context)
    store.set_current("multi/a")
    scope_values = {
        "ROOT_A_SCOPE",
        "CHILD_A_SCOPE",
        "ROOT_B_SCOPE",
        "CHILD_B_SCOPE",
        "EMBEDDED_SCOPE",
    }

    def exposed_memories(*scope_args: str) -> set[str]:
        provider = KeywordProvider()
        monkeypatch.setattr(
            "memcommit.commands.find.connect_codex_chatgpt_provider",
            lambda: provider,
        )
        result = runner.invoke(
            app,
            [
                "search",
                "-c",
                "multi/a",
                "-c",
                "multi/b",
                *scope_args,
                "scope",
            ],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(provider.calls[0][0].split("FIND PAYLOAD:\n", 1)[1])
        return {
            candidate.get("content", "")
            for candidate in payload["candidates"]
        } & scope_values

    assert exposed_memories("--descendants", "--exclude-embeds") == {
        "ROOT_A_SCOPE",
        "CHILD_A_SCOPE",
        "ROOT_B_SCOPE",
        "CHILD_B_SCOPE",
    }
    assert exposed_memories("--context-only", "--follow-embeds") == {
        "ROOT_A_SCOPE",
        "ROOT_B_SCOPE",
        "EMBEDDED_SCOPE",
    }
    assert exposed_memories("--direct") == {
        "ROOT_A_SCOPE",
        "ROOT_B_SCOPE",
    }
    assert exposed_memories(
        "--direct",
        "--descendants",
        "--follow-embeds",
    ) == {
        "ROOT_A_SCOPE",
        "CHILD_A_SCOPE",
        "ROOT_B_SCOPE",
        "CHILD_B_SCOPE",
        "EMBEDDED_SCOPE",
    }


def test_collect_candidates_terminates_cycles_and_visits_shared_context_once():
    root = ops.init("root")
    left = ops.init("left")
    right = ops.init("right")
    shared = ops.init("shared")
    shared_memory = ops.add(shared, "shared fact")
    root.add(left)
    root.add(right)
    left.add(shared)
    right.add(shared)
    shared.add(root)

    candidates = collect_candidates(root)

    assert [candidate.item for candidate in candidates] == [shared_memory]


def test_branch_copies_with_same_memory_uid_remain_distinct_candidates():
    root = ops.init("root")
    first = Context(uid="branch-one", name="branch/one")
    second = Context(uid="branch-two", name="branch/two")
    first.add(Memory(uid="shared-memory", content="first branch version"))
    second.add(Memory(uid="shared-memory", content="second branch version"))
    root.add(first)
    root.add(second)

    candidates = collect_candidates(root)

    assert len(candidates) == 2
    assert {candidate.search_text for candidate in candidates} == {
        "first branch version",
        "second branch version",
    }


def test_memory_refs_search_target_content_and_dedupe_logical_target():
    source = ops.init("source")
    memory = ops.add(source, "latest referenced fact")
    parent = ops.init("parent")
    first_ref = ops.embed_memory(memory, source, parent)
    parent.add(
        MemoryRef(
            uid="second-ref",
            target_context_uid=source.uid,
            target_context_name=source.name,
            target_memory_uid=memory.uid,
            target=memory,
        )
    )
    parent.add(
        MemoryRef(
            uid="dangling-ref",
            target_context_uid="missing-context",
            target_context_name="missing",
            target_memory_uid="missing-memory",
            target=None,
        )
    )
    parent.add(source)

    candidates = collect_candidates(parent)

    assert len(candidates) == 1
    assert candidates[0].item is first_ref
    assert candidates[0].search_text == "latest referenced fact"
    assert candidates[0].context_names == ("parent", "source")


def test_query_context_contributes_name_only_and_never_loads_source(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    hidden = store.create_query_source("contractor-agreements", HIDDEN_SECRET)
    parent = ops.init("facilities-reference")
    ref = ops.reference_query_context(
        "contractor-agreements",
        hidden.uid,
        parent,
    )
    store.save(parent)

    def forbidden(*args, **kwargs):
        raise AssertionError("find opened a concealed query source")

    monkeypatch.setattr(MemoryStore, "load_query_source", forbidden)
    loaded = store.load("facilities-reference")
    candidates = collect_candidates(loaded)
    provider = KeywordProvider()
    matches = rank_candidates(
        "contractor-agreements",
        candidates,
        provider,
    )

    assert len(candidates) == 1
    assert candidates[0].kind == "query_context"
    assert candidates[0].item.uid == ref.uid
    assert candidates[0].search_text == "contractor-agreements"
    assert len(matches) == 1
    prompt = provider.calls[0][0]
    assert "contractor-agreements" in prompt
    assert HIDDEN_SECRET not in prompt
    assert hidden.uid not in prompt
    assert "codex_chatgpt" not in prompt


def test_nested_query_context_is_excluded_by_direct_search():
    root = ops.init("root")
    child = ops.init("child")
    child.add(
        QueryContextRef(
            uid="query-ref",
            name="restricted-policy",
            target_source_uid="source-id",
            provider="codex_chatgpt",
        )
    )
    root.add(child)

    assert collect_candidates(root, recursive=False) == []
    assert [candidate.search_text for candidate in collect_candidates(root)] == [
        "restricted-policy"
    ]


def test_rank_candidates_preserves_model_order_and_dedupes_repeats():
    candidates = [
        _candidate("c000001", content="first"),
        _candidate("c000002", content="second"),
    ]

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            assert operation == "search"
            assert output_schema["properties"]["matches"]["items"]["properties"][
                "candidate_id"
            ]["enum"] == ["c000001", "c000002"]
            return json.dumps(
                {
                    "matches": [
                        {"candidate_id": "c000002"},
                        {"candidate_id": "c000002"},
                        {"candidate_id": "c000001"},
                    ],
                    "related_query": "",
                    "related_matches": [],
                }
            )

    matches = rank_candidates("anything", candidates, Provider(), limit=5)

    assert [match.candidate.candidate_id for match in matches] == ["c000002", "c000001"]
    assert all(match.relevance == "primary" for match in matches)


def test_recursive_find_reserves_room_for_material_omitted_namespace_branch():
    candidates = []
    for index in range(1, 8):
        branch = "baseline" if index <= 5 else "participant"
        item = Memory(uid=f"memory-{index}", content=f"opening hours {index}")
        candidates.append(
            SearchCandidate(
                candidate_id=f"c{index:06d}",
                kind="memory",
                context_uid=f"context-{branch}",
                context_names=(f"task-1/{branch}/building-access",),
                item=item,
                search_text=item.content,
            )
        )
    initial = [SearchMatch(candidate=candidate) for candidate in candidates[:5]]

    matches = _supplement_namespace_branch_coverage(
        "opening hours",
        candidates,
        initial,
        KeywordProvider(),
        root_name="task-1",
        limit=5,
    )

    assert [match.candidate.context_name for match in matches] == [
        "task-1/baseline/building-access",
        "task-1/baseline/building-access",
        "task-1/baseline/building-access",
        "task-1/participant/building-access",
        "task-1/participant/building-access",
    ]


def test_rank_candidates_returns_related_fallback_only_after_no_primary_match():
    candidates = [
        _candidate("c000001", content="clinic appointment"),
        _candidate("c000002", content="dental checkup"),
    ]

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            assert "they do not satisfy the original query" in prompt
            assert output_schema["properties"]["related_matches"]["maxItems"] == 5
            return json.dumps(
                {
                    "matches": [],
                    "related_query": "health and healthcare memories",
                    "related_matches": [
                        {"candidate_id": "c000002"},
                        {"candidate_id": "c000001"},
                    ],
                }
            )

    matches = rank_candidates(
        "health insurance memories",
        candidates,
        Provider(),
        limit=5,
    )

    assert [match.candidate.candidate_id for match in matches] == [
        "c000002",
        "c000001",
    ]
    assert all(match.relevance == "related" for match in matches)
    assert {match.related_query for match in matches} == {
        "health and healthcare memories"
    }


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "not json",
        '{"matches": [], "matches": []}',
        json.dumps([]),
        json.dumps({"wrong": []}),
        json.dumps({"matches": "not-a-list"}),
        json.dumps({"matches": [{}]}),
        json.dumps({"matches": [{"candidate_id": 123}]}),
        json.dumps({"matches": [{"candidate_id": "unknown"}]}),
        json.dumps(
            {
                "matches": [
                    {
                        "candidate_id": "c000001",
                        "content": "model-injected content",
                    }
                ]
            }
        ),
    ],
)
def test_rank_candidates_rejects_malformed_or_unknown_output(raw):
    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            return raw

    with pytest.raises(FindError):
        rank_candidates("query", [_candidate()], Provider())


@pytest.mark.parametrize(
    "response",
    [
        {
            "matches": [{"candidate_id": "c000001"}],
            "related_query": "broader topic",
            "related_matches": [{"candidate_id": "c000001"}],
        },
        {
            "matches": [],
            "related_query": "broader topic",
            "related_matches": [],
        },
        {
            "matches": [],
            "related_query": "",
            "related_matches": [{"candidate_id": "c000001"}],
        },
        {
            "matches": [],
            "related_query": "broader topic",
            "related_matches": [{"candidate_id": "unknown"}],
        },
        {
            "matches": [],
            "related_query": "broader topic\nspoofed heading",
            "related_matches": [{"candidate_id": "c000001"}],
        },
    ],
)
def test_rank_candidates_rejects_incompatible_related_tiers(response):
    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            return json.dumps(response)

    with pytest.raises(FindError):
        rank_candidates("query", [_candidate()], Provider())


def test_ops_find_avoids_provider_for_empty_context_and_invalid_request():
    calls = []

    def provider_factory():
        calls.append("called")
        return KeywordProvider()

    assert ops.find(ops.init("empty"), "anything", provider_factory) == []
    with pytest.raises(FindError, match="non-empty"):
        ops.find(ops.init("empty"), "  ", provider_factory)
    with pytest.raises(FindError, match="between 1 and 20"):
        ops.find(
            ops.init("empty"),
            "anything",
            provider_factory,
            limit=0,
        )
    assert calls == []


def test_find_cli_recurses_renders_local_content_and_does_not_checkpoint(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    child = ops.init("campus/parking")
    memory = ops.add(child, "Temporary parking is available in Lot C.")
    store.save(child)
    root = ops.init("facilities-reference")
    ops.add(root, "The library opens at 8 a.m.")
    ops.embed(child, root)
    store.save(root)
    store.set_current("facilities-reference")
    checkpoints_before = store.list_checkpoints("facilities-reference")
    provider = KeywordProvider()
    monkeypatch.setattr(
        "memcommit.commands.find.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    result = runner.invoke(app, ["search", "-r", "parking"])

    assert result.exit_code == 0
    assert "1 match" not in result.output
    assert "campus/parking\n" in result.output
    assert (
        f"[memory {memory.uid[:8]}] " "Temporary parking is available in Lot C."
    ) in result.output
    assert store.list_checkpoints("facilities-reference") == checkpoints_before

    direct = runner.invoke(app, ["search", "parking", "--direct"])
    assert direct.exit_code == 0
    assert direct.output == "facilities-reference\n  (no matching items)\n"
    assert "Temporary parking" not in direct.output


def test_find_cli_recursive_searches_materialized_namespace_descendants(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    root = ops.init("task-3")
    store.save(root)
    child = ops.init("task-3/personal-memory")
    memory = ops.add(
        child,
        "The user checks healthcare appointment instructions twice.",
    )
    store.save(child)
    sibling = ops.init("task-30/personal-memory")
    sibling_memory = ops.add(
        sibling,
        "Healthcare material outside the selected namespace.",
    )
    store.save(sibling)
    store.set_current(root.name)
    provider = KeywordProvider()
    monkeypatch.setattr(
        "memcommit.commands.find.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    result = runner.invoke(app, ["search", "-r", "healthcare"])

    assert result.exit_code == 0, result.output
    assert "task-3/personal-memory\n" in result.output
    assert f"[memory {memory.uid[:8]}]" in result.output
    payload = json.loads(provider.calls[0][0].split("FIND PAYLOAD:\n", 1)[1])
    candidate_text = json.dumps(payload["candidates"])
    assert memory.content in candidate_text
    assert sibling_memory.content not in candidate_text

    direct = runner.invoke(app, ["search", "healthcare", "--direct"])

    assert direct.exit_code == 0
    assert direct.output == "task-3\n  (no matching items)\n"
    assert len(provider.calls) == 1


def test_find_cli_labels_related_fallback_when_primary_matches_are_empty(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    root = ops.init("task-3")
    clinic = ops.add(root, "The user checks medication instructions.")
    ops.add(root, "The parking permit expires next month.")
    store.save(root)
    store.set_current(root.name)

    class RelatedProvider:
        def complete(self, prompt, *, operation, output_schema=None):
            payload = json.loads(prompt.split("FIND PAYLOAD:\n", 1)[1])
            selected = next(
                candidate["candidate_id"]
                for candidate in payload["candidates"]
                if "medication" in candidate.get("content", "").casefold()
            )
            return json.dumps(
                {
                    "matches": [],
                    "related_query": "health and healthcare memories",
                    "related_matches": [{"candidate_id": selected}],
                }
            )

    monkeypatch.setattr(
        "memcommit.commands.find.connect_codex_chatgpt_provider",
        lambda: RelatedProvider(),
    )

    result = runner.invoke(app, ["search", "health insurance memories"])

    assert result.exit_code == 0, result.output
    assert "task-3\n  (no primary matches)" in result.output
    assert "RELATED RESULTS" in result.output
    assert "Broader search: health and healthcare memories" in result.output
    assert "Related items do not satisfy the original query." in result.output
    assert f"[memory {clinic.uid[:8]}] · RELATED" in result.output
    assert "parking permit" not in result.output


def test_initial_chat_state_preserves_related_tier_and_broader_query():
    candidate = _candidate(content="clinic appointment")
    state = _initial_chat_state(
        "task-3",
        "health insurance memories",
        [
            SearchMatch(
                candidate=candidate,
                relevance="related",
                related_query="health and healthcare memories",
            )
        ],
    )

    assert state.related_query == "health and healthcare memories"
    assert state.results[0].relevance == "related"
    assert state.status == "NO PRIMARY MATCHES · SHOWING RELATED RESULTS"
    assert "I found no primary matches" in state.messages[-1].text


def test_find_cli_tty_prints_static_results_without_opening_chat(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("facilities-reference")
    memory = ops.add(ctx, "The campus cafe will close.")
    store.save(ctx)
    store.set_current(ctx.name)
    provider = KeywordProvider()
    monkeypatch.setattr(
        "memcommit.commands.find.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    monkeypatch.setattr(
        "memcommit.commands.find._interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "memcommit.commands.find.run_find_chat_session",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("ordinary Find must not open the chat shell")
        ),
    )

    result = runner.invoke(app, ["search", "cafe"])

    assert result.exit_code == 0, result.output
    assert ctx.name in result.output
    assert f"[memory {memory.uid[:8]}]" in result.output
    assert memory.content in result.output
    assert "Find dialogue closed" not in result.output


def test_find_without_query_opens_blank_interactive_search_in_a_tty(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("facilities-reference")
    store.save(ctx)
    store.set_current(ctx.name)
    opened = []
    monkeypatch.setattr(
        "memcommit.commands.find._interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "memcommit.commands.find._open_find_search_workbench",
        lambda store, access, **options: opened.append(
            (store.store_dir, access.display_name, options)
        ),
    )

    result = runner.invoke(app, ["search"])
    scoped = runner.invoke(app, ["search", "--context-only", "--follow-embeds"])

    assert result.exit_code == 0, result.output
    assert scoped.exit_code == 0, scoped.output
    assert opened == [
        (
            store.store_dir,
            ctx.name,
            {
                "current_name": ctx.name,
                "include_descendants": True,
                "follow_embeds": True,
                "limit": 5,
            },
        ),
        (
            store.store_dir,
            ctx.name,
            {
                "current_name": ctx.name,
                "include_descendants": False,
                "follow_embeds": True,
                "limit": 5,
            },
        ),
    ]


def test_find_without_query_requires_a_terminal(isolated_store):
    store = MemoryStore()
    ctx = ops.init("facilities-reference")
    store.save(ctx)
    store.set_current(ctx.name)

    result = runner.invoke(app, ["search"])

    assert result.exit_code == 1
    assert "QUERY is required outside a terminal" in result.stderr


def test_find_help_explains_the_bare_route_and_default_scope():
    result = runner.invoke(app, ["search", "--help"])

    assert result.exit_code == 0, result.output
    assert "[QUERY]" in result.output
    assert "interactive search" in result.output
    assert "compact exact-Context Scope" in result.output
    assert "Browse-only Profile/multiple selection" in result.output
    assert "lexical descendants" in result.output
    assert "embedded Contexts" in result.output
    assert "--descendants" in result.output
    assert "--context-only" in result.output
    assert "--follow-embeds" in result.output
    assert "--exclude-embeds" in result.output
    assert "--all" in result.output
    assert "all readable" in result.output
    assert "active" in result.output
    assert "Profile" in result.output
    assert "Search only the selected" in result.output
    assert "-d" in result.output
    assert "-r" in result.output


def test_find_cli_tty_static_results_include_namespace_descendants(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    root = ops.init("task-3")
    store.save(root)
    child = ops.init("task-3/personal-memory")
    memory = ops.add(child, "Healthcare appointment preparation")
    store.save(child)
    store.set_current(root.name)
    monkeypatch.setattr(
        "memcommit.commands.find.connect_codex_chatgpt_provider",
        lambda: KeywordProvider(),
    )
    monkeypatch.setattr(
        "memcommit.commands.find._interactive_terminal",
        lambda: True,
    )

    monkeypatch.setattr(
        "memcommit.commands.find.run_find_chat_session",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("ordinary Find must not open the chat shell")
        ),
    )

    result = runner.invoke(app, ["search", "-r", "healthcare"])

    assert result.exit_code == 0, result.output
    assert child.name in result.output
    assert f"[memory {memory.uid[:8]}]" in result.output
    assert "Find dialogue closed" not in result.output


def test_zero_result_follow_up_refines_and_replaces_search_results(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    root = ops.init("task-3")
    store.save(root)
    child = ops.init("task-3/personal-memory")
    healthcare = ops.add(
        child,
        "The user checks medication instructions after a clinic visit.",
    )
    ops.add(child, "The parking permit expires next month.")
    store.save(child)
    state = _initial_chat_state(
        root.name,
        "건강보험 관련 메모리",
        [],
    )

    class RefineProvider:
        def __init__(self):
            self.operations = []

        def complete(self, prompt, *, operation, output_schema=None):
            self.operations.append(operation)
            if operation == "search turn":
                assert output_schema["properties"]["kind"]["enum"] == [
                    "ASK",
                    "REFINE",
                ]
                return json.dumps(
                    {
                        "kind": "REFINE",
                        "understanding": (
                            "You broadened the search to healthcare and medicine."
                        ),
                        "question": "",
                        "query": "healthcare medicine medication clinic",
                        "selector": "",
                        "scope": "CONTEXT",
                    }
                )
            assert operation == "search"
            payload = json.loads(prompt.split("FIND PAYLOAD:\n", 1)[1])
            selected = next(
                candidate["candidate_id"]
                for candidate in payload["candidates"]
                if "medication" in candidate.get("content", "").casefold()
            )
            return json.dumps(
                {
                    "matches": [{"candidate_id": selected}],
                    "related_query": "",
                    "related_matches": [],
                }
            )

    provider = RefineProvider()
    monkeypatch.setattr(
        "memcommit.commands.find.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    updated = _handle_find_turn(
        state,
        "related to health/healthcare/medicine",
    )

    assert updated.current_query == "healthcare medicine medication clinic"
    assert [result.uid for result in updated.results] == [healthcare.uid]
    assert updated.results[0].context_name == child.name
    assert updated.status == "RESULTS READY · REFINED"
    assert updated.messages[-2] == FindChatMessage(
        role="USER",
        text="related to health/healthcare/medicine",
    )
    assert "I found 1 matching Memory" in updated.messages[-1].text
    assert provider.operations == ["search turn", "search"]


def test_refine_can_replace_zero_results_with_a_labeled_related_fallback(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    root = ops.init("task-3")
    clinic = ops.add(root, "The user checks medication instructions.")
    store.save(root)
    state = _initial_chat_state(root.name, "insurance paperwork", [])

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            if operation == "search turn":
                return json.dumps(
                    {
                        "kind": "REFINE",
                        "understanding": "You asked for health insurance memories.",
                        "question": "",
                        "query": "health insurance memories",
                        "selector": "",
                        "scope": "CONTEXT",
                    }
                )
            payload = json.loads(prompt.split("FIND PAYLOAD:\n", 1)[1])
            selected = next(
                candidate["candidate_id"]
                for candidate in payload["candidates"]
                if "medication" in candidate.get("content", "").casefold()
            )
            return json.dumps(
                {
                    "matches": [],
                    "related_query": "health and healthcare memories",
                    "related_matches": [{"candidate_id": selected}],
                }
            )

    monkeypatch.setattr(
        "memcommit.commands.find.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )

    updated = _handle_find_turn(state, "health insurance memories")

    assert [result.uid for result in updated.results] == [clinic.uid]
    assert updated.results[0].relevance == "related"
    assert updated.related_query == "health and healthcare memories"
    assert updated.status == "NO PRIMARY MATCHES · SHOWING RELATED RESULTS · REFINED"
    assert "I found no primary matches" in updated.messages[-1].text


def test_show_result_proposal_runs_exact_read_only_cli_and_preserves_results(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("task-1")
    memory = ops.add(ctx, "There is a coffee machine on the first floor.")
    store.save(ctx)
    candidate = SearchCandidate(
        candidate_id="c000001",
        kind="memory",
        context_uid=ctx.uid,
        context_names=(ctx.name,),
        item=memory,
        search_text=memory.content,
    )
    state = _initial_chat_state(
        ctx.name,
        "coffee",
        [SearchMatch(candidate=candidate)],
    )
    action = FindTurnAction(
        understanding="You want the first result in full.",
        question="What would you like to inspect next?",
        selector="m1",
    )
    proposal = _show_result_proposal(state, action, "show m1")

    assert proposal.review.argv == (
        "mem",
        "show",
        memory.uid,
        "--context",
        ctx.name,
    )
    monkeypatch.setattr(
        "memcommit.commands.find._run_read_only_find_command",
        lambda argv: subprocess.CompletedProcess(
            args=argv,
            returncode=0,
            stdout=(
                f"Memory: {memory.uid}\n"
                f"Context: {ctx.name}\n\n"
                f"{memory.content}\n"
            ),
            stderr="",
        ),
    )
    updated = _apply_show_result(state, proposal)

    assert updated.results == state.results
    assert updated.status == "SHOWED m1"
    receipt = updated.messages[-1].text
    assert "SHOW COMPLETE" in receipt
    assert "mem show" in receipt
    assert memory.uid in receipt
    assert "ACTUAL OUTPUT" in receipt
    assert memory.content in receipt
    assert store.list_checkpoints(ctx.name) == []


def test_general_parking_question_gets_a_grounded_answer_without_a_command(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("temp/task-1-atomized-en")
    visible = ops.add(
        ctx,
        "The parking area will reopen immediately after construction ends.",
    )
    supplemental = ops.add(
        ctx,
        "Construction runs from June xx through August xx.",
    )
    store.save(ctx)
    candidates = collect_candidates(ctx)
    state = _initial_chat_state(
        ctx.name,
        "related to parking",
        [SearchMatch(candidate=candidates[0])],
    )

    class AnswerProvider:
        def __init__(self):
            self.operations = []

        def complete(self, _prompt, *, operation, output_schema=None):
            self.operations.append(operation)
            if operation == "search turn":
                return json.dumps(
                    {
                        "kind": "ANSWER",
                        "understanding": (
                            "You are asking how long the garage will be closed."
                        ),
                        "question": "",
                        "query": "",
                        "selector": "",
                        "scope": "CONTEXT",
                    }
                )
            assert operation == "search answer"
            return json.dumps(
                {
                    "visible_text": (
                        "The current results say it reopens after construction."
                    ),
                    "visible_sources": ["m1"],
                    "context_text": (
                        "Another Memory places construction between June and " "August."
                    ),
                    "context_sources": ["c1"],
                    "outside_text": "Other Contexts were not checked.",
                    "outside_sources": [],
                }
            )

    provider = AnswerProvider()
    monkeypatch.setattr(
        "memcommit.commands.find.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    def refuse_command(_argv):
        raise AssertionError("An ANSWER turn must not execute a command.")

    monkeypatch.setattr(
        "memcommit.commands.find._run_read_only_find_command",
        refuse_command,
    )

    updated = _handle_find_turn(
        state,
        "garage will 언제까지 closed?",
    )

    assert updated.results == state.results
    assert updated.status == ("ANSWERED · CONTEXT CHECKED · OTHER CONTEXTS NOT CHECKED")
    assert updated.messages[-2] == FindChatMessage(
        role="USER",
        text="garage will 언제까지 closed?",
    )
    answer_text = updated.messages[-1].text
    assert "after construction. [1]" in answer_text
    assert "between June and August. [2]" in answer_text
    assert "다른 Context는 확인하지 않았습니다." in answer_text
    assert "References" in answer_text
    assert visible.content in answer_text
    assert supplemental.content in answer_text
    assert f"[1] {visible.content} — {visible.uid[:8]}, {ctx.name}, m1" in answer_text
    assert (
        f"[2] {supplemental.content} — {supplemental.uid[:8]}, {ctx.name}, c1"
        in answer_text
    )
    assert provider.operations == ["search turn", "search answer"]


def test_explicit_other_context_answer_collects_and_references_outside_memory(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    root = ops.init("task-1")
    visible = ops.add(root, "The garage is closed during construction.")
    store.save(root)
    other = ops.init("facilities-calendar")
    outside = ops.add(
        other,
        "The construction completion review is scheduled for August 28.",
    )
    store.save(other)
    candidates = collect_candidates(root)
    state = _initial_chat_state(
        root.name,
        "garage closure",
        [SearchMatch(candidate=candidates[0])],
    )

    class AnswerProvider:
        def __init__(self):
            self.operations = []

        def complete(self, prompt, *, operation, output_schema=None):
            self.operations.append(operation)
            if operation == "search turn":
                return json.dumps(
                    {
                        "kind": "ANSWER",
                        "understanding": (
                            "You want the other Contexts checked as well."
                        ),
                        "question": "",
                        "query": "",
                        "selector": "",
                        "scope": "ALL_CONTEXTS",
                    }
                )
            assert "facilities-calendar" in prompt
            assert outside.content in prompt
            return json.dumps(
                {
                    "visible_text": (
                        "The visible result confirms a construction closure."
                    ),
                    "visible_sources": ["m1"],
                    "context_text": (
                        "No additional evidence was found in the same Context."
                    ),
                    "context_sources": [],
                    "outside_text": (
                        "Another Context schedules a completion review for "
                        "August 28."
                    ),
                    "outside_sources": ["x1"],
                }
            )

    provider = AnswerProvider()
    monkeypatch.setattr(
        "memcommit.commands.find.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    pending = _handle_find_turn(
        state,
        "Check the other contexts too: when does it end?",
    )

    assert pending.status == "WAITING FOR OTHER CONTEXTS CONFIRMATION"
    assert pending.pending_answer is not None
    assert FIND_OUTSIDE_CONFIRMATION in pending.messages[-1].text
    assert outside.content not in pending.messages[-1].text
    assert provider.operations == ["search turn"]

    updated = _handle_find_turn(
        pending,
        FIND_OUTSIDE_CONFIRMATION,
    )

    assert updated.status == ("ANSWERED · CONTEXT CHECKED · OTHER CONTEXTS CHECKED")
    assert updated.pending_answer is None
    answer_text = updated.messages[-1].text
    assert "closure. [1]" in answer_text
    assert "August 28. [2]" in answer_text
    assert f"[1] {visible.content} — {visible.uid[:8]}, task-1, m1" in answer_text
    assert (
        f"[2] {outside.content} — {outside.uid[:8]}, facilities-calendar, x1"
    ) in answer_text
    assert outside.content in answer_text
    assert provider.operations == ["search turn", "search answer"]


def test_provider_cannot_expand_to_other_contexts_without_user_request(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    root = ops.init("task-1")
    ops.add(root, "The garage is closed.")
    store.save(root)
    candidates = collect_candidates(root)
    state = _initial_chat_state(
        root.name,
        "garage",
        [SearchMatch(candidate=candidates[0])],
    )

    class OverbroadProvider:
        def __init__(self):
            self.operations = []

        def complete(self, _prompt, *, operation, output_schema=None):
            self.operations.append(operation)
            return json.dumps(
                {
                    "kind": "ANSWER",
                    "understanding": "Check every stored Context.",
                    "question": "",
                    "query": "",
                    "selector": "",
                    "scope": "ALL_CONTEXTS",
                }
            )

    provider = OverbroadProvider()
    monkeypatch.setattr(
        "memcommit.commands.find.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    monkeypatch.setattr(
        "memcommit.commands.find.collect_outside_context_evidence",
        lambda *_args, **_kwargs: pytest.fail("outside Contexts must not be collected"),
    )

    pending = _handle_find_turn(state, "When does it reopen?")

    assert pending.status == "WAITING FOR OTHER CONTEXTS CONFIRMATION"
    assert pending.pending_answer is not None
    assert provider.operations == ["search turn"]

    still_pending = _handle_find_turn(pending, "yes")
    assert still_pending.status == "WAITING FOR OTHER CONTEXTS CONFIRMATION"
    assert still_pending.pending_answer == pending.pending_answer
    assert "not confirmed" in still_pending.messages[-1].text
    assert provider.operations == ["search turn"]

    cancelled = _handle_find_turn(
        still_pending,
        FIND_OUTSIDE_CANCELLATION,
    )
    assert cancelled.pending_answer is None
    assert cancelled.status == "OTHER CONTEXTS CANCELLED"

    assert provider.operations == ["search turn"]


def test_read_only_find_runner_rejects_every_non_show_shape():
    with pytest.raises(FindError, match="non-show"):
        _run_read_only_find_command(
            ("mem", "delete", "memory-one", "--context", "task-1")
        )


def test_show_result_failure_does_not_claim_success(monkeypatch):
    candidate = _candidate()
    state = _initial_chat_state(
        "owner",
        "canonical",
        [SearchMatch(candidate=candidate)],
    )
    proposal = _show_result_proposal(
        state,
        FindTurnAction(
            understanding="Inspect it.",
            question="Next?",
            selector="m1",
        ),
        "show it",
    )
    monkeypatch.setattr(
        "memcommit.commands.find._run_read_only_find_command",
        lambda _argv: subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="injected failure",
        ),
    )

    with pytest.raises(FindError, match="injected failure"):
        _apply_show_result(state, proposal)
    assert state.status == "RESULTS READY"


def test_find_cli_groups_contexts_and_aligns_multiline_content(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    child = ops.init("campus/parking")
    first_child = ops.add(child, "First child line\ncontinued detail")
    second_child = ops.add(child, "Second child result")
    store.save(child)
    root = ops.init("facilities-reference")
    root_memory = ops.add(root, "Root result")
    ops.embed(child, root)
    store.save(root)
    store.set_current(root.name)

    class InterleavedProvider:
        def complete(self, prompt, *, operation, output_schema=None):
            payload = json.loads(prompt.split("FIND PAYLOAD:\n", 1)[1])
            by_content = {
                candidate["content"]: candidate["candidate_id"]
                for candidate in payload["candidates"]
            }
            return json.dumps(
                {
                    "matches": [
                        {"candidate_id": by_content[first_child.content]},
                        {"candidate_id": by_content[root_memory.content]},
                        {"candidate_id": by_content[second_child.content]},
                    ],
                    "related_query": "",
                    "related_matches": [],
                }
            )

    monkeypatch.setattr(
        "memcommit.commands.find.connect_codex_chatgpt_provider",
        lambda: InterleavedProvider(),
    )

    result = runner.invoke(app, ["search", "-r", "anything"])

    assert result.exit_code == 0
    first_label = f"[memory {first_child.uid[:8]}]"
    first_row = f"{first_label} First child line"
    continuation = " " * (len(first_label) + 1) + "continued detail"
    second_row = f"[memory {second_child.uid[:8]}] Second child result"
    root_row = f"[memory {root_memory.uid[:8]}] Root result"
    assert result.output.count("campus/parking\n") == 1
    assert result.output.count("facilities-reference\n") == 1
    assert (
        result.output.index("campus/parking\n")
        < result.output.index(first_row)
        < result.output.index(continuation)
        < result.output.index(second_row)
        < result.output.index("facilities-reference\n")
        < result.output.index(root_row)
    )


def test_find_cli_groups_memory_ref_and_renders_target_inline(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("source")
    memory = ops.add(source, "Referenced parking detail")
    store.save(source)
    parent = ops.init("parent")
    ref = ops.embed_memory(memory, source, parent)
    store.save(parent)
    store.set_current(parent.name)
    monkeypatch.setattr(
        "memcommit.commands.find.connect_codex_chatgpt_provider",
        lambda: KeywordProvider(),
    )

    result = runner.invoke(app, ["search", "-r", "parking"])

    assert result.exit_code == 0
    assert result.output == (
        "parent\n"
        f"[memory ref {ref.uid[:8]}] · READ ONLY "
        f"-> source#{memory.uid[:8]} Referenced parking detail\n"
    )


def test_find_cli_explicit_context_does_not_switch_current(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    searchable = ops.init("searchable")
    ops.add(searchable, "Parking information")
    active = ops.init("active")
    store.save(searchable)
    store.save(active)
    store.set_current("active")
    monkeypatch.setattr(
        "memcommit.commands.find.connect_codex_chatgpt_provider",
        lambda: KeywordProvider(),
    )

    result = runner.invoke(
        app,
        ["search", "parking", "--context", "searchable"],
    )

    assert result.exit_code == 0
    assert "Parking information" in result.output
    assert store.current_context_name() == "active"


def test_find_cli_query_ref_hit_prints_hint_without_hidden_content(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = store.create_query_source(
        "contractor-agreements",
        HIDDEN_SECRET,
    )
    parent = ops.init("facilities-reference")
    ref = ops.reference_query_context(
        "contractor-agreements",
        source.uid,
        parent,
    )
    store.save(parent)
    store.set_current("facilities-reference")
    monkeypatch.setattr(
        "memcommit.commands.find.connect_codex_chatgpt_provider",
        lambda: KeywordProvider(),
    )

    result = runner.invoke(app, ["search", "contractor"])

    assert result.exit_code == 0
    assert "facilities-reference\n" in result.output
    assert (
        f"[query view {ref.uid[:8]}] contractor-agreements"
    ) in result.output
    assert "mem query" in result.output
    assert HIDDEN_SECRET not in result.output


def test_query_ref_hint_shell_quotes_untrusted_names(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    parent = Context(uid=str(uuid.uuid4()), name="parent$(unsafe)")
    parent.add(
        QueryContextRef(
            uid="query-ref",
            name="policy$(unsafe)",
            target_source_uid="source",
            provider="codex_chatgpt",
        )
    )
    # Preserve coverage for a pre-portability locator. New Context creation
    # rejects shell metacharacters, but legacy records still need safe hints.
    record = store.contexts_dir / parent.name / "context.json"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(
        json.dumps(parent.to_dict(), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    store.set_current(parent.name)
    monkeypatch.setattr(
        "memcommit.commands.find.connect_codex_chatgpt_provider",
        lambda: KeywordProvider(),
    )

    result = runner.invoke(app, ["search", "policy"])

    assert result.exit_code == 0
    assert "'policy$(unsafe)'" in result.output
    assert "'parent$(unsafe)'" in result.output


def test_find_cli_errors_for_missing_context_without_current_or_bad_limit(
    isolated_store,
    monkeypatch,
):
    monkeypatch.setattr(
        "memcommit.commands.find.connect_codex_chatgpt_provider",
        lambda: pytest.fail("provider should not be called"),
    )

    no_current = runner.invoke(app, ["search", "anything"])
    missing = runner.invoke(
        app,
        ["search", "anything", "--context", "missing"],
    )
    assert no_current.exit_code == 1
    assert missing.exit_code == 1

    store = MemoryStore()
    ctx = ops.init("ctx")
    ops.add(ctx, "searchable")
    store.save(ctx)
    store.set_current("ctx")
    bad_limit = runner.invoke(app, ["search", "anything", "--limit", "0"])
    assert bad_limit.exit_code == 1
    assert "between 1 and 20" in bad_limit.stderr
