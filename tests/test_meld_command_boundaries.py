from __future__ import annotations

from pathlib import Path

import pytest

from memcommit.adapters.console.commands.meld import command
from memcommit.adapters.console.commands.meld import entrypoint
import memcommit.adapters.console.commands.meld.interpretation as interpretation
from memcommit.adapters.console.commands.meld import presentation
from memcommit.adapters.console.commands.meld.workflow import workflow
from memcommit.core.context import Context
from memcommit.persistence.store import MemoryStore


class _InterpretationStore:
    def __init__(self, current: str | None = None, existing: tuple[str, ...] = ()):
        self.current = current
        self.existing = set(existing)
        self.current_reads = 0
        self.store_dir = Path("/tmp/memcommit-interpretation-store")

    def current_context_name(self) -> str | None:
        self.current_reads += 1
        return self.current

    def context_exists(self, name: str) -> bool:
        return name in self.existing

    def list_context_names(self) -> list[str]:
        return sorted(self.existing)

    def load_direct(self, name: str) -> Context:
        if name not in self.existing:
            raise FileNotFoundError(name)
        return Context(
            uid=(name.encode("utf-8").hex() + "0" * 36)[:36],
            name=name,
        )

    def load_direct_context_graph_strict(self) -> tuple[Context, ...]:
        return tuple(self.load_direct(name) for name in sorted(self.existing))


def _request(**overrides) -> interpretation.MeldCommandRequest:
    values = {
        "left": None,
        "right": None,
        "result": None,
        "into": None,
        "to": None,
        "from_": None,
        "issue": None,
        "choice": None,
        "comment": None,
        "expect_session": None,
        "preserve_all": False,
        "defer_all": False,
        "accept": False,
        "restart": False,
        "revision": None,
        "revises_turn": (),
        "expand": None,
        "sessions": False,
        "direct": False,
        "recursive": False,
        "left_descendants": None,
        "right_descendants": None,
        "memory": None,
        "incoming_memory": None,
        "baseline_memory": None,
    }
    values.update(overrides)
    return interpretation.MeldCommandRequest(**values)


def test_meld_command_facade_preserves_existing_imports() -> None:
    assert command.cmd is entrypoint.cmd
    assert command.render_meld_session is presentation.render_meld_session
    assert command._resume_picked_meld is workflow._resume_picked_meld


def test_meld_entrypoint_delegates_one_validated_request(monkeypatch) -> None:
    store = _InterpretationStore(existing=("incoming", "baseline"))
    calls = []

    monkeypatch.setattr(entrypoint, "MemoryStore", lambda *, create: store)
    monkeypatch.setattr(
        entrypoint,
        "execute_meld_command",
        lambda **kwargs: calls.append(kwargs),
    )

    entrypoint.cmd(left="incoming", right="baseline")

    assert len(calls) == 1
    assert calls[0]["store"] is store
    request = calls[0]["request"]
    assert isinstance(request, interpretation.InterpretedMeldCommand)
    assert request.mode == "DIRECTIONAL"
    assert request.left_name == "incoming"
    assert request.right_name == "baseline"
    assert request.target_name == "baseline"
    assert not hasattr(request, "to_is_symmetric")
    assert not hasattr(request, "directional_to")
    assert request.left_descendants is False
    assert request.right_descendants is False
    assert store.current_reads == 1


def test_meld_interpretation_owns_symmetric_to_and_relative_source_meaning() -> None:
    store = _InterpretationStore(
        current="work/current",
        existing=("work/current", "work/a", "work/b"),
    )

    interpreted = interpretation.interpret_meld_command(
        _request(left="../a", right="../b", to="results/c"),
        store=store,
    )

    assert isinstance(interpreted, interpretation.InterpretedMeldCommand)
    assert interpreted.mode == "SYMMETRIC"
    assert interpreted.left_name == "work/a"
    assert interpreted.right_name == "work/b"
    assert interpreted.target_name == "results/c"
    assert interpreted.start_command == "mem meld work/a work/b --to results/c"
    assert store.current_reads == 1


def test_meld_existing_endpoints_round_trip_context_uid_prefixes(tmp_path) -> None:
    store = MemoryStore(root=tmp_path / "store")
    incoming = Context(
        uid="2a4dc8ab-cc03-5721-923f-03e3b4669cf5",
        name="practice/coffee/compare-merge-meld-update/a",
    )
    baseline = Context(
        uid="bbbbbbbb-1111-4111-8111-111111111111",
        name="coffee",
    )
    store.save(incoming)
    store.save(baseline)

    interpreted = interpretation.interpret_meld_command(
        _request(from_="2a4dc8ab", to="bbbbbbbb"),
        store=store,
    )

    assert isinstance(interpreted, interpretation.InterpretedMeldCommand)
    assert interpreted.left_name == incoming.name
    assert interpreted.right_name == baseline.name
    assert interpreted.incoming_text is None
    assert "INLINE MEMORY" not in interpreted.start_command


def test_meld_interpretation_returns_typed_launcher_routes() -> None:
    store = _InterpretationStore()

    assert isinstance(
        interpretation.interpret_meld_command(_request(), store=store),
        interpretation.MeldSetupCommand,
    )
    assert isinstance(
        interpretation.interpret_meld_command(
            _request(sessions=True),
            store=store,
        ),
        interpretation.MeldSessionsCommand,
    )
    assert store.current_reads == 0


def test_meld_interpretation_rejects_conflicting_raw_grammar() -> None:
    store = _InterpretationStore()

    with pytest.raises(
        interpretation.MeldCommandInterpretationError,
        match="both --into and --to",
    ):
        interpretation.interpret_meld_command(
            _request(left="incoming", into="baseline", to="other"),
            store=store,
        )


def test_meld_command_compatibility_assignment_reaches_owning_module(
    monkeypatch,
) -> None:
    def replacement():
        return object()

    monkeypatch.setattr(command, "connect_codex_chatgpt_provider", replacement)

    assert workflow.connect_codex_chatgpt_provider is replacement
    assert not hasattr(entrypoint, "connect_codex_chatgpt_provider")


def test_meld_workflow_has_no_direct_typer_output_dependency() -> None:
    assert not hasattr(workflow, "typer")
