"""Repeated Elaborate content remains a valid exact-count result."""

from __future__ import annotations

from dataclasses import replace
import json

import pytest
from typer.testing import CliRunner

import memcommit.commands.elaborate as elaborate_command
import memcommit.ops as ops
from memcommit.cli import app
from memcommit.elaborate import (
    ELABORATE_OPERATION,
    ELABORATE_PAYLOAD_MARKER,
    ElaborateError,
)
from memcommit.elaborate_application import ElaborateRequest
from memcommit.elaborate_runtime import execute_elaborate
from memcommit.store import MemoryStore
from tests.elaborate_validation_support import (
    passing_elaborate_validation_response,
)


runner = CliRunner()


class RepeatingElaborateProvider:
    """Return exact-count proposal occurrences with intentionally equal content."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def complete(self, prompt, *, operation, output_schema=None):
        validation = passing_elaborate_validation_response(prompt, operation)
        if validation is not None:
            return validation
        assert operation == ELABORATE_OPERATION
        assert output_schema is not None
        self.prompts.append(prompt)
        payload = json.loads(prompt.split(ELABORATE_PAYLOAD_MARKER, 1)[1])
        number = payload["number"]
        if payload["mode"] == "GOAL_TO_RULES":
            return json.dumps(
                {
                    "overview": "The requested Rule content intentionally repeats.",
                    "rules": [
                        {
                            "content": "Repeat this Rule exactly.",
                            "rationale": "The Goal requests a repeated Rule occurrence.",
                        }
                        for _ in range(number)
                    ],
                }
            )
        return json.dumps(
            {
                "overview": "The finite Rule frame intentionally repeats one Case.",
                "cases": [
                    {
                        "proposition": "a is apple",
                        "expected": "The proposition is accepted.",
                        "rationale": "This occurrence satisfies the complete Rule set.",
                        "case_role": "FIT",
                        "rule_checks": [
                            {
                                "source_rule_index": rule_index,
                                "evidence": "The proposition visibly follows this Rule.",
                            }
                            for rule_index, _rule in enumerate(payload["inputs"], 1)
                        ],
                    }
                    for _ in range(number)
                ],
            }
        )


def test_exact_count_accepts_repeated_rule_and_case_content() -> None:
    provider = RepeatingElaborateProvider()

    rules = execute_elaborate(
        ElaborateRequest(goal="Repeat one Rule four times.", number=4),
        provider_factory=lambda: provider,
    ).analysis.rules
    cases = execute_elaborate(
        ElaborateRequest(
            rules=(
                "Write `<lowercase letter> is <lowercase word>`.",
                "Use the mapping `a` to `apple`.",
            ),
            number=23,
        ),
        provider_factory=lambda: provider,
    ).analysis.cases

    assert [rule.content for rule in rules] == ["Repeat this Rule exactly."] * 4
    assert len({rule.uid for rule in rules}) == 4
    assert [case.proposition for case in cases] == ["a is apple"] * 23
    assert len({case.uid for case in cases}) == 23
    assert "Repeated Rule content is valid" in provider.prompts[0]
    assert "Repeated Case propositions are valid" in provider.prompts[1]


def test_repeated_content_still_requires_distinct_proposal_identities() -> None:
    analysis = execute_elaborate(
        ElaborateRequest(goal="Repeat one Rule twice.", number=2),
        provider_factory=RepeatingElaborateProvider,
    ).analysis

    with pytest.raises(ElaborateError, match="duplicate proposal identities"):
        replace(analysis, rules=(analysis.rules[0], analysis.rules[0]))


def test_standalone_add_materializes_every_repeated_case_occurrence(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    source = ops.init("repeat/source")
    ops.add(source, "Write `<lowercase letter> is <lowercase word>`.")
    ops.add(source, "Use the mapping `a` to `apple`.")
    target = ops.init("repeat/target")
    store.create_context(source)
    store.create_context(target)
    store.set_current(target.name)
    monkeypatch.setattr(
        elaborate_command,
        "connect_semantic_provider",
        RepeatingElaborateProvider,
    )

    result = runner.invoke(
        app,
        [
            "elaborate",
            "--from",
            source.name,
            "--to",
            target.name,
            "-n",
            "23",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "EFFECTS · ADD 23 MEMORIES" in result.output
    stored = tuple(store.load_direct(target.name).iter_items())
    assert [memory.content for memory in stored] == ["a is apple"] * 23
    assert len({memory.uid for memory in stored}) == 23

    checkpoint = store.list_checkpoints(target.name)[0]
    receipt = checkpoint["args"]["elaborate"]
    assert [proposal["content"] for proposal in receipt["proposals"]] == [
        "a is apple"
    ] * 23
    assert receipt["result_memory_uids"] == [memory.uid for memory in stored]
