"""Strict Conformance and Fit validation for generated Makemore Cases."""

from __future__ import annotations

import uuid

from memcommit.application.operations.conformance.model import (
    ConformanceError,
    ConformanceRule,
    ConformanceSubject,
    check_context_conformance,
)
from memcommit.application.operations.makemore.model import (
    MakemoreError,
    MakemoreProvider,
    MakemoreCase,
    MakemoreCaseValidation,
    MakemoreTargetContext,
)
from memcommit.application.operations.makemore.proposal_grounding_validation import (
    _referenced_target_memories,
)
from memcommit.application.operations.fit.judgment import (
    FitJudgmentError,
    FitProposition,
    FitQuestion,
    execute_fit_judgments,
    prepare_fit_judgments,
)


def _validate_makemore_cases(
    *,
    analysis_uid: str,
    inputs: tuple[str, ...],
    cases: tuple[MakemoreCase, ...],
    provider: MakemoreProvider,
    target_context: MakemoreTargetContext | None,
) -> tuple[MakemoreCaseValidation, ...]:
    """Fail closed unless the generated collection conforms and Fits its Source."""

    namespace = uuid.UUID(analysis_uid)
    rules = tuple(
        ConformanceRule(
            uid=str(uuid.uuid5(namespace, f"source-rule:{index}:{content}")),
            alias=f"r{index}",
            content=content,
        )
        for index, content in enumerate(inputs, 1)
    )
    rule_uids = tuple(rule.uid for rule in rules)
    rule_index_by_uid = {
        rule.uid: index for index, rule in enumerate(rules, 1)
    }
    target_memories = _referenced_target_memories(target_context, cases)
    target_subjects = tuple(
        ConformanceSubject(
            # Target adapters may retain a stable non-UUID provider identity.
            # Conformance owns UUID subjects, so bind that identity and exact
            # content into this analysis namespace instead of weakening either
            # public contract.
            uid=str(
                uuid.uuid5(
                    namespace,
                    f"target-memory:{item.alias}:{item.memory_uid}:{item.content}",
                )
            ),
            alias=item.alias,
            content=item.content,
            role="TARGET_CONTEXT",
            linked_rule_uids=rule_uids,
        )
        for item in target_memories
        if item.memory_uid is not None and item.content is not None
    )
    case_subjects = tuple(
        ConformanceSubject(
            uid=case.uid,
            alias=f"c{index}",
            content=case.proposition,
            role=case.case_role,
            linked_rule_uids=rule_uids,
        )
        for index, case in enumerate(cases, 1)
    )
    subjects = (*target_subjects, *case_subjects)
    try:
        conformance = check_context_conformance(
            source_label="MAKEMORE TARGET PREFIX AND GENERATED CASES",
            rules_label="MAKEMORE SOURCE RULES",
            rules=rules,
            subjects=subjects,
            provider=provider,  # type: ignore[arg-type]
        )
    except ConformanceError as error:
        raise MakemoreError(
            "Makemore could not validate Case conformance against the complete "
            "Source Rule frame."
        ) from error

    rule_judgment_by_uid = {
        judgment.rule_uid: judgment
        for judgment in conformance.context_judgments
    }
    rule_failures = tuple(
        f"Rule {index}: "
        + (
            "MISSING"
            if rule_judgment_by_uid.get(rule.uid) is None
            else rule_judgment_by_uid[rule.uid].status
        )
        for index, rule in enumerate(rules, 1)
        if rule_judgment_by_uid.get(rule.uid) is None
        or rule_judgment_by_uid[rule.uid].status != "CONFORMS"
    )
    if rule_failures:
        raise MakemoreError(
            "Makemore rejected a generated Case collection that did not conform "
            "to every Source Rule (" + "; ".join(rule_failures) + ")."
        )

    conformance_by_uid = {
        judgment.subject_uid: judgment
        for judgment in conformance.context_example_judgments
    }
    conformance_failures: list[str] = []
    for index, case in enumerate(cases, 1):
        judgment = conformance_by_uid.get(case.uid)
        if judgment is None or judgment.status != "CONFORMS":
            status = "MISSING" if judgment is None else judgment.status
            conformance_failures.append(f"Case {index}: {status}")
    if conformance_failures:
        raise MakemoreError(
            "Makemore rejected generated Cases that did not conform within the "
            "complete Source Rule collection ("
            + "; ".join(conformance_failures)
            + ")."
        )

    questions = (
        FitQuestion(
            question_id="case-set",
            background=tuple(
                FitProposition(
                    alias=item.alias,
                    content=item.content,
                    role="MEMORY",
                )
                for item in target_memories
                if item.content is not None
            ),
            propositions=(
                *(
                    FitProposition(
                        alias=f"r{rule_index}",
                        content=content,
                        role="RULE",
                    )
                    for rule_index, content in enumerate(inputs, 1)
                ),
                *(
                    FitProposition(
                        alias=f"c{case_index}",
                        content=case.proposition,
                        role="EXAMPLE",
                    )
                    for case_index, case in enumerate(cases, 1)
                ),
            ),
        ),
    )
    try:
        prepared_fit = prepare_fit_judgments(questions)
        fit = execute_fit_judgments(
            prepared_fit,
            provider=provider,  # type: ignore[arg-type]
        )
    except FitJudgmentError as error:
        raise MakemoreError(
            "Makemore could not validate generated Cases against the complete "
            "Source frame."
        ) from error

    fit_assessment = fit.assessments[0]
    if fit_assessment.verdict != "YES":
        raise MakemoreError(
            "Makemore rejected the generated Case collection because it did not "
            f"Fit the complete Source frame ({fit_assessment.verdict})."
        )

    conforming_indexes = tuple(
        rule_index_by_uid[rule_uid] for rule_uid in rule_uids
    )
    return tuple(
        MakemoreCaseValidation(
            source_fit="YES",
            source_fit_reason=fit_assessment.reason,
            rule_conformance="CONFORMS",
            conforming_source_rule_indexes=conforming_indexes,
        )
        for index in range(1, len(cases) + 1)
    )
