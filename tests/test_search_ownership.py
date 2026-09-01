"""Ownership and compatibility paths for semantic Search."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_search_operation_package_import_is_lazy_and_separate_from_find() -> None:
    program = """
import sys
import memcommit.application.operations.search

blocked = (
    "memcommit.application.operations.search.application",
    "memcommit.application.operations.search.runtime",
    "memcommit.application.operations.search.save_context",
    "memcommit.application.capabilities.save_context_from_selection.application",
    "memcommit.application.capabilities.save_context_from_selection.runtime",
    "memcommit.application.operations.find.application",
    "memcommit.application.operations.find.runtime",
)
assert not [name for name in blocked if name in sys.modules]
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_search_runtime_import_does_not_assemble_console_adapters() -> None:
    program = """
import sys
import memcommit.application.operations.search.runtime

loaded = sorted(
    name for name in sys.modules if name.startswith("memcommit.adapters.console")
)
assert loaded == [], loaded
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_search_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/_operations/search.py",
        "src/memcommit/adapters/console/commands/search/command.py",
        "src/memcommit/adapters/console/commands/search/search_workbench.py",
        "src/memcommit/application/operations/search/runtime.py",
        "src/memcommit/application/operations/search/save_context.py",
        "src/memcommit/application/capabilities/save_context_from_selection/application.py",
        "src/memcommit/application/capabilities/save_context_from_selection/runtime.py",
    )
    legacy_imports = (
        "from memcommit.find_application import",
        "from memcommit.find_runtime import",
        "from memcommit.search_materialization_application import",
        "from memcommit.search_materialization_runtime import",
    )

    for relative_path in relative_paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert not [legacy for legacy in legacy_imports if legacy in source]


def test_production_code_uses_split_search_owners_not_model_facade() -> None:
    legacy_import = (
        "memcommit.application.operations."
        "search.model import"
    )
    offenders = []
    for path in (REPOSITORY_ROOT / "src" / "memcommit").rglob("*.py"):
        if path.name == "model.py" and path.parent.name == "search":
            continue
        if legacy_import in path.read_text(encoding="utf-8"):
            offenders.append(path.relative_to(REPOSITORY_ROOT).as_posix())

    assert offenders == []


def test_search_model_facade_reexports_the_split_owner_objects() -> None:
    from memcommit.application.capabilities.retrieval_corpus import candidates as corpus_candidates
    from memcommit.application.operations.search import (
        candidates,
        errors,
        model,
        ranking,
    )

    assert model.SearchArtifact is candidates.SearchArtifact
    assert model.SearchCandidate is candidates.SearchCandidate
    assert model.SearchError is errors.SearchError
    assert model.SearchMatch is ranking.SearchMatch
    assert model.rank_candidates is ranking.rank_candidates
    assert candidates.SearchArtifact is corpus_candidates.RetrievalArtifact
    assert candidates.SearchCandidate is corpus_candidates.RetrievalCandidate


def test_production_retrieval_consumers_use_the_shared_corpus_owner() -> None:
    legacy_imports = (
        "memcommit.application.operations.search.candidates import",
        "memcommit.application.operations.search.corpus import",
        "memcommit.application.operations.search.artifacts import",
    )
    offenders = []
    for path in (REPOSITORY_ROOT / "src" / "memcommit").rglob("*.py"):
        if path.parent.name == "search" and path.name in {
            "artifacts.py",
            "candidates.py",
            "corpus.py",
            "model.py",
        }:
            continue
        source = path.read_text(encoding="utf-8")
        if any(legacy in source for legacy in legacy_imports):
            offenders.append(path.relative_to(REPOSITORY_ROOT).as_posix())

    assert offenders == []


def test_legacy_three_sentence_search_answer_api_is_removed() -> None:
    search_package = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/search"
    )
    assert not (search_package / "answer_references.py").exists()
    production = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (REPOSITORY_ROOT / "src" / "memcommit").rglob("*.py")
    )
    assert "SearchAnswerSentence" not in production
    assert "build_search_answer_reference_document" not in production


def test_query_reference_and_corpus_paths_do_not_depend_on_search() -> None:
    paths = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/query",
        REPOSITORY_ROOT / "src/memcommit/adapters/console/commands/query",
    )
    offenders = []
    for root in paths:
        for path in root.rglob("*.py"):
            if "memcommit.application.operations.search." in path.read_text(
                encoding="utf-8"
            ):
                offenders.append(path.relative_to(REPOSITORY_ROOT).as_posix())

    assert offenders == []


def test_complete_search_application_package_has_no_console_imports() -> None:
    search_package = (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/search"
    )
    offenders = [
        path.name
        for path in search_package.glob("*.py")
        if "memcommit.adapters.console" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_search_analysis_and_selection_save_remain_separate_use_cases() -> None:
    application_source = (
        REPOSITORY_ROOT / "src/memcommit/application/operations/search/application.py"
    ).read_text(encoding="utf-8")
    search_save_source = (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/search/save_context.py"
    ).read_text(encoding="utf-8")
    shared_save_source = (
        REPOSITORY_ROOT
        / "src/memcommit/application/capabilities/save_context_from_selection/application.py"
    ).read_text(encoding="utf-8")
    package_source = "\n".join(
        (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        for relative_path in (
            "src/memcommit/application/operations/search/application.py",
            "src/memcommit/application/operations/search/runtime.py",
            "src/memcommit/application/operations/search/save_context.py",
            "src/memcommit/application/capabilities/save_context_from_selection/application.py",
            "src/memcommit/application/capabilities/save_context_from_selection/runtime.py",
        )
    )

    assert "save_context_from_selection" not in application_source
    assert (
        "memcommit.application.operations.search.application" in search_save_source
    )
    assert "memcommit.application.operations.search" not in shared_save_source
    assert "memcommit.adapters.console.commands" not in package_source
    assert "memcommit.adapters.interfaces" not in package_source


def test_selected_public_search_loads_analysis_without_selection_save(
    tmp_path: Path,
) -> None:
    program = f"""
import sys
from pathlib import Path
from memcommit.adapters.python_api import MemCommitClient, SemanticContextError

client = MemCommitClient(root=Path({str(tmp_path / "store")!r}), create=True)
try:
    client.search('needle')
except SemanticContextError:
    pass
else:
    raise AssertionError('Search without a current Context unexpectedly succeeded')

assert 'memcommit.adapters.python_api._operations.search' in sys.modules
assert 'memcommit.application.operations.search.application' in sys.modules
assert 'memcommit.application.operations.search.runtime' in sys.modules
assert 'memcommit.application.operations.search.save_context' not in sys.modules
assert 'memcommit.application.capabilities.save_context_from_selection.application' not in sys.modules
assert 'memcommit.application.capabilities.save_context_from_selection.runtime' not in sys.modules
assert 'memcommit.find_application' not in sys.modules
assert 'memcommit.find_runtime' not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
