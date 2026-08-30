"""Boundary checks for the fully retired Atomize Grounding contract."""

from __future__ import annotations

from pathlib import Path

from memcommit.persistence.store import MemoryStore


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_atomize_grounding_has_no_runtime_or_model_route() -> None:
    retired_paths = (
        "src/memcommit/adapters/agent/atomize_grounding.py",
        "src/memcommit/adapters/console/commands/atomize/grounding.py",
        "src/memcommit/adapters/python_api/atomize_grounding.py",
        "src/memcommit/adapters/python_api/_operations/atomize_grounding.py",
        "src/memcommit/application/operations/atomize/grounding_application.py",
        "src/memcommit/application/operations/atomize/grounding_provider.py",
        "src/memcommit/application/operations/atomize/grounding_runtime.py",
        "src/memcommit/application/operations/atomize/grounding/__init__.py",
        "src/memcommit/application/operations/atomize/grounding/bindings.py",
        "src/memcommit/application/operations/atomize/grounding/changes.py",
        "src/memcommit/application/operations/atomize/grounding/review.py",
        "src/memcommit/application/operations/atomize/grounding/session.py",
        (
            "src/memcommit/application/capabilities/retained_history/"
            "memory_history_reconstruction/retained_record_verification/"
            "validators/grounding.py"
        ),
    )

    assert all(not (REPOSITORY_ROOT / path).exists() for path in retired_paths)
    assert not hasattr(MemoryStore, "load_atomize_grounding_session")
    assert not hasattr(MemoryStore, "save_atomize_grounding_session")
    assert not hasattr(MemoryStore, "load_atomize_grounding_history")
