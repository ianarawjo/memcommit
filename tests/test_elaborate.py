"""Contracts for standalone and Ground-composed Elaborate."""

from __future__ import annotations

import ast
from dataclasses import replace
import json
from pathlib import Path

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import memcommit.commands.elaborate.command as elaborate_command
import memcommit.operations.elaborate.application as elaborate_application
import memcommit.ops as ops
from memcommit.cli import app
from memcommit.conformance import CONTEXT_CONFORMANCE_OPERATION
from memcommit.context import Context, Memory
from memcommit.elaborate import (
    ELABORATE_OPERATION,
    ELABORATE_PAYLOAD_MARKER,
    ElaborateError,
    ElaborateMode,
    ElaborateQualityPolicy,
)
from memcommit.operations.elaborate.application import ElaborateRequest
from memcommit.elaborate_config import ElaborateSemanticConfig
from memcommit.operations.elaborate.runtime import execute_elaborate
from memcommit.operations.fit.judgment import (
    FIT_JUDGMENT_OPERATION,
    FIT_JUDGMENT_PAYLOAD_MARKER,
)
from memcommit.ground import (
    GroundTargetSpec,
    bind_ground_workbench,
    create_ground_session,
    propose_ground_rule,
)
from memcommit.ground_elaborate import (
    apply_ground_elaborate_result,
    execute_ground_elaborate,
    freeze_ground_elaborate,
)
from memcommit.ground_workspace_application import (
    AddGroundWorkspaceMemoryRequest,
    CreateGroundWorkspaceRequest,
)
from memcommit.ground_workspace_runtime import (
    execute_ground_workspace_creation,
    execute_ground_workspace_memory_add,
    load_ground_workspace,
)
from memcommit.ground_workspace_history import (
    build_ground_workspace_command_stack,
    undo_ground_workspace_command,
)
from memcommit.interfaces.tui.operations.elaborate import (
    project_elaborate_clipboard,
    project_elaborate_result,
    run_elaborate_tui,
)
from memcommit.store import MemoryStore, ground_session_record_digest
from tests.elaborate_validation_support import (
    passing_elaborate_validation_response,
)


runner = CliRunner()


class ElaborateProvider:
    def __init__(self, *, empty: bool = False):
        self.empty = empty
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.operations: list[str] = []

    def complete(self, prompt, *, operation, output_schema=None):
        self.operations.append(operation)
        validation = passing_elaborate_validation_response(prompt, operation)
        if validation is not None:
            return validation
        assert operation == ELABORATE_OPERATION
        assert output_schema is not None
        self.calls.append((prompt, output_schema))
        payload = json.loads(prompt.split(ELABORATE_PAYLOAD_MARKER, 1)[1])
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
        validation = passing_elaborate_validation_response(prompt, operation)
        if validation is not None:
            return validation
        assert operation == ELABORATE_OPERATION
        assert output_schema is not None
        payload = json.loads(prompt.split(ELABORATE_PAYLOAD_MARKER, 1)[1])
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


def test_goal_elaborates_to_bounded_unverified_rule_proposals() -> None:
    provider = ElaborateProvider()

    result = execute_elaborate(
        ElaborateRequest(goal="Confirm a chosen option before acting."),
        provider_factory=lambda: provider,
    )

    assert result.analysis.mode is ElaborateMode.GOAL_TO_RULES
    assert len(result.analysis.rules) == 3
    assert result.analysis.cases == ()
    assert provider.calls[0][1]["properties"]["rules"]["minItems"] == 3
    assert provider.calls[0][1]["properties"]["rules"]["maxItems"] == 3
    assert "Propose exactly 3" in provider.calls[0][0]
    assert "not a reason to return an empty set" in provider.calls[0][0]
    assert result.analysis.number == 3


