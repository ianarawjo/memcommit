"""Ownership gates for the consolidated console adapter package."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "src" / "memcommit"
CONSOLE = PACKAGE / "adapters" / "console"
RETIRED = PACKAGE / "adapters" / "interfaces" / "console"


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
        elif isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
    return tuple(modules)


def test_retired_console_staging_package_has_no_source_or_importers() -> None:
    assert not RETIRED.exists()

    offenders = [
        (str(path.relative_to(ROOT)), module)
        for path in PACKAGE.rglob("*.py")
        for module in _imports(path)
        if module.startswith("memcommit.adapters.interfaces.console")
    ]

    assert offenders == []


def test_reusable_console_modules_do_not_import_command_adapters() -> None:
    reusable = [
        *(
            path
            for path in CONSOLE.glob("*.py")
            if path.name != "entrypoint.py"
        ),
        *(CONSOLE / "responses").rglob("*.py"),
        *(CONSOLE / "selection").rglob("*.py"),
    ]
    offenders = [
        (str(path.relative_to(ROOT)), module)
        for path in reusable
        for module in _imports(path)
        if module.startswith("memcommit.adapters.console.commands")
    ]

    assert offenders == []


def test_console_package_import_does_not_assemble_commands() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import importlib.util; import sys; "
                "import memcommit.adapters.console; "
                "assert importlib.util.find_spec("
                "'memcommit.adapters.interfaces.console') is None; "
                "assert 'memcommit.adapters.console.entrypoint' not in sys.modules; "
                "assert 'memcommit.adapters.console.commands' not in sys.modules"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
