"""Contracts for the simultaneous three-pane Sever setup view."""

from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.commands.sever_setup_shell import (
    SeverSetupReceipt,
    _shared_local_output_name,
    choose_sever_setup,
)
from memcommit.commands.context_picker import ContextMemoryRow
from memcommit.source_projection.model import SourceAccess, SourceDisplayFacts


def test_three_pane_setup_stacks_roles_and_supplies_a_default_output() -> None:
    with create_pipe_input() as pipe_input:
        # Both trees begin on current. Confirm Source, move Criteria to the
        # other root, confirm it, then submit the prefilled Output field.
        pipe_input.send_text("\r\x1b[B\r\r")
        result = choose_sever_setup(
            ("personal-memory", "public-guidance"),
            current="personal-memory",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result == SeverSetupReceipt(
        source_name="personal-memory",
        criteria_name="public-guidance",
        output_name="severed",
    )


def test_query_only_row_is_visible_but_cannot_be_selected_as_criteria() -> None:
    with create_pipe_input() as pipe_input:
        # Move from current to the government namespace, expand and enter its
        # query-only child, and verify Enter cannot select it. Collapse back,
        # move to public guidance, select it, then submit the default Output.
        pipe_input.send_text(
            "\r\x1b[B\x1b[C\x1b[C\r\x1b[D\x1b[D\x1b[B\r\r"
        )
        result = choose_sever_setup(
            ("personal-memory",),
            current="personal-memory",
            virtual_names=("government/qna", "public-guidance"),
            selectable_virtual_names=frozenset({"public-guidance"}),
            annotations={
                "government/qna": SourceDisplayFacts(
                    access=SourceAccess.QUERY_GRANT,
                    permissions=("QUERY", "SESSION_LOG"),
                ),
                "public-guidance": SourceDisplayFacts(
                    access=SourceAccess.READ_GRANT,
                    permissions=("READ", "DERIVE"),
                ),
            },
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result is not None
    assert result.criteria_name == "public-guidance"


def test_output_pane_rejects_an_existing_context_name() -> None:
    with create_pipe_input() as pipe_input:
        # The first name submission remains in the editor because it already
        # exists. Ctrl-U replaces it with a fresh exact name.
        pipe_input.send_text(
            "\r\x1b[B\r\x15personal-memory\r\x15healthcare-draft\r"
        )
        result = choose_sever_setup(
            ("personal-memory", "public-guidance"),
            current="personal-memory",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result is not None
    assert result.output_name == "healthcare-draft"


def test_each_context_pane_has_an_independent_descendant_scope_toggle() -> None:
    with create_pipe_input() as pipe_input:
        # Up from the first Context enters Scope; Left chooses exact-only and
        # Down returns to the tree. Repeat independently in Criteria.
        pipe_input.send_text(
            "\x1b[A\x1b[D\x1b[B\r"
            "\x1b[A\x1b[D\x1b[B\x1b[B\r\r"
        )
        result = choose_sever_setup(
            ("personal-memory", "public-guidance"),
            current="personal-memory",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result is not None
    assert not result.source_descendants
    assert not result.criteria_descendants


def test_default_output_uses_a_fresh_suffix_when_the_first_name_exists() -> None:
    assert _shared_local_output_name(
        "personal-memory/source",
        "personal-memory/criteria",
        local_names=("personal-memory",),
        occupied_names=frozenset({"personal-memory/severed"}),
    ) == "personal-memory/severed-2"


def test_granted_peers_default_under_their_shared_local_ancestor() -> None:
    assert _shared_local_output_name(
        "task-3/remote/guidance",
        "task-3/local/guardrails",
        local_names=("task-1", "task-3", "task-3/local/guardrails"),
        occupied_names=frozenset(),
    ) == "task-3/severed"


def test_left_and_right_reuse_switch_tree_navigation_for_nested_criteria() -> None:
    with create_pipe_input() as pipe_input:
        # Confirm Source, move to the collapsed criteria namespace, expand it,
        # enter its child, select that exact Context, and submit Output.
        pipe_input.send_text("\r\x1b[B\x1b[C\x1b[C\r\r")
        result = choose_sever_setup(
            ("personal-memory", "criteria/nested"),
            current="personal-memory",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result is not None
    assert result.criteria_name == "criteria/nested"


def test_three_pane_setup_can_be_cancelled_without_a_receipt() -> None:
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        result = choose_sever_setup(
            ("personal-memory", "public-guidance"),
            current="personal-memory",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result is None


def test_sever_setup_memory_preview_is_lazy_and_read_only() -> None:
    loaded: list[str] = []

    def load(name: str):
        loaded.append(name)
        return (ContextMemoryRow("memory abcdef12", f"{name} content"),)

    with create_pipe_input() as pipe_input:
        # Enter on the Memory must stay in Source. The second m therefore
        # closes the cached Source preview instead of opening Criteria.
        pipe_input.send_text("m\x1b[B\rmq")
        result = choose_sever_setup(
            ("personal-memory", "public-guidance"),
            current="personal-memory",
            memory_loader=load,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result is None
    assert loaded == ["personal-memory"]
