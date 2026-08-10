"""Durable three-finder Audit orchestration, report, and Review contracts."""

from __future__ import annotations

from dataclasses import replace
import threading

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.commands.audit import _AuditWaitState, _run_quality_audit_checks
from memcommit.commands.audit_sessions import audit_session_entries
from memcommit.commands.help_inventory import CommandEntry
from memcommit.commands.quality_find_workbench import (
    QualityFindSetupReceipt,
    choose_quality_find_setup,
)
from memcommit.commands.review_sessions import review_session_entries
from memcommit.findings import (
    AmbiguityFinding,
    AmbiguityReport,
    ConflictFinding,
    ConflictReport,
    DuplicateFinding,
    DuplicateReport,
)
from memcommit.provider_types import CompletionRun, ProviderIdentity
from memcommit.quality_audit import (
    QUALITY_AUDIT_RULESETS,
    QualityAuditCheck,
    QualityAuditProvenance,
    create_quality_audit,
    quality_audit_record_digest,
    quality_audit_resolution_view,
    run_quality_audit,
)
from memcommit.quality_audit_store import QualityAuditStore
from memcommit.store import ConcurrentContextUpdateError, MemoryStore


runner = CliRunner()


class EmptyAuditProvider:
    calls: list[str] = []

    def __init__(self):
        self.identity = ProviderIdentity(provider="test", model="audit-model")
        self.last_run = None

    def complete(self, _prompt, *, operation, output_schema=None):
        del output_schema
        self.calls.append(operation)
        self.last_run = CompletionRun(
            identity=self.identity,
            operation=operation,
            upstream_model="audit-model",
            upstream_provider="test",
        )
        return '{"findings": []}'


class HelpBlockingAuditProvider(EmptyAuditProvider):
    entered = threading.Event()
    help_opened = threading.Event()

    def complete(self, prompt, *, operation, output_schema=None):
        if operation == "find_duplicates":
            self.entered.set()
            if not self.help_opened.wait(3):
                raise RuntimeError("Help was not opened during Duplicate analysis.")
        return super().complete(
            prompt,
            operation=operation,
            output_schema=output_schema,
        )


def _context():
    ctx = ops.init("audit/source")
    first = ops.add(ctx, "The main entrance opens at 8:00.")
    second = ops.add(ctx, "The main entrance remains closed until 9:00.")
    return ctx, first, second


def _provenance(kind):
    return QualityAuditProvenance(
        operation=f"find_{kind}",
        provider_called=True,
        identity=ProviderIdentity(provider="test", model="audit-model"),
    )


def _finding_session(ctx, first, second):
    return create_quality_audit(
        ctx,
        (
            QualityAuditCheck(
                "duplicates",
                QUALITY_AUDIT_RULESETS["duplicates"],
                DuplicateReport(
                    memory_count=2,
                    findings=(
                        DuplicateFinding(
                            first,
                            second,
                            "SEMANTIC_EQUIVALENT",
                            "The two Memories are substitutable.",
                        ),
                    ),
                ),
                _provenance("duplicates"),
            ),
            QualityAuditCheck(
                "ambiguities",
                QUALITY_AUDIT_RULESETS["ambiguities"],
                AmbiguityReport(
                    memory_count=2,
                    findings=(
                        AmbiguityFinding(
                            first,
                            "SINGLE",
                            "HELPFUL",
                            ("The public entrance opens at 8:00.",),
                            "The audience is not explicit.",
                            "Which audience uses this schedule?",
                        ),
                    ),
                ),
                _provenance("ambiguities"),
            ),
            QualityAuditCheck(
                "conflicts",
                QUALITY_AUDIT_RULESETS["conflicts"],
                ConflictReport(
                    memory_count=2,
                    pair_count=1,
                    findings=(
                        ConflictFinding(
                            first,
                            second,
                            "YES",
                            ("TIME",),
                            "The opening states cannot both hold.",
                            "Which time is authoritative?",
                        ),
                    ),
                ),
                _provenance("conflicts"),
            ),
        ),
    )


