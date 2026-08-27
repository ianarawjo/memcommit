"""Ground Distill consumes only active Examples whose durable USE is on."""

from __future__ import annotations

import json

import pytest

from memcommit.core.context import Context, Memory
from memcommit.application.operations.distill.model import DISTILL_PAYLOAD_MARKER, DistillError
from memcommit.application.operations.ground.model import (
    GroundTargetSpec,
    bind_ground_workbench,
    create_ground_session,
    propose_ground_case,
    propose_ground_rule,
    set_ground_example_use,
)
from memcommit.application.operations.ground.distill import execute_ground_distill, freeze_ground_distill
from memcommit.persistence.store import MemoryStore
from tests.distill_goal_fit_support import passing_distill_goal_fit_response


class CapturingDistillProvider:
    def __init__(self) -> None:
        self.payloads: list[dict[str, object]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        validation = passing_distill_goal_fit_response(prompt, operation)
        if validation is not None:
            return validation
        payload = json.loads(prompt.split(DISTILL_PAYLOAD_MARKER, 1)[1])
        self.payloads.append(payload)
        memories = payload["source"]["memories"]
        rule = {
            "content": "Use the reviewed ticker for the company.",
            "rationale": "The included Example supports it.",
            "support_memory_ids": [memories[0]["memory_id"]],
            "boundary_memory_ids": [],
        }
        rule_properties = (
            output_schema.get("properties", {})
            .get("rules", {})
            .get("items", {})
            .get("properties", {})
            if isinstance(output_schema, dict)
            else {}
        )
        if "goal_support" in rule_properties:
            # Ground USE is independent of the simultaneous Distill contract
            # migration that removes Goal-as-evidence. Keep this focused
            # fixture replayable on either side of that separate commit.
            rule["goal_support"] = False
        return json.dumps(
            {
                "overview": "The included Examples support one ticker Rule.",
                "rules": [rule],
                "outside_memory_ids": [
                    memory["memory_id"] for memory in memories[1:]
                ],
            }
        )


def _ground_with_two_examples(store: MemoryStore):
    raw = Context(
        uid="20000000-0000-4000-8000-000000000001",
        name="distill-use/raw",
    )
    candidates = Context(
        uid="20000000-0000-4000-8000-000000000002",
        name="distill-use/candidates",
    )
    sources = (
        Memory(
            uid="20000000-0000-4000-8000-000000000011",
            content="Apple Inc.",
        ),
        Memory(
            uid="20000000-0000-4000-8000-000000000012",
            content="Google LLC",
        ),
    )
    for source in sources:
        candidates.add(source)
    target = Context(
        uid="20000000-0000-4000-8000-000000000003",
        name="distill-use/rules",
    )
    for context in (raw, candidates, target):
        store.create_context(context)
    contexts = (raw, candidates, target)
    session = bind_ground_workbench(
        create_ground_session(
            "distill-use-ground",
            goal="Derive reusable ticker Rules from reviewed Examples.",
        ),
        description="Review which ticker Examples support distillation.",
        raw_context=raw,
        derived_context=candidates,
        target_contexts=(target,),
        target_requirements=(
            GroundTargetSpec(
                context_name=target.name,
                description="Publish reviewed ticker Rules.",
                role="PUBLICATION_TARGET",
            ),
        ),
    )
    session = propose_ground_rule(
        session,
        rule="Use a company's reviewed short ticker.",
        rationale="The Examples need a candidate Rule for Ground review.",
        current_contexts=contexts,
    )
    rule = session.items_of_kind("RULE")[0]
    for source, expected, disposition in (
        (sources[0], "AAPL", "INCLUDE"),
        (sources[1], "GOOG", "EXCLUDE"),
    ):
        session = propose_ground_case(
            session,
            rule_selector=rule.uid,
            case=source.content,
            source_context_uid=candidates.uid,
            source_memory_uid=source.uid,
            target_context_names=(target.name,),
            expected=expected,
            rationale="A concrete ticker Example.",
            current_contexts=contexts,
            disposition=disposition,
        )
    store.save_ground_session(session)
    return session, contexts


def _distill_payload(store: MemoryStore, ground_name: str):
    provider = CapturingDistillProvider()
    frozen = freeze_ground_distill(store, ground_name=ground_name)
    result = execute_ground_distill(
        frozen,
        store=store,
        provider_factory=lambda: provider,
    )
    assert result.frozen.source_kind == "GROUND_EXAMPLES"
    assert len(provider.payloads) == 1
    return provider.payloads[0]


def test_ground_distill_payload_tracks_durable_use_toggle(isolated_store):
    store = MemoryStore()
    session, contexts = _ground_with_two_examples(store)

    first_payload = _distill_payload(store, session.contract_name)
    assert [
        memory["content"] for memory in first_payload["source"]["memories"]
    ] == ["Apple Inc. -> AAPL"]

    google = session.items_of_kind("CASE")[1]
    updated = set_ground_example_use(
        session,
        google.uid,
        use="INCLUDE",
        current_contexts=contexts,
    )
    store.save_ground_session(updated)

    second_payload = _distill_payload(store, session.contract_name)
    assert [
        memory["content"] for memory in second_payload["source"]["memories"]
    ] == ["Apple Inc. -> AAPL", "Google LLC -> GOOG"]


def test_ground_distill_all_use_off_fails_before_provider_connection(
    isolated_store,
):
    store = MemoryStore()
    session, contexts = _ground_with_two_examples(store)
    apple, _google = session.items_of_kind("CASE")
    all_off = set_ground_example_use(
        session,
        apple.uid,
        use="EXCLUDE",
        current_contexts=contexts,
    )
    store.save_ground_session(all_off)
    constructed = []

    with pytest.raises(DistillError, match="no active INCLUDE Examples"):
        frozen = freeze_ground_distill(store, ground_name=session.contract_name)
        execute_ground_distill(
            frozen,
            store=store,
            provider_factory=lambda: constructed.append(True),
        )

    assert constructed == []
