"""Durable three-finder Audit orchestration, report, and Review contracts."""

from __future__ import annotations

from dataclasses import replace

import click
import pytest
from click.testing import CliRunner as ClickCliRunner
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
import memcommit.adapters.console.commands.audit.command as audit_command
from memcommit.adapters.console.commands.audit.receipt import (
    render_quality_audit_receipt,
)
from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.commands.audit.command import (
    _run_quality_audit_checks,
)
from memcommit.adapters.console.commands.audit.review import (
    quality_audit_review_document,
    render_quality_audit_review_snapshot,
    run_quality_audit_review,
)
from memcommit.adapters.console.commands.audit.session_catalog import (
    audit_session_entries,
)
from memcommit.adapters.console.terminal.components.quality_find.workbench import (
    QualityFindSetupReceipt,
    choose_quality_find_setup,
)
from memcommit.adapters.console.commands.review.sessions import review_session_entries
from memcommit.application.capabilities.memory_issue_analysis.model import (
    AmbiguityFinding,
    AmbiguityReport,
    ConflictFinding,
    ConflictReport,
    DuplicateFinding,
    DuplicateReport,
)
from memcommit.providers.types import CompletionRun, ProviderIdentity
from memcommit.adapters.console.terminal.core.theme import (
    SemanticColorRole,
    memory_object_color_rgb,
    semantic_color_rgb,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    semantic_role_style,
)
from memcommit.adapters.console.terminal.components.semantic_viewer import (
    semantic_document_plain_text,
)
from memcommit.application.operations.audit.application import (
    create_quality_audit,
    run_quality_audit,
)
from memcommit.application.operations.audit.model import (
    QUALITY_AUDIT_RULESETS,
    QUALITY_AUDIT_SCHEMA_VERSION,
    QualityAuditCheck,
    QualityAuditError,
    QualityAuditProvenance,
    QualityAuditSession,
    quality_audit_record_digest,
)
from memcommit.persistence.operations.audit import JsonAuditRecordRepository
from memcommit.persistence.store import MemoryStore


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
                            "The opening states cannot both hold.",
                            "Which time is authoritative?",
                        ),
                    ),
                ),
                _provenance("conflicts"),
            ),
        ),
    )


def test_audit_record_schema_contains_no_response_contract():
    ctx, first, second = _context()
    session = _finding_session(ctx, first, second)

    value = session.to_dict()

    assert value["schema_version"] == QUALITY_AUDIT_SCHEMA_VERSION == 1
    assert "responses" not in value
    assert not hasattr(session, "responses")


@pytest.mark.parametrize("schema_version", [2, 3])
def test_audit_rejects_undistributed_draft_schemas(schema_version):
    ctx, first, second = _context()
    value = _finding_session(ctx, first, second).to_dict()
    value["schema_version"] = schema_version
    value["responses"] = {}

    with pytest.raises(QualityAuditError, match="Unsupported Audit session schema"):
        QualityAuditSession.from_dict(value)


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

    assert receipt == QualityFindSetupReceipt(
        target_names=("audit/source",),
        context_names=("audit/source",),
        selection_mode="SINGLE",
        include_descendants=False,
    )


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


def test_audit_initial_checks_never_supply_a_full_screen_return_view(monkeypatch):
    ctx, _first, _second = _context()
    EmptyAuditProvider.calls = []
    stages: list[tuple[object, ...]] = []

    class Progress:
        def update(self, stage, *, step):
            stages.append(("UPDATE", stage, step))

    def wait(operation, stage, *, total, work, **kwargs):
        assert "return_view" not in kwargs
        stages.append(("WAIT", operation, stage, total))
        return work(Progress())

    monkeypatch.setattr(audit_command, "run_command_wait", wait)

    with create_pipe_input() as pipe_input:
        session = _run_quality_audit_checks(
            ctx,
            EmptyAuditProvider,
            app_input=pipe_input,
            app_output=DummyOutput(),
            interactive=True,
            interval=0.01,
            help_entries=(),
            on_help_action=lambda *_args: pytest.fail(
                "initial Audit must not enter full-screen Help"
            ),
        )

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
    assert stages == [
        ("WAIT", "AUDIT", "finding redundancies", 3),
        ("UPDATE", "finding redundancies", 1),
        ("UPDATE", "finding ambiguities", 2),
        ("UPDATE", "finding conflicts", 3),
    ]


