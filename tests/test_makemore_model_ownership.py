"""Physical ownership boundaries inside Makemore generation."""

from __future__ import annotations

from pathlib import Path

from memcommit.application.operations.semantic_updates.derive.makemore.case_validation import (
    _validate_makemore_cases,
)
from memcommit.application.operations.semantic_updates.derive.makemore.model import (
    MakemoreAnalysis,
    analyze_makemore,
    validate_makemore_provider_plan,
)
from memcommit.application.operations.semantic_updates.derive.makemore.proposal_grounding_validation import (
    _decode_target_context_refs,
    _reject_target_restatements,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_makemore_responsibilities_have_concept_owned_modules() -> None:
    assert MakemoreAnalysis.__module__.endswith(".makemore.model")
    assert analyze_makemore.__module__.endswith(".makemore.generation")
    assert validate_makemore_provider_plan.__module__.endswith(
        ".makemore.provider_contract"
    )
    assert _decode_target_context_refs.__module__.endswith(
        ".makemore.proposal_grounding_validation"
    )
    assert _reject_target_restatements.__module__.endswith(
        ".makemore.proposal_grounding_validation"
    )
    assert _validate_makemore_cases.__module__.endswith(
        ".makemore.case_validation"
    )


def test_makemore_application_imports_execution_from_its_owner() -> None:
    source = (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/semantic_updates/derive/makemore/application.py"
    ).read_text(encoding="utf-8")

    assert "makemore.generation import analyze_makemore" in source
    assert "makemore.provider_contract import (" in source


def test_grounding_validation_does_not_own_conformance_or_fit() -> None:
    source = (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/semantic_updates/derive/makemore/"
        "proposal_grounding_validation.py"
    ).read_text(encoding="utf-8")

    assert "operations.conformance" not in source
    assert "operations.fit" not in source
