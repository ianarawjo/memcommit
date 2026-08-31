"""Structural contracts for the Help operations split in this change."""

from __future__ import annotations

import ast
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONSOLE_COMMANDS = (
    REPOSITORY_ROOT / "src/memcommit/adapters/console/commands"
)
APPLICATION_OPERATIONS = (
    REPOSITORY_ROOT / "src/memcommit/application/operations"
)


def test_changed_help_operations_have_independent_console_packages() -> None:
    operation_paths = {
        "checkout": "checkout",
        "list": "list",
        "lock": "lock",
        "unlock": "unlock",
        "rename": "rename",
        "revert": "history_recovery/recovery/revert",
    }
    for operation_path in operation_paths.values():
        package = CONSOLE_COMMANDS / operation_path
        assert (package / "__init__.py").is_file()
        assert (package / "command.py").is_file()

    assert not (CONSOLE_COMMANDS / "list_memories" / "command.py").exists()
    assert not (CONSOLE_COMMANDS / "write_protection" / "command.py").exists()


def test_changed_application_effects_have_operation_packages() -> None:
    operation_paths = (
        "history_recovery/recovery/checkpoint",
        "list",
        "lock",
        "unlock",
        "rename",
        "history_recovery/recovery/revert",
    )
    for operation_path in operation_paths:
        package = APPLICATION_OPERATIONS / operation_path
        assert (package / "__init__.py").is_file()
        assert (package / "application.py").is_file()
        assert (package / "runtime.py").is_file()

    # Checkout is deliberately console composition of these two existing
    # application operations, not a third effect model.
    checkout_source = (CONSOLE_COMMANDS / "checkout" / "command.py").read_text(
        encoding="utf-8"
    )
    assert "branch.cmd(" in checkout_source
    assert "switch.cmd(" in checkout_source


def test_copy_move_and_eval_have_public_operation_packages() -> None:
    for operation_path in ("copy", "direct_changes/move"):
        package = APPLICATION_OPERATIONS / operation_path
        assert (package / "application.py").is_file()
        assert (package / "runtime.py").is_file()
    eval_package = APPLICATION_OPERATIONS / "eval"
    assert (eval_package / "__init__.py").is_file()
    assert {path.name for path in eval_package.glob("*.py")} == {"__init__.py"}
    eval_console = CONSOLE_COMMANDS / "eval"
    assert (eval_console / "__init__.py").is_file()
    assert (eval_console / "command.py").is_file()
    evaluation_capability = (
        REPOSITORY_ROOT
        / "src/memcommit/application/capabilities/evaluation"
    )
    assert not any(evaluation_capability.glob("*.py"))


def test_console_adapters_do_not_reclaim_application_mutations() -> None:
    prohibited = {
        "list": ("resolve_context_access", "freeze_readable_context_catalog"),
        "rename": ("plan_context_rename", "rename_contexts("),
        "history_recovery/recovery/revert": (
            "store.revert(",
            "store.revert_checkpoint_unit(",
        ),
    }
    for operation, snippets in prohibited.items():
        source = (CONSOLE_COMMANDS / operation / "command.py").read_text(
            encoding="utf-8"
        )
        assert all(snippet not in source for snippet in snippets)


def test_root_entrypoint_registers_checkout_without_owning_its_grammar() -> None:
    path = REPOSITORY_ROOT / "src/memcommit/adapters/console/entrypoint.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_checkout"
        for node in ast.walk(tree)
    )
