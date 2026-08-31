"""Stable Python contract for structural Atomize analysis and Apply as-is."""

from __future__ import annotations

import ast
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import memcommit.application.capabilities.ops as ops
from memcommit import (
    AtomizeAnalysisResult,
    AtomizeConflictError,
    AtomizeContextError,
    AtomizeInputError,
    AtomizeProviderFailure,
    AtomizePlanUpdateResult,
    AtomizeSaveAsApplyResult,
    AtomizeStructuralApplyResult,
    MemCommitClient,
)
from memcommit.application.operations.semantic_updates.derive.atomize.domain import (
    create_atomize_analysis,
    impact_atomize,
)
from memcommit.application.operations.semantic_updates.derive.atomize.runtime import (
    capture_atomize_execution_snapshot,
)
from memcommit.adapters.python_api.errors import AtomizeExecutionError
from memcommit.core.context import Memory
from memcommit.persistence.store import MemoryStore
from memcommit.study_scenarios.legacy.prewarm.atomize import AtomizePrewarmMatch


_PAYLOAD_MARKER = "ATOMIZE IMPACT PAYLOAD:\n"


class _Provider:
    def __init__(
        self,
        *,
        composite: bool = False,
        uncertain: bool = False,
        hook=None,
    ):
        self.composite = composite
        self.uncertain = uncertain
        self.calls = 0
        self.payloads = []
        self.hook = hook

    def complete(self, prompt, *, operation, output_schema=None):
        if operation == "find_duplicates":
            assert output_schema is not None
            self.calls += 1
            return json.dumps({"findings": []})
        assert operation == "impact_atomize"
        assert output_schema is not None
        self.calls += 1
        payload = json.loads(prompt.split(_PAYLOAD_MARKER, 1)[1])
        self.payloads.append(payload)
        validating = payload.get("phase") == "normal_form_validation"
        if self.hook is not None and not validating:
            self.hook()
        records = []
        for item in payload["memories"]:
            content = item["content"]
            if self.uncertain and not validating:
                records.append(
                    {
                        "candidate_id": item["candidate_id"],
                        "classification": "UNCERTAIN",
                        "reason_codes": ["A06_NO_HIDDEN_CONTEXT"],
                        "children": [],
                        "reason": "The source needs context before splitting.",
                    }
                )
            elif self.composite and not validating:
                left, right = content.split(" and ", 1)
                records.append(
                    {
                        "candidate_id": item["candidate_id"],
                        "classification": "COMPOSITE",
                        "reason_codes": ["A01_ONE_FOCUS"],
                        "children": [
                            {"content": left, "source_spans": [left]},
                            {"content": right, "source_spans": [right]},
                        ],
                        "reason": "The source contains two independent facts.",
                    }
                )
            else:
                records.append(
                    {
                        "candidate_id": item["candidate_id"],
                        "classification": "ATOMIC",
                        "reason_codes": ["A01_ONE_FOCUS"],
                        "children": [],
                        "reason": "The source has one revisable focus.",
                    }
                )
        ids = [item["candidate_id"] for item in payload["memories"]]
        return json.dumps(
            {
                "overview": {
                    "understood": {
                        "text": "The supplied Memories describe closing times.",
                        "source_ids": ids,
                    },
                    "changed": {
                        "text": (
                            "Composite Memories will be split."
                            if self.composite
                            else "No Memory needs to be split."
                        ),
                        "source_ids": ids,
                    },
                    "unresolved": {
                        "text": (
                            "The Memory needs more context." if self.uncertain else ""
                        ),
                        "source_ids": ids if self.uncertain else [],
                    },
                },
                "items": records,
                "quality_issues": [],
            }
        )


def _client_and_context(
    *,
    composite: bool = False,
    uncertain: bool = False,
    name: str = "atomize/public",
):
    store = MemoryStore()
    context = ops.init(name)
    content = (
        "The library closes at five and the cafe closes at six."
        if composite
        else "The library entrance closes at five."
    )
    memory = ops.add(context, content)
    store.save(context)
    store.set_current(context.name)
    provider = _Provider(composite=composite, uncertain=uncertain)
    client = MemCommitClient(
        root=store.store_dir,
        semantic_provider_factory=lambda: provider,
    )
    return client, store, context, memory, provider


