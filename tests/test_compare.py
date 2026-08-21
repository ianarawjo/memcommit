"""Contracts for targetless, durable peer-Context comparison."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import threading
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
import memcommit.commands.compare as compare_command
import memcommit.commands.compare_sessions as compare_sessions_module
from memcommit.cli import app
from memcommit.comparison import ComparisonInput, comparison_canonical_digest
from memcommit.comparison_provider import (
    COMPARISON_PAYLOAD_MARKER,
    ComparisonProviderError,
    analyze_comparison,
    comparison_output_schema,
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
from memcommit.commands.compare_setup import CompareSetupReceipt
from memcommit.commands.compare_sessions import (
    choose_comparison_session,
    comparison_session_entries,
)
from memcommit.context import Context
from memcommit.interfaces.tui.components.operation_launcher.session import SessionNewReceipt, SessionOpenReceipt
from memcommit.store import MemoryStore
from memcommit.query_provider import CodexChatGPTProvider


runner = CliRunner()


def test_compare_launcher_passes_exact_setup_memories_to_command(
    isolated_store,
    monkeypatch,
):
    monkeypatch.setattr(
        compare_command,
        "choose_comparison_session",
        lambda _store, *, ledger: SessionNewReceipt(
            kind="compare",
            argv=("mem", "compare"),
        ),
    )
    monkeypatch.setattr(
        compare_command,
        "choose_compare_setup",
        lambda _store: CompareSetupReceipt(
            "focused/reference",
            "focused/peer",
            reference_memory_uid="reference-memory",
            compared_memory_uid="peer-memory",
        ),
    )
    calls = []
    monkeypatch.setattr(compare_command, "cmd", lambda **kwargs: calls.append(kwargs))

    result = runner.invoke(app, ["compare", "--sessions"])

    assert result.exit_code == 0, result.output
    assert calls == [
        {
            "from_": "focused/reference",
            "to": "focused/peer",
            "refresh": False,
            "ledger": False,
            "snapshot": False,
            "reference_descendants": False,
            "compared_descendants": False,
            "reference_memory": "reference-memory",
            "compared_memory": "peer-memory",
        }
    ]


def test_compare_codex_provider_uses_whole_ledger_timeout():
    provider = CodexChatGPTProvider(
        binary=Path("codex"),
        env={},
        timeout=600,
    )

    connected = compare_command._connect_compare_provider(lambda: provider)

    assert connected is provider
    assert provider.timeout == compare_command.COMPARE_AGGREGATE_TIMEOUT_SECONDS


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
            "reports": {
                "both": (
                    "Both advisors require a concise proposal under the "
                    "same scope."
                ),
                "differences": "",
                "reference_only": (
                    "The reference alone adds guidance about headings."
                    if len(reference) > 1
                    else ""
                ),
                "compared_only": (
                    "The compared peer alone adds terminology guidance."
                    if len(compared) > 1
                    else ""
                ),
            },
            "relations": relations,
            "issues": [],
        }

    @staticmethod
    def source_indexed_response(
        response: dict[str, object],
    ) -> dict[str, object]:
        assignments: list[dict[str, str]] = []
        for relation in response["relations"]:
            relation_key = relation["relation_key"]
            for source_id in relation.pop("reference_memory_ids"):
                assignments.append(
                    {
                        "source_memory_id": source_id,
                        "relation_key": relation_key,
                    }
                )
            for source_id in relation.pop("compared_memory_ids"):
                assignments.append(
                    {
                        "source_memory_id": source_id,
                        "relation_key": relation_key,
                    }
                )
        response["source_assignments"] = assignments
        return response

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "compare_contexts"
        assert output_schema is not None
        assert set(output_schema["required"]) == {
            "overview",
            "reports",
            "relations",
            "source_assignments",
            "issues",
        }
        # Codex structured output rejects JSON Schema uniqueItems. The strict
        # parser below the schema remains the authority for alias uniqueness.
        assert "uniqueItems" not in json.dumps(output_schema)
        assert "target" not in json.dumps(output_schema).lower()
        assert "miscellaneous bucket" in prompt
        assert "Do not state relation counts in overview" in prompt
        assert "roughly 40-50 words at most" in prompt
        assert "within roughly 150 English words at most" in prompt
        assert (
            "normally no more than roughly 40-50 words"
            in output_schema["properties"]["overview"]["description"]
        )
        assert (
            "share the remaining first-frame attention budget"
            in output_schema["properties"]["reports"]["properties"]["both"][
                "description"
            ]
        )
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
        return json.dumps(self.source_indexed_response(builder(payload)))


def test_compare_output_schema_requires_one_assignment_per_frozen_source():
    source_ids = ("m1_000001", "m2_000001", "m2_000002")

    schema = comparison_output_schema(source_ids)

    assignments = schema["properties"]["source_assignments"]
    assert assignments["minItems"] == len(source_ids)
    assert assignments["maxItems"] == len(source_ids)
    assert assignments["items"]["properties"]["source_memory_id"]["enum"] == list(
        source_ids
    )
    relation_properties = schema["properties"]["relations"]["items"][
        "properties"
    ]
    assert "reference_memory_ids" not in relation_properties
    assert "compared_memory_ids" not in relation_properties


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


def test_focused_compare_relates_only_selected_memories_and_keeps_neighbors_context_only():
    reference = ops.init("focused/reference")
    reference_neighbor = ops.add(reference, "Reference background policy.")
    reference_focus = ops.add(reference, "The lobby closes at five.")
    compared = ops.init("focused/compared")
    compared_focus = ops.add(compared, "The lobby shuts at 5 p.m.")
    compared_neighbor = ops.add(compared, "Compared background policy.")
    comparison_input = ComparisonInput.from_contexts(
        reference,
        compared,
        reference_memory_selector=reference_focus.uid[:8],
        compared_memory_selector=compared_focus.uid[:8],
    )
    provider = ExhaustiveCompareProvider()

    analysis = analyze_comparison(comparison_input, provider)
    payload = provider.payloads[0]

    assert [memory.uid for memory in analysis.frames[0].memories] == [
        reference_focus.uid
    ]
    assert [memory.uid for memory in analysis.frames[1].memories] == [
        compared_focus.uid
    ]
    assert payload["frames"][0]["context_evidence"][0]["content"] == (
        reference_neighbor.content
    )
    assert payload["frames"][1]["context_evidence"][0]["content"] == (
        compared_neighbor.content
    )
    assert "context_id" not in json.dumps(provider.schemas[0])
    assert {
        member.memory_uid for member in analysis.relations[0].members
    } == {reference_focus.uid, compared_focus.uid}


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
    assert "METRICS · MEMORIES 2 + 2 · RELATIONS 3 · POTENTIAL CONFLICTS 0" in (
        created.output
    )
    assert created.output.index("METRICS ·") < created.output.index(
        "WHAT MEM UNDERSTOOD"
    )
    assert "WHAT BOTH CONTAIN · 1" in created.output
    assert (
        "ONLY IN task2/advisor1 · 1 · "
        "not automatically a deficiency"
    ) in created.output
    assert (
        "ONLY IN task2/advisor2 · 1 · "
        "not automatically a deficiency"
    ) in created.output
    assert "Both advisors require a concise proposal" in created.output
    assert "The reference alone adds guidance about headings." in (
        created.output
    )
    assert (
        "The complete source-linked relation ledger is saved. "
        "Inspect it with:\n"
        "  mem compare --from task2/advisor1 --to task2/advisor2 --ledger"
    ) in (
        created.output
    )
    assert "Create a new result Context" not in created.output
    assert "mem meld" not in created.output
    assert created.output.rstrip().endswith(
        "mem compare --from task2/advisor1 --to task2/advisor2 --ledger"
    )
    assert "\nWHAT DIFFERS" not in created.output
    assert "\nPOTENTIAL CONFLICTS" not in created.output
    assert reference.uid[:8] not in created.output
    assert next(iter(reference.memories))[:8] not in created.output
    assert next(iter(compared.memories))[:8] not in created.output
    assert "\n      REF " not in created.output
    assert "\n      TO  " not in created.output
    assert "\n      WHY ·" not in created.output
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
    expected_members = {
        (frame.uid, memory.uid)
        for frame in saved.frames
        for memory in frame.memories
    }
    observed_members = {
        (member.frame_uid, member.memory_uid)
        for relation in saved.relations
        for member in relation.members
    }
    assert observed_members == expected_members

    ledger = runner.invoke(
        app,
        ["compare", "--to", compared.name, "--ledger"],
    )

    assert ledger.exit_code == 0, ledger.output
    assert "REUSED" in ledger.output
    assert "RELATION LEDGER · 3" in ledger.output
    assert next(iter(reference.memories))[:8] in ledger.output
    assert next(iter(compared.memories))[:8] in ledger.output
    assert "\n      REF " in ledger.output
    assert "\n      TO  " in ledger.output
    assert "\n      WHY ·" in ledger.output
    assert "\nWHAT DIFFERS\n  (none)" in ledger.output
    assert "\nPOTENTIAL CONFLICTS · 0\n  (none)" in ledger.output
    assert "complete source-linked relation ledger is saved" not in (
        ledger.output
    )
    assert len(provider.payloads) == 1

    resumed = runner.invoke(
        app,
        ["compare", "--to", compared.name],
    )

    assert resumed.exit_code == 0, resumed.output
    assert "REUSED" in resumed.output
    assert len(provider.payloads) == 1
    assert path.read_bytes() == saved_before


def test_compare_descendant_flags_freeze_lexical_child_memories(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    reference = ops.init("scoped/reference")
    reference_child = ops.init("scoped/reference/child")
    ops.add(reference_child, "Reference child policy.")
    compared = ops.init("scoped/compared")
    compared_child = ops.init("scoped/compared/child")
    ops.add(compared_child, "Compared child policy.")
    for context in (reference, reference_child, compared, compared_child):
        store.create_context(context)
    store.set_current(reference.name)
    provider = ExhaustiveCompareProvider()
    _patch_provider(monkeypatch, provider)

    result = runner.invoke(
        app,
        [
            "compare",
            "--to",
            compared.name,
            "-r",
            "--snapshot",
        ],
    )
    analysis = load_comparison_analysis(reference.uid, compared.uid)

    assert result.exit_code == 0, result.output
    assert analysis is not None
    assert analysis.include_descendants == (True, True)
    assert "[scoped/reference/child] Reference child policy." in {
        memory.content for memory in analysis.frames[0].memories
    }
    assert "[scoped/compared/child] Compared child policy." in {
        memory.content for memory in analysis.frames[1].memories
    }


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


def test_relative_peer_locator_uses_active_namespace_and_reuses_cache(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    reference, compared = _task2_contexts(store)
    provider = ExhaustiveCompareProvider()
    _patch_provider(monkeypatch, provider)

    relative = runner.invoke(
        app,
        ["compare", "--to", "../advisor2"],
    )

    assert relative.exit_code == 0, relative.output
    assert "Reference: task2/advisor1" in relative.output
    assert "Compared:  task2/advisor2" in relative.output
    assert "NEW" in relative.output
    assert len(provider.payloads) == 1
    saved = load_comparison_analysis(reference.uid, compared.uid)
    assert saved is not None
    assert [frame.context_name for frame in saved.frames] == [
        "task2/advisor1",
        "task2/advisor2",
    ]

    canonical = runner.invoke(
        app,
        ["compare", "--to", compared.name],
    )

    assert canonical.exit_code == 0, canonical.output
    assert "REUSED" in canonical.output
    assert len(provider.payloads) == 1


def test_relative_peer_locator_errors_before_provider(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    reference, _ = _task2_contexts(store)
    provider = ExhaustiveCompareProvider()
    _patch_provider(monkeypatch, provider)

    missing = runner.invoke(
        app,
        ["compare", "--to", "../missing"],
    )
    same = runner.invoke(
        app,
        ["compare", "--to", "."],
    )
    malformed = runner.invoke(
        app,
        ["compare", "--to", "..//advisor2"],
    )

    assert missing.exit_code == 1
    assert (
        "Compared Context '../missing' "
        "(resolved to 'task2/missing') does not exist"
    ) in missing.output
    assert same.exit_code == 1
    assert "two distinct Contexts" in same.output
    assert malformed.exit_code == 1
    assert "contains an empty segment" in malformed.output
    assert provider.payloads == []
    assert store.current_context_name() == reference.name


def test_compare_explicit_from_does_not_change_current_context(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    reference, compared = _task2_contexts(store)
    orientation = ops.init("orientation/only")
    store.create_context(orientation)
    store.set_current(orientation.name)
    provider = ExhaustiveCompareProvider()
    _patch_provider(monkeypatch, provider)

    result = runner.invoke(
        app,
        [
            "compare",
            "--from",
            reference.name,
            "--to",
            compared.name,
            "--snapshot",
        ],
    )

    assert result.exit_code == 0, result.output
    assert len(provider.payloads) == 1
    assert store.current_context_name() == orientation.name


def test_compare_explicit_endpoints_work_without_current_context(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    reference, compared = _task2_contexts(store)
    store._write_state({"current": None})
    provider = ExhaustiveCompareProvider()
    _patch_provider(monkeypatch, provider)

    result = runner.invoke(
        app,
        [
            "compare",
            "--from",
            reference.name,
            "--to",
            compared.name,
            "--snapshot",
        ],
    )

    assert result.exit_code == 0, result.output
    assert len(provider.payloads) == 1
    assert store.current_context_name() is None


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
            "reports": {
                "both": "",
                "differences": (
                    "The advisors give incompatible directions for the "
                    "same case."
                ),
                "reference_only": (
                    "Only the reference supplies a heading policy."
                ),
                "compared_only": "",
            },
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
    rendered = render_comparison(analysis, reused=False)
    assert "WHAT DIFFERS · 1" in rendered
    assert "POTENTIAL CONFLICTS · 1" in rendered
    assert "[REQUIRED]" not in rendered
    assert "RELATED · R1" not in rendered
    assert "Preserve explicit alternatives:" in rendered
    assert rendered.rfind("POTENTIAL CONFLICTS") < rendered.rfind(
        "The complete source-linked relation ledger"
    )
    assert rendered.rstrip().endswith(
        "mem compare --from task2/advisor1 --to task2/advisor2 --ledger"
    )


def test_provider_requires_the_complete_report_object(
    isolated_store,
):
    store = MemoryStore()
    reference, compared = _task2_contexts(store)

    def missing_reports(payload):
        response = ExhaustiveCompareProvider.default_response(payload)
        response.pop("reports")
        return response

    with pytest.raises(
        ComparisonProviderError,
        match="invalid comparison response",
    ):
        analyze_comparison(
            ComparisonInput.from_contexts(reference, compared),
            ExhaustiveCompareProvider(missing_reports),
        )


@pytest.mark.parametrize(
    ("report_name", "replacement"),
    [
        ("both", ""),
        ("differences", "A difference that has no supporting relation."),
    ],
)
def test_report_presence_must_match_the_validated_relation_group(
    isolated_store,
    report_name,
    replacement,
):
    store = MemoryStore()
    reference, compared = _task2_contexts(store)

    def mismatched_report(payload):
        response = ExhaustiveCompareProvider.default_response(payload)
        response["reports"][report_name] = replacement
        return response

    with pytest.raises(
        ComparisonProviderError,
        match=f"{report_name.replace('_', '-')} report",
    ):
        analyze_comparison(
            ComparisonInput.from_contexts(reference, compared),
            ExhaustiveCompareProvider(mismatched_report),
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
    value["schema_version"] = 1
    value["ruleset_version"] = "peer-relations-v2"
    value.pop("reports")
    value.pop("include_descendants")
    path.write_text(json.dumps(value))
    older = load_comparison_analysis(reference.uid, compared.uid)
    assert older is not None
    assert older.ruleset_version == "peer-relations-v2"
    assert older.reports is None
    assert older.to_dict()["schema_version"] == 1
    assert "reports" not in older.to_dict()

    replaced = runner.invoke(
        app,
        ["compare", "--to", compared.name],
    )

    assert replaced.exit_code == 0, replaced.output
    assert "NEW" in replaced.output
    assert len(provider.payloads) == 2
    current = load_comparison_analysis(reference.uid, compared.uid)
    assert current is not None
    assert current.ruleset_version == "peer-relations-v3"


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


def test_ordered_slot_exact_version_rejects_same_uid_content_replacement(
    isolated_store,
):
    store = MemoryStore()
    reference, compared = _task2_contexts(store)
    initial = analyze_comparison(
        ComparisonInput.from_contexts(reference, compared),
        ExhaustiveCompareProvider(),
    )
    save_comparison_analysis(store, initial, expected_analysis_uid=None)
    reviewed_version = comparison_canonical_digest(initial.to_dict())
    same_identity = replace(
        initial,
        understanding=replace(
            initial.understanding,
            text="A separately written summary with the same analysis UID.",
        ),
    )
    save_comparison_analysis(
        store,
        same_identity,
        expected_analysis_uid=initial.uid,
    )
    replacement = analyze_comparison(
        ComparisonInput.from_contexts(reference, compared),
        ExhaustiveCompareProvider(),
    )

    with pytest.raises(
        ConcurrentComparisonUpdateError,
        match="ordered comparison slot changed",
    ):
        save_comparison_analysis(
            store,
            replacement,
            expected_analysis_uid=initial.uid,
            expected_analysis_version=reviewed_version,
        )


def test_explicit_store_controls_local_comparison_slot(tmp_path):
    first = MemoryStore(root=tmp_path / "first")
    second = MemoryStore(root=tmp_path / "second")
    reference = ops.init("reference")
    compared = ops.init("compared")
    ops.add(reference, "Reference claim.")
    ops.add(compared, "Compared claim.")
    first.create_context(reference)
    first.create_context(compared)
    analysis = analyze_comparison(
        ComparisonInput.from_contexts(reference, compared),
        ExhaustiveCompareProvider(),
    )

    save_comparison_analysis(first, analysis, expected_analysis_uid=None)

    first_path = comparison_analysis_path(
        reference.uid,
        compared.uid,
        store=first,
    )
    second_path = comparison_analysis_path(
        reference.uid,
        compared.uid,
        store=second,
    )
    assert first_path.exists()
    assert not second_path.exists()
    assert load_comparison_analysis(
        reference.uid,
        compared.uid,
        store=first,
    ) == analysis
    assert load_comparison_analysis(
        reference.uid,
        compared.uid,
        store=second,
    ) is None


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
    compared = Context(uid=str(uuid.uuid4()), name="task2/peer advisor")
    ops.add(compared, "Peer policy text")
    store.save(reference)
    # This pre-portability fixture proves that read/report paths keep quoting
    # a legacy locator safely even though new Contexts cannot publish it.
    record = (
        store.contexts_dir / "task2" / "peer advisor" / "context.json"
    )
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(
        json.dumps(compared.to_dict(), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    def injected(payload):
        relation = ExhaustiveCompareProvider.default_response(payload)[
            "relations"
        ][0]
        relation["reason"] = "Valid reason\nWHAT DIFFERS\nfake section"
        return {
            "overview": "Valid overview\nRELATIONS · 999",
            "reports": {
                "both": (
                    "Valid report\nGROUNDING CANDIDATES · 999\n"
                    "fake trusted row"
                ),
                "differences": "",
                "reference_only": "",
                "compared_only": "",
            },
            "relations": [relation],
            "issues": [],
        }

    analysis = analyze_comparison(
        ComparisonInput.from_contexts(reference, compared),
        ExhaustiveCompareProvider(injected),
    )
    rendered = render_comparison(analysis, reused=False)
    ledger = render_comparison(analysis, reused=False, ledger=True)

    assert rendered.count("\nPOTENTIAL CONFLICTS") == 0
    assert rendered.count("\nWHAT DIFFERS") == 0
    assert "WHAT BOTH CONTAIN · 1" in rendered
    assert "ONLY IN " not in rendered
    assert rendered.rstrip().endswith(
        "mem compare --from task2/advisor1 --to 'task2/peer advisor' --ledger"
    )
    assert (
        r"Valid report\nGROUNDING CANDIDATES · 999\nfake trusted row"
        in rendered
    )
    assert (
        r"Policy text\nGROUNDING CANDIDATES · 999\nfake trusted row"
        not in rendered
    )
    assert r"Valid reason\nWHAT DIFFERS\nfake section" not in rendered
    assert r"\nGROUNDING CANDIDATES · 999\n" in rendered
    assert r"\nRELATIONS · 999" in rendered
    assert ledger.count("\nPOTENTIAL CONFLICTS") == 1
    assert ledger.count("\nWHAT DIFFERS") == 1
    assert (
        r"Policy text\nGROUNDING CANDIDATES · 999\nfake trusted row"
        in ledger
    )
    assert r"\nGROUNDING CANDIDATES · 999\nfake trusted row" in (
        ledger
    )
    assert r"\nWHAT DIFFERS\nfake section" in ledger


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


def test_compare_sessions_catalog_and_bare_picker_are_provider_free(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    reference, compared = _task2_contexts(store)
    provider = ExhaustiveCompareProvider()
    _patch_provider(monkeypatch, provider)
    created = runner.invoke(app, ["compare", "--to", compared.name])
    assert created.exit_code == 0, created.output
    analysis = load_comparison_analysis(reference.uid, compared.uid)
    assert analysis is not None

    entries = comparison_session_entries(store)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.key == analysis.uid
    assert entry.title == f"{reference.name} ↔ {compared.name}"
    assert entry.group == reference.name
    assert entry.status == "CURRENT"
    assert entry.reopen_argv == (
        "mem",
        "compare",
        "--to",
        compared.name,
    )
    assert entry.detail_only is True
    assert entry.detail.startswith("MEM COMPARE · SYMMETRIC PEERS")
    assert "WHAT MEM UNDERSTOOD" in entry.detail
    assert "WHAT BOTH CONTAIN" in entry.detail

    unrelated = ops.init("unrelated/current")
    ops.add(unrelated, "This Context is not a comparison source.")
    store.save(unrelated)
    store.set_current(unrelated.name)
    monkeypatch.setattr(
        "memcommit.commands.compare.choose_comparison_session",
        lambda _store, *, ledger: SessionOpenReceipt(
            kind="compare",
            key=entry.key,
            argv=entry.reopen_argv,
        ),
    )

    def provider_must_not_connect():
        raise AssertionError("saved Compare selection must be provider-free")

    monkeypatch.setattr(
        "memcommit.commands.compare.connect_codex_chatgpt_provider",
        provider_must_not_connect,
    )
    resumed = runner.invoke(app, ["compare"])

    assert resumed.exit_code == 0, resumed.output
    assert "REUSED" in resumed.output
    assert f"Reference: {reference.name}" in resumed.output
    assert f"Compared:  {compared.name}" in resumed.output
    assert store.current_context_name() == unrelated.name
    assert len(provider.payloads) == 1


def test_compare_sessions_empty_and_forged_receipts_fail_closed(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    monkeypatch.setattr(
        "memcommit.commands.compare_sessions.choose_session",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("empty catalog must not open the picker")
        ),
    )

    assert choose_comparison_session(store) is None
    empty = runner.invoke(app, ["compare"])
    assert empty.exit_code == 0, empty.output
    assert "Compare selection ended; no analysis was opened." in empty.output

    class TTY:
        @staticmethod
        def isatty():
            return True

    monkeypatch.setattr(compare_sessions_module.sys, "stdin", TTY())
    monkeypatch.setattr(compare_sessions_module.sys, "stdout", TTY())
    new_receipt = SessionNewReceipt(kind="compare", argv=("mem", "compare"))
    monkeypatch.setattr(
        "memcommit.commands.compare_sessions.choose_session",
        lambda entries, **kwargs: (
            new_receipt
            if entries == () and kwargs["new_receipt"] == new_receipt
            else pytest.fail("empty Compare must offer the exact New receipt")
        ),
    )
    # Compare constructs an equivalent immutable receipt for the picker.
    opened = choose_comparison_session(store)
    assert opened == new_receipt

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
    monkeypatch.setattr(
        "memcommit.commands.compare_sessions.choose_session",
        lambda *_args, **_kwargs: SessionOpenReceipt(
            kind="compare",
            key=analysis.uid,
            argv=("mem", "compare", "--refresh", "--to", compared.name),
        ),
    )

    with pytest.raises(ValueError, match="forged receipt"):
        choose_comparison_session(store)


def test_compare_session_selection_revalidates_sources_without_refresh(
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
    entry = comparison_session_entries(store)[0]

    def change_source(_store, *, ledger):
        changed = store.load_direct(reference.name)
        ops.add(changed, "A source changed after picker discovery.")
        store.save(changed)
        return SessionOpenReceipt(
            kind="compare",
            key=analysis.uid,
            argv=entry.reopen_argv,
        )

    monkeypatch.setattr(
        "memcommit.commands.compare.choose_comparison_session",
        change_source,
    )
    monkeypatch.setattr(
        "memcommit.commands.compare.connect_codex_chatgpt_provider",
        lambda: (_ for _ in ()).throw(
            AssertionError("stale selection must not refresh")
        ),
    )

    result = runner.invoke(app, ["compare", "--sessions"])

    assert result.exit_code == 1
    assert "changed after this comparison was saved" in result.output
    saved = load_comparison_analysis(reference.uid, compared.uid)
    assert saved is not None and saved.uid == analysis.uid


def test_compare_picker_options_do_not_expand_refresh_authority(
    isolated_store,
):
    combined = runner.invoke(
        app,
        ["compare", "--sessions", "--to", "peer"],
    )
    refresh_without_pair = runner.invoke(app, ["compare", "--refresh"])

    assert combined.exit_code == 2
    assert "either --sessions or --to" in combined.output
    assert refresh_without_pair.exit_code == 2
    assert "--refresh requires an explicit --to" in refresh_without_pair.output
