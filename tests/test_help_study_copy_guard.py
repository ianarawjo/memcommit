"""Study-only exact-copy boundaries for natural-language Help lookup."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from memcommit.help_application import describe_operation
from memcommit.profile_config import ProfileEntry, virtual_authoring_registry
from memcommit.interfaces.tui.operations.help import study_copy_guard as guard


def _field(text: str) -> guard.StudyHelpAuthoredField:
    return guard.StudyHelpAuthoredField(
        operation_name="query",
        language="EN",
        kind="DESCRIPTION",
        text=text,
    )


def _study_profile(*, role: str = "PARTICIPANT") -> ProfileEntry:
    authority = role == "GRANTED_MEMORY"
    return ProfileEntry(
        uid=(
            "33333333-3333-4333-8333-333333333333"
            if authority
            else "22222222-2222-4222-8222-222222222222"
        ),
        name="study-run-granted-memory" if authority else "study-run",
        kind="MANAGED",
        source={
            "kind": "STUDY_RUN_GRANTED_MEMORY" if authority else "STUDY_RUN",
            "study_uid": "11111111-1111-4111-8111-111111111111",
            "study_name": "study-run",
            "created_at": "2026-08-20T12:00:00+00:00",
            "baseline_sha256": "a" * 64,
            "baseline_profile_uid": "44444444-4444-4444-8444-444444444444",
            "baseline_profile_name": "study-baseline",
        },
    )


def test_exact_contiguous_half_is_rejected_after_safe_normalization():
    match = guard.find_study_help_copy_match(
        "prefix ONE, two\nthree four five suffix",
        (_field("one two three four five six seven eight nine ten"),),
    )

    assert match is not None
    assert match.exact_run_tokens == 5
    assert match.authored_field_tokens == 10


def test_less_than_half_or_distributed_words_are_allowed():
    field = _field("one two three four five six seven eight nine ten")

    assert guard.find_study_help_copy_match("one two three four", (field,)) is None
    assert (
        guard.find_study_help_copy_match(
            "one two gap three four gap five",
            (field,),
        )
        is None
    )


def test_every_visible_description_and_when_is_frozen_for_each_operation():
    fields = guard.authored_study_help_fields((describe_operation("query"),))

    assert len(fields) == 2
    assert {(field.language, field.kind) for field in fields} == {
        ("EN", "DESCRIPTION"),
        ("EN", "WHEN"),
    }
    description = next(field for field in fields if field.kind == "DESCRIPTION")
    match = guard.find_study_help_copy_match(description.text, fields)
    assert match is not None
    assert match.language == "EN"


@pytest.mark.parametrize("role", ["PARTICIPANT", "GRANTED_MEMORY"])
def test_study_mode_comes_from_active_profile_provenance(monkeypatch, role):
    monkeypatch.setattr(
        guard,
        "load_profile_registry",
        lambda: SimpleNamespace(active=_study_profile(role=role)),
    )
    assert guard.active_profile_is_study() is True

    monkeypatch.setattr(guard, "load_profile_registry", virtual_authoring_registry)
    assert guard.active_profile_is_study() is False