def test_root_exports_structural_atomize_contract():
    assert AtomizeAnalysisResult.__module__ == "memcommit.adapters.python_api.atomize"
    assert AtomizePlanUpdateResult.__module__ == "memcommit.adapters.python_api.atomize"
    assert (
        AtomizeSaveAsApplyResult.__module__ == "memcommit.adapters.python_api.atomize"
    )
    assert (
        AtomizeStructuralApplyResult.__module__
        == "memcommit.adapters.python_api.atomize"
    )
    assert issubclass(AtomizeConflictError, Exception)


def test_open_projects_provider_analysis_then_resumes_without_provider(
    isolated_store,
):
    client, _store, context, memory, provider = _client_and_context(composite=True)

    created = client.open_atomize_analysis(".")
    resumed_client = MemCommitClient(
        root=client.store_root,
        semantic_provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("saved Atomize resume opened a provider")
        ),
    )
    resumed = resumed_client.open_atomize_analysis(context.name)

    assert created.origin == "PROVIDER"
    assert resumed.origin == "SAVED"
    assert resumed.analysis_uid == created.analysis_uid
    assert resumed.version == created.version
    assert created.context_uid == context.uid
    assert created.memory_count == 1
    assert created.projected_memory_count == 2
    assert created.items[0].memory_uid == memory.uid
    assert created.items[0].action == "SPLIT"
    assert len(created.items[0].children) == 2
    assert created.issues[0].kind == "ATOMIZE_SPLIT"
    assert created.overview.understood.source_memory_uids == (memory.uid,)
    assert created.in_place_apply_allowed is True
    assert provider.calls == 1


def test_exact_hidden_prewarm_is_materialized_without_provider(
    isolated_store,
    monkeypatch,
):
    client, store, context, _memory, _provider = _client_and_context()
    prepared = create_atomize_analysis(
        context,
        impact_atomize(context, lambda: _Provider()),
    )
    match = AtomizePrewarmMatch(
        entry_key="capture/atomize",
        analysis=prepared,
        output_context_name=context.name,
    )
    monkeypatch.setattr(
        "memcommit.application.operations.semantic_updates.derive.atomize.analysis_runtime.find_declared_atomize_prewarm",
        lambda *, store, context: match,
    )
    client = MemCommitClient(
        root=store.store_dir,
        semantic_provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("exact prewarm opened a provider")
        ),
    )

    result = client.open_atomize_analysis(use_prepared=True)

    assert result.origin == "EXACT_PREWARM"
    assert result.analysis_uid == prepared.uid


def test_refresh_dominates_prepared_preference_and_calls_provider(
    isolated_store,
    monkeypatch,
):
    client, _store, context, _memory, provider = _client_and_context()
    monkeypatch.setattr(
        "memcommit.application.operations.semantic_updates.derive.atomize.analysis_runtime.find_declared_atomize_prewarm",
        lambda **_kwargs: pytest.fail("refresh looked up a prepared analysis"),
    )

    refreshed = client.open_atomize_analysis(
        context.name,
        refresh=True,
        use_prepared=True,
    )

    assert refreshed.origin == "PROVIDER"
    assert provider.calls == 1


def test_apply_as_is_records_one_checkpoint_and_exact_retry_recovers(
    isolated_store,
):
    client, store, context, memory, _provider = _client_and_context(composite=True)
    proposal = client.open_atomize_analysis(context.name)

    first = client.apply_atomize_as_is(proposal)
    retry = client.apply_atomize_as_is(proposal)

    assert first.recovered is False
    assert retry.recovered is True
    assert retry.checkpoint_uid == first.checkpoint_uid
    assert first.split_count == 1
    assert first.child_count == 2
    assert first.preserved_count == 0
    assert first.application_mode == "REVIEWED"
    assert first.items[0].source_memory_uid == memory.uid
    assert len(first.items[0].result_memory_uids) == 2
    assert len(store.list_checkpoints(context.name)) == 1
    current = store.load_direct(context.name)
    assert [item.content for item in current.iter_items()] == [
        "The library closes at five",
        "the cafe closes at six.",
    ]


