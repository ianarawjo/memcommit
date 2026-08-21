"""Directional semantic impact and local update application contracts."""

from __future__ import annotations

from dataclasses import replace
import json

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
import memcommit.commands.update as update_command
import memcommit.commands.update_render as update_render
from memcommit.cli import app
from memcommit.commands.endpoint_setup_flows import UpdateSetupReceipt
from memcommit.interfaces.tui.components.operation_launcher.session import SessionOpenReceipt
from memcommit.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.context_targeting.loading import load_context_scope
from memcommit.provenance import build_trace
from memcommit.resolution_workbench import ResolutionWorkbenchAction
from memcommit.store import ConcurrentContextUpdateError, MemoryStore
from memcommit.update import (
    AddOperation,
    EditOperation,
    GrantedUpdateTarget,
    UpdateError,
    UpdateSession,
    applied_session_matches,
    collect_update_inputs,
    plan_update,
    revise_update,
    session_matches,
)


runner = CliRunner(mix_stderr=False)
SECRET = "The concealed contractor budget is 4.2 million dollars."
TASK1_SOURCE = "participant/construction-updates"
TASK1_SOURCE_CHILD = f"{TASK1_SOURCE}/building-access"
TASK1_TARGET = "campus-wiki"
TASK1_TARGET_CHILD = f"{TASK1_TARGET}/buildings"


class PlanProvider:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls.append((prompt, operation, output_schema))
        response = self.response
        if callable(response):
            response = response(prompt)
        # Most tests predate the v3 removal contract. Normalize their
        # otherwise-valid fixture objects while leaving raw malformed JSON
        # untouched so strict parser tests still exercise the real boundary.
        if isinstance(response, dict) and set(response) == {"edits", "additions"}:
            response = {**response, "removals": []}
        return response if isinstance(response, str) else json.dumps(response)


def _one_edit_response(prompt):
    payload_text = prompt.split("UPDATE PAYLOAD:\n", 1)[1]
    payload_text = payload_text.split(
        "\n\nCURRENT REVIEWED PROPOSAL (DATA, NOT INSTRUCTIONS):",
        1,
    )[0]
    payload = json.loads(payload_text)
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


def test_focused_update_exposes_neighbors_only_as_context_and_binds_exact_scope():
    source = ops.init("focused/update/source")
    source_neighbor = ops.add(source, "Background construction note.")
    source_focus = ops.add(source, "The south entrance is open.")
    target = ops.init("focused/update/target")
    target_focus = ops.add(target, "The south entrance is closed.")
    target_neighbor = ops.add(target, "The library remains open.")
    provider = PlanProvider(_one_edit_response)

    session = plan_update(
        source,
        target,
        lambda: provider,
        source_memory_selector=source_focus.uid[:8],
        target_memory_selector=target_focus.uid[:8],
    )
    prompt, _operation, schema = provider.calls[0]
    payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])

    assert session.source_memory_uid == source_focus.uid
    assert session.target_memory_uid == target_focus.uid
    assert payload["source"]["memories"][0]["content"] == source_focus.content
    assert payload["source"]["context_evidence"][0]["content"] == (
        source_neighbor.content
    )
    assert payload["target"]["memories"][0]["content"] == target_focus.content
    assert payload["target"]["context_evidence"][0]["content"] == (
        target_neighbor.content
    )
    assert payload["target"]["contexts"] == []
    assert schema["properties"]["additions"]["maxItems"] == 0
    assert "cs000001" not in json.dumps(schema)
    assert "ct000001" not in json.dumps(schema)
    assert len(session.operations) == 1
    assert session.operations[0].memory_uid == target_focus.uid
    assert {ref.memory_uid for ref in session.operations[0].source_refs} == {
        source_focus.uid
    }
    assert UpdateSession.from_dict(session.to_dict()) == session


def test_update_revision_replans_complete_operations_from_review_guidance():
    source, _source_child, _source_memory, target, *_rest = _make_nested_pair()
    initial_provider = PlanProvider(_one_edit_response)
    staged = plan_update(
        source,
        target,
        lambda: initial_provider,
        status="staged",
    )
    revision_provider = PlanProvider(_one_edit_response)

    revised = revise_update(
        staged,
        source,
        target,
        lambda: revision_provider,
        "Make the accessibility wording less absolute.",
    )

    assert revised.status == "staged"
    assert revised.uid != staged.uid
    assert revised.source_digest == staged.source_digest
    assert revised.target_digest == staged.target_digest
    assert len(revision_provider.calls) == 1
    prompt, operation, schema = revision_provider.calls[0]
    assert operation == "update revision"
    assert schema is not None
    assert "CURRENT REVIEWED PROPOSAL (DATA, NOT INSTRUCTIONS)" in prompt
    assert "Make the accessibility wording less absolute." in prompt


def test_local_staged_update_auto_accepts_without_decision_rows(monkeypatch):
    source, _source_child, _source_memory, target, *_rest = _make_nested_pair()
    staged = plan_update(
        source,
        target,
        lambda: PlanProvider(_one_edit_response),
        status="staged",
    )
    captured = []

    def approve(view, **kwargs):
        captured.append((view, kwargs))
        return ResolutionWorkbenchAction(kind="ACCEPT")

    monkeypatch.setattr(update_render, "run_resolution_workbench_shell", approve)

    reviewed = update_render.review_update_application(
        staged,
        incorporate=lambda *_args: pytest.fail("no revision was requested"),
    )

    assert reviewed is staged
    view, kwargs = captured[0]
    assert all(item.effective_obligation == "NONE" for item in view.items)
    assert kwargs["review_and_apply"] is True
    assert kwargs["decision_free_behavior"] == "AUTO_ACCEPT"


