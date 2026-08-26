"""Whole-corpus ordinary Query synthesis and host-owned citations."""

from __future__ import annotations

import json

import pytest

import memcommit.ops as ops
from memcommit.authority.access import resolve_context_access
from memcommit.operations.query.ordinary_application import (
    OrdinaryQueryRequest,
)
from memcommit.operations.query.ordinary_runtime import execute_ordinary_query
from memcommit.commands.shared.readable_context_catalog import (
    freeze_readable_context_catalog,
)
from memcommit.find_answer_references import FindAnswerEvidence
from memcommit.ordinary_query_answer import (
    OrdinaryQueryAnswerError,
    OrdinaryQueryCorpusTooLarge,
    build_ordinary_query_reference_document,
    complete_ordinary_query_answer,
    prepare_ordinary_query_answer,
)
from memcommit.store import MemoryStore


def _evidence() -> tuple[FindAnswerEvidence, ...]:
    return (
        FindAnswerEvidence(
            "m1",
            "task/left",
            "memory",
            "11111111-left",
            "Left-side example.",
        ),
        FindAnswerEvidence(
            "m2",
            "task/right",
            "memory",
            "22222222-right",
            "Right-side example.",
        ),
        FindAnswerEvidence(
            "m3",
            "task",
            "artifact",
            "33333333-comparison",
            "Comparison issues: none in the reviewed relation set.",
        ),
    )


class _Provider:
    def __init__(self, response: dict[str, object]):
        self.response = response
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls.append((prompt, operation, output_schema))
        return json.dumps(self.response, ensure_ascii=False)


def test_one_completion_returns_answer_and_aliases_then_host_numbers_references():
    evidence = _evidence()
    provider = _Provider(
        {
            "outcome_kind": "ANSWER",
            "blocks": [
                {
                    "role": "SUPPORTED_CLAIM",
                    "text": "두 쪽의 예시는 서로 다릅니다.",
                    "source_aliases": ["m1", "m2"],
                },
                {
                    "role": "SUPPORTED_CLAIM",
                    "text": "검토된 관계 집합에는 보고된 문제가 없습니다.",
                    "source_aliases": ["m3"],
                },
            ],
        }
    )

    plan = prepare_ordinary_query_answer("차이와 문제를 확인해줘", evidence)
    answer = complete_ordinary_query_answer(plan, provider)
    document = build_ordinary_query_reference_document(evidence, answer)

    assert len(provider.calls) == 1
    assert provider.calls[0][1] == "ordinary query"
    assert '"alias": "m1"' in provider.calls[0][0]
    assert '"alias": "m2"' in provider.calls[0][0]
    assert '"alias": "m3"' in provider.calls[0][0]
    assert document.body == (
        "두 쪽의 예시는 서로 다릅니다. [1] [2]\n\n"
        "검토된 관계 집합에는 보고된 문제가 없습니다. [3]"
    )
    assert [reference.evidence.alias for reference in document.references] == [
        "m1",
        "m2",
        "m3",
    ]
    assert document.text.count("References") == 1


@pytest.mark.parametrize(
    "response",
    [
        {
            "outcome_kind": "ANSWER",
            "blocks": [
                {
                    "role": "SUPPORTED_CLAIM",
                    "text": "Provider-authored [1] marker.",
                    "source_aliases": ["m1"],
                }
            ],
        },
        {
            "outcome_kind": "ANSWER",
            "blocks": [
                {
                    "role": "SUPPORTED_CLAIM",
                    "text": "Provider-authored [1, 2] markers.",
                    "source_aliases": ["m1"],
                }
            ],
        },
        {
            "outcome_kind": "ANSWER",
            "blocks": [
                {
                    "role": "SUPPORTED_CLAIM",
                    "text": "Temporary alias m1 in prose.",
                    "source_aliases": ["m1"],
                }
            ],
        },
        {
            "outcome_kind": "ANSWER",
            "blocks": [
                {
                    "role": "SUPPORTED_CLAIM",
                    "text": "Unsupported alias.",
                    "source_aliases": ["m99"],
                }
            ],
        },
        {
            "outcome_kind": "ANSWER",
            "blocks": [
                {
                    "role": "SUPPORTED_CLAIM",
                    "text": "Unsourced claim.",
                    "source_aliases": [],
                }
            ],
        },
    ],
)
def test_provider_cannot_forge_numbers_aliases_or_unsourced_claims(response):
    provider = _Provider(response)
    plan = prepare_ordinary_query_answer("question", _evidence())

    with pytest.raises(OrdinaryQueryAnswerError):
        complete_ordinary_query_answer(plan, provider)


