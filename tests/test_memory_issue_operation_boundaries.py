"""Ownership checks for the four Memory Issue finding operations."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

from memcommit.application.capabilities.memory_issue_analysis.model import (
    AmbiguityReport,
    ConflictReport,
)
from memcommit.application.capabilities.memory_issue_analysis.source import (
    QualityFindSourceFrame,
)
from memcommit.application.operations.quality_resolution.diagnose.find_ambiguities.application import (
    analyze_find_ambiguities,
)
from memcommit.application.operations.quality_resolution.diagnose.find_conflicts.application import (
    analyze_find_conflicts,
)
from memcommit.application.operations.quality_resolution.diagnose.find_duplicates.application import (
    ExactDuplicateReport,
    FindDuplicatesRequest,
    find_duplicates,
)
from memcommit.core.context import Context, Memory
from memcommit.persistence.store import MemoryStore


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class _ForbiddenProvider:
    def __call__(self):
        raise AssertionError("an empty detection frame must not connect a provider")


def test_old_reviewing_memory_issue_package_is_unavailable() -> None:
    assert (
        importlib.util.find_spec(
            "memcommit.application.capabilities.reviewing.memory_issue"
        )
        is None
    )


def test_frozen_source_is_owned_by_memory_issue_analysis() -> None:
    assert QualityFindSourceFrame.__module__.endswith("memory_issue_analysis.source")


def test_empty_issue_operations_return_typed_reports_without_provider() -> None:
    source = QualityFindSourceFrame.create((Context(uid="context-1", name="empty"),))

    ambiguity = analyze_find_ambiguities(source, _ForbiddenProvider())
    conflict = analyze_find_conflicts(source, _ForbiddenProvider())

    assert ambiguity.report == AmbiguityReport(memory_count=0, findings=())
    assert conflict.report == ConflictReport(
        memory_count=0,
        pair_count=0,
        findings=(),
    )
    assert ambiguity.session.source is source
    assert conflict.session.source is source


def test_find_duplicates_application_owns_readable_scope_resolution(tmp_path) -> None:
    store = MemoryStore(root=tmp_path / ".mem")
    context = Context(uid="context-1", name="quality/source")
    context.add(Memory(uid="memory-1", content="same"))
    context.add(Memory(uid="memory-2", content="same"))
    store.create_context(context)
    store.set_current(context.name)

    report = find_duplicates(
        store,
        FindDuplicatesRequest(),
        current_name=context.name,
    )

    assert report.root_name == context.name
    assert report.group_count == 1
    assert store.current_context_name() == context.name
    assert ExactDuplicateReport.__module__.endswith("find_duplicates.application")


def test_dedup_consumes_find_duplicates_analysis_without_rediscovery() -> None:
    find_source = (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/quality_resolution/diagnose/find_duplicates/application.py"
    ).read_text(encoding="utf-8")
    dedup_source = (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/quality_resolution/repair/dedup/application.py"
    ).read_text(encoding="utf-8")

    assert "memcommit.application.operations.quality_resolution.repair.dedup" not in find_source
    assert "memcommit.application.operations.quality_resolution.diagnose.find_duplicates" in dedup_source
    assert "find_exact_duplicate_groups" not in dedup_source


def test_console_find_routes_import_named_application_boundaries() -> None:
    for operation in (
        "find_ambiguities",
        "find_conflicts",
        "find_duplicates",
        "find_redundancies",
    ):
        path = (
            REPOSITORY_ROOT
            / "src/memcommit/adapters/console/commands"
            / "quality_resolution"
            / "diagnose"
            / operation
            / "command.py"
        )
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        assert (
            f"memcommit.application.operations.quality_resolution.diagnose.{operation}.application"
            in imports
        )
        assert "memcommit.application.capabilities.ops" not in imports


def test_find_application_modules_have_no_terminal_dependency() -> None:
    for operation in (
        "find_ambiguities",
        "find_conflicts",
        "find_duplicates",
        "find_redundancies",
    ):
        path = (
            REPOSITORY_ROOT
            / "src/memcommit/application/operations"
            / "quality_resolution"
            / "diagnose"
            / operation
            / "application.py"
        )
        source = path.read_text(encoding="utf-8")
        assert "memcommit.adapters.console" not in source
        assert "import typer" not in source
