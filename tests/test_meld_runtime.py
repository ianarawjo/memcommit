"""Infrastructure-boundary checks for production Meld execution."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

import memcommit.meld_assessment_application as meld_assessment_application
import memcommit.meld_runtime as meld_runtime
import memcommit.meld_session_application as meld_session_application
import memcommit.meld_start_application as meld_start_application


@pytest.mark.parametrize(
    "module",
    (
        meld_assessment_application,
        meld_session_application,
        meld_start_application,
        meld_runtime,
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

    assert tuple(
        name
        for name in imported
        if name == "typer"
        or name.startswith("prompt_toolkit")
        or name.startswith("memcommit.commands")
    ) == ()


def test_assessment_freeze_falls_back_to_exact_installed_branch(monkeypatch):
    completion = "saved complete Meld response"
    branch = SimpleNamespace(completion=completion)
    store = SimpleNamespace(load_meld_resolution_branch=lambda key: None)
    session = SimpleNamespace(
        current_turn=SimpleNamespace(sequence=1, scope="ALL")
    )
    monkeypatch.setattr(
        meld_runtime,
        "meld_turn_request_digest",
        lambda value: "0" * 64,
    )
    monkeypatch.setattr(
        meld_runtime,
        "configured_meld_cache_identity",
        lambda: {
            "provider": "codex-chatgpt",
            "model": "current-recommended",
            "reasoning_effort": None,
        },
    )
    monkeypatch.setattr(
        meld_runtime,
        "meld_resolution_cache_key",
        lambda request, provider: "1" * 64,
    )
    monkeypatch.setattr(
        meld_runtime,
        "find_installed_meld_resolution_branch",
        lambda **kwargs: branch,
    )

    frozen = meld_runtime.MemoryStoreMeldAssessmentPort(store).freeze(
        session,
        expected_session_digest="version-1",
    )

    assert frozen.cached_completion == completion
