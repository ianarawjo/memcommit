"""Argv contracts for interactive semantic commands."""

from click import Group, Option
from typer.main import get_command

from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.coordination.command_review import (
    meld as meld_command_review,
    sever as sever_command_review,
    update as update_command_review,
)


def test_start_command_builders_use_public_portable_grammar() -> None:
    assert meld_command_review.build_start_review(
        mode="SYMMETRIC",
        left_name="a",
        right_name="b",
        target_name="c",
        left_descendants=True,
    ).argv == (
        "mem",
        "meld",
        "a",
        "b",
        "--to",
        "c",
        "--left-descendants",
    )
    assert meld_command_review.build_start_review(
        mode="DIRECTIONAL",
        left_name="INLINE MEMORY",
        right_name="baseline",
        incoming_text='all greetings need "."!',
    ).argv == (
        "mem",
        "meld",
        "--memory",
        'all greetings need "."!',
        "--into",
        "baseline",
    )
    assert update_command_review.build_start_review(
        source_name="a",
        target_name="b",
        target_memory_uid="memory-b",
    ).argv == (
        "mem",
        "update",
        "--from",
        "a",
        "--to",
        "b",
        "--target-memory",
        "memory-b",
    )
    assert sever_command_review.build_start_review(
        source_name="a",
        criteria_name="rules",
        output_name="result",
        source_descendants=True,
        criteria_descendants=True,
    ).argv == (
        "mem",
        "sever",
        "a",
        "rules",
        "result",
        "--source-descendants",
        "--criteria-descendants",
    )
    assert sever_command_review.build_start_review(
        source_name="a",
        criteria_name="rules",
        output_name="a",
    ).argv == ("mem", "sever", "a", "rules")


def test_turn_command_builders_freeze_the_reviewed_session_revision() -> None:
    meld = meld_command_review.build_turn_review(
        left_name="a",
        right_name="b",
        target_name=None,
        left_descendants=False,
        right_descendants=False,
        left_memory_uid=None,
        right_memory_uid=None,
        issue_uid="issue-1",
        option_number=2,
        comment="keep this scope",
        expected_session="a" * 64,
    )
    update = update_command_review.build_turn_review(
        source_name="a",
        target_name="b",
        source_descendants=False,
        target_descendants=False,
        source_memory_uid=None,
        target_memory_uid=None,
        comment="remove the proposed deletion",
        expected_session="b" * 64,
    )
    sever = sever_command_review.build_turn_review(
        session_uid="session-1",
        candidate_uid="candidate-1",
        choice="custom",
        comment="exact replacement",
        expected_session="c" * 64,
    )

    assert meld.argv[-2:] == ("--expect-session", "a" * 64)
    assert update.argv[-2:] == ("--expect-session", "b" * 64)
    assert sever.argv[-2:] == ("--expect-session", "c" * 64)
    assert "--accept" not in meld.argv + update.argv + sever.argv


def test_public_semantic_session_commands_accept_revision_guards() -> None:
    command = get_command(app)
    assert isinstance(command, Group)

    for operation in ("meld", "update", "sever"):
        spellings = {
            spelling
            for parameter in command.commands[operation].params
            if isinstance(parameter, Option)
            for spelling in (*parameter.opts, *parameter.secondary_opts)
        }
        assert "--expect-session" in spellings