def test_audit_review_is_one_complete_answer_free_document():
    ctx, first, second = _context()
    session = _finding_session(ctx, first, second)

    document = quality_audit_review_document(session)
    rendered = semantic_document_plain_text(
        document,
        focused_uid=None,
        whole_document=True,
    )

    assert "MEM AUDIT" in rendered
    assert "SAVED · 3/3 CHECKS · READ-ONLY REPORT" in rendered
    assert "SNAPSHOT ·" in rendered
    assert "SOURCE MEMORY 1/2" not in rendered
    assert first.content in rendered
    assert second.content in rendered
    assert "= DUPLICATE · SEMANTIC_EQUIVALENT" not in rendered
    assert "≈ REDUNDANT · SEMANTIC EQUIVALENT" in rendered
    assert "? UNDERSPECIFIED" in rendered
    assert "! CONFLICT" in rendered
    assert (
        "REDUNDANCIES · 2 MEMORIES CHECKED · 1 GROUP · 1 PROPOSED ABSORPTION"
    ) in rendered
    assert "AMBIGUITIES · 1/2 MEMORIES FLAGGED" in rendered
    assert "CONFLICTS · 2/2 MEMORIES INVOLVED · 1/1 PAIRS FLAGGED" in rendered
    assert "WHY THESE MEMORIES ARE SEMANTICALLY REDUNDANT" not in rendered
    assert "QUESTION · Which audience uses this schedule?" in rendered
    assert "QUESTION · Which time is authoritative?" in rendered
    assert "READINGS" not in rendered
    assert "RESPONSES" not in rendered
    assert "TO DO" not in rendered
    assert "[Enter] select" not in rendered
    assert [section.kind for section in document.sections] == [
        "OVERVIEW",
        "CHECK",
        "FINDING",
        "CHECK",
        "FINDING",
        "CHECK",
        "FINDING",
        "PROVENANCE",
        "BOUNDARY",
    ]
    assert all(section.kind != "SOURCE_MEMORY" for section in document.sections)
    assert all(section.kind != "SAVED_NOTE" for section in document.sections)
    assert document.sections[-1].kind == "BOUNDARY"
    check_fragments = [
        section.block.fragments
        for section in document.sections
        if section.kind == "CHECK"
    ]
    assert (
        semantic_role_style(SemanticColorRole.QUALITY_DUPLICATE),
        "REDUNDANCIES",
    ) in check_fragments[0]
    assert (
        semantic_role_style(SemanticColorRole.QUALITY_AMBIGUITY),
        "AMBIGUITIES",
    ) in check_fragments[1]
    assert (
        semantic_role_style(SemanticColorRole.QUALITY_CONFLICT),
        "CONFLICTS",
    ) in check_fragments[2]
    finding_sections = tuple(
        section for section in document.sections if section.kind == "FINDING"
    )
    for section, marker, role, label in zip(
        finding_sections,
        ("≈ ", "? ", "! "),
        (
            SemanticColorRole.QUALITY_DUPLICATE,
            SemanticColorRole.QUALITY_AMBIGUITY,
            SemanticColorRole.QUALITY_CONFLICT,
        ),
        ("REDUNDANT", "UNDERSPECIFIED", "CONFLICT"),
        strict=True,
    ):
        assert ("class:finding-marker", marker) in section.block.fragments
        resting_label_style = f"{semantic_role_style(role)} class:finding-label"
        focused_label_style = f"{semantic_role_style(role)} class:finding-label.focused"
        assert (resting_label_style, label) in section.block.fragments
        focused_fragments = section.block.render(active=True)
        assert ("class:finding-marker.focused", marker) in focused_fragments
        # Focus adds emphasis while the semantic class keeps category color.
        assert (focused_label_style, label) in focused_fragments


