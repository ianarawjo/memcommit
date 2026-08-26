"""Canonical operation evidence and generated-ledger regressions."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.verify_operation_evidence import (
    EvidenceError,
    GENERATED_INDEX,
    REPOSITORY,
    combine_records,
    load_evidence_records,
    load_registry,
    operation_records,
    validate_boundary_matrix_registration,
    validate_markdown_links,
    verify,
)


def test_checked_in_operation_evidence_index_is_current() -> None:
    assert GENERATED_INDEX.read_text(encoding="utf-8") == verify(REPOSITORY)


def test_evidence_and_classification_cover_the_same_help_operations() -> None:
    classifications = operation_records(load_registry(REPOSITORY), REPOSITORY)
    evidence = load_evidence_records(REPOSITORY)

    assert set(classifications) == set(evidence)
    assert set(combine_records(classifications, evidence)) == set(classifications)


def test_reviewed_compatibility_evidence_cannot_drift() -> None:
    classifications = {
        "show": ("CLOSED", ("agent-records/docs/show-application-boundary-matrix.md",), "done")
    }

    with pytest.raises(EvidenceError, match="evidence differs"):
        combine_records(
            classifications,
            {"show": ("agent-records/docs/show-application-design-rationale.md",)},
        )


def test_governed_markdown_rejects_a_missing_local_link(tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text("[missing](does-not-exist.md)\n", encoding="utf-8")

    with pytest.raises(EvidenceError, match="missing link target"):
        validate_markdown_links({note}, tmp_path)


def test_unregistered_final_boundary_matrix_is_rejected(tmp_path: Path) -> None:
    agent_records = tmp_path / "agent-records" / "docs"
    agent_records.mkdir(parents=True)
    (agent_records / "status-application-boundary-matrix.md").write_text(
        "# Status boundary\n",
        encoding="utf-8",
    )

    with pytest.raises(EvidenceError, match="unregistered operation boundary"):
        validate_boundary_matrix_registration({}, tmp_path)
