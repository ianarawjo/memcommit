"""Strict persistence and interaction contracts for the atomize workbench."""

from __future__ import annotations

import copy
import hashlib
import uuid

import pytest

from memcommit.atomize_workbench import (
    ATOMIZE_WORKBENCH_SCHEMA_VERSION,
    AtomizeWorkbenchError,
    AtomizeWorkbenchIssue,
    AtomizeWorkbenchSession,
    atomize_workbench_issue_digest,
)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _issues() -> tuple[AtomizeWorkbenchIssue, ...]:
    return (
        AtomizeWorkbenchIssue(
            uid="ambiguity:m2",
            source_order=1,
            priority=2,
            choice_uids=("ambiguity:m2:reading:1", "ambiguity:m2:reading:2"),
        ),
        AtomizeWorkbenchIssue(
            uid="atomize:m1",
            source_order=0,
            priority=1,
        ),
        AtomizeWorkbenchIssue(
            uid="conflict:m2:m3",
            source_order=1,
            priority=3,
            choice_uids=("conflict:m2:m3:reading:1",),
        ),
    )


def _session(
    issues: tuple[AtomizeWorkbenchIssue, ...] | None = None,
) -> AtomizeWorkbenchSession:
    return AtomizeWorkbenchSession.create(
        analysis_uid=str(uuid.uuid4()),
        context_uid=str(uuid.uuid4()),
        context_name="temp/task-1",
        context_digest=_digest("context"),
        issues=issues if issues is not None else _issues(),
    )


def test_create_round_trips_only_mutable_state_bound_to_issue_digest():
    issues = _issues()
    session = _session(issues)
    session.response_for(
        "ambiguity:m2"
    ).text = "The first reading is right, but staff alone are authorized."
    session.move(1)
    session.select_choice(0)
    session.toggle_layout()

    data = session.to_dict()
    restored = AtomizeWorkbenchSession.from_dict(data, issues=issues)

    assert set(data) == {
        "schema_version",
        "uid",
        "analysis_uid",
        "context",
        "output_context_name",
        "issue_digest",
        "cursor_uid",
        "sort",
        "layout",
        "responses",
        "application",
    }
    assert data["schema_version"] == ATOMIZE_WORKBENCH_SCHEMA_VERSION
    assert data["output_context_name"] == "temp/task-1"
    assert data["issue_digest"] == atomize_workbench_issue_digest(issues)
    assert "issues" not in data
    assert restored.to_dict() == data
    assert restored.layout == "STACKED"
    assert restored.answered_count == 1


def test_output_plan_round_trips_and_schema_one_defaults_to_in_place():
    issues = _issues()
    session = AtomizeWorkbenchSession.create(
        analysis_uid=str(uuid.uuid4()),
        context_uid=str(uuid.uuid4()),
        context_name="atomize/input",
        context_digest=_digest("context"),
        output_context_name="atomize/output",
        issues=issues,
    )

    assert session.output_context_name == "atomize/output"
    restored = AtomizeWorkbenchSession.from_dict(
        session.to_dict(),
        issues=issues,
    )
    assert restored.output_context_name == "atomize/output"

    destination_only = session.to_dict()
    destination_only["schema_version"] = 2
    destination_only.pop("application")
    restored_destination_only = AtomizeWorkbenchSession.from_dict(
        destination_only,
        issues=issues,
    )
    assert restored_destination_only.output_context_name == "atomize/output"
    assert restored_destination_only.application is None

    legacy = session.to_dict()
    legacy["schema_version"] = 1
    legacy.pop("output_context_name")
    legacy.pop("application")
    restored_legacy = AtomizeWorkbenchSession.from_dict(
        legacy,
        issues=issues,
    )
    assert restored_legacy.output_context_name == "atomize/input"


def test_application_receipt_is_terminal_and_round_trips_with_comments():
    issues = _issues()
    session = AtomizeWorkbenchSession.create(
        analysis_uid=str(uuid.uuid4()),
        context_uid=str(uuid.uuid4()),
        context_name="atomize/input",
        context_digest=_digest("context"),
        output_context_name="atomize/output",
        issues=issues,
    )
    checkpoint_uid = str(uuid.uuid4())
    session.record_application(
        output_context_name="atomize/output",
        checkpoint_uid=checkpoint_uid,
    )
    session.response_for("ambiguity:m2").text = "Retain this as review evidence."

    restored = AtomizeWorkbenchSession.from_dict(
        session.to_dict(),
        issues=issues,
    )

    assert restored.application is not None
    assert restored.application.output_context_name == "atomize/output"
    assert restored.application.checkpoint_uid == checkpoint_uid
    assert restored.response_for("ambiguity:m2").text == (
        "Retain this as review evidence."
    )
    with pytest.raises(AtomizeWorkbenchError, match="different application"):
        restored.record_application(
            output_context_name="atomize/output",
            checkpoint_uid=str(uuid.uuid4()),
        )


