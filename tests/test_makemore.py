"""Contracts for standalone and Ground-composed Makemore."""

from __future__ import annotations

import ast
from dataclasses import replace
import json
from pathlib import Path

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import memcommit.adapters.console.commands.makemore.command as makemore_command
import memcommit.application.operations.makemore.application as makemore_application
import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.application.operations.conformance.model import (
    CONTEXT_CONFORMANCE_OPERATION,
)
from memcommit.application.operations.makemore.model import (
    MAKEMORE_OPERATION,
    MAKEMORE_PAYLOAD_MARKER,
    MakemoreError,
    MakemoreMode,
    MakemoreQualityPolicy,
)
from memcommit.application.operations.makemore.application import MakemoreRequest
from memcommit.application.operations.makemore.config import MakemoreSemanticConfig
from memcommit.application.operations.makemore.runtime import execute_makemore
from memcommit.application.operations.fit.judgment import (
    FIT_JUDGMENT_OPERATION,
    FIT_JUDGMENT_PAYLOAD_MARKER,
)
from memcommit.application.operations.ground.makemore import (
    apply_ground_makemore_result,
    execute_ground_makemore,
    freeze_ground_makemore,
)
from memcommit.application.operations.ground.workspace_application import (
    AddGroundWorkspaceMemoryRequest,
    CreateGroundWorkspaceRequest,
)
from memcommit.application.operations.ground.workspace_runtime import (
    execute_ground_workspace_creation,
    execute_ground_workspace_memory_add,
    load_ground_workspace,
)
from memcommit.application.operations.ground.workspace_history import (
    build_ground_workspace_command_stack,
    undo_ground_workspace_command,
)
from memcommit.adapters.console.commands.makemore.viewer import (
    project_makemore_clipboard,
    project_makemore_result,
    run_makemore_tui,
)
from memcommit.persistence.store import MemoryStore
from tests.makemore_validation_support import (
    passing_makemore_validation_response,
)


runner = CliRunner()


class MakemoreProvider:
    def __init__(self, *, empty: bool = False):
        self.empty = empty
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.operations: list[str] = []

    def complete(self, prompt, *, operation, output_schema=None):
        self.operations.append(operation)
        validation = passing_makemore_validation_response(prompt, operation)
        if validation is not None:
            return validation
        assert operation == MAKEMORE_OPERATION
        assert output_schema is not None
        self.calls.append((prompt, output_schema))
        payload = json.loads(prompt.split(MAKEMORE_PAYLOAD_MARKER, 1)[1])
        number = payload["number"]
        if payload["mode"] == "GOAL_TO_RULES":
            rules = (
                (
                    "Confirm the selected option before acting.",
                    "This operationalizes the requested confirmation.",
                ),
                (
                    "Record which option was explicitly confirmed.",
                    "This keeps the confirmed choice reviewable.",
                ),
                (
                    "Do not act when confirmation is missing or ambiguous.",
                    "This defines the confirmation boundary.",
                ),
                (
                    "Reconfirm after the selected option changes.",
                    "This prevents stale confirmation from authorizing a new choice.",
                ),
            )
            return json.dumps(
                {
                    "overview": f"The Goal yields exactly {number} Rule hypotheses.",
                    "rules": []
                    if self.empty
                    else [
                        {
                            "content": content,
                            "rationale": rationale,
                        }
                        for content, rationale in rules[:number]
                    ],
                }
            )
        case_specs = (
            (
                "A person explicitly confirms option A, and the system proceeds "
                "with option A only after that confirmation.",
                "Proceed with option A.",
                "This is an ordinary fitting Case.",
                "FIT",
            ),
            (
                "A person mentions option A without confirming it, so the system "
                "asks for explicit confirmation and does not proceed.",
                "Do not proceed yet.",
                "This distinguishes mention from confirmation.",
                "BOUNDARY",
            ),
            (
                "A person confirms option A and then requests option B, so the "
                "system obtains fresh confirmation for B before proceeding.",
                "Proceed with B only after fresh confirmation.",
                "This contrasts current confirmation with stale confirmation.",
                "CONTRAST",
            ),
        )
        return json.dumps(
            {
                "overview": f"The Rule yields exactly {number} diverse Cases.",
                "cases": []
                if self.empty
                else [
                    {
                        "proposition": proposition,
                        "expected": expected,
                        "rationale": rationale,
                        "case_role": role,
                        "rule_checks": [
                            {
                                "source_rule_index": index,
                                "evidence": "The proposition visibly complies with this Rule.",
                            }
                            for index, _rule in enumerate(payload["inputs"], 1)
                        ],
                    }
                    for proposition, expected, rationale, role in case_specs[:number]
                ],
            }
        )


