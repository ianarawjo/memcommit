"""Physical layout contracts for application operations and capabilities."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys


REPOSITORY = Path(__file__).resolve().parents[1]
APPLICATION = REPOSITORY / "src" / "memcommit" / "application"
CAPABILITIES = APPLICATION / "capabilities"

CAPABILITY_ENTRIES = {
    "__init__.py",
    "authority",
    "context_locator.py",
    "evaluation",
    "flow.py",
    "memory_issue_analysis",
    "memory_report_targeting.py",
    "ops.py",
    "resolution",
    "retained_history",
    "review_policy.py",
    "reviewing",
    "semantic",
    "semantic_execution",
    "semantic_result_memorization.py",
}

LEGACY_APPLICATION_MODULES = (
    "memcommit.application.authority",
    "memcommit.application.context_locator",
    "memcommit.application.evaluation",
    "memcommit.application.exact_command_review",
    "memcommit.application.flow",
    "memcommit.application.interactive_command",
    "memcommit.application.interactive_command_review",
    "memcommit.application.ops",
    "memcommit.application.resolution",
    "memcommit.application.retained_history",
    "memcommit.application.review_policy",
    "memcommit.application.reviewing",
    "memcommit.application.semantic",
    "memcommit.application.semantic_execution",
    "memcommit.application.capabilities.exact_command_review",
    "memcommit.application.capabilities.interactive_command_review",
)
LEGACY_APPLICATION_MEMBERS = {
    module.rsplit(".", 1)[-1] for module in LEGACY_APPLICATION_MODULES
}


def test_application_root_has_only_operations_and_capabilities() -> None:
    visible = {
        path.name
        for path in APPLICATION.iterdir()
        if path.name != "__pycache__"
    }

    assert visible == {"__init__.py", "capabilities", "operations"}
    assert {path.name for path in CAPABILITIES.iterdir() if path.name != "__pycache__"} == (
        CAPABILITY_ENTRIES
    )


def test_production_source_uses_no_pre_capability_application_paths() -> None:
    offenders: list[tuple[str, str]] = []
    for path in (REPOSITORY / "src" / "memcommit").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for module in LEGACY_APPLICATION_MODULES:
            if module in source:
                offenders.append((str(path.relative_to(REPOSITORY)), module))

    assert offenders == []


def test_repository_python_imports_do_not_reach_through_application_root() -> None:
    offenders: list[tuple[str, int, str]] = []
    roots = (
        REPOSITORY / "src",
        REPOSITORY / "tests",
        REPOSITORY / "scripts",
        REPOSITORY / "agent-records" / "docs",
    )
    for root in roots:
        for path in root.rglob("*.py"):
            if path == Path(__file__):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                if node.module != "memcommit.application":
                    continue
                for alias in node.names:
                    if alias.name in LEGACY_APPLICATION_MEMBERS:
                        offenders.append(
                            (
                                str(path.relative_to(REPOSITORY)),
                                node.lineno,
                                alias.name,
                            )
                        )

    assert offenders == []


def test_pre_capability_application_modules_are_unavailable() -> None:
    program = "\n".join(
        (
            "from importlib import import_module",
            f"legacy = {LEGACY_APPLICATION_MODULES!r}",
            "unexpected = []",
            "for module in legacy:",
            "    try:",
            "        import_module(module)",
            "    except ModuleNotFoundError:",
            "        pass",
            "    else:",
            "        unexpected.append(module)",
            "assert not unexpected, unexpected",
        )
    )

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY,
        check=True,
    )
