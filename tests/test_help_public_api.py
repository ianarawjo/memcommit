"""Public Python projection of the stable Help catalog."""

from __future__ import annotations

import pytest

from memcommit.adapters.python_api import HelpInputError, MemCommitClient


def test_client_lists_operations_without_store_or_provider_access(tmp_path):
    root = tmp_path / "missing-store"

    def provider():
        raise AssertionError("Help must not connect a provider")

    result = MemCommitClient(
        root=root,
        semantic_provider_factory=provider,
    ).list_operations()

    assert len(result.operations) == 66
    assert result.operations[0].name == "add"
    assert result.operations[-1].name == "update"
    assert not root.exists()


def test_client_describes_one_json_safe_public_value(tmp_path):
    result = MemCommitClient(root=tmp_path / "missing-store").describe_operation("help")

    assert result.name == "help"
    assert result.execution == "MIXED"
    assert result.effect == "Browses command guidance"
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


def test_client_projects_provider_as_partial(tmp_path):
    client = MemCommitClient(root=tmp_path / "missing-store")

    operation = client.describe_operation("provider")

    assert operation.maturity == "PARTIAL"


def test_client_projects_query_only_access_as_typed_detail(tmp_path):
    client = MemCommitClient(root=tmp_path / "missing-store")

    operation = client.describe_operation("query")
    detail = client.describe_operation_detail("query", "query-only-access")

    assert operation.details[0].discovery == "TOOL_SELECTION"
    assert operation.details[0].discovery_summary is not None
    assert detail.kind == "ACCESS_BOUNDARY"
    assert "QUERY without READ" in detail.body


def test_client_projects_update_meld_semantic_boundary_on_both_operations(tmp_path):
    client = MemCommitClient(root=tmp_path / "missing-store")

    for operation in ("update", "meld"):
        detail = client.describe_operation_detail(operation, "update-vs-meld")
        assert detail.kind == "SEMANTIC_BOUNDARY"
        assert detail.title == "UPDATE VS. MELD"
        assert "revision-oriented" in detail.body
        assert "merge-oriented" in detail.body


def test_client_projects_reviewed_operation_boundaries_as_typed_comparisons(
    tmp_path,
):
    client = MemCommitClient(root=tmp_path / "missing-store")

    distill = client.describe_operation_detail("distill", "distill-or-atomize")
    impact = client.describe_operation_detail("impact", "invocation")
    fit = client.describe_operation_detail("fit", "verdicts")
    conformance = client.describe_operation_detail(
        "check-conformance",
        "fit-or-conformance",
    )

    assert distill.discovery == "TOOL_SELECTION"
    assert [option.label for option in distill.options] == ["DISTILL", "ATOMIZE"]
    assert "--from or --to" in impact.options[1].guidance
    assert [option.label for option in fit.options] == ["YES", "MAY", "NO"]
    assert conformance.discovery_summary is not None
    assert "propositions can coexist" in conformance.discovery_summary


def test_client_projects_final_category_routes_as_typed_details(tmp_path):
    client = MemCommitClient(root=tmp_path / "missing-store")

    log = client.describe_operation_detail("log", "history-routes")
    profile = client.describe_operation_detail("profile", "management-actions")
    eval_scope = client.describe_operation_detail("eval", "evaluation-scope")

    assert [option.label for option in log.options] == [
        "CONTEXT CHECKPOINTS",
        "MEMORY LINEAGE",
        "SEMANTIC SEARCH",
        "PROFILE ATTEMPTS",
        "STUDY ACTIONS",
    ]
    assert [option.label for option in profile.options] == [
        "CREATE",
        "SELECT",
        "RENAME",
        "RENAME STUDY",
        "REMOVE",
        "REMOVE STUDY",
    ]
    assert eval_scope.discovery == "ON_DEMAND"
    assert eval_scope.title == "RESERVED SHELL"
    assert "no executable subcommands" in eval_scope.body
