"""Pure staged-update application tests."""
from __future__ import annotations

import uuid

import pytest

from memcommit.core.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.application.operations.update.model import AddOperation, EditOperation, UpdateSession
from memcommit.application.operations.update.application import apply_update
from memcommit.application.operations.update.model import UpdatePlan
from memcommit.application.operations.update.materialization import (
    UpdateApplicationError,
    prepare_update_application,
)


SHA256 = "0" * 64


def _session(
    target: Context,
    *operations: EditOperation | AddOperation,
    status: str = "staged",
) -> UpdateSession:
    return UpdateSession(
        uid=str(uuid.uuid4()),
        status=status,  # type: ignore[arg-type]
        created_at="2026-07-29T00:00:00+00:00",
        source_uid="source-uid",
        source_name="participant/construction-updates",
        source_digest=SHA256,
        source_contexts=(),
        target_uid=target.uid,
        target_name=target.name,
        target_digest=SHA256,
        target_contexts=(),
        operations=operations,
    )


def _edit(
    owner: Context,
    memory: Memory,
    new_content: str = "new content",
) -> EditOperation:
    return EditOperation(
        owner_context_uid=owner.uid,
        owner_context_name=owner.name,
        memory_uid=memory.uid,
        old_content=memory.content,
        new_content=new_content,
        source_refs=(),
        reason="verified change",
    )


def _add(
    owner: Context,
    *,
    memory_uid: str | None = None,
    new_content: str = "added content",
) -> AddOperation:
    return AddOperation(
        owner_context_uid=owner.uid,
        owner_context_name=owner.name,
        memory_uid=memory_uid or str(uuid.uuid4()),
        new_content=new_content,
        source_refs=(),
        reason="verified addition",
    )


def test_applies_edits_and_additions_to_detached_owner_post_images():
    target = Context(uid="target", name="campus-wiki")
    child = Context(uid="buildings", name="campus-wiki/buildings")
    unchanged = Context(uid="parking", name="campus-wiki/parking")
    root_memory = Memory(uid="root-memory", content="old root")
    child_memory = Memory(uid="child-memory", content="old child")
    target.add(root_memory)
    target.add(child)
    target.add(unchanged)
    child.add(child_memory)
    child._store_digest = "child-load-digest"
    addition = _add(target)

    result = prepare_update_application(
        _session(
            target,
            _edit(child, child_memory, "new child"),
            addition,
            _edit(target, root_memory, "new root"),
        ),
        target,
    )

    assert [
        owner.owner_context_name
        for owner in result.affected_owners
    ] == [target.name, child.name]
    root_post, child_post = result.post_images
    assert root_post is not target
    assert child_post is not child
    assert root_post.memories[root_memory.uid].content == "new root"
    assert root_post.memories[addition.memory_uid].content == "added content"
    assert child_post.memories[child_memory.uid].content == "new child"
    assert child_post._store_digest == "child-load-digest"
    assert target.memories[root_memory.uid].content == "old root"
    assert child.memories[child_memory.uid].content == "old child"
    assert addition.memory_uid not in target.memories
    assert unchanged not in result.post_images

    child_post.memories[child_memory.uid].content = "mutated result"
    assert child.memories[child_memory.uid].content == "old child"


def test_application_boundary_applies_a_session_independent_plan():
    target = Context(uid="target", name="campus-wiki")
    memory = Memory(uid="memory", content="old")
    target.add(memory)
    plan = UpdatePlan(
        uid=str(uuid.uuid4()),
        target_uid=target.uid,
        target_name=target.name,
        operations=(_edit(target, memory, "new"),),
    )

    result = apply_update(plan, target)

    assert result.plan_uid == plan.uid
    assert result.session_uid == plan.uid
    assert result.post_image_for(target.uid) is not None
    assert result.post_image_for(target.uid).memories[memory.uid].content == "new"
    assert target.memories[memory.uid].content == "old"


def test_additions_append_in_session_order_and_edits_preserve_item_order():
    target = Context(uid="target", name="campus-wiki")
    first = Memory(uid="first", content="first old")
    second = Memory(uid="second", content="second old")
    target.add(first)
    target.add(second)
    addition_one = _add(target, memory_uid=str(uuid.uuid4()))
    addition_two = _add(target, memory_uid=str(uuid.uuid4()))

    result = prepare_update_application(
        _session(
            target,
            addition_one,
            _edit(target, first, "first new"),
            addition_two,
        ),
        target,
    )

    assert result.post_images[0].ordered_uids() == [
        first.uid,
        second.uid,
        addition_one.memory_uid,
        addition_two.memory_uid,
    ]


def test_empty_staged_plan_returns_no_owners_without_mutating_target():
    target = Context(uid="target", name="campus-wiki")
    memory = Memory(uid="memory", content="unchanged")
    target.add(memory)
    before = target.to_dict()

    result = prepare_update_application(_session(target), target)

    assert result.affected_owners == ()
    assert result.post_images == ()
    assert target.to_dict() == before


@pytest.mark.parametrize("status", ["impact", "applied", "unknown"])
def test_only_staged_sessions_can_be_applied(status):
    target = Context(uid="target", name="campus-wiki")

    with pytest.raises(
        UpdateApplicationError,
        match="requires a staged update session",
    ):
        prepare_update_application(_session(target, status=status), target)