def test_granted_source_local_target_update_keeps_local_auto_accept(monkeypatch):
    source, _source_child, _source_memory, target, *_rest = _make_nested_pair()
    staged = plan_update(
        source,
        target,
        lambda: PlanProvider(_one_edit_response),
        status="staged",
    )
    staged = replace(
        staged,
        granted_source=GrantedUpdateTarget(
            public_name="shared/construction-updates",
            grantee_profile_uid="11111111-1111-4111-8111-111111111111",
            authority_profile_uid="22222222-2222-4222-8222-222222222222",
            attachment_context_uid="attachment-context",
            attachment_context_name="shared",
            grant_uid="33333333-3333-4333-8333-333333333333",
            grant_revision=1,
            grant_digest="a" * 64,
            resource_uid=source.uid,
            resource_name=source.name,
            authority_context_name=source.name,
            permissions=("READ", "DERIVE", "EXPORT"),
        ),
    )
    captured = []

    def approve(view, **kwargs):
        captured.append((view, kwargs))
        return ResolutionWorkbenchAction(kind="ACCEPT")

    monkeypatch.setattr(update_render, "run_resolution_workbench_shell", approve)

    reviewed = update_render.review_update_application(
        staged,
        incorporate=lambda *_args: pytest.fail("no revision was requested"),
    )

    assert reviewed is staged
    assert captured[0][1]["decision_free_behavior"] == "AUTO_ACCEPT"


def test_granted_target_update_retains_exact_final_review(monkeypatch):
    source, _source_child, _source_memory, target, *_rest = _make_nested_pair()
    staged = plan_update(
        source,
        target,
        lambda: PlanProvider(_one_edit_response),
        status="staged",
    )
    staged = replace(
        staged,
        granted_target=GrantedUpdateTarget(
            public_name="shared/campus-wiki",
            grantee_profile_uid="11111111-1111-4111-8111-111111111111",
            authority_profile_uid="22222222-2222-4222-8222-222222222222",
            attachment_context_uid="attachment-context",
            attachment_context_name="shared",
            grant_uid="33333333-3333-4333-8333-333333333333",
            grant_revision=1,
            grant_digest="a" * 64,
            resource_uid=target.uid,
            resource_name=target.name,
            authority_context_name=target.name,
            permissions=("READ", "UPDATE"),
        ),
    )
    captured = []

    def close(view, **kwargs):
        captured.append((view, kwargs))
        return ResolutionWorkbenchAction(kind="CLOSE")

    monkeypatch.setattr(update_render, "run_resolution_workbench_shell", close)

    reviewed = update_render.review_update_application(
        staged,
        incorporate=lambda *_args: pytest.fail("no revision was requested"),
    )

    assert reviewed is None
    assert captured[0][1]["decision_free_behavior"] == "FINAL_REVIEW"


def test_granted_target_noop_auto_accepts_without_authority_review(monkeypatch):
    source, _source_child, _source_memory, target, *_rest = _make_nested_pair()
    staged = plan_update(
        source,
        target,
        lambda: PlanProvider({"edits": [], "additions": []}),
        status="staged",
    )
    staged = replace(
        staged,
        granted_target=GrantedUpdateTarget(
            public_name="shared/campus-wiki",
            grantee_profile_uid="11111111-1111-4111-8111-111111111111",
            authority_profile_uid="22222222-2222-4222-8222-222222222222",
            attachment_context_uid="attachment-context",
            attachment_context_name="shared",
            grant_uid="33333333-3333-4333-8333-333333333333",
            grant_revision=1,
            grant_digest="a" * 64,
            resource_uid=target.uid,
            resource_name=target.name,
            authority_context_name=target.name,
            permissions=("READ", "UPDATE"),
        ),
    )
    captured = []

    def approve(view, **kwargs):
        captured.append((view, kwargs))
        return ResolutionWorkbenchAction(kind="ACCEPT")

    monkeypatch.setattr(update_render, "run_resolution_workbench_shell", approve)

    reviewed = update_render.review_update_application(
        staged,
        incorporate=lambda *_args: pytest.fail("no revision was requested"),
    )

    assert reviewed is staged
    assert staged.operations == ()
    assert captured[0][1]["decision_free_behavior"] == "AUTO_ACCEPT"


def _edit_and_root_add_response(prompt):
    payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
    source_id = payload["source"]["memories"][0]["source_id"]
    target = payload["target"]["memories"][0]
    root = payload["target"]["contexts"][0]
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
        "additions": [
            {
                "target_context_id": root["context_id"],
                "new_content": "Construction visitor guidance is in effect.",
                "source_ids": [source_id],
                "reason": "The campus wiki needs an overview notice.",
            }
        ],
    }


def _make_nested_pair():
    source = ops.init(TASK1_SOURCE)
    source_child = ops.init(TASK1_SOURCE_CHILD)
    source_memory = ops.add(
        source_child,
        "Use the Main Building south entrance for step-free access.",
    )
    ops.embed(source_child, source)

    target = ops.init(TASK1_TARGET)
    target.add(
        QueryContextRef(
            uid="11111111-1111-4111-8111-111111111111",
            name="construction-details",
            target_source_uid="22222222-2222-4222-8222-222222222222",
            provider="codex_chatgpt",
        )
    )
    target_child = ops.init(TASK1_TARGET_CHILD)
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


def test_task1_sized_frame_reaches_provider_without_operation_count_gate():
    source = Context(uid="task1-source", name=TASK1_SOURCE)
    for index in range(75):
        source.add(
            Memory(
                uid=f"source-memory-{index}",
                content=f"Verified construction update {index}.",
            )
        )
    target = Context(uid="task1-target", name=TASK1_TARGET)
    for index in range(300):
        target.add(
            Memory(
                uid=f"target-memory-{index}",
                content=f"Existing campus wiki fact {index}.",
            )
        )
    provider = PlanProvider(
        {"edits": [], "additions": [], "removals": []}
    )

    session = plan_update(source, target, lambda: provider, status="staged")

    assert len(provider.calls) == 1
    assert session.operations == ()
    schema = provider.calls[0][2]
    assert schema["properties"]["edits"]["maxItems"] == 300
    assert schema["properties"]["additions"]["maxItems"] == 75
    assert schema["properties"]["removals"]["maxItems"] == 300


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

    assert [candidate.memory_uid for candidate in inputs.source_candidates] == [
        shared_memory.uid
    ]
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

    assert [candidate.content for candidate in inputs.source_candidates] == [
        "first version",
        "second version",
    ]


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
    assert "store only the content payload" in prompt
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
        '{"edits": [], "additions": []}',
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


