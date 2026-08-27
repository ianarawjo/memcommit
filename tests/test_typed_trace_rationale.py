"""Typed Trace/Rationale coverage for references and granted current views."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from memcommit.adapters.console.entrypoint import app
from memcommit.core.context import Memory, MemoryRef
from memcommit.application.operations.rationale.rules import (
    RationaleLimitUnit,
    RationaleNarrativeStatus,
)
from memcommit.application.operations.rationale.semantic import RationaleNarrativeProjection
from memcommit.persistence.store import MemoryStore


runner = CliRunner()


def invoke(*args: str):
    return runner.invoke(app, list(args))


def _memory(store: MemoryStore, context_name: str) -> Memory:
    return next(
        item
        for item in store.load_direct(context_name).iter_items()
        if isinstance(item, Memory)
    )


def _reference(store: MemoryStore, context_name: str) -> MemoryRef:
    return next(
        item
        for item in store.load_direct(context_name).iter_items()
        if isinstance(item, MemoryRef)
    )


def test_bare_reference_uid_traces_occurrence_and_live_target_separately(
    isolated_store,
):
    assert invoke("init", "source").exit_code == 0
    assert invoke("add", "version one").exit_code == 0
    store = MemoryStore()
    memory = _memory(store, "source")
    assert invoke("init", "parent").exit_code == 0
    assert invoke("embed", memory.uid, "--from", "source").exit_code == 0
    reference = _reference(store, "parent")
    assert invoke("edit", f"source:{memory.uid}", "version two").exit_code == 0

    result = invoke("trace", reference.uid[:8], "--plain")

    assert result.exit_code == 0, result.output + result.stderr
    assert f"[REFERENCE {reference.uid[:8]}] · LIVE" in result.output
    assert "REFERENCE OCCURRENCE" in result.output
    assert "[embed] [CHECKPOINT " in result.output
    assert f"TARGET · source:[{memory.uid[:8]}]" in result.output
    assert "TARGET MEMORY" in result.output
    assert "version one" in result.output
    assert "version two" in result.output


def test_reference_trace_json_keeps_pointer_and_target_identity_distinct(
    isolated_store,
):
    assert invoke("init", "source").exit_code == 0
    assert invoke("add", "source value").exit_code == 0
    store = MemoryStore()
    memory = _memory(store, "source")
    assert invoke("init", "parent").exit_code == 0
    assert invoke("embed", f"source:{memory.uid}").exit_code == 0
    reference = _reference(store, "parent")

    result = invoke("trace", f"parent:{reference.uid}", "--json")

    assert result.exit_code == 0, result.output + result.stderr
    payload = json.loads(result.stdout)
    assert payload["kind"] == "memory_reference"
    assert payload["selected_uid"] == reference.uid
    assert payload["reference"]["target_memory_uid"] == memory.uid
    assert payload["target_trace"]["selected_uid"] == memory.uid
    assert payload["events"][0]["kind"] == "CREATED"


def test_removed_reference_remains_traceable_as_historical_occurrence(
    isolated_store,
):
    assert invoke("init", "source").exit_code == 0
    assert invoke("add", "source value").exit_code == 0
    store = MemoryStore()
    memory = _memory(store, "source")
    assert invoke("init", "parent").exit_code == 0
    assert invoke("embed", f"source:{memory.uid}").exit_code == 0
    reference = _reference(store, "parent")
    assert invoke("remove", reference.uid[:8]).exit_code == 0

    result = invoke("trace", f"parent:{reference.uid}", "--json")

    assert result.exit_code == 0, result.output + result.stderr
    payload = json.loads(result.stdout)
    assert payload["current"] is False
    assert [event["kind"] for event in payload["events"]] == [
        "CREATED",
        "REMOVED",
    ]
    assert payload["target_trace"]["selected_uid"] == memory.uid


def test_reference_rationale_explains_relation_then_target_provenance(
    isolated_store,
    monkeypatch,
):
    assert invoke("init", "source").exit_code == 0
    assert invoke("add", "source value").exit_code == 0
    store = MemoryStore()
    memory = _memory(store, "source")
    assert invoke("init", "parent").exit_code == 0
    assert invoke("embed", memory.uid, "--from", "source").exit_code == 0
    reference = _reference(store, "parent")
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.rationale.command.connect_semantic_provider",
        lambda: object(),
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.rationale.command.synthesize_rationale_provenance",
        lambda *args, **kwargs: RationaleNarrativeProjection(
            status=RationaleNarrativeStatus.AVAILABLE,
            text="The target was added directly as retained source evidence.",
            limit=40,
            unit=RationaleLimitUnit.WORDS,
            length=9,
        ),
    )

    result = invoke("rationale", reference.uid[:8])

    assert result.exit_code == 0, result.output + result.stderr
    assert "REFERENCE\n  LIVE EMBED → source:" in result.output
    assert "RELATION PROVENANCE" in result.output
    assert "pointer and target keep separate identities" in result.output
    assert "TARGET MEMORY\n  source value" in result.output
    assert "TARGET PROVENANCE" in result.output
    assert "added directly as retained source evidence" in result.output


def test_snapshot_reference_rationale_never_opens_live_target_provenance(
    isolated_store,
    monkeypatch,
):
    assert invoke("init", "source").exit_code == 0
    assert invoke("add", "captured value").exit_code == 0
    store = MemoryStore()
    memory = _memory(store, "source")
    assert invoke("init", "parent").exit_code == 0
    assert (
        invoke("reference", f"source:{memory.uid}", "--into", "parent").exit_code == 0
    )
    reference = _reference(store, "parent")

    def forbidden():
        raise AssertionError("snapshot rationale connected a provider")

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.rationale.command.connect_semantic_provider",
        forbidden,
    )
    assert invoke("edit", f"source:{memory.uid}", "later source value").exit_code == 0

    result = invoke("rationale", reference.uid[:8])

    assert result.exit_code == 0, result.output + result.stderr
    assert "IMMUTABLE SNAPSHOT" in result.output
    assert "captured value" in result.output
    assert "later source value" not in result.output
    assert "snapshot fixed at reference time" in result.output


def test_duplicate_bare_report_uid_lists_every_typed_owner(isolated_store):
    shared_uid = "aaaaaaaa-0000-4000-8000-000000000000"
    store = MemoryStore()
    from memcommit.application import ops

    first = ops.init("first")
    first.add(Memory(uid=shared_uid, content="first copy"))
    second = ops.init("second")
    second.add(Memory(uid=shared_uid, content="second copy"))
    store.save(first)
    store.save(second)

    result = invoke("trace", shared_uid[:8])

    assert result.exit_code == 1
    assert f"first:{shared_uid} (MEMORY)" in result.output
    assert f"second:{shared_uid} (MEMORY)" in result.output
    assert (
        "To select one, rerun with its CONTEXT:UID value shown above."
        in result.output
    )
