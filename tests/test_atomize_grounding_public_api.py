"""Stable public Python API coverage for conversational Atomize Grounding."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import uuid

import pytest

import memcommit
import memcommit.adapters.python_api._operations.atomize_grounding as grounding_operation
import memcommit.application.ops as ops
from memcommit.adapters.python_api import (
    AtomizeGroundingContextError,
    AtomizeGroundingInputError,
    AtomizeGroundingProviderFailure,
    AtomizeGroundingSessionResult,
    MemCommitClient,
)
from memcommit.application.operations.atomize.grounding import (
    AtomizeGroundingAnchor,
    AtomizeGroundingBindings,
    AtomizeGroundingSession,
)
from memcommit.persistence.store import MemoryStore


REPOSITORY = Path(__file__).parents[1]


def _saved_dialogue(store: MemoryStore, name: str = "task/source"):
    context = ops.init(name)
    store.save(context)
    store.set_current(context.name)
    digest = "0" * 64
    session = AtomizeGroundingSession.create(
        bindings=AtomizeGroundingBindings(
            context_uid=context.uid,
            context_name=context.name,
            context_digest=digest,
            analysis_uid=str(uuid.uuid4()),
            analysis_digest=digest,
            workbench_uid=str(uuid.uuid4()),
            workbench_digest=digest,
            response_digest=digest,
        ),
        anchor=AtomizeGroundingAnchor(
            issue_uid="ambiguity:example",
            kind="AMBIGUITY",
            arity="UNARY",
            source_uids=(str(uuid.uuid4()),),
            issue_digest=digest,
        ),
    )
    store.save_atomize_grounding_session(session)
    return context, session


def test_root_package_exports_public_grounding_objects() -> None:
    assert memcommit.AtomizeGroundingSessionResult is AtomizeGroundingSessionResult
    assert memcommit.AtomizeGroundingInputError is AtomizeGroundingInputError


def test_open_grounding_is_provider_free_and_resolves_relative_context(
    isolated_store,
) -> None:
    store = MemoryStore()
    _context, session = _saved_dialogue(store)
    session.keep_review_only()
    store.save_atomize_grounding_session(session)
    provider_calls = 0

    def connect():
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("provider must not be opened")

    result = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=connect,
    ).open_atomize_grounding(".")

    assert result.session_uid == session.uid
    assert result.context_name == "task/source"
    assert result.state == "KEPT_REVIEW_ONLY"
    assert result.issue_uid == "ambiguity:example"
    assert result.turn_count == 0
    assert provider_calls == 0


def test_keep_grounding_changes_only_the_dialogue_receipt(isolated_store) -> None:
    store = MemoryStore()
    context, _session = _saved_dialogue(store)
    before_context = store._context_file(context.name).read_bytes()
    before_checkpoints = len(store.list_checkpoints(context.name))

    result = MemCommitClient(root=isolated_store).keep_atomize_grounding()

    assert result.state == "KEPT_REVIEW_ONLY"
    assert result.ready_to_apply is False
    assert store._context_file(context.name).read_bytes() == before_context
    assert len(store.list_checkpoints(context.name)) == before_checkpoints


def test_open_grounding_maps_missing_dialogue_to_context_error(
    isolated_store,
) -> None:
    store = MemoryStore()
    context = ops.init("empty")
    store.save(context)

    with pytest.raises(AtomizeGroundingContextError, match="No atomize grounding"):
        MemCommitClient(root=isolated_store).open_atomize_grounding("empty")


def test_start_rejects_invalid_input_before_store_or_provider(tmp_path) -> None:
    root = tmp_path / "missing-store"
    client = MemCommitClient(
        root=root,
        semantic_provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("provider must not be opened")
        ),
    )

    with pytest.raises(AtomizeGroundingInputError, match="selector"):
        client.start_atomize_grounding("", "Clarify this.")

    assert not root.exists()


def test_start_uses_typed_application_request(monkeypatch, isolated_store) -> None:
    store = MemoryStore()
    context, session = _saved_dialogue(store)
    captured = []

    monkeypatch.setattr(
        grounding_operation,
        "_saved_inputs",
        lambda runtime, context_name: (context, object(), object()),
    )

    def run(request, **kwargs):
        captured.append((request, kwargs))
        return session

    monkeypatch.setattr(grounding_operation, "run_atomize_grounding_start", run)

    result = MemCommitClient(root=isolated_store).start_atomize_grounding(
        "1",
        "Use the physical-card-only reading.",
    )

    request, kwargs = captured[0]
    assert request.context is context
    assert request.selector == "1"
    assert request.comment == "Use the physical-card-only reading."
    assert kwargs["port"].store.store_dir == store.store_dir
    assert result.session_uid == session.uid


def test_provider_failure_is_projected_without_command_exceptions(
    monkeypatch,
    isolated_store,
) -> None:
    store = MemoryStore()
    context, _session = _saved_dialogue(store)
    monkeypatch.setattr(
        grounding_operation,
        "_saved_inputs",
        lambda runtime, context_name: (context, object(), object()),
    )

    def run(request, *, provider_factory, **kwargs):
        del request, kwargs
        provider_factory().complete("prompt", operation="atomize_grounding_turn")

    monkeypatch.setattr(grounding_operation, "run_atomize_grounding_start", run)

    class BrokenProvider:
        def complete(self, prompt, *, operation, output_schema=None):
            del prompt, operation, output_schema
            raise RuntimeError("provider unavailable")

    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=BrokenProvider,
    )

    with pytest.raises(
        AtomizeGroundingProviderFailure,
        match="provider unavailable",
    ):
        client.start_atomize_grounding("1", "Clarify this.")


def test_public_client_import_keeps_grounding_assembly_lazy(tmp_path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "\n".join(
                (
                    "import sys",
                    "from memcommit.adapters.python_api import MemCommitClient",
                    "assert 'memcommit.adapters.python_api._operations.atomize_grounding' not in sys.modules",
                    "assert 'memcommit.application.operations.atomize.grounding_runtime' not in sys.modules",
                    "client = MemCommitClient(root=r'%s', create=True)" % (tmp_path / "store"),
                    "try:",
                    "    client.start_atomize_grounding('', 'comment')",
                    "except Exception:",
                    "    pass",
                    "assert 'memcommit.adapters.python_api._operations.atomize_grounding' in sys.modules",
                    "assert 'memcommit.application.operations.atomize.grounding_runtime' in sys.modules",
                )
            ),
        ],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
