"""Public Python projection of the stable Help catalog."""

from __future__ import annotations

import pytest

from memcommit.api import HelpInputError, MemCommitClient


def test_client_lists_operations_without_store_or_provider_access(tmp_path):
    root = tmp_path / "missing-store"

    def provider():
        raise AssertionError("Help must not connect a provider")

    result = MemCommitClient(
        root=root,
        semantic_provider_factory=provider,
    ).list_operations()

    assert len(result.operations) == 62
    assert result.operations[0].name == "add"
    assert result.operations[-1].name == "update"
    assert not root.exists()


def test_client_describes_one_json_safe_public_value(tmp_path):
    result = MemCommitClient(root=tmp_path / "missing-store").describe_operation("help")

    assert result.name == "help"
    assert result.execution == "DETERMINISTIC"
    assert result.effect == "Read-only"
    assert result.range is None


def test_client_exposes_use_when_and_structured_detail_reference(tmp_path):
    client = MemCommitClient(root=tmp_path / "missing-store")

    result = client.describe_operation("add")
    [reference] = result.details
    comparison = client.describe_operation_detail("add", "copy-or-link")

    assert result.use_when == result.best_for
    assert reference.id == "copy-or-link"
    assert reference.kind == "COMPARISON"
    assert comparison.title == "COPY OR LINK"
    assert comparison.options[0].label == "INDEPENDENT WORK"
    assert "Branch the containing Context" in comparison.options[0].guidance


def test_client_reports_unknown_operation_through_public_error(tmp_path):
    client = MemCommitClient(root=tmp_path / "missing-store")

    with pytest.raises(HelpInputError, match="No public MemCommit operation"):
        client.describe_operation("not-an-operation")


def test_client_projects_import_maturity_and_exact_limitation_detail(tmp_path):
    client = MemCommitClient(root=tmp_path / "missing-store")

    operation = client.describe_operation("import")
    detail_index = client.list_operation_details("import")
    detail = client.describe_operation_detail("import", "current-limitation")

    assert operation.maturity == "PARTIAL"
    assert [item.id for item in operation.details] == ["current-limitation"]
    assert [item.id for item in detail_index.details] == ["current-limitation"]
    assert detail.kind == "LIMITATION"
    assert detail.title == "CURRENT LIMITATION"
    assert "arbitrary documents or Skills" in detail.body


def test_client_projects_query_only_access_as_typed_detail(tmp_path):
    client = MemCommitClient(root=tmp_path / "missing-store")

    operation = client.describe_operation("query")
    detail = client.describe_operation_detail("query", "query-only-access")

    assert operation.details[0].discovery == "TOOL_SELECTION"
    assert operation.details[0].discovery_summary is not None
    assert detail.kind == "ACCESS_BOUNDARY"
    assert "QUERY without READ" in detail.body