class ExactNumberProvider:
    def __init__(self):
        self.calls: list[tuple[dict[str, object], dict[str, object], str]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        validation = passing_makemore_validation_response(prompt, operation)
        if validation is not None:
            return validation
        assert operation == MAKEMORE_OPERATION
        assert output_schema is not None
        payload = json.loads(prompt.split(MAKEMORE_PAYLOAD_MARKER, 1)[1])
        number = payload["number"]
        self.calls.append((payload, output_schema, prompt))
        if payload["mode"] == "GOAL_TO_RULES":
            return json.dumps(
                {
                    "overview": f"Exactly {number} Rule proposals.",
                    "rules": [
                        {
                            "content": f"Operational Rule {index}.",
                            "rationale": f"Distinct rationale {index}.",
                        }
                        for index in range(1, number + 1)
                    ],
                }
            )
        roles = ("FIT", "BOUNDARY", "CONTRAST")
        return json.dumps(
            {
                "overview": f"Exactly {number} Case proposals.",
                "cases": [
                    {
                        "proposition": f"Complete compliant Case {index}.",
                        "expected": f"Expected outcome {index}.",
                        "rationale": f"Distinct rationale {index}.",
                        "case_role": roles[(index - 1) % len(roles)],
                        "rule_checks": [
                            {
                                "source_rule_index": rule_index,
                                "evidence": f"Case {index} checks Rule {rule_index}.",
                            }
                            for rule_index, _rule in enumerate(payload["inputs"], 1)
                        ],
                    }
                    for index in range(1, number + 1)
                ],
            }
        )


def test_goal_makemores_to_bounded_unverified_rule_proposals() -> None:
    provider = MakemoreProvider()

    result = execute_makemore(
        MakemoreRequest(goal="Confirm a chosen option before acting."),
        provider_factory=lambda: provider,
    )

    assert result.analysis.mode is MakemoreMode.GOAL_TO_RULES
    assert len(result.analysis.rules) == 3
    assert result.analysis.cases == ()
    assert provider.calls[0][1]["properties"]["rules"]["minItems"] == 3
    assert provider.calls[0][1]["properties"]["rules"]["maxItems"] == 3
    assert "Propose exactly 3" in provider.calls[0][0]
    assert "not a reason to return an empty set" in provider.calls[0][0]
    assert result.analysis.number == 3


def test_rules_makemore_to_diverse_unverified_case_propositions() -> None:
    provider = MakemoreProvider()
    result = execute_makemore(
        MakemoreRequest(rules=("Act only after explicit confirmation.",)),
        provider_factory=lambda: provider,
    )

    assert result.analysis.mode is MakemoreMode.RULES_TO_CASES
    assert [case.case_role for case in result.analysis.cases] == [
        "FIT",
        "BOUNDARY",
        "CONTRAST",
    ]
    assert all(
        tuple(check.source_rule_index for check in case.rule_checks) == (1,)
        for case in result.analysis.cases
    )
    assert provider.calls[0][1]["properties"]["cases"]["minItems"] == 3
    assert provider.calls[0][1]["properties"]["cases"]["maxItems"] == 3
    checks_schema = provider.calls[0][1]["properties"]["cases"]["items"]["properties"][
        "rule_checks"
    ]
    assert checks_schema["minItems"] == checks_schema["maxItems"] == 1
    assert "Propose exactly 3" in provider.calls[0][0]
    assert "complete input Rule set together" in provider.calls[0][0]
    assert "not a reason to return an empty set" in provider.calls[0][0]
    assert result.analysis.number == 3
    assert result.analysis.quality_policy is MakemoreQualityPolicy.BEST_EFFORT
    assert all(case.validation is None for case in result.analysis.cases)
    assert provider.operations == [MAKEMORE_OPERATION]


def test_rules_makemore_accepts_source_absent_values_when_they_fit() -> None:
    class CapturingProvider(MakemoreProvider):
        def __init__(self) -> None:
            super().__init__()
            self.semantic_calls: list[tuple[str, str]] = []

        def complete(self, prompt, *, operation, output_schema=None):
            self.semantic_calls.append((operation, prompt))
            return super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )

    provider = CapturingProvider()
    result = execute_makemore(
        MakemoreRequest(
            rules=("Act only after explicit confirmation.",),
            number=1,
            strict=True,
        ),
        provider_factory=lambda: provider,
    )

    assert "option A" in result.analysis.cases[0].proposition
    assert "option A" not in result.analysis.inputs[0]
    assert [operation for operation, _prompt in provider.semantic_calls] == [
        MAKEMORE_OPERATION,
        CONTEXT_CONFORMANCE_OPERATION,
        FIT_JUDGMENT_OPERATION,
    ]
    fit_prompt = provider.semantic_calls[-1][1]
    assert (
        "Missing support or an unknown fact is not itself a contradiction" in fit_prompt
    )


