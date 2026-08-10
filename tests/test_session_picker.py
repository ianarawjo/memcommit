"""Contract tests for the operation-neutral saved-session picker."""

from __future__ import annotations

import io

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.utils import get_cwidth

import memcommit.commands.session_picker as session_picker_module
from memcommit.commands.session_picker import (
    SessionNewReceipt,
    SessionOpenReceipt,
    SessionPickerEntry,
    SessionPickerLocation,
    _compact,
    _grouped_line_count,
    _ordered_entries,
    _render_detail,
    _render_entry_line,
    _render_location,
    _render_new_detail,
    _new_session_label,
    _visible_bounds,
    _visible_grouped_bounds,
    choose_session,
)


def entry(
    key: str,
    *,
    title: str,
    timestamp: float,
    group: str = "campus/wiki",
    kind: str = "ground",
    status: str = "OPEN",
    subtitle: str = "rev 2",
) -> SessionPickerEntry:
    return SessionPickerEntry(
        kind=kind,
        key=key,
        title=title,
        status=status,
        subtitle=subtitle,
        group=group,
        sort_timestamp=timestamp,
        detail=f"Saved work for {title}",
        reopen_argv=("mem", kind, key),
    )


def test_compact_uses_terminal_cell_width_for_korean_text():
    compact = _compact("저장된 작업을 다시 엽니다", 12)

    assert compact.endswith("…")
    assert get_cwidth(compact) <= 12


def test_session_row_uses_available_width_before_eliding_summary():
    candidate = entry(
        "task-one",
        title="task-1/description",
        timestamp=1,
        status="CURRENT",
        subtitle=(
            "task-1/description → task-1/description/atomized · "
            "1 → 1 Memories · 1 issues"
        ),
    )

    wide = _render_entry_line(
        candidate,
        entries=(candidate,),
        selected=True,
        available_width=160,
    )
    narrow = _render_entry_line(
        candidate,
        entries=(candidate,),
        selected=True,
        available_width=80,
    )

    assert candidate.subtitle in wide
    assert "…" not in wide
    assert "…" in narrow
    assert get_cwidth(narrow) <= 80


def test_session_row_does_not_reserve_thirty_cells_for_a_short_title():
    candidate = entry(
        "short",
        title="Input",
        timestamp=1,
        status="OPEN",
        subtitle="This summary receives every cell the short title does not need.",
    )

    rendered = _render_entry_line(
        candidate,
        entries=(candidate,),
        selected=False,
        available_width=110,
    )

    assert candidate.subtitle in rendered
    assert "…" not in rendered


def test_location_escapes_frozen_profile_and_store_orientation():
    rendered = _render_location(
        SessionPickerLocation(
            profile_name="task-1\nFAKE",
            store_path="/tmp/store\u202eexe",
        )
    )

    assert rendered == (
        " PROFILE · task-1\\nFAKE\n"
        " STORE   · /tmp/store\\u202eexe"
    )
    assert "\u202e" not in rendered