def test_saved_version_apply_runs_normal_form_once_and_is_retryable(isolated_store):
    client, store, context, _memory, provider = _client_and_context(composite=True)
    proposal = client.open_atomize_analysis(context.name)

    first = client.apply_saved_atomize_as_is(
        context.name,
        expected_version=proposal.version,
    )
    retry = client.apply_saved_atomize_as_is(
        context.name,
        expected_version=proposal.version,
    )

    assert first.recovered is False
    assert retry.recovered is True
    assert retry.checkpoint_uid == first.checkpoint_uid
    assert first.normal_form_verified is True
    assert provider.calls == 4
    assert len(store.list_checkpoints(context.name)) == 1


def test_saved_version_apply_rejects_unknown_or_changed_revision(isolated_store):
    client, store, context, _memory, _provider = _client_and_context()
    proposal = client.open_atomize_analysis(context.name)

    with pytest.raises(AtomizeInputError, match="64-character"):
        client.apply_saved_atomize_as_is(
            context.name,
            expected_version="not-a-version",
        )
    with pytest.raises(AtomizeConflictError, match="version changed"):
        client.apply_saved_atomize_as_is(
            context.name,
            expected_version="0" * 64,
        )
    assert store.list_checkpoints(context.name) == []

    workbench = store.load_atomize_workbench(proposal._snapshot.analysis)
    assert workbench is not None
    workbench.layout = "STACKED"
    store.save_atomize_workbench(workbench)
    with pytest.raises(AtomizeConflictError, match="version changed"):
        client.apply_saved_atomize_as_is(
            context.name,
            expected_version=proposal.version,
        )


def test_open_can_focus_one_memory_without_reusing_whole_prepared_state(
    isolated_store,
):
    store = MemoryStore()
    context = ops.init("atomize/focused-public")
    first = ops.add(context, "The library closes at five and the cafe closes at six.")
    ops.add(context, "The lab closes at seven and the gym closes at eight.")
    store.save(context)
    provider = _Provider(composite=True)
    client = MemCommitClient(
        root=store.store_dir,
        semantic_provider_factory=lambda: provider,
    )

    proposal = client.open_atomize_analysis(
        context.name,
        memory_selector=first.uid[:8],
    )

    assert proposal.origin == "PROVIDER"
    assert proposal.memory_count == 1
    assert proposal.items[0].memory_uid == first.uid
    assert provider.calls == 1


def test_atomize_issues_are_read_only_evidence(isolated_store):
    client, _store, context, memory, provider = _client_and_context(composite=True)

    opened = client.open_atomize_analysis(context.name)
    issue = opened.issues[0]

    assert issue.uid == f"atomize:{memory.uid}"
    assert issue.kind == "ATOMIZE_SPLIT"
    assert not hasattr(issue, "answered")
    assert not hasattr(issue, "response_text")
    assert not hasattr(client, "update_atomize_response")
    assert not hasattr(client, "reanalyze_atomize_responses")
    assert not hasattr(client, "incorporate_and_apply_atomize")
    assert provider.calls == 1


def test_terminal_review_output_plan_cannot_be_edited(isolated_store):
    client, store, context, _memory, _provider = _client_and_context(
        composite=True,
        name="atomize/terminal-review",
    )
    proposal = client.open_atomize_analysis(context.name)
    applied = client.apply_saved_atomize_as_is(
        context.name,
        expected_version=proposal.version,
    )
    analysis = store.load_atomize_analysis(context.uid)
    terminal = capture_atomize_execution_snapshot(
        store=store,
        analysis=analysis,
        expected_review_record=store.load_atomize_workbench(analysis),
    )

    assert applied.recovered is False
    with pytest.raises(AtomizeExecutionError, match="cannot change its Output"):
        client.plan_atomize_output(
            context.name,
            expected_version=terminal.version_token,
            output_context_name="atomize/late-output",
        )


