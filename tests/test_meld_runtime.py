"""Infrastructure-boundary checks for production Meld execution."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

import memcommit.meld_assessment_application as meld_assessment_application
import memcommit.meld_restart_application as meld_restart_application
import memcommit.meld_runtime as meld_runtime
import memcommit.meld_session_application as meld_session_application
import memcommit.meld_start_application as meld_start_application
from memcommit.authority.access import ContextAccess
from memcommit.context import Context, Memory
from memcommit.meld import meld_canonical_digest
from memcommit.meld_restart_application import MeldRestartRequest


@pytest.mark.parametrize(
    "module",
    (
        meld_assessment_application,
        meld_session_application,
        meld_start_application,
        meld_restart_application,
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


def test_meld_command_contains_no_target_or_session_publication_primitive():
    command_path = Path(meld_runtime.__file__).with_name("commands") / "meld.py"
    source = command_path.read_text(encoding="utf-8")

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


def test_directional_restart_reuses_prewarm_and_cas_replaces_without_provider(
    monkeypatch,
):
    incoming = Context(uid="11111111-1111-4111-8111-111111111111", name="incoming")
    incoming.add(
        Memory(uid="22222222-2222-4222-8222-222222222222", content="New fact.")
    )
    baseline = Context(uid="33333333-3333-4333-8333-333333333333", name="baseline")
    baseline.add(
        Memory(uid="44444444-4444-4444-8444-444444444444", content="Old fact.")
    )
    prior = SimpleNamespace(to_dict=lambda: {"uid": "prior"})

    class _Store:
        def __init__(self):
            self.saved = []

        def current_context_name(self):
            return None

        def load_meld_session(self, target_uid):
            assert target_uid == baseline.uid
            return prior

        def save_meld_session(self, session, *, expected_session_digest):
            self.saved.append((session, expected_session_digest))

    store = _Store()
    version = meld_canonical_digest(prior.to_dict())
    accesses = {
        incoming.name: ContextAccess(
            store=store,
            context_name=incoming.name,
            display_name=incoming.name,
            attachment_name=None,
            permission="READ",
        ),
        baseline.name: ContextAccess(
            store=store,
            context_name=baseline.name,
            display_name=baseline.name,
            attachment_name=None,
            permission="READ",
        ),
    }
    monkeypatch.setattr(
        meld_runtime,
        "resolve_context_access",
        lambda _store, name, **kwargs: accesses[name],
    )
    monkeypatch.setattr(meld_runtime, "authorize_combination", lambda values: None)
    monkeypatch.setattr(
        meld_runtime,
        "authorize_derived_transfer",
        lambda source, target: None,
    )
    monkeypatch.setattr(
        meld_runtime,
        "analysis_retention",
        lambda values: "LOCAL",
    )
    monkeypatch.setattr(
        meld_runtime,
        "authorize_analysis_save",
        lambda values, **kwargs: None,
    )
    monkeypatch.setattr(
        meld_runtime,
        "load_meld_source",
        lambda access, **kwargs: (
            incoming if access.context_name == incoming.name else baseline
        ),
    )
    monkeypatch.setattr(meld_runtime, "_start_comparison", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        meld_runtime,
        "find_installed_directional_meld_prewarm",
        lambda **kwargs: SimpleNamespace(
            session=kwargs["current"],
            origin="EXACT_PREWARM",
        ),
    )
    monkeypatch.setattr(
        meld_runtime,
        "load_bound_meld_contexts",
        lambda *args, **kwargs: (incoming, baseline, baseline),
    )
    monkeypatch.setattr(
        meld_runtime,
        "assert_meld_source_bindings",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        meld_runtime,
        "assert_unapplied_meld_target",
        lambda *args, **kwargs: None,
    )

    result = meld_runtime.execute_meld_restart(
        MeldRestartRequest(
            mode="DIRECTIONAL",
            left_name=incoming.name,
            right_name=baseline.name,
            target_name=baseline.name,
            expected_version=version,
        ),
        store=store,
        provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("A prewarmed restart connected a provider.")
        ),
    )

    assert result.origin == "EXACT_PREWARM"
    assert store.saved == [(result.session, version)]
