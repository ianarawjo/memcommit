"""Contracts for targetless, durable peer-Context comparison."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import threading
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.comparison import ComparisonInput
from memcommit.comparison_provider import (
    COMPARISON_PAYLOAD_MARKER,
    ComparisonProviderError,
    analyze_comparison,
)
from memcommit.comparison_store import (
    ConcurrentComparisonUpdateError,
    comparison_analysis_path,
    comparison_paths_for_context,
    delete_comparison_paths,
    load_comparison_analysis,
    save_comparison_analysis,
)
from memcommit.commands.compare import render_comparison
from memcommit.store import MemoryStore


runner = CliRunner()


class ExhaustiveCompareProvider:
    """Return one paired relation plus exhaustive one-sided relations."""

    def __init__(self, response_builder=None):
        self.response_builder = response_builder
        self.payloads: list[dict[str, object]] = []
        self.schemas: list[dict[str, object]] = []

    @staticmethod
    def default_response(payload: dict[str, object]) -> dict[str, object]:
        frames = payload["frames"]
        assert isinstance(frames, list)
        reference = frames[0]["memories"]
        compared = frames[1]["memories"]
        assert isinstance(reference, list)
        assert isinstance(compared, list)
        relations: list[dict[str, object]] = [
            {
                "relation_key": "shared",
                "reference_memory_ids": [reference[0]["memory_id"]],
                "compared_memory_ids": [compared[0]["memory_id"]],
                "kind": "EQUIVALENT",
                "status": "RESOLVED",
                "summary": "Both advisors require a concise proposal.",
                "reason": "The operational requirement and scope agree.",
            }
        ]
        for index, memory in enumerate(reference[1:], start=1):
            relations.append(
                {
                    "relation_key": f"reference_only_{index}",
                    "reference_memory_ids": [memory["memory_id"]],
                    "compared_memory_ids": [],
                    "kind": "DISTINCT",
                    "status": "RESOLVED",
                    "summary": "Useful guidance appears only in the reference.",
                    "reason": "The peer contains no corresponding claim.",
                }
            )
        for index, memory in enumerate(compared[1:], start=1):
            relations.append(
                {
                    "relation_key": f"compared_only_{index}",
                    "reference_memory_ids": [],
                    "compared_memory_ids": [memory["memory_id"]],
                    "kind": "DISTINCT",
                    "status": "RESOLVED",
                    "summary": "Useful guidance appears only in the peer.",
                    "reason": "The reference contains no corresponding claim.",
                }
            )
        return {
            "overview": (
                "The two equal-authority advisors share one policy and each "
                "contributes independently useful guidance."
            ),
            "relations": relations,
            "issues": [],
        }

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "compare_contexts"
        assert output_schema is not None
        assert set(output_schema["required"]) == {
            "overview",
            "relations",
            "issues",
        }
        # Codex structured output rejects JSON Schema uniqueItems. The strict
        # parser below the schema remains the authority for alias uniqueness.
        assert "uniqueItems" not in json.dumps(output_schema)
        assert "target" not in json.dumps(output_schema).lower()
        assert "miscellaneous bucket" in prompt
        assert "Do not state relation counts in overview" in prompt
        payload = json.loads(
            prompt.split(COMPARISON_PAYLOAD_MARKER, 1)[1]
        )
        assert payload["mode"] == "SYMMETRIC_PEER_COMPARISON"
        assert [frame["authority"] for frame in payload["frames"]] == [
            "PEER",
            "PEER",
        ]
        assert "context_name" not in json.dumps(payload)
        self.payloads.append(payload)
        self.schemas.append(output_schema)
        builder = self.response_builder or self.default_response
        return json.dumps(builder(payload))


def _task2_contexts(store: MemoryStore):
    reference = ops.init("task2/advisor1")
    ops.add_many(
        reference,
        [
            "Keep the proposal to two pages.",
            "Use concrete section headings.",
        ],
    )
    compared = ops.init("task2/advisor2")
    ops.add_many(
        compared,
        [
            "The research proposal must not exceed two pages.",
            "Define specialist terminology on first use.",
        ],
    )
    store.save(reference)
    store.save(compared)
    store.set_current(reference.name)
    return reference, compared


def _patch_provider(monkeypatch, provider) -> None:
    monkeypatch.setattr(
        "memcommit.commands.compare.connect_codex_chatgpt_provider",
        lambda: provider,
    )


def test_compare_creates_durable_read_only_analysis_and_resumes_provider_free(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    reference, compared = _task2_contexts(store)
    provider = ExhaustiveCompareProvider()
    _patch_provider(monkeypatch, provider)
    reference_before = store._context_file(reference.name).read_bytes()
    compared_before = store._context_file(compared.name).read_bytes()

    created = runner.invoke(
        app,
        ["compare", "--to", compared.name],
    )

    assert created.exit_code == 0, created.output
    assert len(provider.payloads) == 1
    assert "MEM COMPARE · SYMMETRIC PEERS" in created.output
    assert "Reference: task2/advisor1 (layout only; no authority)" in (
        created.output
    )
    assert "Analysis:" in created.output
    assert "NEW" in created.output
    assert "WHAT BOTH CONTAIN" in created.output
    assert "ONLY IN task2/advisor1 · not automatically a deficiency" in (
        created.output
    )
    assert "ONLY IN task2/advisor2 · not automatically a deficiency" in (
        created.output
    )
    assert reference.uid[:8] not in created.output
    assert next(iter(reference.memories))[:8] in created.output
    assert next(iter(compared.memories))[:8] in created.output
    assert store._context_file(reference.name).read_bytes() == reference_before
    assert store._context_file(compared.name).read_bytes() == compared_before
    assert store.list_checkpoints(reference.name) == []
    assert store.list_checkpoints(compared.name) == []
    assert store.current_context_name() == reference.name

    path = comparison_analysis_path(reference.uid, compared.uid)
    assert path.is_file()
    saved_before = path.read_bytes()
    saved = load_comparison_analysis(reference.uid, compared.uid)
    assert saved is not None
    assert [frame.context_name for frame in saved.frames] == [
        reference.name,
        compared.name,
    ]

    resumed = runner.invoke(
        app,
        ["compare", "--to", compared.name],
    )

    assert resumed.exit_code == 0, resumed.output
    assert "REUSED" in resumed.output
    assert len(provider.payloads) == 1
    assert path.read_bytes() == saved_before


def test_refresh_and_source_change_each_replace_the_ordered_latest_slot(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    reference, compared = _task2_contexts(store)
    provider = ExhaustiveCompareProvider()
    _patch_provider(monkeypatch, provider)

    assert runner.invoke(
        app,
        ["compare", "--to", compared.name],
    ).exit_code == 0
    first = load_comparison_analysis(reference.uid, compared.uid)
    assert first is not None

    refreshed = runner.invoke(
        app,
        ["compare", "--to", compared.name, "--refresh"],
    )

    assert refreshed.exit_code == 0, refreshed.output
    second = load_comparison_analysis(reference.uid, compared.uid)
    assert second is not None
    assert second.uid != first.uid
    assert len(provider.payloads) == 2

    changed = store.load_direct(compared.name)
    ops.add(changed, "Prefer active voice in the abstract.")
    store.save(changed)
    rerun = runner.invoke(
        app,
        ["compare", "--to", compared.name],
    )

    assert rerun.exit_code == 0, rerun.output
    third = load_comparison_analysis(reference.uid, compared.uid)
    assert third is not None
    assert third.uid != second.uid
    assert third.matches(
        store.load_direct(reference.name),
        store.load_direct(compared.name),
    )
    assert len(provider.payloads) == 3


def test_reverse_orientation_has_an_independent_cache_slot(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    reference, compared = _task2_contexts(store)
    provider = ExhaustiveCompareProvider()
    _patch_provider(monkeypatch, provider)

    forward = runner.invoke(
        app,
        ["compare", "--to", compared.name],
    )
    assert forward.exit_code == 0, forward.output
    store.set_current(compared.name)
    reverse = runner.invoke(
        app,
        ["compare", "--to", reference.name],
    )

    assert reverse.exit_code == 0, reverse.output
    assert len(provider.payloads) == 2
    assert comparison_analysis_path(reference.uid, compared.uid).is_file()
    assert comparison_analysis_path(compared.uid, reference.uid).is_file()
    assert provider.payloads[0]["frames"][0]["memories"][0]["content"] == (
        "Keep the proposal to two pages."
    )
    assert provider.payloads[1]["frames"][0]["memories"][0]["content"] == (
        "The research proposal must not exceed two pages."
    )

    store.set_current(reference.name)
    resumed = runner.invoke(
        app,
        ["compare", "--to", compared.name],
    )
    assert resumed.exit_code == 0
    assert "REUSED" in resumed.output
    assert len(provider.payloads) == 2


def test_provider_accepts_one_to_many_relation_and_required_conflict_issue(
    isolated_store,
):
    store = MemoryStore()
    reference, compared = _task2_contexts(store)
    comparison_input = ComparisonInput.from_contexts(reference, compared)

    def response(payload):
        reference_memories = payload["frames"][0]["memories"]
        compared_memories = payload["frames"][1]["memories"]
        return {
            "overview": "One policy cluster conflicts; one item is distinct.",
            "relations": [
                {
                    "relation_key": "one_to_many_conflict",
                    "reference_memory_ids": [
                        reference_memories[0]["memory_id"],
                    ],
                    "compared_memory_ids": [
                        memory["memory_id"] for memory in compared_memories
                    ],
                    "kind": "CONFLICT",
                    "status": "UNRESOLVED",
                    "summary": "One policy conflicts with a two-part peer rule.",
                    "reason": "The same case receives incompatible directions.",
                },
                {
                    "relation_key": "reference_only",
                    "reference_memory_ids": [
                        reference_memories[1]["memory_id"],
                    ],
                    "compared_memory_ids": [],
                    "kind": "DISTINCT",
                    "status": "RESOLVED",
                    "summary": "The heading policy is one-sided.",
                    "reason": "No peer Memory addresses headings.",
                },
            ],
            "issues": [
                {
                    "issue_key": "conflict_scope",
                    "relation_keys": ["one_to_many_conflict"],
                    "priority": "REQUIRED",
                    "title": "Set the governing scope",
                    "question": "Which rule governs when both conditions hold?",
                    "why_it_matters": "A later meld cannot retain both as-is.",
                    "options": [
                        {
                            "label": "Preserve explicit alternatives",
                            "text": "Keep both rules under disjoint conditions.",
                        }
                    ],
                }
            ],
        }

    analysis = analyze_comparison(
        comparison_input,
        ExhaustiveCompareProvider(response),
    )

    assert [relation.kind for relation in analysis.relations] == [
        "CONFLICT",
        "DISTINCT",
    ]
    assert len(analysis.relations[0].members) == 3
    assert analysis.issues[0].priority == "REQUIRED"
    assert analysis.issues[0].relation_uids == (
        analysis.relations[0].uid,
    )


@pytest.mark.parametrize("failure", ["omitted", "duplicated", "unknown"])
def test_provider_rejects_non_exhaustive_or_untrusted_source_ids(
    isolated_store,
    failure,
):
    store = MemoryStore()
    reference, compared = _task2_contexts(store)
    comparison_input = ComparisonInput.from_contexts(reference, compared)

    def malformed(payload):
        response = ExhaustiveCompareProvider.default_response(payload)
        relations = response["relations"]
        if failure == "omitted":
            relations.pop()
        elif failure == "duplicated":
            relations[0]["reference_memory_ids"].append(
                relations[1]["reference_memory_ids"][0]
            )
        else:
            relations[0]["compared_memory_ids"] = ["unknown"]
        return response

    with pytest.raises(
        ComparisonProviderError,
        match="every source Memory exactly once|unknown",
    ):
        analyze_comparison(
            comparison_input,
            ExhaustiveCompareProvider(malformed),
        )


def test_failed_refresh_preserves_previous_analysis(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    reference, compared = _task2_contexts(store)
    provider = ExhaustiveCompareProvider()
    _patch_provider(monkeypatch, provider)
    assert runner.invoke(
        app,
        ["compare", "--to", compared.name],
    ).exit_code == 0
    path = comparison_analysis_path(reference.uid, compared.uid)
    before = path.read_bytes()

    def malformed(payload):
        response = ExhaustiveCompareProvider.default_response(payload)
        response["relations"].pop()
        return response

    _patch_provider(
        monkeypatch,
        ExhaustiveCompareProvider(malformed),
    )
    failed = runner.invoke(
        app,
        ["compare", "--to", compared.name, "--refresh"],
    )

    assert failed.exit_code == 1
    assert "every source Memory exactly once" in failed.output
    assert path.read_bytes() == before


def test_source_change_during_provider_call_is_not_saved(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    reference, compared = _task2_contexts(store)

    class MutatingProvider(ExhaustiveCompareProvider):
        def complete(self, prompt, *, operation, output_schema=None):
            changed = store.load_direct(compared.name)
            ops.add(changed, "This arrives while analysis is in flight.")
            store.save(changed)
            return super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )

    _patch_provider(monkeypatch, MutatingProvider())
    result = runner.invoke(
        app,
        ["compare", "--to", compared.name],
    )

    assert result.exit_code == 1
    assert "changed while Compare was analyzing" in result.output
    assert not comparison_analysis_path(reference.uid, compared.uid).exists()


def test_saved_frame_snapshot_is_cryptographically_bound_to_context_digest(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    reference, compared = _task2_contexts(store)
    _patch_provider(monkeypatch, ExhaustiveCompareProvider())
    assert runner.invoke(
        app,
        ["compare", "--to", compared.name],
    ).exit_code == 0
    path = comparison_analysis_path(reference.uid, compared.uid)
    value = json.loads(path.read_text())
    memory = value["frames"][0]["memories"][0]
    memory["content"] = "FORGED exact source text"
    memory["content_digest"] = hashlib.sha256(
        memory["content"].encode("utf-8")
    ).hexdigest()
    path.write_text(json.dumps(value))

    with pytest.raises(
        ValueError,
        match="Saved comparison analysis is invalid",
    ):
        load_comparison_analysis(reference.uid, compared.uid)


def test_older_supported_ruleset_is_readable_but_not_reused(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    reference, compared = _task2_contexts(store)
    provider = ExhaustiveCompareProvider()
    _patch_provider(monkeypatch, provider)
    assert runner.invoke(
        app,
        ["compare", "--to", compared.name],
    ).exit_code == 0
    path = comparison_analysis_path(reference.uid, compared.uid)
    value = json.loads(path.read_text())
    value["ruleset_version"] = "peer-relations-v1"
    path.write_text(json.dumps(value))
    older = load_comparison_analysis(reference.uid, compared.uid)
    assert older is not None
    assert older.ruleset_version == "peer-relations-v1"

    replaced = runner.invoke(
        app,
        ["compare", "--to", compared.name],
    )

    assert replaced.exit_code == 0, replaced.output
    assert "NEW" in replaced.output
    assert len(provider.payloads) == 2
    current = load_comparison_analysis(reference.uid, compared.uid)
    assert current is not None
    assert current.ruleset_version == "peer-relations-v2"


def test_ordered_slot_cas_rejects_stale_competing_refresh(
    isolated_store,
):
    store = MemoryStore()
    reference, compared = _task2_contexts(store)
    initial = analyze_comparison(
        ComparisonInput.from_contexts(reference, compared),
        ExhaustiveCompareProvider(),
    )
    save_comparison_analysis(
        store,
        initial,
        expected_analysis_uid=None,
    )
    winner = analyze_comparison(
        ComparisonInput.from_contexts(reference, compared),
        ExhaustiveCompareProvider(),
    )
    stale = analyze_comparison(
        ComparisonInput.from_contexts(reference, compared),
        ExhaustiveCompareProvider(),
    )

    save_comparison_analysis(
        store,
        winner,
        expected_analysis_uid=initial.uid,
    )
    with pytest.raises(
        ConcurrentComparisonUpdateError,
        match="ordered comparison slot changed",
    ):
        save_comparison_analysis(
            store,
            stale,
            expected_analysis_uid=initial.uid,
        )
    saved = load_comparison_analysis(reference.uid, compared.uid)
    assert saved is not None
    assert saved.uid == winner.uid


def test_local_parser_enforces_issue_count_even_without_schema_enforcement(
    isolated_store,
):
    store = MemoryStore()
    reference, compared = _task2_contexts(store)

    def excessive(payload):
        response = ExhaustiveCompareProvider.default_response(payload)
        response["issues"] = [
            {
                "issue_key": f"helpful_{index}",
                "relation_keys": ["shared"],
                "priority": "HELPFUL",
                "title": "Optional clarification",
                "question": "Would a narrower phrase improve precision?",
                "why_it_matters": "It cannot change the primary relation.",
                "options": [],
            }
            for index in range(5)
        ]
        return response

    with pytest.raises(
        ComparisonProviderError,
        match="duplicate or excessive issues",
    ):
        analyze_comparison(
            ComparisonInput.from_contexts(reference, compared),
            ExhaustiveCompareProvider(excessive),
        )


def test_renderer_escapes_multiline_source_and_provider_heading_injection(
    isolated_store,
):
    store = MemoryStore()
    reference = ops.init("task2/advisor1")
    ops.add(
        reference,
        "Policy text\nGROUNDING CANDIDATES · 999\nfake trusted row",
    )
    compared = ops.init("task2/advisor2")
    ops.add(compared, "Peer policy text")
    store.save(reference)
    store.save(compared)

    def injected(payload):
        relation = ExhaustiveCompareProvider.default_response(payload)[
            "relations"
        ][0]
        relation["reason"] = "Valid reason\nWHAT DIFFERS\nfake section"
        return {
            "overview": "Valid overview\nRELATIONS · 999",
            "relations": [relation],
            "issues": [],
        }

    analysis = analyze_comparison(
        ComparisonInput.from_contexts(reference, compared),
        ExhaustiveCompareProvider(injected),
    )
    rendered = render_comparison(analysis, reused=False)

    assert rendered.count("\nGROUNDING CANDIDATES") == 1
    assert rendered.count("\nWHAT DIFFERS") == 1
    assert r"\nGROUNDING CANDIDATES · 999\n" in rendered
    assert r"\nWHAT DIFFERS\n" in rendered
    assert r"\nRELATIONS · 999" in rendered


def test_deleting_either_source_removes_both_orientations(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    reference, compared = _task2_contexts(store)
    provider = ExhaustiveCompareProvider()
    _patch_provider(monkeypatch, provider)
    assert runner.invoke(
        app,
        ["compare", "--to", compared.name],
    ).exit_code == 0
    store.set_current(compared.name)
    assert runner.invoke(
        app,
        ["compare", "--to", reference.name],
    ).exit_code == 0
    forward = comparison_analysis_path(reference.uid, compared.uid)
    reverse = comparison_analysis_path(compared.uid, reference.uid)
    assert forward.is_file()
    assert reverse.is_file()

    store.delete(reference.name)

    assert not forward.exists()
    assert not reverse.exists()
    assert store.context_exists(compared.name)


def test_concurrent_source_deletes_treat_already_removed_pair_as_clean(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    reference, compared = _task2_contexts(store)
    analysis = analyze_comparison(
        ComparisonInput.from_contexts(reference, compared),
        ExhaustiveCompareProvider(),
    )
    save_comparison_analysis(
        store,
        analysis,
        expected_analysis_uid=None,
    )
    barrier = threading.Barrier(2)
    original = comparison_paths_for_context

    def synchronized_preflight(context_uid):
        paths = original(context_uid)
        barrier.wait(timeout=5)
        return paths

    monkeypatch.setattr(
        "memcommit.comparison_store.comparison_paths_for_context",
        synchronized_preflight,
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(store.delete, reference.name),
            executor.submit(store.delete, compared.name),
        ]
        for future in futures:
            future.result(timeout=10)

    assert not store.context_exists(reference.name)
    assert not store.context_exists(compared.name)
    assert not comparison_analysis_path(
        reference.uid,
        compared.uid,
    ).exists()


def test_unrelated_atomic_temp_does_not_block_source_cleanup(
    isolated_store,
):
    store = MemoryStore()
    reference, compared = _task2_contexts(store)
    analysis = analyze_comparison(
        ComparisonInput.from_contexts(reference, compared),
        ExhaustiveCompareProvider(),
    )
    save_comparison_analysis(
        store,
        analysis,
        expected_analysis_uid=None,
    )
    path = comparison_analysis_path(reference.uid, compared.uid)
    unrelated = path.parent / (
        f".{uuid.uuid4()}--{uuid.uuid4()}.json.write-{uuid.uuid4().hex}"
    )
    unrelated.write_text("unfinished unrelated analysis")

    store.delete(reference.name)

    assert not path.exists()
    assert unrelated.exists()


def test_missing_preflighted_artifact_is_an_idempotent_privacy_result(
    isolated_store,
):
    store = MemoryStore()
    reference, compared = _task2_contexts(store)
    analysis = analyze_comparison(
        ComparisonInput.from_contexts(reference, compared),
        ExhaustiveCompareProvider(),
    )
    save_comparison_analysis(
        store,
        analysis,
        expected_analysis_uid=None,
    )
    paths = comparison_paths_for_context(reference.uid)
    assert len(paths) == 1

    delete_comparison_paths(paths)
    delete_comparison_paths(paths)

    assert not paths[0].exists()


def test_compare_preconditions_fail_before_provider_connection(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    provider = ExhaustiveCompareProvider()
    _patch_provider(monkeypatch, provider)

    no_current = runner.invoke(
        app,
        ["compare", "--to", "task2/missing"],
    )
    assert no_current.exit_code == 1
    assert "No current reference Context" in no_current.output

    reference = ops.init("task2/advisor1")
    ops.add(reference, "Use a concise proposal structure.")
    store.save(reference)
    store.set_current(reference.name)
    missing = runner.invoke(
        app,
        ["compare", "--to", "task2/missing"],
    )
    same = runner.invoke(
        app,
        ["compare", "--to", reference.name],
    )

    assert missing.exit_code == 1
    assert "does not exist" in missing.output
    assert same.exit_code == 1
    assert "two distinct Contexts" in same.output
    assert provider.payloads == []
