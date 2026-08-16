"""Agent handoff across Ground semantic analysis, Resolve review, and Apply."""

from __future__ import annotations

import json
import uuid

from memcommit.api import MemCommitClient
from memcommit.context import Context
from memcommit.elaborate import ELABORATE_PAYLOAD_MARKER
from memcommit.fit_judgment import FIT_JUDGMENT_PAYLOAD_MARKER
from memcommit.ground import (
    GroundTargetSpec,
    bind_ground_workbench,
    create_ground_session,
    propose_ground_example,
    propose_ground_rule,
    upgrade_ground_to_propositions,
)
from memcommit.interfaces.agent import (
    ELABORATE_AGENT_TOOL_NAME,
    GROUND_RESOLUTION_AGENT_TOOL_NAME,
    build_default_agent_tool_registry,
)
from memcommit.store import MemoryStore


class GroundWorkflowProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert output_schema is not None
        if operation == "fit_propositions":
            payload = json.loads(prompt.split(FIT_JUDGMENT_PAYLOAD_MARKER, 1)[1])
            return json.dumps(
                {
                    "overview": "The Rule leaves a single-word boundary open.",
                    "judgments": [
                        {
                            "question_id": question["question_id"],
                            "verdict": "MAY",
                            "reason": "The Rule does not select the exact letters.",
                            "considered_proposition_ids": [
                                item["proposition_id"]
                                for item in question["propositions"]
                            ],
                            "material_proposition_ids": [
                                item["proposition_id"]
                                for item in question["propositions"]
                            ],
                            "consistent_reading": "The mnemonic could be RED.",
                            "inconsistent_reading": "The mnemonic could be RWD.",
                        }
                        for question in payload["questions"]
                    ],
                }
            )
        payload = json.loads(prompt.split(ELABORATE_PAYLOAD_MARKER, 1)[1])
        assert payload["mode"] == "GOAL_TO_RULES"
        return json.dumps(
            {
                "overview": "One normalization candidate.",
                "rules": [
                    {
                        "content": "Remove legal-form suffixes before ticker generation.",
                        "rationale": "This is a Goal-derived hypothesis.",
                    }
                ],
            }
        )


def _ground(store: MemoryStore):
    description = Context(uid=str(uuid.uuid4()), name="agent/resolve-description")
    examples = Context(uid=str(uuid.uuid4()), name="agent/resolve-examples")
    output = Context(uid=str(uuid.uuid4()), name="agent/resolve-output")
    for context in (description, examples, output):
        store.create_context(context)
    contexts = (description, examples, output)
    session = bind_ground_workbench(
        create_ground_session(
            "agent-resolve-ground",
            goal="티커가 어떻게 만들어지는지 규칙을 알고 싶어",
        ),
        description="Refine synthetic ticker Rules from reviewed Examples.",
        raw_context=description,
        derived_context=examples,
        target_contexts=(output,),
        target_requirements=(
            GroundTargetSpec(
                context_name=output.name,
                description="Retain reviewed ticker Rules.",
                role="PUBLICATION_TARGET",
            ),
        ),
    )
    session = upgrade_ground_to_propositions(session)
    session = propose_ground_rule(
        session,
        rule="Use one initial per meaningful company-name token.",
        rationale="Start with an intentionally incomplete Rule.",
        current_contexts=contexts,
    )
    session = propose_ground_example(
        session,
        proposition=(
            'Applying the synthetic ticker Rules to "Redwood Inc." '
            'produces "RED".'
        ),
        rationale="A single-word boundary Example.",
        current_contexts=contexts,
        case_role="BOUNDARY",
    )
    store.save_ground_session(session)
    return session


def test_agent_elaborate_plan_and_apply_are_three_distinct_calls(
    isolated_store,
) -> None:
    store = MemoryStore()
    session = _ground(store)
    registry = build_default_agent_tool_registry(
        MemCommitClient(
            root=isolated_store,
            semantic_provider_factory=GroundWorkflowProvider,
        )
    )

    analyzed = registry.invoke(
        ELABORATE_AGENT_TOOL_NAME,
        {
            "version": 1,
            "kind": "ground_goal_to_rules",
            "ground_name": session.contract_name,
        },
    )
    candidate = analyzed["result"]["rules"][0]
    planned = registry.invoke(
        GROUND_RESOLUTION_AGENT_TOOL_NAME,
        {
            "version": 1,
            "kind": "plan_candidate",
            "artifact_uid": analyzed["result"]["analysis_uid"],
            "candidate_uid": candidate["uid"],
        },
    )

    assert analyzed["ok"] is True
    assert planned["ok"] is True
    assert planned["result"]["effect"] == "NONE"
    assert planned["result"]["source_verification"] == "UNVERIFIED"
    assert planned["result"]["action"]["content"] == candidate["content"]
    assert store.load_ground_session(session.contract_name) == session

    applied = registry.invoke(
        GROUND_RESOLUTION_AGENT_TOOL_NAME,
        planned["result"]["apply_request"],
    )

    assert applied["ok"] is True
    assert applied["result"]["effect"] == "GROUND_REVISION"
    assert applied["result"]["previous_revision"] == session.revision
    assert applied["result"]["resulting_revision"] == session.revision + 1
    saved = store.load_ground_session(session.contract_name)
    assert saved is not None
    assert saved.items_of_kind("RULE")[-1].content == candidate["content"]


def test_agent_ground_fit_can_defer_without_a_ground_revision(isolated_store) -> None:
    store = MemoryStore()
    session = _ground(store)
    registry = build_default_agent_tool_registry(
        MemCommitClient(
            root=isolated_store,
            semantic_provider_factory=GroundWorkflowProvider,
        )
    )

    fit = registry.invoke(
        GROUND_RESOLUTION_AGENT_TOOL_NAME,
        {
            "version": 1,
            "kind": "fit_ground",
            "ground_name": session.contract_name,
        },
    )
    judgment = fit["result"]["judgments"][0]
    planned = registry.invoke(
        GROUND_RESOLUTION_AGENT_TOOL_NAME,
        {
            "version": 1,
            "kind": "plan_fit",
            "artifact_uid": fit["result"]["artifact_uid"],
            "example_uid": judgment["example_uid"],
            "action": "DEFER",
            "rationale": "Wait for an approved policy instead of guessing.",
        },
    )
    applied = registry.invoke(
        GROUND_RESOLUTION_AGENT_TOOL_NAME,
        planned["result"]["apply_request"],
    )

    assert fit["ok"] is True
    assert fit["result"]["current"] is True
    assert judgment["status"] == "UNDERDETERMINED"
    assert planned["result"]["action"]["kind"] == "DEFER"
    assert applied["result"]["mutated"] is False
    assert applied["result"]["effect"] == "NONE"
    assert store.load_ground_session(session.contract_name) == session


def test_agent_resolve_requires_a_retained_process_local_artifact(
    isolated_store,
) -> None:
    registry = build_default_agent_tool_registry(
        MemCommitClient(root=isolated_store)
    )

    response = registry.invoke(
        GROUND_RESOLUTION_AGENT_TOOL_NAME,
        {
            "version": 1,
            "kind": "plan_candidate",
            "artifact_uid": str(uuid.uuid4()),
            "candidate_uid": str(uuid.uuid4()),
        },
    )

    assert response["error"]["code"] == "artifact_expired"
    assert response["error"]["retryable"] is False
