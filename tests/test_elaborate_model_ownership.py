"""Physical ownership boundaries inside Elaborate generation."""

from __future__ import annotations

from pathlib import Path

from memcommit.application.operations.elaborate.case_validation import (
    _validate_elaborated_cases,
)
from memcommit.application.operations.elaborate.model import (
    ElaborateAnalysis,
    analyze_elaborate,
    validate_elaborate_provider_plan,
)
from memcommit.application.operations.elaborate.proposal_grounding_validation import (
    _decode_target_context_refs,
    _reject_target_restatements,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_elaborate_responsibilities_have_concept_owned_modules() -> None:
    assert ElaborateAnalysis.__module__.endswith(".elaborate.model")
    assert analyze_elaborate.__module__.endswith(".elaborate.generation")
    assert validate_elaborate_provider_plan.__module__.endswith(
        ".elaborate.provider_contract"
    )
    assert _decode_target_context_refs.__module__.endswith(
        ".elaborate.proposal_grounding_validation"
    )
    assert _reject_target_restatements.__module__.endswith(
        ".elaborate.proposal_grounding_validation"
    )
    assert _validate_elaborated_cases.__module__.endswith(
        ".elaborate.case_validation"
    )


def test_elaborate_application_imports_execution_from_its_owner() -> None:
    source = (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/elaborate/application.py"
    ).read_text(encoding="utf-8")

    assert "elaborate.generation import analyze_elaborate" in source
    assert "elaborate.provider_contract import (" in source


def test_grounding_validation_does_not_own_conformance_or_fit() -> None:
    source = (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/elaborate/"
        "proposal_grounding_validation.py"
    ).read_text(encoding="utf-8")

    assert "operations.conformance" not in source
    assert "operations.fit" not in source
