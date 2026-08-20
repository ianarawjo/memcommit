"""Reviewed café regression for Distill reduction and Elaborate generation."""

from __future__ import annotations

import json
from pathlib import Path
import re

from memcommit.context import Context, Memory
from memcommit.distill import DISTILL_PAYLOAD_MARKER, analyze_distill
from memcommit.elaborate import ELABORATE_PAYLOAD_MARKER
from memcommit.elaborate_application import ElaborateRequest
from memcommit.elaborate_runtime import execute_elaborate
from memcommit.summarize import collect_summary_frame


FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "memcommit"
    / "eval"
    / "fixtures"
    / "distill_elaborate.json"
)


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _cafe_frame(example_memories: list[str]):
    context = Context(
        uid="00000000-0000-4000-8000-000000000901",
        name="calibration/cafe/examples",
    )
    for index, content in enumerate(example_memories, 1):
        context.add(
            Memory(
                uid=f"00000000-0000-4000-8000-{900 + index:012d}",
                content=content,
            )
        )
    return collect_summary_frame(context)


def _cloze_frame(example_memories: list[str]):
    context = Context(
        uid="00000000-0000-4000-8000-000000000951",
        name="calibration/cloze/examples",
    )
    for index, content in enumerate(example_memories, 1):
        context.add(
            Memory(
                uid=f"00000000-0000-4000-8000-{950 + index:012d}",
                content=content,
            )
        )
    return collect_summary_frame(context)


def test_cafe_fixture_contains_actual_known_wrong_and_reviewed_io() -> None:
    fixture = _fixture()

    assert fixture["schema_version"] == 1
    assert fixture["ruleset_version"] == 2
    assert len(fixture["shared_example_memories"]) == 3
    assert len(fixture["shared_rule_memories"]) == 7
    assert fixture["distill_cases"][0]["known_wrong_rules"]
    assert fixture["elaborate_cases"][0]["known_wrong_cases"]
    assert fixture["distill_cases"][0]["expected_rule_memory_indexes"] == list(
        range(1, 8)
    )
    assert fixture["elaborate_cases"][0]["required_rule_indexes_per_example"] == list(
        range(1, 8)
    )


def test_cloze_surface_form_fixture_is_a_literal_three_part_transformation() -> None:
    cloze = _fixture()["surface_form_calibrations"]["cloze"]

    assert len(cloze["rule_memories"]) == 4
    assert len(cloze["example_memories"]) == 3
    assert cloze["known_wrong_rules"]
    for memory in cloze["example_memories"]:
        example_section, cloze_section, meaning_section = memory.split("\n\n")
        example = example_section.removeprefix("EXAMPLE\n")
        masked = cloze_section.removeprefix("CLOZE\n")
        match = re.search(r"\{\{c1::([^{}]+)\}\}", masked)
        assert match is not None
        target = match.group(1)
        assert masked.replace(match.group(0), target) == example
        meaning = meaning_section.removeprefix("뜻 설명\n")
        assert meaning.startswith(target)
        assert meaning.endswith("뜻이다.")


def test_distill_cloze_fixture_requires_shared_language_tone_and_notation_rules() -> None:
    cloze = _fixture()["surface_form_calibrations"]["cloze"]
    examples = cloze["example_memories"]
    expected_rules = cloze["rule_memories"]

    class ReviewedSurfaceDistillProvider:
        prompt = ""

        def complete(self, prompt, *, operation, output_schema=None):
            type(self).prompt = prompt
            payload = json.loads(prompt.split(DISTILL_PAYLOAD_MARKER, 1)[1])
            aliases = [item["memory_id"] for item in payload["source"]["memories"]]
            return json.dumps(
                {
                    "overview": "공통 언어, 어투, 라벨과 Cloze 표기법을 환원한다.",
                    "rules": [
                        {
                            "content": content,
                            "rationale": "세 Cloze Example에 문자 그대로 반복되는 생성 형식이다.",
                            "support_memory_ids": aliases,
                            "boundary_memory_ids": [],
                        }
                        for content in expected_rules
                    ],
                    "outside_memory_ids": [],
                },
                ensure_ascii=False,
            )

    analysis = analyze_distill(
        _cloze_frame(examples),
        goal=None,
        provider=ReviewedSurfaceDistillProvider(),
    )

    assert [rule.content for rule in analysis.rules] == expected_rules
    assert all(len(rule.support_memory_uids) == 3 for rule in analysis.rules)
    prompt = ReviewedSurfaceDistillProvider.prompt
    assert "surface-form audit is mandatory" in prompt
    assert "language and language-mixing pattern" in prompt
    assert "register, tone, formality" in prompt
    assert "section labels and their order" in prompt
    assert "markup, placeholders, delimiters, symbols" in prompt
    assert "particles, inflection" in prompt
    assert "compare the literal character sequence" in prompt
    assert "state only the observed alternatives" in prompt
    assert "do not infer a hidden linguistic cause" in prompt
    assert "Support and boundary aliases for one Rule must be disjoint" in prompt
    assert "mechanical consequence of another Rule" in prompt


