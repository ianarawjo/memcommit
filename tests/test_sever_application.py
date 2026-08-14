"""Application-boundary contracts for terminal-independent Sever execution."""

from __future__ import annotations

import ast
from dataclasses import replace
import json
from pathlib import Path

import pytest

import memcommit.ops as ops
from memcommit.sever import (
    SeverApplication,
    SeverCandidate,
    SeverContextBinding,
    SeverMemory,
    SeverSession,
)
import memcommit.sever_application as sever_application
from memcommit.sever_application import (
    FrozenSeverInputs,
    SeverAnalysisProgress,
    SeverAnalysisRequest,
    SeverApplicationError,
    SeverApplyRequest,
    SeverPreparedAnalysis,
    SeverPreparedOrigin,
    run_sever_analysis,
    run_sever_apply,
)
from memcommit.sever_provider import SEVER_PAYLOAD_MARKER
import memcommit.sever_runtime as sever_runtime
from memcommit.sever_runtime import execute_sever_analysis, execute_sever_apply
from memcommit.store import MemoryStore


SOURCE_CONTEXT_UID = "11111111-1111-4111-8111-111111111111"
CRITERIA_CONTEXT_UID = "22222222-2222-4222-8222-222222222222"
SOURCE_MEMORY_UID = "33333333-3333-4333-8333-333333333333"
CRITERIA_MEMORY_UID = "44444444-4444-4444-8444-444444444444"
SESSION_UID = "55555555-5555-4555-8555-555555555555"
CANDIDATE_UID = "66666666-6666-4666-8666-666666666666"


def _binding(
    *,
    context_uid: str,
    memory_uid: str,
    name: str,
    content: str,
) -> SeverContextBinding:
    return SeverContextBinding(
        root_uid=context_uid,
        root_name=name,
        frame_digest="a" * 64,
        contexts=((name, context_uid, "b" * 64),),
        memories=(
            SeverMemory(
                uid=memory_uid,
                context_name=name,
                content=content,
            ),
        ),
        include_descendants=False,
    )


def _inputs() -> FrozenSeverInputs:
    return FrozenSeverInputs(
        source=_binding(
            context_uid=SOURCE_CONTEXT_UID,
            memory_uid=SOURCE_MEMORY_UID,
            name="source",
            content="Keep only the access requirement.",
        ),
        criteria=_binding(
            context_uid=CRITERIA_CONTEXT_UID,
            memory_uid=CRITERIA_MEMORY_UID,
            name="criteria",
            content="Minimize unrelated personal detail.",
        ),
    )


def _review(inputs: FrozenSeverInputs, *, output_name: str = "result") -> SeverSession:
    return SeverSession(
        uid=SESSION_UID,
        revision=1,
        state="REVIEWING",
        source=inputs.source,
        criteria=inputs.criteria,
        output_name=output_name,
        overview="The result retains only the necessary access requirement.",
        candidates=(
            SeverCandidate(
                uid=CANDIDATE_UID,
                source_memory_uid=inputs.source.memories[0].uid,
                recommendation="KEEP_SUMMARY",
                proposed_content="Needs step-free access.",
                rationale="The criterion permits the necessary access requirement.",
                criterion_memory_uids=(inputs.criteria.memories[0].uid,),
            ),
        ),
    )


class _StaticInputPort:
    def __init__(self, inputs: FrozenSeverInputs):
        self.inputs = inputs
        self.requests: list[SeverAnalysisRequest] = []

    def freeze(self, request: SeverAnalysisRequest) -> FrozenSeverInputs:
        self.requests.append(request)
        return self.inputs