def test_session_must_name_the_supplied_target_root():
    target = Context(uid="target", name="campus-wiki")
    other = Context(uid="other", name="participant/other-fork")

    with pytest.raises(UpdateApplicationError, match="does not match"):
        prepare_update_application(_session(target), other)


@pytest.mark.parametrize(
    ("owner_uid", "owner_name"),
    [
        ("missing-owner", "campus-wiki/buildings"),
        ("buildings", "campus-wiki/wrong-name"),
    ],
)
def test_every_operation_owner_uid_and_name_are_preflighted(
    owner_uid,
    owner_name,
):
    target = Context(uid="target", name="campus-wiki")
    child = Context(uid="buildings", name="campus-wiki/buildings")
    memory = Memory(uid="memory", content="old")
    child.add(memory)
    target.add(child)
    operation = EditOperation(
        owner_context_uid=owner_uid,
        owner_context_name=owner_name,
        memory_uid=memory.uid,
        old_content=memory.content,
        new_content="new",
        source_refs=(),
        reason="verified change",
    )

    with pytest.raises(UpdateApplicationError):
        prepare_update_application(_session(target, operation), target)

    assert memory.content == "old"


def test_a_late_invalid_operation_leaves_every_original_owner_unchanged():
    target = Context(uid="target", name="campus-wiki")
    child = Context(uid="child", name="campus-wiki/buildings")
    root_memory = Memory(uid="root-memory", content="old root")
    child_memory = Memory(uid="child-memory", content="old child")
    target.add(root_memory)
    target.add(child)
    child.add(child_memory)
    invalid = EditOperation(
        owner_context_uid=child.uid,
        owner_context_name=child.name,
        memory_uid=child_memory.uid,
        old_content="stale child",
        new_content="new child",
        source_refs=(),
        reason="verified change",
    )

    with pytest.raises(UpdateApplicationError, match="staged old content"):
        prepare_update_application(
            _session(
                target,
                _edit(target, root_memory, "new root"),
                invalid,
            ),
            target,
        )

    assert target.memories[root_memory.uid].content == "old root"
    assert child.memories[child_memory.uid].content == "old child"


@pytest.mark.parametrize(
    "read_only_item",
    [
        MemoryRef(
            uid="read-only",
            target_context_uid="origin",
            target_context_name="campus-wiki",
            target_memory_uid="origin-memory",
        ),
        QueryContextRef(
            uid="read-only",
            name="campus-wiki",
            target_source_uid="query-source",
            provider="codex",
        ),
    ],
)
def test_edit_cannot_modify_memory_or_query_context_references(read_only_item):
    target = Context(uid="target", name="campus-wiki")
    target.add(read_only_item)
    operation = EditOperation(
        owner_context_uid=target.uid,
        owner_context_name=target.name,
        memory_uid=read_only_item.uid,
        old_content="opaque",
        new_content="forbidden",
        source_refs=(),
        reason="invalid edit",
    )

    with pytest.raises(UpdateApplicationError, match="cannot be modified"):
        prepare_update_application(_session(target, operation), target)

    assert target.memories[read_only_item.uid] is read_only_item


def test_edit_requires_an_existing_direct_memory_with_matching_old_content():
    target = Context(uid="target", name="campus-wiki")
    memory = Memory(uid="memory", content="current")
    target.add(memory)
    missing = EditOperation(
        owner_context_uid=target.uid,
        owner_context_name=target.name,
        memory_uid="missing",
        old_content="old",
        new_content="new",
        source_refs=(),
        reason="invalid edit",
    )
    stale = EditOperation(
        owner_context_uid=target.uid,
        owner_context_name=target.name,
        memory_uid=memory.uid,
        old_content="stale",
        new_content="new",
        source_refs=(),
        reason="invalid edit",
    )

    with pytest.raises(UpdateApplicationError, match="does not exist"):
        prepare_update_application(_session(target, missing), target)
    with pytest.raises(UpdateApplicationError, match="staged old content"):
        prepare_update_application(_session(target, stale), target)

    assert memory.content == "current"


@pytest.mark.parametrize(
    "existing_item",
    [
        Memory(uid="collision", content="memory"),
        MemoryRef(
            uid="collision",
            target_context_uid="origin",
            target_context_name="campus-wiki",
            target_memory_uid="origin-memory",
        ),
        QueryContextRef(
            uid="collision",
            name="campus-wiki",
            target_source_uid="query-source",
            provider="codex",
        ),
        Context(uid="collision", name="campus-wiki/child"),
    ],
)
def test_addition_rejects_collision_with_any_direct_owner_item(existing_item):
    target = Context(uid="target", name="campus-wiki")
    target.add(existing_item)

    with pytest.raises(UpdateApplicationError, match="already exists"):
        prepare_update_application(
            _session(
                target,
                _add(target, memory_uid=existing_item.uid),
            ),
            target,
        )

    assert target.memories[existing_item.uid] is existing_item


def test_duplicate_operation_target_is_rejected_before_application():
    target = Context(uid="target", name="campus-wiki")
    memory = Memory(uid="memory", content="old")
    target.add(memory)

    with pytest.raises(UpdateApplicationError, match="more than once"):
        prepare_update_application(
            _session(
                target,
                _edit(target, memory, "new one"),
                _edit(target, memory, "new two"),
            ),
            target,
        )

    assert memory.content == "old"
