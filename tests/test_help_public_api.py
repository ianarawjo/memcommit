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

    assert len(result.operations) == 59
    assert result.operations[0].name == "add"
    assert result.operations[-1].name == "update"
    assert not root.exists()


def test_client_describes_one_json_safe_public_value(tmp_path):
    result = MemCommitClient(root=tmp_path / "missing-store").describe_operation(
        "help"
    )

    assert result.name == "help"
    assert result.execution == "DETERMINISTIC"
    assert result.effect == "Read-only"
    assert result.range is None


def test_client_reports_unknown_operation_through_public_error(tmp_path):
    client = MemCommitClient(root=tmp_path / "missing-store")

    with pytest.raises(HelpInputError, match="No public MemCommit operation"):
        client.describe_operation("not-an-operation")