def test_rules_makemore_rejects_a_case_that_fails_source_rule_conformance() -> None:
    class RejectingProvider(MakemoreProvider):
        def complete(self, prompt, *, operation, output_schema=None):
            if operation == CONTEXT_CONFORMANCE_OPERATION:
                payload = json.loads(
                    prompt.split("CONFORMANCE CONTEXT PAYLOAD:\n", 1)[1]
                )
                case_id = payload["target_context"]["memories"][0]["memory_id"]
                return json.dumps(
                    {
                        "judgments": [
                            {
                                "rule_id": payload["rules"][0]["rule_id"],
                                "status": "VIOLATES",
                                "evidence_memory_ids": [case_id],
                                "nonconforming_cases": [
                                    {
                                        "memory_id": case_id,
                                        "reason": "The Case acts before confirmation.",
                                    }
                                ],
                                "reason": "The generated Case violates the Rule.",
                            }
                        ],
                        "outside_memory_ids": [],
                    }
                )
            return super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )

    with pytest.raises(MakemoreError, match="did not conform to every Source Rule"):
        execute_makemore(
            MakemoreRequest(
                rules=("Act only after explicit confirmation.",),
                number=1,
                strict=True,
            ),
            provider_factory=RejectingProvider,
        )


def test_rules_makemore_rejects_a_case_that_does_not_fit_the_source() -> None:
    class RejectingProvider(MakemoreProvider):
        def complete(self, prompt, *, operation, output_schema=None):
            if operation == FIT_JUDGMENT_OPERATION:
                payload = json.loads(prompt.split(FIT_JUDGMENT_PAYLOAD_MARKER, 1)[1])
                question = payload["questions"][0]
                aliases = [
                    item["proposition_id"]
                    for item in (
                        *question["background"],
                        *question["propositions"],
                    )
                ]
                return json.dumps(
                    {
                        "overview": "The generated Case conflicts with the Source.",
                        "judgments": [
                            {
                                "question_id": question["question_id"],
                                "verdict": "NO",
                                "reason": "The Case contradicts the Source Rule.",
                                "considered_proposition_ids": aliases,
                                "material_proposition_ids": aliases,
                                "consistent_reading": "",
                                "inconsistent_reading": "",
                            }
                        ],
                    }
                )
            return super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )

    with pytest.raises(MakemoreError, match="did not Fit the complete Source frame"):
        execute_makemore(
            MakemoreRequest(
                rules=("Act only after explicit confirmation.",),
                number=1,
                strict=True,
            ),
            provider_factory=RejectingProvider,
        )


