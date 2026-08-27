"""Shared compact result paging mechanics."""

from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.adapters.interfaces.tui.components.paged_result import (
    PagedResultRenderer,
    PagedResultState,
    run_paged_result,
)


def test_paged_result_state_exposes_range_total_and_discrete_pages() -> None:
    state = PagedResultState(64, page_size=10)

    assert state.showing_label == "SHOWING 1–10 OF 64"
    assert tuple(state.visible_indices) == tuple(range(10))
    assert state.move_page(1)
    assert state.selected_index == 10
    assert state.showing_label == "SHOWING 11–20 OF 64"
    assert state.move_to_boundary(end=True)
    assert state.selected_index == 63
    assert state.showing_label == "SHOWING 61–64 OF 64"
    assert not state.move(1)


def test_paged_result_page_move_retains_row_position_when_possible() -> None:
    state = PagedResultState(24, page_size=10, selected_index=6)

    assert state.move_page(1)
    assert state.selected_index == 16
    assert state.showing_label == "SHOWING 11–20 OF 24"
    assert state.move_page(1)
    assert state.selected_index == 23
    assert state.showing_label == "SHOWING 21–24 OF 24"


def test_compact_pager_arrows_change_selection_without_full_screen() -> None:
    renderer = PagedResultRenderer(
        item_count=24,
        header=lambda state: [("", state.showing_label)],
        row=lambda index: [("", f"row {index + 1}")],
        header_height=1,
        page_size=10,
    )
    with create_pipe_input() as pipe_input:
        # Right moves to the corresponding row on page two; Down then focuses
        # the next result before q returns to the surrounding command flow.
        pipe_input.send_text("\x1b[C\x1b[Bq")
        selected = run_paged_result(
            renderer,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == 11