def test_distill_cafe_fixture_recovers_behavior_and_generative_form_rules() -> None:
    fixture = _fixture()
    examples = fixture["shared_example_memories"]
    expected_rules = fixture["shared_rule_memories"]

    class ReviewedDistillProvider:
        prompt = ""

        def complete(self, prompt, *, operation, output_schema=None):
            type(self).prompt = prompt
            payload = json.loads(prompt.split(DISTILL_PAYLOAD_MARKER, 1)[1])
            aliases = [item["memory_id"] for item in payload["source"]["memories"]]
            return json.dumps(
                {
                    "overview": "행동과 반복되는 생성 형식을 함께 환원한다.",
                    "rules": [
                        {
                            "content": content,
                            "rationale": "세 카페 Example에 반복되는 생성 불변조건이다.",
                            "support_memory_ids": aliases,
                            "boundary_memory_ids": [],
                        }
                        for content in expected_rules
                    ],
                    "outside_memory_ids": [],
                },
                ensure_ascii=False,
            )

    analysis = analyze_distill(
        _cafe_frame(examples),
        goal=None,
        provider=ReviewedDistillProvider(),
    )

    assert [rule.content for rule in analysis.rules] == expected_rules
    assert all(len(rule.support_memory_uids) == 3 for rule in analysis.rules)
    assert "presentation or narrative form" in ReviewedDistillProvider.prompt
    assert "topic label or a broad summary" in ReviewedDistillProvider.prompt


def test_elaborate_cafe_fixture_requires_every_rule_in_every_example() -> None:
    fixture = _fixture()
    rules = fixture["shared_rule_memories"]
    examples = fixture["shared_example_memories"]

    class ReviewedElaborateProvider:
        prompt = ""

        def complete(self, prompt, *, operation, output_schema=None):
            type(self).prompt = prompt
            payload = json.loads(prompt.split(ELABORATE_PAYLOAD_MARKER, 1)[1])
            checks = [
                {
                    "source_rule_index": index,
                    "evidence": f"이 Example은 Rule {index}의 구조를 직접 보여준다.",
                }
                for index, _rule in enumerate(payload["inputs"], 1)
            ]
            return json.dumps(
                {
                    "overview": "각 Example이 일곱 Rule을 함께 구현한다.",
                    "cases": [
                        {
                            "proposition": content,
                            "expected": "일곱 Rule을 모두 구현하는 완전한 Example Memory이다.",
                            "rationale": "고정 구조를 유지하고 음료별 값만 바꾼다.",
                            "case_role": role,
                            "rule_checks": checks,
                        }
                        for content, role in zip(
                            examples,
                            ("FIT", "BOUNDARY", "CONTRAST"),
                            strict=True,
                        )
                    ],
                },
                ensure_ascii=False,
            )

    result = execute_elaborate(
        ElaborateRequest(rules=tuple(rules)),
        provider_factory=ReviewedElaborateProvider,
    )

    assert [case.proposition for case in result.analysis.cases] == examples
    assert all(
        tuple(check.source_rule_index for check in case.rule_checks)
        == tuple(range(1, 8))
        for case in result.analysis.cases
    )
    assert "complete input Rule set together" in ReviewedElaborateProvider.prompt
    assert "stored proposition must still show the Rule-compliant handling" in (
        ReviewedElaborateProvider.prompt
    )