class _Provider:
    def __init__(self):
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls += 1
        assert operation == "sever_context"
        payload = json.loads(prompt.split(SEVER_PAYLOAD_MARKER, 1)[1])
        source_id = payload["source"]["memories"][0]["memory_id"]
        criterion_id = payload["criteria"]["memories"][0]["memory_id"]
        return json.dumps(
            {
                "overview": "The result retains only the necessary access requirement.",
                "application_summary": {
                    "text": "The access requirement was condensed under minimization.",
                    "source_memory_ids": [source_id],
                    "criterion_memory_ids": [criterion_id],
                },
                "candidates": [
                    {
                        "source_memory_id": source_id,
                        "decision": "KEEP_SUMMARY",
                        "proposed_content": "Needs step-free access.",
                        "rationale": (
                            "The criterion permits the necessary access requirement."
                        ),
                        "criterion_memory_ids": [criterion_id],
                    }
                ],
            }
        )


def test_run_sever_analysis_converges_on_one_typed_request_without_terminal():
    inputs = _inputs()
    input_port = _StaticInputPort(inputs)
    provider = _Provider()
    provider_calls = 0
    stages: list[SeverAnalysisProgress] = []
    request = SeverAnalysisRequest(
        source_locator="source",
        criteria_locator="criteria",
        output_name="result",
        source_include_descendants=False,
        criteria_include_descendants=False,
    )

    def provider_factory():
        nonlocal provider_calls
        provider_calls += 1
        return provider

    result = run_sever_analysis(
        request,
        input_port=input_port,
        provider_factory=provider_factory,
        progress_observer=stages.append,
    )

    assert input_port.requests == [request]
    assert provider_calls == 1
    assert provider.calls == 1
    assert [event.stage for event in stages] == [
        "INPUTS_FROZEN",
        "CONNECTING_PROVIDER",
        "ANALYZING",
    ]
    assert result.origin == "PROVIDER"
    assert result.session.source == inputs.source
    assert result.session.criteria == inputs.criteria
    assert result.session.output_name == "result"


@pytest.mark.parametrize(
    "origin",
    (
        "EXACT_PREWARM",
        "EQUIVALENT_SCOPE_PREWARM",
        "PROJECTED_PREWARM",
    ),
)
def test_prepared_review_retains_origin_and_never_constructs_provider(
    origin: SeverPreparedOrigin,
):
    inputs = _inputs()
    stages: list[SeverAnalysisProgress] = []

    result = run_sever_analysis(
        SeverAnalysisRequest("source", "criteria", "result", False, False),
        input_port=_StaticInputPort(inputs),
        provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("an exact prepared review must not construct a provider")
        ),
        prepared_lookup=lambda frozen, output: SeverPreparedAnalysis(
            session=_review(frozen, output_name=output),
            origin=origin,
        ),
        progress_observer=stages.append,
    )

    assert result.origin == origin
    assert [event.stage for event in stages] == [
        "INPUTS_FROZEN",
        "PREPARED_REUSED",
    ]


def test_prepared_review_cannot_change_frozen_source_or_output():
    inputs = _inputs()
    other_source = replace(inputs.source, root_name="other-source")
    invalid = replace(
        _review(inputs),
        source=other_source,
        output_name="other-result",
    )

    with pytest.raises(SeverApplicationError, match="outside the frozen request"):
        run_sever_analysis(
            SeverAnalysisRequest("source", "criteria", "result", False, False),
            input_port=_StaticInputPort(inputs),
            provider_factory=lambda: (_ for _ in ()).throw(
                AssertionError("invalid prepared review must not reach provider")
            ),
            prepared_lookup=lambda _inputs, _output: SeverPreparedAnalysis(
                session=invalid,
                origin="PROJECTED_PREWARM",
            ),
        )


def test_run_sever_apply_validates_receipt_and_is_idempotent():
    session = _review(_inputs())
    materialized: list[SeverSession] = []

    class OutputPort:
        def materialize(self, review: SeverSession) -> SeverSession:
            materialized.append(review)
            return review.with_application(
                SeverApplication(
                    output_context_uid="77777777-7777-4777-8777-777777777777",
                    checkpoint_uid="88888888-8888-4888-8888-888888888888",
                    result_memory_uids=(
                        "99999999-9999-4999-8999-999999999999",
                    ),
                )
            )

    first = run_sever_apply(
        SeverApplyRequest(session),
        output_port=OutputPort(),
    )
    second = run_sever_apply(
        SeverApplyRequest(first.session),
        output_port=OutputPort(),
    )

    assert materialized == [session]
    assert first.created is True
    assert first.session.state == "APPLIED"
    assert second.created is False
    assert second.session is first.session


