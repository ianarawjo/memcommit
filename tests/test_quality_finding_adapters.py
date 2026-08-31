"""Public, CLI, and agent parity for quality finding handoffs."""

from __future__ import annotations

import json
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.python_api import (
    MemCommitClient,
    ResolveDecisionInput,
    SemanticConflictError,
)
from memcommit.adapters.console.entrypoint import app
from memcommit.core.context import Memory, MemoryRef
from memcommit.adapters.agent.quality_find import QualityFindAgentAdapter
from memcommit.adapters.agent.resolve import (
    RESOLVE_AGENT_CONTRACT_VERSION,
    ResolveAgentAdapter,
)
from memcommit.persistence.store import MemoryStore
from memcommit.providers.types import ProviderIdentity


QUALITY_MARKER = "QUALITY FIND PAYLOAD:\n"
RESOLVE_MARKER = "RESOLVE AUDIT PAYLOAD:\n"
runner = CliRunner(mix_stderr=False)


class FindingResolveProvider:
    def __init__(self) -> None:
        self.operations: list[str] = []
        self.identity = ProviderIdentity(provider="test", model="resolve-model")

    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        self.operations.append(operation)
        if operation in {"find_duplicates", "find_ambiguities"}:
            return json.dumps({"findings": []})
        if operation == "find_conflicts":
            payload = json.loads(prompt.split(QUALITY_MARKER, 1)[1])
            if any(
                "different schedule" in memory["content"]
                for memory in payload["memories"]
            ):
                return json.dumps({"findings": []})
            return json.dumps(
                {
                    "findings": [
                        {
                            "pair_id": payload["pairs"][0]["pair_id"],
                            "conflict": "YES",
                            "reason": "The same entrance has incompatible hours.",
                            "question": "Which opening time is authoritative?",
                        }
                    ]
                }
            )
        if operation == "update planning":
            payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
            source_ids = [
                memory["source_id"] for memory in payload["source"]["memories"]
            ]
            target = next(
                memory
                for memory in payload["target"]["memories"]
                if memory["content"]
                == "The main entrance remains closed until 9:00."
            )
            return json.dumps(
                {
                    "edits": [
                        {
                            "target_id": target["target_id"],
                            "new_content": (
                                "On a different schedule, the main entrance "
                                "remains closed until 9:00."
                            ),
                            "source_ids": source_ids,
                            "reason": "Represent the confirmed schedule distinction.",
                        }
                    ],
                    "additions": [],
                    "removals": [],
                }
            )
        if operation == "resolve_audit_directions":
            payload = json.loads(prompt.split(RESOLVE_MARKER, 1)[1])
            return json.dumps(
                {
                    "directions": [
                        {
                            "item_id": item["item_id"],
                            "direction": (
                                "The opening times apply to different schedules."
                            ),
                        }
                        for item in payload["audit"]["items"]
                    ]
                }
            )
        raise AssertionError(operation)


class CountingFactory:
    def __init__(self, provider: FindingResolveProvider) -> None:
        self.provider = provider
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.provider


def _stored_context():
    store = MemoryStore()
    context = ops.init("quality/source")
    ops.add(context, "The main entrance opens at 8:00.")
    ops.add(context, "The main entrance remains closed until 9:00.")
    store.create_context(context)
    store.set_current(context.name)
    return store, context


def test_public_client_returns_handoff_and_the_same_typed_resolve_input(
    isolated_store,
):
    _store, context = _stored_context()
    provider = FindingResolveProvider()
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=lambda: provider,
    )

    found = client.find_conflicts((context.name,))
    analysis = client.resolve_conflict_finding(found.handoffs[0])

    assert found.kind == "conflicts"
    assert found.context_names == (context.name,)
    assert found.pair_count == 1
    assert found.handoffs[0].route == "RESOLVE"
    assert analysis.status == "NEEDS_INPUT"
    assert len(analysis.issues) == 1
    assert analysis.issues[0].proposed_direction == (
        "The opening times apply to different schedules."
    )
    assert provider.operations == [
        "find_conflicts",
        "find_duplicates",
        "find_ambiguities",
        "find_conflicts",
        "resolve_audit_directions",
    ]