def test_output_plan_is_exact_provider_free_and_require_new(isolated_store):
    client, store, context, _memory, provider = _client_and_context(composite=True)
    opened = client.open_atomize_analysis(context.name)

    planned = client.plan_atomize_output(
        context.name,
        expected_version=opened.version,
        output_context_name="atomize/public-output",
    )

    assert planned.changed is True
    assert planned.proposal.output_context_name == "atomize/public-output"
    assert planned.proposal.in_place_apply_allowed is False
    assert provider.calls == 1
    assert not store.context_exists("atomize/public-output")

    occupied = ops.init("atomize/occupied")
    store.save(occupied)
    with pytest.raises(AtomizeInputError):
        client.plan_atomize_output(
            context.name,
            expected_version=planned.proposal.version,
            output_context_name=occupied.name,
        )
    assert client.open_atomize_analysis(context.name).output_context_name == (
        "atomize/public-output"
    )


def test_save_as_uses_reviewed_plan_and_exact_retry(isolated_store):
    client, store, context, _memory, provider = _client_and_context(composite=True)
    source_before = store.load_direct(context.name).to_dict()
    opened = client.open_atomize_analysis(context.name)
    planned = client.plan_atomize_output(
        context.name,
        expected_version=opened.version,
        output_context_name="atomize/saved-output",
    )

    applied = client.save_saved_atomize_as(
        context.name,
        expected_version=planned.proposal.version,
    )
    retried = client.save_saved_atomize_as(
        context.name,
        expected_version=planned.proposal.version,
    )

    assert applied.recovered is False
    assert retried.recovered is True
    assert retried.checkpoint_uid == applied.checkpoint_uid
    assert applied.source_context_name == context.name
    assert applied.context_name == "atomize/saved-output"
    assert applied.current_context_name == "atomize/saved-output"
    assert store.load_direct(context.name).to_dict() == source_before
    assert [
        item.content for item in store.load_direct(applied.context_name).iter_items()
    ] == ["The library closes at five", "the cafe closes at six."]
    assert len(store.list_checkpoints(applied.context_name)) == 1
    assert provider.calls == 4


def test_all_preserved_apply_still_records_deliberate_completion(
    isolated_store,
):
    client, store, context, memory, _provider = _client_and_context()
    proposal = client.open_atomize_analysis(context.name)

    result = client.apply_atomize_as_is(proposal)

    assert result.split_count == 0
    assert result.preserved_count == 1
    assert result.items[0].result_memory_uids == (memory.uid,)
    assert len(store.list_checkpoints(context.name)) == 1


def test_open_uncertainty_is_preserved_and_audited_as_is(isolated_store):
    client, store, context, memory, _provider = _client_and_context(uncertain=True)
    proposal = client.open_atomize_analysis(context.name)

    result = client.apply_atomize_as_is(proposal)

    assert proposal.issues[0].kind == "ATOMIZE_UNCERTAINTY"
    assert result.application_mode == "AS_IS"
    assert result.unresolved_at_apply_count == 1
    assert result.items[0].result_memory_uids == (memory.uid,)
    checkpoint = store.list_checkpoints(context.name)[0]
    assert checkpoint["args"]["unresolved_at_apply"][0]["response_state"] == "OPEN"


def test_source_or_workbench_change_is_a_conflict(isolated_store):
    client, store, context, memory, _provider = _client_and_context()
    proposal = client.open_atomize_analysis(context.name)
    changed = store.load_direct(context.name)
    changed.replace(Memory(uid=memory.uid, content="The entrance closes at six."))
    store.save(changed)

    with pytest.raises(AtomizeConflictError):
        client.apply_atomize_as_is(proposal)

    # A fresh Store proves a nonterminal workbench edit is also not mistaken
    # for the exact terminal extension accepted by retry recovery.
    client, store, context, _memory, _provider = _client_and_context(
        name="atomize/public-workbench"
    )
    proposal = client.open_atomize_analysis(context.name)
    workbench = store.load_atomize_workbench(proposal._snapshot.analysis)
    assert workbench is not None
    workbench.layout = "STACKED"
    store.save_atomize_workbench(workbench)
    with pytest.raises(AtomizeConflictError):
        client.apply_atomize_as_is(proposal)


