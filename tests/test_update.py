"""Directional semantic impact and staged update contracts."""
from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.store import MemoryStore
from memcommit.update import (
    AddOperation,
    EditOperation,
    UpdateError,
    UpdateSession,
    collect_update_inputs,
    plan_update,
    session_matches,
)


runner = CliRunner(mix_stderr=False)
SECRET = "The concealed contractor budget is 4.2 million dollars."


class PlanProvider:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls.append((prompt, operation, output_schema))
        response = self.response
        if callable(response):
            response = response(prompt)
        return (
            response
            if isinstance(response, str)
            else json.dumps(response)
        )


def _one_edit_response(prompt):
    payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
    source_id = payload["source"]["memories"][0]["source_id"]
    target = payload["target"]["memories"][0]
    return {
        "edits": [
            {
                "target_id": target["target_id"],
                "new_content": (
                    "The Main Building south entrance is open and provides "
                    "step-free access."
                ),
                "source_ids": [source_id],
                "reason": "The verified access update supersedes the old entrance.",
            }
        ],
        "additions": [],
    }


def _make_nested_pair():
    source = ops.init("construction-updates")
    source_child = ops.init("construction-updates/building-access")
    source_memory = ops.add(
        source_child,
        "Use the Main Building south entrance for step-free access.",
    )
    ops.embed(source_child, source)

    target = ops.init("campus/wiki")
    target_child = ops.init("campus/wiki/buildings")
    target_memory = ops.add(
        target_child,
        "The Main Building north entrance provides public access.",
    )
    ops.embed(target_child, target)
    return (
        source,
        source_child,
        source_memory,
        target,
        target_child,
        target_memory,
    )


def _persist_pair(store):
    (
        source,
        source_child,
        source_memory,
        target,
        target_child,
        target_memory,
    ) = _make_nested_pair()
    store.save(source_child)
    store.save(source)
    store.save(target_child)
    store.save(target)
    store.set_current(source.name)
    return source_memory, target_memory


def test_collect_update_inputs_recurses_and_records_owner_context():
    (
        source,
        source_child,
        source_memory,
        target,
        target_child,
        target_memory,
    ) = _make_nested_pair()

    inputs = collect_update_inputs(source, target)

    assert len(inputs.source_candidates) == 1
    source_candidate = inputs.source_candidates[0]
    assert source_candidate.context_uid == source_child.uid
    assert source_candidate.context_name == source_child.name
    assert source_candidate.memory_uid == source_memory.uid
    assert source_candidate.content == source_memory.content

    assert [candidate.context_name for candidate in inputs.target_contexts] == [
        target.name,
        target_child.name,
    ]
    assert len(inputs.target_memories) == 1
    target_candidate = inputs.target_memories[0]
    assert target_candidate.context_uid == target_child.uid
    assert target_candidate.context_name == target_child.name
    assert target_candidate.memory_uid == target_memory.uid


def test_collect_update_inputs_terminates_cycles_and_shared_contexts():
    source = ops.init("source")
    left = ops.init("source/left")
    right = ops.init("source/right")
    shared = ops.init("source/shared")
    shared_memory = ops.add(shared, "one shared source fact")
    source.add(left)
    source.add(right)
    left.add(shared)
    right.add(shared)
    shared.add(source)
    target = ops.init("target")

    inputs = collect_update_inputs(source, target)

    assert [
        candidate.memory_uid
        for candidate in inputs.source_candidates
    ] == [shared_memory.uid]
    assert len(inputs.source_contexts) == 4


def test_same_memory_uid_in_distinct_source_contexts_is_not_deduped():
    source = ops.init("source")
    first = Context(uid="first-context", name="source/first")
    second = Context(uid="second-context", name="source/second")
    first.add(Memory(uid="shared-memory", content="first version"))
    second.add(Memory(uid="shared-memory", content="second version"))
    source.add(first)
    source.add(second)
    target = ops.init("target")

    inputs = collect_update_inputs(source, target)

    assert [
        candidate.content
        for candidate in inputs.source_candidates
    ] == ["first version", "second version"]


