"""Characterize Atomize's operation-owned structural Apply boundary.

These tests exercise the typed application/runtime junction together with its
command adapter. They freeze Atomize's operation-owned no-op decision and the
receipt compensation, late-success, interrupted recovery, and CAS boundaries.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import typer
import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.operations.atomize.application import atomize_application_audit
from memcommit.operations.atomize.runtime import (
    MemoryStoreAtomizeSessionRepository,
    MemoryStoreAtomizeOutputPort,
    capture_atomize_session_snapshot,
)
from memcommit.atomize_workflow import open_or_create_atomize_workbench
from memcommit.commands.atomize.command import cmd as atomize_command
from memcommit.context import AutoCheckpoint, Memory
from memcommit.provenance import build_trace
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
        if operation == "find_duplicates":
            return json.dumps({"findings": []})
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


class _OneCompositeProvider:
    """Split one exact two-clause Memory with grounded child evidence."""

    def complete(self, prompt, *, operation, output_schema=None):
        if operation == "find_duplicates":
            return json.dumps({"findings": []})
        assert operation == "impact_atomize"
        assert output_schema is not None
        payload = json.loads(prompt.split(_PAYLOAD_MARKER, 1)[1])
        candidate_id = payload["memories"][0]["candidate_id"]
        if payload.get("phase") == "normal_form_validation":
            return _AllAtomicProvider().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )
        return json.dumps(
            {
                "overview": {
                    "understood": {
                        "text": "The Memory contains two independent facts.",
                        "source_ids": [candidate_id],
                    },
                    "changed": {
                        "text": "The two facts become separate Memories.",
                        "source_ids": [candidate_id],
                    },
                    "unresolved": {"text": "", "source_ids": []},
                },
                "items": [
                    {
                        "candidate_id": candidate_id,
                        "classification": "COMPOSITE",
                        "reason_codes": ["A01_ONE_FOCUS"],
                        "children": [
                            {
                                "content": "The library closes at five.",
                                "source_spans": ["The library closes at five"],
                            },
                            {
                                "content": "Security remains on site.",
                                "source_spans": ["Security remains on site"],
                            },
                        ],
                        "reason": "Each clause can be revised independently.",
                    }
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


@pytest.fixture(autouse=True)
def _normal_form_provider(monkeypatch):
    monkeypatch.setattr(
        "memcommit.commands.atomize.command.connect_codex_chatgpt_provider",
        _AllAtomicProvider,
    )


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
    assert "ATOMIZE APPLIED · atomize/apply-boundary" in applied.output
    assert "EFFECTS · SPLIT 0 · CHILDREN 0 · KEEP 1" in applied.output
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


def test_receipt_save_failure_publishes_no_partial_structural_apply(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context, _memory, opened = _open_all_atomic_session(store)
    context_before = store._context_file(context.name).read_bytes()
    history_before = store.list_checkpoints(context.name)
    original_save = MemoryStore._save_atomize_workbench_locked

    def reject_terminal_receipt(self, session):
        if session.application is not None:
            raise OSError("injected terminal receipt failure")
        return original_save(self, session)

    monkeypatch.setattr(
        MemoryStore,
        "_save_atomize_workbench_locked",
        reject_terminal_receipt,
    )

    failed = runner.invoke(
        app,
        ["atomize", "--context", context.name, "--save"],
    )

    assert failed.exit_code == 1
    assert "injected terminal receipt failure" in failed.stderr
    assert store._context_file(context.name).read_bytes() == context_before
    assert store.list_checkpoints(context.name) == history_before
    retained = store.load_atomize_workbench(opened.analysis)
    assert retained is not None and retained.application is None


def test_late_committed_terminal_receipt_is_reported_as_success(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context, _memory, opened = _open_all_atomic_session(store)
    original_save = MemoryStore._save_atomize_workbench_locked

    def commit_then_report_failure(self, session):
        result = original_save(self, session)
        if session.application is not None:
            raise OSError("injected late receipt failure")
        return result

    monkeypatch.setattr(
        MemoryStore,
        "_save_atomize_workbench_locked",
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


def test_retry_recovers_terminal_receipt_from_exact_atomize_checkpoint(
    isolated_store,
):
    store = MemoryStore()
    context, _memory, opened = _open_all_atomic_session(store)
    snapshot = capture_atomize_session_snapshot(
        store=store,
        analysis=opened.analysis,
        expected_workbench=opened.workbench,
    )
    materialized = MemoryStoreAtomizeOutputPort(
        store,
        provider_factory=_AllAtomicProvider,
    ).materialize(
        snapshot,
        atomize_application_audit(snapshot.analysis, snapshot.workbench),
    )
    assert materialized.created
    history = store.list_checkpoints(context.name)
    assert len(history) == 1 and history[0]["command"] == "atomize"
    interrupted = store.load_atomize_workbench(opened.analysis)
    assert interrupted is not None and interrupted.application is None

    retried = runner.invoke(
        app,
        ["atomize", "--context", context.name, "--save"],
    )

    assert retried.exit_code == 0, retried.output
    assert "RECOVERY STATUS · prior checkpoint recovered" in retried.output
    terminal = store.load_atomize_workbench(opened.analysis)
    assert terminal is not None and terminal.application is not None
    assert terminal.application.checkpoint_uid == history[0]["uid"]
    assert store.list_checkpoints(context.name) == history


def test_save_as_publishes_one_final_checkpoint_and_restores_one_lifecycle(
    isolated_store,
):
    store = MemoryStore()
    source, memory, opened = _open_all_atomic_session(store)
    source_record = store.load_direct(source.name).to_dict()

    applied = runner.invoke(
        app,
        ["atomize", "--context", source.name, "--save-as", "atomize/output"],
    )

    assert applied.exit_code == 0, applied.output
    assert "ATOMIZE APPLIED · atomize/output" in applied.output
    assert "CONTEXT · CREATED AND CURRENT · atomize/output" in applied.output
    output = store.load_direct("atomize/output")
    output_record = output.to_dict()
    assert output.uid != source.uid
    assert [item.uid for item in output.iter_items() if isinstance(item, Memory)] == [
        memory.uid
    ]
    checkpoints = store.list_checkpoints(output.name)
    assert [checkpoint["command"] for checkpoint in checkpoints] == ["atomize"]
    checkpoint_uid = checkpoints[0]["uid"]
    assert store.load_direct(source.name).to_dict() == source_record
    assert store.current_context_name() == output.name
    trace = build_trace(store, output, memory.uid)
    assert [event.kind for event in trace.events] == [
        "CREATED",
        "ATOMIZE_KEEP",
    ]
    assert all(event.evidence == "RECORDED" for event in trace.events)
    assert not trace.warnings

    undone = store.restore_recent_context_command("undo")

    assert undone.unit.command == "atomize"
    assert not store.context_exists(output.name)
    assert store.current_context_name() == source.name
    reviewing = store.load_atomize_workbench(opened.analysis)
    assert reviewing is not None and reviewing.application is None

    redone = store.restore_recent_context_command("redo")

    assert redone.unit.uid == undone.unit.uid
    assert store.load_direct(output.name).to_dict() == output_record
    assert store.current_context_name() == output.name
    terminal = store.load_atomize_workbench(opened.analysis)
    assert terminal is not None and terminal.application is not None
    assert terminal.application.checkpoint_uid == checkpoint_uid
    assert [
        checkpoint["command"]
        for checkpoint in store.list_checkpoints(output.name)[:3]
    ] == ["redo", "undo", "atomize"]


def test_save_as_prepublication_failure_leaves_no_context_or_hidden_analysis(
    isolated_store,
    monkeypatch,
):
    from memcommit.atomize import AtomizeImpactError

    store = MemoryStore()
    source, _memory, _opened = _open_all_atomic_session(store)
    analysis_paths = set(store.atomize_analyses_dir.glob("*.json"))

    def reject_apply(*_args, **_kwargs):
        raise AtomizeImpactError("injected prepublication failure")

    monkeypatch.setattr(
        "memcommit.atomize_normal_form.apply_atomize_analysis",
        reject_apply,
    )

    failed = runner.invoke(
        app,
        ["atomize", "--context", source.name, "--save-as", "atomize/failed"],
    )

    assert failed.exit_code == 1
    assert "injected prepublication failure" in failed.stderr
    assert not store.context_exists("atomize/failed")
    assert set(store.atomize_analyses_dir.glob("*.json")) == analysis_paths
    assert store.current_context_name() == source.name


def test_save_as_trace_uses_recorded_nonpublished_source_frame_for_split(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("atomize/split-source")
    original = ops.add(
        source,
        "The library closes at five. Security remains on site.",
    )
    store.save(source)
    store.set_current(source.name)
    open_or_create_atomize_workbench(
        store=store,
        ctx=source,
        provider_factory=_OneCompositeProvider,
    )

    applied = runner.invoke(
        app,
        ["atomize", "--context", source.name, "--save-as", "atomize/split-output"],
    )

    assert applied.exit_code == 0, applied.output
    output = store.load_direct("atomize/split-output")
    children = [item for item in output.iter_items() if isinstance(item, Memory)]
    assert [item.content for item in children] == [
        "The library closes at five.",
        "Security remains on site.",
    ]
    trace = build_trace(store, output, children[0].uid)
    assert trace.component_uids == tuple(
        sorted((original.uid, children[0].uid, children[1].uid))
    )
    assert [event.kind for event in trace.events] == ["CREATED", "SPLIT"]
    assert all(event.evidence == "RECORDED" for event in trace.events)
    assert not trace.warnings


def test_save_as_retry_finishes_source_receipt_without_second_checkpoint(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source, _memory, opened = _open_all_atomic_session(store)
    original = MemoryStoreAtomizeSessionRepository.replace_application
    failed_once = False

    def reject_once(repository, *args, **kwargs):
        nonlocal failed_once
        if not failed_once:
            failed_once = True
            raise OSError("injected Save As receipt failure")
        return original(repository, *args, **kwargs)

    monkeypatch.setattr(
        MemoryStoreAtomizeSessionRepository,
        "replace_application",
        reject_once,
    )

    failed = runner.invoke(
        app,
        ["atomize", "--context", source.name, "--save-as", "atomize/retry"],
    )

    assert failed.exit_code == 1
    assert "retained" in failed.stderr
    checkpoints = store.list_checkpoints("atomize/retry")
    assert [checkpoint["command"] for checkpoint in checkpoints] == ["atomize"]
    reviewing = store.load_atomize_workbench(opened.analysis)
    assert reviewing is not None and reviewing.application is None

    retried = runner.invoke(
        app,
        ["atomize", "--context", source.name, "--save-as", "atomize/retry"],
    )

    assert retried.exit_code == 0, retried.output
    assert "RECOVERY STATUS · prior checkpoint recovered" in retried.output
    assert store.list_checkpoints("atomize/retry") == checkpoints
    terminal = store.load_atomize_workbench(opened.analysis)
    assert terminal is not None and terminal.application is not None
    assert terminal.application.checkpoint_uid == checkpoints[0]["uid"]


def test_receipt_recovery_does_not_overwrite_later_context_edits(
    isolated_store,
):
    store = MemoryStore()
    context, _memory, opened = _open_all_atomic_session(store)
    snapshot = capture_atomize_session_snapshot(
        store=store,
        analysis=opened.analysis,
        expected_workbench=opened.workbench,
    )
    materialized = MemoryStoreAtomizeOutputPort(
        store,
        provider_factory=_AllAtomicProvider,
    ).materialize(
        snapshot,
        atomize_application_audit(snapshot.analysis, snapshot.workbench),
    )
    assert materialized.created

    changed = store.load_for_update(context.name)
    ops.add(changed, "Security remains on site after five.")
    store.save(
        changed,
        AutoCheckpoint(
            command="add",
            args={"content": "Security remains on site after five."},
            description="Added a later fact",
        ),
    )
    context_before_recovery = store._context_file(context.name).read_bytes()
    history_before_recovery = store.list_checkpoints(context.name)

    recovered = runner.invoke(
        app,
        ["atomize", "--context", context.name, "--save"],
    )

    assert recovered.exit_code == 0, recovered.output
    assert "RECOVERY STATUS · prior checkpoint recovered" in recovered.output
    assert store._context_file(context.name).read_bytes() == context_before_recovery
    assert store.list_checkpoints(context.name) == history_before_recovery
    terminal = store.load_atomize_workbench(opened.analysis)
    assert terminal is not None and terminal.application is not None
    assert terminal.application.checkpoint_uid == materialized.checkpoint_uid


def test_workbench_race_after_context_save_compensates_the_exact_checkpoint(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context, _memory, opened = _open_all_atomic_session(store)
    context_before = store._context_file(context.name).read_bytes()
    history_before = store.list_checkpoints(context.name)
    original_save = MemoryStore._save_command_locked

    def save_then_revise_workbench(self, *args, **kwargs):
        checkpoint = original_save(self, *args, **kwargs)
        auto_checkpoint = args[1] if len(args) > 1 else None
        if auto_checkpoint is not None and auto_checkpoint.command == "atomize":
            latest_analysis = self.load_atomize_analysis(context.uid)
            assert latest_analysis is not None
            latest = self.load_atomize_workbench(latest_analysis)
            assert latest is not None
            latest.toggle_sort()
            self.save_atomize_workbench(latest)
        return checkpoint

    monkeypatch.setattr(
        MemoryStore,
        "_save_command_locked",
        save_then_revise_workbench,
    )

    raced = runner.invoke(
        app,
        ["atomize", "--context", context.name, "--save"],
    )

    assert raced.exit_code == 1
    assert "session changed" in raced.stderr
    assert "rolled back" in raced.stderr
    assert store._context_file(context.name).read_bytes() == context_before
    assert store.list_checkpoints(context.name) == history_before
    revised = store.load_atomize_workbench(opened.analysis)
    assert revised is not None
    assert revised.application is None
    assert revised.sort_mode != opened.workbench.sort_mode


def test_atomize_application_and_runtime_do_not_import_terminal_adapters():
    root = Path(__file__).resolve().parents[1]
    forbidden = ("typer", "prompt_toolkit", "memcommit.commands")
    for relative in (
        "memcommit/operations/atomize/application.py",
        "memcommit/operations/atomize/runtime.py",
    ):
        tree = ast.parse((root / relative).read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imports.append(node.module)
        assert not [
            name
            for name in imports
            if any(name == item or name.startswith(f"{item}.") for item in forbidden)
        ]
