"""Grant alias identity collisions cannot replace an existing Context Embed."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from threading import Barrier
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.application.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.context import Context
from memcommit.application.operations.embed.application import EmbedRequest
from memcommit.application.operations.embed.runtime import MemoryStoreEmbedPort
from memcommit.application.operations.profile.config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.application.operations.profile.model import create_authority_grant
from memcommit.persistence.store import ConcurrentContextUpdateError, MemoryStore


runner = CliRunner(mix_stderr=False)


def _two_alias_fixture(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> tuple[MemoryStore, Context, Context, str, str]:
    monkeypatch.setenv("HOME", str(tmp_path))
    local = MemoryStore()
    target = ops.init("workspace")
    local.save(target)
    local.set_current(target.name)

    grantee = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="alias-authority",
        kind="MANAGED",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    source = ops.init("authority-source")
    ops.add(source, "One authority-owned Memory.")
    authority_store.save(source)

    registry = ProfileRegistry(
        generation=1,
        active_uid=grantee.uid,
        profiles=(grantee, authority),
        grants=(),
    )
    path = profile_registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry.to_dict(), indent=2) + "\n")

    first_alias = "source-primary"
    second_alias = "source-secondary"
    create_authority_grant(
        authority_name=authority.name,
        grantee_name=grantee.name,
        resource_name=source.name,
        attachment_name=target.name,
        public_name=first_alias,
        permissions=("READ", "EMBED"),
    )
    create_authority_grant(
        authority_name=authority.name,
        grantee_name=grantee.name,
        resource_name=source.name,
        attachment_name=target.name,
        public_name=second_alias,
        permissions=("READ", "EMBED"),
    )
    return local, target, source, first_alias, second_alias


def test_embed_rejects_a_second_name_for_the_same_context_identity() -> None:
    parent = ops.init("target")
    first = Context(uid=str(uuid.uuid4()), name="source-primary")
    second = Context(uid=first.uid, name="source-secondary")
    ops.embed(first, parent)
    before = parent.to_dict()

    with pytest.raises(
        ValueError,
        match=(
            "'source-secondary' has the same Context identity as already "
            "embedded 'source-primary' in 'target'"
        ),
    ):
        ops.embed(second, parent)

    assert parent.to_dict() == before


def test_second_grant_alias_embed_preserves_record_order_and_checkpoints(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, target, source, first_alias, second_alias = _two_alias_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    first = runner.invoke(app, ["embed", first_alias, "--into", target.name])
    assert first.exit_code == 0, first.output + first.stderr

    before = store.load_direct(target.name)
    before_record = before.to_dict()
    before_order = tuple(before.ordered_uids())
    before_checkpoints = tuple(
        checkpoint["uid"] for checkpoint in store.list_checkpoints(target.name)
    )
    first_link = before_record["memories"][source.uid]
    assert first_link["type"] == "granted_context_ref"
    assert first_link["name"] == first_alias

    second = runner.invoke(app, ["embed", second_alias, "--into", target.name])

    assert second.exit_code == 1
    assert second_alias in second.stderr
    assert first_alias in second.stderr
    assert "same Context identity as already embedded" in second.stderr
    after = store.load_direct(target.name)
    assert after.to_dict() == before_record
    assert tuple(after.ordered_uids()) == before_order == (source.uid,)
    assert (
        tuple(checkpoint["uid"] for checkpoint in store.list_checkpoints(target.name))
        == before_checkpoints
    )


def test_two_frozen_grant_alias_plans_cas_the_same_target_revision(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, target, source, first_alias, second_alias = _two_alias_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    port = MemoryStoreEmbedPort.capture(store, allow_granted_sources=True)
    plans = tuple(
        port.freeze(EmbedRequest(alias, target.name))
        for alias in (first_alias, second_alias)
    )
    assert plans[0].into_digest == plans[1].into_digest

    # Force both Apply calls to hold a Target object loaded from the same
    # reviewed revision before either can publish. The Grant registry lock then
    # serializes the writes, so the second save must still reject its stale CAS.
    ready = Barrier(2)
    original_load_for_update = store.load_for_update

    def synchronized_load_for_update(name: str) -> Context:
        context = original_load_for_update(name)
        ready.wait(timeout=10)
        return context

    expected_digests: list[str | None] = []
    original_save = store.save

    def recording_save(
        context: Context,
        checkpoint=None,
        *,
        expected_context_digest: str | None = None,
    ):
        expected_digests.append(expected_context_digest)
        return original_save(
            context,
            checkpoint,
            expected_context_digest=expected_context_digest,
        )

    monkeypatch.setattr(store, "load_for_update", synchronized_load_for_update)
    monkeypatch.setattr(store, "save", recording_save)

    receipts = []
    errors = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = tuple(executor.submit(port.apply, plan) for plan in plans)
        for future in futures:
            try:
                receipts.append(future.result(timeout=20))
            except Exception as error:  # noqa: BLE001 - assert the exact loser below.
                errors.append(error)

    assert len(receipts) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], ConcurrentContextUpdateError)
    assert expected_digests == [plans[0].into_digest, plans[0].into_digest]

    final = store.load_direct(target.name)
    assert tuple(final.ordered_uids()) == (source.uid,)
    assert final.memories[source.uid].name in {first_alias, second_alias}
    assert len(store.list_checkpoints(target.name)) == 1