def test_save_as_plan_is_visible_but_not_silently_applied_in_place(
    isolated_store,
):
    client, store, context, _memory, _provider = _client_and_context()
    first = client.open_atomize_analysis(context.name)
    workbench = store.load_atomize_workbench(first._snapshot.analysis)
    assert workbench is not None
    workbench.output_context_name = "atomize/planned-output"
    store.save_atomize_workbench(workbench)

    planned = client.open_atomize_analysis(context.name)

    assert planned.output_context_name == "atomize/planned-output"
    assert planned.in_place_apply_allowed is False
    with pytest.raises(AtomizeInputError, match="different Output Context"):
        client.apply_atomize_as_is(planned)
    with pytest.raises(AtomizeInputError, match="accepted Atomize revision"):
        client.apply_atomize_as_is(replace(planned, in_place_apply_allowed=True))
    assert store.list_checkpoints(context.name) == []


def test_public_error_taxonomy_and_validation_precede_provider(isolated_store):
    client, _store, context, _memory, provider = _client_and_context()
    with pytest.raises(AtomizeInputError):
        client.open_atomize_analysis(" ")
    with pytest.raises(AtomizeInputError):
        client.open_atomize_analysis(refresh=1)  # type: ignore[arg-type]
    with pytest.raises(AtomizeContextError):
        client.open_atomize_analysis("missing/context")
    assert provider.calls == 0

    failing = MemCommitClient(
        root=client.store_root,
        semantic_provider_factory=lambda: (_ for _ in ()).throw(
            RuntimeError("endpoint unavailable")
        ),
    )
    with pytest.raises(AtomizeProviderFailure, match="endpoint unavailable"):
        failing.open_atomize_analysis(context.name, refresh=True)


def test_invalid_provider_output_is_execution_not_transport_failure(
    isolated_store,
):
    client, store, context, _memory, _provider = _client_and_context()

    class _InvalidProvider:
        def complete(self, *_args, **_kwargs):
            return "not json"

    client = MemCommitClient(
        root=store.store_dir,
        semantic_provider_factory=_InvalidProvider,
    )
    with pytest.raises(AtomizeExecutionError):
        client.open_atomize_analysis(context.name, refresh=True)


def test_atomize_adapter_does_not_reach_back_into_client_facade():
    root = Path(__file__).resolve().parents[1]
    tree = ast.parse(
        (root / "src/memcommit/adapters/python_api/_operations/atomize.py").read_text(
            encoding="utf-8"
        )
    )
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.append(node.module)
    assert "memcommit.adapters.python_api.client" not in imports


def test_public_client_keeps_structural_atomize_assembly_lazy(tmp_path):
    environment = os.environ.copy()
    environment["MEMCOMMIT_ATOMIZE_IMPORT_ROOT"] = str(tmp_path / "store")
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "\n".join(
                (
                    "import os, sys",
                    "from pathlib import Path",
                    "from memcommit.adapters.python_api import AtomizeInputError, MemCommitClient",
                    "assert 'memcommit.adapters.python_api._operations.atomize' not in sys.modules",
                    "assert 'memcommit.application.operations.semantic_updates.derive.atomize.analysis_runtime' not in sys.modules",
                    "client = MemCommitClient(root=Path(os.environ['MEMCOMMIT_ATOMIZE_IMPORT_ROOT']), create=True)",
                    "assert 'memcommit.adapters.python_api._operations.atomize' not in sys.modules",
                    "try:",
                    "    client.open_atomize_analysis('')",
                    "except AtomizeInputError:",
                    "    pass",
                    "else:",
                    "    raise AssertionError('invalid Atomize input succeeded')",
                    "assert 'memcommit.adapters.python_api._operations.atomize' in sys.modules",
                    "assert 'memcommit.application.operations.semantic_updates.derive.atomize.analysis_runtime' in sys.modules",
                    "assert 'memcommit.adapters.python_api._operations.atomize_grounding' not in sys.modules",
                )
            ),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
