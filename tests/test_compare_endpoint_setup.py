"""Contracts for Compare's shared Endpoint Setup adapter."""

from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
import pytest

import memcommit.commands.compare_setup as compare_setup_command
import memcommit.ops as ops
from memcommit.interfaces.tui.components.endpoint_setup import EndpointSetupMemory
from memcommit.interfaces.tui.operations.compare import (
    CompareEndpointSelection,
    CompareTuiSetup,
    choose_compare_endpoint_setup,
    compare_endpoint_setup_spec,
)


REFERENCE_UID = "11111111-1111-4111-8111-111111111111"
PEER_UID = "22222222-2222-4222-8222-222222222222"


def _setup() -> CompareTuiSetup:
    return CompareTuiSetup(
        names=("reference", "peer"),
        reference_name="reference",
        peer_name="peer",
        current_context="reference",
    )


def _load(role_uid: str, context_name: str):
    uid = REFERENCE_UID if context_name == "reference" else PEER_UID
    return (
        EndpointSetupMemory(
            context_name,
            uid,
            f"{role_uid} exact Memory in {context_name}.",
        ),
    )


def test_compare_setup_projects_two_independent_shared_endpoint_roles() -> None:
    spec = compare_endpoint_setup_spec(_setup())

    assert spec.initial_mode_uid == "COMPARE"
    assert tuple(role.uid for role in spec.roles) == ("A", "B")
    assert all(role.allow_descendants for role in spec.roles)
    assert all(role.allow_memory_focus for role in spec.roles)
    assert spec.roles[0].selected_name == "reference"
    assert spec.roles[1].selected_name == "peer"


def test_compare_setup_returns_unchanged_whole_exact_defaults() -> None:
    with create_pipe_input() as pipe_input:
        # A Context -> Range -> Memory -> B Context -> Range -> Memory -> Run.
        pipe_input.send_text("\t\t\t\t\t\t\r")
        selected = choose_compare_endpoint_setup(
            _setup(),
            memory_loader=_load,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == CompareEndpointSelection("reference", "peer")


def test_compare_setup_keeps_a_memory_and_b_descendants_independent() -> None:
    with create_pipe_input() as pipe_input:
        # Select A's Memory, leave B's Context unchanged, broaden only B, and
        # cross its disabled Memory surface to the reviewed action.
        pipe_input.send_text("\t\t\x1b[B\r\t\t\x1b[C\t\t\r")
        selected = choose_compare_endpoint_setup(
            _setup(),
            memory_loader=_load,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == CompareEndpointSelection(
        "reference",
        "peer",
        peer_descendants=True,
        reference_memory_uid=REFERENCE_UID,
    )


def test_compare_setup_can_focus_one_exact_memory_per_side() -> None:
    with create_pipe_input() as pipe_input:
        pipe_input.send_text(
            "\t\t\x1b[B\r\t\t\t\x1b[B\r\t\r"
        )
        selected = choose_compare_endpoint_setup(
            _setup(),
            memory_loader=_load,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == CompareEndpointSelection(
        "reference",
        "peer",
        reference_memory_uid=REFERENCE_UID,
        peer_memory_uid=PEER_UID,
    )


def test_compare_setup_rejects_identical_or_unknown_defaults() -> None:
    with pytest.raises(ValueError, match="distinct available"):
        CompareTuiSetup(
            names=("reference", "peer"),
            reference_name="reference",
            peer_name="reference",
        )
    with pytest.raises(ValueError, match="distinct available"):
        CompareTuiSetup(
            names=("reference", "peer"),
            reference_name="reference",
            peer_name="missing",
        )


def test_compare_command_composition_preserves_a_frozen_readable_catalog(
    monkeypatch,
) -> None:
    reference = ops.init("reference")
    ops.add(reference, "Reference Memory.")
    granted_peer = ops.init("granted/peer")
    ops.add(granted_peer, "Granted peer Memory.")
    contexts = {
        reference.name: reference,
        granted_peer.name: granted_peer,
    }
    loaded: list[str] = []

    class Store:
        def list_context_names(self):
            return [reference.name]

        def current_context_name(self):
            return reference.name

    class Access:
        def __init__(self, *, granted: bool):
            self.is_granted = granted

    class Catalog:
        def list_context_names(self):
            return [reference.name, granted_peer.name]

        def access_for(self, name: str):
            return Access(granted=name == granted_peer.name)

        def load(self, name: str):
            loaded.append(name)
            return contexts[name]

    monkeypatch.setattr(
        compare_setup_command,
        "freeze_profile_readable_context_catalog",
        lambda *_args, **_kwargs: Catalog(),
    )
    monkeypatch.setattr(
        compare_setup_command,
        "context_access_display_facts",
        lambda _access: "READ GRANT",
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\t\x1b[B\r\t\t\t\x1b[B\r\t\r")
        receipt = compare_setup_command.choose_compare_setup(
            Store(),  # type: ignore[arg-type]
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt == compare_setup_command.CompareSetupReceipt(
        reference.name,
        granted_peer.name,
        reference_memory_uid=next(iter(reference.memories)),
        compared_memory_uid=next(iter(granted_peer.memories)),
    )
    assert loaded == [reference.name, granted_peer.name]