def test_sever_application_has_no_command_typer_or_tui_imports():
    source = Path(sever_application.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)

    forbidden = tuple(
        name
        for name in imported
        if name == "typer"
        or name.startswith("prompt_toolkit")
        or name.startswith("memcommit.commands")
    )
    assert forbidden == ()


def test_sever_runtime_has_no_typer_or_tui_imports():
    source = Path(sever_runtime.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)

    forbidden = tuple(
        name
        for name in imported
        if name == "typer" or name.startswith("prompt_toolkit")
    )
    assert forbidden == ()


def test_real_store_analysis_and_apply_are_terminal_free_and_preserve_source(
    isolated_store,
    capsys,
):
    store = MemoryStore()
    source = ops.init("application/source")
    ops.add(source, "Keep only the access requirement.")
    criteria = ops.init("application/criteria")
    ops.add(criteria, "Minimize unrelated personal detail.")
    store.create_context(source)
    store.create_context(criteria)
    provider = _Provider()

    analysis = execute_sever_analysis(
        SeverAnalysisRequest(
            source_locator=source.name,
            criteria_locator=criteria.name,
            output_name="application/result",
            source_include_descendants=False,
            criteria_include_descendants=False,
        ),
        store=store,
        provider_factory=lambda: provider,
    )

    assert analysis.origin == "PROVIDER"
    assert provider.calls == 1
    assert not store.context_exists("application/result")
    before = store.load_direct(source.name).to_dict()

    applied = execute_sever_apply(
        SeverApplyRequest(analysis.session),
        store=store,
    )

    assert applied.created is True
    assert applied.session.application is not None
    assert store.load_direct(source.name).to_dict() == before
    result = store.load_direct("application/result")
    assert [item.content for item in result.iter_items()] == [
        "Needs step-free access."
    ]
    [checkpoint] = store.list_checkpoints("application/result")
    assert checkpoint["command"] == "sever"
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_runtime_retains_projected_cache_origin_and_skips_provider(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("projection/source")
    ops.add(source, "Keep only the access requirement.")
    criteria = ops.init("projection/criteria")
    ops.add(criteria, "Minimize unrelated personal detail.")
    store.create_context(source)
    store.create_context(criteria)
    lookups = []

    def projected_lookup(*, store, source, criteria, output_name):
        lookups.append((store, source, criteria, output_name))

        class Match:
            session = _review(
                FrozenSeverInputs(source=source, criteria=criteria),
                output_name=output_name,
            )
            origin = "PROJECTED_PREWARM"

        return Match()

    monkeypatch.setattr(
        sever_runtime,
        "find_installed_projectable_sever_prewarm",
        projected_lookup,
    )

    result = execute_sever_analysis(
        SeverAnalysisRequest(
            source_locator=source.name,
            criteria_locator=criteria.name,
            output_name="projection/result",
            source_include_descendants=False,
            criteria_include_descendants=False,
        ),
        store=store,
        provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("projected prepared analysis must not construct provider")
        ),
    )

    assert result.origin == "PROJECTED_PREWARM"
    assert len(lookups) == 1
    assert lookups[0][3] == "projection/result"
    assert not store.context_exists("projection/result")


def test_real_store_rejects_missing_source_before_provider_construction(
    isolated_store,
):
    store = MemoryStore()
    criteria = ops.init("criteria")
    ops.add(criteria, "Criterion")
    store.create_context(criteria)
    provider_calls = 0

    def forbidden_provider():
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("missing input must fail before provider construction")

    with pytest.raises(FileNotFoundError, match="missing-source"):
        execute_sever_analysis(
            SeverAnalysisRequest(
                source_locator="missing-source",
                criteria_locator=criteria.name,
                output_name="result",
            ),
            store=store,
            provider_factory=forbidden_provider,
        )

    assert provider_calls == 0