def test_audit_review_scrolls_each_finding_in_one_check_independently():
    ctx, first, second = _context()
    session = _finding_session(ctx, first, second)
    ambiguity_check = session.checks[1]
    assert isinstance(ambiguity_check.report, AmbiguityReport)
    second_finding = AmbiguityFinding(
        second,
        "SINGLE",
        "HELPFUL",
        ("The public entrance stays closed until 9:00.",),
        "The affected audience is not explicit.",
        "Which audience is affected?",
    )
    session = replace(
        session,
        checks=(
            session.checks[0],
            replace(
                ambiguity_check,
                report=replace(
                    ambiguity_check.report,
                    findings=ambiguity_check.report.findings + (second_finding,),
                ),
            ),
            session.checks[2],
        ),
    )

    document = quality_audit_review_document(session)
    ambiguity_sections = tuple(
        section
        for section in document.sections
        if section.uid.startswith("AUDIT:CHECK:ambiguities")
    )

    assert [section.kind for section in ambiguity_sections] == [
        "CHECK",
        "FINDING",
        "FINDING",
    ]
    assert first.content in "".join(
        text for _style, text in ambiguity_sections[1].block.fragments
    )
    assert second.content in "".join(
        text for _style, text in ambiguity_sections[2].block.fragments
    )
    focused = document.render(
        focused_uid=ambiguity_sections[2].uid,
        viewer_focused=True,
    )
    assert sum(style == "[SetCursorPosition]" for style, _text in focused) == 1


