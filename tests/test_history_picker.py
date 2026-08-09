"""Interaction and presentation contract for the shared history picker."""
from __future__ import annotations

import io

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.utils import get_cwidth

from memcommit.commands.history_picker import (
    HISTORY_BACK,
    HistoryPickerEntry,
    HistorySelectionReceipt,
    _PickerState,
    _activate,
    _move,
    _render_detail,
    _render_entry_line,
    _visible_bounds,
    choose_history,
)


def entry(
    suffix: int,
    *,
    description: str = "Added one note",
) -> HistoryPickerEntry:
    return HistoryPickerEntry(
        uid=f"00000000-0000-4000-8000-{suffix:012d}",
        timestamp=f"2026-07-30T11:{suffix:02d}:00-04:00",
        command="add",
        description=description,
        detail=(
            f"Snapshot: {suffix + 3} direct items · {suffix} Memories · "
            "1 MemoryRef · 1 query-only Context · 1 embedded Context\n"
            "Transition: +1 added · ~2 edited · -3 removed · 4 reordered"
        ),
    )


def test_history_row_gives_wide_viewport_to_description():
    candidate = entry(
        1,
        description=(
            "A complete checkpoint description that used to be cut at a fixed "
            "fifty-eight characters even on a wide terminal."
        ),
    )

    wide = _render_entry_line(
        candidate,
        entries=(candidate,),
        selected=True,
        available_width=180,
    )
    narrow = _render_entry_line(
        candidate,
        entries=(candidate,),
        selected=True,
        available_width=70,
    )

    assert candidate.description in wide
    assert "…" not in wide
    assert "…" in narrow
    assert get_cwidth(narrow) <= 70