@pytest.mark.parametrize(
    ("makemore_request", "field", "number"),
    (
        (MakemoreRequest(goal="Make this Goal operational.", number=5), "rules", 5),
        (
            MakemoreRequest(
                rules=("Keep every result reviewable.",),
                number=5,
            ),
            "cases",
            5,
        ),
    ),
)
def test_makemore_number_requires_exactly_n_proposals(
    makemore_request,
    field,
    number,
) -> None:
    provider = ExactNumberProvider()

    result = execute_makemore(
        makemore_request,
        provider_factory=lambda: provider,
    )

    proposals = getattr(result.analysis, field)
    payload, schema, prompt = provider.calls[0]
    proposal_schema = schema["properties"][field]
    assert len(proposals) == number
    assert result.analysis.number == number
    assert payload["number"] == number
    assert proposal_schema["minItems"] == proposal_schema["maxItems"] == number
    assert f"Propose exactly {number}" in prompt


def test_makemore_number_rejects_a_provider_count_mismatch() -> None:
    class MismatchProvider:
        def complete(self, prompt, *, operation, output_schema=None):
            return json.dumps(
                {
                    "overview": "Only one Rule was returned.",
                    "rules": [
                        {
                            "content": "One Rule only.",
                            "rationale": "This deliberately violates the exact count.",
                        }
                    ],
                }
            )

    provider = MismatchProvider()

    with pytest.raises(MakemoreError, match="invalid Rules"):
        execute_makemore(
            MakemoreRequest(goal="Make this Goal operational.", number=2),
            provider_factory=lambda: provider,
        )


@pytest.mark.parametrize(
    "makemore_request",
    (
        MakemoreRequest(goal="One Goal.", number=5),
        MakemoreRequest(rules=("One Rule.",), number=4),
    ),
)
def test_makemore_optional_direction_bound_rejects_before_provider(
    makemore_request,
) -> None:
    provider_constructions = 0

    def provider_factory():
        nonlocal provider_constructions
        provider_constructions += 1
        return ExactNumberProvider()

    with pytest.raises(MakemoreError, match="number must be between"):
        execute_makemore(
            makemore_request,
            provider_factory=provider_factory,
            config=MakemoreSemanticConfig(
                max_rule_proposals=4,
                max_case_proposals=3,
            ),
        )

    assert provider_constructions == 0


def test_rules_makemore_rejects_partial_or_reordered_rule_coverage() -> None:
    class PartialCoverageProvider:
        def complete(self, prompt, *, operation, output_schema=None):
            return json.dumps(
                {
                    "overview": "The Case omits one source Rule.",
                    "cases": [
                        {
                            "proposition": "One partial Case.",
                            "expected": "A partial result must not be accepted.",
                            "rationale": "Only the first Rule is checked.",
                            "case_role": "FIT",
                            "rule_checks": [
                                {
                                    "source_rule_index": 1,
                                    "evidence": "Only Rule 1 appears.",
                                }
                            ],
                        }
                    ],
                }
            )

    with pytest.raises(MakemoreError, match="every source Rule exactly once"):
        execute_makemore(
            MakemoreRequest(rules=("Rule one.", "Rule two."), number=1),
            provider_factory=PartialCoverageProvider,
        )


@pytest.mark.parametrize(
    "makemore_request, message",
    (
        (MakemoreRequest(goal="Explore a sparse Goal."), "invalid Rules"),
        (
            MakemoreRequest(rules=("An underspecified Rule.",)),
            "invalid Cases",
        ),
    ),
)
def test_makemore_rejects_an_empty_proposal_set(
    makemore_request,
    message,
) -> None:
    provider = MakemoreProvider(empty=True)

    with pytest.raises(MakemoreError, match=message):
        execute_makemore(
            makemore_request,
            provider_factory=lambda: provider,
        )

    assert len(provider.calls) == 1


def test_makemore_request_requires_exactly_one_direction() -> None:
    with pytest.raises(MakemoreError):
        MakemoreRequest()
    with pytest.raises(MakemoreError):
        MakemoreRequest(goal="One Goal", rules=("One Rule",))
    with pytest.raises(MakemoreError, match="positive integer"):
        MakemoreRequest(goal="One Goal", number=0)
    with pytest.raises(MakemoreError, match="positive integer"):
        MakemoreRequest(goal="One Goal", number=-1)
    with pytest.raises(MakemoreError, match="positive integer"):
        MakemoreRequest(goal="One Goal", number=True)
    with pytest.raises(MakemoreError, match="Strict Makemore applies only"):
        MakemoreRequest(goal="One Goal", strict=True)