def test_rules_elaborate_to_diverse_unverified_case_propositions() -> None:
    provider = ElaborateProvider()
    result = execute_elaborate(
        ElaborateRequest(rules=("Act only after explicit confirmation.",)),
        provider_factory=lambda: provider,
    )

    assert result.analysis.mode is ElaborateMode.RULES_TO_CASES
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
    checks_schema = provider.calls[0][1]["properties"]["cases"]["items"][
        "properties"
    ]["rule_checks"]
    assert checks_schema["minItems"] == checks_schema["maxItems"] == 1
    assert "Propose exactly 3" in provider.calls[0][0]
    assert "complete input Rule set together" in provider.calls[0][0]
    assert "not a reason to return an empty set" in provider.calls[0][0]
    assert result.analysis.number == 3
    assert result.analysis.quality_policy is ElaborateQualityPolicy.BEST_EFFORT
    assert all(case.validation is None for case in result.analysis.cases)
    assert provider.operations == [ELABORATE_OPERATION]


def test_rules_elaborate_accepts_source_absent_values_when_they_fit() -> None:
    class CapturingProvider(ElaborateProvider):
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
    result = execute_elaborate(
        ElaborateRequest(
            rules=("Act only after explicit confirmation.",),
            number=1,
            strict=True,
        ),
        provider_factory=lambda: provider,
    )

    assert "option A" in result.analysis.cases[0].proposition
    assert "option A" not in result.analysis.inputs[0]
    assert [operation for operation, _prompt in provider.semantic_calls] == [
        ELABORATE_OPERATION,
        CONTEXT_CONFORMANCE_OPERATION,
        FIT_JUDGMENT_OPERATION,
    ]
    fit_prompt = provider.semantic_calls[-1][1]
    assert "Missing support or an unknown fact is not itself a contradiction" in fit_prompt


def test_rules_elaborate_rejects_a_case_that_fails_source_rule_conformance() -> None:
    class RejectingProvider(ElaborateProvider):
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

    with pytest.raises(ElaborateError, match="did not conform to every Source Rule"):
        execute_elaborate(
            ElaborateRequest(
                rules=("Act only after explicit confirmation.",),
                number=1,
                strict=True,
            ),
            provider_factory=RejectingProvider,
        )


def test_rules_elaborate_rejects_a_case_that_does_not_fit_the_source() -> None:
    class RejectingProvider(ElaborateProvider):
        def complete(self, prompt, *, operation, output_schema=None):
            if operation == FIT_JUDGMENT_OPERATION:
                payload = json.loads(
                    prompt.split(FIT_JUDGMENT_PAYLOAD_MARKER, 1)[1]
                )
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

    with pytest.raises(ElaborateError, match="did not Fit the complete Source frame"):
        execute_elaborate(
            ElaborateRequest(
                rules=("Act only after explicit confirmation.",),
                number=1,
                strict=True,
            ),
            provider_factory=RejectingProvider,
        )


