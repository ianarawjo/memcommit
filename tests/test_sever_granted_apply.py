"""Granted-input freshness boundaries for Sever Apply."""

from __future__ import annotations

from tests.grant_placement_support import create_authority_grant_with_placement

import json
import uuid

import pytest

import memcommit.application.capabilities.ops as ops
from memcommit.application.operations.profile.config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.application.operations.profile.model import (
    delete_authority_grant,
    update_authority_grant,
)
from memcommit.application.operations.sever.model import SeverCandidate, SeverSession
from memcommit.application.operations.sever.application import (
    SeverAnalysisRequest,
    SeverAnalysisResult,
    SeverApplicationError,
    SeverPersistedApplyRequest,
)
from memcommit.application.operations.sever.apply.execution import MemoryStoreSeverOutputPort
from memcommit.application.operations.sever.runtime import (
    MemoryStoreSeverInputPort,
    execute_sever_session_apply,
    execute_sever_session_start,
)
from memcommit.application.operations.sever.session_store import SeverSessionStore
from memcommit.persistence.store import MemoryStore


GRANT_PERMISSIONS = ("READ",)


def _granted_review(
    isolated_store,
    tmp_path,
    monkeypatch,
    *,
    granted_role: str,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    active = MemoryStore()
    attachment = ops.init("participant")
    active.create_context(attachment)
    local = ops.init("local-input")
    ops.add(local, "Keep the local access requirement.")
    active.create_context(local)
    active.set_current(attachment.name)

    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="sever-authority",
        kind="MANAGED",
    )
    authoring = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    authority_input = ops.init("authority-input")
    ops.add(authority_input, "Keep the granted access requirement.")
    authority_store.create_context(authority_input)
    registry = ProfileRegistry(
        generation=1,
        active_uid=authoring.uid,
        profiles=(authoring, authority),
        grants=(),
    )
    registry_path = profile_registry_file()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(registry.to_dict()) + "\n",
        encoding="utf-8",
    )
    _registry, grant = create_authority_grant_with_placement(
        authority_name=authority.name,
        grantee_name=authoring.name,
        resource_name=authority_input.name,
        access_name="granted-input",
        permissions=GRANT_PERMISSIONS,
    )

    source_name = "granted-input" if granted_role == "source" else local.name
    criteria_name = local.name if granted_role == "source" else "granted-input"
    request = SeverAnalysisRequest(
        source_locator=source_name,
        criteria_locator=criteria_name,
        output_name=f"granted-{granted_role}-result",
    )
    inputs = MemoryStoreSeverInputPort.capture(active).freeze(request)
    source_memory = inputs.source.memories[0]
    criterion_memory = inputs.criteria.memories[0]
    session = SeverSession(
        uid=str(uuid.uuid4()),
        revision=1,
        state="REVIEWING",
        source=inputs.source,
        criteria=inputs.criteria,
        output_name=request.output_name,
        overview="Keep the reviewed access requirement.",
        candidates=(
            SeverCandidate(
                uid=str(uuid.uuid4()),
                source_memory_uid=source_memory.uid,
                recommendation="KEEP_AS_WRITTEN",
                proposed_content=source_memory.content,
                rationale="The criterion permits the access requirement.",
                criterion_memory_uids=(criterion_memory.uid,),
            ),
        ),
    )
    started = execute_sever_session_start(
        SeverAnalysisResult(session=session, origin="PROVIDER"),
        store=active,
    )
    return active, authority_store, authority_input, grant, started


@pytest.mark.parametrize("granted_role", ("source", "criteria"))
def test_granted_input_apply_succeeds_while_exact_snapshot_is_current(
    isolated_store,
    tmp_path,
    monkeypatch,
    granted_role,
):
    active, _authority, _input, _grant, started = _granted_review(
        isolated_store,
        tmp_path,
        monkeypatch,
        granted_role=granted_role,
    )

    applied = execute_sever_session_apply(
        SeverPersistedApplyRequest(snapshot=started.snapshot),
        store=active,
    )

    assert applied.created is True
    result = active.load_direct(f"granted-{granted_role}-result")
    assert [memory.content for memory in result.iter_items()] == [
        started.snapshot.session.source.memories[0].content
    ]


def test_granted_source_self_save_fails_at_input_boundary(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, _authority, _input, _grant, _started = _granted_review(
        isolated_store,
        tmp_path,
        monkeypatch,
        granted_role="source",
    )

    with pytest.raises(
        SeverApplicationError,
        match="In-place Sever requires an ordinary local Source",
    ):
        MemoryStoreSeverInputPort.capture(active).freeze(
            SeverAnalysisRequest(
                source_locator="granted-input",
                criteria_locator="local-input",
                output_name="granted-input",
                source_include_descendants=False,
            )
        )


@pytest.mark.parametrize("granted_role", ("source", "criteria"))
def test_granted_input_content_change_rejects_apply_without_partial_result(
    isolated_store,
    tmp_path,
    monkeypatch,
    granted_role,
):
    active, authority, authority_input, _grant, started = _granted_review(
        isolated_store,
        tmp_path,
        monkeypatch,
        granted_role=granted_role,
    )
    changed = authority.load_direct(authority_input.name)
    ops.add(changed, "Changed after the Sever review.")
    authority.save(changed)

    with pytest.raises(SeverApplicationError, match="changed after review"):
        execute_sever_session_apply(
            SeverPersistedApplyRequest(snapshot=started.snapshot),
            store=active,
        )

    assert not active.context_exists(f"granted-{granted_role}-result")
    assert SeverSessionStore(active).load(started.snapshot.session.uid).state == (
        "REVIEWING"
    )


def test_granted_input_change_during_creation_rolls_back_partial_result(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, authority, authority_input, _grant, started = _granted_review(
        isolated_store,
        tmp_path,
        monkeypatch,
        granted_role="source",
    )
    original_materialize = MemoryStoreSeverOutputPort._materialize_frozen

    def materialize_then_change(self, session):
        applied = original_materialize(self, session)
        changed = authority.load_direct(authority_input.name)
        ops.add(changed, "Changed while the local Result was being created.")
        authority.save(changed)
        return applied

    monkeypatch.setattr(
        MemoryStoreSeverOutputPort,
        "_materialize_frozen",
        materialize_then_change,
    )

    with pytest.raises(SeverApplicationError, match="changed after review"):
        execute_sever_session_apply(
            SeverPersistedApplyRequest(snapshot=started.snapshot),
            store=active,
        )

    assert not active.context_exists("granted-source-result")
    assert SeverSessionStore(active).load(started.snapshot.session.uid).state == (
        "REVIEWING"
    )


@pytest.mark.parametrize("grant_change", ("revision", "revocation"))
def test_grant_change_rejects_apply_without_partial_result(
    isolated_store,
    tmp_path,
    monkeypatch,
    grant_change,
):
    active, _authority, _input, grant, started = _granted_review(
        isolated_store,
        tmp_path,
        monkeypatch,
        granted_role="source",
    )
    if grant_change == "revision":
        update_authority_grant(
            grant.uid,
            permissions=GRANT_PERMISSIONS,
        )
    else:
        delete_authority_grant(grant.uid)

    with pytest.raises(SeverApplicationError, match="no longer authorized"):
        execute_sever_session_apply(
            SeverPersistedApplyRequest(snapshot=started.snapshot),
            store=active,
        )

    assert not active.context_exists("granted-source-result")
    assert SeverSessionStore(active).load(started.snapshot.session.uid).state == (
        "REVIEWING"
    )
