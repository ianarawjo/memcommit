"""Mode-dependent role and new-name coverage for shared Endpoint Setup."""

from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
import pytest

from memcommit.adapters.console.tui.components.endpoint_setup import (
    EndpointSetupMode,
    EndpointSetupRole,
    EndpointSetupSpec,
    EndpointSetupValue,
    run_endpoint_setup,
)


def _meld_shaped_spec() -> EndpointSetupSpec:
    names = ("meld/a", "meld/b", "meld/empty")
    source_names = frozenset(names)
    return EndpointSetupSpec(
        title="NEW MELD",
        subtitle="SETUP ONLY",
        modes=(
            EndpointSetupMode(
                "SYMMETRIC",
                "SYMMETRIC · A + B → C",
                active_role_uids=("A", "B", "C"),
                role_labels=(
                    ("A", "A · PEER"),
                    ("B", "B · PEER"),
                    ("C", "C · RESULT"),
                ),
                descendant_role_uids=frozenset({"A", "B"}),
                memory_focus_role_uids=frozenset(),
            ),
            EndpointSetupMode(
                "DIRECTIONAL",
                "DIRECTIONAL · A → B",
                active_role_uids=("A", "B"),
                role_labels=(
                    ("A", "A · INCOMING"),
                    ("B", "B · BASELINE + RESULT"),
                ),
                descendant_role_uids=frozenset({"A", "B"}),
                memory_focus_role_uids=frozenset({"A", "B"}),
            ),
        ),
        initial_mode_uid="SYMMETRIC",
        roles=(
            EndpointSetupRole(
                "A",
                "A",
                names,
                source_names,
                "meld/a",
                allow_descendants=True,
                allow_memory_focus=True,
            ),
            EndpointSetupRole(
                "B",
                "B",
                names,
                source_names,
                "meld/b",
                allow_descendants=True,
                allow_memory_focus=True,
            ),
            EndpointSetupRole(
                "C",
                "C",
                names,
                frozenset({"meld/empty"}),
                "meld/empty",
                allow_new=True,
                new_label="CREATE NEW RESULT CONTEXT",
                prefer_new=True,
            ),
        ),
    )


def test_endpoint_setup_mode_contract_projects_roles_labels_and_capabilities():
    spec = _meld_shaped_spec()

    assert spec.screen_layout == "WORKBENCH"
    assert spec.active_role_uids("SYMMETRIC") == ("A", "B", "C")
    assert spec.active_role_uids("DIRECTIONAL") == ("A", "B")
    assert spec.role_label("SYMMETRIC", "C") == "C · RESULT"
    assert spec.role_label("DIRECTIONAL", "B") == "B · BASELINE + RESULT"
    assert spec.role_allows_descendants("SYMMETRIC", "A") is True
    assert spec.role_allows_memory_focus("SYMMETRIC", "A") is False
    assert spec.role_allows_memory_focus("DIRECTIONAL", "A") is True


def test_endpoint_setup_rejects_mode_capabilities_outside_active_roles():
    with pytest.raises(ValueError, match="unknown role"):
        EndpointSetupSpec(
            title="INVALID",
            subtitle="INVALID",
            modes=(
                EndpointSetupMode(
                    "ONE",
                    "ONE",
                    active_role_uids=("A",),
                    role_labels=(("B", "B"),),
                ),
            ),
            initial_mode_uid="ONE",
            roles=(
                EndpointSetupRole(
                    "A",
                    "A",
                    ("one",),
                    frozenset({"one"}),
                    "one",
                ),
            ),
        )


def test_new_endpoint_value_cannot_retain_existing_scope_state():
    with pytest.raises(ValueError, match="new endpoint"):
        EndpointSetupValue("C", "new/result", include_descendants=True, create=True)


def test_shared_setup_omits_inactive_result_role_from_directional_draft():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[C" + "\t" * 7 + "\r")
        draft = run_endpoint_setup(
            _meld_shaped_spec(),
            memory_loader=lambda _role_uid, _context_name: (),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert draft is not None
    assert draft.mode_uid == "DIRECTIONAL"
    assert tuple(value.role_uid for value in draft.values) == ("A", "B")
    assert all(value.memory_uid is None for value in draft.values)


def test_shared_setup_confirms_a_new_symmetric_result_name():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t" * 6 + "meld/new-result\r\r")
        draft = run_endpoint_setup(
            _meld_shaped_spec(),
            memory_loader=lambda _role_uid, _context_name: (),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert draft is not None
    assert draft.mode_uid == "SYMMETRIC"
    assert tuple(value.role_uid for value in draft.values) == ("A", "B", "C")
    assert draft.value("C").context_name == "meld/new-result"
    assert draft.value("C").create is True
