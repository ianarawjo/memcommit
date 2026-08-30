"""Lexical per-Context boundaries for recursive Find Redundancies."""

from __future__ import annotations

import copy

from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.python_api import MemCommitClient
from memcommit.adapters.console.entrypoint import app
from memcommit.application.capabilities.reviewing.memory_issue_finding.model import (
    DuplicateReport,
    FindingsError,
)
from memcommit.adapters.agent.quality_find import QualityFindAgentAdapter
from memcommit.persistence.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _lexical_store():
    store = MemoryStore()
    root = ops.init("recursive-dun")
    child = ops.init("recursive-dun/child")
    outside = ops.init("outside-dun")
    for context, content in (
        (root, "root claim"),
        (child, "child claim"),
        (outside, "outside claim"),
    ):
        ops.add(context, content)
        store.save(context)
    store.set_current(root.name)
    return store, root, child, outside


def test_cli_recursive_redundancies_analyzes_each_context_independently(
    isolated_store,
    monkeypatch,
):
    store, root, child, outside = _lexical_store()
    before = {
        name: copy.deepcopy(store.load_direct(name).to_dict())
        for name in store.list_context_names()
    }
    analyzed: list[tuple[str, tuple[str, ...]]] = []

    def analyze(context, _provider_factory, *, context_name_by_uid):
        analyzed.append((context.name, tuple(context_name_by_uid.values())))
        return DuplicateReport(memory_count=1, findings=())

    monkeypatch.setattr(
        "memcommit.application.operations.find_redundancies.application.detect_redundancies",
        analyze,
    )

    result = runner.invoke(app, ["find-redundancies", root.name, "-r"])

    assert result.exit_code == 0, result.output
    assert analyzed == [
        (root.name, (root.name,)),
        (child.name, (child.name,)),
    ]
    assert "2 Contexts" in result.output
    assert f"CONTEXT 1/2 · {root.name}" in result.output
    assert f"CONTEXT 2/2 · {child.name}" in result.output
    assert outside.name not in result.output
    assert {
        name: store.load_direct(name).to_dict() for name in store.list_context_names()
    } == before


def test_cli_recursive_redundancies_publishes_no_report_after_later_failure(
    isolated_store,
    monkeypatch,
):
    _store, root, _child, _outside = _lexical_store()
    calls = 0

    def analyze(context, _provider_factory, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise FindingsError("later frame failed")
        return DuplicateReport(memory_count=len(context.memories), findings=())

    monkeypatch.setattr(
        "memcommit.application.operations.find_redundancies.application.detect_redundancies",
        analyze,
    )

    result = runner.invoke(app, ["find-redundancies", root.name, "--recursive"])

    assert result.exit_code == 1
    assert calls == 2
    assert "later frame failed" in result.stderr
    assert "CONTEXT 1/2" not in result.stdout
    assert "Find Redundancies ·" not in result.stdout


def test_public_and_agent_recursive_redundancies_return_context_frames(
    isolated_store,
):
    store = MemoryStore()
    root = ops.init("recursive-dun-exact")
    child = ops.init("recursive-dun-exact/child")
    for context, content in ((root, "same root"), (child, "same child")):
        ops.add(context, content)
        ops.add(context, content)
        store.save(context)
    store.set_current(root.name)
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("exact-only frames must not connect a provider")
        ),
    )

    found = client.find_redundancies(
        (root.name,),
        include_descendants=True,
    )

    assert found.include_descendants is True
    assert found.context_names == (root.name, child.name)
    assert found.memory_count == 4
    assert len(found.evidence) == 2
    assert [frame.context_name for frame in found.contexts] == [
        root.name,
        child.name,
    ]
    assert all(len(frame.evidence) == 1 for frame in found.contexts)
    assert all(
        len({source.display_name for source in handoff.sources}) == 1
        for handoff in found.evidence
    )

    agent = QualityFindAgentAdapter(client).invoke(
        {
            "version": 1,
            "kind": "redundancies",
            "context_names": [root.name],
            "include_descendants": True,
        }
    )
    assert agent["ok"] is True
    assert agent["result"]["include_descendants"] is True
    assert [frame["context_name"] for frame in agent["result"]["contexts"]] == [
        root.name,
        child.name,
    ]


def test_recursive_redundancies_rejects_multiple_roots_and_mixed_presets(
    isolated_store,
):
    _store, root, _child, outside = _lexical_store()
    client = MemCommitClient(root=isolated_store)

    agent = QualityFindAgentAdapter(client).invoke(
        {
            "version": 1,
            "kind": "redundancies",
            "context_names": [root.name, outside.name],
            "include_descendants": True,
        }
    )
    cli = runner.invoke(app, ["find-redundancies", root.name, "-d", "-r"])

    assert agent["ok"] is False
    assert agent["error"]["code"] == "invalid_request"
    assert cli.exit_code == 2
    assert "either --direct/-d or --recursive/-r" in cli.stderr
