"""Compact operation-oriented ``mem trace`` presentation contracts."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.commands.trace import command as trace_command
from memcommit.adapters.console.commands.trace import projection as trace_projection
from memcommit.adapters.console.commands.trace.projection import (
    format_compact_trace_report,
    trace_document_fragments,
)
from memcommit.adapters.interfaces.tui.components.plain_text_clipboard import (
    plain_text_from_fragments,
)
from memcommit.core.context_targeting.report_items import ResolvedMemoryReportTarget
from memcommit.application.retained_history.memory_history_reconstruction.retained_record_verification import (
    MemoryHistoryCommandContext,
    MemoryHistoryContextTransition,
    MemoryState,
)
from memcommit.application.retained_history.memory_history_reconstruction.memory_history_event_derivation import (
    MemoryHistoryEvent,
)
from memcommit.application.retained_history.memory_history_reconstruction.memory_history_construction import (
    MemoryHistory,
)


runner = CliRunner()

SELECTED_UID = "11111111-1111-4111-8111-111111111111"
CHILD_UID = "22222222-2222-4222-8222-222222222222"
UNRELATED_UID = "33333333-3333-4333-8333-333333333333"
CONTEXT_UID = "44444444-4444-4444-8444-444444444444"
CREATE_CHECKPOINT_UID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
EDIT_CHECKPOINT_UID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
RESTORE_CHECKPOINT_UID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"


def _state(uid: str, content: str, position: int = 0) -> MemoryState:
    return MemoryState(uid=uid, content=content, position=position)


def _event(
    kind: str,
    *,
    timestamp: str,
    command: str,
    checkpoint_uid: str,
    before: tuple[MemoryState, ...] = (),
    after: tuple[MemoryState, ...] = (),
    operation_id: str | None = None,
) -> MemoryHistoryEvent:
    return MemoryHistoryEvent(
        kind=kind,  # type: ignore[arg-type]
        evidence="RECORDED",
        timestamp=timestamp,
        checkpoint_uid=checkpoint_uid,
        command=command,
        description="",
        before=before,
        after=after,
        operation_id=operation_id,
    )


def _report(
    *,
    originals: tuple[MemoryState, ...],
    current: tuple[MemoryState, ...],
    events: tuple[MemoryHistoryEvent, ...],
    component_uids: tuple[str, ...] = (SELECTED_UID,),
) -> MemoryHistory:
    return MemoryHistory(
        context_uid=CONTEXT_UID,
        context_name="test/compact",
        selected_uid=SELECTED_UID,
        component_uids=component_uids,
        originals=originals,
        current=current,
        events=events,
        analyses=(),
        warnings=(),
    )


def _operation_lines(output: str) -> list[str]:
    return [
        line
        for line in output.splitlines()
        if line.startswith("[") and "[CHECKPOINT " in line
    ]


def test_default_trace_is_newest_first_with_log_rows_and_inline_diffs(
    capsys,
):
    original = _state(SELECTED_UID, "first wording")
    current = _state(SELECTED_UID, "current wording")
    report = _report(
        originals=(original,),
        current=(current,),
        events=(
            _event(
                "CREATED",
                timestamp="2026-07-30T11:31:00Z",
                command="add",
                checkpoint_uid=CREATE_CHECKPOINT_UID,
                after=(original,),
            ),
            _event(
                "EDITED",
                timestamp="2026-08-01T09:15:00Z",
                command="edit",
                checkpoint_uid=EDIT_CHECKPOINT_UID,
                before=(original,),
                after=(current,),
            ),
        ),
    )

    trace_command.render_trace(report)
    output = capsys.readouterr().out

    assert "TRACE · test/compact" in output
    assert "[MEMORY 11111111] · 2 OPERATIONS · LATEST FIRST" in output
    assert "NOW" not in output
    assert "ORIGIN" not in output
    rows = _operation_lines(output)
    assert len(rows) == 2
    assert rows[0] == (
        "[edit] [CHECKPOINT bbbbbbbb] [MEMORY 11111111]  2026-08-01 09:15"
    )
    assert rows[1].startswith(
        "[add] [CHECKPOINT aaaaaaaa] [MEMORY 11111111]  "
        '2026-07-30 11:31 · created "first wording"'
    )
    assert rows[1].endswith('created "first wording"')
    assert " · EDITED · RECORDED" not in output
    assert " · CREATED · RECORDED" not in output
    assert "  − [11111111]@1 first wording\n  + [11111111]@1 current wording" in output
    assert "  − ∅" not in output


def test_trace_projects_one_formatted_vertical_document_without_items_surface(
    monkeypatch,
):
    original = _state(SELECTED_UID, "first wording")
    current = _state(SELECTED_UID, "current wording")
    report = _report(
        originals=(original,),
        current=(current,),
        events=(
            _event(
                "CREATED",
                timestamp="2026-07-30T11:31:00Z",
                command="add",
                checkpoint_uid=CREATE_CHECKPOINT_UID,
                after=(original,),
            ),
            _event(
                "EDITED",
                timestamp="2026-08-01T09:15:00Z",
                command="edit",
                checkpoint_uid=EDIT_CHECKPOINT_UID,
                before=(original,),
                after=(current,),
            ),
        ),
    )
    observed: dict[str, object] = {}
    monkeypatch.setattr(
        trace_projection,
        "run_read_only_viewer",
        lambda document, **kwargs: observed.update(document=document, kwargs=kwargs),
    )

    trace_projection.open_trace_viewer(
        report,
        require_tty=False,
    )

    document = observed["document"]
    assert isinstance(document, list)
    plain = plain_text_from_fragments(document, whole_document=True)
    assert plain.index("[edit]") < plain.index("[add]")
    assert "[CHECKPOINT bbbbbbbb] [MEMORY 11111111]" in plain
    assert "NOW" not in plain and "ORIGIN" not in plain
    assert "ITEMS" not in plain
    assert observed["kwargs"]["title"] == "TRACE REPORT"
    assert observed["kwargs"]["frame_title"] == "LINEAGE"
    assert 10 <= observed["kwargs"]["compact_height"] <= 28
    styles = {style for style, _text in document}
    assert "class:semantic.edit" in styles
    assert "class:semantic.remove" in styles
    assert "class:memory-object" in styles


def test_branch_route_renders_context_movement_without_a_fake_content_edit(capsys):
    unchanged = _state(SELECTED_UID, "a is apple")
    branch = MemoryHistoryEvent(
        kind="BRANCHED",
        evidence="RECORDED",
        timestamp="2026-08-21T09:30:00Z",
        checkpoint_uid=RESTORE_CHECKPOINT_UID,
        command="branch",
        description="Branched 'practice/1' to 'practice/2'.",
        before=(unchanged,),
        after=(unchanged,),
        operation_id="branch:dddddddd-dddd-4ddd-8ddd-dddddddddddd",
        context_transition=MemoryHistoryContextTransition(
            source=MemoryHistoryCommandContext(uid="source-context", name="practice/1"),
            target=MemoryHistoryCommandContext(uid=CONTEXT_UID, name="practice/2"),
        ),
    )
    report = MemoryHistory(
        context_uid=CONTEXT_UID,
        context_name="practice/2",
        selected_uid=SELECTED_UID,
        component_uids=(SELECTED_UID,),
        originals=(unchanged,),
        current=(unchanged,),
        events=(branch,),
        analyses=(),
        warnings=(),
    )

    trace_command.render_trace(report)
    output = capsys.readouterr().out

    assert "[branch] [CHECKPOINT cccccccc]" in output
    assert "practice/1 → practice/2 · Memory content unchanged" in output
    assert "  Source Context: practice/1" in output
    assert "  Target Context: practice/2" in output
    assert "  = [11111111]@1 a is apple" in output
    assert "  − [11111111]" not in output
    assert "  + [11111111]" not in output


def test_restore_that_removes_lineage_is_one_forward_transition_to_empty(
    capsys,
):
    original = _state(SELECTED_UID, "It's going to rain today")
    report = _report(
        originals=(original,),
        current=(),
        events=(
            _event(
                "CREATED",
                timestamp="2026-07-30T11:31:00Z",
                command="add",
                checkpoint_uid=CREATE_CHECKPOINT_UID,
                after=(original,),
            ),
            _event(
                "RESTORED",
                timestamp="2026-08-03T10:29:00Z",
                command="revert",
                checkpoint_uid=RESTORE_CHECKPOINT_UID,
                before=(original,),
                operation_id="revert:one-command",
            ),
        ),
    )

    trace_command.render_trace(report)
    output = capsys.readouterr().out

    newest = _operation_lines(output)[0]
    assert newest.startswith("[revert] [CHECKPOINT cccccccc]")
    assert newest.endswith("restored/removed")
    assert "It’s going to rain today" not in newest
    assert "  − [11111111]@1 It's going to rain today\n  + ∅" in output
    assert "NOW" not in output


def test_direct_add_and_remove_are_single_rows_while_edit_keeps_its_diff(capsys):
    original = _state(SELECTED_UID, "first wording")
    edited = _state(SELECTED_UID, "edited wording")
    report = _report(
        originals=(original,),
        current=(),
        events=(
            _event(
                "CREATED",
                timestamp="2026-07-30T11:31:00Z",
                command="add",
                checkpoint_uid=CREATE_CHECKPOINT_UID,
                after=(original,),
            ),
            _event(
                "EDITED",
                timestamp="2026-08-01T09:15:00Z",
                command="edit",
                checkpoint_uid=EDIT_CHECKPOINT_UID,
                before=(original,),
                after=(edited,),
            ),
            _event(
                "REMOVED",
                timestamp="2026-08-02T10:30:00Z",
                command="remove",
                checkpoint_uid=RESTORE_CHECKPOINT_UID,
                before=(edited,),
            ),
        ),
    )

    trace_command.render_trace(report)
    compact = capsys.readouterr().out
    trace_command.render_trace(report, verbose=True)
    verbose = capsys.readouterr().out

    assert compact.count("  − ") == 1
    assert compact.count("  + ") == 1
    edit_row = next(line for line in compact.splitlines() if line.startswith("[edit]"))
    assert edit_row.endswith("2026-08-01 09:15")
    assert "content changed" not in compact
    assert "  − [11111111]@1 first wording" in compact
    assert "  + [11111111]@1 edited wording" in compact
    assert "  − ∅" not in compact and "  + ∅" not in compact
    assert verbose.count("  − ") == 3
    assert verbose.count("  + ") == 3


def test_multiline_and_terminal_controls_stay_on_one_escaped_operation_line(
    capsys,
):
    unsafe = _state(SELECTED_UID, "a\nb\t\x1b\u202ec")
    report = _report(
        originals=(unsafe,),
        current=(unsafe,),
        events=(
            _event(
                "CREATED",
                timestamp="2026-07-30T11:31:00Z",
                command="add",
                checkpoint_uid=CREATE_CHECKPOINT_UID,
                after=(unsafe,),
            ),
        ),
    )

    trace_command.render_trace(report)
    output = capsys.readouterr().out

    rows = _operation_lines(output)
    assert len(rows) == 1
    assert r"a\nb\t\x1b\u202ec" in output
    assert "\x1b" not in output
    assert "\u202e" not in output


def test_same_operation_is_grouped_and_unrelated_states_are_filtered(capsys):
    source = _state(SELECTED_UID, "selected before")
    child = _state(CHILD_UID, "selected after")
    unrelated_before = _state(UNRELATED_UID, "UNRELATED BEFORE", 1)
    unrelated_after = _state(UNRELATED_UID, "UNRELATED AFTER", 1)
    operation_id = "atomize:shared-command"
    report = _report(
        originals=(source,),
        current=(child,),
        component_uids=(SELECTED_UID, CHILD_UID),
        events=(
            _event(
                "REMOVED",
                timestamp="2026-08-02T12:00:00Z",
                command="atomize",
                checkpoint_uid=EDIT_CHECKPOINT_UID,
                before=(source, unrelated_before),
                operation_id=operation_id,
            ),
            _event(
                "CREATED",
                timestamp="2026-08-02T12:00:00Z",
                command="atomize",
                checkpoint_uid=EDIT_CHECKPOINT_UID,
                after=(child, unrelated_after),
                operation_id=operation_id,
            ),
        ),
    )

    trace_command.render_trace(report)
    output = capsys.readouterr().out

    rows = _operation_lines(output)
    assert len(rows) == 1
    assert rows[0].startswith("[atomize] [CHECKPOINT bbbbbbbb]")
    assert rows[0].endswith("removed+created")
    assert "  − [11111111]@1 selected before" in output
    assert "  + [22222222]@1 selected after" in output
    assert UNRELATED_UID[:8] not in output
    assert "UNRELATED BEFORE" not in output
    assert "UNRELATED AFTER" not in output


def test_default_hides_checkpoint_detail_while_verbose_shows_full_uids(capsys):
    state = _state(SELECTED_UID, "inspect me")
    report = _report(
        originals=(state,),
        current=(state,),
        events=(
            _event(
                "CREATED",
                timestamp="2026-07-30T11:31:00Z",
                command="add",
                checkpoint_uid=CREATE_CHECKPOINT_UID,
                after=(state,),
            ),
        ),
    )

    trace_command.render_trace(report)
    compact = capsys.readouterr().out
    trace_command.render_trace(report, verbose=True)
    verbose = capsys.readouterr().out

    assert "Checkpoint:" not in compact
    assert "Lineage: CREATED · RECORDED" not in compact
    assert SELECTED_UID not in compact
    assert CREATE_CHECKPOINT_UID not in compact
    assert "Checkpoint:" in verbose
    assert "Lineage: CREATED · RECORDED" in verbose
    assert SELECTED_UID in verbose
    assert CREATE_CHECKPOINT_UID in verbose


def test_bounded_trace_names_omitted_older_operations_without_hiding_origin():
    state = _state(SELECTED_UID, "same wording")
    events = tuple(
        _event(
            "EDITED",
            timestamp=f"2026-08-{index + 1:02d}T09:15:00Z",
            command="edit",
            checkpoint_uid=f"{index:08d}-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            before=(state,),
            after=(state,),
        )
        for index in range(3)
    )
    report = _report(originals=(state,), current=(state,), events=events)

    bounded = format_compact_trace_report(report, limit=2)
    complete = format_compact_trace_report(report, limit=None)

    assert "SHOWING 2 OF 3" in bounded
    assert "… 1 OLDER OPERATIONS HIDDEN · use --all or --limit N" in bounded
    assert bounded.count("2026-") == 2
    assert "ORIGIN" not in bounded
    assert "HIDDEN" not in complete
    assert complete.count("2026-") == 3


def test_plain_projection_is_exactly_the_unstyled_tui_document():
    state = _state(SELECTED_UID, "inspect me")
    report = _report(
        originals=(state,),
        current=(state,),
        events=(
            _event(
                "CREATED",
                timestamp="2026-07-30T11:31:00Z",
                command="add",
                checkpoint_uid=CREATE_CHECKPOINT_UID,
                after=(state,),
            ),
        ),
    )

    fragments = trace_document_fragments(report)

    assert format_compact_trace_report(report) == plain_text_from_fragments(
        fragments,
        whole_document=True,
    )


def test_cli_limit_and_all_control_only_the_human_operation_projection(
    isolated_store,
    monkeypatch,
):
    assert runner.invoke(app, ["init", "bounded-trace"]).exit_code == 0
    state = _state(SELECTED_UID, "same wording")
    report = _report(
        originals=(state,),
        current=(state,),
        events=tuple(
            _event(
                "EDITED",
                timestamp=f"2026-08-{index + 1:02d}T09:15:00Z",
                command="edit",
                checkpoint_uid=f"{index:08d}-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                before=(state,),
                after=(state,),
            )
            for index in range(3)
        ),
    )
    monkeypatch.setattr(trace_command, "build_memory_history", lambda *_args: report)
    monkeypatch.setattr(
        trace_command,
        "resolve_local_memory_report_target",
        lambda *_args, **_kwargs: ResolvedMemoryReportTarget(
            context_name="bounded-trace",
            uid=SELECTED_UID,
            kind="MEMORY",
            status="CURRENT",
        ),
    )

    bounded = runner.invoke(app, ["trace", SELECTED_UID, "--limit", "1", "--plain"])
    complete = runner.invoke(app, ["trace", SELECTED_UID, "--all", "--plain"])
    invalid = runner.invoke(app, ["trace", SELECTED_UID, "--limit", "0"])

    assert bounded.exit_code == 0, bounded.output
    assert bounded.output.count("2026-") == 1
    assert "SHOWING 1 OF 3" in bounded.output
    assert complete.exit_code == 0, complete.output
    assert complete.output.count("2026-") == 3
    assert "HIDDEN" not in complete.output
    assert invalid.exit_code == 2
    assert "--limit must be between 1 and 200" in invalid.output


def test_json_keeps_structured_events_in_chronological_order(
    isolated_store,
    monkeypatch,
):
    initialized = runner.invoke(app, ["init", "json-trace"])
    assert initialized.exit_code == 0
    original = _state(SELECTED_UID, "old")
    current = _state(SELECTED_UID, "new")
    report = _report(
        originals=(original,),
        current=(current,),
        events=(
            _event(
                "CREATED",
                timestamp="2026-07-30T11:31:00Z",
                command="add",
                checkpoint_uid=CREATE_CHECKPOINT_UID,
                after=(original,),
            ),
            _event(
                "EDITED",
                timestamp="2026-08-01T09:15:00Z",
                command="edit",
                checkpoint_uid=EDIT_CHECKPOINT_UID,
                before=(original,),
                after=(current,),
            ),
        ),
    )

    monkeypatch.setattr(
        trace_command,
        "build_memory_history",
        lambda *_args: report,
    )
    monkeypatch.setattr(
        trace_command,
        "resolve_local_memory_report_target",
        lambda *_args, **_kwargs: ResolvedMemoryReportTarget(
            context_name="json-trace",
            uid=SELECTED_UID,
            kind="MEMORY",
            status="CURRENT",
        ),
    )

    result = runner.invoke(app, ["trace", SELECTED_UID, "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert [event["kind"] for event in payload["events"]] == [
        "CREATED",
        "EDITED",
    ]
    assert [event["timestamp"] for event in payload["events"]] == [
        "2026-07-30T11:31:00Z",
        "2026-08-01T09:15:00Z",
    ]
