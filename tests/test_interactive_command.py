"""Global classification and argv contracts for interactive semantic commands."""

from click import Group, Option
from typer.main import get_command

from memcommit.adapters.console.entrypoint import app
from memcommit.application.interactive_command import (
    InteractiveCommandBinding,
    InteractiveCommandRebuildTrigger,
    InteractiveCommandRole,
    interactive_command_surface,
    validate_interactive_command_surfaces,
)
from memcommit.application.interactive_command_review import (
    meld_start_command_review,
    meld_turn_command_review,
    sever_start_command_review,
    sever_turn_command_review,
    update_start_command_review,
    update_turn_command_review,
)


def test_semantic_session_command_surfaces_are_globally_classified() -> None:
    validate_interactive_command_surfaces()

    for operation in ("meld", "update", "sever"):
        start = interactive_command_surface(operation, "setup")
        turn = interactive_command_surface(operation, "semantic-turn")
        apply = interactive_command_surface(operation, "final-apply")

        assert start.role is InteractiveCommandRole.START
        assert start.binding is InteractiveCommandBinding.PORTABLE
        assert start.rebuild_on == frozenset(
            {InteractiveCommandRebuildTrigger.DRAFT_CHANGE}
        )
        assert turn.role is InteractiveCommandRole.TURN
        assert turn.binding is InteractiveCommandBinding.SESSION_REVISION
        assert turn.rebuild_on == frozenset(
            {
                InteractiveCommandRebuildTrigger.DRAFT_CHANGE,
                InteractiveCommandRebuildTrigger.SESSION_REVISION,
            }
        )
        assert apply.role is InteractiveCommandRole.NONE


def test_bounded_semantic_transforms_remain_explicitly_commandless() -> None:
    for operation in ("summarize", "distill", "atomize"):
        assert (
            interactive_command_surface(operation, "semantic-result").role
            is InteractiveCommandRole.NONE
        )


def test_start_command_builders_use_public_portable_grammar() -> None:
    assert meld_start_command_review(
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
    assert meld_start_command_review(
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
    assert update_start_command_review(
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
    assert sever_start_command_review(
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
    assert sever_start_command_review(
        source_name="a",
        criteria_name="rules",
        output_name="a",
    ).argv == ("mem", "sever", "a", "rules")


def test_turn_command_builders_freeze_the_reviewed_session_revision() -> None:
    meld = meld_turn_command_review(
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
    update = update_turn_command_review(
        source_name="a",
        target_name="b",
        source_descendants=False,
        target_descendants=False,
        source_memory_uid=None,
        target_memory_uid=None,
        comment="remove the proposed deletion",
        expected_session="b" * 64,
    )
    sever = sever_turn_command_review(
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
