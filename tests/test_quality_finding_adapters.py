"""Public, CLI, and agent parity for quality finding handoffs."""

from __future__ import annotations

import json
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.python_api import MemCommitClient, SemanticConflictError
from memcommit.adapters.console.entrypoint import app
from memcommit.core.context import MemoryRef
from memcommit.adapters.agent.quality_find import QualityFindAgentAdapter
from memcommit.adapters.agent.resolve import (
    RESOLVE_AGENT_CONTRACT_VERSION,
    ResolveAgentAdapter,
)
from memcommit.persistence.store import MemoryStore


QUALITY_MARKER = "QUALITY FIND PAYLOAD:\n"
FIT_MARKER = "FIT PROPOSITION PAYLOAD:\n"
runner = CliRunner(mix_stderr=False)


class FindingResolveProvider:
    def __init__(self) -> None:
        self.operations: list[str] = []

    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        self.operations.append(operation)
        if operation == "find_conflicts":
            payload = json.loads(prompt.split(QUALITY_MARKER, 1)[1])
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
        if operation == "fit_propositions":
            payload = json.loads(prompt.split(FIT_MARKER, 1)[1])
            judgments = []
            for question in payload["questions"]:
                aliases = [
                    item["proposition_id"]
                    for item in (
                        *question["background"],
                        *question["propositions"],
                    )
                ]
                judgments.append(
                    {
                        "question_id": question["question_id"],
                        "verdict": "YES",
                        "reason": "The complete frame is already compatible.",
                        "considered_proposition_ids": aliases,
                        "material_proposition_ids": [],
                        "consistent_reading": "",
                        "inconsistent_reading": "",
                    }
                )
            return json.dumps(
                {"overview": "Complete Fit coverage.", "judgments": judgments}
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


def test_public_client_returns_handoff_and_resolves_the_same_typed_receipt(
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
    assert analysis.status == "ALREADY_FIT"
    assert provider.operations == ["find_conflicts", "fit_propositions"]


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
    assert resolved["result"]["status"] == "ALREADY_FIT"


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
    assert resolved.output == (f"RESOLVE · {context.name}\nFIT · YES · NO CHANGE\n")