def test_audit_setup_is_one_context_and_one_run_action():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\r")
        receipt = choose_quality_find_setup(
            ("audit/source",),
            current="audit/source",
            kind="audit",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt == QualityFindSetupReceipt("audit/source")


def test_run_quality_audit_calls_all_three_independent_finders_once():
    ctx, _first, _second = _context()
    EmptyAuditProvider.calls = []
    stages = []

    session = run_quality_audit(
        ctx,
        EmptyAuditProvider,
        on_check=lambda kind, step, total: stages.append((kind, step, total)),
    )

    assert EmptyAuditProvider.calls == [
        "find_duplicates",
        "find_ambiguities",
        "find_conflicts",
    ]
    assert stages == [
        ("duplicates", 1, 3),
        ("ambiguities", 2, 3),
        ("conflicts", 3, 3),
    ]
    assert [check.kind for check in session.checks] == [
        "duplicates",
        "ambiguities",
        "conflicts",
    ]
    assert all(check.report.memory_count == 2 for check in session.checks)
    assert all(
        check.provenance.identity.model == "audit-model" for check in session.checks
    )


def _wait_lines(state: _AuditWaitState) -> list[str]:
    text = "".join(fragment[1] for fragment in state.render(0))
    return [
        line
        for line in text.splitlines()
        if line.startswith(("1.", "2.", "3."))
    ]


def test_audit_wait_accumulates_all_three_checks_on_one_screen():
    state = _AuditWaitState(context_name="audit/source", memory_count=2)

    assert [line.rsplit("·", 1)[1].strip() for line in _wait_lines(state)] == [
        "WAITING",
        "WAITING",
        "WAITING",
    ]

    state.begin("duplicates", 1, 3)
    assert [line.rsplit("·", 1)[1].strip() for line in _wait_lines(state)] == [
        "RUNNING .",
        "WAITING",
        "WAITING",
    ]

    state.begin("ambiguities", 2, 3)
    assert [line.rsplit("·", 1)[1].strip() for line in _wait_lines(state)] == [
        "COMPLETE",
        "RUNNING .",
        "WAITING",
    ]

    state.begin("conflicts", 3, 3)
    assert [line.rsplit("·", 1)[1].strip() for line in _wait_lines(state)] == [
        "COMPLETE",
        "COMPLETE",
        "RUNNING .",
    ]

    state.complete()
    assert [line.rsplit("·", 1)[1].strip() for line in _wait_lines(state)] == [
        "COMPLETE",
        "COMPLETE",
        "COMPLETE",
    ]
    assert state.view().title == "AUDIT CHECKS · 1 → 2 → 3"


def test_audit_wait_h_opens_help_without_restarting_finders():
    ctx, _first, _second = _context()
    EmptyAuditProvider.calls = []
    HelpBlockingAuditProvider.entered = threading.Event()
    HelpBlockingAuditProvider.help_opened = threading.Event()
    result_ready = threading.Event()
    actions: list[tuple[str, str | None]] = []

    def observe(action: str, command_name: str | None) -> None:
        actions.append((action, command_name))
        if action == "OPEN":
            HelpBlockingAuditProvider.help_opened.set()
        elif action == "RESULT_READY":
            result_ready.set()

    help_entries = (
        CommandEntry(
            name="audit",
            annotation=None,
            description="Run all three Memory quality finders.",
            command=object(),
            forms=("mem audit", "mem audit --context NAME"),
        ),
    )

    with create_pipe_input() as pipe_input:
        def drive_terminal() -> None:
            if not HelpBlockingAuditProvider.entered.wait(3):
                pipe_input.send_text("\x03")
                return
            pipe_input.send_text("h")
            if not result_ready.wait(3):
                pipe_input.send_text("\x03")
                return
            # Completion does not dismiss Help; H returns to the ready Audit.
            pipe_input.send_text("h")

        driver = threading.Thread(target=drive_terminal, daemon=True)
        driver.start()
        session = _run_quality_audit_checks(
            ctx,
            HelpBlockingAuditProvider,
            app_input=pipe_input,
            app_output=DummyOutput(),
            interactive=True,
            interval=0.01,
            help_entries=help_entries,
            on_help_action=observe,
        )
        driver.join(timeout=3)

    assert not driver.is_alive()
    assert [check.kind for check in session.checks] == [
        "duplicates",
        "ambiguities",
        "conflicts",
    ]
    assert EmptyAuditProvider.calls == [
        "find_duplicates",
        "find_ambiguities",
        "find_conflicts",
    ]
    assert ("OPEN", None) in actions
    assert ("RESULT_READY", None) in actions


def test_audit_report_keeps_three_sections_and_type_specific_items():
    ctx, first, second = _context()
    session = _finding_session(ctx, first, second)

    view = quality_audit_resolution_view(session)

    assert [metric.label for metric in view.metrics] == [
        "SOURCE MEMORIES",
        "DUPLICATES",
        "AMBIGUITIES",
        "CONFLICTS",
    ]
    assert [metric.value for metric in view.metrics] == ["2", "1", "1", "1"]
    assert [item.kind for item in view.items] == [
        "DUPLICATE",
        "AMBIGUITY",
        "CONFLICT",
    ]
    assert "DUPLICATES · COMPLETE · 1 finding" in view.overview
    assert "AMBIGUITIES · COMPLETE · 1 finding" in view.overview
    assert "CONFLICTS · COMPLETE · 1 finding" in view.overview
    assert "not proof" in view.overview


def test_audit_store_preserves_snapshot_while_saving_review_response(isolated_store):
    ctx, first, second = _context()
    session = _finding_session(ctx, first, second)
    sessions = QualityAuditStore(MemoryStore())
    sessions.save(session, expected_digest=None)
    original_snapshot = session.snapshot_digest
    expected = quality_audit_record_digest(session)
    item = quality_audit_resolution_view(session).items[0]
    response = session.response_for(item.uid)
    response.selected_option_uid = item.options[0].uid
    response.text = "Keep this duplicate evidence."

    sessions.save(session, expected_digest=expected)
    restored = sessions.load(session.uid)

    assert restored.snapshot_digest == original_snapshot
    assert restored.response_for(item.uid).text == "Keep this duplicate evidence."

    ambiguity_report = session.checks[1].report
    assert isinstance(ambiguity_report, AmbiguityReport)
    altered_check = replace(
        session.checks[1],
        report=replace(
            ambiguity_report,
            findings=(
                replace(
                    ambiguity_report.findings[0],
                    reason="A replaced provider result.",
                ),
            ),
        ),
    )
    session.checks = (session.checks[0], altered_check, session.checks[2])
    with pytest.raises(
        ConcurrentContextUpdateError,
        match="immutable Audit snapshot",
    ):
        sessions.save(
            session,
            expected_digest=quality_audit_record_digest(restored),
        )


def test_saved_audit_is_in_audit_and_aggregate_review_catalogs(isolated_store):
    ctx, first, second = _context()
    store = MemoryStore()
    session = _finding_session(ctx, first, second)
    sessions = QualityAuditStore(store)
    sessions.save(session, expected_digest=None)

    audit_entries = audit_session_entries(sessions)
    review_entries = review_session_entries(store)

    assert [(entry.kind, entry.key) for entry in audit_entries] == [
        ("audit", session.uid)
    ]
    assert ("audit", session.uid) in {
        (entry.kind, entry.key) for entry in review_entries
    }


def test_review_audit_snapshot_reopens_exact_saved_report(isolated_store):
    ctx, first, second = _context()
    session = _finding_session(ctx, first, second)
    QualityAuditStore(MemoryStore()).save(session, expected_digest=None)

    result = runner.invoke(
        app,
        ["review", "audit", "--session", session.uid, "--snapshot"],
    )

    assert result.exit_code == 0
    assert "MEM AUDIT" in result.stdout
    assert "SAVED · 3/3 CHECKS" in result.stdout
    assert "DUPLICATES · COMPLETE · 1 finding" in result.stdout
    assert "AMBIGUITIES · COMPLETE · 1 finding" in result.stdout
    assert "CONFLICTS · COMPLETE · 1 finding" in result.stdout


def test_audit_help_names_all_three_finders():
    result = runner.invoke(app, ["audit", "--help"])

    assert result.exit_code == 0
    output = result.stdout.casefold()
    assert "duplicate" in output
    assert "ambiguity" in output
    assert "conflict" in output


def test_audit_command_runs_all_three_and_saves_before_snapshot(
    isolated_store,
    monkeypatch,
):
    ctx, _first, _second = _context()
    store = MemoryStore()
    store.create_context(ctx)
    store.set_current(ctx.name)
    EmptyAuditProvider.calls = []
    monkeypatch.setattr(
        "memcommit.commands.audit.connect_codex_chatgpt_provider",
        EmptyAuditProvider,
    )

    result = runner.invoke(
        app,
        ["audit", "--context", ctx.name, "--snapshot"],
    )

    assert result.exit_code == 0
    assert EmptyAuditProvider.calls == [
        "find_duplicates",
        "find_ambiguities",
        "find_conflicts",
    ]
    saved = QualityAuditStore(store).list()
    assert len(saved) == 1
    assert saved[0].source.context_name == ctx.name
    assert "SAVED · 3/3 CHECKS" in result.stdout
