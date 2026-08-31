"""Argv contracts for interactive semantic commands."""

from click import Group, Option
from typer.main import get_command

from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.commands.semantic_updates.curate_integrate.meld import (
    command_codec as meld_command_review,
)
from memcommit.adapters.console.commands.semantic_updates.curate_integrate.sever import (
    command_codec as sever_command_review,
)
from memcommit.adapters.console.commands.semantic_updates.foundation.update import (
    command_codec as update_command_review,
)
from memcommit.adapters.console.commands.create_copy_connect.branch import (
    command_codec as branch_command_review,
)
from memcommit.adapters.console.terminal.components.endpoint_setup import (
    EndpointSetupDraft,
    EndpointSetupValue,
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


def test_iterative_turn_command_builders_freeze_the_reviewed_session_revision() -> None:
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
    sever = sever_command_review.build_turn_review(
        session_uid="session-1",
        candidate_uid="candidate-1",
        choice="custom",
        comment="exact replacement",
        expected_session="c" * 64,
    )

    assert meld.argv[-2:] == ("--expect-session", "a" * 64)
    assert sever.argv[-2:] == ("--expect-session", "c" * 64)
    assert "--accept" not in meld.argv + sever.argv


def test_endpoint_command_codecs_round_trip_all_editable_setup_shapes() -> None:
    meld_symmetric = EndpointSetupDraft(
        "SYMMETRIC",
        (
            EndpointSetupValue("A", "a", include_descendants=True),
            EndpointSetupValue("B", "b"),
            EndpointSetupValue("C", "c", create=True),
        ),
    )
    meld_directional = EndpointSetupDraft(
        "DIRECTIONAL",
        (
            EndpointSetupValue("A", "a", memory_uid="memory-a"),
            EndpointSetupValue("B", "b", memory_uid="memory-b"),
        ),
    )
    update = EndpointSetupDraft(
        "UPDATE",
        (
            EndpointSetupValue("A", "a", include_descendants=True),
            EndpointSetupValue("B", "b", memory_uid="memory-b"),
        ),
    )
    sever = EndpointSetupDraft(
        "SEVER",
        (
            EndpointSetupValue("SOURCE", "a", include_descendants=True),
            EndpointSetupValue("CRITERIA", "rules"),
            EndpointSetupValue("OUTPUT", "result", create=True),
        ),
    )
    branch = EndpointSetupDraft(
        "BRANCH",
        (
            EndpointSetupValue("A", "a", include_descendants=True),
            EndpointSetupValue("B", "new", create=True),
        ),
    )

    assert meld_command_review.parse_endpoint_argv(
        meld_command_review.build_start_review(
            mode="SYMMETRIC",
            left_name="a",
            right_name="b",
            target_name="c",
            left_descendants=True,
        ).argv
    ) == EndpointSetupDraft(
        meld_symmetric.mode_uid,
        (*meld_symmetric.values[:2], EndpointSetupValue("C", "c")),
    )
    assert (
        meld_command_review.parse_endpoint_argv(
            meld_command_review.build_start_review(
                mode="DIRECTIONAL",
                left_name="a",
                right_name="b",
                left_memory_uid="memory-a",
                right_memory_uid="memory-b",
            ).argv
        )
        == meld_directional
    )
    assert (
        update_command_review.parse_endpoint_argv(
            update_command_review.build_start_review(
                source_name="a",
                target_name="b",
                source_descendants=True,
                target_memory_uid="memory-b",
            ).argv
        )
        == update
    )
    assert sever_command_review.parse_endpoint_argv(
        sever_command_review.build_start_review(
            source_name="a",
            criteria_name="rules",
            output_name="result",
            source_descendants=True,
        ).argv
    ) == EndpointSetupDraft(
        sever.mode_uid,
        (*sever.values[:2], EndpointSetupValue("OUTPUT", "result")),
    )
    assert (
        branch_command_review.parse_endpoint_argv(
            branch_command_review.build_review(branch).argv
        )
        == branch
    )


def test_only_iterative_semantic_commands_accept_revision_guards() -> None:
    command = get_command(app)
    assert isinstance(command, Group)

    for operation in ("meld", "sever"):
        spellings = {
            spelling
            for parameter in command.commands[operation].params
            if isinstance(parameter, Option)
            for spelling in (*parameter.opts, *parameter.secondary_opts)
        }
        assert "--expect-session" in spellings
    update_spellings = {
        spelling
        for parameter in command.commands["update"].params
        if isinstance(parameter, Option)
        for spelling in (*parameter.opts, *parameter.secondary_opts)
    }
    assert "--expect-session" not in update_spellings
    assert "--comment" not in update_spellings
