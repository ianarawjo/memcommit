from __future__ import annotations

from typer.testing import CliRunner
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.cli import app
from memcommit.commands.review_report import (
    render_review_report_snapshot,
    run_review_report_shell,
)
from memcommit.resolution_workbench import (
    ResolutionItem,
    ResolutionOption,
    ResolutionWorkbenchView,
)
from memcommit.review_report import ReviewReportController
from memcommit.review_report_adapters import update_review_report
from memcommit.store import MemoryStore
from memcommit.update import (
    AddOperation,
    ContextFingerprint,
    SourceReference,
    UpdateSession,
)


runner = CliRunner(mix_stderr=False)


def _update_session() -> UpdateSession:
    digest = "a" * 64
    operation = AddOperation(
        owner_context_uid="c0d853a6-985e-574f-a921-7602a470d432",
        owner_context_name="task-1/campus-wiki/temporary-parking",
        memory_uid="7cdeee34-f97f-4e17-98b1-63e035735d5f",
        new_content=(
            "After the underground parking garage clear-out, personal items "
            "left there were moved to the lost and found center."
        ),
        source_refs=(
            SourceReference(
                context_uid="b392133c-278c-5c86-aaf9-5791ed5e9cd4",
                context_name=(
                    "task-1/participant/construction-updates/temporary-parking"
                ),
                memory_uid="8fa46317-ba39-54bb-8cf0-f85770bd5032",
                content_digest="b" * 64,
            ),
        ),
        reason="Adds the disposition of items left in the garage.",
    )
    return UpdateSession(
        uid="11111111-1111-4111-8111-111111111111",
        status="impact",
        created_at="2026-08-05T00:00:00+00:00",
        source_uid="22222222-2222-4222-8222-222222222222",
        source_name="task-1/participant/construction-updates",
        source_digest=digest,
        source_contexts=(
            ContextFingerprint(
                "22222222-2222-4222-8222-222222222222",
                "task-1/participant/construction-updates",
                digest,
            ),
        ),
        target_uid="33333333-3333-4333-8333-333333333333",
        target_name="task-1/campus-wiki",
        target_digest=digest,
        target_contexts=(
            ContextFingerprint(
                "33333333-3333-4333-8333-333333333333",
                "task-1/campus-wiki",
                digest,
            ),
        ),
        operations=(operation,),
    )


def test_review_report_removes_apply_but_retains_semantic_review_actions():
    view = ResolutionWorkbenchView(
        operation="MELD",
        artifact_uid="meld-uid",
        revision="revision-1",
        title="Meld",
        route="left + right → target",
        status="READY",
        metrics=(),
        overview="Reviewed proposal.",
        list_label="ISSUES",
        items=(),
        empty_message="No issues.",
        results_label="PROPOSALS",
        results=(),
        capabilities=frozenset({"SUBMIT_ALL", "ACCEPT"}),
        accept_enabled=True,
    )

    report = ReviewReportController.from_resolution(
        view,
        kind="RESOLUTION",
        title="MEM REVIEW · MELD",
        summary="Review without applying.",
    ).report()

    assert report.view is not None
    assert report.view.capabilities == frozenset({"SUBMIT_ALL"})
    assert report.view.accept_enabled is False


def test_update_existing_change_blocks_are_preserved_as_review_report():
    report = update_review_report(_update_session()).report()

    rendered = render_review_report_snapshot(report)

    assert "task-1/campus-wiki/temporary-parking Memory" in rendered
    assert "ADD 1 · ADD" not in rendered
    assert "OWNER" in rendered
    assert "MEMORY UID" in rendered
    assert "AFTER" in rendered
    assert "Adds the disposition of items left in the garage." in rendered
    assert "SOURCE REFERENCES" in rendered
    assert "8fa46317-ba39-54bb-8cf0-f85770bd5032" in rendered
    assert "REVIEW & APPLY" not in rendered
    assert "APPLY CHANGES" not in rendered


def test_mem_review_update_prints_saved_exact_change_report(isolated_store):
    session = _update_session()
    MemoryStore().save_impact_plan(session)

    result = runner.invoke(app, ["review", "update", "--snapshot"])

    assert result.exit_code == 0, result.output
    assert "MEM REVIEW · UPDATE" in result.output
    assert "task-1/campus-wiki/temporary-parking Memory" in result.output
    assert "ADD 1 · ADD" not in result.output
    assert "SOURCE REFERENCES" in result.output
    assert "REVIEW & APPLY" not in result.output
    assert "APPLY CHANGES" not in result.output


def test_review_host_cannot_turn_accept_key_into_apply():
    controller = update_review_report(_update_session())

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("aq")
        action = run_review_report_shell(
            controller,
            interactive_actions=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"


def test_adaptive_review_starts_in_viewer_and_opens_the_selected_item():
    view = ResolutionWorkbenchView(
        operation="ATOMIZE",
        artifact_uid="workbench-uid",
        revision="analysis-revision",
        title="Atomize",
        route="CONTEXT example",
        status="REVIEWING",
        metrics=(),
        overview="One ambiguity needs clarification.",
        list_label="ACTIONABLE ISSUES",
        items=(
            ResolutionItem(
                uid="finding-1",
                kind="ATOMIZE_UNCERTAINTY",
                status="OPEN",
                priority="REQUIRED",
                title="ATOMIZE UNCERTAINTY",
                summary="A referent is missing.",
                options=(
                    ResolutionOption(
                        uid="reading-1",
                        label="First reading",
                        text="Use the locally declared referent.",
                    ),
                ),
            ),
        ),
        empty_message="No issues.",
        results_label="EXACT RESULTS",
        results=(),
        capabilities=frozenset({"SUBMIT_ITEM"}),
        accept_enabled=False,
    )
    controller = ReviewReportController.from_resolution(
        view,
        kind="CLARIFICATION",
        title="MEM REVIEW · ATOMIZE",
        summary="Review without applying.",
    )

    with create_pipe_input() as pipe_input:
        # Tab moves from the initial Viewer to Items. Open the finding, Tab to
        # RESPONSES, choose the first reading, then submit its Response draft.
        pipe_input.send_text("\t\x1b[B\r\t\r\r\x1b\x1b[B\r\r")
        action = run_review_report_shell(
            controller,
            interactive_actions=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "SUBMIT_ITEM"
    assert action.item_uid == "finding-1"
    assert action.option_uid == "reading-1"
