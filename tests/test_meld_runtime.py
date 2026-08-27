"""Infrastructure-boundary checks for production Meld execution."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

import memcommit.comparison_execution as comparison_execution
import memcommit.application.operations.meld.assessment_application as meld_assessment_application
import memcommit.application.operations.meld.restart_application as meld_restart_application
import memcommit.application.operations.meld.runtime as meld_runtime
import memcommit.application.operations.meld.session_application as meld_session_application
import memcommit.application.operations.meld.start_application as meld_start_application
from memcommit.application.authority.access import ContextAccess
from memcommit.context import Context, Memory
from memcommit.meld import meld_canonical_digest
from memcommit.application.operations.meld.restart_application import MeldRestartRequest


PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "src" / "memcommit"


@pytest.mark.parametrize(
    "module",
    (
        meld_assessment_application,
        meld_session_application,
        meld_start_application,
        meld_restart_application,
        meld_runtime,
        comparison_execution,
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
            or name.startswith("memcommit.commands")
        )
        == ()
    )


def test_meld_command_contains_no_target_or_session_publication_primitive():
    command_path = PACKAGE_ROOT / "commands" / "meld" / "command.py"
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


def test_meld_command_contains_no_initial_cache_or_provisional_session_logic():
    command_path = PACKAGE_ROOT / "commands" / "meld" / "command.py"
    source = command_path.read_text(encoding="utf-8")

    assert all(
        primitive not in source
        for primitive in (
            "find_installed_directional_meld_prewarm",
            "find_installed_equivalent_directional_comparison",
            "ensure_comparison_analysis",
            "install_prepared_comparison_analysis",
            "MeldSession.create_directional",
            "prepare_meld_assessment",
            "execute_meld_assessment",
        )
    )


def test_meld_command_calls_the_operation_owned_apply_service_directly():
    command_path = PACKAGE_ROOT / "commands" / "meld" / "command.py"
    source = command_path.read_text(encoding="utf-8")

    assert "execute_meld_apply(" in source
    assert "run_application_flow" not in source
    assert "MeldApplicationFlowPort" not in source


def test_python_client_uses_the_operation_owned_meld_resolution_boundary():
    client_path = PACKAGE_ROOT / "adapters" / "python_api" / "client.py"
    operation_path = client_path.with_name("_operations") / "meld.py"
    source = client_path.read_text(encoding="utf-8")
    if operation_path.exists():
        source += operation_path.read_text(encoding="utf-8")

    assert "prepare_meld_resolution_turn(" in source
    assert "execute_prepared_meld_turn(" in source
    assert "execute_meld_turn(" not in source
    assert "prepare_meld_assessment" not in source


def test_meld_provider_timeout_policy_is_runtime_owned(monkeypatch):
    class Provider:
        def __init__(self):
            self.timeout = 30

    monkeypatch.setattr(meld_runtime, "CodexChatGPTProvider", Provider)

    provider = meld_runtime.connect_meld_provider(Provider)

    assert provider.timeout == meld_runtime.MELD_AGGREGATE_TIMEOUT_SECONDS


def test_symmetric_saved_compare_reuse_does_not_connect_provider(monkeypatch):
    left = Context(uid="11111111-1111-4111-8111-111111111111", name="left")
    right = Context(uid="22222222-2222-4222-8222-222222222222", name="right")
    left.add(Memory(uid="33333333-3333-4333-8333-333333333333", content="Left."))
    right.add(Memory(uid="44444444-4444-4444-8444-444444444444", content="Right."))
    store = SimpleNamespace()
    accesses = tuple(
        ContextAccess(
            store=store,
            context_name=context.name,
            display_name=context.name,
            attachment_name=None,
            permission="READ",
        )
        for context in (left, right)
    )
    saved = SimpleNamespace(name="saved-analysis")

    def ensure(**kwargs):
        # A saved/equivalent hit returns before invoking the lazy live callback.
        assert callable(kwargs["analyze"])
        return SimpleNamespace(analysis=saved, origin="SAVED_REUSE")

    monkeypatch.setattr(meld_runtime, "ensure_comparison_analysis", ensure)

    result = meld_runtime._start_comparison(
        meld_start_application.MeldStartRequest(
            mode="SYMMETRIC",
            left_name=left.name,
            right_name=right.name,
            target_name="result",
        ),
        store=store,
        left_access=accesses[0],
        right_access=accesses[1],
        left=left,
        right=right,
        current_name=None,
        provider_factory=lambda: pytest.fail(
            "saved symmetric Compare reuse connected a provider"
        ),
    )

    assert result is saved


def test_symmetric_subset_projection_is_resolved_and_recorded_in_runtime(
    monkeypatch,
):
    left = Context(uid="11111111-1111-4111-8111-111111111111", name="left")
    right = Context(uid="22222222-2222-4222-8222-222222222222", name="right")
    left.add(Memory(uid="33333333-3333-4333-8333-333333333333", content="Left."))
    right.add(Memory(uid="44444444-4444-4444-8444-444444444444", content="Right."))
    store = SimpleNamespace()
    accesses = tuple(
        ContextAccess(
            store=store,
            context_name=context.name,
            display_name=context.name,
            attachment_name=None,
            permission="READ",
        )
        for context in (left, right)
    )
    projected = SimpleNamespace(name="projected-analysis")
    match = SimpleNamespace(
        analysis=projected,
        origin="PROJECTED_PREWARM",
        entry_key="projected-entry",
        prepared_context_names=("prepared/left", "prepared/right"),
    )
    recorded = []
    monkeypatch.setattr(meld_runtime, "load_profile_registry", lambda: None)
    monkeypatch.setattr(
        meld_runtime,
        "find_declared_equivalent_compare_analysis",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        meld_runtime,
        "find_declared_projected_compare_analysis",
        lambda **kwargs: match,
    )

    def ensure(**kwargs):
        assert (
            kwargs["equivalent"](
                meld_runtime.ComparisonInput.from_contexts(left, right)
            )
            is projected
        )
        return SimpleNamespace(
            analysis=projected,
            origin="EQUIVALENT_SCOPE_PREWARM",
        )

    monkeypatch.setattr(meld_runtime, "ensure_comparison_analysis", ensure)
    monkeypatch.setattr(
        meld_runtime,
        "record_projected_compare_prewarm",
        lambda *args, **kwargs: recorded.append((args, kwargs)),
    )

    result = meld_runtime._start_comparison(
        meld_start_application.MeldStartRequest(
            mode="SYMMETRIC",
            left_name=left.name,
            right_name=right.name,
            target_name="result",
        ),
        store=store,
        left_access=accesses[0],
        right_access=accesses[1],
        left=left,
        right=right,
        current_name=None,
        provider_factory=lambda: pytest.fail(
            "projected symmetric Compare reuse connected a provider"
        ),
    )

    assert result is projected
    assert recorded[0][1]["entry_key"] == "projected-entry"


def test_assessment_freeze_falls_back_to_exact_installed_branch(monkeypatch):
    completion = "saved complete Meld response"
    branch = SimpleNamespace(completion=completion)
    store = SimpleNamespace(load_meld_resolution_branch=lambda key: None)
    session = SimpleNamespace(current_turn=SimpleNamespace(sequence=1, scope="ALL"))
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


def test_memory_focused_directional_restart_reuses_prewarm_and_cas_replaces_without_provider(
    monkeypatch,
):
    incoming = Context(uid="11111111-1111-4111-8111-111111111111", name="incoming")
    incoming_memory_uid = "22222222-2222-4222-8222-222222222222"
    incoming.add(Memory(uid=incoming_memory_uid, content="New fact."))
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
    comparison_calls = []

    def resolve_comparison(*args, **kwargs):
        comparison_calls.append((args, kwargs))
        return None

    monkeypatch.setattr(meld_runtime, "_start_comparison", resolve_comparison)
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
            incoming_memory=incoming_memory_uid[:8],
        ),
        store=store,
        provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("A prewarmed restart connected a provider.")
        ),
    )

    assert result.origin == "EXACT_PREWARM"
    assert result.session.frames[0].selected_memory_uid == incoming_memory_uid
    assert store.saved == [(result.session, version)]
    assert len(comparison_calls) == 1
    assert comparison_calls[0][1]["allow_provider"] is False