def test_public_handoff_staleness_fails_before_a_second_provider_connection(
    isolated_store,
):
    store, context = _stored_context()
    provider = FindingResolveProvider()
    factory = CountingFactory(provider)
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=factory,
    )
    handoff = client.find_conflicts((context.name,)).handoffs[0]
    changed = store.load_for_update(context.name)
    ops.add(changed, "The entrance uses holiday hours on statutory holidays.")
    store.save(changed)

    with pytest.raises(SemanticConflictError, match="finding source"):
        client.resolve_conflict_finding(handoff)

    assert factory.calls == 1


def test_public_resolve_applies_decisions_through_update_and_post_image_check(
    isolated_store,
):
    store, context = _stored_context()
    provider = FindingResolveProvider()
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=lambda: provider,
    )
    analysis = client.resolve_context(context.name)

    receipt = client.apply_resolve(
        analysis,
        decisions=(ResolveDecisionInput(analysis.issues[0].uid, "CONFIRM"),),
    )

    assert receipt.plan_uid
    assert receipt.checkpoint_uid
    assert len(receipt.updated_uids) == 1
    assert receipt.unresolved_issue_uids == ()
    updated = store.load_direct(context.name)
    assert any(
        "different schedule" in memory.content
        for memory in updated.iter_items()
        if isinstance(memory, Memory)
    )
    assert provider.operations == [
        "find_duplicates",
        "find_ambiguities",
        "find_conflicts",
        "resolve_audit_directions",
        "update planning",
        "find_duplicates",
        "find_ambiguities",
        "find_conflicts",
    ]


def test_public_find_redundancies_includes_exact_dup_without_provider(
    isolated_store,
):
    store = MemoryStore()
    context = ops.init("quality/exact-inclusive")
    first = ops.add(context, "same")
    second = ops.add(context, "same")
    store.create_context(context)
    store.set_current(context.name)
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("an exact-only DUN frame must not connect a provider")
        ),
    )

    found = client.find_redundancies((context.name,))

    assert found.kind == "redundancies"
    assert found.memory_count == 2
    assert len(found.evidence) == 1
    assert found.evidence[0].classification == "EXACT"
    assert found.evidence[0].memory_uids == (first.uid, second.uid)

    agent_result = QualityFindAgentAdapter(client).invoke(
        {
            "version": 1,
            "kind": "redundancies",
            "context_names": [context.name],
        }
    )
    agent_evidence = agent_result["result"]["evidence"][0]
    assert agent_evidence["contract"] == "redundancy-evidence-v2"
    assert agent_evidence["classification"] == "EXACT"


def test_public_and_agent_redundancy_results_include_exact_embed_groups(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("quality/embed-source")
    memory = ops.add(source, "live source")
    target = ops.init("quality/embed-target")
    ops.add(target, "one direct candidate")
    refs = tuple(
        MemoryRef(
            uid=str(uuid.uuid4()),
            target_context_uid=source.uid,
            target_context_name=source.name,
            target_memory_uid=memory.uid,
            target=memory,
        )
        for _ in range(2)
    )
    for reference in refs:
        target.add(reference)
    store.save(source)
    store.save(target)
    store.set_current(target.name)
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("one direct Memory must not connect a provider")
        ),
    )

    found = client.find_redundancies((target.name,))

    assert found.evidence == ()
    assert len(found.exact_item_groups) == 1
    assert found.exact_item_groups[0].item_kind == "MEMORY_EMBED"
    assert found.exact_item_groups[0].survivor_uid == refs[0].uid
    assert found.exact_item_groups[0].absorbed_uids == (refs[1].uid,)

    agent_result = QualityFindAgentAdapter(client).invoke(
        {
            "version": 1,
            "kind": "redundancies",
            "context_names": [target.name],
        }
    )
    exact = agent_result["result"]["exact_item_groups"][0]
    assert exact["item_kind"] == "MEMORY_EMBED"
    assert exact["survivor_uid"] == refs[0].uid
    assert exact["absorbed_uids"] == [refs[1].uid]


