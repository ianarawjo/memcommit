"""Infrastructure-boundary checks for production Meld execution."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import memcommit.application.operations.meld.coverage as meld_coverage
import memcommit.application.operations.meld.model.candidate as meld_candidate
import memcommit.application.operations.meld.preparation as meld_preparation
import memcommit.application.operations.meld.resolution as meld_resolution
import memcommit.application.operations.meld.runtime as meld_runtime
import memcommit.application.operations.meld.runtime.candidate_resolution as meld_apply
import memcommit.application.operations.meld.runtime.preparation as meld_session_launch
import memcommit.application.operations.meld.runtime.source_access as meld_source_bindings


PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "src" / "memcommit"
MELD_COMMAND_ROOT = (
    PACKAGE_ROOT
    / "adapters"
    / "console"
    / "commands"
    / "meld"
)


def _meld_command_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(MELD_COMMAND_ROOT.rglob("*.py"))
    )


@pytest.mark.parametrize(
    "module",
    (
        meld_candidate,
        meld_coverage,
        meld_preparation,
        meld_resolution,
        meld_runtime,
        meld_apply,
        meld_session_launch,
        meld_source_bindings,
    ),
)
def test_meld_execution_modules_have_no_terminal_or_command_dependencies(module):
    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)

    assert (
        tuple(
            name
            for name in imported
            if name == "typer"
            or name.startswith("prompt_toolkit")
            or name.startswith("memcommit.adapters.console.commands")
        )
        == ()
    )


def test_meld_runtime_facade_preserves_concept_owned_execution_api():
    assert meld_runtime.load_meld_source.__module__.endswith(".runtime.source_access")
    assert meld_runtime.PreparedMeldExecution.__module__.endswith(
        ".runtime.preparation"
    )
    assert meld_runtime.execute_meld_candidate_proposal.__module__.endswith(
        ".runtime.candidate_resolution"
    )


def test_meld_command_contains_no_target_or_session_publication_primitive():
    source = _meld_command_source()

    assert all(
        primitive not in source
        for primitive in (
            "save_meld_session(",
            "save_meld_target(",
            "create_meld_target_with_session(",
            "_save_locked(",
            "_write_json_atomic(",
        )
    )


def test_meld_command_contains_no_initial_cache_or_provisional_session_logic():
    source = _meld_command_source()

    assert all(
        primitive not in source
        for primitive in (
            "find_installed_directional_meld_prewarm",
            "find_installed_equivalent_directional_relation_analysis",
            "ensure_memory_relation_analysis",
            "install_prepared_memory_relation_analysis",
            "MeldSession.create_directional",
            "prepare_meld_assessment",
            "execute_meld_assessment",
        )
    )


def test_meld_command_calls_the_candidate_resolution_boundary_directly():
    source = _meld_command_source()

    assert "execute_meld_candidate_proposal(" in source
    assert "run_resolve_tui(" in source
    assert "execute_meld_apply(" not in source
    assert "run_application_flow" not in source
    assert "MeldApplicationFlowPort" not in source


def test_python_client_uses_the_operation_owned_meld_resolution_boundary():
    client_path = PACKAGE_ROOT / "adapters" / "python_api" / "client.py"
    operation_path = client_path.with_name("_operations") / "meld.py"
    source = client_path.read_text(encoding="utf-8")
    if operation_path.exists():
        source += operation_path.read_text(encoding="utf-8")

    assert "plan_meld_candidate_update(" in source
    assert "execute_meld_candidate_proposal(" in source
    assert "prepare_meld_resolution_turn(" not in source
    assert "execute_prepared_meld_turn(" not in source
    assert "execute_meld_turn(" not in source
    assert "prepare_meld_assessment" not in source


def test_candidate_preparation_has_no_compare_or_prewarm_dependency():
    source = Path(meld_session_launch.__file__).read_text(encoding="utf-8")

    assert all(
        token not in source
        for token in (
            "peer_relations",
            "comparison_seed",
            "relation_analysis",
            "prewarm",
        )
    )


def test_candidate_resolution_owns_target_and_session_publication():
    command_source = _meld_command_source()
    runtime_source = Path(meld_apply.__file__).read_text(encoding="utf-8")
    persistence_source = (
        PACKAGE_ROOT.parent
        / "memcommit"
        / "persistence"
        / "operations"
        / "meld"
        / "state_repository.py"
    ).read_text(encoding="utf-8")

    assert "save_meld_target(" not in command_source
    assert "save_meld_session(" not in command_source
    assert "save_meld_candidate_target_with_session(" in runtime_source
    assert "def save_meld_candidate_target_with_session(" in persistence_source
    assert "_save_locked(" in persistence_source
    assert "_write_json_atomic(path, data)" in persistence_source


def test_current_external_meld_surface_omits_legacy_turn_actions():
    client_path = PACKAGE_ROOT / "adapters" / "python_api" / "client.py"
    source = client_path.read_text(encoding="utf-8")

    assert "def resolve_meld(" in source
    assert all(
        f"def {name}_meld(" not in source
        for name in ("comment", "preserve", "defer", "apply")
    )
