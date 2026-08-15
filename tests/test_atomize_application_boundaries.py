"""Characterize Atomize's structural Apply boundary before extraction.

These tests intentionally exercise the current command-owned junction.  The
passing case freezes an operation-owned no-op decision.  Strict xfails state
the receipt/recovery contract that the future application slice must satisfy;
they must be removed, not silently converted into compatibility behavior,
when that slice is implemented.
"""

from __future__ import annotations

import json

import pytest
import typer
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.atomize_workflow import open_or_create_atomize_workbench
from memcommit.commands.atomize import cmd as atomize_command
from memcommit.context import Memory
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)
app = typer.Typer()


@app.callback()
def _test_root() -> None:
    """Keep Atomize as a subcommand without importing the full CLI graph."""


app.command("atomize")(atomize_command)
_PAYLOAD_MARKER = "ATOMIZE IMPACT PAYLOAD:\n"


class _AllAtomicProvider:
    """Return one exhaustive, decision-free Atomize assessment."""

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "impact_atomize"
        assert output_schema is not None
        payload = json.loads(prompt.split(_PAYLOAD_MARKER, 1)[1])
        candidate_ids = [item["candidate_id"] for item in payload["memories"]]
        return json.dumps(
            {
                "overview": {
                    "understood": {
                        "text": "Each supplied Memory states one independent fact.",
                        "source_ids": candidate_ids,
                    },
                    "changed": {
                        "text": "No Memory needs to be split.",
                        "source_ids": candidate_ids,
                    },
                    "unresolved": {"text": "", "source_ids": []},
                },
                "items": [
                    {
                        "candidate_id": candidate_id,
                        "classification": "ATOMIC",
                        "reason_codes": ["A01_ONE_FOCUS"],
                        "children": [],
                        "reason": (
                            "The source has one independently revisable focus."
                        ),
                    }
                    for candidate_id in candidate_ids
                ],
                "quality_issues": [],
            }
        )


def _open_all_atomic_session(store: MemoryStore):
    context = ops.init("atomize/apply-boundary")
    memory = ops.add(context, "The library entrance closes at five.")
    store.save(context)
    store.set_current(context.name)
    opened = open_or_create_atomize_workbench(
        store=store,
        ctx=context,
        provider_factory=_AllAtomicProvider,
    )
    return context, memory, opened


def test_all_atomic_apply_records_a_deliberate_no_change_checkpoint(
    isolated_store,
):
    """Atomize completion is recorded even when every Memory is preserved."""

    store = MemoryStore()
    context, memory, opened = _open_all_atomic_session(store)
    before = store.load_direct(context.name).to_dict()
    history_before = store.list_checkpoints(context.name)

    applied = runner.invoke(
        app,
        ["atomize", "--context", context.name, "--save"],
    )

    assert applied.exit_code == 0, applied.output
    assert "0 splits -> 0 children" in applied.output
    assert "1 Memories preserved in place" in applied.output
    current = store.load_direct(context.name)
    assert current.to_dict() == before
    assert [item.uid for item in current.iter_items() if isinstance(item, Memory)] == [
        memory.uid
    ]
    history = store.list_checkpoints(context.name)
    assert len(history) == len(history_before) + 1
    assert history[0]["command"] == "atomize"
    assert history[0]["args"]["split_count"] == 0
    assert history[0]["args"]["preserved_count"] == 1
    terminal = store.load_atomize_workbench(opened.analysis)
    assert terminal is not None
    assert terminal.application is not None
    assert terminal.application.checkpoint_uid == history[0]["uid"]

    repeated = runner.invoke(
        app,
        ["atomize", "--context", context.name, "--save"],
    )
    assert repeated.exit_code == 0, repeated.output
    assert "already applied" in repeated.output
    assert store.list_checkpoints(context.name) == history


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Atomize structural Apply does not yet compensate its Context "
        "checkpoint when the terminal workbench receipt cannot be saved."
    ),
)
def test_receipt_save_failure_publishes_no_partial_structural_apply(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context, _memory, opened = _open_all_atomic_session(store)
    context_before = store._context_file(context.name).read_bytes()
    history_before = store.list_checkpoints(context.name)
    original_save = MemoryStore.save_atomize_workbench

    def reject_terminal_receipt(self, session):
        if session.application is not None:
            raise OSError("injected terminal receipt failure")
        return original_save(self, session)

    monkeypatch.setattr(
        MemoryStore,
        "save_atomize_workbench",
        reject_terminal_receipt,
    )

    failed = runner.invoke(
        app,
        ["atomize", "--context", context.name, "--save"],
    )

    assert failed.exit_code == 1
    assert "injected terminal receipt failure" in failed.output
    assert store._context_file(context.name).read_bytes() == context_before
    assert store.list_checkpoints(context.name) == history_before
    retained = store.load_atomize_workbench(opened.analysis)
    assert retained is not None and retained.application is None


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Atomize structural Apply does not yet re-read a terminal workbench "
        "receipt after an atomic save commits and then reports failure."
    ),
)
def test_late_committed_terminal_receipt_is_reported_as_success(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context, _memory, opened = _open_all_atomic_session(store)
    original_save = MemoryStore.save_atomize_workbench

    def commit_then_report_failure(self, session):
        result = original_save(self, session)
        if session.application is not None:
            raise OSError("injected late receipt failure")
        return result

    monkeypatch.setattr(
        MemoryStore,
        "save_atomize_workbench",
        commit_then_report_failure,
    )

    applied = runner.invoke(
        app,
        ["atomize", "--context", context.name, "--save"],
    )

    assert applied.exit_code == 0, applied.output
    terminal = store.load_atomize_workbench(opened.analysis)
    assert terminal is not None and terminal.application is not None
    assert len(store.list_checkpoints(context.name)) == 1


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Atomize recognizes an existing checkpoint as applied but does not "
        "yet recover the missing Source-owned terminal workbench receipt."
    ),
)
def test_retry_recovers_terminal_receipt_from_exact_atomize_checkpoint(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context, _memory, opened = _open_all_atomic_session(store)
    original_save = MemoryStore.save_atomize_workbench

    def reject_terminal_receipt(self, session):
        if session.application is not None:
            raise OSError("injected interrupted Apply")
        return original_save(self, session)

    with monkeypatch.context() as patch:
        patch.setattr(
            MemoryStore,
            "save_atomize_workbench",
            reject_terminal_receipt,
        )
        failed = runner.invoke(
            app,
            ["atomize", "--context", context.name, "--save"],
        )
    assert failed.exit_code == 1
    history = store.list_checkpoints(context.name)
    assert len(history) == 1 and history[0]["command"] == "atomize"

    retried = runner.invoke(
        app,
        ["atomize", "--context", context.name, "--save"],
    )

    assert retried.exit_code == 0, retried.output
    terminal = store.load_atomize_workbench(opened.analysis)
    assert terminal is not None and terminal.application is not None
    assert terminal.application.checkpoint_uid == history[0]["uid"]
    assert store.list_checkpoints(context.name) == history