def test_agent_finder_output_enters_resolve_without_adapter_reconstruction(
    isolated_store,
):
    _store, context = _stored_context()
    provider = FindingResolveProvider()
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=lambda: provider,
    )

    found = QualityFindAgentAdapter(client).invoke(
        {
            "version": 1,
            "kind": "conflicts",
            "context_names": [context.name],
        }
    )
    handoff = found["result"]["evidence"][0]
    resolved = ResolveAgentAdapter(client).invoke(
        {
            "version": RESOLVE_AGENT_CONTRACT_VERSION,
            "kind": "analyze",
            "finding_handoff": handoff,
        }
    )

    assert found["ok"] is True
    assert found["result"]["effect"] == "NONE"
    assert resolved["ok"] is True
    assert resolved["result"]["status"] == "NEEDS_INPUT"
    assert len(resolved["result"]["issues"]) == 1


def test_agent_resolve_rejects_tampered_handoff_identity(isolated_store):
    _store, context = _stored_context()
    provider = FindingResolveProvider()
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=lambda: provider,
    )
    found = QualityFindAgentAdapter(client).invoke(
        {
            "version": 1,
            "kind": "conflicts",
            "context_names": [context.name],
        }
    )
    handoff = found["result"]["evidence"][0]
    handoff["reason"] = "Tampered after finder output."

    resolved = ResolveAgentAdapter(client).invoke(
        {
            "version": RESOLVE_AGENT_CONTRACT_VERSION,
            "kind": "analyze",
            "finding_handoff": handoff,
        }
    )

    assert resolved["ok"] is False
    assert resolved["error"]["code"] == "invalid_request"
    assert provider.operations == ["find_conflicts"]


def test_agent_resolve_applies_the_cached_revision_with_typed_decisions(
    isolated_store,
):
    _store, context = _stored_context()
    provider = FindingResolveProvider()
    adapter = ResolveAgentAdapter(
        MemCommitClient(
            root=isolated_store,
            semantic_provider_factory=lambda: provider,
        )
    )
    analyzed = adapter.invoke(
        {
            "version": RESOLVE_AGENT_CONTRACT_VERSION,
            "kind": "analyze",
            "context_name": context.name,
        }
    )
    issue = analyzed["result"]["issues"][0]

    applied = adapter.invoke(
        {
            "version": RESOLVE_AGENT_CONTRACT_VERSION,
            "kind": "apply",
            "context_name": context.name,
            "expected_revision": analyzed["result"]["revision"],
            "decisions": [
                {
                    "issue_uid": issue["uid"],
                    "kind": "CONFIRM",
                }
            ],
        }
    )

    assert applied["ok"] is True
    assert applied["result"]["effect"] == "CHECKPOINT"
    assert len(applied["result"]["updated_uids"]) == 1


def test_cli_json_handoff_round_trips_into_plain_resolve(
    isolated_store,
    monkeypatch,
):
    _store, context = _stored_context()
    provider = FindingResolveProvider()
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.find_conflicts.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.resolve.command.connect_semantic_provider",
        lambda: provider,
    )

    found = runner.invoke(
        app,
        ["find-conflicts", "--context", context.name, "--handoff-json"],
    )
    assert found.exit_code == 0, found.output
    receipt = found.output.strip()
    assert json.loads(receipt)["route"] == "RESOLVE"

    resolved = runner.invoke(
        app,
        ["resolve", "--finding-handoff", receipt],
    )
    assert resolved.exit_code == 0, resolved.output
    assert f"RESOLVE · {context.name}\n" in resolved.output
    assert "NEEDS DECISIONS · 1\n" in resolved.output
    assert "DIRECTION · The opening times apply to different schedules.\n" in (
        resolved.output
    )
    assert "DECISIONS REQUIRED" in resolved.output
