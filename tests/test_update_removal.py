"""Constrained whole-Memory removal contracts for directional Update."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.core.context import Context, MemoryRef, QueryContextRef
from memcommit.persistence.store import MemoryStore
from memcommit.application.operations.update.model import RemoveOperation, UpdateError, UpdateSession, plan_update
from memcommit.application.operations.update.application import (
    UpdateApplicationError,
    apply_staged_update_plan,
)


runner = CliRunner(mix_stderr=False)
SOURCE_NAME = "participant/construction-updates"
TARGET_NAME = "campus-wiki"


class _RemovalProvider:
    def __init__(self):
        self.calls = 0
        self.schemas = []

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls += 1
        self.schemas.append(output_schema)
        payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
        source_id = payload["source"]["memories"][0]["source_id"]
        target_id = next(
            item["target_id"]
            for item in payload["target"]["memories"]
            if "detour" in item["content"].lower()
        )
        return json.dumps(
            {
                "edits": [],
                "additions": [],
                "removals": [
                    {
                        "target_id": target_id,
                        "source_ids": [source_id],
                        "reason": (
                            "The verified source explicitly retires the "
                            "standalone detour notice."
                        ),
                    }
                ],
            }
        )


def _persist_removal_pair(store: MemoryStore):
    source = ops.init(SOURCE_NAME)
    source_memory = ops.add(
        source,
        "Verified removal instruction: the East Gate shuttle detour ended. "
        "Remove the standalone detour notice from the campus wiki.",
    )
    target = ops.init(TARGET_NAME)
    pointer = QueryContextRef(
        uid="33333333-3333-4333-8333-333333333301",
        name="campus-wiki",
        target_source_uid="33333333-3333-4333-8333-333333333302",
        provider="codex_chatgpt",
    )
    target.add(pointer)
    obsolete = ops.add(
        target,
        "The East Gate shuttle follows a construction detour until further notice.",
    )
    preserved = ops.add(
        target,
        "The Campus Health Centre is open on weekdays.",
    )
    store.save(source)
    store.save(target)
    store.set_current(source.name)
    return source, source_memory, target, pointer, obsolete, preserved


def test_mem_update_applies_explicit_removal_and_diff_keeps_provenance(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    source, source_memory, _, pointer, obsolete, preserved = (
        _persist_removal_pair(store)
    )
    provider = _RemovalProvider()
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.update.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    result = runner.invoke(app, ["update", "--to", TARGET_NAME])

    assert result.exit_code == 0, result.output
    assert "EFFECTS · ADD 0 · EDIT 0 · REMOVE 1" in result.output
    assert "REVIEW · mem review update --session" in result.output
    assert obsolete.content not in result.output
    updated = store.load_direct(TARGET_NAME)
    assert updated.ordered_uids() == [pointer.uid, preserved.uid]
    assert updated.memories[pointer.uid].name == "campus-wiki"
    assert store.load_direct(SOURCE_NAME).to_dict() == source.to_dict()
    assert provider.calls == 1
    schema = provider.schemas[0]
    assert schema["required"] == ["edits", "additions", "removals"]
    assert schema["properties"]["removals"]["items"]["required"] == [
        "target_id",
        "source_ids",
        "reason",
    ]

    semantic = runner.invoke(app, ["diff"])
    raw = runner.invoke(app, ["diff", "--raw"])

    assert semantic.exit_code == 0, semantic.output
    assert "0 EDITS · 0 ADDITIONS · 1 REMOVALS · 1 CHANGES" in semantic.output
    assert f"REMOVE {TARGET_NAME} Memory [{obsolete.uid}]" in semantic.output
    assert (
        f"Memory [{source_memory.uid}]"
        in semantic.output
    )
    assert raw.exit_code == 0, raw.output
    assert f"--- a/{TARGET_NAME}#{obsolete.uid}" in raw.output
    assert "+++ /dev/null" in raw.output
    assert f"Sources: {SOURCE_NAME}#{source_memory.uid}" in raw.output


def test_remove_session_round_trip_is_v3_and_legacy_schema_rejects_it() -> None:
    source = ops.init("source")
    ops.add(
        source,
        "Explicitly remove the whole obsolete standalone notice.",
    )
    target = ops.init("target")
    obsolete = ops.add(target, "Obsolete standalone notice.")

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
            return json.dumps(
                {
                    "edits": [],
                    "additions": [],
                    "removals": [
                        {
                            "target_id": payload["target"]["memories"][0][
                                "target_id"
                            ],
                            "source_ids": [
                                payload["source"]["memories"][0]["source_id"]
                            ],
                            "reason": "The source explicitly requires removal.",
                        }
                    ],
                }
            )

    session = plan_update(source, target, Provider, status="staged")
    data = session.to_dict()

    assert data["schema_version"] == 6
    assert isinstance(session.operations[0], RemoveOperation)
    assert session.operations[0].old_content == obsolete.content
    assert UpdateSession.from_dict(data) == session

    legacy_without_removal = json.loads(json.dumps(data))
    legacy_without_removal["schema_version"] = 2
    legacy_without_removal["operations"] = []
    for endpoint in ("source", "target"):
        legacy_without_removal[endpoint].pop("access")
        legacy_without_removal[endpoint].pop("include_descendants")
    assert UpdateSession.from_dict(legacy_without_removal).operations == ()

    data["schema_version"] = 2
    for endpoint in ("source", "target"):
        data[endpoint].pop("access")
        data[endpoint].pop("include_descendants")
    with pytest.raises(ValueError, match="Legacy update sessions"):
        UpdateSession.from_dict(data)


def test_planner_rejects_edit_and_remove_for_the_same_target() -> None:
    source = ops.init("source")
    ops.add(source, "Explicitly remove the obsolete whole notice.")
    target = ops.init("target")
    ops.add(target, "Obsolete whole notice.")

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
            source_id = payload["source"]["memories"][0]["source_id"]
            target_id = payload["target"]["memories"][0]["target_id"]
            return json.dumps(
                {
                    "edits": [
                        {
                            "target_id": target_id,
                            "new_content": "Revised notice.",
                            "source_ids": [source_id],
                            "reason": "Edit it.",
                        }
                    ],
                    "additions": [],
                    "removals": [
                        {
                            "target_id": target_id,
                            "source_ids": [source_id],
                            "reason": "Remove it too.",
                        }
                    ],
                }
            )

    with pytest.raises(UpdateError, match="same target Memory"):
        plan_update(source, target, Provider)


def test_remove_application_rejects_refs_and_stale_old_content() -> None:
    target = Context(uid="target", name=TARGET_NAME)
    reference = MemoryRef(
        uid="read-only",
        target_context_uid="origin",
        target_context_name="origin",
        target_memory_uid="origin-memory",
    )
    target.add(reference)

    def session(operation: RemoveOperation) -> UpdateSession:
        return UpdateSession(
            uid="44444444-4444-4444-8444-444444444444",
            status="staged",
            created_at="2026-07-29T00:00:00+00:00",
            source_uid="source",
            source_name=SOURCE_NAME,
            source_digest="0" * 64,
            source_contexts=(),
            target_uid=target.uid,
            target_name=target.name,
            target_digest="0" * 64,
            target_contexts=(),
            operations=(operation,),
        )

    read_only = RemoveOperation(
        owner_context_uid=target.uid,
        owner_context_name=target.name,
        memory_uid=reference.uid,
        old_content="opaque",
        source_refs=(),
        reason="invalid",
    )
    with pytest.raises(UpdateApplicationError, match="cannot be removed"):
        apply_staged_update_plan(session(read_only), target)

    memory = ops.add(target, "current")
    stale = RemoveOperation(
        owner_context_uid=target.uid,
        owner_context_name=target.name,
        memory_uid=memory.uid,
        old_content="stale",
        source_refs=(),
        reason="invalid",
    )
    with pytest.raises(UpdateApplicationError, match="staged old content"):
        apply_staged_update_plan(session(stale), target)
    assert target.ordered_uids() == [reference.uid, memory.uid]