def test_makemore_exact_prepared_lookup_avoids_provider() -> None:
    request = MakemoreRequest(goal="Confirm before acting.")
    live = execute_makemore(request, provider_factory=MakemoreProvider)

    prepared = execute_makemore(
        request,
        provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("exact prepared Makemore must avoid provider")
        ),
        prepared_lookup=lambda _request, _config: live.analysis,
    )

    assert prepared.analysis is live.analysis
    assert prepared.origin == "PREPARED_EXACT"


def test_rules_makemore_prepared_lookup_reuses_exact_validation() -> None:
    request = MakemoreRequest(
        rules=("Act only after explicit confirmation.",),
        number=1,
        strict=True,
    )
    live = execute_makemore(request, provider_factory=MakemoreProvider)

    prepared = execute_makemore(
        request,
        provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("validated prepared Makemore must avoid providers")
        ),
        prepared_lookup=lambda _request, _config: live.analysis,
    )

    assert prepared.analysis is live.analysis
    assert prepared.analysis.cases[0].validation is not None
    assert prepared.origin == "PREPARED_EXACT"


def test_makemore_prepared_result_must_match_quality_policy() -> None:
    live = execute_makemore(
        MakemoreRequest(
            rules=("Act only after explicit confirmation.",),
            number=1,
        ),
        provider_factory=MakemoreProvider,
    )

    with pytest.raises(MakemoreError, match="does not exactly match"):
        execute_makemore(
            MakemoreRequest(
                rules=("Act only after explicit confirmation.",),
                number=1,
                strict=True,
            ),
            provider_factory=lambda: (_ for _ in ()).throw(
                AssertionError("policy mismatch must fail before provider")
            ),
            prepared_lookup=lambda _request, _config: live.analysis,
        )


def test_makemore_rejects_an_analysis_from_the_prior_provider_contract() -> None:
    live = execute_makemore(
        MakemoreRequest(goal="Confirm before acting."),
        provider_factory=MakemoreProvider,
    )

    with pytest.raises(
        MakemoreError,
        match="Unsupported Makemore provider contract version",
    ):
        replace(live.analysis, provider_contract_version=1)


def test_makemore_rejects_nonexact_prepared_result() -> None:
    live = execute_makemore(
        MakemoreRequest(goal="Confirm before acting."),
        provider_factory=MakemoreProvider,
    )

    with pytest.raises(MakemoreError, match="does not exactly match"):
        execute_makemore(
            MakemoreRequest(goal="Confirm a different action."),
            provider_factory=lambda: (_ for _ in ()).throw(
                AssertionError("a nonexact prepared result must fail closed")
            ),
            prepared_lookup=lambda _request, _config: live.analysis,
        )


def test_makemore_prepared_result_must_match_the_exact_number() -> None:
    provider = ExactNumberProvider()
    live = execute_makemore(
        MakemoreRequest(goal="Confirm before acting.", number=1),
        provider_factory=lambda: provider,
    )

    with pytest.raises(MakemoreError, match="does not exactly match"):
        execute_makemore(
            MakemoreRequest(goal="Confirm before acting.", number=2),
            provider_factory=lambda: (_ for _ in ()).throw(
                AssertionError("a nonexact prepared result must fail closed")
            ),
            prepared_lookup=lambda _request, _config: live.analysis,
        )


def test_makemore_live_plan_rejects_oversized_input_before_provider() -> None:
    provider_constructions = 0

    def provider_factory():
        nonlocal provider_constructions
        provider_constructions += 1
        return MakemoreProvider()

    config = MakemoreSemanticConfig(text_limit=600_100)
    with pytest.raises(MakemoreError, match="shared Conformance/Fit"):
        execute_makemore(
            MakemoreRequest(
                rules=("A" * 600_000, "B" * 600_000),
                strict=True,
            ),
            provider_factory=provider_factory,
            config=config,
        )

    assert provider_constructions == 0


