"""Contracts for the rebuilt operation-neutral endpoint setup component."""

from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
import pytest

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


def _independent_reach_spec() -> EndpointSetupSpec:
    return EndpointSetupSpec(
        title="NEW RANGE OPERATION",
        subtitle="CHOOSE EACH ENDPOINT RANGE INDEPENDENTLY",
        modes=(EndpointSetupMode("RANGE", "A → B"),),
        initial_mode_uid="RANGE",
        roles=(
            EndpointSetupRole(
                "A",
                "A · SOURCE",
                ("source", "source/child"),
                frozenset({"source", "source/child"}),
                "source",
                allow_descendants=True,
            ),
            EndpointSetupRole(
                "B",
                "B · TARGET",
                ("target", "target/child"),
                frozenset({"target", "target/child"}),
                "target",
                allow_descendants=True,
            ),
        ),
    )


@pytest.mark.parametrize(
    ("keys", "source_descendants", "target_descendants"),
    (
        ("\t\t\t\t\r", False, False),
        ("\t\x1b[C\t\t\t\r", True, False),
        ("\t\t\t\x1b[C\t\r", False, True),
        ("\t\x1b[C\t\t\x1b[C\t\r", True, True),
    ),
)
def test_endpoint_setup_freezes_each_role_range_independently(
    keys: str,
    source_descendants: bool,
    target_descendants: bool,
) -> None:
    with create_pipe_input() as pipe_input:
        pipe_input.send_text(keys)
        returned = run_endpoint_setup(
            _independent_reach_spec(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is not None
    assert returned.value("A").include_descendants is source_descendants
    assert returned.value("B").include_descendants is target_descendants


def test_endpoint_setup_rejects_hidden_initial_descendant_state() -> None:
    with pytest.raises(ValueError, match="without a range control"):
        EndpointSetupRole(
            "A",
            "A",
            ("source",),
            frozenset({"source"}),
            "source",
            include_descendants=True,
        )


def test_endpoint_setup_preserves_an_explicit_initial_role_range() -> None:
    spec = _independent_reach_spec()
    source, target = spec.roles
    spec = EndpointSetupSpec(
        title=spec.title,
        subtitle=spec.subtitle,
        modes=spec.modes,
        initial_mode_uid=spec.initial_mode_uid,
        roles=(
            EndpointSetupRole(
                source.uid,
                source.label,
                source.names,
                source.selectable_names,
                source.selected_name,
                allow_descendants=True,
                include_descendants=True,
            ),
            target,
        ),
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\t\t\t\r")
        returned = run_endpoint_setup(
            spec,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is not None
    assert returned.value("A").include_descendants is True
    assert returned.value("B").include_descendants is False


def test_endpoint_setup_validator_receives_both_exact_role_ranges() -> None:
    observed: list[tuple[bool, bool]] = []

    def validate(draft: EndpointSetupDraft) -> str | None:
        ranges = (
            draft.value("A").include_descendants,
            draft.value("B").include_descendants,
        )
        observed.append(ranges)
        return "Target descendants are unavailable." if ranges[1] else None

    with create_pipe_input() as pipe_input:
        # Select only B descendants, attempt Continue, then cancel after the
        # operation-owned validator keeps the setup open.
        pipe_input.send_text("\t\t\t\x1b[C\t\rq")
        returned = run_endpoint_setup(
            _independent_reach_spec(),
            validate_draft=validate,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is None
    assert observed == [(False, True)]
