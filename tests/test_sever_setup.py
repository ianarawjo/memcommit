"""Contracts for Sever's command-owned shared Endpoint Setup adapter."""

from __future__ import annotations

from pathlib import Path

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
import pytest

from memcommit.adapters.console.terminal.components.context_picker import (
    ContextMemoryRow,
)
from memcommit.adapters.console.commands.sever.endpoint_setup import (
    SeverEndpointSelection,
    SeverSetupReceipt,
    SeverTuiSetup,
    _validate_sever_draft,
    choose_sever_endpoint_setup,
    choose_sever_setup,
    sever_endpoint_setup_spec,
)
from memcommit.adapters.console.terminal.components.endpoint_setup import (
    EndpointSetupDraft,
    EndpointSetupValue,
)
from memcommit.source_projection.model import SourceAccess, SourceDisplayFacts


REPOSITORY_ROOT = Path(__file__).parents[1]


def _setup() -> SeverTuiSetup:
    return SeverTuiSetup(
        names=("personal-memory", "public-guidance"),
        local_names=("personal-memory", "public-guidance"),
        selectable_names=frozenset({"personal-memory", "public-guidance"}),
        source_name="personal-memory",
        criteria_name="public-guidance",
        current_context="personal-memory",
    )


def test_sever_setup_projects_two_in_place_roles_with_descendant_controls() -> None:
    spec = sever_endpoint_setup_spec(_setup())

    assert spec.screen_layout == "COMPACT_FORM"
    assert spec.initial_mode_uid == "SEVER"
    assert tuple(role.uid for role in spec.roles) == ("SOURCE", "CRITERIA")
    assert all(role.include_descendants for role in spec.roles)
    assert all(role.memory_preview_only for role in spec.roles)
    assert "UPDATED IN PLACE" in spec.roles[0].label
    assert "RESULT" not in spec.title
    assert spec.action_label == "START SEVER"


def test_shared_role_pane_returns_the_default_recursive_in_place_receipt() -> None:
    with create_pipe_input() as pipe_input:
        # Source -> Criteria -> exact START command.
        pipe_input.send_text("\x1b[B" * 2 + "\r")
        result = choose_sever_endpoint_setup(
            _setup(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result == SeverEndpointSelection(
        source_name="personal-memory",
        criteria_name="public-guidance",
        source_descendants=True,
        criteria_descendants=True,
    )


def test_query_only_row_is_visible_but_not_selectable_for_either_input() -> None:
    setup = SeverTuiSetup(
        names=("personal-memory", "government/qna", "public-guidance"),
        local_names=("personal-memory",),
        selectable_names=frozenset({"personal-memory", "public-guidance"}),
        source_name="personal-memory",
        criteria_name="public-guidance",
        current_context="personal-memory",
        annotations=(
            (
                "government/qna",
                SourceDisplayFacts(
                    access=SourceAccess.QUERY_GRANT,
                    permissions=("QUERY",),
                ),
            ),
            (
                "public-guidance",
                SourceDisplayFacts(
                    access=SourceAccess.READ_GRANT,
                    permissions=("READ",),
                ),
            ),
        ),
    )
    spec = sever_endpoint_setup_spec(setup)

    assert "government/qna" in spec.roles[0].names
    assert "government/qna" not in spec.roles[0].selectable_names
    assert "government/qna" not in spec.roles[1].selectable_names


def test_source_descendants_remain_a_valid_in_place_scope() -> None:
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B" * 2 + "\r")
        result = choose_sever_endpoint_setup(
            _setup(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result == SeverEndpointSelection(
        source_name="personal-memory",
        criteria_name="public-guidance",
        source_descendants=True,
        criteria_descendants=True,
    )


def test_each_input_role_keeps_an_independent_descendant_toggle() -> None:
    with create_pipe_input() as pipe_input:
        # Clear Source descendants, move to Criteria and clear its independent
        # range, then move to the exact START command.
        pipe_input.send_text("\t\t \x1b[B\t\t \x1b[B\r")
        result = choose_sever_endpoint_setup(
            _setup(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result is not None
    assert result.source_descendants is False
    assert result.criteria_descendants is False


def test_shared_role_pane_can_be_cancelled_without_a_receipt() -> None:
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        result = choose_sever_endpoint_setup(
            _setup(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result is None


def test_sever_memory_rows_remain_lazy_read_only_preview_evidence() -> None:
    loaded: list[str] = []

    def load(name: str):
        loaded.append(name)
        return (
            ContextMemoryRow(
                "11111111",
                f"{name} content",
                selector="11111111-1111-4111-8111-111111111111",
            ),
        )

    with create_pipe_input() as pipe_input:
        # Source input -> Browse -> Range -> Memory. Open, move to the Memory,
        # and press Enter; preview-only mode must not stage its UID.
        pipe_input.send_text("\t\t \t\r\x1b[B\rq")
        result = choose_sever_endpoint_setup(
            _setup(),
            memory_loader=load,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result is None
    assert loaded == ["personal-memory"]


def test_sever_tui_setup_rejects_an_unusable_catalog() -> None:
    with pytest.raises(ValueError, match="two selectable"):
        SeverTuiSetup(
            names=("local", "query-only"),
            local_names=("local",),
            selectable_names=frozenset({"local"}),
            source_name="local",
            criteria_name="query-only",
        )


def test_granted_source_cannot_be_presented_as_an_in_place_source() -> None:
    setup = SeverTuiSetup(
        names=("remote/source", "local/criteria"),
        local_names=("local/criteria",),
        selectable_names=frozenset({"remote/source", "local/criteria"}),
        source_name="local/criteria",
        criteria_name="remote/source",
    )
    draft = EndpointSetupDraft(
        "SEVER",
        (
            EndpointSetupValue("SOURCE", "remote/source"),
            EndpointSetupValue("CRITERIA", "local/criteria"),
        ),
    )

    assert _validate_sever_draft(setup, draft) == (
        "In-place Sever requires an ordinary local Source Context."
    )


def test_sever_setup_is_command_owned_without_compatibility_facades() -> None:
    assert choose_sever_setup.__module__ == (
        "memcommit.adapters.console.commands.sever.endpoint_setup"
    )
    assert not (
        REPOSITORY_ROOT / "src/memcommit/adapters/console/commands/sever/setup_shell.py"
    ).exists()
    former_interface = (
        REPOSITORY_ROOT / "src/memcommit/adapters/interfaces/tui/operations/sever"
    )
    assert not tuple(former_interface.glob("*.py"))


def test_legacy_shaped_entry_uses_the_shared_role_pane() -> None:
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B" * 3 + "\r")
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
    )