def test_no_answer_is_explicit_and_has_no_reference_document():
    provider = _Provider(
        {
            "outcome_kind": "NO_ANSWER",
            "blocks": [
                {
                    "role": "SCOPE_LIMITATION",
                    "text": "The selected corpus does not support this answer.",
                    "source_aliases": [],
                }
            ],
        }
    )
    plan = prepare_ordinary_query_answer("unknown", _evidence())

    answer = complete_ordinary_query_answer(plan, provider)

    assert answer.grounded is False
    assert answer.text.startswith("The selected corpus")
    with pytest.raises(OrdinaryQueryAnswerError):
        build_ordinary_query_reference_document(_evidence(), answer)


@pytest.mark.parametrize(
    ("question", "response", "grounded", "expected_text"),
    [
        (
            "저장된 한 단어 인사말의 형식은?",
            {
                "outcome_kind": "ANSWER",
                "blocks": [
                    {
                        "role": "SUPPORTED_CLAIM",
                        "text": "소문자 한 단어를 구두점 없이 작성합니다.",
                        "source_aliases": ["m1"],
                    }
                ],
            },
            True,
            "소문자 한 단어를 구두점 없이 작성합니다. [1]",
        ),
        (
            "저장된 인사말 형식과 토론토의 내일 날씨를 알려줘.",
            {
                "outcome_kind": "PARTIAL_ANSWER",
                "blocks": [
                    {
                        "role": "SUPPORTED_CLAIM",
                        "text": "저장된 인사말 형식은 소문자 한 단어입니다.",
                        "source_aliases": ["m1"],
                    },
                    {
                        "role": "SCOPE_LIMITATION",
                        "text": "토론토 날씨 정보는 현재 Context에 없습니다.",
                        "source_aliases": [],
                    },
                ],
            },
            True,
            (
                "저장된 인사말 형식은 소문자 한 단어입니다. [1] "
                "토론토 날씨 정보는 현재 Context에 없습니다."
            ),
        ),
        (
            "토론토의 내일 날씨는?",
            {
                "outcome_kind": "NO_ANSWER",
                "blocks": [
                    {
                        "role": "SCOPE_LIMITATION",
                        "text": "현재 Context에는 토론토 날씨 정보가 없습니다.",
                        "source_aliases": [],
                    }
                ],
            },
            False,
            "현재 Context에는 토론토 날씨 정보가 없습니다.",
        ),
        (
            "안녕하세요",
            {
                "outcome_kind": "RELATED_OBSERVATION",
                "blocks": [
                    {
                        "role": "INPUT_INTERPRETATION",
                        "text": "질문이라기보다 인사로 보입니다.",
                        "source_aliases": [],
                    },
                    {
                        "role": "SUPPORTED_CLAIM",
                        "text": "현재 Context에는 관련 표현이 저장되어 있습니다.",
                        "source_aliases": ["m1"],
                    },
                ],
            },
            True,
            (
                "질문이라기보다 인사로 보입니다. 현재 Context에는 관련 "
                "표현이 저장되어 있습니다. [1]"
            ),
        ),
        (
            "오늘은 기분이 묘하네.",
            {
                "outcome_kind": "NO_RELATED_OBSERVATION",
                "blocks": [
                    {
                        "role": "INPUT_INTERPRETATION",
                        "text": "질문이라기보다 진술로 보입니다.",
                        "source_aliases": [],
                    },
                    {
                        "role": "SCOPE_LIMITATION",
                        "text": "현재 Context에서 관련 내용을 찾지 못했습니다.",
                        "source_aliases": [],
                    },
                ],
            },
            False,
            (
                "질문이라기보다 진술로 보입니다. 현재 Context에서 관련 "
                "내용을 찾지 못했습니다."
            ),
        ),
        (
            "인사?",
            {
                "outcome_kind": "AMBIGUOUS_OBSERVATION",
                "blocks": [
                    {
                        "role": "INPUT_INTERPRETATION",
                        "text": "구체적인 질문은 불분명합니다.",
                        "source_aliases": [],
                    },
                    {
                        "role": "SUPPORTED_CLAIM",
                        "text": "현재 Context에는 관련 항목이 있습니다.",
                        "source_aliases": ["m1"],
                    },
                ],
            },
            True,
            "구체적인 질문은 불분명합니다. 현재 Context에는 관련 항목이 있습니다. [1]",
        ),
    ],
)
def test_case_derived_outcomes_preserve_input_act_and_citation_roles(
    question,
    response,
    grounded,
    expected_text,
):
    evidence = _evidence()
    answer = complete_ordinary_query_answer(
        prepare_ordinary_query_answer(question, evidence),
        _Provider(response),
    )

    assert answer.grounded is grounded
    if grounded:
        assert build_ordinary_query_reference_document(evidence, answer).body == (
            expected_text
        )
    else:
        assert answer.text == expected_text


