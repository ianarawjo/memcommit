"""Contracts for Atomize's typed saved/prepared/provider open boundary."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

import memcommit.application.capabilities.ops as ops
from memcommit.application.operations.atomize.domain import (
    AtomizeImpactError,
    create_atomize_analysis,
    impact_atomize,
)
from memcommit.application.operations.atomize.analysis_application import (
    AtomizeAnalysisOpenRequest,
)
from memcommit.application.operations.atomize.analysis_runtime import (
    execute_atomize_analysis_open,
)
from memcommit.core.context import Memory
from memcommit.persistence.store import MemoryStore
from memcommit.study_scenarios.legacy.prewarm.atomize import AtomizePrewarmMatch


_PAYLOAD_MARKER = "ATOMIZE IMPACT PAYLOAD:\n"


class _Provider:
    def __init__(self):
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "impact_atomize"
        assert output_schema is not None
        self.calls += 1
        payload = json.loads(prompt.split(_PAYLOAD_MARKER, 1)[1])
        ids = [item["candidate_id"] for item in payload["memories"]]
        return json.dumps(
            {
                "overview": {
                    "understood": {
                        "text": "Each supplied Memory states one fact.",
                        "source_ids": ids,
                    },
                    "changed": {
                        "text": "No Memory needs to be split.",
                        "source_ids": ids,
                    },
                    "unresolved": {"text": "", "source_ids": []},
                },
                "items": [
                    {
                        "candidate_id": uid,
                        "classification": "ATOMIC",
                        "reason_codes": ["A01_ONE_FOCUS"],
                        "children": [],
                        "reason": "The source has one revisable focus.",
                    }
                    for uid in ids
                ],
                "quality_issues": [],
            }
        )


def _context(store: MemoryStore):
    context = ops.init("atomize/analysis-boundary")
    ops.add(context, "The library entrance closes at five.")
    store.save(context)
    return context


def test_provider_create_then_saved_resume_does_not_reconnect(isolated_store):
    store = MemoryStore()
    context = _context(store)
    provider = _Provider()
    request = AtomizeAnalysisOpenRequest(context=context)

    created = execute_atomize_analysis_open(
        request,
        store=store,
        provider_factory=lambda: provider,
    )
    resumed = execute_atomize_analysis_open(
        request,
        store=store,
        provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("saved Atomize resume opened a provider")
        ),
    )

    assert created.origin == "PROVIDER"
    assert created.created_analysis is True
    assert resumed.origin == "SAVED"
    assert resumed.created_analysis is False
    assert resumed.analysis.uid == created.analysis.uid
    assert resumed.review_record.uid == created.review_record.uid
    assert provider.calls == 1


def test_runtime_looks_up_hidden_prepared_analysis_before_provider(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context = _context(store)
    prepared = create_atomize_analysis(
        context,
        impact_atomize(context, lambda: _Provider()),
    )
    match = AtomizePrewarmMatch(
        entry_key="capture/atomize",
        analysis=prepared,
        output_context_name="atomize/prepared-output",
    )
    monkeypatch.setattr(
        "memcommit.application.operations.atomize.analysis_runtime.find_declared_atomize_prewarm",
        lambda *, store, context: match,
    )

    opened = execute_atomize_analysis_open(
        AtomizeAnalysisOpenRequest(
            context=context,
            allow_prepared=True,
        ),
        store=store,
        provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("exact prewarm opened a provider")
        ),
    )

    assert opened.origin == "EXACT_PREWARM"
    assert opened.materialized_prepared is True
    assert opened.analysis == prepared
    assert opened.review_record.output_context_name == "atomize/prepared-output"


def test_disallowed_prepared_lookup_falls_through_to_provider(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context = _context(store)
    monkeypatch.setattr(
        "memcommit.application.operations.atomize.analysis_runtime.find_declared_atomize_prewarm",
        lambda **_kwargs: pytest.fail("disallowed prepared lookup was attempted"),
    )
    prepared = create_atomize_analysis(
        context,
        impact_atomize(context, lambda: _Provider()),
    )
    provider = _Provider()

    opened = execute_atomize_analysis_open(
        AtomizeAnalysisOpenRequest(
            context=context,
            allow_prepared=False,
        ),
        store=store,
        provider_factory=lambda: provider,
        prepared_analysis_override=prepared,
    )

    assert opened.origin == "PROVIDER"
    assert opened.analysis.uid != prepared.uid
    assert provider.calls == 1


def test_stale_saved_analysis_fails_before_provider_without_refresh(
    isolated_store,
):
    store = MemoryStore()
    context = _context(store)
    first = execute_atomize_analysis_open(
        AtomizeAnalysisOpenRequest(context=context),
        store=store,
        provider_factory=_Provider,
    )
    changed = store.load_direct(context.name)
    memory = next(item for item in changed.iter_items() if isinstance(item, Memory))
    changed.replace(Memory(uid=memory.uid, content="Changed closing time."))
    store.save(changed)

    with pytest.raises(AtomizeImpactError, match="stale"):
        execute_atomize_analysis_open(
            AtomizeAnalysisOpenRequest(context=store.load_direct(context.name)),
            store=store,
            provider_factory=lambda: (_ for _ in ()).throw(
                AssertionError("stale resume opened a provider")
            ),
        )

    retained = store.load_atomize_analysis(context.uid)
    assert retained is not None and retained.uid == first.analysis.uid


def test_refresh_calls_provider_and_preserves_durable_output_plan(isolated_store):
    store = MemoryStore()
    context = _context(store)
    first = execute_atomize_analysis_open(
        AtomizeAnalysisOpenRequest(
            context=context,
            output_context_name="atomize/planned-output",
        ),
        store=store,
        provider_factory=_Provider,
    )
    provider = _Provider()

    refreshed = execute_atomize_analysis_open(
        AtomizeAnalysisOpenRequest(
            context=context,
            refresh=True,
        ),
        store=store,
        provider_factory=lambda: provider,
    )

    assert refreshed.origin == "PROVIDER"
    assert refreshed.analysis.uid != first.analysis.uid
    assert refreshed.review_record.output_context_name == "atomize/planned-output"
    assert provider.calls == 1


def test_analysis_application_and_runtime_import_no_terminal_adapters():
    root = Path(__file__).resolve().parents[1]
    forbidden = ("typer", "prompt_toolkit", "memcommit.adapters.console.commands")
    for relative in (
        "src/memcommit/application/operations/atomize/analysis_application.py",
        "src/memcommit/application/operations/atomize/analysis_runtime.py",
    ):
        tree = ast.parse((root / relative).read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imports.append(node.module)
        assert not [
            name
            for name in imports
            if any(name == item or name.startswith(f"{item}.") for item in forbidden)
        ]