def test_resolved_source_ref_is_evidence_and_target_refs_are_not_writable():
    origin = ops.init("origin")
    origin_memory = ops.add(origin, "referenced verified fact")
    source = ops.init("source")
    source.add(
        MemoryRef(
            uid="source-ref",
            target_context_uid=origin.uid,
            target_context_name=origin.name,
            target_memory_uid=origin_memory.uid,
            target=origin_memory,
        )
    )
    source.add(
        MemoryRef(
            uid="duplicate-source-ref",
            target_context_uid=origin.uid,
            target_context_name=origin.name,
            target_memory_uid=origin_memory.uid,
            target=origin_memory,
        )
    )
    target = ops.init("target")
    target.add(
        MemoryRef(
            uid="target-ref",
            target_context_uid=origin.uid,
            target_context_name=origin.name,
            target_memory_uid=origin_memory.uid,
            target=origin_memory,
        )
    )

    inputs = collect_update_inputs(source, target)

    assert len(inputs.source_candidates) == 1
    candidate = inputs.source_candidates[0]
    assert candidate.context_uid == origin.uid
    assert candidate.memory_uid == origin_memory.uid
    assert candidate.content == origin_memory.content
    assert inputs.target_memories == ()


def test_query_only_items_are_excluded_without_opening_hidden_source(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    hidden = store.create_query_source("restricted", SECRET)
    source = ops.init("source")
    source.add(
        QueryContextRef(
            uid="source-query-ref",
            name="restricted",
            target_source_uid=hidden.uid,
            provider="codex_chatgpt",
        )
    )
    ops.add(source, "public verified fact")
    target = ops.init("target")
    target.add(
        QueryContextRef(
            uid="target-query-ref",
            name="restricted",
            target_source_uid=hidden.uid,
            provider="codex_chatgpt",
        )
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("update opened a concealed query source")

    monkeypatch.setattr(MemoryStore, "load_query_source", forbidden)
    provider = PlanProvider({"edits": [], "additions": []})

    session = plan_update(source, target, lambda: provider)

    prompt = provider.calls[0][0]
    persisted = json.dumps(session.to_dict())
    assert SECRET not in prompt
    assert hidden.uid not in prompt
    assert "codex_chatgpt" not in prompt
    assert SECRET not in persisted


def test_plan_maps_model_ids_to_canonical_edit_add_and_provenance():
    (
        source,
        source_child,
        source_memory,
        target,
        target_child,
        target_memory,
    ) = _make_nested_pair()

    def response(prompt):
        payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
        source_id = payload["source"]["memories"][0]["source_id"]
        target_item = payload["target"]["memories"][0]
        root_context = payload["target"]["contexts"][0]
        return {
            "edits": [
                {
                    "target_id": target_item["target_id"],
                    "new_content": "Revised complete Wiki memory.",
                    "source_ids": [source_id],
                    "reason": "Verified source revises the Wiki.",
                }
            ],
            "additions": [
                {
                    "target_context_id": root_context["context_id"],
                    "new_content": "A separate newly supported Wiki fact.",
                    "source_ids": [source_id],
                    "reason": "No corresponding target memory exists.",
                }
            ],
        }

    provider = PlanProvider(response)
    session = plan_update(source, target, lambda: provider)

    assert session.status == "impact"
    assert len(session.operations) == 2
    edit, addition = session.operations
    assert isinstance(edit, EditOperation)
    assert edit.owner_context_uid == target_child.uid
    assert edit.memory_uid == target_memory.uid
    assert edit.old_content == target_memory.content
    assert edit.new_content == "Revised complete Wiki memory."
    assert edit.source_refs[0].context_uid == source_child.uid
    assert edit.source_refs[0].memory_uid == source_memory.uid

    assert isinstance(addition, AddOperation)
    assert addition.owner_context_uid == target.uid
    assert addition.owner_context_name == target.name
    assert addition.memory_uid not in {
        source_memory.uid,
        target_memory.uid,
    }
    assert provider.calls[0][1] == "update planning"
    schema = provider.calls[0][2]
    assert schema["additionalProperties"] is False


def test_noop_edits_and_exact_duplicate_additions_are_dropped():
    source = ops.init("source")
    ops.add(source, "same fact")
    target = ops.init("target")
    target_memory = ops.add(target, "same fact")

    def response(prompt):
        payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
        source_id = payload["source"]["memories"][0]["source_id"]
        target_id = payload["target"]["memories"][0]["target_id"]
        context_id = payload["target"]["contexts"][0]["context_id"]
        return {
            "edits": [
                {
                    "target_id": target_id,
                    "new_content": target_memory.content,
                    "source_ids": [source_id],
                    "reason": "Already exact.",
                }
            ],
            "additions": [
                {
                    "target_context_id": context_id,
                    "new_content": target_memory.content,
                    "source_ids": [source_id],
                    "reason": "Duplicate.",
                }
            ],
        }

    session = plan_update(source, target, lambda: PlanProvider(response))

    assert session.operations == ()


@pytest.mark.parametrize(
    "response",
    [
        None,
        "not json",
        '{"edits": [], "edits": [], "additions": []}',
        [],
        {"edits": []},
        {"edits": [], "additions": [], "extra": []},
        {"edits": "wrong", "additions": []},
        {
            "edits": [
                {
                    "target_id": "unknown",
                    "new_content": "new",
                    "source_ids": ["s000001"],
                    "reason": "reason",
                }
            ],
            "additions": [],
        },
        {
            "edits": [
                {
                    "target_id": "t000001",
                    "new_content": "new",
                    "source_ids": ["unknown"],
                    "reason": "reason",
                }
            ],
            "additions": [],
        },
        {
            "edits": [
                {
                    "target_id": "t000001",
                    "new_content": " ",
                    "source_ids": ["s000001"],
                    "reason": "reason",
                }
            ],
            "additions": [],
        },
        {
            "edits": [
                {
                    "target_id": "t000001",
                    "new_content": "new",
                    "source_ids": [],
                    "reason": "reason",
                }
            ],
            "additions": [],
        },
        {
            "edits": [
                {
                    "target_id": "t000001",
                    "new_content": "first",
                    "source_ids": ["s000001"],
                    "reason": "reason",
                },
                {
                    "target_id": "t000001",
                    "new_content": "second",
                    "source_ids": ["s000001"],
                    "reason": "reason",
                },
            ],
            "additions": [],
        },
        {
            "edits": [],
            "additions": [
                {
                    "target_context_id": "unknown",
                    "new_content": "new",
                    "source_ids": ["s000001"],
                    "reason": "reason",
                }
            ],
        },
    ],
)
def test_plan_rejects_malformed_or_unknown_provider_output(response):
    source = ops.init("source")
    ops.add(source, "source fact")
    target = ops.init("target")
    ops.add(target, "target fact")

    with pytest.raises(UpdateError):
        plan_update(source, target, lambda: PlanProvider(response))


def test_empty_source_and_overlapping_graph_fail_before_provider():
    calls = []

    def factory():
        calls.append("called")
        return PlanProvider({"edits": [], "additions": []})

    with pytest.raises(UpdateError, match="no readable Memories"):
        plan_update(ops.init("empty"), ops.init("target"), factory)

    source = ops.init("source")
    ops.add(source, "fact")
    shared = ops.init("shared")
    source.add(shared)
    target = ops.init("target")
    target.add(shared)
    with pytest.raises(UpdateError, match="overlap"):
        plan_update(source, target, factory)

    assert calls == []


def test_empty_target_still_allows_addition_to_root():
    source = ops.init("source")
    ops.add(source, "novel fact")
    target = ops.init("target")

    def response(prompt):
        payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
        return {
            "edits": [],
            "additions": [
                {
                    "target_context_id": payload["target"]["contexts"][0][
                        "context_id"
                    ],
                    "new_content": "novel fact",
                    "source_ids": [
                        payload["source"]["memories"][0]["source_id"]
                    ],
                    "reason": "Target is empty.",
                }
            ],
        }

    session = plan_update(source, target, lambda: PlanProvider(response))

    assert len(session.operations) == 1
    addition = session.operations[0]
    assert isinstance(addition, AddOperation)
    assert addition.owner_context_uid == target.uid


def test_update_session_round_trip_and_detects_input_changes():
    (
        source,
        source_child,
        _,
        target,
        target_child,
        _,
    ) = _make_nested_pair()
    session = plan_update(
        source,
        target,
        lambda: PlanProvider(_one_edit_response),
    )

    restored = UpdateSession.from_dict(session.to_dict())

    assert restored == session
    assert session_matches(restored, source, target)
    ops.add(source_child, "a later source fact")
    assert not session_matches(restored, source, target)
    source_child.remove(source_child.ordered_uids()[-1])
    assert session_matches(restored, source, target)
    ops.add(target_child, "a later target fact")
    assert not session_matches(restored, source, target)


def test_resolved_source_ref_content_change_invalidates_session():
    origin = ops.init("origin")
    memory = ops.add(origin, "first version")
    source = ops.init("source")
    ref = MemoryRef(
        uid="ref",
        target_context_uid=origin.uid,
        target_context_name=origin.name,
        target_memory_uid=memory.uid,
        target=memory,
    )
    source.add(ref)
    target = ops.init("target")
    session = plan_update(
        source,
        target,
        lambda: PlanProvider({"edits": [], "additions": []}),
    )

    ref.target = Memory(uid=memory.uid, content="second version")

    assert not session_matches(session, source, target)


def test_impact_then_update_reuses_plan_and_changes_no_context(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _persist_pair(store)
    provider = PlanProvider(_one_edit_response)
    connections = []

    def factory():
        connections.append("connected")
        return provider

    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        factory,
    )
    monkeypatch.setattr(
        "memcommit.commands.update.connect_codex_chatgpt_provider",
        factory,
    )
    context_bytes_before = {
        path: path.read_bytes()
        for path in (isolated_store / "contexts").rglob("*.json")
    }
    state_before = (isolated_store / "state.json").read_bytes()

    impact = runner.invoke(app, ["impact", "--to", "campus/wiki"])
    update = runner.invoke(app, ["update", "--to", "campus/wiki"])

    assert impact.exit_code == 0, impact.output
    assert "Impact: construction-updates -> campus/wiki" in impact.output
    assert "1 edit, 0 additions" in impact.output
    assert "No changes applied." in impact.output
    assert update.exit_code == 0, update.output
    assert "Staged update: construction-updates -> campus/wiki" in update.output
    assert "Shared campus/wiki is unchanged." in update.output
    assert connections == ["connected"]
    assert len(provider.calls) == 1

    impact_data = json.loads(
        (isolated_store / "impact-plan.json").read_text()
    )
    staged_data = json.loads(
        (isolated_store / "staged-update.json").read_text()
    )
    assert impact_data["uid"] == staged_data["uid"]
    assert impact_data["status"] == "impact"
    assert staged_data["status"] == "staged"
    assert {
        path: path.read_bytes()
        for path in (isolated_store / "contexts").rglob("*.json")
    } == context_bytes_before
    assert (isolated_store / "state.json").read_bytes() == state_before
    assert store.current_context_name() == "construction-updates"


def test_repeated_update_is_idempotent_and_does_not_reconnect(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _persist_pair(store)
    provider = PlanProvider(_one_edit_response)
    monkeypatch.setattr(
        "memcommit.commands.update.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    first = runner.invoke(app, ["update", "--to", "campus/wiki"])
    first_bytes = (isolated_store / "staged-update.json").read_bytes()
    second = runner.invoke(app, ["update", "--to", "campus/wiki"])

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert "already staged" in second.output
    assert len(provider.calls) == 1
    assert (isolated_store / "staged-update.json").read_bytes() == first_bytes


def test_stale_impact_replans_before_staging(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _persist_pair(store)
    provider = PlanProvider(_one_edit_response)
    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    monkeypatch.setattr(
        "memcommit.commands.update.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    impact = runner.invoke(app, ["impact", "--to", "campus/wiki"])
    assert impact.exit_code == 0
    source_child = store.load("construction-updates/building-access")
    ops.add(source_child, "Construction now runs through October.")
    store.save(source_child)

    update = runner.invoke(app, ["update", "--to", "campus/wiki"])

    assert update.exit_code == 0, update.output
    assert len(provider.calls) == 2
    impact_session = store.load_impact_plan()
    staged_session = store.load_staged_update()
    assert impact_session.uid != staged_session.uid
    assert staged_session.status == "staged"


def test_invalid_provider_output_leaves_contexts_and_sessions_unchanged(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _persist_pair(store)
    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: PlanProvider("not json"),
    )
    context_bytes_before = {
        path: path.read_bytes()
        for path in (isolated_store / "contexts").rglob("*.json")
    }

    result = runner.invoke(app, ["impact", "--to", "campus/wiki"])

    assert result.exit_code == 1
    assert "invalid structured output" in result.stderr
    assert not (isolated_store / "impact-plan.json").exists()
    assert not (isolated_store / "staged-update.json").exists()
    assert {
        path: path.read_bytes()
        for path in (isolated_store / "contexts").rglob("*.json")
    } == context_bytes_before


def test_update_requires_explicit_replace_for_a_different_stage(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _persist_pair(store)
    provider = PlanProvider(_one_edit_response)
    monkeypatch.setattr(
        "memcommit.commands.update.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    first = runner.invoke(app, ["update", "--to", "campus/wiki"])
    assert first.exit_code == 0

    other = ops.init("other-target")
    ops.add(other, "other old fact")
    store.save(other)
    refused = runner.invoke(app, ["update", "--to", "other-target"])

    assert refused.exit_code == 1
    assert "--replace-stage" in refused.stderr
    assert len(provider.calls) == 1


def test_missing_target_and_same_target_fail_without_traceback(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("source")
    ops.add(source, "fact")
    store.save(source)
    store.set_current("source")
    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: pytest.fail("provider should not connect"),
    )

    missing = runner.invoke(app, ["impact", "--to", "missing"])
    same = runner.invoke(app, ["impact", "--to", "source"])

    assert missing.exit_code == 1
    assert "not found" in missing.stderr
    assert same.exit_code == 1
    assert "cannot update itself" in same.stderr
    assert "Traceback" not in missing.output + same.output