def test_audit_review_close_cannot_change_the_saved_record(isolated_store):
    ctx, first, second = _context()
    store = MemoryStore()
    session = _finding_session(ctx, first, second)
    sessions = JsonAuditRecordRepository(store)
    sessions.create(session)
    before = quality_audit_record_digest(sessions.load(session.uid))

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        returned = run_quality_audit_review(
            store,
            sessions.load(session.uid),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert quality_audit_record_digest(returned) == before
    assert quality_audit_record_digest(sessions.load(session.uid)) == before
    assert "RESPONSES" not in render_quality_audit_review_snapshot(returned)


def test_audit_store_rejects_replacing_an_immutable_record(isolated_store):
    ctx, first, second = _context()
    session = _finding_session(ctx, first, second)
    sessions = JsonAuditRecordRepository(MemoryStore())
    sessions.create(session)
    before = quality_audit_record_digest(sessions.load(session.uid))

    with pytest.raises(QualityAuditError, match="already exists"):
        sessions.create(session)

    assert quality_audit_record_digest(sessions.load(session.uid)) == before


def test_saved_audit_is_in_audit_and_aggregate_review_catalogs(isolated_store):
    ctx, first, second = _context()
    store = MemoryStore()
    session = _finding_session(ctx, first, second)
    sessions = JsonAuditRecordRepository(store)
    sessions.create(session)

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
    JsonAuditRecordRepository(MemoryStore()).create(session)

    result = runner.invoke(
        app,
        ["review", "audit", "--session", session.uid, "--snapshot"],
    )

    assert result.exit_code == 0
    assert "MEM AUDIT" in result.stdout
    assert "SAVED · 3/3 CHECKS" in result.stdout
    assert "REDUNDANCIES · FINISHED · 2 MEMORIES CHECKED" in result.stdout
    assert "AMBIGUITIES · FINISHED · 1/2 MEMORIES FLAGGED" in result.stdout
    assert "CONFLICTS · FINISHED · 2/2 MEMORIES INVOLVED" in result.stdout


def test_review_audit_snapshot_accepts_displayed_session_prefix(isolated_store):
    ctx, first, second = _context()
    session = _finding_session(ctx, first, second)
    JsonAuditRecordRepository(MemoryStore()).create(session)

    result = runner.invoke(
        app,
        ["review", "audit", "--session", session.uid[:8], "--snapshot"],
    )

    assert result.exit_code == 0, result.output
    assert f"SESSION [{session.uid[:8]}]" in result.stdout
    assert "SAVED · 3/3 CHECKS" in result.stdout


def test_review_audit_rejects_an_ambiguous_session_prefix(isolated_store):
    ctx, first, second = _context()
    original = _finding_session(ctx, first, second)
    sessions = JsonAuditRecordRepository(MemoryStore())
    sessions.create(replace(original, uid="aaaaaaaa-0000-4000-8000-000000000000"))
    sessions.create(replace(original, uid="aaaaaaaa-1111-4000-8000-000000000000"))

    result = runner.invoke(
        app,
        ["review", "audit", "--session", "aaaaaaaa", "--snapshot"],
    )

    assert result.exit_code == 1
    assert "matches 2 candidates" in result.output
    assert "pass a longer UID" in result.output


def test_audit_help_names_all_three_finders():
    result = runner.invoke(app, ["audit", "--help"])

    assert result.exit_code == 0
    output = result.stdout.casefold()
    assert "duplicate" in output
    assert "ambiguity" in output
    assert "conflict" in output


def test_audit_receipt_colors_only_quality_labels_and_preserves_plain_text():
    ctx, first, second = _context()
    session = _finding_session(ctx, first, second)

    @click.command()
    def receipt():
        render_quality_audit_receipt(session)

    colored = ClickCliRunner().invoke(receipt, color=True)
    plain = ClickCliRunner().invoke(receipt, color=False)
    no_color = ClickCliRunner().invoke(
        receipt,
        color=None,
        env={"NO_COLOR": "1"},
    )

    assert colored.exit_code == 0, colored.output
    assert plain.exit_code == 0, plain.output
    assert no_color.exit_code == 0, no_color.output
    assert click.unstyle(colored.output) == plain.output == no_color.output
    assert plain.output == (
        "Audit saved: 3 quality checks.\n"
        "Source: audit/source · 2 memories\n"
        "\n"
        "REDUNDANCIES   2 MEMORIES CHECKED · 1 GROUP · 1 PROPOSED ABSORPTION\n"
        f"  ≈ REDUNDANT · SEMANTIC EQUIVALENT · "
        f"[MEMORY {first.uid[:8]}] “{first.content}” ↔ "
        f"[MEMORY {second.uid[:8]}] “{second.content}”\n"
        "AMBIGUITIES    1/2 MEMORIES FLAGGED\n"
        f"  ? UNDERSPECIFIED · [MEMORY {first.uid[:8]}] “{first.content}” · "
        "WHY · The audience is not explicit. — The public entrance opens at 8:00. · "
        "QUESTION · Which audience uses this schedule?\n"
        "CONFLICTS      2/2 MEMORIES INVOLVED · 1/1 PAIRS FLAGGED\n"
        f"  ! CONFLICT · [MEMORY {first.uid[:8]}] “{first.content}” ↔ "
        f"[MEMORY {second.uid[:8]}] “{second.content}” · "
        "WHY · The opening states cannot both hold. · "
        "QUESTION · Which time is authoritative?\n"
        "\n"
        "Review full audit:\n"
        f"mem review audit --session {session.uid}\n"
    )
    for label, role in (
        ("REDUNDANCIES", SemanticColorRole.QUALITY_DUPLICATE),
        ("AMBIGUITIES", SemanticColorRole.QUALITY_AMBIGUITY),
        ("CONFLICTS", SemanticColorRole.QUALITY_CONFLICT),
    ):
        assert (
            click.style(
                label,
                fg=semantic_color_rgb(role),
                bold=True,
            )
            in colored.output
        )
    for label, role in (
        ("REDUNDANT", SemanticColorRole.QUALITY_DUPLICATE),
        ("UNDERSPECIFIED", SemanticColorRole.QUALITY_AMBIGUITY),
        ("CONFLICT", SemanticColorRole.QUALITY_CONFLICT),
    ):
        assert (
            click.style(
                label,
                fg=semantic_color_rgb(role),
                bold=True,
            )
            in colored.output
        )
    assert (
        click.style(
            f"“{first.content}”",
            fg=memory_object_color_rgb(),
        )
        in colored.output
    )
    assert "\x1b[" not in plain.output
    assert "\x1b[" not in no_color.output


def test_audit_receipt_previews_three_findings_then_reports_the_remainder():
    ctx = ops.init("audit/preview-limit")
    memories = tuple(ops.add(ctx, f"Preview Memory {index}.") for index in range(4))
    ambiguities = tuple(
        AmbiguityFinding(
            memory,
            "SINGLE",
            "HELPFUL",
            (f"Reading {index}.",),
            f"Reason {index}.",
            f"Question {index}?",
        )
        for index, memory in enumerate(memories)
    )
    session = create_quality_audit(
        ctx,
        (
            QualityAuditCheck(
                "duplicates",
                QUALITY_AUDIT_RULESETS["duplicates"],
                DuplicateReport(memory_count=4, findings=()),
                _provenance("duplicates"),
            ),
            QualityAuditCheck(
                "ambiguities",
                QUALITY_AUDIT_RULESETS["ambiguities"],
                AmbiguityReport(memory_count=4, findings=ambiguities),
                _provenance("ambiguities"),
            ),
            QualityAuditCheck(
                "conflicts",
                QUALITY_AUDIT_RULESETS["conflicts"],
                ConflictReport(memory_count=4, pair_count=6, findings=()),
                _provenance("conflicts"),
            ),
        ),
    )

    @click.command()
    def receipt():
        render_quality_audit_receipt(session)

    result = ClickCliRunner().invoke(receipt, color=False)

    assert result.exit_code == 0, result.output
    assert "AMBIGUITIES    4/4 MEMORIES FLAGGED" in result.output
    for memory in memories[:3]:
        assert memory.content in result.output
    assert memories[3].content not in result.output
    assert result.output.count("  … 1 more") == 1


def test_audit_receipt_preview_expands_colliding_memory_uid_prefixes():
    ctx, first, second = _context()
    first.uid = "a31f02c1-0000-4000-8000-000000000001"
    second.uid = "a31f02c1-0000-4000-8000-000000000002"
    session = _finding_session(ctx, first, second)

    @click.command()
    def receipt():
        render_quality_audit_receipt(session)

    result = ClickCliRunner().invoke(receipt, color=False)

    assert result.exit_code == 0, result.output
    assert f"[MEMORY {first.uid}]" in result.output
    assert f"[MEMORY {second.uid}]" in result.output


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
        "memcommit.adapters.console.commands.audit.command.connect_codex_chatgpt_provider",
        EmptyAuditProvider,
    )

    result = runner.invoke(
        app,
        ["audit", ctx.name, "--snapshot"],
    )

    assert result.exit_code == 0
    assert EmptyAuditProvider.calls == [
        "find_duplicates",
        "find_ambiguities",
        "find_conflicts",
    ]
    saved = JsonAuditRecordRepository(store).list()
    assert len(saved) == 1
    assert saved[0].source.context_name == ctx.name
    assert "SAVED · 3/3 CHECKS" in result.stdout