def test_revert_enter_returns_exact_checkpoint_receipt():
    candidate = entry(1)
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\r")
        selected = choose_history(
            (candidate,),
            context_name="test/update/to",
            mode="revert",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == HistorySelectionReceipt(
        context_name="test/update/to",
        checkpoint_uid=candidate.uid,
    )


def test_revert_arrows_move_and_clamp_before_accepting():
    candidates = (entry(1), entry(2), entry(3))
    with create_pipe_input() as pipe_input:
        # Clamp below the last row, move once up, then choose the second row.
        pipe_input.send_text("\x1b[B\x1b[B\x1b[B\x1b[B\x1b[A\r")
        selected = choose_history(
            candidates,
            context_name="journal",
            mode="revert",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is not None
    assert selected.checkpoint_uid == candidates[1].uid


def test_log_enter_toggles_details_and_q_closes_without_selection():
    candidate = entry(1)
    with create_pipe_input() as pipe_input:
        # Enter must not exit log mode. q closes only after both detail toggles.
        pipe_input.send_text("\r\rq")
        selected = choose_history(
            (candidate,),
            context_name="journal",
            mode="log",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is None

    state = _PickerState(selected_index=0, details_open=False)
    assert (
        _activate(
            state,
            mode="log",
            context_name="journal",
            entry=candidate,
        )
        is None
    )
    assert state.details_open is True
    _activate(
        state,
        mode="log",
        context_name="journal",
        entry=candidate,
    )
    assert state.details_open is False


def test_empty_log_stays_open_until_an_explicit_close_key():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\rq")
        selected = choose_history(
            (),
            context_name="empty/context",
            mode="log",
            initial_details_open=True,
            empty_message="No checkpoints for this Context yet.",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is None


@pytest.mark.parametrize("key", ["q", "\x1b", "\x7f", "\x03"])
def test_cancel_keys_return_no_receipt(key: str):
    with create_pipe_input() as pipe_input:
        pipe_input.send_text(key)
        selected = choose_history(
            (entry(1),),
            context_name="journal",
            mode="revert",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is None


@pytest.mark.parametrize("key", ["\x1b", "\x7f"])
def test_diff_style_back_keys_return_explicit_navigation_receipt(key: str):
    with create_pipe_input() as pipe_input:
        pipe_input.send_text(key)
        selected = choose_history(
            (entry(1),),
            context_name="journal",
            mode="log",
            back_navigation=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is HISTORY_BACK


def test_viewer_back_returns_to_items_before_leaving_history():
    with create_pipe_input() as pipe_input:
        # Enter opens VIEWER; the first Backspace returns to ITEMS and only the
        # second requests the owning Context selector.
        pipe_input.send_text("\r\x7f\x7f")
        selected = choose_history(
            (entry(1),),
            context_name="journal",
            mode="log",
            initial_details_open=True,
            back_navigation=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is HISTORY_BACK


def test_move_helper_clamps_at_both_boundaries():
    state = _PickerState(selected_index=0, details_open=False)
    _move(state, -100, 3)
    assert state.selected_index == 0
    _move(state, 100, 3)
    assert state.selected_index == 2


def test_visible_window_tracks_selection_and_never_exceeds_twelve_rows():
    assert _visible_bounds(0, 20) == (0, 12)
    assert _visible_bounds(10, 20) == (4, 16)
    assert _visible_bounds(19, 20) == (8, 20)


def test_detail_contains_full_checkpoint_and_direct_change_summaries():
    candidate = entry(5)

    rendered = _render_detail(candidate)

    assert candidate.uid in rendered
    assert candidate.timestamp in rendered
    assert "Command      add" in rendered
    assert "Description  Added one note" in rendered
    assert (
        "Detail       Snapshot: 8 direct items · 5 Memories · "
        "1 MemoryRef · 1 query-only Context · 1 embedded Context"
    ) in rendered
    assert (
        "              Transition: +1 added · ~2 edited · "
        "-3 removed · 4 reordered"
    ) in rendered


def test_generic_detail_can_render_a_temporal_memory_version():
    candidate = HistoryPickerEntry(
        uid="11111111-1111-4111-8111-111111111111",
        timestamp="2026-07-30T11:00:00-04:00",
        command="memory-version",
        description="Latest version while the shuttle notice existed",
        detail=(
            "Memory: The East Gate shuttle follows a construction detour.\n"
            "Temporal relation: before checkpoint 22222222"
        ),
    )

    rendered = _render_detail(candidate)

    assert "Command      memory-version" in rendered
    assert "Memory: The East Gate shuttle" in rendered
    assert "Temporal relation: before checkpoint" in rendered


def test_log_mode_accepts_a_non_checkpoint_protocol_projection():
    class TemporalMemoryVersion:
        uid = "version:shuttle:before-change"
        timestamp = "2026-07-30T11:00:00-04:00"
        command = "memory-version"
        description = "Latest matching Memory version"
        detail = "The shuttle notice still existed."

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        selected = choose_history(
            (TemporalMemoryVersion(),),
            context_name="transportation",
            mode="log",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is None


def test_untrusted_fields_are_display_escaped_in_detail():
    candidate = HistoryPickerEntry(
        uid="uid\nsecond-heading",
        timestamp="time\u202eexe",
        command="add\tFAKE",
        description="safe\nREVERT NOW\u2066",
        detail="Memory text\u202e\nFAKE TRUSTED HEADING",
    )

    rendered = _render_detail(candidate)

    assert "uid\\nsecond-heading" in rendered
    assert "time\\u202eexe" in rendered
    assert "add\\tFAKE" in rendered
    assert "safe\\nREVERT NOW\\u2066" in rendered
    assert "Memory text\\u202e" in rendered
    assert "\n              FAKE TRUSTED HEADING" in rendered
    assert "\u202e" not in rendered
    assert "\u2066" not in rendered


def test_picker_requires_tty_when_requested(monkeypatch):
    monkeypatch.setattr(
        "memcommit.commands.history_picker.sys.stdin",
        io.StringIO(),
    )
    monkeypatch.setattr(
        "memcommit.commands.history_picker.sys.stdout",
        io.StringIO(),
    )

    with pytest.raises(ValueError, match="requires a terminal"):
        choose_history(
            (entry(1),),
            context_name="journal",
            mode="log",
        )


def test_picker_rejects_empty_duplicate_or_invalid_inputs():
    candidate = entry(1)

    with pytest.raises(ValueError, match="No history entries"):
        choose_history(
            (),
            context_name="journal",
            mode="log",
            require_tty=False,
        )
    with pytest.raises(ValueError, match="duplicate"):
        choose_history(
            (candidate, candidate),
            context_name="journal",
            mode="log",
            require_tty=False,
        )
    with pytest.raises(ValueError, match="Context name"):
        choose_history(
            (candidate,),
            context_name="",
            mode="log",
            require_tty=False,
        )
    with pytest.raises(ValueError, match="mode"):
        choose_history(
            (candidate,),
            context_name="journal",
            mode="inspect",  # type: ignore[arg-type]
            require_tty=False,
        )


def test_entry_rejects_non_text_detail():
    with pytest.raises(ValueError, match="detail"):
        HistoryPickerEntry(
            uid="11111111-1111-4111-8111-111111111111",
            timestamp="2026-07-30T11:00:00-04:00",
            command="add",
            description="Added",
            detail=3,  # type: ignore[arg-type]
        )
