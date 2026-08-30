from __future__ import annotations

import json
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.adapters.console.commands.fit.command as fit_command
import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.application.operations.fit.ground_report import (
    FIT_SCHEMA_VERSION,
    FitError,
    FitExample,
    FitRule,
    fit_ground_examples,
)
from memcommit.application.operations.fit.coherence import (
    FIT_COHERENCE_OPERATION,
    FIT_COHERENCE_PAYLOAD_MARKER,
)
from memcommit.application.operations.fit.runtime import (
    execute_and_save_ground_fit,
)
from memcommit.application.operations.fit.judgment import FIT_JUDGMENT_PAYLOAD_MARKER
from memcommit.application.operations.fit.store import FitStore
from memcommit.persistence.store import MemoryStore
from memcommit.application.operations.ground.workspace_application import (
    AddGroundWorkspaceMemoryRequest,
    CreateGroundWorkspaceRequest,
)
from memcommit.application.operations.ground.workspace_runtime import (
    execute_ground_workspace_creation,
    execute_ground_workspace_memory_add,
    load_ground_workspace,
)


def _uid() -> str:
    return str(uuid.uuid4())


class _Provider:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.prompt = ""
        self.operation = ""

    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        self.prompt = prompt
        self.operation = operation
        return json.dumps(self.response)


class _PhysicalGroundProvider:
    """Return all-fitting proposition and coherence judgments."""

    def __init__(self) -> None:
        self.operations: list[str] = []

    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        self.operations.append(operation)
        if operation == FIT_COHERENCE_OPERATION:
            payload = json.loads(prompt.split(FIT_COHERENCE_PAYLOAD_MARKER, 1)[1])
            return json.dumps(
                {
                    "overview": "The physical Ground graph stays aligned.",
                    "findings": [
                        {
                            **check,
                            "status": "FIT",
                            "material_aliases": [],
                            "reason": "The frozen relation stays coherent.",
                        }
                        for check in payload["checks"]
                    ],
                }
            )
        payload = json.loads(prompt.split(FIT_JUDGMENT_PAYLOAD_MARKER, 1)[1])
        return json.dumps(
            {
                "overview": "Every Rule and Example can jointly hold.",
                "judgments": [
                    {
                        "question_id": question["question_id"],
                        "verdict": "YES",
                        "reason": "The reviewed Example is compatible.",
                        "considered_proposition_ids": [
                            item["proposition_id"]
                            for item in (
                                *question["background"],
                                *question["propositions"],
                            )
                        ],
                        "material_proposition_ids": [],
                        "consistent_reading": "",
                        "inconsistent_reading": "",
                    }
                    for question in payload["questions"]
                ],
            }
        )


def _rule(statement: str = "Use the first four letters in uppercase.") -> FitRule:
    return FitRule(_uid(), "r1", statement)


def test_proposition_fit_accounts_for_observation_counterexample() -> None:
    rule = _rule("The sky is always blue.")
    example = FitExample(
        _uid(),
        "e1",
        "On August 15 the sky was yellow.",
        (rule.uid,),
    )
    provider = _Provider(
        {
            "overview": "The observation conflicts with the universal claim.",
            "judgments": [
                {
                    "question_id": "e1",
                    "verdict": "NO",
                    "reason": "One yellow observation refutes always blue.",
                    "considered_proposition_ids": ["r1", "e1"],
                    "material_proposition_ids": ["r1", "e1"],
                    "consistent_reading": "",
                    "inconsistent_reading": "",
                }
            ],
        }
    )
    report = fit_ground_examples(
        ground_uid=_uid(),
        ground_name="sky",
        ground_revision=1,
        ground_digest="b" * 64,
        rules=(rule,),
        examples=(example,),
        provider=provider,
    )

    assert report.judgments[0].status == "CONTRADICTS"
    assert provider.operation == "fit_propositions"
    assert "role-neutral compatibility judgment" in provider.prompt
    assert "MAY describes a real semantic split" in provider.prompt
    assert (
        "Missing support or an unknown fact is not itself a contradiction"
        in provider.prompt
    )
    assert "Do not omit, rank, retrieve, generate, revise" in provider.prompt
    serialized = report.to_dict()
    assert set(serialized["examples"][0]) == {
        "uid",
        "alias",
        "statement",
        "rule_uids",
    }
    assert set(serialized["judgments"][0]) == {
        "example_uid",
        "status",
        "rule_uids",
        "reason",
    }
    assert type(report).from_dict(serialized) == report

    serialized["schema_version"] = 2
    with pytest.raises(FitError, match="Unsupported"):
        type(report).from_dict(serialized)