def test_rules_makemore_rejects_oversized_validation_frame_before_provider() -> None:
    provider_constructions = 0

    def provider_factory():
        nonlocal provider_constructions
        provider_constructions += 1
        return ExactNumberProvider()

    with pytest.raises(MakemoreError, match="validation frame exceeds"):
        execute_makemore(
            MakemoreRequest(
                rules=("Apply the complete Rule.",),
                number=2_001,
                strict=True,
            ),
            provider_factory=provider_factory,
        )

    assert provider_constructions == 0


def test_rules_makemore_accepts_collection_level_rule_applicability() -> None:
    class CollectionProvider(ExactNumberProvider):
        def complete(self, prompt, *, operation, output_schema=None):
            if operation == CONTEXT_CONFORMANCE_OPERATION:
                payload = json.loads(
                    prompt.split("CONFORMANCE CONTEXT PAYLOAD:\n", 1)[1]
                )
                memory_ids = [
                    item["memory_id"] for item in payload["target_context"]["memories"]
                ]
                return json.dumps(
                    {
                        "judgments": [
                            {
                                "rule_id": payload["rules"][0]["rule_id"],
                                "status": "CONFORMS",
                                "evidence_memory_ids": memory_ids[:2],
                                "nonconforming_cases": [],
                                "reason": "The first two members satisfy the seed Rule.",
                            },
                            {
                                "rule_id": payload["rules"][1]["rule_id"],
                                "status": "CONFORMS",
                                "evidence_memory_ids": memory_ids[2:],
                                "nonconforming_cases": [],
                                "reason": "The later members satisfy the recurrence Rule.",
                            },
                        ],
                        "outside_memory_ids": [],
                    }
                )
            return super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )

    provider = CollectionProvider()
    result = execute_makemore(
        MakemoreRequest(
            rules=(
                "The family begins with two ordered seed members.",
                "Every later member follows the family recurrence.",
            ),
            number=4,
            strict=True,
        ),
        provider_factory=lambda: provider,
    )

    assert len(result.analysis.cases) == 4
    assert all(case.validation is not None for case in result.analysis.cases)
    assert result.analysis.quality_policy is MakemoreQualityPolicy.STRICT
    assert "ordered collection or family" in provider.calls[0][2]
    assert "applicable to that member" in provider.calls[0][2]
    assert "`COLLECTION:`" in provider.calls[0][2]


