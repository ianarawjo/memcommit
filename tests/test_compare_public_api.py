"""Public Python lifecycle contracts for durable read-only Compare."""

from __future__ import annotations

from dataclasses import replace
import json
import uuid

import pytest

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.python_api import (
    CompareConflictError,
    ComparisonResult,
    MemCommitClient,
)
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.provider_contract import COMPARISON_PAYLOAD_MARKER
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.repository import (
    load_comparison_analysis,
    save_comparison_analysis,
)
from memcommit.persistence.store import MemoryStore


class _CompareProvider:
    def __init__(self) -> None:
        self.payloads: list[dict[str, object]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "compare_contexts"
        assert output_schema is not None
        payload = json.loads(prompt.split(COMPARISON_PAYLOAD_MARKER, 1)[1])
        self.payloads.append(payload)
        reference = payload["frames"][0]["memories"][0]["memory_id"]
        compared = payload["frames"][1]["memories"][0]["memory_id"]
        return json.dumps(
            {
                "overview": "The two peers state the same operating policy.",
                "reports": {
                    "both": "Both peers keep the library open.",
                    "differences": "",
                    "reference_only": "",
                    "compared_only": "",
                },
                "relations": [
                    {
                        "relation_key": "same_policy",
                        "kind": "EQUIVALENT",
                        "status": "RESOLVED",
                        "summary": "Both Memories state the same policy.",
                        "reason": "Their operational scope and outcome agree.",
                    }
                ],
                "source_assignments": [
                    {
                        "source_memory_id": reference,
                        "relation_key": "same_policy",
                    },
                    {
                        "source_memory_id": compared,
                        "relation_key": "same_policy",
                    },
                ],
                "issues": [],
            }
        )


def _contexts(root):
    store = MemoryStore(root=root)
    reference = ops.init("compare/reference")
    ops.add(reference, "The library remains open.")
    compared = ops.init("compare/peer")
    ops.add(compared, "The library stays open.")
    store.save(reference)
    store.save(compared)
    store.set_current(reference.name)
    return store, reference, compared


@pytest.mark.usefixtures("retired_study_artifacts")
def test_public_compare_run_open_reuse_and_exact_refresh(isolated_store):
    store, reference, compared = _contexts(isolated_store)
    provider = _CompareProvider()
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=lambda: provider,
    )

    created = client.compare_contexts(reference.name, compared.name)
    opened = client.open_comparison(created.analysis_uid)
    reused = client.compare_contexts(reference.name, compared.name)
    refreshed = client.refresh_comparison(
        opened.analysis_uid,
        expected_version=opened.version,
    )

    assert isinstance(created, ComparisonResult)
    assert created.origin == "LIVE"
    assert created.durable is True
    assert created.frames[0].context_name == reference.name
    assert created.relations[0].kind == "EQUIVALENT"
    assert opened.origin == "SAVED_OPEN"
    assert opened.version == created.version
    assert reused.origin == "SAVED_REUSE"
    assert refreshed.analysis_uid != opened.analysis_uid
    assert refreshed.version != opened.version
    assert len(provider.payloads) == 2
    assert len(store.list_checkpoints(reference.name)) == 0
    assert len(store.list_checkpoints(compared.name)) == 0

    with pytest.raises(CompareConflictError, match="changed"):
        client.refresh_comparison(
            opened.analysis_uid,
            expected_version=opened.version,
        )
    assert len(provider.payloads) == 2


def test_public_open_rejects_stale_sources_but_refresh_updates_them(
    isolated_store,
):
    store, reference, compared = _contexts(isolated_store)
    provider = _CompareProvider()
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=lambda: provider,
    )
    created = client.compare_contexts(reference.name, compared.name)
    changed = store.load_direct(reference.name)
    changed.memories[next(iter(changed.memories))].content = (
        "The library remains open every weekday."
    )
    store.save(changed)

    with pytest.raises(CompareConflictError, match="source Context changed"):
        client.open_comparison(created.analysis_uid)

    refreshed = client.refresh_comparison(
        created.analysis_uid,
        expected_version=created.version,
    )

    assert refreshed.analysis_uid != created.analysis_uid
    assert len(provider.payloads) == 2


def test_public_refresh_rejects_an_invalid_or_unknown_review_before_provider(
    isolated_store,
):
    provider = _CompareProvider()
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=lambda: provider,
    )

    with pytest.raises(CompareConflictError, match="changed"):
        client.refresh_comparison(
            str(uuid.uuid4()),
            expected_version="0" * 64,
        )

    assert provider.payloads == []


def test_public_open_revalidates_recursive_scopes_in_the_explicit_store(
    isolated_store,
):
    store = MemoryStore(root=isolated_store)
    reference = ops.init("recursive/reference")
    compared = ops.init("recursive/peer")
    reference_child = ops.init("recursive/reference/child")
    compared_child = ops.init("recursive/peer/child")
    ops.add(reference_child, "The library remains open.")
    ops.add(compared_child, "The library stays open.")
    for context in (reference, compared, reference_child, compared_child):
        store.save(context)
    store.set_current(reference.name)
    provider = _CompareProvider()
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=lambda: provider,
    )

    created = client.compare_contexts(
        reference.name,
        compared.name,
        reference_descendants=True,
        compared_descendants=True,
    )
    opened = client.open_comparison(created.analysis_uid)

    assert opened.version == created.version
    assert opened.include_descendants == (True, True)
    assert len(provider.payloads) == 1


def test_public_refresh_rejects_same_uid_content_drift_before_provider(
    isolated_store,
):
    store, reference, compared = _contexts(isolated_store)
    provider = _CompareProvider()
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=lambda: provider,
    )
    created = client.compare_contexts(reference.name, compared.name)
    saved = load_comparison_analysis(
        reference.uid,
        compared.uid,
        store=store,
    )
    assert saved is not None
    changed = replace(
        saved,
        understanding=replace(
            saved.understanding,
            text="A separately written summary with the same analysis UID.",
        ),
    )
    save_comparison_analysis(
        store,
        changed,
        expected_analysis_uid=saved.uid,
    )

    with pytest.raises(CompareConflictError, match="changed"):
        client.refresh_comparison(
            created.analysis_uid,
            expected_version=created.version,
        )

    assert len(provider.payloads) == 1


def test_public_refresh_preserves_explicit_singleton_memory_focus(
    isolated_store,
):
    store, reference, compared = _contexts(isolated_store)
    reference_focus = next(iter(reference.memories))
    compared_focus = next(iter(compared.memories))
    provider = _CompareProvider()
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=lambda: provider,
    )
    created = client.compare_contexts(
        reference.name,
        compared.name,
        reference_memory=reference_focus,
        compared_memory=compared_focus,
    )
    changed_reference = store.load_direct(reference.name)
    changed_compared = store.load_direct(compared.name)
    ops.add(changed_reference, "A new neighboring reference claim.")
    ops.add(changed_compared, "A new neighboring peer claim.")
    store.save(changed_reference)
    store.save(changed_compared)

    refreshed = client.refresh_comparison(
        created.analysis_uid,
        expected_version=created.version,
    )

    assert created.frames[0].selected_memory_uid == reference_focus
    assert created.frames[1].selected_memory_uid == compared_focus
    assert refreshed.frames[0].selected_memory_uid == reference_focus
    assert refreshed.frames[1].selected_memory_uid == compared_focus
    assert len(provider.payloads) == 2
    assert [
        len(frame["memories"])
        for frame in provider.payloads[1]["frames"]
    ] == [1, 1]
    assert [
        len(frame["context_evidence"])
        for frame in provider.payloads[1]["frames"]
    ] == [1, 1]
