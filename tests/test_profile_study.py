"""Current Study topology and the retired split-Study boundary."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import subprocess
import sys
import uuid

import pytest

from memcommit.application.operations.profile.config import (
    ProfileEntry,
    ProfileRegistry,
)
from memcommit.application.operations.profile.errors import ProfileError
from memcommit.application.operations.profile.study.topology import (
    _study_target,
    study_run_profile_pairs,
)


def _pair(name: str = "pilot") -> tuple[ProfileEntry, ProfileEntry]:
    common = {
        "study_uid": str(uuid.uuid4()),
        "study_name": name,
        "created_at": "2026-09-06T00:00:00+00:00",
        "baseline_profile_uid": str(uuid.uuid4()),
        "baseline_profile_name": "coffee",
        "baseline_sha256": "a" * 64,
    }
    return tuple(
        ProfileEntry(
            uid=str(uuid.uuid4()),
            name=profile_name,
            kind="MANAGED",
            source={"kind": kind, **common},
        )
        for profile_name, kind in (
            (f"{name}-participant", "STUDY_RUN"),
            (f"{name}-authority", "STUDY_RUN_GRANTED_MEMORY"),
        )
    )


def test_study_target_uses_shared_label_and_stable_member_identity():
    participant, authority = _pair()
    participant = replace(participant, name="independent-member-name")
    registry = ProfileRegistry(
        generation=7, active_uid=participant.uid, profiles=(participant, authority)
    )
    uid, name, members = _study_target(registry, "PILOT")
    assert uid == participant.source["study_uid"]
    assert name == "pilot"
    assert members == (participant, authority)
    with pytest.raises(ProfileError, match="does not exist"):
        _study_target(registry, participant.name)


@pytest.mark.parametrize(
    "invalid", ["missing", "duplicate_role", "different_provenance"]
)
def test_current_study_requires_one_consistent_participant_authority_pair(invalid):
    participant, authority = _pair()
    if invalid == "missing":
        profiles = (participant,)
    elif invalid == "duplicate_role":
        profiles = (participant, replace(authority, source=dict(participant.source)))
    else:
        profiles = (
            participant,
            replace(
                authority, source={**authority.source, "baseline_sha256": "b" * 64}
            ),
        )
    with pytest.raises(ProfileError, match="incomplete|inconsistent"):
        study_run_profile_pairs(profiles)


def test_study_labels_remain_unique_case_insensitively():
    with pytest.raises(ProfileError, match="names must be unique"):
        study_run_profile_pairs((*_pair("pilot"), *_pair("PILOT")))


def test_retired_split_provenance_is_not_a_study_target():
    old_profile = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="old-task-1",
        kind="MANAGED",
        source={"kind": "STUDY_RUN_TASK", "study_name": "old"},
    )
    registry = ProfileRegistry(
        generation=1, active_uid=old_profile.uid, profiles=(old_profile,)
    )
    assert study_run_profile_pairs(registry.profiles) == ()
    with pytest.raises(ProfileError, match="does not exist"):
        _study_target(registry, "old")
    assert registry.profiles == (old_profile,)


def test_topology_import_does_not_load_storage_or_lifecycle():
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
from memcommit.application.operations.profile.study.topology import study_run_profile_pairs
assert study_run_profile_pairs(()) == ()
assert 'memcommit.application.operations.profile.model._storage' not in sys.modules
assert 'memcommit.application.operations.profile.study.lifecycle' not in sys.modules
assert 'memcommit.application.operations.profile.study.provider_policy_migration' not in sys.modules
""",
        ],
        check=True,
    )


@pytest.mark.parametrize(
    "first", ["topology", "lifecycle", "provider_policy_migration"]
)
def test_current_aggregate_exports_share_canonical_identity_for_each_import_order(
    first,
):
    subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
from importlib import import_module
import_module('memcommit.application.operations.profile.study.{first}')
from memcommit.application.operations.profile import model
from memcommit.application.operations.profile.study import lifecycle, topology
from memcommit.application.operations.profile.errors import ProfileError
assert model.rename_study is lifecycle.rename_study
assert model.remove_study is lifecycle.remove_study
assert model.study_run_profile_pairs is topology.study_run_profile_pairs
assert model.ProfileError is ProfileError
assert not hasattr(model, 'archive_legacy_study')
assert not hasattr(model, 'study_profile_groups')
""",
        ],
        check=True,
    )


def test_retired_archive_route_and_physical_module_are_absent():
    from typer.main import get_command
    from memcommit.adapters.console.commands.profile.command import app

    from memcommit.adapters.console.commands.help.inventory import COMMAND_FORMS

    commands = get_command(app).commands
    assert "archive-study" not in commands
    assert all("archive-study" not in form for form in COMMAND_FORMS["profile"])
    assert {"rename-study", "remove-study"} <= commands.keys()
    root = Path(__file__).parents[1]
    assert not (
        root / "src/memcommit/application/operations/profile/model/study.py"
    ).exists()
