"""Audit's projection through the shared endpoint setup component."""

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
import pytest

import memcommit.adapters.console.commands.quality_resolution.diagnose.audit.command as audit_command
import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.commands.quality_resolution.diagnose.audit.endpoint_setup import (
    audit_endpoint_setup_spec,
    choose_audit_setup,
)
from memcommit.persistence.store import MemoryStore


def test_audit_setup_spec_freezes_one_direct_readable_source() -> None:
    spec = audit_endpoint_setup_spec(
        ("audit/current", "audit/peer"),
        current="audit/current",
    )

    assert spec.initial_mode_uid == "AUDIT"
    assert tuple(mode.uid for mode in spec.modes) == ("AUDIT",)
    assert tuple(role.uid for role in spec.roles) == ("SOURCE",)
    assert spec.roles[0].selected_name == "audit/current"
    assert spec.roles[0].selectable_names == frozenset(
        {"audit/current", "audit/peer"}
    )


def test_audit_setup_returns_the_visible_selected_source() -> None:
    with create_pipe_input() as pipe_input:
        # SOURCE starts focused. Choose the next row, then continue.
        pipe_input.send_text("\x1b[B\r\t\r")
        selected = choose_audit_setup(
            ("audit/current", "audit/peer"),
            current="audit/current",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == "audit/peer"


def test_audit_setup_cancel_returns_no_source() -> None:
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        selected = choose_audit_setup(
            ("audit/current",),
            current="audit/current",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is None


def test_audit_setup_rejects_a_current_context_outside_the_catalog() -> None:
    with pytest.raises(ValueError, match="outside the catalog"):
        audit_endpoint_setup_spec(("audit/source",), current="missing")


def test_audit_command_loads_the_source_selected_by_the_shared_setup(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    current = ops.init("audit/current")
    peer = ops.init("audit/peer")
    ops.add(peer, "Peer evidence.")
    store.create_context(current)
    store.create_context(peer)
    store.set_current(current.name)
    observed: dict[str, object] = {}

    def choose(names, *, current, annotations):
        observed.update(
            names=tuple(names),
            current=current,
            annotations=dict(annotations),
        )
        return peer.name

    monkeypatch.setattr(audit_command, "choose_audit_setup", choose)

    access, selected = audit_command._interactive_source(
        store,
        current_name=current.name,
    )

    assert observed["names"] == (current.name, peer.name)
    assert observed["current"] == current.name
    assert access.display_name == peer.name
    assert selected.name == peer.name