@pytest.mark.parametrize(
    ("elaborate_request", "field", "number"),
    (
        (ElaborateRequest(goal="Make this Goal operational.", number=5), "rules", 5),
        (
            ElaborateRequest(
                rules=("Keep every result reviewable.",),
                number=5,
            ),
            "cases",
            5,
        ),
    ),
)
def test_elaborate_number_requires_exactly_n_proposals(
    elaborate_request,
    field,
    number,
) -> None:
    provider = ExactNumberProvider()

    result = execute_elaborate(
        elaborate_request,
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


def test_elaborate_number_rejects_a_provider_count_mismatch() -> None:
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

    with pytest.raises(ElaborateError, match="invalid Rules"):
        execute_elaborate(
            ElaborateRequest(goal="Make this Goal operational.", number=2),
            provider_factory=lambda: provider,
        )

@pytest.mark.parametrize(
    "elaborate_request",
    (
        ElaborateRequest(goal="One Goal.", number=5),
        ElaborateRequest(rules=("One Rule.",), number=4),
    ),
)
def test_elaborate_optional_direction_bound_rejects_before_provider(
    elaborate_request,
) -> None:
    provider_constructions = 0

    def provider_factory():
        nonlocal provider_constructions
        provider_constructions += 1
        return ExactNumberProvider()

    with pytest.raises(ElaborateError, match="number must be between"):
        execute_elaborate(
            elaborate_request,
            provider_factory=provider_factory,
            config=ElaborateSemanticConfig(
                max_rule_proposals=4,
                max_case_proposals=3,
            ),
        )

    assert provider_constructions == 0


def test_rules_elaborate_rejects_partial_or_reordered_rule_coverage() -> None:
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

    with pytest.raises(ElaborateError, match="every source Rule exactly once"):
        execute_elaborate(
            ElaborateRequest(rules=("Rule one.", "Rule two."), number=1),
            provider_factory=PartialCoverageProvider,
        )


@pytest.mark.parametrize(
    "elaborate_request, message",
    (
        (ElaborateRequest(goal="Explore a sparse Goal."), "invalid Rules"),
        (
            ElaborateRequest(rules=("An underspecified Rule.",)),
            "invalid Cases",
        ),
    ),
)
def test_elaborate_rejects_an_empty_proposal_set(
    elaborate_request,
    message,
) -> None:
    provider = ElaborateProvider(empty=True)

    with pytest.raises(ElaborateError, match=message):
        execute_elaborate(
            elaborate_request,
            provider_factory=lambda: provider,
        )

    assert len(provider.calls) == 1


def test_elaborate_request_requires_exactly_one_direction() -> None:
    with pytest.raises(ElaborateError):
        ElaborateRequest()
    with pytest.raises(ElaborateError):
        ElaborateRequest(goal="One Goal", rules=("One Rule",))
    with pytest.raises(ElaborateError, match="positive integer"):
        ElaborateRequest(goal="One Goal", number=0)
    with pytest.raises(ElaborateError, match="positive integer"):
        ElaborateRequest(goal="One Goal", number=-1)
    with pytest.raises(ElaborateError, match="positive integer"):
        ElaborateRequest(goal="One Goal", number=True)
    with pytest.raises(ElaborateError, match="Strict Elaborate applies only"):
        ElaborateRequest(goal="One Goal", strict=True)


def test_elaborate_exact_prepared_lookup_avoids_provider() -> None:
    request = ElaborateRequest(goal="Confirm before acting.")
    live = execute_elaborate(request, provider_factory=ElaborateProvider)

    prepared = execute_elaborate(
        request,
        provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("exact prepared Elaborate must avoid provider")
        ),
        prepared_lookup=lambda _request, _config: live.analysis,
    )

    assert prepared.analysis is live.analysis
    assert prepared.origin == "PREPARED_EXACT"


def test_rules_elaborate_prepared_lookup_reuses_exact_validation() -> None:
    request = ElaborateRequest(
        rules=("Act only after explicit confirmation.",),
        number=1,
        strict=True,
    )
    live = execute_elaborate(request, provider_factory=ElaborateProvider)

    prepared = execute_elaborate(
        request,
        provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("validated prepared Elaborate must avoid providers")
        ),
        prepared_lookup=lambda _request, _config: live.analysis,
    )

    assert prepared.analysis is live.analysis
    assert prepared.analysis.cases[0].validation is not None
    assert prepared.origin == "PREPARED_EXACT"


def test_elaborate_prepared_result_must_match_quality_policy() -> None:
    live = execute_elaborate(
        ElaborateRequest(
            rules=("Act only after explicit confirmation.",),
            number=1,
        ),
        provider_factory=ElaborateProvider,
    )

    with pytest.raises(ElaborateError, match="does not exactly match"):
        execute_elaborate(
            ElaborateRequest(
                rules=("Act only after explicit confirmation.",),
                number=1,
                strict=True,
            ),
            provider_factory=lambda: (_ for _ in ()).throw(
                AssertionError("policy mismatch must fail before provider")
            ),
            prepared_lookup=lambda _request, _config: live.analysis,
        )


def test_elaborate_rejects_an_analysis_from_the_prior_provider_contract() -> None:
    live = execute_elaborate(
        ElaborateRequest(goal="Confirm before acting."),
        provider_factory=ElaborateProvider,
    )

    with pytest.raises(
        ElaborateError,
        match="Unsupported Elaborate provider contract version",
    ):
        replace(live.analysis, provider_contract_version=1)


def test_elaborate_rejects_nonexact_prepared_result() -> None:
    live = execute_elaborate(
        ElaborateRequest(goal="Confirm before acting."),
        provider_factory=ElaborateProvider,
    )

    with pytest.raises(ElaborateError, match="does not exactly match"):
        execute_elaborate(
            ElaborateRequest(goal="Confirm a different action."),
            provider_factory=lambda: (_ for _ in ()).throw(
                AssertionError("a nonexact prepared result must fail closed")
            ),
            prepared_lookup=lambda _request, _config: live.analysis,
        )


