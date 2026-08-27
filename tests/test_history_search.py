"""Strict semantic planning with locally enforced temporal relations."""

import json

import pytest

from memcommit.core.context import AutoCheckpoint, Memory
from memcommit.application.retained_history.reconstruction import build_history
from memcommit.application.operations.log.search import (
    HistorySearchError,
    search_history,
)
from memcommit.application import ops
from memcommit.persistence.store import MemoryStore


def _save(store, ctx, command, description):
    store.save(
        ctx,
        AutoCheckpoint(
            command=command,
            args={},
            description=description,
        ),
    )


def _timeline(isolated_store, name="campus"):
    store = MemoryStore()
    ctx = ops.init(name)
    store.save(ctx)
    _save(store, ctx, "init", "Initialized")
    shuttle = ops.add(ctx, "The shuttle detour notice is active.")
    _save(store, ctx, "add", "Added shuttle notice")
    parking = ops.add(ctx, "Parking is in Lot A.")
    _save(store, ctx, "add", "Added parking")
    ctx.replace(Memory(uid=parking.uid, content="Parking is in Lot B."))
    _save(store, ctx, "edit", "Changed parking while shuttle notice existed")
    ctx.remove(shuttle.uid)
    _save(store, ctx, "remove", "Removed shuttle notice")
    ctx.replace(Memory(uid=parking.uid, content="Parking is in Lot C."))
    _save(store, ctx, "edit", "Changed parking after shuttle notice")
    return build_history(store, name)


class PlanProvider:
    def __init__(self, make_plan):
        self.make_plan = make_plan
        self.calls = []

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls.append((prompt, operation, output_schema))
        payload = json.loads(prompt.split("HISTORY SEARCH PAYLOAD:\n", 1)[1])
        return json.dumps(self.make_plan(payload))


def _base_plan(**changes):
    plan = {
        "understanding": "Search the retained history.",
        "result_kind": "memory_transition",
        "subject_mode": "ALL",
        "subject_ids": [],
        "event_kinds": ["EDITED"],
        "anchor_kind": "NONE",
        "anchor_ids": [],
        "anchor_occurrence": "ANY",
        "relation": "NONE",
        "reduce": "ALL",
    }
    plan.update(changes)
    return plan


def test_latest_edit_while_semantic_memory_version_was_present(isolated_store):
    timeline = _timeline(isolated_store)

    def plan(payload):
        shuttle_alias = next(
            candidate["candidate_id"]
            for candidate in payload["candidates"]
            if candidate["type"] == "memory_version"
            and "shuttle detour" in candidate["content"]
        )
        return _base_plan(
            anchor_kind="MEMORY_PRESENCE",
            anchor_ids=[shuttle_alias],
            relation="WHILE_PRESENT",
            reduce="LATEST",
        )

    results = search_history(
        timeline,
        "the last Memory updated while the shuttle notice still existed",
        PlanProvider(plan),
        result_kinds=["memory_transition"],
        limit=5,
    )

    assert len(results) == 1
    assert results[0].transition is not None
    assert results[0].transition.before.content == "Parking is in Lot A."
    assert results[0].transition.after.content == "Parking is in Lot B."


def test_memory_presence_anchor_expands_across_same_uid_text_versions(
    isolated_store,
):
    store = MemoryStore()
    ctx = ops.init("campus-lineage")
    store.save(ctx)
    _save(store, ctx, "init", "Initialized")
    shuttle = ops.add(ctx, "The shuttle detour notice is active.")
    _save(store, ctx, "add", "Added shuttle notice")
    ctx.replace(
        Memory(
            uid=shuttle.uid,
            content="The shuttle detour remains active on a revised route.",
        )
    )
    _save(store, ctx, "edit", "Reworded shuttle notice")
    parking = ops.add(ctx, "Parking is in Lot A.")
    _save(store, ctx, "add", "Added parking")
    ctx.replace(Memory(uid=parking.uid, content="Parking is in Lot B."))
    _save(store, ctx, "edit", "Changed parking")
    ctx.remove(shuttle.uid)
    _save(store, ctx, "remove", "Removed shuttle notice")
    timeline = build_history(store, "campus-lineage")

    def plan(payload):
        first_shuttle_version = next(
            candidate["candidate_id"]
            for candidate in payload["candidates"]
            if candidate["type"] == "memory_version"
            and candidate["content"]
            == "The shuttle detour notice is active."
        )
        return _base_plan(
            anchor_kind="MEMORY_PRESENCE",
            anchor_ids=[first_shuttle_version],
            relation="WHILE_PRESENT",
            reduce="LATEST",
        )

    results = search_history(
        timeline,
        "the last Memory updated while the shuttle notice existed",
        PlanProvider(plan),
        result_kinds=["memory_transition"],
        limit=5,
    )

    assert len(results) == 1
    assert results[0].transition.before.content == "Parking is in Lot A."
    assert results[0].transition.after.content == "Parking is in Lot B."


def test_changes_after_anchor_transition_are_filtered_locally(isolated_store):
    timeline = _timeline(isolated_store)

    def plan(payload):
        versions = {
            candidate["candidate_id"]: candidate.get("content")
            for candidate in payload["candidates"]
            if candidate["type"] == "memory_version"
        }
        removal = next(
            candidate["candidate_id"]
            for candidate in payload["candidates"]
            if candidate["type"] == "memory_transition"
            and candidate["event"] == "REMOVED"
            and "shuttle detour" in versions[candidate["before_version"]]
        )
        return _base_plan(
            anchor_kind="MEMORY_TRANSITION",
            anchor_ids=[removal],
            anchor_occurrence="LAST",
            relation="AFTER",
            reduce="ALL",
        )

    results = search_history(
        timeline,
        "Memories changed after the shuttle notice changed",
        PlanProvider(plan),
        result_kinds=["memory_transition"],
        limit=10,
    )

    assert [result.transition.after.content for result in results] == [
        "Parking is in Lot C."
    ]


