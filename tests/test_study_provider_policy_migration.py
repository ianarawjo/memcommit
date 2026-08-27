"""Pilot Study provider-policy migration preserves pair and tombstone boundaries."""

from __future__ import annotations

import json
import uuid

import pytest

from memcommit.providers.policy import (
    LEGACY_STUDY_PROVIDER_POLICY_VERSION,
    STUDY_PROVIDER_POLICY_DIGEST,
    STUDY_PROVIDER_POLICY_VERSION,
    study_provider_config,
)
from memcommit.profile_config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_registry_file,
    study_run_identity,
)
from memcommit.profiles import (
    ProfileError,
    migrate_visible_study_provider_policy,
)


def _study_pair(
    name: str,
    *,
    version: str | None,
    digest: str | None,
) -> tuple[ProfileEntry, ProfileEntry]:
    study_uid = str(uuid.uuid4())
    baseline_uid = str(uuid.uuid4())
    common: dict[str, object] = {
        "study_uid": study_uid,
        "study_name": name,
        "created_at": "2026-08-24T12:00:00+00:00",
        "baseline_sha256": "0" * 64,
        "baseline_profile_uid": baseline_uid,
        "baseline_profile_name": "study-baseline",
    }
    if version is not None:
        common["provider_policy_version"] = version
        common["provider_policy_digest"] = digest
    participant = ProfileEntry(
        uid=str(uuid.uuid4()),
        name=name,
        kind="MANAGED",
        source={"kind": "STUDY_RUN", **common},
    )
    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name=f"{name}-granted-memory",
        kind="MANAGED",
        source={"kind": "STUDY_RUN_GRANTED_MEMORY", **common},
    )
    return participant, authority


def _write_registry(registry: ProfileRegistry) -> None:
    path = profile_registry_file()
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(registry.to_dict()), encoding="utf-8")


def _accepted_sources() -> frozenset[tuple[str | None, str | None]]:
    legacy = study_provider_config(LEGACY_STUDY_PROVIDER_POLICY_VERSION)
    return frozenset(
        {
            (None, None),
            (LEGACY_STUDY_PROVIDER_POLICY_VERSION, legacy.digest),
        }
    )


def test_migration_repins_visible_legacy_and_v1_pairs_but_not_tombstones(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    legacy_digest = study_provider_config(LEGACY_STUDY_PROVIDER_POLICY_VERSION).digest
    unpinned = _study_pair("pilot-unpinned", version=None, digest=None)
    v1 = _study_pair(
        "pilot-v1",
        version=LEGACY_STUDY_PROVIDER_POLICY_VERSION,
        digest=legacy_digest,
    )
    removed = _study_pair(
        "pilot-removed",
        version=LEGACY_STUDY_PROVIDER_POLICY_VERSION,
        digest=legacy_digest,
    )
    authoring = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    _write_registry(
        ProfileRegistry(
            generation=7,
            active_uid=v1[0].uid,
            profiles=(authoring, *unpinned, *v1, *removed),
            removed_profile_uids=tuple(profile.uid for profile in removed),
        )
    )

    result = migrate_visible_study_provider_policy(
        target_version=STUDY_PROVIDER_POLICY_VERSION,
        target_digest=STUDY_PROVIDER_POLICY_DIGEST,
        accepted_sources=_accepted_sources(),
    )

    assert result.generation == 8
    assert result.migrated_study_count == 2
    assert result.migrated_profile_count == 4
    loaded = load_profile_registry()
    assert loaded.active_uid == v1[0].uid
    for profile in (*unpinned, *v1):
        identity = study_run_identity(loaded.by_name(profile.name))  # type: ignore[arg-type]
        assert identity is not None
        assert identity.provider_policy_version == STUDY_PROVIDER_POLICY_VERSION
        assert identity.provider_policy_digest == STUDY_PROVIDER_POLICY_DIGEST
    for profile in removed:
        identity = study_run_identity(loaded.by_name(profile.name))  # type: ignore[arg-type]
        assert identity is not None
        assert identity.provider_policy_version == LEGACY_STUDY_PROVIDER_POLICY_VERSION

    unchanged = migrate_visible_study_provider_policy(
        target_version=STUDY_PROVIDER_POLICY_VERSION,
        target_digest=STUDY_PROVIDER_POLICY_DIGEST,
        accepted_sources=_accepted_sources(),
    )
    assert unchanged.generation == 8
    assert unchanged.migrated_profile_count == 0


def test_migration_rejects_an_unknown_visible_condition_without_a_write(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    unknown = _study_pair(
        "pilot-unknown",
        version="study-provider-config-unknown",
        digest="b" * 64,
    )
    authoring = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    _write_registry(
        ProfileRegistry(
            generation=3,
            active_uid=unknown[0].uid,
            profiles=(authoring, *unknown),
        )
    )
    before = profile_registry_file().read_bytes()

    with pytest.raises(ProfileError, match="unaccepted provider policy"):
        migrate_visible_study_provider_policy(
            target_version=STUDY_PROVIDER_POLICY_VERSION,
            target_digest=STUDY_PROVIDER_POLICY_DIGEST,
            accepted_sources=_accepted_sources(),
        )

    assert profile_registry_file().read_bytes() == before