def test_flagless_audit_uses_current_context_and_prints_saved_session_receipt(
    isolated_store,
    monkeypatch,
):
    ctx, _first, _second = _context()
    store = MemoryStore()
    store.create_context(ctx)
    store.set_current(ctx.name)
    EmptyAuditProvider.calls = []
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.audit.command.connect_codex_chatgpt_provider",
        EmptyAuditProvider,
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.audit.command.choose_audit_setup",
        lambda *_args, **_kwargs: pytest.fail(
            "flagless Audit must not open Source setup"
        ),
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.audit.review.run_quality_audit_review",
        lambda *_args, **_kwargs: pytest.fail(
            "Audit execution must not open Review automatically"
        ),
    )

    result = runner.invoke(app, ["audit"])

    assert result.exit_code == 0, result.output
    assert "Audit saved: 3 quality checks." in result.output
    assert "Source: audit/source · 2 memories" in result.output
    assert (
        "REDUNDANCIES   2 MEMORIES CHECKED · 0 GROUPS · 0 PROPOSED ABSORPTIONS"
    ) in result.output
    assert "AMBIGUITIES    0/2 MEMORIES FLAGGED" in result.output
    assert "CONFLICTS      0/2 MEMORIES INVOLVED · 0/1 PAIRS FLAGGED" in result.output
    assert "Review full audit:\nmem review audit --session" in result.output
    assert "Source unchanged. No checkpoint created." not in result.output
    saved = JsonAuditRecordRepository(store).list()
    assert len(saved) == 1
    assert saved[0].source.context_name == ctx.name