def test_fit_rejects_incomplete_coverage() -> None:
    rule = _rule()
    proposition = FitExample(_uid(), "e1", "Apple maps to AAPL.", (rule.uid,))

    with pytest.raises(FitError, match="omitted"):
        fit_ground_examples(
            ground_uid=_uid(),
            ground_name="ticker",
            ground_revision=1,
            ground_digest="c" * 64,
            rules=(rule,),
            examples=(proposition,),
            provider=_Provider({"overview": "none", "judgments": []}),
        )


def test_mem_fit_has_no_viewer_route_and_fails_before_opening_storage(
    monkeypatch,
) -> None:
    def fail_store(*_args, **_kwargs):
        raise AssertionError("Fit must validate the TUI route before storage")

    monkeypatch.setattr(fit_command, "MemoryStore", fail_store)

    result = CliRunner().invoke(app, ["fit", "--ground", "ticker", "--tui"])

    assert result.exit_code == 2
    assert "No such option: --tui" in result.output


def _physical_fit_ground(store: MemoryStore) -> None:
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(
            name="physical-fit",
            goal="Learn how real US ticker symbols are assigned.",
        ),
        store=store,
    )
    for lane, content in (
        ("contexts", "Use actual US-listed companies and their real symbols."),
        ("rules", "Remove a trailing legal entity suffix when appropriate."),
        ("examples", "Apple Inc. is listed under AAPL."),
    ):
        execute_ground_workspace_memory_add(
            AddGroundWorkspaceMemoryRequest(
                workspace_name="physical-fit",
                lane=lane,
                content=content,
            ),
            store=store,
        )


def test_physical_ground_fit_saves_and_reopens_an_input_bound_receipt(
    isolated_store,
):
    store = MemoryStore()
    _physical_fit_ground(store)
    provider = _PhysicalGroundProvider()

    report = execute_and_save_ground_fit(
        store=store,
        ground_name="physical-fit",
        provider_factory=lambda: provider,
    )
    workspace = load_ground_workspace(store, "physical-fit")
    latest = FitStore(store).latest_for_workspace(workspace)

    assert latest is not None and latest.current
    assert latest.report.uid == report.uid
    assert report.schema_version == FIT_SCHEMA_VERSION
    assert report.coherence is not None
    assert report.issue_count == 0
    assert provider.operations == ["fit_propositions", FIT_COHERENCE_OPERATION]


def test_physical_fit_receipt_ignores_unconsumed_relation_but_tracks_rule(
    isolated_store,
):
    store = MemoryStore()
    _physical_fit_ground(store)
    report = execute_and_save_ground_fit(
        store=store,
        ground_name="physical-fit",
        provider_factory=_PhysicalGroundProvider,
    )
    execute_ground_workspace_memory_add(
        AddGroundWorkspaceMemoryRequest(
            workspace_name="physical-fit",
            lane="relations",
            content="The Goal is evaluated against all active Rules.",
        ),
        store=store,
    )
    after_relation = FitStore(store).latest_for_workspace(
        load_ground_workspace(store, "physical-fit")
    )
    assert after_relation is not None and after_relation.current
    assert after_relation.report.uid == report.uid

    execute_ground_workspace_memory_add(
        AddGroundWorkspaceMemoryRequest(
            workspace_name="physical-fit",
            lane="rules",
            content="A later consumed Rule.",
        ),
        store=store,
    )
    after_rule = FitStore(store).latest_for_workspace(
        load_ground_workspace(store, "physical-fit")
    )
    assert after_rule is not None and not after_rule.current


def test_physical_fit_rejects_typed_context_input_before_provider_construction(
    isolated_store,
):
    store = MemoryStore()
    _physical_fit_ground(store)
    source = ops.init("physical-fit/external-source")
    memory = ops.add(source, "An externally owned market observation.")
    store.create_context(source)
    contexts = store.load_for_update("physical-fit/contexts")
    ops.embed_memory(memory, source, contexts)
    store.save(contexts)
    provider_constructions = 0

    def provider_factory():
        nonlocal provider_constructions
        provider_constructions += 1
        return _PhysicalGroundProvider()

    with pytest.raises(FitError, match="authority-aware Ground projection"):
        execute_and_save_ground_fit(
            store=store,
            ground_name="physical-fit",
            provider_factory=provider_factory,
        )

    assert provider_constructions == 0


def test_mem_fit_plain_runs_against_physical_ground(monkeypatch, isolated_store):
    store = MemoryStore()
    _physical_fit_ground(store)
    monkeypatch.setattr(
        fit_command,
        "connect_semantic_provider",
        _PhysicalGroundProvider,
    )

    result = CliRunner().invoke(
        app,
        ["fit", "--ground", "physical-fit"],
    )

    assert result.exit_code == 0, result.output
    assert result.output == (
        "FIT · YES · [TARGETS: GROUND physical-fit] · 6/6 checks · CONTEXT 0 · VERTICAL 0 · PEER 0\n"
    )