def test_makemore_application_imports_no_terminal_or_command_adapter() -> None:
    source = Path(makemore_application.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.append(node.module)

    assert (
        tuple(
            name
            for name in imports
            if name == "typer"
            or name.startswith("prompt_toolkit")
            or name.startswith("memcommit.adapters.console.commands")
        )
        == ()
    )


def test_makemore_result_limits_follow_the_injected_config() -> None:
    request = MakemoreRequest(goal="G" * 2_100)
    result = execute_makemore(
        request,
        provider_factory=MakemoreProvider,
        config=MakemoreSemanticConfig(text_limit=2_200),
    )

    assert result.analysis.inputs == (request.goal,)


def test_makemore_prepared_result_is_revalidated_against_current_config() -> None:
    request = MakemoreRequest(goal="Confirm.")
    live = execute_makemore(request, provider_factory=MakemoreProvider)

    with pytest.raises(MakemoreError, match="semantic config does not match"):
        execute_makemore(
            request,
            provider_factory=lambda: (_ for _ in ()).throw(
                AssertionError("prepared validation must happen before provider")
            ),
            prepared_lookup=lambda _request, _config: live.analysis,
            config=MakemoreSemanticConfig(text_limit=20),
        )


def test_makemore_shared_viewer_copies_one_proposal_or_all() -> None:
    result = execute_makemore(
        MakemoreRequest(goal="Confirm before acting."),
        provider_factory=MakemoreProvider,
    )
    document = project_makemore_result(result)
    rendered = "".join(
        text for _style, text in document.render(focused_uid="MAKEMORE:TITLE")
    )
    focused = project_makemore_clipboard(
        result,
        focused_uid="MAKEMORE:RULE:0",
        whole_document=False,
    )

    assert "SUGGESTED · UNVERIFIED" in rendered
    assert "PROPOSAL OVERVIEW" in rendered
    assert "WHAT MEM UNDERSTOOD" not in rendered
    assert focused.text.startswith("[Suggested] [Unverified]")
    assert "WHAT MEM UNDERSTOOD" not in focused.text

    copied: list[str] = []
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\x1b[B\x1b[ByYq")
        returned = run_makemore_tui(
            result,
            clipboard_writer=copied.append,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
    assert returned == result
    assert copied[0].startswith("[Suggested] [Unverified]")
    assert "PROPOSAL OVERVIEW" in copied[1]


def test_makemore_console_keeps_projection_without_a_mode_router() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    command_root = repository_root / "src/memcommit/adapters/console/commands/makemore"
    retired_tui_root = (
        repository_root / "src/memcommit/adapters/interfaces/tui/operations/makemore"
    )

    assert (command_root / "proposal.py").is_file()
    assert not (command_root / "runner.py").exists()
    assert (command_root / "viewer/model.py").is_file()
    assert (command_root / "viewer/projection.py").is_file()
    assert (command_root / "viewer/screen.py").is_file()
    assert not tuple(retired_tui_root.glob("*.py"))
    assert not (
        repository_root / "src/memcommit/adapters/interfaces/cli/makemore.py"
    ).exists()

    assert not (repository_root / "src/memcommit/bootstrap.py").exists()


def test_elaborate_and_makemore_keep_distinct_command_contracts() -> None:
    elaborate_result = runner.invoke(app, ["elaborate", "--help"])
    makemore_result = runner.invoke(app, ["makemore", "--help"])

    assert elaborate_result.exit_code == 0
    assert "MEMORY_SELECTOR" in elaborate_result.output
    assert "without rewriting" in elaborate_result.output
    assert makemore_result.exit_code == 0
    assert "--goal" in makemore_result.output
    assert "candidate propositions" in makemore_result.output


def test_mem_makemore_plain_uses_the_typed_application(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    target = ops.init("makemore/inline-target")
    store.create_context(target)
    store.set_current(target.name)
    monkeypatch.setattr(
        makemore_command,
        "connect_semantic_provider",
        MakemoreProvider,
    )

    result = runner.invoke(
        app,
        ["makemore", "--goal", "Confirm before acting."],
    )

    assert result.exit_code == 0, result.output
    assert "MAKEMORE APPLIED · makemore/inline-target" in result.output
    assert "MODE · GOAL_TO_RULES · VERIFICATION · UNVERIFIED" in result.output
    assert "EFFECTS · ADD 3 MEMORIES" in result.output
    assert "REVIEW · mem review makemore --receipt" in result.output
    assert len(store.load_direct(target.name).order) == 3


def test_mem_makemore_ground_adopt_is_an_explicit_physical_write(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(
            name="physical-makemore",
            goal="Confirm a chosen option before acting.",
        ),
        store=store,
    )
    monkeypatch.setattr(
        makemore_command,
        "connect_semantic_provider",
        MakemoreProvider,
    )

    result = runner.invoke(
        app,
        [
            "makemore",
            "--ground",
            "physical-makemore",
            "--from-goal",
            "--adopt",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "MAKEMORE ADOPTED · physical-makemore/rules" in result.output
    assert "EFFECTS · ADD 3 MEMORIES" in result.output
    assert (
        len(
            tuple(load_ground_workspace(store, "physical-makemore").rules.iter_items())
        )
        == 3
    )


def test_physical_ground_goal_makemore_freezes_only_the_goal_memory(
    isolated_store,
):
    store = MemoryStore()
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(
            name="physical-makemore",
            goal="Confirm a chosen option before acting.",
        ),
        store=store,
    )
    frozen = freeze_ground_makemore(
        store,
        ground_name="physical-makemore",
        direction="GOAL_TO_RULES",
    )
    # An Example is outside this direction's consumed frame and must not make
    # a safe cached/provider request stale.
    execute_ground_workspace_memory_add(
        AddGroundWorkspaceMemoryRequest(
            workspace_name="physical-makemore",
            lane="examples",
            content="A person explicitly confirms option A.",
        ),
        store=store,
    )
    provider = MakemoreProvider()

    result = execute_ground_makemore(
        frozen,
        store=store,
        provider_factory=lambda: provider,
    )

    assert result.frozen.request.goal == "Confirm a chosen option before acting."
    assert result.frozen.request.goal_focus is not None
    assert result.frozen.request.goal_focus.kind == "GROUND"
    assert result.frozen.request.goal_focus.items[0].memory_uid is not None
    assert len(provider.calls) == 1


def test_physical_ground_makemore_adopts_rules_as_one_ground_command(
    isolated_store,
):
    store = MemoryStore()
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(
            name="physical-makemore",
            goal="Confirm a chosen option before acting.",
        ),
        store=store,
    )
    frozen = freeze_ground_makemore(
        store,
        ground_name="physical-makemore",
        direction="GOAL_TO_RULES",
    )
    proposal = execute_ground_makemore(
        frozen,
        store=store,
        provider_factory=MakemoreProvider,
    )

    receipt = apply_ground_makemore_result(proposal, store=store)

    workspace = load_ground_workspace(store, "physical-makemore")
    assert receipt.revision == frozen.ground_revision + 1
    assert len(tuple(workspace.rules.iter_items())) == 3
    [unit] = build_ground_workspace_command_stack(
        store,
        "physical-makemore",
    ).undo
    assert unit.action == "adopt-makemore"
    undo_ground_workspace_command(store, "physical-makemore")
    assert (
        tuple(load_ground_workspace(store, "physical-makemore").rules.iter_items())
        == ()
    )


def test_physical_ground_makemore_adoption_rejects_changed_ground_revision(
    isolated_store,
):
    store = MemoryStore()
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(
            name="physical-makemore",
            goal="Confirm a chosen option before acting.",
        ),
        store=store,
    )
    frozen = freeze_ground_makemore(
        store,
        ground_name="physical-makemore",
        direction="GOAL_TO_RULES",
    )
    proposal = execute_ground_makemore(
        frozen,
        store=store,
        provider_factory=MakemoreProvider,
    )
    execute_ground_workspace_memory_add(
        AddGroundWorkspaceMemoryRequest(
            workspace_name="physical-makemore",
            lane="examples",
            content="An independently reviewed Example.",
        ),
        store=store,
    )

    with pytest.raises(MakemoreError, match="changed after the Makemore"):
        apply_ground_makemore_result(proposal, store=store)


def test_physical_ground_rules_makemore_and_fail_on_consumed_rule_drift(
    isolated_store,
):
    store = MemoryStore()
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(name="physical-makemore"),
        store=store,
    )
    execute_ground_workspace_memory_add(
        AddGroundWorkspaceMemoryRequest(
            workspace_name="physical-makemore",
            lane="rules",
            content="Act only after explicit confirmation.",
        ),
        store=store,
    )
    frozen = freeze_ground_makemore(
        store,
        ground_name="physical-makemore",
        direction="RULES_TO_CASES",
    )
    rules = store.load_for_update("physical-makemore/rules")
    rules.add("A concurrent consumed Rule.")
    store.save(rules)
    provider = MakemoreProvider()

    with pytest.raises(MakemoreError, match="consumed Ground workspace"):
        execute_ground_makemore(
            frozen,
            store=store,
            provider_factory=lambda: provider,
        )

    assert provider.calls == []


def test_physical_ground_makemore_rejects_typed_rule_before_provider(
    isolated_store,
):
    store = MemoryStore()
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(name="physical-makemore"),
        store=store,
    )
    source = ops.init("physical-makemore/external-rules")
    memory = ops.add(source, "Act only after explicit confirmation.")
    store.create_context(source)
    rules = store.load_for_update("physical-makemore/rules")
    ops.embed_memory(memory, source, rules)
    store.save(rules)

    with pytest.raises(MakemoreError, match="authority-aware Ground projection"):
        freeze_ground_makemore(
            store,
            ground_name="physical-makemore",
            direction="RULES_TO_CASES",
        )
