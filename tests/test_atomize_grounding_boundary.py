"""Architectural contract for Atomize Grounding application extraction."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest

from memcommit.atomize_grounding_application import (
    AtomizeGroundingApplicationError,
    GroundingKeepRequest,
    run_atomize_grounding_keep,
)
from memcommit.atomize_grounding import (
    AtomizeGroundingAnchor,
    AtomizeGroundingBindings,
    AtomizeGroundingSession,
)
from memcommit.atomize_grounding_runtime import MemoryStoreAtomizeGroundingPort
from memcommit.store import MemoryStore


ROOT = Path(__file__).resolve().parents[1]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return imported


def test_grounding_application_and_runtime_do_not_import_commands() -> None:
    for relative in (
        "memcommit/atomize_grounding_application.py",
        "memcommit/atomize_grounding_runtime.py",
    ):
        imports = _imports(ROOT / relative)
        assert not any(name.startswith("memcommit.commands") for name in imports)


def test_command_grounding_module_is_a_compatibility_facade() -> None:
    source = (ROOT / "memcommit/commands/atomize_grounding.py").read_text(
        encoding="utf-8"
    )
    assert len(source.splitlines()) < 150
    assert "MemoryStoreAtomizeGroundingPort" in source
    assert "AutoCheckpoint" not in source
    assert "assess_atomize_grounding_turn" not in source


def test_keep_runner_rejects_a_nonterminal_port_result() -> None:
    context_uid = "context-uid"

    class Port:
        def keep(self, request):
            assert request == GroundingKeepRequest(context_uid=context_uid)
            return SimpleNamespace(
                bindings=SimpleNamespace(
                    context_uid=context_uid,
                    context_name="example",
                ),
                state="AWAITING_REPLY",
            )

    with pytest.raises(
        AtomizeGroundingApplicationError,
        match="did not close",
    ):
        run_atomize_grounding_keep(
            GroundingKeepRequest(context_uid=context_uid),
            port=Port(),
        )


def test_runtime_keep_is_callable_without_a_command_adapter(isolated_store) -> None:
    del isolated_store
    digest = "0" * 64
    context_uid = str(uuid.uuid4())
    session = AtomizeGroundingSession.create(
        bindings=AtomizeGroundingBindings(
            context_uid=context_uid,
            context_name="example/source",
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
    store = MemoryStore()
    store.save_atomize_grounding_session(session)

    kept = run_atomize_grounding_keep(
        GroundingKeepRequest(context_uid=context_uid),
        port=MemoryStoreAtomizeGroundingPort(store),
    )

    assert kept.state == "KEPT_REVIEW_ONLY"
    assert store.load_atomize_grounding_session(context_uid) == kept