def test_elaborate_prepared_result_must_match_the_exact_number() -> None:
    provider = ExactNumberProvider()
    live = execute_elaborate(
        ElaborateRequest(goal="Confirm before acting.", number=1),
        provider_factory=lambda: provider,
    )

    with pytest.raises(ElaborateError, match="does not exactly match"):
        execute_elaborate(
            ElaborateRequest(goal="Confirm before acting.", number=2),
            provider_factory=lambda: (_ for _ in ()).throw(
                AssertionError("a nonexact prepared result must fail closed")
            ),
            prepared_lookup=lambda _request, _config: live.analysis,
        )


def test_elaborate_live_plan_rejects_oversized_input_before_provider() -> None:
    provider_constructions = 0

    def provider_factory():
        nonlocal provider_constructions
        provider_constructions += 1
        return ElaborateProvider()

    config = ElaborateSemanticConfig(text_limit=600_100)
    with pytest.raises(ElaborateError, match="shared Conformance/Fit"):
        execute_elaborate(
            ElaborateRequest(
                rules=("A" * 600_000, "B" * 600_000),
                strict=True,
            ),
            provider_factory=provider_factory,
            config=config,
        )

    assert provider_constructions == 0


def test_rules_elaborate_rejects_oversized_validation_frame_before_provider() -> None:
    provider_constructions = 0

    def provider_factory():
        nonlocal provider_constructions
        provider_constructions += 1
        return ExactNumberProvider()

    with pytest.raises(ElaborateError, match="validation frame exceeds"):
        execute_elaborate(
            ElaborateRequest(
                rules=("Apply the complete Rule.",),
                number=2_001,
                strict=True,
            ),
            provider_factory=provider_factory,
        )

    assert provider_constructions == 0


