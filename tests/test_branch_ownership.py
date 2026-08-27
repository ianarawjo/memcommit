"""Application, runtime, and command ownership for Branch."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys

import pytest

from memcommit.application.operations.branch.application import (
    BranchError,
    BranchRequest,
    BranchResult,
    BranchedContext,
    plan_branch,
    run_branch,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _request(
    *,
    include_descendants: bool = True,
    target_name: str = "experiment",
) -> BranchRequest:
    return BranchRequest(
        source_name="source",
        target_name=target_name,
        include_descendants=include_descendants,
        expected_current="source",
        local_context_names=(
            "other",
            "source",
            "source/child",
            "source/child/deep",
        ),
    )


def test_branch_application_plans_exact_lexical_name_mapping() -> None:
    plan = plan_branch(_request())

    assert tuple(
        (context.source_name, context.target_name) for context in plan.contexts
    ) == (
        ("source", "experiment"),
        ("source/child", "experiment/child"),
        ("source/child/deep", "experiment/child/deep"),
    )
    assert plan.context_count == 3
    assert plan.descendant_count == 2


def test_exact_branch_plan_does_not_hide_descendant_expansion() -> None:
    plan = plan_branch(_request(include_descendants=False))

    assert tuple(
        (context.source_name, context.target_name) for context in plan.contexts
    ) == (("source", "experiment"),)


def test_branch_plan_rejects_any_occupied_mapped_target() -> None:
    request = BranchRequest(
        source_name="source",
        target_name="experiment",
        include_descendants=True,
        expected_current="source",
        local_context_names=(
            "source",
            "source/child",
            "experiment/child",
        ),
    )

    with pytest.raises(BranchError, match="experiment/child.*already exists"):
        plan_branch(request)


def test_branch_application_rejects_a_receipt_outside_the_plan() -> None:
    request = _request(include_descendants=False)

    class WrongPort:
        def apply(self, plan):
            return BranchResult(
                source_root="source",
                target_root="experiment",
                include_descendants=False,
                contexts=(
                    BranchedContext(
                        source_name="source",
                        source_uid="source-uid",
                        target_name="elsewhere",
                        target_uid="target-uid",
                    ),
                ),
                current_context_name="experiment",
            )

    with pytest.raises(BranchError, match="outside its plan"):
        run_branch(request, port=WrongPort())


def test_branch_application_has_no_cli_tui_or_store_dependency() -> None:
    path = REPOSITORY_ROOT / "src/memcommit/application/operations/branch/application.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    imports.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )

    assert not any(
        module == "typer"
        or module == "memcommit.store"
        or module.startswith("memcommit.adapters.interfaces.")
        or module.startswith("memcommit.adapters.console.commands.")
        for module in imports
    )


def test_branch_command_delegates_materialization_to_the_operation_runtime() -> None:
    path = REPOSITORY_ROOT / "src/memcommit/adapters/console/commands/branch/command.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    imports.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )

    assert "memcommit.application.operations.branch.application" in imports
    assert "memcommit.application.operations.branch.runtime" in imports
    assert "memcommit.application.ops" not in imports
    assert "memcommit.memory_lineage" not in imports
    assert not {
        "ContextBranchBinding",
        "ContextBranchMemoryBinding",
    } & {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }


def test_branch_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.branch

assert "memcommit.application.operations.branch.application" not in sys.modules
assert "memcommit.application.operations.branch.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
