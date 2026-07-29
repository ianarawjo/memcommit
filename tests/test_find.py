"""Semantic find traversal, validation, privacy, and CLI contracts."""

import json

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.search import (
    FindError,
    SearchCandidate,
    collect_candidates,
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
                str(value)
                for key, value in candidate.items()
                if key != "candidate_id"
            ).casefold()
            if query in searchable:
                matches.append({"candidate_id": candidate["candidate_id"]})
        return json.dumps({"matches": matches[: payload["limit"]]})


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
    first_ref = ops.reference_memory(memory, source, parent)
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
    assert [
        candidate.search_text
        for candidate in collect_candidates(root)
    ] == ["restricted-policy"]


def test_rank_candidates_preserves_model_order_and_dedupes_repeats():
    candidates = [
        _candidate("c000001", content="first"),
        _candidate("c000002", content="second"),
    ]

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            assert operation == "find"
            assert output_schema["properties"]["matches"]["items"]["properties"][
                "candidate_id"
            ]["enum"] == ["c000001", "c000002"]
            return json.dumps(
                {
                    "matches": [
                        {"candidate_id": "c000002"},
                        {"candidate_id": "c000002"},
                        {"candidate_id": "c000001"},
                    ]
                }
            )

    matches = rank_candidates("anything", candidates, Provider(), limit=5)

    assert [
        match.candidate.candidate_id
        for match in matches
    ] == ["c000002", "c000001"]


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

    result = runner.invoke(app, ["find", "parking"])

    assert result.exit_code == 0
    assert "1 match" not in result.output
    assert "campus/parking\n" in result.output
    assert (
        f"[memory  {memory.uid[:8]}] "
        "Temporary parking is available in Lot C."
    ) in result.output
    assert store.list_checkpoints("facilities-reference") == checkpoints_before

    direct = runner.invoke(app, ["find", "parking", "--direct"])
    assert direct.exit_code == 0
    assert direct.output == "facilities-reference\n  (no matching items)\n"
    assert "Temporary parking" not in direct.output


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
                    ]
                }
            )

    monkeypatch.setattr(
        "memcommit.commands.find.connect_codex_chatgpt_provider",
        lambda: InterleavedProvider(),
    )

    result = runner.invoke(app, ["find", "anything"])

    assert result.exit_code == 0
    first_label = f"[memory  {first_child.uid[:8]}]"
    first_row = f"{first_label} First child line"
    continuation = " " * (len(first_label) + 1) + "continued detail"
    second_row = (
        f"[memory  {second_child.uid[:8]}] Second child result"
    )
    root_row = f"[memory  {root_memory.uid[:8]}] Root result"
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
    ref = ops.reference_memory(memory, source, parent)
    store.save(parent)
    store.set_current(parent.name)
    monkeypatch.setattr(
        "memcommit.commands.find.connect_codex_chatgpt_provider",
        lambda: KeywordProvider(),
    )

    result = runner.invoke(app, ["find", "parking"])

    assert result.exit_code == 0
    assert result.output == (
        "parent\n"
        f"[ref     {ref.uid[:8]}] "
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
        ["find", "parking", "--context", "searchable"],
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

    result = runner.invoke(app, ["find", "contractor"])

    assert result.exit_code == 0
    assert "facilities-reference\n" in result.output
    assert (
        f"[query   {ref.uid[:8]}] "
        "contractor-agreements (query-only)"
    ) in result.output
    assert "mem query" in result.output
    assert HIDDEN_SECRET not in result.output


def test_query_ref_hint_shell_quotes_untrusted_names(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    parent = ops.init("parent$(unsafe)")
    parent.add(
        QueryContextRef(
            uid="query-ref",
            name="policy$(unsafe)",
            target_source_uid="source",
            provider="codex_chatgpt",
        )
    )
    store.save(parent)
    store.set_current(parent.name)
    monkeypatch.setattr(
        "memcommit.commands.find.connect_codex_chatgpt_provider",
        lambda: KeywordProvider(),
    )

    result = runner.invoke(app, ["find", "policy"])

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

    no_current = runner.invoke(app, ["find", "anything"])
    missing = runner.invoke(
        app,
        ["find", "anything", "--context", "missing"],
    )
    assert no_current.exit_code == 1
    assert missing.exit_code == 1

    store = MemoryStore()
    ctx = ops.init("ctx")
    ops.add(ctx, "searchable")
    store.save(ctx)
    store.set_current("ctx")
    bad_limit = runner.invoke(app, ["find", "anything", "--limit", "0"])
    assert bad_limit.exit_code == 1
    assert "between 1 and 20" in bad_limit.stderr