@pytest.mark.parametrize(
    "response",
    [
        {
            "outcome_kind": "RELATED_OBSERVATION",
            "blocks": [
                {
                    "role": "INPUT_INTERPRETATION",
                    "text": "This is a statement.",
                    "source_aliases": ["m1"],
                },
                {
                    "role": "SUPPORTED_CLAIM",
                    "text": "Related evidence exists.",
                    "source_aliases": ["m1"],
                },
            ],
        },
        {
            "outcome_kind": "PARTIAL_ANSWER",
            "blocks": [
                {
                    "role": "SUPPORTED_CLAIM",
                    "text": "Only the supported part.",
                    "source_aliases": ["m1"],
                }
            ],
        },
        {
            "outcome_kind": "NO_ANSWER",
            "blocks": [
                {
                    "role": "SUPPORTED_CLAIM",
                    "text": "This is not a no-answer.",
                    "source_aliases": ["m1"],
                }
            ],
        },
        {
            "outcome_kind": "AMBIGUOUS_OBSERVATION",
            "blocks": [
                {
                    "role": "INPUT_INTERPRETATION",
                    "text": "The input is ambiguous.",
                    "source_aliases": [],
                }
            ],
        },
    ],
)
def test_outcome_kind_and_block_roles_must_agree(response):
    with pytest.raises(OrdinaryQueryAnswerError):
        complete_ordinary_query_answer(
            prepare_ordinary_query_answer("input", _evidence()),
            _Provider(response),
        )


def test_prompt_and_schema_publish_the_case_derived_contract():
    plan = prepare_ordinary_query_answer("안녕하세요", _evidence())

    assert "ORDINARY QUERY PROVIDER CONTRACT VERSION 2" in plan.prompt
    assert "NO_RELATED_OBSERVATION" in plan.prompt
    assert "This is a fragment rather than a question." in plan.prompt
    assert "I feel strange today." in plan.prompt
    assert "cannot establish that removed or earlier content is currently stored" in (
        plan.prompt
    )
    properties = plan.output_schema["properties"]
    assert set(properties) == {"outcome_kind", "blocks"}
    block_properties = properties["blocks"]["items"]["properties"]
    assert set(block_properties) == {"role", "text", "source_aliases"}


def test_complete_corpus_over_one_shot_bound_fails_before_provider_use():
    oversized = tuple(
        FindAnswerEvidence(
            f"m{index}",
            "task",
            "memory",
            f"{index:08d}-memory",
            "x" * 100_000,
        )
        for index in range(1, 12)
    )

    with pytest.raises(OrdinaryQueryCorpusTooLarge, match="does not hide batching"):
        prepare_ordinary_query_answer("question", oversized)


def test_query_execution_sends_every_frozen_candidate_in_one_provider_call(
    isolated_store,
):
    store = MemoryStore()
    root = ops.init("task")
    ops.add(root, "Root fact")
    child = ops.init("task/child")
    ops.add(child, "Child fact one")
    ops.add(child, "Child fact two")
    for context in (root, child):
        store.save(context)
    store.set_current(root.name)
    access = resolve_context_access(
        store,
        root.name,
        current_name=root.name,
        required_permission="READ",
    )
    catalog = freeze_readable_context_catalog(store, access)
    stages: list[str] = []

    class InspectingProvider:
        def __init__(self):
            self.calls = 0

        def complete(self, prompt, *, operation, output_schema=None):
            self.calls += 1
            assert operation == "ordinary query"
            payload = json.loads(prompt.split("ORDINARY QUERY PAYLOAD:\n", 1)[1])
            corpus = payload["complete_frozen_corpus"]
            assert {item["content"] for item in corpus} == {
                "Root fact",
                "Child fact one",
                "Child fact two",
            }
            aliases = [item["alias"] for item in corpus]
            return json.dumps(
                {
                    "outcome_kind": "ANSWER",
                    "blocks": [
                        {
                            "role": "SUPPORTED_CLAIM",
                            "text": "All three frozen Memories were reviewed.",
                            "source_aliases": aliases,
                        }
                    ],
                }
            )

    provider = InspectingProvider()
    request = OrdinaryQueryRequest(
        "What is in the complete scope?",
        (root.name,),
        include_descendants=True,
        follow_embeds=False,
    )

    response = execute_ordinary_query(
        request,
        store=store,
        catalog=catalog,
        provider_factory=lambda: provider,
        observer=stages.append,
    )

    assert provider.calls == 1
    assert response.grounded is True
    assert response.reference_document is not None
    assert len(response.reference_document.references) == 3
    assert stages == [
        "INPUTS_FROZEN",
        "CONNECTING_PROVIDER",
        "ANSWERING",
    ]