def test_source_and_priority_order_are_deterministic_and_cursor_is_stable():
    session = _session()

    assert [issue.uid for issue in session.ordered_issues()] == [
        "atomize:m1",
        "ambiguity:m2",
        "conflict:m2:m3",
    ]
    assert session.cursor_uid == "atomize:m1"

    session.move(1)
    assert session.cursor_uid == "ambiguity:m2"
    session.toggle_sort()

    assert session.cursor_uid == "ambiguity:m2"
    assert [issue.uid for issue in session.ordered_issues()] == [
        "conflict:m2:m3",
        "ambiguity:m2",
        "atomize:m1",
    ]
    session.move(-1)
    assert session.cursor_uid == "conflict:m2:m3"
    session.move(-10)
    assert session.cursor_uid == "conflict:m2:m3"
    session.move(10)
    assert session.cursor_uid == "atomize:m1"


def test_select_choice_and_freeform_response_are_independent():
    session = _session()
    session.move(1)

    session.select_choice(1)
    response = session.response_for("ambiguity:m2")
    response.text = "Keep this reading and add the staff-only condition."

    assert response.selected_choice_uid == "ambiguity:m2:reading:2"
    assert session.selected_choice_index() == 1
    assert session.answered_count == 1

    session.select_choice(None)
    assert response.selected_choice_uid is None
    assert response.text
    assert session.answered_count == 1

    with pytest.raises(AtomizeWorkbenchError, match="Unknown"):
        session.select_choice(2)


def test_empty_issue_set_has_no_cursor_and_movement_is_safe():
    session = _session(())

    assert session.cursor_uid is None
    assert session.current_issue() is None
    session.move(1)
    session.select_choice(None)
    assert session.cursor_uid is None
    assert session.answered_count == 0


def test_exact_match_checks_revision_context_and_complete_issue_projection():
    issues = _issues()
    session = _session(issues)
    arguments = {
        "analysis_uid": session.analysis_uid,
        "context_uid": session.context_uid,
        "context_name": session.context_name,
        "context_digest": session.context_digest,
        "issues": issues,
    }

    assert session.matches_analysis(**arguments)
    assert not session.matches_analysis(
        **{**arguments, "analysis_uid": str(uuid.uuid4())}
    )
    assert not session.matches_analysis(
        **{**arguments, "context_digest": _digest("edited")}
    )
    changed_choices = (
        AtomizeWorkbenchIssue(
            uid=issues[0].uid,
            source_order=issues[0].source_order,
            priority=issues[0].priority,
            choice_uids=("a-different-reading",),
        ),
        *issues[1:],
    )
    assert not session.matches_analysis(**{**arguments, "issues": changed_choices})


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda data: data.update({"extra": True}),
            "Invalid atomize workbench session",
        ),
        (
            lambda data: data.update({"schema_version": True}),
            "Unsupported atomize workbench schema",
        ),
        (
            lambda data: data.update({"uid": str(uuid.uuid4()).upper()}),
            "Invalid atomize workbench session uid",
        ),
        (
            lambda data: data["context"].update({"digest": "0" * 63}),
            "Invalid atomize workbench Context digest",
        ),
        (
            lambda data: data.update({"sort": "TIME"}),
            "Invalid atomize workbench sort mode",
        ),
        (
            lambda data: data.update({"layout": "GRID"}),
            "Invalid atomize workbench layout",
        ),
        (
            lambda data: data.update({"cursor_uid": "missing"}),
            "Invalid atomize workbench cursor",
        ),
    ],
)
def test_strict_loader_rejects_invalid_session_shapes(mutate, message):
    issues = _issues()
    data = copy.deepcopy(_session(issues).to_dict())
    mutate(data)

    with pytest.raises(AtomizeWorkbenchError, match=message):
        AtomizeWorkbenchSession.from_dict(data, issues=issues)


def test_loader_rejects_issue_or_choice_mismatch_and_unknown_response_target():
    issues = _issues()
    session = _session(issues)
    data = session.to_dict()

    reordered = tuple(reversed(issues))
    with pytest.raises(AtomizeWorkbenchError, match="do not match"):
        AtomizeWorkbenchSession.from_dict(data, issues=reordered)

    unknown_target = copy.deepcopy(data)
    unknown_target["responses"] = {
        "missing": {"selected_choice_uid": None, "text": "comment"}
    }
    with pytest.raises(AtomizeWorkbenchError, match="response target"):
        AtomizeWorkbenchSession.from_dict(unknown_target, issues=issues)

    unknown_choice = copy.deepcopy(data)
    unknown_choice["responses"] = {
        "ambiguity:m2": {
            "selected_choice_uid": "not-a-reading",
            "text": "",
        }
    }
    with pytest.raises(AtomizeWorkbenchError, match="unknown choice"):
        AtomizeWorkbenchSession.from_dict(unknown_choice, issues=issues)


def test_issue_descriptors_are_strict_and_digest_all_ordering_inputs():
    with pytest.raises(AtomizeWorkbenchError, match="Duplicate"):
        AtomizeWorkbenchIssue(
            uid="issue",
            source_order=0,
            priority=1,
            choice_uids=("same", "same"),
        )
    with pytest.raises(AtomizeWorkbenchError, match="source order"):
        AtomizeWorkbenchIssue(
            uid="issue",
            source_order=True,
            priority=1,
        )

    base = _issues()
    priority_changed = (
        AtomizeWorkbenchIssue(
            uid=base[0].uid,
            source_order=base[0].source_order,
            priority=base[0].priority + 1,
            choice_uids=base[0].choice_uids,
        ),
        *base[1:],
    )
    assert atomize_workbench_issue_digest(base) != (
        atomize_workbench_issue_digest(priority_changed)
    )