def test_descendant_scope_loads_lexical_children_and_applies_to_child_owner(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("source")
    source_child = ops.init("source/child")
    ops.add(source_child, "new child fact")
    target = ops.init("target")
    target_child = ops.init("target/child")
    target_memory = ops.add(target_child, "old child fact")
    for context in (source, source_child, target, target_child):
        store.create_context(context)

    source_scope = load_context_scope(
        store,
        source.name,
        include_descendants=True,
    )
    target_scope = load_context_scope(
        store,
        target.name,
        include_descendants=True,
    )

    def response(prompt):
        payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
        return {
            "edits": [
                {
                    "target_id": payload["target"]["memories"][0]["target_id"],
                    "new_content": "updated child fact",
                    "source_ids": [payload["source"]["memories"][0]["source_id"]],
                    "reason": "The source updates the child-owned fact.",
                }
            ],
            "additions": [],
            "removals": [],
        }

    session = plan_update(
        source_scope,
        target_scope,
        lambda: PlanProvider(response),
        status="staged",
        source_include_descendants=True,
        target_include_descendants=True,
    )
    store.save_staged_update(session, expected_current=None)
    applied = store.apply_staged_update(session)

    assert applied.source_include_descendants is True
    assert applied.target_include_descendants is True
    updated = store.load_direct(target_child.name).memories[target_memory.uid]
    assert isinstance(updated, Memory)
    assert updated.content == "updated child fact"


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
                    "target_context_id": payload["target"]["contexts"][0]["context_id"],
                    "new_content": "novel fact",
                    "source_ids": [payload["source"]["memories"][0]["source_id"]],
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


def test_schema_one_update_session_remains_readable():
    source, _, _, target, _, _ = _make_nested_pair()
    session = plan_update(
        source,
        target,
        lambda: PlanProvider(_one_edit_response),
    )
    legacy = session.to_dict()
    legacy["schema_version"] = 1
    legacy.pop("application")
    legacy["source"].pop("access")
    legacy["source"].pop("include_descendants")
    legacy["target"].pop("access")
    legacy["target"].pop("include_descendants")

    assert UpdateSession.from_dict(legacy) == session


def test_planning_and_status_promotion_cannot_forge_applied_state():
    source, _, _, target, _, _ = _make_nested_pair()
    provider_calls = []

    def provider_factory():
        provider_calls.append("connected")
        return PlanProvider(_one_edit_response)

    with pytest.raises(ValueError, match="impact or staged"):
        plan_update(
            source,
            target,
            provider_factory,
            status="applied",
        )
    session = plan_update(source, target, provider_factory)
    with pytest.raises(ValueError, match="application receipt"):
        session.with_status("applied")

    assert provider_calls == ["connected"]


def test_active_update_compare_and_swap_preserves_concurrent_record(
    isolated_store,
):
    store = MemoryStore()
    _persist_pair(store)
    source = store.load(TASK1_SOURCE)
    target = store.load(TASK1_TARGET)
    staged = plan_update(
        source,
        target,
        lambda: PlanProvider(_one_edit_response),
        status="staged",
    )
    store.save_staged_update(staged, expected_current=None)

    with pytest.raises(
        ConcurrentContextUpdateError,
        match="active update record changed",
    ):
        store.save_staged_update(
            staged.with_status("impact"),
            expected_current=None,
        )

    assert store.load_staged_update() == staged


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


def test_impact_then_update_reuses_plan_and_materializes_local_fork(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _, target_memory = _persist_pair(store)
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
    source_bytes_before = {
        path: path.read_bytes()
        for path in (
            isolated_store / "contexts" / "participant" / "construction-updates"
        ).rglob("context.json")
    }
    state_before = (isolated_store / "state.json").read_bytes()

    impact = runner.invoke(app, ["impact", "-r", "--to", TASK1_TARGET])
    update = runner.invoke(app, ["update", "-r", "--to", TASK1_TARGET])

    assert impact.exit_code == 0, impact.output
    assert f"Impact: {TASK1_SOURCE} -> {TASK1_TARGET}" in impact.output
    assert "1 edit, 0 additions" in impact.output
    assert "No changes applied." in impact.output
    assert update.exit_code == 0, update.output
    assert f"UPDATE APPLIED · {TASK1_SOURCE} → {TASK1_TARGET}" in update.output
    assert "REVIEW · mem review update --session" in update.output
    assert "RECOVERY · mem undo" in update.output
    assert connections == ["connected"]
    assert len(provider.calls) == 1

    impact_data = json.loads((isolated_store / "impact-plan.json").read_text())
    staged_data = json.loads((isolated_store / "staged-update.json").read_text())
    assert impact_data["uid"] == staged_data["uid"]
    assert impact_data["status"] == "impact"
    assert staged_data["status"] == "applied"
    assert staged_data["application"] is not None
    assert len(staged_data["application"]["checkpoints"]) == 1

    updated_child = store.load_direct(TASK1_TARGET_CHILD)
    assert updated_child.memories[target_memory.uid].content == (
        "The Main Building south entrance is open and provides step-free access."
    )
    checkpoints = store.list_checkpoints(TASK1_TARGET_CHILD)
    assert len(checkpoints) == 1
    checkpoint = checkpoints[0]
    assert checkpoint["auto"] is True
    assert checkpoint["command"] == "update"
    assert checkpoint["args"]["update_session_uid"] == staged_data["uid"]
    assert checkpoint["args"]["target_context_name"] == TASK1_TARGET
    assert checkpoint["args"]["owner_context_uid"] == updated_child.uid
    assert checkpoint["args"]["operation_memory_uids"] == [target_memory.uid]
    assert staged_data["application"]["checkpoints"][0] == {
        "context_uid": updated_child.uid,
        "context_name": TASK1_TARGET_CHILD,
        "checkpoint_uid": checkpoint["uid"],
    }

    fork_root = store.load_direct(TASK1_TARGET)
    origin_pointer = fork_root.memories["11111111-1111-4111-8111-111111111111"]
    assert isinstance(origin_pointer, QueryContextRef)
    assert origin_pointer.name == "construction-details"
    assert not store.context_exists("construction-details")
    assert {
        path: path.read_bytes()
        for path in (
            isolated_store / "contexts" / "participant" / "construction-updates"
        ).rglob("context.json")
    } == source_bytes_before
    assert (isolated_store / "state.json").read_bytes() == state_before
    assert store.current_context_name() == TASK1_SOURCE


def test_tty_update_keeps_stage_when_impact_apply_review_is_closed(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _, target_memory = _persist_pair(store)
    target_before = store.load_direct(TASK1_TARGET_CHILD)
    monkeypatch.setattr(
        update_command,
        "connect_codex_chatgpt_provider",
        lambda: PlanProvider(_one_edit_response),
    )
    monkeypatch.setattr(update_command, "_interactive_terminal", lambda: True)
    reviewed = []
    monkeypatch.setattr(
        update_command,
        "review_update_application",
        lambda session, *, incorporate: reviewed.append(session) or None,
    )

    result = runner.invoke(app, ["update", "--to", TASK1_TARGET])

    assert result.exit_code == 0, result.output
    assert "UPDATE INCOMPLETE" in result.output
    assert "No target changes were applied. Resume with mem update." in result.output
    assert len(reviewed) == 1
    staged = store.load_staged_update()
    assert staged is not None
    assert staged.status == "staged"
    assert staged.application is None
    target_after = store.load_direct(TASK1_TARGET_CHILD)
    assert target_after.memories[target_memory.uid].content == (
        target_before.memories[target_memory.uid].content
    )


def test_tty_update_incorporates_review_comment_before_applying(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _persist_pair(store)
    provider = PlanProvider(_one_edit_response)
    monkeypatch.setattr(
        update_command,
        "connect_codex_chatgpt_provider",
        lambda: provider,
    )
    monkeypatch.setattr(update_command, "_interactive_terminal", lambda: True)
    revisions: list[tuple[UpdateSession, UpdateSession]] = []
    wait_views = []
    progress_updates = []

    class Progress:
        def update(self, stage, *, step):
            progress_updates.append((stage, step))

    def wait(
        operation,
        stage,
        *,
        total,
        work,
        return_view=None,
        context_view=None,
    ):
        wait_views.append((operation, stage, total, return_view, context_view))
        return work(Progress())

    monkeypatch.setattr(update_command, "run_command_wait", wait)

    def review(session, *, incorporate):
        revised = incorporate(
            session,
            "Make the accessibility wording less absolute.",
        )
        revisions.append((session, revised))
        return revised

    monkeypatch.setattr(update_command, "review_update_application", review)

    result = runner.invoke(app, ["update", "--to", TASK1_TARGET])

    assert result.exit_code == 0, result.output
    assert [call[1] for call in provider.calls] == [
        "update planning",
        "update revision",
    ]
    original, revised = revisions[0]
    assert revised.uid != original.uid
    applied = store.load_staged_update()
    assert applied is not None
    assert applied.status == "applied"
    assert applied.uid == revised.uid
    assert [view[0:3] for view in wait_views] == [
        ("UPDATE", "connecting provider", 2),
        ("UPDATE", "connecting provider", 2),
    ]
    assert wait_views[0][3:] == (None, None)

    revision_report = wait_views[1][3]
    assert revision_report.title == "PREVIOUS UPDATE REPORT · READ-ONLY"
    assert "Staged update:" in revision_report.text
    assert "PENDING REVISION · SUBMITTED · NOT YET INCORPORATED" in (
        revision_report.text
    )
    assert "Make the accessibility wording less absolute." in revision_report.text
    assert "REVISION COMMENT · SUBMITTED" in wait_views[1][4].text
    assert progress_updates == [
        ("planning memory changes", 2),
        ("incorporating review comments", 2),
    ]


def test_update_undo_and_redo_follow_the_affected_target_not_current_context(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _, target_memory = _persist_pair(store)
    provider = PlanProvider(_one_edit_response)
    monkeypatch.setattr(
        "memcommit.commands.update.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    original = store.load_direct(TASK1_TARGET_CHILD).memories[target_memory.uid].content

    update = runner.invoke(app, ["update", "--to", TASK1_TARGET])

    assert update.exit_code == 0, update.output
    assert store.current_context_name() == TASK1_SOURCE
    assert (
        store.load_direct(TASK1_TARGET_CHILD).memories[target_memory.uid].content
        != original
    )

    undo = runner.invoke(app, ["undo"])

    assert undo.exit_code == 0, undo.output
    assert (
        f"Undid command: mem update --from {TASK1_SOURCE} --to {TASK1_TARGET}"
        in undo.output
    )
    assert store.current_context_name() == TASK1_SOURCE
    assert (
        store.load_direct(TASK1_TARGET_CHILD).memories[target_memory.uid].content
        == original
    )
    undone_session = store.load_staged_update()
    assert undone_session.status == "undone"
    assert undone_session.application is not None
    undone_diff = runner.invoke(app, ["diff"])
    assert undone_diff.exit_code == 0, undone_diff.output
    assert "Undone update" in undone_diff.output

    redo = runner.invoke(app, ["redo"])

    assert redo.exit_code == 0, redo.output
    assert (
        f"Redid command: mem update --from {TASK1_SOURCE} --to {TASK1_TARGET}"
        in redo.output
    )
    assert store.current_context_name() == TASK1_SOURCE
    assert store.load_direct(TASK1_TARGET_CHILD).memories[
        target_memory.uid
    ].content == (
        "The Main Building south entrance is open and provides step-free access."
    )
    redone_session = store.load_staged_update()
    assert redone_session.status == "applied"
    assert redone_session.application == undone_session.application
    assert [
        entry["command"] for entry in store.list_checkpoints(TASK1_TARGET_CHILD)[:3]
    ] == ["redo", "undo", "update"]


def test_impact_then_update_resolve_relative_existing_target(
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

    impact = runner.invoke(
        app,
        ["impact", "--to", "../../campus-wiki"],
    )
    update = runner.invoke(
        app,
        ["update", "--to", "../../campus-wiki"],
    )

    assert impact.exit_code == 0, impact.output
    assert update.exit_code == 0, update.output
    assert TASK1_TARGET in impact.output
    assert TASK1_TARGET in update.output
    assert len(provider.calls) == 1


@pytest.mark.parametrize("command", ["impact", "update"])
def test_directional_endpoint_help_explains_current_complement(command):
    result = runner.invoke(app, [command, "--help"])

    assert result.exit_code == 0, result.output
    normalized = " ".join(result.output.replace("│", "").split())
    assert "if --to is omitted, current supplies B" in normalized
    assert "if --from is omitted, current supplies A" in normalized


def test_impact_then_update_accept_from_with_current_target(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _persist_pair(store)
    store.set_current(TASK1_TARGET)
    provider = PlanProvider(_one_edit_response)
    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    monkeypatch.setattr(
        "memcommit.commands.update.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    impact = runner.invoke(app, ["impact", "--from", TASK1_SOURCE])
    update = runner.invoke(app, ["update", "--from", TASK1_SOURCE])

    assert impact.exit_code == 0, impact.output
    assert update.exit_code == 0, update.output
    assert f"Impact: {TASK1_SOURCE} -> {TASK1_TARGET}" in impact.output
    assert f"UPDATE APPLIED · {TASK1_SOURCE} → {TASK1_TARGET}" in update.output
    assert store.current_context_name() == TASK1_TARGET
    assert len(provider.calls) == 1


def test_cross_spelling_update_reuses_from_only_impact_plan(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _persist_pair(store)
    store.set_current(TASK1_TARGET)
    provider = PlanProvider(_one_edit_response)
    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    monkeypatch.setattr(
        "memcommit.commands.update.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    impact = runner.invoke(app, ["impact", "--from", TASK1_SOURCE])
    impact_session = store.load_impact_plan()
    anchor = ops.init("participant/after-impact")
    store.save(anchor)
    store.set_current(anchor.name)
    update = runner.invoke(
        app,
        [
            "update",
            "--from",
            TASK1_SOURCE,
            "--to",
            TASK1_TARGET,
        ],
    )
    applied_session = store.load_staged_update()

    assert impact.exit_code == 0, impact.output
    assert update.exit_code == 0, update.output
    assert impact_session is not None
    assert applied_session is not None
    assert applied_session.uid == impact_session.uid
    assert store.current_context_name() == anchor.name
    assert len(provider.calls) == 1


def test_explicit_from_and_to_work_without_current_context(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source, source_child, _, target, target_child, _ = _make_nested_pair()
    for context in (source_child, source, target_child, target):
        store.save(context)
    provider = PlanProvider(_one_edit_response)
    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    monkeypatch.setattr(
        "memcommit.commands.update.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    endpoints = [
        "--from",
        TASK1_SOURCE,
        "--to",
        TASK1_TARGET,
    ]
    impact = runner.invoke(app, ["impact", *endpoints])
    update = runner.invoke(app, ["update", *endpoints])

    assert impact.exit_code == 0, impact.output
    assert update.exit_code == 0, update.output
    assert f"Impact: {TASK1_SOURCE} -> {TASK1_TARGET}" in impact.output
    assert f"UPDATE APPLIED · {TASK1_SOURCE} → {TASK1_TARGET}" in update.output
    assert store.current_context_name() is None
    assert len(provider.calls) == 1


def test_from_and_to_relative_locators_share_one_current_snapshot(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _persist_pair(store)
    anchor = ops.init("participant/endpoint-anchor")
    store.save(anchor)
    store.set_current(anchor.name)
    provider = PlanProvider(_one_edit_response)
    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    monkeypatch.setattr(
        "memcommit.commands.update.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    endpoints = [
        "--from",
        "../construction-updates",
        "--to",
        "../../campus-wiki",
    ]
    impact = runner.invoke(app, ["impact", *endpoints])
    update = runner.invoke(app, ["update", *endpoints])

    assert impact.exit_code == 0, impact.output
    assert update.exit_code == 0, update.output
    assert f"Impact: {TASK1_SOURCE} -> {TASK1_TARGET}" in impact.output
    assert f"UPDATE APPLIED · {TASK1_SOURCE} → {TASK1_TARGET}" in update.output
    assert len(provider.calls) == 1


@pytest.mark.parametrize(
    ("command", "endpoint", "message"),
    [
        (
            "impact",
            ["--from", TASK1_SOURCE],
            "No current target Context. Supply '--to TARGET'.",
        ),
        (
            "update",
            ["--to", TASK1_TARGET],
            "No current source Context. Supply '--from SOURCE'.",
        ),
    ],
)
def test_omitted_endpoint_requires_current_context(
    isolated_store,
    monkeypatch,
    command,
    endpoint,
    message,
):
    store = MemoryStore()
    source, source_child, _, target, target_child, _ = _make_nested_pair()
    for context in (source_child, source, target_child, target):
        store.save(context)
    monkeypatch.setattr(
        f"memcommit.commands.{command}.connect_codex_chatgpt_provider",
        lambda: pytest.fail("provider should not connect"),
    )

    result = runner.invoke(app, [command, *endpoint])

    assert result.exit_code == 1
    assert message in result.stderr


def test_bare_update_reports_empty_saved_session_outside_tty(
    isolated_store,
    monkeypatch,
):
    monkeypatch.setattr(
        "memcommit.commands.update.connect_codex_chatgpt_provider",
        lambda: pytest.fail("provider should not connect"),
    )

    result = runner.invoke(app, ["update"])

    assert result.exit_code == 0
    assert "No saved Update session." in result.output


def test_empty_update_launcher_new_collects_distinct_endpoints(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()

    class TTY:
        @staticmethod
        def isatty():
            return True

    monkeypatch.setattr(update_command.sys, "stdin", TTY())
    monkeypatch.setattr(update_command.sys, "stdout", TTY())
    monkeypatch.setattr(
        update_command,
        "choose_session",
        lambda entries, **kwargs: (
            kwargs["new_receipt"]
            if entries == ()
            else pytest.fail("empty Update unexpectedly had a saved row")
        ),
    )
    monkeypatch.setattr(
        update_command,
        "choose_update_setup",
        lambda _store: UpdateSetupReceipt("source", "target"),
    )
    invoked = []
    monkeypatch.setattr(
        update_command,
        "cmd",
        lambda **kwargs: invoked.append(kwargs),
    )

    update_command._browse_saved_update(store)

    assert invoked == [
        {
            "source_name": "source",
            "target_name": "target",
            "source_descendants": False,
            "target_descendants": False,
        }
    ]


def test_empty_update_launcher_passes_exact_setup_memories(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()

    class TTY:
        @staticmethod
        def isatty():
            return True

    monkeypatch.setattr(update_command.sys, "stdin", TTY())
    monkeypatch.setattr(update_command.sys, "stdout", TTY())
    monkeypatch.setattr(
        update_command,
        "choose_session",
        lambda entries, **kwargs: kwargs["new_receipt"],
    )
    monkeypatch.setattr(
        update_command,
        "choose_update_setup",
        lambda _store: UpdateSetupReceipt(
            "source",
            "target",
            source_memory_uid="source-memory",
            target_memory_uid="target-memory",
        ),
    )
    invoked = []
    monkeypatch.setattr(update_command, "cmd", lambda **kwargs: invoked.append(kwargs))

    update_command._browse_saved_update(store)

    assert invoked == [
        {
            "source_name": "source",
            "target_name": "target",
            "source_descendants": False,
            "target_descendants": False,
            "source_memory": "source-memory",
            "target_memory": "target-memory",
        }
    ]


def test_saved_update_launcher_opens_state_aware_interactive_workbench(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source, source_child, _, target, target_child, _ = _make_nested_pair()
    for context in (source_child, source, target_child, target):
        store.save(context)
    session = plan_update(
        source,
        target,
        lambda: PlanProvider(_one_edit_response),
        status="staged",
    )
    store.save_staged_update(session, expected_current=None)

    class TTY:
        @staticmethod
        def isatty():
            return True

    monkeypatch.setattr(update_command.sys, "stdin", TTY())
    monkeypatch.setattr(update_command.sys, "stdout", TTY())
    monkeypatch.setattr(
        update_command,
        "choose_session",
        lambda entries, **_kwargs: SessionOpenReceipt(
            kind="update",
            key=entries[0].key,
            argv=entries[0].reopen_argv,
        ),
    )
    opened = []
    monkeypatch.setattr(
        update_command,
        "_run_saved_update_workbench",
        lambda opened_session: opened.append(opened_session) or False,
    )
    monkeypatch.setattr(update_command.typer, "echo", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        update_command,
        "render_plan",
        lambda *_args, **_kwargs: pytest.fail(
            "interactive saved Update fell back to the static plan dump"
        ),
    )

    update_command._browse_saved_update(store)

    assert len(opened) == 1
    opened_session = opened[0]
    assert opened_session == session


def test_saved_update_workbench_handoff_reenters_normal_update_command(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source, source_child, _, target, target_child, _ = _make_nested_pair()
    for context in (source_child, source, target_child, target):
        store.save(context)
    session = plan_update(
        source,
        target,
        lambda: PlanProvider(_one_edit_response),
        status="staged",
    )
    store.save_staged_update(session, expected_current=None)

    class TTY:
        @staticmethod
        def isatty():
            return True

    monkeypatch.setattr(update_command.sys, "stdin", TTY())
    monkeypatch.setattr(update_command.sys, "stdout", TTY())
    monkeypatch.setattr(
        update_command,
        "choose_session",
        lambda entries, **_kwargs: SessionOpenReceipt(
            kind="update",
            key=entries[0].key,
            argv=entries[0].reopen_argv,
        ),
    )
    opened = []
    handoffs = iter((True, False))

    def open_workbench(opened_session):
        opened.append(opened_session)
        return next(handoffs)

    monkeypatch.setattr(
        update_command,
        "_run_saved_update_workbench",
        open_workbench,
    )
    monkeypatch.setattr(update_command.typer, "echo", lambda *_args, **_kwargs: None)
    invoked = []
    monkeypatch.setattr(update_command, "cmd", lambda **kwargs: invoked.append(kwargs))

    update_command._browse_saved_update(store)

    assert invoked == [
        {
            "source_name": session.source_name,
            "target_name": session.target_name,
            "replace_stage": False,
            "source_descendants": session.source_include_descendants,
            "target_descendants": session.target_include_descendants,
        }
    ]
    assert opened == [session, session]


@pytest.mark.parametrize("command", ["impact", "update"])
def test_directional_commands_reject_same_canonical_endpoints(
    isolated_store,
    monkeypatch,
    command,
):
    store = MemoryStore()
    context = ops.init("participant/source")
    store.save(context)
    store.set_current(context.name)
    monkeypatch.setattr(
        f"memcommit.commands.{command}.connect_codex_chatgpt_provider",
        lambda: pytest.fail("provider should not connect"),
    )

    result = runner.invoke(
        app,
        [
            command,
            "--from",
            ".",
            "--to",
            "participant/source",
        ],
    )

    assert result.exit_code == 1
    assert "Source and target Contexts must be distinct" in result.stderr


def test_task1_query_only_origin_cannot_be_an_update_target(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _persist_pair(store)
    monkeypatch.setattr(
        "memcommit.commands.update.connect_codex_chatgpt_provider",
        lambda: pytest.fail("provider should not connect"),
    )

    result = runner.invoke(app, ["update", "--to", "construction-details"])

    assert result.exit_code == 1
    assert "Context 'construction-details' not found" in result.stderr
    assert not (isolated_store / "staged-update.json").exists()
    assert not store.context_exists("construction-details")


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

    first = runner.invoke(app, ["update", "--to", TASK1_TARGET])
    first_bytes = (isolated_store / "staged-update.json").read_bytes()
    checkpoints_before = store.list_checkpoints(TASK1_TARGET_CHILD)
    second = runner.invoke(app, ["update", "--to", TASK1_TARGET])

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert "receipt was already applied" in second.output
    assert len(provider.calls) == 1
    assert (isolated_store / "staged-update.json").read_bytes() == first_bytes
    assert store.list_checkpoints(TASK1_TARGET_CHILD) == checkpoints_before


def test_stale_impact_replans_before_applying(
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

    impact = runner.invoke(app, ["impact", "--to", TASK1_TARGET])
    assert impact.exit_code == 0
    source_child = store.load(TASK1_SOURCE_CHILD)
    ops.add(source_child, "Construction now runs through October.")
    store.save(source_child)

    update = runner.invoke(app, ["update", "--to", TASK1_TARGET])

    assert update.exit_code == 0, update.output
    assert len(provider.calls) == 2
    impact_session = store.load_impact_plan()
    staged_session = store.load_staged_update()
    assert impact_session.uid != staged_session.uid
    assert staged_session.status == "applied"
    assert staged_session.application is not None


def test_update_applies_multiple_owners_with_one_checkpoint_each(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _, target_memory = _persist_pair(store)
    provider = PlanProvider(_edit_and_root_add_response)
    monkeypatch.setattr(
        "memcommit.commands.update.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    result = runner.invoke(app, ["update", "--to", TASK1_TARGET])

    assert result.exit_code == 0, result.output
    applied = store.load_staged_update()
    assert applied.status == "applied"
    assert applied.application is not None
    assert applied_session_matches(
        applied,
        store.load(TASK1_SOURCE),
        store.load(TASK1_TARGET),
    )

    root_addition = next(
        operation
        for operation in applied.operations
        if isinstance(operation, AddOperation)
    )
    root = store.load_direct(TASK1_TARGET)
    child = store.load_direct(TASK1_TARGET_CHILD)
    assert root.memories[root_addition.memory_uid].content == (
        "Construction visitor guidance is in effect."
    )
    assert child.memories[target_memory.uid].content.startswith(
        "The Main Building south entrance is open"
    )

    receipts = applied.application.checkpoints
    assert [receipt.context_name for receipt in receipts] == [
        TASK1_TARGET,
        TASK1_TARGET_CHILD,
    ]
    for receipt in receipts:
        checkpoints = store.list_checkpoints(receipt.context_name)
        assert len(checkpoints) == 1
        checkpoint = checkpoints[0]
        assert checkpoint["uid"] == receipt.checkpoint_uid
        assert checkpoint["auto"] is True
        assert checkpoint["command"] == "update"
        assert checkpoint["args"]["update_session_uid"] == applied.uid
        assert checkpoint["args"]["operation_digest"] == (
            applied.application.operation_digest
        )


def test_multi_context_update_is_one_atomic_undo_and_redo_unit(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _, target_memory = _persist_pair(store)
    provider = PlanProvider(_edit_and_root_add_response)
    monkeypatch.setattr(
        "memcommit.commands.update.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    root_before = store.load_direct(TASK1_TARGET).to_dict()
    child_before = store.load_direct(TASK1_TARGET_CHILD).to_dict()
    assert (
        runner.invoke(
            app,
            ["update", "--to", TASK1_TARGET],
        ).exit_code
        == 0
    )
    root_after = store.load_direct(TASK1_TARGET).to_dict()
    child_after = store.load_direct(TASK1_TARGET_CHILD).to_dict()

    undo = runner.invoke(app, ["undo"])

    assert undo.exit_code == 0, undo.output
    assert "Undid command: mem update" in undo.output
    assert "Affected Contexts: 2" in undo.output
    assert store.load_direct(TASK1_TARGET).to_dict() == root_before
    assert store.load_direct(TASK1_TARGET_CHILD).to_dict() == child_before

    redo = runner.invoke(app, ["redo"])

    assert redo.exit_code == 0, redo.output
    assert "Redid command: mem update" in redo.output
    assert "Affected Contexts: 2" in redo.output
    assert store.load_direct(TASK1_TARGET).to_dict() == root_after
    assert store.load_direct(TASK1_TARGET_CHILD).to_dict() == child_after
    assert (
        store.load_direct(TASK1_TARGET_CHILD)
        .memories[target_memory.uid]
        .content.startswith("The Main Building south entrance is open")
    )

    trace = build_trace(
        store,
        store.load_direct(TASK1_TARGET_CHILD),
        target_memory.uid,
    )
    restorations = [
        event for event in trace.events if event.command in {"undo", "redo"}
    ]
    update_event = next(event for event in trace.events if event.command == "update")

    assert [event.command for event in restorations] == ["undo", "redo"]
    assert update_event.command_operation is not None
    assert update_event.command_operation.command == "update"
    assert [context.name for context in update_event.command_operation.contexts] == [
        TASK1_TARGET,
        TASK1_TARGET_CHILD,
    ]
    assert all(
        event.command_operation is not None
        and event.command_operation.source_command == "update"
        and event.command_operation.source_uid == update_event.command_operation.uid
        and [context.name for context in event.command_operation.contexts]
        == [TASK1_TARGET, TASK1_TARGET_CHILD]
        for event in restorations
    )

    rendered = runner.invoke(
        app,
        [
            "trace",
            target_memory.uid[:8],
            "--context",
            TASK1_TARGET_CHILD,
            "--verbose",
        ],
    )

    assert rendered.exit_code == 0, rendered.output
    assert "Operation: update" in rendered.output
    assert rendered.output.count("Source operation: mem update") == 2
    assert rendered.output.count("Affected Contexts: 2") == 3


def test_multi_context_undo_rolls_back_if_second_owner_write_fails(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _persist_pair(store)
    provider = PlanProvider(_edit_and_root_add_response)
    monkeypatch.setattr(
        "memcommit.commands.update.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    assert (
        runner.invoke(
            app,
            ["update", "--to", TASK1_TARGET],
        ).exit_code
        == 0
    )
    records_after = {
        name: store.load_direct(name).to_dict()
        for name in (TASK1_TARGET, TASK1_TARGET_CHILD)
    }
    histories_after = {
        name: store.list_checkpoints(name)
        for name in (TASK1_TARGET, TASK1_TARGET_CHILD)
    }
    original_save_locked = MemoryStore._save_locked
    undo_writes = 0

    def fail_second_undo(self, context, auto_checkpoint, **kwargs):
        nonlocal undo_writes
        if auto_checkpoint is not None and auto_checkpoint.command == "undo":
            undo_writes += 1
            if undo_writes == 2:
                raise OSError("simulated second-owner failure")
        return original_save_locked(
            self,
            context,
            auto_checkpoint,
            **kwargs,
        )

    monkeypatch.setattr(MemoryStore, "_save_locked", fail_second_undo)

    undo = runner.invoke(app, ["undo"])

    assert undo.exit_code == 1
    assert "simulated second-owner failure" in undo.stderr
    for name in (TASK1_TARGET, TASK1_TARGET_CHILD):
        assert store.load_direct(name).to_dict() == records_after[name]
        assert store.list_checkpoints(name) == histories_after[name]


def test_multi_context_undo_rejects_an_incomplete_update_receipt(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _persist_pair(store)
    provider = PlanProvider(_edit_and_root_add_response)
    monkeypatch.setattr(
        "memcommit.commands.update.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    assert (
        runner.invoke(
            app,
            ["update", "--to", TASK1_TARGET],
        ).exit_code
        == 0
    )
    records_after = {
        name: store.load_direct(name).to_dict()
        for name in (TASK1_TARGET, TASK1_TARGET_CHILD)
    }
    applied = store.load_staged_update()
    assert applied.application is not None
    missing = applied.application.checkpoints[-1]
    checkpoint_path = next(
        path
        for path in store._checkpoints_dir(missing.context_name).glob("*.json")
        if missing.checkpoint_uid[:8] in path.name
    )
    checkpoint_path.unlink()

    undo = runner.invoke(app, ["undo"])

    assert undo.exit_code == 1
    assert "inconsistent checkpoint metadata" in undo.stderr
    for name in (TASK1_TARGET, TASK1_TARGET_CHILD):
        assert store.load_direct(name).to_dict() == records_after[name]


def test_empty_update_records_applied_receipt_without_context_checkpoint(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _persist_pair(store)
    provider = PlanProvider({"edits": [], "additions": []})
    monkeypatch.setattr(
        "memcommit.commands.update.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    target_bytes_before = {
        path: path.read_bytes()
        for path in (isolated_store / "contexts" / "campus-wiki").rglob("context.json")
    }

    result = runner.invoke(app, ["update", "--to", TASK1_TARGET])

    assert result.exit_code == 0, result.output
    assert "OUTCOME · NO CHANGE · no Context checkpoint" in result.output
    applied = store.load_staged_update()
    assert applied.status == "applied"
    assert applied.operations == ()
    assert applied.application is not None
    assert applied.application.checkpoints == ()
    assert {
        path: path.read_bytes()
        for path in (isolated_store / "contexts" / "campus-wiki").rglob("context.json")
    } == target_bytes_before
    assert store.list_checkpoints(TASK1_TARGET) == []
    assert store.list_checkpoints(TASK1_TARGET_CHILD) == []
    receipt_bytes = (isolated_store / "staged-update.json").read_bytes()

    repeated = runner.invoke(app, ["update", "--to", TASK1_TARGET])

    assert repeated.exit_code == 0, repeated.output
    assert "receipt was already applied" in repeated.output
    assert len(provider.calls) == 1
    assert (isolated_store / "staged-update.json").read_bytes() == receipt_bytes
    assert store.list_checkpoints(TASK1_TARGET) == []
    assert store.list_checkpoints(TASK1_TARGET_CHILD) == []


def test_multi_owner_write_failure_rolls_back_contexts_and_checkpoints(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _persist_pair(store)
    provider = PlanProvider(_edit_and_root_add_response)
    monkeypatch.setattr(
        "memcommit.commands.update.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    context_bytes_before = {
        path: path.read_bytes()
        for path in (isolated_store / "contexts").rglob("context.json")
    }
    original_save_locked = MemoryStore._save_locked
    update_writes = []

    def fail_second_update_write(
        self,
        context,
        auto_checkpoint,
        *,
        expected_context_digest,
        require_new=False,
    ):
        if auto_checkpoint is not None and auto_checkpoint.command == "update":
            update_writes.append(context.name)
            if len(update_writes) == 2:
                raise OSError("simulated second owner write failure")
        return original_save_locked(
            self,
            context,
            auto_checkpoint,
            expected_context_digest=expected_context_digest,
            require_new=require_new,
        )

    monkeypatch.setattr(MemoryStore, "_save_locked", fail_second_update_write)

    result = runner.invoke(app, ["update", "--to", TASK1_TARGET])

    assert result.exit_code == 1
    assert "simulated second owner write failure" in result.stderr
    assert update_writes == [TASK1_TARGET, TASK1_TARGET_CHILD]
    assert {
        path: path.read_bytes()
        for path in (isolated_store / "contexts").rglob("context.json")
    } == context_bytes_before
    assert store.list_checkpoints(TASK1_TARGET) == []
    assert store.list_checkpoints(TASK1_TARGET_CHILD) == []
    staged = store.load_staged_update()
    assert staged.status == "staged"
    assert staged.application is None


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

    result = runner.invoke(app, ["impact", "--to", TASK1_TARGET])

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
    first = runner.invoke(app, ["update", "--to", TASK1_TARGET])
    assert first.exit_code == 0

    other = ops.init("other-target")
    ops.add(other, "other old fact")
    store.save(other)
    refused = runner.invoke(app, ["update", "--to", "other-target"])

    assert refused.exit_code == 1
    assert "--replace-stage" in refused.stderr
    assert len(provider.calls) == 1

    replaced = runner.invoke(
        app,
        ["update", "--to", "other-target", "--replace-stage"],
    )

    assert replaced.exit_code == 0, replaced.output
    assert "UPDATE APPLIED" in replaced.output
    assert store.load_staged_update().target_name == "other-target"
    assert len(provider.calls) == 2


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
    assert "Source and target Contexts must be distinct" in same.stderr
    assert "Traceback" not in missing.output + same.output
