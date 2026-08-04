"""Compact operation-oriented ``mem trace`` presentation contracts."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from memcommit.cli import app
from memcommit.commands import trace as trace_command
from memcommit.provenance import MemoryState, TraceEvent, TraceReport


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
) -> TraceEvent:
    return TraceEvent(
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
    events: tuple[TraceEvent, ...],
    component_uids: tuple[str, ...] = (SELECTED_UID,),
) -> TraceReport:
    return TraceReport(
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
    return [line for line in output.splitlines() if line.startswith("2026-")]


def test_default_trace_is_newest_first_with_explicit_scope_and_endpoints(
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

    assert "Trace [11111111] · test/compact" in output
    assert (
        "RANGE · earliest retained evidence → current Context · "
        "LATEST FIRST (↓ older); each row is BEFORE → AFTER"
    ) in output
    assert "NOW · [11111111]@1 “current wording”" in output
    assert "ORIGIN · [11111111]@1 “first wording”" in output
    rows = _operation_lines(output)
    assert len(rows) == 2
    assert "EDITED" in rows[0]
    assert "first wording” → [11111111]@1 “current wording" in rows[0]
    assert "CREATED" in rows[1]
    assert "∅ → [11111111]@1 “first wording”" in rows[1]


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
    assert "mem revert · RESTORED/REMOVED" in newest
    assert "It’s going to rain today" not in newest
    assert "It's going to rain today” → ∅" in newest
    assert "NOW · ∅ (lineage absent from current Context)" in output


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
    assert r"a\nb\t\x1b\u202ec" in rows[0]
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
    assert "REMOVED+CREATED" in rows[0]
    assert "selected before” → [22222222]@1 “selected after" in rows[0]
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
    assert SELECTED_UID not in compact
    assert CREATE_CHECKPOINT_UID not in compact
    assert "Checkpoint:" in verbose
    assert SELECTED_UID in verbose
    assert CREATE_CHECKPOINT_UID in verbose


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

    monkeypatch.setattr(trace_command, "build_trace", lambda *_args: report)

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
