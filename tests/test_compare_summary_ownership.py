"""Ownership and compatibility paths for lightweight Compare Summary."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_compare_operation_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.compare

assert not [
    name
    for name in sys.modules
    if name.startswith("memcommit.application.operations.compare.")
]
assert "memcommit.comparison" not in sys.modules
assert "memcommit.comparison_store" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_summary_consumers_use_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/console/commands/compare/command.py",
        "src/memcommit/application/operations/compare/compare_summary.py",
        "src/memcommit/application/operations/compare/provider_contract.py",
        "src/memcommit/application/operations/compare/application.py",
    )
    legacy_imports = (
        "from memcommit.comparison_summary import",
        "from memcommit.comparison_summary_rules import",
        "from memcommit.comparison_summary_provider import",
        "from memcommit.comparison_summary_application import",
        "import memcommit.comparison_summary",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert not [legacy for legacy in legacy_imports if legacy in source]


def test_compare_summary_owner_does_not_absorb_deep_compare_or_presentation() -> None:
    summary_modules = (
        "application.py",
        "compare_rules.py",
        "compare_summary.py",
        "provider_contract.py",
    )
    package_source = "\n".join(
        (
            REPOSITORY_ROOT
            / "src/memcommit/application/operations/compare"
            / module
        ).read_text(encoding="utf-8")
        for module in summary_modules
    )

    assert "memcommit.adapters.console.commands" not in package_source
    assert "memcommit.adapters.interfaces" not in package_source
    assert "render_comparison" not in package_source
    assert "from memcommit.comparison import ComparisonAnalysis" not in package_source
    assert "ensure_comparison_analysis" not in package_source
    assert "save_comparison_analysis" not in package_source
    assert "open_comparison_session" not in package_source


def test_deep_relation_judgment_is_not_owned_by_compare_operation() -> None:
    compare_root = REPOSITORY_ROOT / "src/memcommit/application/operations/compare"

    # An ignored ``__pycache__`` directory may survive a source relocation in
    # an already-used checkout; physical ownership is defined by Python source.
    assert not tuple((compare_root / "ledger").glob("*.py"))
    capability_root = (
        REPOSITORY_ROOT
        / "src/memcommit/application/capabilities/memory_issue_analysis/peer_relations"
    )
    assert {path.name for path in capability_root.glob("*.py")} >= {
        "evidence.py",
        "execution.py",
        "model.py",
        "provider_contract.py",
        "repository.py",
    }


def test_compare_vocabulary_is_an_identity_preserving_capability_alias() -> None:
    from memcommit.application.capabilities.memory_issue_analysis.peer_relations.execution import (
        ComparisonExecutionResult,
        MemoryRelationExecutionResult,
        ensure_comparison_analysis,
        ensure_memory_relation_analysis,
    )
    from memcommit.application.capabilities.memory_issue_analysis.peer_relations.model import (
        ComparisonAnalysis,
        ComparisonInput,
        MemoryRelationAnalysis,
        MemoryRelationInput,
    )
    from memcommit.application.capabilities.memory_issue_analysis.peer_relations.provider_contract import (
        analyze_comparison,
        analyze_memory_relations,
    )

    assert ComparisonAnalysis is MemoryRelationAnalysis
    assert ComparisonInput is MemoryRelationInput
    assert ComparisonExecutionResult is MemoryRelationExecutionResult
    assert ensure_comparison_analysis is ensure_memory_relation_analysis
    assert analyze_comparison is analyze_memory_relations
    assert MemoryRelationAnalysis.__name__ == "MemoryRelationAnalysis"


def test_meld_and_update_do_not_depend_on_compare_operation() -> None:
    operations_root = REPOSITORY_ROOT / "src/memcommit/application/operations"
    source_by_operation = {
        operation: "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((operations_root / operation).rglob("*.py"))
        )
        for operation in ("meld", "update")
    }

    assert all(
        "memcommit.application.operations.compare" not in source
        for source in source_by_operation.values()
    )
    assert (
        "memcommit.application.capabilities.memory_issue_analysis.peer_relations"
        in source_by_operation["meld"]
    )


def test_meld_has_no_compare_operation_presentation_or_prewarm_dependency() -> None:
    meld_roots = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/meld",
        REPOSITORY_ROOT / "src/memcommit/adapters/console/commands/meld",
    )
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for root in meld_roots
        for path in sorted(root.rglob("*.py"))
    )

    assert "memcommit.application.operations.compare" not in source
    assert "memcommit.adapters.console.commands.compare" not in source
    assert "study_scenarios.legacy.prewarm.compare" not in source
    assert "study_scenarios.legacy.prewarm.peer_relations" in source
