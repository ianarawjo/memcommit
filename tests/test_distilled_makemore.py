"""Process-local Distill→Makemore composition for Context-backed generation."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
import memcommit.adapters.console.commands.makemore.command as makemore_command
from memcommit.adapters.console.entrypoint import app
from memcommit.application.operations.distill.model import (
    DISTILL_OPERATION,
    DISTILL_PAYLOAD_MARKER,
)
from memcommit.application.operations.makemore.distilled_runtime import (
    apply_prepared_distilled_makemore_add,
    prepare_distilled_makemore_add,
)
from memcommit.application.operations.makemore.model import (
    MAKEMORE_OPERATION,
    MAKEMORE_PAYLOAD_MARKER,
    MakemoreError,
)
from memcommit.persistence.store import MemoryStore
from tests.makemore_validation_support import passing_makemore_validation_response


runner = CliRunner()


class _PipelineProvider:
    def __init__(self) -> None:
        self.operations: list[str] = []
        self.distill_payload: dict[str, object] | None = None
        self.makemore_payload: dict[str, object] | None = None

    def complete(self, prompt, *, operation, output_schema=None):
        self.operations.append(operation)
        validation = passing_makemore_validation_response(prompt, operation)
        if validation is not None:
            return validation
        if operation == DISTILL_OPERATION:
            payload = json.loads(prompt.split(DISTILL_PAYLOAD_MARKER, 1)[1])
            self.distill_payload = payload
            aliases = [item["memory_id"] for item in payload["source"]["memories"]]
            return json.dumps(
                {
                    "overview": "The Source supports one review-state family Rule.",
                    "rules": [
                        {
                            "content": "Record each review state as a short standalone Memory.",
                            "rationale": "The Source Memories use short review-state entries.",
                            "support_memory_ids": aliases[:1],
                            "boundary_memory_ids": [],
                        }
                    ],
                    "outside_memory_ids": aliases[1:],
                }
            )
        assert operation == MAKEMORE_OPERATION
        payload = json.loads(prompt.split(MAKEMORE_PAYLOAD_MARKER, 1)[1])
        self.makemore_payload = payload
        number = payload["number"]
        roles = ("FIT", "BOUNDARY", "CONTRAST")
        target_refs = {"target_context_refs": []} if "target_context" in payload else {}
        return json.dumps(
            {
                "overview": f"The transient Rule yields exactly {number} Cases.",
                "cases": [
                    {
                        "proposition": f"generated review state {index}",
                        "expected": f"Retain generated state {index} for review.",
                        "rationale": "This is a new member of the distilled family.",
                        "case_role": roles[(index - 1) % len(roles)],
                        "rule_checks": [
                            {
                                "source_rule_index": rule_index,
                                "evidence": "The Case is one short standalone Memory.",
                            }
                            for rule_index, _rule in enumerate(payload["inputs"], 1)
                        ],
                        **target_refs,
                    }
                    for index in range(1, number + 1)
                ],
            }
        )


def _context(store: MemoryStore, name: str, *contents: str):
    context = ops.init(name)
    for content in contents:
        ops.add(context, content)
    store.create_context(context)
    return context


def test_distilled_makemore_keeps_rules_transient_and_adds_only_final_cases(
    isolated_store,
) -> None:
    store = MemoryStore()
    context = _context(store, "pipeline/current", "reviewed", "reviewed")
    provider = _PipelineProvider()
    before_uids = tuple(store.load_direct(context.name).ordered_uids())

    prepared = prepare_distilled_makemore_add(
        store=store,
        source_name=context.name,
        target_name=context.name,
        provider_factory=lambda: provider,
        number=3,
        will_apply=True,
    )

    assert tuple(store.load_direct(context.name).ordered_uids()) == before_uids
    assert store.list_checkpoints(context.name) == []
    assert provider.operations == [DISTILL_OPERATION, MAKEMORE_OPERATION]
    assert prepared.result.analysis.inputs == (
        "Record each review state as a short standalone Memory.",
    )
    assert provider.makemore_payload is not None
    assert "target_context" not in provider.makemore_payload

    receipt = apply_prepared_distilled_makemore_add(prepared, store=store)

    current = store.load_direct(context.name)
    contents = [memory.content for memory in current.memories.values()]
    assert contents == [
        "reviewed",
        "reviewed",
        "generated review state 1",
        "generated review state 2",
        "generated review state 3",
    ]
    assert "Record each review state as a short standalone Memory." not in contents
    assert receipt.count == 3
    [checkpoint] = store.list_checkpoints(context.name)
    payload = checkpoint["args"]["makemore"]
    assert payload["version"] == 6
    assert payload["source_mode"] == "DISTILL_THEN_MAKEMORE"
    assert payload["source_context"] == context.name
    assert payload["distillation"]["rules"][0]["support_memory_uids"] == [
        before_uids[0]
    ]
    assert len(payload["result_memory_uids"]) == 3


def test_bare_mem_makemore_runs_the_distill_pipeline_with_default_count(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    context = _context(store, "pipeline/cli", "reviewed", "reviewed")
    store.set_current(context.name)
    provider = _PipelineProvider()
    monkeypatch.setattr(
        makemore_command,
        "connect_semantic_provider",
        lambda: provider,
    )

    result = runner.invoke(app, ["makemore"])

    assert result.exit_code == 0, result.output
    assert "PIPELINE · DISTILL → MAKEMORE · 1 TRANSIENT RULES" in result.output
    assert "MODE · RULES_TO_CASES · VERIFICATION · UNVERIFIED" in result.output
    assert "EFFECTS · ADD 3 MEMORIES" in result.output
    assert provider.operations == [DISTILL_OPERATION, MAKEMORE_OPERATION]
    [checkpoint] = store.list_checkpoints(context.name)
    assert checkpoint["args"]["makemore"]["source_mode"] == ("DISTILL_THEN_MAKEMORE")

    review = runner.invoke(
        app,
        [
            "review",
            "makemore",
            "--receipt",
            checkpoint["uid"][:8],
            "--snapshot",
        ],
    )
    assert review.exit_code == 0, review.output
    assert "PIPELINE · DISTILL → MAKEMORE" in review.output
    assert "TRANSIENT DISTILLED RULES · 1" in review.output
    assert "SUPPORT ·" in review.output
    assert "generated review state 1" in review.output


def test_context_as_rules_skips_the_distill_stage(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    source = _context(
        store,
        "pipeline/direct-rules",
        "Record each review state as a short standalone Memory.",
    )
    target = _context(store, "pipeline/direct-target")
    store.set_current(target.name)
    provider = _PipelineProvider()
    monkeypatch.setattr(
        makemore_command,
        "connect_semantic_provider",
        lambda: provider,
    )

    result = runner.invoke(
        app,
        [
            "makemore",
            "--from",
            source.name,
            "--to",
            target.name,
            "--as",
            "rules",
            "--number",
            "1",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "PIPELINE ·" not in result.output
    assert provider.operations == [MAKEMORE_OPERATION]
    [checkpoint] = store.list_checkpoints(target.name)
    assert checkpoint["args"]["makemore"]["version"] == 5
    assert "distillation" not in checkpoint["args"]["makemore"]


def test_distilled_makemore_target_drift_between_stages_fails_without_cases(
    isolated_store,
) -> None:
    store = MemoryStore()
    source = _context(store, "pipeline/source", "reviewed")
    target = _context(store, "pipeline/target", "existing target")

    class _DriftingProvider(_PipelineProvider):
        def complete(self, prompt, *, operation, output_schema=None):
            response = super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )
            if operation == DISTILL_OPERATION:
                changed = store.load_for_update(target.name)
                ops.add(changed, "concurrent target change")
                store.save(changed)
            return response

    provider = _DriftingProvider()

    with pytest.raises(MakemoreError, match="changed before Makemore began"):
        prepare_distilled_makemore_add(
            store=store,
            source_name=source.name,
            target_name=target.name,
            provider_factory=lambda: provider,
            will_apply=True,
        )

    assert provider.operations == [DISTILL_OPERATION]
    assert [
        memory.content for memory in store.load_direct(target.name).memories.values()
    ] == ["existing target", "concurrent target change"]
    assert store.list_checkpoints(target.name) == []


def test_distilled_makemore_source_drift_during_generation_publishes_nothing(
    isolated_store,
) -> None:
    store = MemoryStore()
    source = _context(store, "pipeline/drifting-source", "reviewed")
    target = _context(store, "pipeline/stable-target", "existing target")

    class _DriftingProvider(_PipelineProvider):
        def complete(self, prompt, *, operation, output_schema=None):
            response = super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )
            if operation == MAKEMORE_OPERATION:
                changed = store.load_for_update(source.name)
                ops.add(changed, "concurrent source change")
                store.save(changed)
            return response

    with pytest.raises(MakemoreError, match="Context Source changed"):
        prepare_distilled_makemore_add(
            store=store,
            source_name=source.name,
            target_name=target.name,
            provider_factory=_DriftingProvider,
            will_apply=True,
        )

    assert [
        memory.content for memory in store.load_direct(target.name).memories.values()
    ] == ["existing target"]
    assert store.list_checkpoints(target.name) == []