def test_checkpoint_immediately_before_transition_resolves_exact_local_uid(
    isolated_store,
):
    timeline = _timeline(isolated_store)

    def plan(payload):
        versions = {
            candidate["candidate_id"]: candidate.get("content")
            for candidate in payload["candidates"]
            if candidate["type"] == "memory_version"
        }
        removal = next(
            candidate["candidate_id"]
            for candidate in payload["candidates"]
            if candidate["type"] == "memory_transition"
            and candidate["event"] == "REMOVED"
            and "shuttle detour" in versions[candidate["before_version"]]
        )
        return _base_plan(
            result_kind="checkpoint",
            event_kinds=[],
            anchor_kind="MEMORY_TRANSITION",
            anchor_ids=[removal],
            anchor_occurrence="LAST",
            relation="IMMEDIATELY_BEFORE",
            reduce="LATEST",
        )

    result = search_history(
        timeline,
        "the version immediately before the shuttle notice was removed",
        PlanProvider(plan),
        result_kinds=["checkpoint"],
        limit=5,
    )

    assert len(result) == 1
    assert result[0].checkpoint_uid is not None
    assert result[0].selectable is True
    assert any(
        version.content == "The shuttle detour notice is active."
        for version in result[0].state.memories
    )


def test_memory_version_renders_the_qualifying_occurrence_not_its_later_state(
    isolated_store,
):
    timeline = _timeline(isolated_store)

    def plan(payload):
        shuttle = next(
            candidate["candidate_id"]
            for candidate in payload["candidates"]
            if candidate["type"] == "memory_version"
            and "shuttle detour" in candidate["content"]
        )
        lot_b = next(
            candidate["candidate_id"]
            for candidate in payload["candidates"]
            if candidate["type"] == "memory_version"
            and candidate["content"] == "Parking is in Lot B."
        )
        return _base_plan(
            result_kind="memory_version",
            subject_mode="MATCHED",
            subject_ids=[lot_b],
            event_kinds=[],
            anchor_kind="MEMORY_PRESENCE",
            anchor_ids=[shuttle],
            relation="PRESENT",
            reduce="LATEST",
        )

    result = search_history(
        timeline,
        "the latest Lot B state while the shuttle notice still existed",
        PlanProvider(plan),
        result_kinds=["memory_version"],
        limit=5,
    )

    assert len(result) == 1
    assert result[0].state.description == (
        "Changed parking while shuttle notice existed"
    )
    assert any(
        version.content == "The shuttle detour notice is active."
        for version in result[0].state.memories
    )


@pytest.mark.parametrize(
    "relation, expected_description",
    [
        ("IMMEDIATELY_BEFORE", "Changed parking while shuttle notice existed"),
        ("IMMEDIATELY_AFTER", "Changed parking after shuttle notice"),
    ],
)
def test_checkpoint_anchor_immediate_relation_selects_adjacent_checkpoint(
    isolated_store,
    relation,
    expected_description,
):
    timeline = _timeline(isolated_store)

    def plan(payload):
        anchor = next(
            candidate["candidate_id"]
            for candidate in payload["candidates"]
            if candidate["type"] == "checkpoint"
            and candidate["description"] == "Removed shuttle notice"
        )
        return _base_plan(
            result_kind="checkpoint",
            event_kinds=[],
            anchor_kind="CHECKPOINT",
            anchor_ids=[anchor],
            anchor_occurrence="LAST",
            relation=relation,
            reduce="ALL",
        )

    result = search_history(
        timeline,
        f"the checkpoint {relation.lower()} shuttle removal",
        PlanProvider(plan),
        result_kinds=["checkpoint"],
        limit=5,
    )

    assert len(result) == 1
    assert result[0].state.description == expected_description


def test_multiple_timelines_use_globally_unique_aliases_and_same_context_join(
    isolated_store,
):
    first = _timeline(isolated_store, "first")
    second = _timeline(isolated_store, "second")

    def plan(payload):
        ids = [candidate["candidate_id"] for candidate in payload["candidates"]]
        assert len(ids) == len(set(ids))
        anchors = [
            candidate["candidate_id"]
            for candidate in payload["candidates"]
            if candidate["type"] == "memory_version"
            and "shuttle detour" in candidate["content"]
        ]
        return _base_plan(
            anchor_kind="MEMORY_PRESENCE",
            anchor_ids=anchors,
            relation="WHILE_PRESENT",
            reduce="LATEST",
        )

    results = search_history(
        [first, second],
        "latest edit while each Context's shuttle notice existed",
        PlanProvider(plan),
        result_kinds=["memory_transition"],
        limit=10,
    )

    assert {result.context_name for result in results} == {"first", "second"}
    assert all("Lot B" in result.transition.after.content for result in results)


def test_provider_cannot_return_durable_or_wrong_kind_candidate(
    isolated_store,
):
    timeline = _timeline(isolated_store)
    provider = PlanProvider(
        lambda payload: _base_plan(
            subject_mode="MATCHED",
            subject_ids=[
                next(
                    candidate["candidate_id"]
                    for candidate in payload["candidates"]
                    if candidate["type"] == "checkpoint"
                )
            ],
        )
    )

    with pytest.raises(HistorySearchError, match="wrong kind"):
        search_history(
            timeline,
            "an invalid provider choice",
            provider,
            result_kinds=["memory_transition"],
            limit=5,
        )
    prompt = provider.calls[0][0]
    assert timeline.context_uid not in prompt
    assert all(checkpoint.uid not in prompt for checkpoint in timeline.checkpoints)
