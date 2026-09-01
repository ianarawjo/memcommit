"""Semantic search traversal, validation, privacy, and CLI contracts."""

import json
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.commands.search.command import (
    _run_search_request,
)
from memcommit.application.operations.search.corpus import load_readable_search_roots
from memcommit.application.context_access.access import resolve_context_access
from memcommit.application.context_access.readable_contexts import (
    freeze_readable_context_catalog,
)
from memcommit.adapters.console.commands.search.search_workbench import (
    SearchRequest,
    SearchResponse,
)
from memcommit.core.context import (
    Context,
    GrantedContextLink,
    GrantedMemorySource,
    Memory,
    MemoryRef,
    QueryContextRef,
)
from memcommit.application.operations.search.application import (
    supplement_namespace_branch_coverage,
)
from memcommit.application.operations.search.candidates import (
    SearchCandidate,
    collect_candidates,
    collect_candidates_from_roots,
)
from memcommit.application.operations.search.errors import (
    SearchError,
)
from memcommit.application.operations.search.ranking import (
    SearchMatch,
    rank_candidates,
)
from memcommit.persistence.store import MemoryStore


runner = CliRunner(mix_stderr=False)
HIDDEN_SECRET = "The confidential contract ceiling is 4.2 million dollars."


class KeywordProvider:
    """Test provider that selects candidates by local payload substring."""

    def __init__(self):
        self.calls = []

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls.append((prompt, operation, output_schema))
        payload = json.loads(prompt.split("SEARCH PAYLOAD:\n", 1)[1])
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

    exact_roots = load_readable_search_roots(
        catalog,
        (root.name,),
        include_descendants=False,
        follow_embeds=False,
    )
    below_roots = load_readable_search_roots(
        catalog,
        (root.name,),
        include_descendants=True,
        follow_embeds=False,
    )
    embedded_roots = load_readable_search_roots(
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


def test_interactive_searches_multiple_exact_targets_in_one_provider_turn(
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
        "memcommit.adapters.console.commands.search.command.connect_search_provider",
        lambda: provider,
    )
    request = SearchRequest(
        query="shared needle",
        target_names=(first.name, second.name),
        include_descendants=False,
        follow_embeds=False,
        limit=5,
    )

    response = _run_search_request(store, catalog, request)

    assert response.request == request
    assert response.mode == "CURRENT"
    assert {result.uid for result in response.results} == {
        first_memory.uid,
        second_memory.uid,
    }
    payload = json.loads(provider.calls[0][0].split("SEARCH PAYLOAD:\n", 1)[1])
    sent_content = {candidate.get("content", "") for candidate in payload["candidates"]}
    assert first_memory.content in sent_content
    assert second_memory.content in sent_content
    assert omitted_memory.content not in sent_content


def test_explicit_search_repeats_context_for_the_same_multi_root_request(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    first = ops.init("first")
    second = ops.init("second")
    for context in (first, second):
        store.save(context)
    store.set_current(first.name)
    observed: list[SearchRequest] = []

    def run_request(_store, _catalog, request):
        observed.append(request)
        return SearchResponse(request=request, mode="CURRENT", results=())

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.search.command._run_search_request",
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
        SearchRequest(
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
    observed: list[SearchRequest] = []

    def run_request(_store, _catalog, request):
        observed.append(request)
        return SearchResponse(request=request, mode="CURRENT", results=())

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.search.command._run_search_request",
        run_request,
    )

    for option in ("--all", "-a"):
        result = runner.invoke(app, ["search", option, "shared detail"])
        assert result.exit_code == 0, result.output + result.stderr
        assert result.output == "ALL READABLE CONTEXTS\n  (no matching items)\n"

    assert observed == [
        SearchRequest(
            query="shared detail",
            target_names=(first.name, second.name),
            include_descendants=False,
            follow_embeds=False,
            limit=5,
        ),
        SearchRequest(
            query="shared detail",
            target_names=(first.name, second.name),
            include_descendants=False,
            follow_embeds=False,
            limit=5,
        ),
    ]


def test_search_all_rejects_explicit_context(isolated_store, monkeypatch):
    store = MemoryStore()
    context = ops.init("first")
    store.save(context)
    store.set_current(context.name)
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.search.command._run_search_request",
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


def test_search_cli_multi_roots_keep_descendants_and_embeds_independent(
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
            "memcommit.adapters.console.commands.search.command.connect_search_provider",
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
        payload = json.loads(provider.calls[0][0].split("SEARCH PAYLOAD:\n", 1)[1])
        return {
            candidate.get("content", "") for candidate in payload["candidates"]
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


def test_search_rejects_granted_live_embed_before_provider_construction():
    authority = Context(uid=str(uuid.uuid4()), name="public/advisor")
    memory = Memory(uid=str(uuid.uuid4()), content="Granted search secret.")
    authority.add(memory)
    containing = Context(uid=str(uuid.uuid4()), name="workspace")
    containing.add(
        MemoryRef(
            uid=str(uuid.uuid4()),
            target_context_uid=authority.uid,
            target_context_name=authority.name,
            target_memory_uid=memory.uid,
            target=memory,
            granted_source=GrantedMemorySource(
                context_uid=authority.uid,
                access_name=authority.name,
                authority_context_name="authority/advisor",
                authority_profile_uid=str(uuid.uuid4()),
                grantee_profile_uid=str(uuid.uuid4()),
                grant_uid=str(uuid.uuid4()),
                grant_revision_at_creation=1,
                resource_uid=authority.uid,
                resource_name="authority/advisor",
                memory_uid=memory.uid,
            ),
        )
    )
    provider_connections = 0

    def provider_factory():
        nonlocal provider_connections
        provider_connections += 1
        return KeywordProvider()

    with pytest.raises(
        SearchError,
        match="EMBED authorizes live reading, not provider disclosure",
    ):
        ops.search(containing, "secret", provider_factory)

    assert provider_connections == 0


def test_search_rejects_nested_granted_context_before_provider_construction():
    granted = Context(uid=str(uuid.uuid4()), name="public/advisor")
    granted.add(Memory(uid=str(uuid.uuid4()), content="Granted context secret."))
    containing = Context(uid=str(uuid.uuid4()), name="workspace")
    granted._granted_link = GrantedContextLink(
        context_uid=granted.uid,
        access_name=granted.name,
        authority_context_name="authority/advisor",
        authority_profile_uid=str(uuid.uuid4()),
        grantee_profile_uid=str(uuid.uuid4()),
        grant_uid=str(uuid.uuid4()),
        grant_revision_at_creation=1,
        resource_uid=granted.uid,
        resource_name="authority/advisor",
    )
    containing.add(granted)
    provider_connections = 0

    def provider_factory():
        nonlocal provider_connections
        provider_connections += 1
        return KeywordProvider()

    with pytest.raises(
        SearchError,
        match="granted Context Embed.*not provider disclosure",
    ):
        ops.search(containing, "secret", provider_factory)

    assert provider_connections == 0


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
        raise AssertionError("search opened a concealed query source")

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


def test_recursive_search_reserves_room_for_material_omitted_namespace_branch():
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

    matches = supplement_namespace_branch_coverage(
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

    with pytest.raises(SearchError):
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

    with pytest.raises(SearchError):
        rank_candidates("query", [_candidate()], Provider())


def test_ops_search_avoids_provider_for_empty_context_and_invalid_request():
    calls = []

    def provider_factory():
        calls.append("called")
        return KeywordProvider()

    assert ops.search(ops.init("empty"), "anything", provider_factory) == []
    with pytest.raises(SearchError, match="non-empty"):
        ops.search(ops.init("empty"), "  ", provider_factory)
    with pytest.raises(SearchError, match="between 1 and 20"):
        ops.search(
            ops.init("empty"),
            "anything",
            provider_factory,
            limit=0,
        )
    assert calls == []


def test_search_cli_recurses_renders_local_content_and_does_not_checkpoint(
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
        "memcommit.adapters.console.commands.search.command.connect_search_provider",
        lambda: provider,
    )

    result = runner.invoke(app, ["search", "-r", "parking"])

    assert result.exit_code == 0
    assert "1 match" not in result.output
    assert "campus/parking\n" in result.output
    assert (
        f"[memory {memory.uid[:8]}] Temporary parking is available in Lot C."
    ) in result.output
    assert store.list_checkpoints("facilities-reference") == checkpoints_before

    direct = runner.invoke(app, ["search", "parking", "--direct"])
    assert direct.exit_code == 0
    assert direct.output == "facilities-reference\n  (no matching items)\n"
    assert "Temporary parking" not in direct.output


def test_search_cli_accepts_a_memory_uid_without_connecting_provider(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context = ops.init("search-uid")
    memory = ops.add(context, "Identity-selected Search result.")
    store.save(context)
    store.set_current(context.name)
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.search.command.connect_search_provider",
        lambda: pytest.fail("UID Search must not connect a provider"),
    )

    result = runner.invoke(app, ["search", memory.uid[:8]])

    assert result.exit_code == 0, result.output + result.stderr
    assert f"[memory {memory.uid[:8]}]" in result.output
    assert memory.content in result.output


def test_search_cli_recursive_searches_materialized_namespace_descendants(
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
        "memcommit.adapters.console.commands.search.command.connect_search_provider",
        lambda: provider,
    )

    result = runner.invoke(app, ["search", "-r", "healthcare"])

    assert result.exit_code == 0, result.output
    assert "task-3/personal-memory\n" in result.output
    assert f"[memory {memory.uid[:8]}]" in result.output
    payload = json.loads(provider.calls[0][0].split("SEARCH PAYLOAD:\n", 1)[1])
    candidate_text = json.dumps(payload["candidates"])
    assert memory.content in candidate_text
    assert sibling_memory.content not in candidate_text

    direct = runner.invoke(app, ["search", "healthcare", "--direct"])

    assert direct.exit_code == 0
    assert direct.output == "task-3\n  (no matching items)\n"
    assert len(provider.calls) == 1


def test_search_cli_labels_related_fallback_when_primary_matches_are_empty(
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
            payload = json.loads(prompt.split("SEARCH PAYLOAD:\n", 1)[1])
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
        "memcommit.adapters.console.commands.search.command.connect_search_provider",
        lambda: RelatedProvider(),
    )

    result = runner.invoke(app, ["search", "health insurance memories"])

    assert result.exit_code == 0, result.output
    assert "task-3\n  (no primary matches)" in result.output
    assert "RELATED RESULTS" in result.output
    assert "No matching results for: health insurance memories" in result.output
    assert "Broader search: health and healthcare memories" in result.output
    assert "Related results may not satisfy the original query." in result.output
    assert f"[memory {clinic.uid[:8]}] · RELATED" in result.output
    assert "parking permit" not in result.output
    assert result.output.index("No matching results for:") < result.output.index(
        "Broader search:"
    )
    assert result.output.index(f"[memory {clinic.uid[:8]}]") < result.output.index(
        "Related results may not satisfy the original query."
    )


def test_search_cli_tty_prints_static_results_without_opening_chat(
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
        "memcommit.adapters.console.commands.search.command.connect_search_provider",
        lambda: provider,
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.search.command._interactive_terminal",
        lambda: True,
    )
    result = runner.invoke(app, ["search", "cafe"])

    assert result.exit_code == 0, result.output
    assert ctx.name in result.output
    assert f"[memory {memory.uid[:8]}]" in result.output
    assert memory.content in result.output
    assert "Search dialogue closed" not in result.output


def test_search_without_query_opens_blank_interactive_search_in_a_tty(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("facilities-reference")
    store.save(ctx)
    store.set_current(ctx.name)
    opened = []
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.search.command._interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.search.command._open_search_workbench",
        lambda store, access, **options: opened.append(
            (store.store_dir, access.access_name, options)
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


def test_search_without_query_requires_a_terminal(isolated_store):
    store = MemoryStore()
    ctx = ops.init("facilities-reference")
    store.save(ctx)
    store.set_current(ctx.name)

    result = runner.invoke(app, ["search"])

    assert result.exit_code == 1
    assert "QUERY is required outside a terminal" in result.stderr


def test_search_help_explains_the_bare_route_and_default_scope():
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


def test_search_cli_tty_static_results_include_namespace_descendants(
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
        "memcommit.adapters.console.commands.search.command.connect_search_provider",
        lambda: KeywordProvider(),
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.search.command._interactive_terminal",
        lambda: True,
    )

    result = runner.invoke(app, ["search", "-r", "healthcare"])

    assert result.exit_code == 0, result.output
    assert child.name in result.output
    assert f"[memory {memory.uid[:8]}]" in result.output
    assert "Search dialogue closed" not in result.output


def test_search_cli_groups_contexts_and_aligns_multiline_content(
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
            payload = json.loads(prompt.split("SEARCH PAYLOAD:\n", 1)[1])
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
        "memcommit.adapters.console.commands.search.command.connect_search_provider",
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


def test_search_cli_groups_memory_ref_and_renders_target_inline(
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
        "memcommit.adapters.console.commands.search.command.connect_search_provider",
        lambda: KeywordProvider(),
    )

    result = runner.invoke(app, ["search", "-r", "parking"])

    assert result.exit_code == 0
    assert result.output == (
        "parent\n"
        f"[memory ref {ref.uid[:8]}] · READ ONLY "
        f"-> source#{memory.uid[:8]} Referenced parking detail\n"
    )


def test_search_cli_explicit_context_does_not_switch_current(
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
        "memcommit.adapters.console.commands.search.command.connect_search_provider",
        lambda: KeywordProvider(),
    )

    result = runner.invoke(
        app,
        ["search", "parking", "--context", "searchable"],
    )

    assert result.exit_code == 0
    assert "Parking information" in result.output
    assert store.current_context_name() == "active"


def test_search_cli_query_ref_hit_prints_hint_without_hidden_content(
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
        "memcommit.adapters.console.commands.search.command.connect_search_provider",
        lambda: KeywordProvider(),
    )

    result = runner.invoke(app, ["search", "contractor"])

    assert result.exit_code == 0
    assert "facilities-reference\n" in result.output
    assert (f"[query view {ref.uid[:8]}] contractor-agreements") in result.output
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
        "memcommit.adapters.console.commands.search.command.connect_search_provider",
        lambda: KeywordProvider(),
    )

    result = runner.invoke(app, ["search", "policy"])

    assert result.exit_code == 0
    assert "'policy$(unsafe)'" in result.output
    assert "'parent$(unsafe)'" in result.output


def test_search_cli_errors_for_missing_context_without_current_or_bad_limit(
    isolated_store,
    monkeypatch,
):
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.search.command.connect_search_provider",
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
