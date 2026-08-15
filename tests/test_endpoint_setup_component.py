"""Contracts for the rebuilt operation-neutral endpoint setup component."""

from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.interfaces.tui.components.endpoint_setup import (
    EndpointSetupDraft,
    EndpointSetupMode,
    EndpointSetupRole,
    EndpointSetupSpec,
    EndpointSetupValue,
    run_endpoint_setup,
)


def _spec() -> EndpointSetupSpec:
    return EndpointSetupSpec(
        title="NEW TEST OPERATION",
        subtitle="CHOOSE SHAPE AND ENDPOINTS WITHOUT MUTATION",
        modes=(
            EndpointSetupMode("DIRECT", "DIRECT · A → B", "Exact roots only."),
            EndpointSetupMode(
                "RECURSIVE",
                "RECURSIVE · A/** → B/**",
                "Match descendants by relative path.",
            ),
        ),
        initial_mode_uid="DIRECT",
        roles=(
            EndpointSetupRole(
                "A",
                "A · SOURCE",
                ("source", "target"),
                frozenset({"source"}),
                "source",
                current_context="target",
            ),
            EndpointSetupRole(
                "B",
                "B · TARGET",
                ("target",),
                frozenset({"target"}),
                "target",
                current_context="target",
                fixed=True,
            ),
        ),
    )


def test_endpoint_setup_returns_default_shape_and_frozen_target() -> None:
    with create_pipe_input() as pipe_input:
        # The editable Source owns first focus; one Tab reaches Continue.
        pipe_input.send_text("\t\r")
        returned = run_endpoint_setup(
            _spec(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned == EndpointSetupDraft(
        "DIRECT",
        (
            EndpointSetupValue("A", "source"),
            EndpointSetupValue("B", "target"),
        ),
    )


def test_endpoint_setup_switches_coupled_operation_shape() -> None:
    with create_pipe_input() as pipe_input:
        # Shift-Tab reaches Operation Shape, Right stages Recursive, and two
        # Tabs cross Source to Continue. The frozen target is not a focus stop.
        pipe_input.send_text("\x1b[Z\x1b[C\t\t\r")
        returned = run_endpoint_setup(
            _spec(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is not None
    assert returned.mode_uid == "RECURSIVE"
    assert returned.value("B").context_name == "target"


def test_endpoint_setup_cancel_returns_no_draft() -> None:
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        returned = run_endpoint_setup(
            _spec(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is None
