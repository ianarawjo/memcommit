"""Interaction and presentation contracts for trace/rationale Memory selection."""

from __future__ import annotations

import io

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.commands.shared.memory_picker import (
    MemoryReportTargetSelection,
    ScopedMemoryPickerItem,
    _render_memory_options,
    choose_memory,
    choose_memory_report_target,
)
import memcommit.context_targeting.tui.picker as context_picker
import memcommit.application.ops as ops
from memcommit.retained_history.memory_history_reconstruction.memory_history_construction import (
    MemoryHistoryCandidate,
    collect_memory_history_candidates,
)
from memcommit.store import MemoryStore
from memcommit.interfaces.console.theme import ERROR_HEX
from memcommit.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)


def candidate(
    suffix: int,
    *,
    content: str | None = None,
    status: str = "CURRENT",
    change_count: int | None = None,
) -> MemoryHistoryCandidate:
    return MemoryHistoryCandidate(
        uid=f"00000000-0000-4000-8000-{suffix:012d}",
        content=content if content is not None else f"Memory {suffix}",
        position=suffix,
        status=status,  # type: ignore[arg-type]
        change_count=change_count,
    )


def test_picker_returns_the_exact_selected_uid():
    options = (candidate(1), candidate(2, status="HISTORICAL"))
    with create_pipe_input() as pipe_input:
        # The common selector starts on the current Context, then visits its
        # Memory rows in display order.
        pipe_input.send_text("\x1b[B\x1b[B\r")
        selected = choose_memory(
            options,
            context_name="notes",
            operation="trace",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == options[1].uid


def test_scoped_picker_keeps_empty_current_context_as_initial_focus():
    item = ScopedMemoryPickerItem(
        context_name="notes/child",
        uid=candidate(1).uid,
        content="child Memory",
        status="CURRENT",
        catalog_context_names=("notes", "notes/child"),
    )
    with create_pipe_input() as pipe_input:
        # Root Context -> child Context -> child's Memory.
        pipe_input.send_text("\x1b[B\x1b[B\r")
        selected = choose_memory(
            (item,),
            context_name="notes",
            operation="rationale",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == item.uid


def test_report_picker_opens_a_frozen_context_catalog_with_no_memories():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        selected = choose_memory_report_target(
            (),
            context_name="empty",
            operation="rationale",
            catalog_context_names=("empty",),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is None


def test_report_picker_can_broaden_an_empty_root_to_descendant_memories():
    item = ScopedMemoryPickerItem(
        context_name="notes/child",
        uid=candidate(1).uid,
        content="child Memory",
        status="CURRENT",
        catalog_context_names=("notes", "notes/child"),
        change_count=3,
    )
    with create_pipe_input() as pipe_input:
        # RANGE starts on THIS CONTEXT ONLY. Broaden, enter the tree, then
        # visit root -> child -> child Memory and open the exact target.
        pipe_input.send_text("\x1b[C\t\x1b[B\x1b[B\r")
        selected = choose_memory_report_target(
            (item,),
            context_name="notes",
            operation="trace",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == MemoryReportTargetSelection(
        root_context_name="notes",
        owner_context_name="notes/child",
        memory_uid=item.uid,
        include_descendants=True,
    )


def test_report_picker_composes_the_shared_focused_frames(monkeypatch):
    item = ScopedMemoryPickerItem(
        context_name="notes",
        uid=candidate(1).uid,
        content="root Memory",
        status="CURRENT",
        catalog_context_names=("notes",),
        change_count=2,
    )
    titles: list[str] = []
    original = context_picker.build_focused_frame

    def observe_shared_frame(body, **kwargs):
        titles.append(kwargs["title"])
        return original(body, **kwargs)

    monkeypatch.setattr(
        context_picker,
        "build_focused_frame",
        observe_shared_frame,
    )
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        selected = choose_memory_report_target(
            (item,),
            context_name="notes",
            operation="trace",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is None
    assert titles == ["RANGE", "CONTEXTS & MEMORIES"]


def test_report_picker_projects_current_and_historical_as_separate_badges(
    monkeypatch,
):
    observed_rows = []

    def observe_rows(names, **kwargs):
        observed_rows.extend(kwargs["memory_loader"](names[0]))
        return None

    monkeypatch.setattr(
        "memcommit.commands.shared.memory_picker.choose_context",
        observe_rows,
    )

    selected = choose_memory_report_target(
        (
            candidate(1, change_count=2),
            candidate(2, status="HISTORICAL", change_count=3),
        ),
        context_name="notes",
        operation="trace",
        require_tty=False,
    )

    assert selected is None
    assert [
        (
            row.label,
            row.label_style,
            tuple((badge.text, badge.style) for badge in row.badges),
        )
        for row in observed_rows
    ] == [
        ("00000000", None, (("r2", None),)),
        (
            "historical",
            "historical-memory-badge",
            (("00000000", None), ("r3", None)),
        ),
    ]


def test_report_picker_rejects_context_rows_with_a_red_exact_memory_hint(
    monkeypatch,
):
    observed_receipt = None

    def observe_context_rejection(names, **kwargs):
        nonlocal observed_receipt
        observed_receipt = kwargs["context_accept_handler"](names[0])
        return None

    monkeypatch.setattr(
        "memcommit.commands.shared.memory_picker.choose_context",
        observe_context_rejection,
    )

    selected = choose_memory_report_target(
        (candidate(1, change_count=2),),
        context_name="notes",
        operation="trace",
        require_tty=False,
    )

    assert selected is None
    assert observed_receipt is not None
    assert observed_receipt.label == "CONTEXT NOT SELECTABLE"
    assert "exact Memory" in observed_receipt.detail
    assert observed_receipt.label_style == "class:memcommit.error"
    assert (
        MEMCOMMIT_TUI_STYLE.get_attrs_for_style_str(
            observed_receipt.label_style
        ).color
        == ERROR_HEX[1:]
    )


def test_report_picker_uses_shared_enter_and_vertical_surface_routing():
    item = ScopedMemoryPickerItem(
        context_name="notes/child",
        uid=candidate(1).uid,
        content="child Memory",
        status="CURRENT",
        catalog_context_names=("notes", "notes/child"),
        change_count=3,
    )
    with create_pipe_input() as pipe_input:
        # Enter toggles RANGE through the common Surface activation. Down then
        # crosses the frame boundary before visiting child and Memory rows.
        pipe_input.send_text("\r\x1b[B\x1b[B\x1b[B\r")
        selected = choose_memory_report_target(
            (item,),
            context_name="notes",
            operation="rationale",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == MemoryReportTargetSelection(
        root_context_name="notes",
        owner_context_name="notes/child",
        memory_uid=item.uid,
        include_descendants=True,
    )


def test_report_picker_keeps_exact_scope_when_opening_a_root_memory():
    item = ScopedMemoryPickerItem(
        context_name="notes",
        uid=candidate(1).uid,
        content="root Memory",
        status="CURRENT",
        catalog_context_names=("notes", "notes/child"),
        change_count=2,
    )
    with create_pipe_input() as pipe_input:
        # Tab enters the tree, then Down reaches the root's Memory.
        pipe_input.send_text("\t\x1b[B\r")
        selected = choose_memory_report_target(
            (item,),
            context_name="notes",
            operation="rationale",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == MemoryReportTargetSelection(
        root_context_name="notes",
        owner_context_name="notes",
        memory_uid=item.uid,
        include_descendants=False,
    )


def test_picker_navigation_clamps_and_supports_home_end():
    options = tuple(candidate(index) for index in range(1, 5))
    with create_pipe_input() as pipe_input:
        # End -> clamp below last -> Home -> second row -> accept.
        pipe_input.send_text("\x1b[F\x1b[B\x1b[H\x1b[B\r")
        selected = choose_memory(
            options,
            context_name="notes",
            operation="rationale",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == options[1].uid


def test_picker_uses_shared_held_arrow_rate_without_skipping_rows(monkeypatch):
    visited: list[int] = []

    class ThreeRowAccelerator:
        def move(self, direction, *, app, move_one):
            for _ in range(3):
                move_one(direction)
                visited.append(direction)
                app.invalidate()

        def reset(self):
            pass

    monkeypatch.setattr(
        context_picker,
        "NavigationAccelerator",
        ThreeRowAccelerator,
    )
    options = tuple(candidate(index) for index in range(1, 6))
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\r")
        selected = choose_memory(
            options,
            context_name="notes",
            operation="rationale",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert visited == [1, 1, 1]
    assert selected == options[2].uid


@pytest.mark.parametrize("key", ["q", "\x1b", "\x03"])
def test_picker_cancel_keys_return_no_uid(key: str):
    with create_pipe_input() as pipe_input:
        pipe_input.send_text(key)
        selected = choose_memory(
            (candidate(1),),
            context_name="notes",
            operation="trace",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is None


def test_picker_rows_escape_untrusted_content_and_mark_historical_state():
    options = (
        candidate(
            1,
            content="safe\nFAKE HEADING\u202e",
            status="HISTORICAL",
            change_count=4,
        ),
    )

    rendered = "".join(
        text
        for style, text in _render_memory_options(options, selected=0)
        if style != "[SetCursorPosition]"
    )

    assert "[historical][00000000][r4]" in rendered
    historical_style = next(
        style
        for style, text in _render_memory_options(options + (candidate(2),), selected=1)
        if text == "[historical]"
    )
    assert historical_style == "class:historical-memory-badge"
    assert (
        SEMANTIC_VIEWER_STYLE.get_attrs_for_style_str(historical_style).color
        == "c9ad93"
    )
    assert "safe\\nFAKE HEADING\\u202e" in rendered
    assert "\u202e" not in rendered


def test_picker_marks_withheld_history_instead_of_fabricating_zero_changes():
    rendered = "".join(
        text
        for style, text in _render_memory_options((candidate(1),), selected=0)
        if style != "[SetCursorPosition]"
    )

    assert "[00000000][history unavailable]" in rendered
    assert "[r0]" not in rendered


def test_unrecorded_current_gap_has_zero_recorded_changes(isolated_store):
    store = MemoryStore()
    context = ops.init("unrecorded")
    memory = ops.add(context, "Only the current file retains this.")
    store.save(context)

    candidates = collect_memory_history_candidates(
        store,
        store.load_direct(context.name),
    )

    assert [(item.uid, item.change_count) for item in candidates] == [(memory.uid, 0)]
    rendered = "".join(
        text
        for style, text in _render_memory_options(candidates, selected=0)
        if style != "[SetCursorPosition]"
    )
    assert f"[{memory.uid[:8]}][r0]" in rendered
    assert "[current" not in rendered.casefold()


def test_picker_requires_a_tty_when_requested(monkeypatch):
    monkeypatch.setattr(
        "memcommit.commands.shared.memory_picker.sys.stdin",
        io.StringIO(),
    )
    monkeypatch.setattr(
        "memcommit.commands.shared.memory_picker.sys.stdout",
        io.StringIO(),
    )

    with pytest.raises(ValueError, match="requires a terminal"):
        choose_memory(
            (candidate(1),),
            context_name="notes",
            operation="trace",
        )


def test_picker_rejects_empty_duplicate_or_invalid_inputs():
    item = candidate(1)
    with pytest.raises(ValueError, match="No current or retained"):
        choose_memory(
            (),
            context_name="notes",
            operation="trace",
            require_tty=False,
        )
    with pytest.raises(ValueError, match="duplicate"):
        choose_memory(
            (item, item),
            context_name="notes",
            operation="trace",
            require_tty=False,
        )
    with pytest.raises(ValueError, match="Context name"):
        choose_memory(
            (item,),
            context_name="",
            operation="trace",
            require_tty=False,
        )
    with pytest.raises(ValueError, match="operation"):
        choose_memory(
            (item,),
            context_name="notes",
            operation="inspect",  # type: ignore[arg-type]
            require_tty=False,
        )
