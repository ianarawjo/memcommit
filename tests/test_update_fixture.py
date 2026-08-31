"""Executable contract for the compact Task 1 update example."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from memcommit.core.context import Context, Memory, QueryContextRef
from memcommit.application.operations.semantic_updates.foundation.update.model import (
    AddOperation,
    EditOperation,
    RemoveOperation,
    count_operations,
    plan_update,
)
from memcommit.application.operations.semantic_updates.foundation.update.application import (
    apply_staged_update_plan,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "memcommit" / "application" / "capabilities" / "evaluation"
    / "fixtures"
    / "update.json"
)


def _reject_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_fixture() -> dict:
    return json.loads(
        FIXTURE_PATH.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
    )


def _memory_records(graph: dict) -> list[dict]:
    return [
        memory
        for context in graph["child_contexts"]
        for memory in context["memories"]
    ]


def _assert_context_graph(graph: dict, *, origin: bool) -> None:
    expected_keys = {"root_context", "child_contexts"}
    if origin:
        expected_keys.add("origin_pointer")
    assert set(graph) == expected_keys
    assert set(graph["root_context"]) == {"uid", "name"}
    uuid.UUID(graph["root_context"]["uid"])

    context_uids: set[str] = set()
    context_names: set[str] = set()
    memory_uids: set[str] = set()
    memory_ids: set[str] = set()
    for child in graph["child_contexts"]:
        assert set(child) == {"uid", "name", "memories"}
        uuid.UUID(child["uid"])
        assert child["uid"] not in context_uids
        assert child["name"] not in context_names
        assert child["name"].startswith(f"{graph['root_context']['name']}/")
        context_uids.add(child["uid"])
        context_names.add(child["name"])
        for memory in child["memories"]:
            assert set(memory) == {"id", "uid", "content"}
            uuid.UUID(memory["uid"])
            assert memory["uid"] not in memory_uids
            assert memory["id"] not in memory_ids
            assert memory["content"].strip()
            memory_uids.add(memory["uid"])
            memory_ids.add(memory["id"])

    if origin:
        pointer = graph["origin_pointer"]
        assert set(pointer) == {
            "uid",
            "name",
            "target_source_uid",
            "provider",
        }
        uuid.UUID(pointer["uid"])
        uuid.UUID(pointer["target_source_uid"])


def test_update_fixture_is_a_strict_compact_5x5_task1_case() -> None:
    fixture = _load_fixture()

    assert set(fixture) == {
        "command",
        "schema_version",
        "ruleset_version",
        "description",
        "cases",
    }
    assert fixture["command"] == "update"
    assert fixture["schema_version"] == 1
    assert fixture["ruleset_version"] == "update-task1-v1-draft"
    assert len(fixture["cases"]) == 1

    case = fixture["cases"][0]
    assert set(case) == {
        "id",
        "description",
        "context_names",
        "source",
        "target_baseline",
        "expected",
    }
    assert case["id"] == "task1-compact-5x5"
    assert case["context_names"] == {
        "upstream_query_only": "construction-details",
        "source_root": "participant/construction-updates",
        "target_root": "campus-wiki",
    }
    _assert_context_graph(case["source"], origin=False)
    _assert_context_graph(case["target_baseline"], origin=True)

    source_records = _memory_records(case["source"])
    target_records = _memory_records(case["target_baseline"])
    assert len(source_records) == 5
    assert len(target_records) == 5

    expected = case["expected"]
    assert set(expected) == {
        "edits",
        "additions",
        "removals",
        "unchanged_target_ids",
        "source_dispositions",
        "final_target_count",
    }
    assert (len(expected["edits"]), len(expected["additions"])) == (2, 1)
    assert len(expected["removals"]) == 1
    assert len(expected["unchanged_target_ids"]) == 2
    assert expected["final_target_count"] == 5

    source_ids = {record["id"] for record in source_records}
    target_ids = {record["id"] for record in target_records}
    dispositions = expected["source_dispositions"]
    assert {item["source_id"] for item in dispositions} == source_ids
    assert {
        item["outcome"]
        for item in dispositions
    } == {"EDIT", "ADD", "REMOVE", "ALREADY_PRESENT"}
    assert {
        target_id
        for item in dispositions
        for target_id in item["target_ids"]
    }.issubset(target_ids)

    changed_target_ids = {
        operation["target_id"]
        for operation in [
            *expected["edits"],
            *expected["removals"],
        ]
    }
    assert changed_target_ids.isdisjoint(expected["unchanged_target_ids"])
    assert (
        changed_target_ids | set(expected["unchanged_target_ids"])
        == target_ids
    )
    assert all(
        set(operation["source_ids"]).issubset(source_ids)
        for operation in [
            *expected["edits"],
            *expected["additions"],
            *expected["removals"],
        ]
    )
    removal_source = next(
        record
        for record in source_records
        if record["id"] == expected["removals"][0]["source_ids"][0]
    )
    assert "Remove the standalone detour notice" in removal_source["content"]


def _build_graph(graph: dict, *, include_origin: bool) -> Context:
    root_data = graph["root_context"]
    root = Context(uid=root_data["uid"], name=root_data["name"])
    if include_origin:
        pointer = graph["origin_pointer"]
        root.add(
            QueryContextRef(
                uid=pointer["uid"],
                name=pointer["name"],
                target_source_uid=pointer["target_source_uid"],
                provider=pointer["provider"],
            )
        )
    for child_data in graph["child_contexts"]:
        child = Context(uid=child_data["uid"], name=child_data["name"])
        for memory in child_data["memories"]:
            child.add(Memory(uid=memory["uid"], content=memory["content"]))
        root.add(child)
    return root


class _FixtureProvider:
    def __init__(self, case: dict):
        self.case = case
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls += 1
        payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
        source_by_fixture_id = {
            record["id"]: record
            for record in _memory_records(self.case["source"])
        }
        target_by_fixture_id = {
            record["id"]: record
            for record in _memory_records(self.case["target_baseline"])
        }
        source_id_by_content = {
            record["content"]: record["source_id"]
            for record in payload["source"]["memories"]
        }
        target_id_by_content = {
            record["content"]: record["target_id"]
            for record in payload["target"]["memories"]
        }
        context_id_by_name = {
            record["name"]: record["context_id"]
            for record in payload["target"]["contexts"]
        }

        def source_ids(fixture_ids):
            return [
                source_id_by_content[source_by_fixture_id[item]["content"]]
                for item in fixture_ids
            ]

        expected = self.case["expected"]
        response = {
            "edits": [
                {
                    "target_id": target_id_by_content[
                        target_by_fixture_id[item["target_id"]]["content"]
                    ],
                    "new_content": item["new_content"],
                    "source_ids": source_ids(item["source_ids"]),
                    "reason": item["reason"],
                }
                for item in expected["edits"]
            ],
            "additions": [
                {
                    "target_context_id": context_id_by_name[
                        item["owner_context"]
                    ],
                    "new_content": item["new_content"],
                    "source_ids": source_ids(item["source_ids"]),
                    "reason": item["reason"],
                }
                for item in expected["additions"]
            ],
            "removals": [
                {
                    "target_id": target_id_by_content[
                        target_by_fixture_id[item["target_id"]]["content"]
                    ],
                    "source_ids": source_ids(item["source_ids"]),
                    "reason": item["reason"],
                }
                for item in expected["removals"]
            ],
        }
        return json.dumps(response)


def test_compact_task1_fixture_plans_and_applies_exactly_four_changes() -> None:
    case = _load_fixture()["cases"][0]
    source = _build_graph(case["source"], include_origin=False)
    target = _build_graph(case["target_baseline"], include_origin=True)
    target_before = target.to_dict()
    provider = _FixtureProvider(case)

    session = plan_update(
        source,
        target,
        lambda: provider,
        status="staged",
    )

    assert count_operations(session) == (2, 1, 1)
    assert [
        type(operation)
        for operation in session.operations
    ] == [
        EditOperation,
        EditOperation,
        AddOperation,
        RemoveOperation,
    ]
    assert provider.calls == 1

    application = apply_staged_update_plan(session, target)

    assert target.to_dict() == target_before
    post_images = {
        owner.owner_context_uid: owner.post_image
        for owner in application.affected_owners
    }
    final_memories: list[Memory] = []
    for item in target.iter_items():
        if not isinstance(item, Context):
            continue
        owner = post_images.get(item.uid, item)
        final_memories.extend(
            child
            for child in owner.iter_items()
            if isinstance(child, Memory)
        )

    expected = case["expected"]
    target_by_id = {
        record["id"]: record
        for record in _memory_records(case["target_baseline"])
    }
    expected_contents = {
        target_by_id[target_id]["content"]
        for target_id in expected["unchanged_target_ids"]
    }
    expected_contents.update(
        operation["new_content"]
        for operation in [*expected["edits"], *expected["additions"]]
    )
    assert len(final_memories) == expected["final_target_count"]
    assert {memory.content for memory in final_memories} == expected_contents
    assert all(
        not isinstance(item, QueryContextRef)
        for owner in application.affected_owners
        for item in owner.post_image.iter_items()
    )