def test_rules_elaborate_accepts_collection_level_rule_applicability() -> None:
    class CollectionProvider(ExactNumberProvider):
        def complete(self, prompt, *, operation, output_schema=None):
            if operation == CONTEXT_CONFORMANCE_OPERATION:
                payload = json.loads(
                    prompt.split("CONFORMANCE CONTEXT PAYLOAD:\n", 1)[1]
                )
                memory_ids = [
                    item["memory_id"]
                    for item in payload["target_context"]["memories"]
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
    result = execute_elaborate(
        ElaborateRequest(
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
    assert result.analysis.quality_policy is ElaborateQualityPolicy.STRICT
    assert "ordered collection or family" in provider.calls[0][2]
    assert "applicable to that member" in provider.calls[0][2]
    assert "`COLLECTION:`" in provider.calls[0][2]


def test_elaborate_application_imports_no_terminal_or_command_adapter() -> None:
    source = Path(elaborate_application.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.append(node.module)

    assert tuple(
        name
        for name in imports
        if name == "typer"
        or name.startswith("prompt_toolkit")
        or name.startswith("memcommit.commands")
    ) == ()


def test_elaborate_result_limits_follow_the_injected_config() -> None:
    request = ElaborateRequest(goal="G" * 2_100)
    result = execute_elaborate(
        request,
        provider_factory=ElaborateProvider,
        config=ElaborateSemanticConfig(text_limit=2_200),
    )

    assert result.analysis.inputs == (request.goal,)


def test_elaborate_prepared_result_is_revalidated_against_current_config() -> None:
    request = ElaborateRequest(goal="Confirm.")
    live = execute_elaborate(request, provider_factory=ElaborateProvider)

    with pytest.raises(ElaborateError, match="semantic config does not match"):
        execute_elaborate(
            request,
            provider_factory=lambda: (_ for _ in ()).throw(
                AssertionError("prepared validation must happen before provider")
            ),
            prepared_lookup=lambda _request, _config: live.analysis,
            config=ElaborateSemanticConfig(text_limit=20),
        )


def test_elaborate_shared_viewer_copies_one_proposal_or_all() -> None:
    result = execute_elaborate(
        ElaborateRequest(goal="Confirm before acting."),
        provider_factory=ElaborateProvider,
    )
    document = project_elaborate_result(result)
    rendered = "".join(
        text for _style, text in document.render(focused_uid="ELABORATE:TITLE")
    )
    focused = project_elaborate_clipboard(
        result,
        focused_uid="ELABORATE:RULE:0",
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
        returned = run_elaborate_tui(
            result,
            clipboard_writer=copied.append,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
    assert returned == result
    assert copied[0].startswith("[Suggested] [Unverified]")
    assert "PROPOSAL OVERVIEW" in copied[1]


def _bound_ground(store: MemoryStore):
    raw = Context(uid="00000000-0000-4000-8000-000000000101", name="ground/raw")
    candidates = Context(
        uid="00000000-0000-4000-8000-000000000102",
        name="ground/candidates",
    )
    candidates.add(
        Memory(
            uid="00000000-0000-4000-8000-000000000104",
            content="A person explicitly confirmed option A before it was used.",
        )
    )
    target = Context(
        uid="00000000-0000-4000-8000-000000000103",
        name="ground/target",
    )
    for context in (raw, candidates, target):
        store.create_context(context)
    session = bind_ground_workbench(
        create_ground_session(
            "elaborate-ground",
            goal="Confirm a chosen option before acting.",
        ),
        description="Build a reviewed confirmation behavior contract.",
        raw_context=raw,
        derived_context=candidates,
        target_contexts=(target,),
        target_requirements=(
            GroundTargetSpec(
                context_name=target.name,
                description="Add one reviewed confirmation Case.",
                role="PUBLICATION_TARGET",
            ),
        ),
    )
    store.save_ground_session(session)
    return session, (raw, candidates, target)


def test_ground_and_standalone_use_the_same_elaborate_application(isolated_store):
    store = MemoryStore()
    session, contexts = _bound_ground(store)
    provider = ElaborateProvider()
    frozen = freeze_ground_elaborate(
        store,
        ground_name=session.contract_name,
        direction="GOAL_TO_RULES",
    )

    ground_result = execute_ground_elaborate(
        frozen,
        store=store,
        provider_factory=lambda: provider,
    )

    assert ground_result.frozen.request == ElaborateRequest(goal=session.goal)
    assert ground_result.elaborate.analysis.rules[0].content == (
        "Confirm the selected option before acting."
    )
    assert store.load_ground_session(session.contract_name) == session
    assert all(store.list_checkpoints(context.name) == [] for context in contexts)


def test_ground_elaborate_preserves_the_exact_number(isolated_store):
    store = MemoryStore()
    session, _contexts = _bound_ground(store)
    provider = ExactNumberProvider()
    frozen = freeze_ground_elaborate(
        store,
        ground_name=session.contract_name,
        direction="GOAL_TO_RULES",
        number=2,
    )

    result = execute_ground_elaborate(
        frozen,
        store=store,
        provider_factory=lambda: provider,
    )

    assert frozen.request.number == 2
    assert result.elaborate.analysis.number == 2
    assert len(result.elaborate.analysis.rules) == 2


def test_ground_rules_use_the_same_rules_to_cases_application(isolated_store):
    store = MemoryStore()
    session, contexts = _bound_ground(store)
    before = session
    session = propose_ground_rule(
        session,
        rule="Act only after explicit confirmation.",
        rationale="This is the Rule under review.",
        current_contexts=contexts,
    )
    store.save_ground_session(
        session,
        expected_uid=session.uid,
        expected_revision=0,
        expected_digest=ground_session_record_digest(before),
    )
    frozen = freeze_ground_elaborate(
        store,
        ground_name=session.contract_name,
        direction="RULES_TO_CASES",
        number=1,
    )

    result = execute_ground_elaborate(
        frozen,
        store=store,
        provider_factory=ElaborateProvider,
    )

    assert result.elaborate.analysis.mode is ElaborateMode.RULES_TO_CASES
    assert len(result.elaborate.analysis.cases) == 1
    assert store.load_ground_session(session.contract_name) == session


def test_ground_elaborate_rejects_stale_revision_before_provider(isolated_store):
    store = MemoryStore()
    session, contexts = _bound_ground(store)
    frozen = freeze_ground_elaborate(
        store,
        ground_name=session.contract_name,
        direction="GOAL_TO_RULES",
    )
    changed = propose_ground_rule(
        session,
        rule="A concurrent Rule.",
        rationale="Simulate another reviewed Ground turn.",
        current_contexts=contexts,
    )
    store.save_ground_session(
        changed,
        expected_uid=session.uid,
        expected_revision=session.revision,
        expected_digest=ground_session_record_digest(session),
    )
    provider = ElaborateProvider()

    with pytest.raises(ElaborateError, match="changed before Elaborate began"):
        execute_ground_elaborate(
            frozen,
            store=store,
            provider_factory=lambda: provider,
        )

    assert provider.calls == []


def test_ground_elaborate_rejects_revision_change_during_provider(isolated_store):
    store = MemoryStore()
    session, contexts = _bound_ground(store)
    frozen = freeze_ground_elaborate(
        store,
        ground_name=session.contract_name,
        direction="GOAL_TO_RULES",
    )

    class ConcurrentProvider(ElaborateProvider):
        def complete(self, prompt, *, operation, output_schema=None):
            current = store.load_ground_session(session.contract_name)
            assert current is not None
            changed = propose_ground_rule(
                current,
                rule="A concurrent Rule.",
                rationale="Simulate another reviewed Ground turn.",
                current_contexts=contexts,
            )
            store.save_ground_session(
                changed,
                expected_uid=current.uid,
                expected_revision=current.revision,
                expected_digest=ground_session_record_digest(current),
            )
            return super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )

    provider = ConcurrentProvider()
    with pytest.raises(ElaborateError, match="changed while Elaborate was running"):
        execute_ground_elaborate(
            frozen,
            store=store,
            provider_factory=lambda: provider,
        )

    assert len(provider.calls) == 1
    assert all(store.list_checkpoints(context.name) == [] for context in contexts)


def test_mem_elaborate_plain_uses_the_typed_application(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    target = ops.init("elaborate/inline-target")
    store.create_context(target)
    store.set_current(target.name)
    monkeypatch.setattr(
        elaborate_command,
        "connect_semantic_provider",
        ElaborateProvider,
    )

    result = runner.invoke(
        app,
        ["elaborate", "--goal", "Confirm before acting.", "--plain"],
    )

    assert result.exit_code == 0, result.output
    assert "ELABORATE APPLIED · elaborate/inline-target" in result.output
    assert "MODE · GOAL_TO_RULES · VERIFICATION · UNVERIFIED" in result.output
    assert "EFFECTS · ADD 3 MEMORIES" in result.output
    assert "REVIEW · mem review elaborate --receipt" in result.output
    assert len(store.load_direct(target.name).order) == 3


def test_mem_elaborate_ground_adopt_is_an_explicit_physical_write(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(
            name="physical-elaborate",
            goal="Confirm a chosen option before acting.",
        ),
        store=store,
    )
    monkeypatch.setattr(
        elaborate_command,
        "connect_semantic_provider",
        ElaborateProvider,
    )

    result = runner.invoke(
        app,
        [
            "elaborate",
            "--ground",
            "physical-elaborate",
            "--from-goal",
            "--adopt",
            "--plain",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "ELABORATE ADOPTED · physical-elaborate/rules" in result.output
    assert "EFFECTS · ADD 3 MEMORIES" in result.output
    assert len(
        tuple(load_ground_workspace(store, "physical-elaborate").rules.iter_items())
    ) == 3


def test_physical_ground_goal_elaborate_freezes_only_the_goal_memory(
    isolated_store,
):
    store = MemoryStore()
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(
            name="physical-elaborate",
            goal="Confirm a chosen option before acting.",
        ),
        store=store,
    )
    frozen = freeze_ground_elaborate(
        store,
        ground_name="physical-elaborate",
        direction="GOAL_TO_RULES",
    )
    # An Example is outside this direction's consumed frame and must not make
    # a safe cached/provider request stale.
    execute_ground_workspace_memory_add(
        AddGroundWorkspaceMemoryRequest(
            workspace_name="physical-elaborate",
            lane="examples",
            content="A person explicitly confirms option A.",
        ),
        store=store,
    )
    provider = ElaborateProvider()

    result = execute_ground_elaborate(
        frozen,
        store=store,
        provider_factory=lambda: provider,
    )

    assert result.frozen.request.goal == "Confirm a chosen option before acting."
    assert result.frozen.request.goal_focus is not None
    assert result.frozen.request.goal_focus.kind == "GROUND"
    assert result.frozen.request.goal_focus.items[0].memory_uid is not None
    assert len(provider.calls) == 1


def test_physical_ground_elaborate_adopts_rules_as_one_ground_command(
    isolated_store,
):
    store = MemoryStore()
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(
            name="physical-elaborate",
            goal="Confirm a chosen option before acting.",
        ),
        store=store,
    )
    frozen = freeze_ground_elaborate(
        store,
        ground_name="physical-elaborate",
        direction="GOAL_TO_RULES",
    )
    proposal = execute_ground_elaborate(
        frozen,
        store=store,
        provider_factory=ElaborateProvider,
    )

    receipt = apply_ground_elaborate_result(proposal, store=store)

    workspace = load_ground_workspace(store, "physical-elaborate")
    assert receipt.revision == frozen.ground_revision + 1
    assert len(tuple(workspace.rules.iter_items())) == 3
    [unit] = build_ground_workspace_command_stack(
        store,
        "physical-elaborate",
    ).undo
    assert unit.action == "adopt-elaborate"
    undo_ground_workspace_command(store, "physical-elaborate")
    assert tuple(
        load_ground_workspace(store, "physical-elaborate").rules.iter_items()
    ) == ()


def test_physical_ground_elaborate_adoption_rejects_changed_ground_revision(
    isolated_store,
):
    store = MemoryStore()
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(
            name="physical-elaborate",
            goal="Confirm a chosen option before acting.",
        ),
        store=store,
    )
    frozen = freeze_ground_elaborate(
        store,
        ground_name="physical-elaborate",
        direction="GOAL_TO_RULES",
    )
    proposal = execute_ground_elaborate(
        frozen,
        store=store,
        provider_factory=ElaborateProvider,
    )
    execute_ground_workspace_memory_add(
        AddGroundWorkspaceMemoryRequest(
            workspace_name="physical-elaborate",
            lane="examples",
            content="An independently reviewed Example.",
        ),
        store=store,
    )

    with pytest.raises(ElaborateError, match="changed after the Elaborate"):
        apply_ground_elaborate_result(proposal, store=store)


def test_physical_ground_rules_elaborate_and_fail_on_consumed_rule_drift(
    isolated_store,
):
    store = MemoryStore()
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(name="physical-elaborate"),
        store=store,
    )
    execute_ground_workspace_memory_add(
        AddGroundWorkspaceMemoryRequest(
            workspace_name="physical-elaborate",
            lane="rules",
            content="Act only after explicit confirmation.",
        ),
        store=store,
    )
    frozen = freeze_ground_elaborate(
        store,
        ground_name="physical-elaborate",
        direction="RULES_TO_CASES",
    )
    rules = store.load_for_update("physical-elaborate/rules")
    rules.add("A concurrent consumed Rule.")
    store.save(rules)
    provider = ElaborateProvider()

    with pytest.raises(ElaborateError, match="consumed Ground workspace"):
        execute_ground_elaborate(
            frozen,
            store=store,
            provider_factory=lambda: provider,
        )

    assert provider.calls == []


def test_physical_ground_elaborate_rejects_typed_rule_before_provider(
    isolated_store,
):
    store = MemoryStore()
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(name="physical-elaborate"),
        store=store,
    )
    source = ops.init("physical-elaborate/external-rules")
    memory = ops.add(source, "Act only after explicit confirmation.")
    store.create_context(source)
    rules = store.load_for_update("physical-elaborate/rules")
    ops.embed_memory(memory, source, rules)
    store.save(rules)

    with pytest.raises(ElaborateError, match="authority-aware Ground projection"):
        freeze_ground_elaborate(
            store,
            ground_name="physical-elaborate",
            direction="RULES_TO_CASES",
        )
