"""Validate one frozen inventory and project its Profile/Study keyboard rows."""

from __future__ import annotations

from collections.abc import Sequence

from memcommit.adapters.console.commands.profile.picker.model import (
    ProfilePickerEntry,
    ProfilePickerRow,
)


def _validate_entries(
    entries: Sequence[ProfilePickerEntry],
    *,
    current: str,
) -> tuple[ProfilePickerEntry, ...]:
    options = tuple(entries)
    if not options:
        raise ValueError("No profiles are available to select.")
    names = [entry.name for entry in options]
    if any(
        not isinstance(entry.name, str)
        or not entry.name
        or entry.context_count < 0
        or entry.memory_count < 0
        or (entry.uid is not None and not entry.uid)
        or (entry.removal_block is not None and not entry.removal_block.strip())
        or (entry.rename_block is not None and not entry.rename_block.strip())
        or (
            any(
                value is not None
                for value in (
                    entry.study_uid,
                    entry.study_name,
                    entry.study_created_at,
                    entry.study_role,
                    entry.study_session,
                )
            )
            and not (
                isinstance(entry.study_uid, str)
                and bool(entry.study_uid)
                and isinstance(entry.study_name, str)
                and bool(entry.study_name)
                and isinstance(entry.study_created_at, str)
                and bool(entry.study_created_at)
                and entry.study_profile_count >= 1
                and entry.study_role in {"PARTICIPANT"}
                and (
                    (isinstance(entry.study_session, str) and bool(entry.study_session))
                    or (entry.study_session is None and entry.study_profile_count == 1)
                )
            )
        )
        or (entry.study_name is None and entry.study_profile_count != 0)
        for entry in options
    ) or len(set(names)) != len(names):
        raise ValueError("Profile selection received invalid entries.")
    study_metadata: dict[
        str,
        tuple[str, str, int, set[str]],
    ] = {}
    finished_studies: set[str] = set()
    previous_study: str | None = None
    for entry in options:
        study_name = entry.study_name
        if study_name is None:
            if previous_study is not None:
                finished_studies.add(previous_study)
            previous_study = None
            continue
        if previous_study is not None and study_name != previous_study:
            finished_studies.add(previous_study)
        if study_name in finished_studies:
            raise ValueError("Study Profile entries must remain contiguous.")
        created_at = entry.study_created_at
        study_uid = entry.study_uid
        assert isinstance(created_at, str)
        assert isinstance(study_uid, str)
        assert entry.study_role is not None
        member = entry.study_session or entry.study_role
        existing = study_metadata.get(study_name)
        metadata = (
            study_uid,
            created_at,
            entry.study_profile_count,
        )
        if existing is None:
            study_metadata[study_name] = (*metadata, {member})
        elif existing[:3] != metadata or member in existing[3]:
            raise ValueError("Study Profile entries are inconsistent.")
        else:
            existing[3].add(member)
        previous_study = study_name
    if any(len(metadata[3]) != metadata[2] for metadata in study_metadata.values()):
        raise ValueError("Study Profile count does not match its registered entries.")
    if current not in names:
        raise ValueError("The current profile is not available to select.")
    return options


def build_picker_rows(
    entries: Sequence[ProfilePickerEntry],
    *,
    current: str,
) -> tuple[ProfilePickerRow, ...]:
    options = _validate_entries(entries, current=current)
    rows: list[ProfilePickerRow] = []
    previous_study: str | None = None
    for entry in options:
        if entry.study_name is not None and entry.study_name != previous_study:
            rows.append(
                ProfilePickerRow(
                    kind="STUDY",
                    name=entry.study_name,
                    uid=entry.study_uid,
                    created_at=entry.study_created_at,
                    profile_count=entry.study_profile_count,
                )
            )
        rows.append(
            ProfilePickerRow(
                kind="PROFILE",
                name=entry.name,
                uid=entry.uid,
                entry=entry,
            )
        )
        previous_study = entry.study_name
    return tuple(rows)