def test_enter_returns_exact_reopen_argv_without_executing_it():
    candidate = entry("task-one", title="Task One", timestamp=3)
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\r")
        selected = choose_session(
            (candidate,),
            title="MEM GROUND · SAVED",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == SessionOpenReceipt(
        kind="ground",
        key="task-one",
        argv=("mem", "ground", "task-one"),
    )
    assert selected.argv is candidate.reopen_argv


def test_default_recent_sort_and_arrows_select_second_newest():
    candidates = (
        entry("old", title="Old", timestamp=1),
        entry("new", title="New", timestamp=3),
        entry("middle", title="Middle", timestamp=2),
    )
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\r")
        selected = choose_session(
            candidates,
            title="SAVED WORK",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert isinstance(selected, SessionOpenReceipt)
    assert selected.key == "middle"


def test_adapter_can_start_grouped_by_context_with_recent_order_inside_groups():
    candidates = (
        entry("beta-new", title="Beta New", timestamp=4, group="beta"),
        entry("alpha-new", title="Alpha New", timestamp=3, group="alpha"),
        entry("alpha-old", title="Alpha Old", timestamp=2, group="alpha"),
    )
    with create_pipe_input() as pipe_input:
        # Context grouping puts Alpha first; recent ordering inside that group
        # puts Alpha New before Alpha Old.
        pipe_input.send_text("\x1b[B\r")
        selected = choose_session(
            candidates,
            title="SAVED WORK",
            initial_group_mode="context",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert isinstance(selected, SessionOpenReceipt)
    assert selected.key == "alpha-old"


def test_s_toggles_to_name_sort_while_preserving_current_selection():
    candidates = (
        entry("z", title="Zulu", timestamp=3),
        entry("a", title="Alpha", timestamp=1),
        entry("b", title="Bravo", timestamp=2),
    )
    with create_pipe_input() as pipe_input:
        # Zulu starts selected under recent-first. The sort toggle preserves it;
        # moving up once in name order reaches Bravo.
        pipe_input.send_text("s\x1b[A\r")
        selected = choose_session(
            candidates,
            title="SAVED WORK",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert isinstance(selected, SessionOpenReceipt)
    assert selected.key == "b"


def test_g_groups_by_context_and_preserves_selection():
    candidates = (
        entry("b-new", title="B New", timestamp=4, group="beta"),
        entry("a-new", title="A New", timestamp=3, group="alpha"),
        entry("a-old", title="A Old", timestamp=2, group="alpha"),
    )
    with create_pipe_input() as pipe_input:
        # B New is initially first and remains selected after grouping. Moving
        # up reaches the preceding Alpha item in the grouped projection.
        pipe_input.send_text("g\x1b[A\r")
        selected = choose_session(
            candidates,
            title="SAVED WORK",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert isinstance(selected, SessionOpenReceipt)
    assert selected.key == "a-old"


def test_slash_filter_searches_presentation_metadata():
    candidates = (
        entry("first", title="Planning", timestamp=3, group="facilities"),
        entry("second", title="Atomized", timestamp=2, group="research"),
    )
    with create_pipe_input() as pipe_input:
        # The first Enter applies the filter; the second reopens its sole match.
        pipe_input.send_text("/research\r\r")
        selected = choose_session(
            candidates,
            title="SAVED WORK",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert isinstance(selected, SessionOpenReceipt)
    assert selected.key == "second"


def test_slash_filter_can_find_a_secondary_context_in_detail():
    candidate = SessionPickerEntry(
        kind="ground",
        key="task-one",
        title="Task One",
        status="OPEN",
        subtitle="Build the fixture.",
        group="temp/task-1",
        sort_timestamp=1,
        detail="Contexts: temp/task-1, campus-wiki",
        reopen_argv=("mem", "ground", "task-one"),
    )
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("/campus-wiki\r\r")
        selected = choose_session(
            (candidate,),
            title="SAVED WORK",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert isinstance(selected, SessionOpenReceipt)
    assert selected.key == "task-one"


def test_n_returns_only_an_explicitly_enabled_new_receipt():
    receipt = SessionNewReceipt(kind="ground", argv=("mem", "ground"))
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("n")
        selected = choose_session(
            (),
            title="MEM GROUND · SAVED",
            new_receipt=receipt,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is receipt

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("nq")
        disabled = choose_session(
            (entry("one", title="One", timestamp=1),),
            title="MEM GROUND · SAVED",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert disabled is None


def test_add_new_is_a_selectable_row_above_saved_sessions():
    receipt = SessionNewReceipt(kind="meld", argv=("mem", "meld"))
    candidate = entry("saved", title="Saved", timestamp=1, kind="meld")
    with create_pipe_input() as pipe_input:
        # A nonempty catalog retains the saved session as the initial choice;
        # Up reaches the pinned Add-new row and Enter returns its exact receipt.
        pipe_input.send_text("\x1b[A\r")
        selected = choose_session(
            (candidate,),
            title="MEM MELD · SAVED SESSIONS",
            new_receipt=receipt,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is receipt


def test_empty_catalog_selects_add_new_row_for_enter():
    receipt = SessionNewReceipt(kind="sever", argv=("mem", "sever"))
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\r")
        selected = choose_session(
            (),
            title="MEM SEVER · SAVED SESSIONS",
            new_receipt=receipt,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is receipt


def test_add_new_label_and_detail_omit_the_internal_action_receipt():
    receipt = SessionNewReceipt(
        kind="saved_review",
        argv=("mem", "review", "unsafe\nname"),
    )

    assert _new_session_label(receipt) == "Add new Saved Review session"
    detail = _render_new_detail(receipt)
    assert "Add new Saved Review session" in detail
    assert "NOT EXECUTED" not in detail
    assert "[0]" not in detail
    assert "unsafe\\nname" not in detail
    assert "unsafe\nname" not in detail

    unsafe = SessionNewReceipt(kind="meld\nFAKE", argv=("mem", "meld"))
    assert _new_session_label(unsafe) == "Add new Meld\\nFake session"


def test_pinned_action_can_name_selection_instead_of_a_new_session():
    receipt = SessionNewReceipt(
        kind="trace-select",
        argv=("mem", "trace"),
        action_label="SELECT A MEMORY",
        action_description="Choose from the common Memory tree.",
    )

    assert _new_session_label(receipt) == "SELECT A MEMORY"
    detail = _render_new_detail(receipt)
    assert "SELECT A MEMORY" in detail
    assert "Choose from the common Memory tree." in detail
    assert "Exact action route" not in detail
    assert "[0]" not in detail


@pytest.mark.parametrize("key", ["q", "\x1b", "\x03"])
def test_cancel_keys_return_none(key: str):
    with create_pipe_input() as pipe_input:
        pipe_input.send_text(key)
        selected = choose_session(
            (entry("one", title="One", timestamp=1),),
            title="SAVED WORK",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is None


def test_order_helper_filters_and_sorts_without_mutating_input():
    candidates = [
        entry("z", title="Zulu", timestamp=1, group="beta"),
        entry("a", title="Alpha", timestamp=3, group="alpha"),
        entry("b", title="Bravo", timestamp=2, group="alpha"),
    ]

    recent = _ordered_entries(
        candidates,
        sort_mode="recent",
        group_mode="all",
    )
    named = _ordered_entries(
        candidates,
        sort_mode="name",
        group_mode="all",
    )
    grouped = _ordered_entries(
        candidates,
        sort_mode="recent",
        group_mode="context",
    )
    filtered = _ordered_entries(
        candidates,
        sort_mode="recent",
        group_mode="all",
        query="BETA",
    )

    assert [item.key for item in recent] == ["a", "b", "z"]
    assert [item.key for item in named] == ["a", "b", "z"]
    assert [item.key for item in grouped] == ["a", "b", "z"]
    assert [item.key for item in filtered] == ["z"]
    assert [item.key for item in candidates] == ["z", "a", "b"]


def test_visible_window_tracks_selection_and_handles_an_empty_catalog():
    assert _visible_bounds(0, 0) == (0, 0)
    assert _visible_bounds(0, 20) == (0, 12)
    assert _visible_bounds(10, 20) == (4, 16)
    assert _visible_bounds(19, 20) == (8, 20)
    # The pinned Add-new launcher consumes one of the twelve list lines.
    assert _visible_bounds(10, 20, line_budget=11) == (5, 16)


def test_grouped_window_accounts_for_heading_and_separator_lines():
    candidates = tuple(
        entry(
            f"item-{index}",
            title=f"Item {index}",
            timestamp=float(index),
            group=f"context-{index}",
        )
        for index in range(20)
    )

    start, end = _visible_grouped_bounds(candidates, 10)

    assert start <= 10 < end
    # Five distinct Context rows occupy 14 lines, so no more than four can be
    # included in the picker's twelve-line list region.
    assert end - start <= 4
    assert _grouped_line_count(candidates, start=start, end=end) <= 12


def test_grouped_window_keeps_more_rows_when_they_share_one_context():
    candidates = tuple(
        entry(
            f"item-{index}",
            title=f"Item {index}",
            timestamp=float(index),
            group="one-context",
        )
        for index in range(20)
    )

    start, end = _visible_grouped_bounds(candidates, 10)

    assert start <= 10 < end
    assert end - start == 11
    assert _grouped_line_count(candidates, start=start, end=end) == 12


def test_context_group_sort_keeps_case_variants_contiguous():
    candidates = (
        entry("upper-new", title="Zulu", timestamp=4, group="A"),
        entry("lower", title="Alpha", timestamp=3, group="a"),
        entry("upper-old", title="Bravo", timestamp=2, group="A"),
    )

    grouped = _ordered_entries(
        candidates,
        sort_mode="recent",
        group_mode="context",
    )

    assert [candidate.group for candidate in grouped] == ["A", "A", "a"]
    assert [candidate.key for candidate in grouped[:2]] == [
        "upper-new",
        "upper-old",
    ]


def test_detail_escapes_untrusted_metadata_and_omits_internal_open_argv():
    candidate = SessionPickerEntry(
        kind="ground\nFAKE",
        key="key\u202eexe",
        title="Title\tFORGED",
        status="OPEN\u2066",
        subtitle="subtitle\nheading",
        group="context\rOTHER",
        sort_timestamp=0,
        detail="first line\nsecond line\u202e",
        reopen_argv=("mem", "ground", "unsafe\n--delete", "\\literal"),
    )

    rendered = _render_detail(candidate)

    assert "ground\\nFAKE" in rendered
    assert "key\\u202eexe" in rendered
    assert "Title\\tFORGED" in rendered
    assert "OPEN\\u2066" in rendered
    assert "context\\rOTHER" in rendered
    assert "first line" in rendered
    assert " Summary      subtitle\\nheading" in rendered
    assert " Subtitle     " not in rendered
    assert "              second line\\u202e" in rendered
    assert "Public route hint" not in rendered
    assert "[0]" not in rendered
    assert "unsafe\\n--delete" not in rendered
    assert "\\\\literal" not in rendered
    assert "\u202e" not in rendered
    assert "\u2066" not in rendered


def test_detail_only_mode_renders_content_without_metadata_envelope():
    candidate = SessionPickerEntry(
        kind="compare",
        key="analysis-one",
        title="Advisor 1 ↔ Advisor 2",
        status="CURRENT",
        subtitle="12 relations",
        group="advisor1",
        sort_timestamp=0,
        detail="MEM COMPARE\nWHAT BOTH CONTAIN\nunsafe\tvalue",
        reopen_argv=("mem", "compare", "--to", "advisor2"),
        detail_only=True,
    )

    rendered = _render_detail(candidate)

    assert rendered == "MEM COMPARE\nWHAT BOTH CONTAIN\nunsafe\\tvalue"
    assert " Kind " not in rendered
    assert "Public route hint" not in rendered


def test_picker_rejects_non_tty_by_default(monkeypatch):
    monkeypatch.setattr(session_picker_module.sys, "stdin", io.StringIO())
    monkeypatch.setattr(session_picker_module.sys, "stdout", io.StringIO())

    with pytest.raises(ValueError, match="requires a terminal"):
        choose_session(
            (entry("one", title="One", timestamp=1),),
            title="SAVED WORK",
        )


def test_picker_validates_empty_duplicate_and_invalid_catalogs():
    candidate = entry("one", title="One", timestamp=1)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        assert (
            choose_session(
                (),
                title="SAVED WORK",
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )
            is None
        )
    with pytest.raises(ValueError, match="duplicate"):
        choose_session(
            (candidate, candidate),
            title="SAVED WORK",
            require_tty=False,
        )
    with pytest.raises(ValueError, match="title"):
        choose_session(
            (candidate,),
            title="",
            require_tty=False,
        )
    with pytest.raises(ValueError, match="invalid entry"):
        choose_session(
            (object(),),  # type: ignore[arg-type]
            title="SAVED WORK",
            require_tty=False,
        )
    with pytest.raises(ValueError, match="initial sort mode"):
        choose_session(
            (candidate,),
            title="SAVED WORK",
            initial_sort_mode="other",  # type: ignore[arg-type]
            require_tty=False,
        )
    with pytest.raises(ValueError, match="initial group mode"):
        choose_session(
            (candidate,),
            title="SAVED WORK",
            initial_group_mode="other",  # type: ignore[arg-type]
            require_tty=False,
        )
    with pytest.raises(ValueError, match="invalid location"):
        choose_session(
            (candidate,),
            title="SAVED WORK",
            location=object(),  # type: ignore[arg-type]
            require_tty=False,
        )


def test_empty_picker_can_return_an_explicit_new_session_receipt():
    receipt = SessionNewReceipt(kind="sever", argv=("mem", "sever"))
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("N")
        selected = choose_session(
            (),
            title="MEM SEVER · SAVED SESSIONS",
            new_receipt=receipt,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == receipt


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"profile_name": ""}, "profile name"),
        ({"store_path": ""}, "store path"),
        ({"profile_name": 1}, "profile name"),
        ({"store_path": 1}, "store path"),
    ],
)
def test_picker_location_rejects_invalid_orientation(changes, message):
    values = {"profile_name": "authoring", "store_path": "/tmp/store"}
    values.update(changes)

    with pytest.raises(ValueError, match=message):
        SessionPickerLocation(**values)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"group": ""}, "group"),
        ({"subtitle": 1}, "subtitle"),
        ({"sort_timestamp": float("nan")}, "timestamp"),
        ({"sort_timestamp": 1e100}, "timestamp"),
        ({"sort_timestamp": True}, "timestamp"),
        ({"reopen_argv": ("", "ground")}, "argv"),
        ({"reopen_argv": ["mem", "ground"]}, "argv"),
        ({"detail_only": "yes"}, "detail-only"),
    ],
)
def test_entry_rejects_invalid_presentation_fields(changes, message):
    values = {
        "kind": "ground",
        "key": "one",
        "title": "One",
        "status": "OPEN",
        "subtitle": "rev 1",
        "group": "Unbound",
        "sort_timestamp": 1.0,
        "detail": "Detail",
        "reopen_argv": ("mem", "ground", "one"),
    }
    values.update(changes)

    with pytest.raises(ValueError, match=message):
        SessionPickerEntry(**values)


def test_same_key_is_valid_for_different_operation_kinds():
    ground = entry("shared", title="Ground", timestamp=2, kind="ground")
    meld = entry("shared", title="Meld", timestamp=1, kind="meld")
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        selected = choose_session(
            (ground, meld),
            title="SAVED WORK",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is None


def test_application_is_full_screen_and_receives_no_io_callbacks(monkeypatch):
    captured = {}

    class FakeApplication:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run(self):
            return None

    monkeypatch.setattr(session_picker_module, "Application", FakeApplication)

    assert (
        choose_session(
            (entry("one", title="One", timestamp=1),),
            title="SAVED WORK",
            require_tty=False,
        )
        is None
    )
    assert captured["full_screen"] is True
    assert captured["erase_when_done"] is True
