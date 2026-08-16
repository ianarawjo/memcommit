"""Capture every Help category and every expanded operation record."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/screenshots/mem-help-wording-audit-20260814"
SOURCE_ROOT = Path(os.environ.get("MEMCOMMIT_CAPTURE_SOURCE_ROOT", ROOT)).resolve()
sys.path.insert(0, str(SOURCE_ROOT))

_BASE_PATH = ROOT / "docs/screenshots/mem-help-command-naming-20260813/capture.py"
_SPEC = importlib.util.spec_from_file_location("mem_help_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.ROOT = SOURCE_ROOT
_BASE.OUT = OUT


def _slug(value: str) -> str:
    return value.casefold().replace(" & ", "-").replace(" ", "-")


def _close(child) -> None:
    child.send("q")
    child.expect(_BASE.pexpect.EOF, timeout=5)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)


def main() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")

    # Import after the capture environment is configured so this script audits
    # the same source checkout used by the installed `mem` entry point.
    from memcommit.commands.help_inventory import HELP_CATEGORY_GROUPS
    from memcommit.help_catalog import OPERATION_HELP_BY_NAME

    OUT.mkdir(parents=True, exist_ok=True)
    operation_names = sorted(
        OPERATION_HELP_BY_NAME,
        key=lambda name: (name.casefold(), name),
    )
    expected_detail_names = {
        f"detail-{operation_index:02d}-{operation_name}{suffix}"
        for operation_index, operation_name in enumerate(operation_names, start=1)
        for suffix in (".png", ".txt", ".typescript")
    }
    # Operation insertions change every following ordinal. Remove superseded
    # generated captures so the directory remains one exact ordered sequence.
    for existing in OUT.glob("detail-*"):
        if existing.name not in expected_detail_names:
            existing.unlink()

    category_child, category_recorder = _BASE._spawn(executable, interactive=True)
    _BASE._pump(category_child, seconds=0.8)
    for category_index, (category, command_names) in enumerate(
        HELP_CATEGORY_GROUPS,
        start=1,
    ):
        # Initial focus is the first Contexts row. Each later Tab advances to
        # the next visible category and retains its first command as target.
        if category_index > 1:
            category_child.send("\t")
            _BASE._pump(category_child, seconds=0.35)
        screen = _BASE._snapshot(
            category_recorder,
            f"category-{category_index:02d}-{_slug(category)}",
        )
        assert category in screen
        assert f"mem {command_names[0]}" in screen
    _BASE._assert_color(category_recorder.getvalue())
    _close(category_child)

    detail_child, detail_recorder = _BASE._spawn(executable, interactive=True)
    _BASE._pump(detail_child, seconds=0.8)
    # Initial focus is the first BY KIND command row. Move back to VIEW,
    # select A-Z, re-enter the command surface, and select its first row.
    detail_child.send("\x1b[Z\x1b[C\t\x1b[H")
    _BASE._pump(detail_child, seconds=0.4)
    for operation_index, operation_name in enumerate(operation_names, start=1):
        detail_child.send("\x1b[C")
        _BASE._pump(detail_child, seconds=0.22)
        screen = _BASE._snapshot(
            detail_recorder,
            f"detail-{operation_index:02d}-{operation_name}",
        )
        assert f"▾ mem {operation_name}" in screen
        assert "FLOW" in screen
        assert "EXECUTION" in screen
        assert "EFFECT" in screen

        # The first Left leaves FORM 1; the second collapses the operation.
        # Down then advances exactly one A-Z command for the next capture.
        detail_child.send("\x1b[D\x1b[D")
        if operation_index < len(operation_names):
            detail_child.send("\x1b[B")
        _BASE._pump(detail_child, seconds=0.08)
    _BASE._assert_color(detail_recorder.getvalue())
    _close(detail_child)

    wording_rows = [
        "# Help wording audit matrix",
        "",
        "| Category | Operation | Summary | Flow | Execution | Effect | Range |",
        "|---|---|---|---|---|---|---|",
    ]
    category_by_name = {
        name: category
        for category, names in HELP_CATEGORY_GROUPS
        for name in names
    }
    for operation_name in operation_names:
        operation = OPERATION_HELP_BY_NAME[operation_name]
        values = (
            category_by_name[operation_name],
            operation.name,
            operation.summary,
            operation.flow,
            operation.execution.value,
            operation.effect,
            operation.range or "—",
        )
        escaped = [value.replace("|", "\\|").replace("\n", " ") for value in values]
        wording_rows.append("| " + " | ".join(escaped) + " |")
    (OUT / "wording-matrix.md").write_text(
        "\n".join(wording_rows) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
