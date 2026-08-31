"""Ownership and compatibility paths for reviewed Meld execution."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODULE_PAIRS = (
    (
        "memcommit.meld_application",
        "memcommit.application.operations.semantic_updates.curate_integrate.meld.apply",
    ),
    (
        "memcommit.meld_runtime",
        "memcommit.application.operations.semantic_updates.curate_integrate.meld.runtime",
    ),
    (
        "memcommit.meld_application_flow",
        "memcommit.application.operations.semantic_updates.curate_integrate.meld.application",
    ),
    (
        "memcommit.meld_session_application",
        "memcommit.application.operations.semantic_updates.curate_integrate.meld.proposal_iteration",
    ),
    (
        "memcommit.meld_start_application",
        "memcommit.application.operations.semantic_updates.curate_integrate.meld.preparation",
    ),
    (
        "memcommit.meld_restart_application",
        "memcommit.application.operations.semantic_updates.curate_integrate.meld.preparation",
    ),
    (
        "memcommit.meld_assessment_application",
        "memcommit.application.operations.semantic_updates.curate_integrate.meld.planning",
    ),
    (
        "memcommit.meld_resolution_application",
        "memcommit.application.operations.semantic_updates.curate_integrate.meld.proposal_iteration",
    ),
)


def test_meld_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.semantic_updates.curate_integrate.meld

assert "memcommit.application.operations.semantic_updates.curate_integrate.meld.apply" not in sys.modules
assert "memcommit.application.operations.semantic_updates.curate_integrate.meld.runtime" not in sys.modules
assert "memcommit.application.operations.semantic_updates.curate_integrate.meld.application" not in sys.modules
assert "memcommit.application.operations.semantic_updates.curate_integrate.meld.proposal_iteration" not in sys.modules
assert "memcommit.application.operations.semantic_updates.curate_integrate.meld.preparation" not in sys.modules
assert "memcommit.application.operations.semantic_updates.curate_integrate.meld.planning" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_production_meld_consumers_use_the_operation_owner() -> None:
    paths = (
        tuple(
            REPOSITORY_ROOT / relative_path
            for relative_path in (
                "src/memcommit/adapters/python_api/_operations/meld.py",
                "src/memcommit/application/operations/semantic_updates/curate_integrate/meld/preparation.py",
                "src/memcommit/application/operations/semantic_updates/curate_integrate/meld/proposal_iteration.py",
            )
        )
        + tuple(
            sorted(
                (
                    REPOSITORY_ROOT
                    / "src/memcommit/adapters/console/commands/semantic_updates/curate_integrate/meld/command"
                ).glob("*.py")
            )
        )
        + tuple(
            sorted(
                (
                    REPOSITORY_ROOT
                    / "src/memcommit/application/operations/semantic_updates/curate_integrate/meld/runtime"
                ).glob("*.py")
            )
        )
    )

    legacy_modules = tuple(legacy_name for legacy_name, _canonical_name in MODULE_PAIRS)

    for path in paths:
        source = path.read_text(encoding="utf-8")
        assert not [name for name in legacy_modules if name in source]


def test_meld_model_facade_preserves_api_with_concept_owned_modules() -> None:
    from memcommit.application.operations.semantic_updates.curate_integrate.meld.model import (
        MeldAssessment,
        MeldChangeSet,
        MeldFrame,
        MeldSession,
        MeldTurn,
    )

    assert MeldFrame.__module__.endswith(".model.source_snapshot")
    assert MeldAssessment.__module__.endswith(".model.integration_proposal")
    assert MeldChangeSet.__module__.endswith(".model.apply_effects")
    assert MeldSession.__module__.endswith(".model.proposal_session")
    assert MeldTurn.__module__.endswith(".model.integration_proposal")


def test_meld_compare_era_model_names_are_thin_compatibility_aliases() -> None:
    from memcommit.application.operations.semantic_updates.curate_integrate.meld.model import (
        MELD_COMPARISON_SCHEMA_VERSION,
        MELD_DIRECTIONAL_COMPARISON_SCHEMA_VERSION,
        MELD_DIRECTIONAL_RELATION_SCHEMA_VERSION,
        MELD_RELATION_ANALYSIS_SCHEMA_VERSION,
        MeldComparisonSeed,
        MeldRelationAnalysisSeed,
    )

    assert MeldComparisonSeed is MeldRelationAnalysisSeed
    assert MELD_COMPARISON_SCHEMA_VERSION == MELD_RELATION_ANALYSIS_SCHEMA_VERSION
    assert (
        MELD_DIRECTIONAL_COMPARISON_SCHEMA_VERSION
        == MELD_DIRECTIONAL_RELATION_SCHEMA_VERSION
    )


def test_meld_provider_package_is_lazy_and_has_no_compatibility_facade() -> None:
    program = """
import sys
import memcommit.application.operations.semantic_updates.curate_integrate.meld.provider as provider

assert not hasattr(provider, "MeldProviderError")
assert not hasattr(provider, "assess_meld_turn")
assert not hasattr(provider, "meld_turn_request_digest")
assert "memcommit.application.operations.semantic_updates.curate_integrate.meld.provider.contract" not in sys.modules
assert "memcommit.application.operations.semantic_updates.curate_integrate.meld.provider.projection" not in sys.modules
assert "memcommit.application.operations.semantic_updates.curate_integrate.meld.provider.request" not in sys.modules
assert "memcommit.application.operations.semantic_updates.curate_integrate.meld.provider.decoder" not in sys.modules
assert "memcommit.application.operations.semantic_updates.curate_integrate.meld.provider.execution" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_meld_provider_symbols_are_owned_by_narrow_pipeline_modules() -> None:
    from memcommit.application.operations.semantic_updates.curate_integrate.meld.provider.contract import (
        MeldProviderError,
        meld_output_schema,
    )
    from memcommit.application.operations.semantic_updates.curate_integrate.meld.provider.decoder import (
        _parse_assessment,
    )
    from memcommit.application.operations.semantic_updates.curate_integrate.meld.provider.execution import (
        assess_meld_turn,
    )
    from memcommit.application.operations.semantic_updates.curate_integrate.meld.provider.projection import (
        _provider_view,
    )
    from memcommit.application.operations.semantic_updates.curate_integrate.meld.provider.request import (
        meld_turn_request_digest,
    )

    assert MeldProviderError.__module__.endswith(".provider.contract")
    assert meld_output_schema.__module__.endswith(".provider.contract")
    assert _provider_view.__module__.endswith(".provider.projection")
    assert meld_turn_request_digest.__module__.endswith(".provider.request")
    assert _parse_assessment.__module__.endswith(".provider.decoder")
    assert assess_meld_turn.__module__.endswith(".provider.execution")


def test_production_code_does_not_import_the_meld_provider_package_root() -> None:
    package_name = "memcommit.application.operations.semantic_updates.curate_integrate.meld.provider"
    offenders: list[str] = []
    for path in (REPOSITORY_ROOT / "src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(
            isinstance(node, ast.ImportFrom) and node.module == package_name
            for node in ast.walk(tree)
        ):
            offenders.append(path.relative_to(REPOSITORY_ROOT).as_posix())

    assert offenders == []
