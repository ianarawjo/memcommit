"""Contracts for interactive Context selection in ``mem switch``."""

from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.clipboard import ClipboardError
from memcommit.core.context_targeting.tui.picker import (
    ContextPickerActionReceipt,
    ContextMemorySelection,
    _CONTEXT_NAVIGATION_HINT,
    _CONTEXT_PICKER_STYLE,
    ContextTreeState,
    ContextMemoryRow,
    build_context_tree,
    context_memory_rows,
    context_option_continuation_prefixes,
    context_picker_navigation_units,
    project_context_picker_clipboard,
    _build_context_tree,
    _context_ancestors,
    _expandable_context_subtree,
    _render_context_options,
    _render_context_roots,
    _visible_context_rows,
    choose_context,
)
from memcommit.core.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.core.context_targeting.catalog import grant_navigation_annotation
from memcommit.core.context_targeting.tui.picker import (
    ContextMemoryBadge,
    ContextMemoryDetail,
    memory_visibility_key_hint,
    render_context_memory_detail,
)
from memcommit.source_projection.model import SourceForm, SourceReach, SourceState
from memcommit.persistence.store import MemoryStore


runner = CliRunner()


def invoke(*args: str):
    return runner.invoke(app, list(args))


def test_switch_help_documents_explicit_relative_navigation():
    result = invoke("switch", "--help")

    assert result.exit_code == 0
    assert "explicit lexical relative" in result.output
    assert "./child" in result.output
    assert "../sibling" in result.output


def test_picker_navigation_hint_names_expand_instead_of_tree():
    assert "←→ expand" in _CONTEXT_NAVIGATION_HINT
    assert "←→ tree" not in _CONTEXT_NAVIGATION_HINT


def test_public_context_tree_state_can_be_embedded_without_running_an_app():
    tree = build_context_tree(("alpha", "alpha/child", "alpha/child/deep", "beta"))
    state = ContextTreeState.create(tree, selected="alpha")

    state.expand_selected()
    state.expand_selected()
    state.move(2)

    assert state.selected_name == "alpha/child/deep"
    assert [row.name for row in state.visible_rows()] == [
        "alpha",
        "alpha/child",
        "alpha/child/deep",
        "beta",
    ]

    state.toggle_expand_all()
    assert state.all_expanded
    state.toggle_expand_all()
    assert not state.all_expanded
    assert state.selected_name == "alpha/child/deep"


def test_memory_visibility_hint_makes_local_and_global_scopes_explicit():
    tree = build_context_tree(("alpha", "beta"))
    state = ContextTreeState.create(tree, selected="alpha")

    assert memory_visibility_key_hint(state) == (
        "m THIS Context: show items · M EVERY Context: show items"
    )

    state.toggle_selected_memories()
    assert memory_visibility_key_hint(state) == (
        "m THIS Context: hide items · M EVERY Context: show items"
    )

    state.toggle_memories()
    assert memory_visibility_key_hint(state) == (
        "m THIS Context: hide items · M EVERY Context: hide items"
    )


def test_picker_preselects_current_and_accepts_enter():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\r")
        selected = choose_context(
            ("alpha", "beta", "gamma"),
            current="beta",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == "beta"


def test_picker_can_resume_on_one_exact_direct_item():
    rows = (
        ContextMemoryRow("first", "first", selector="first-full"),
        ContextMemoryRow("second", "second", selector="second-full"),
    )
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\r")
        selected = choose_context(
            ("alpha",),
            current="alpha",
            initial_target=ContextMemorySelection("alpha", "second-full"),
            memory_loader=lambda _name: rows,
            initially_show_memories=True,
            selectable_memories=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == ContextMemorySelection("alpha", "second-full")


def test_picker_in_place_nested_action_refreshes_without_closing():
    rows = [
        ContextMemoryRow("first", "first", selector="first-full"),
        ContextMemoryRow("second", "second", selector="second-full"),
        ContextMemoryRow("third", "third", selector="third-full"),
    ]
    accepted: list[str] = []

    def remove_row(_context_name: str, selector: str):
        accepted.append(selector)
        rows[:] = [row for row in rows if row.selector != selector]
        return ContextPickerActionReceipt(
            label="REMOVED",
            detail=selector,
            label_style="class:semantic.remove",
        )

    with create_pipe_input() as pipe_input:
        # Context -> first item -> remove; focus stays at the same row index,
        # now occupied by second. Remove again, then close the same app.
        pipe_input.send_text("\x1b[B\r\rq")
        selected = choose_context(
            ("alpha",),
            current="alpha",
            memory_loader=lambda _name: rows,
            initially_show_memories=True,
            selectable_memories=True,
            nested_accept_handler=remove_row,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
            exit_label="close",
        )

    assert selected is None
    assert accepted == ["first-full", "second-full"]
    assert [row.selector for row in rows] == ["third-full"]


def test_picker_can_reject_a_context_in_place_without_selecting_it():
    rejected: list[str] = []

    def reject_context(context_name: str):
        rejected.append(context_name)
        return ContextPickerActionReceipt(
            label="CONTEXT NOT SELECTABLE",
            detail="Select an exact Memory row.",
            label_style="class:semantic.error",
        )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\rq")
        selected = choose_context(
            ("alpha",),
            current="alpha",
            browse_only=True,
            context_accept_handler=reject_context,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is None
    assert rejected == ["alpha"]


def test_picker_moves_with_arrows_and_clamps_at_boundaries():
    with create_pipe_input() as pipe_input:
        # beta -> gamma -> beta -> alpha -> clamp at alpha -> accept
        pipe_input.send_text("\x1b[B\x1b[A\x1b[A\x1b[A\r")
        selected = choose_context(
            ("alpha", "beta", "gamma"),
            current="beta",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == "alpha"


def test_picker_starts_with_roots_and_current_ancestry_visible():
    options = (
        "granted-memory",
        "granted-memory/task-1",
        "granted-memory/task-1/participant",
        "task-1",
        "task-1/participant",
        "task-1/participant/route-changes",
        "task-2",
        "task-3",
    )
    tree = _build_context_tree(options)
    expanded = _context_ancestors(
        tree,
        "task-1/participant/route-changes",
    )

    rows = _visible_context_rows(tree, expanded)

    assert [row.name for row in rows] == [
        "granted-memory",
        "task-1",
        "task-1/participant",
        "task-1/participant/route-changes",
        "task-2",
        "task-3",
    ]
    assert [row.depth for row in rows] == [0, 0, 1, 2, 0, 0]
    assert rows[0].has_children is True
    assert rows[0].expanded is False
    assert rows[1].expanded is True
    assert rows[2].expanded is True


def test_picker_renders_tree_and_anchors_exact_selected_context():
    options = (
        "namespace",
        "namespace/child",
        "namespace/child/deep",
        "other",
    )
    tree = _build_context_tree(options)
    rows = _visible_context_rows(tree, {"namespace"})

    fragments = _render_context_options(
        rows,
        selected="namespace/child",
        current="namespace",
    )
    cursor_markers = [
        index
        for index, fragment in enumerate(fragments)
        if fragment[0] == "[SetCursorPosition]"
    ]

    assert len(cursor_markers) == 1
    selected_fragment = fragments[cursor_markers[0] + 1]
    assert selected_fragment[0] == "class:selected"
    assert selected_fragment[1].endswith("namespace/child")
    assert selected_fragment[1].startswith("›")
    rendered = "".join(
        text for style, text in fragments if style != "[SetCursorPosition]"
    )
    assert "▾ namespace" in rendered
    assert "  ▸ namespace/child" in rendered
    assert "namespace/child/deep" not in rendered


def test_picker_memory_rows_toggle_without_becoming_context_rows():
    tree = build_context_tree(("alpha", "alpha/child"))
    state = ContextTreeState.create(tree, selected="alpha")
    memories = {"alpha": (ContextMemoryRow("memory abcdef12", "first\nline"),)}

    hidden = _render_context_options(
        state.visible_rows(),
        selected="alpha",
        current="alpha",
        memories_by_context=memories,
        show_memories=state.show_memories,
    )
    state.toggle_memories()
    shown = _render_context_options(
        state.visible_rows(),
        selected="alpha",
        current="alpha",
        memories_by_context=memories,
        show_memories=state.show_memories,
    )

    assert "first" not in "".join(text for _, text in hidden)
    rendered = "".join(text for _, text in shown)
    assert "[memory abcdef12] first\\nline" in rendered
    assert [row.name for row in state.visible_rows()] == ["alpha"]


def test_switch_preview_projects_every_direct_item_in_persisted_order():
    parent = Context("parent-uid", "parent")
    owned = Memory("memory-uid", "owned Memory")
    reference = MemoryRef(
        "reference-uid",
        "source-uid",
        "source",
        owned.uid,
        target=owned,
    )
    query_view = QueryContextRef(
        "query-uid",
        "private/query-view",
        "query-source-uid",
        "test-provider",
    )
    embedded = Context("embedded-uid", "parent/embedded")
    for item in (owned, reference, query_view, embedded):
        parent.add(item)

    rows = context_memory_rows(parent)

    assert [row.label for row in rows] == [
        "memory-u",
        "referenc",
        "query-ui",
        "embedded",
    ]
    assert [row.content for row in rows] == [
        "owned Memory",
        "owned Memory",
        "private/query-view",
        "parent/embedded",
    ]
    assert [row.source.form for row in rows if row.source is not None] == [
        SourceForm.MEMORY,
        SourceForm.MEMORY_EMBED,
        SourceForm.QUERY_VIEW,
        SourceForm.CONTEXT,
    ]
    assert rows[1].source is not None
    assert rows[1].source.states == (SourceState.READ_ONLY,)
    assert rows[2].style == "report-neutral"
    assert rows[2].object_label_override == "context"
    assert tuple(
        token.text for token in rows[2].supplemental_annotations
    ) == ("QUERY ONLY",)
    assert rows[2].annotation_style == "context-query-only"
    assert rows[3].source is not None
    assert rows[3].source.reach is SourceReach.VIA_EMBED
    assert rows[3].style == "report-neutral"
    assert rows[3].annotation_style == "context-embedded"

    tree = build_context_tree((parent.name,))
    state = ContextTreeState.create(tree, selected=parent.name)
    fragments = _render_context_options(
        state.visible_rows(),
        selected=parent.name,
        current=parent.name,
        memories_by_context={parent.name: rows},
        visible_memory_contexts={parent.name},
    )
    rendered = "".join(text for _style, text in fragments)
    assert rendered.index("[memory memory-u]") < rendered.index(
        "[embedded memory referenc]"
    )
    assert rendered.index("[embedded memory referenc]") < rendered.index(
        "[context query-ui] QUERY ONLY"
    )
    assert rendered.index("[context query-ui] QUERY ONLY") < rendered.index(
        "[context embedded]"
    )
    assert "[embedded memory referenc] READ ONLY · owned Memory" in rendered
    assert "[context embedded] VIA EMBED · parent/embedded" in rendered
    assert any(
        style == "class:report-neutral" and "[context query-ui]" in text
        for style, text in fragments
    )
    assert ("class:context-query-only", "QUERY ONLY") in fragments
    assert ("class:report-neutral", "private/query-view") in fragments
    assert ("class:context-embedded", "VIA EMBED") in fragments
    assert any(
        style == "class:report-neutral" and "[context embedded]" in text
        for style, text in fragments
    )
    assert ("class:report-neutral", "parent/embedded") in fragments


def test_picker_keeps_grant_identity_neutral_and_colors_capabilities():
    tree = build_context_tree(
        ("owned", "public/shared"),
        materialized_names={"owned"},
    )
    fragments = _render_context_options(
        _visible_context_rows(tree, set()),
        selected="owned",
        current="owned",
        annotations={
            "public/shared": grant_navigation_annotation(("READ",)),
        },
    )

    assert ("class:source-ownership", "GRANT") in fragments
    assert ("class:report-neutral", "public/shared") in fragments
    assert ("class:source-capability", "READ") in fragments
    assert not any(
        style in {"class:context-embedded", "class:context-query-only"}
        for style, _text in fragments
    )
    focused_fragments = _render_context_options(
        _visible_context_rows(tree, set()),
        selected="public/shared",
        current="owned",
        annotations={
            "public/shared": grant_navigation_annotation(("READ",)),
        },
    )
    assert ("class:selected", "GRANT") in focused_fragments
    assert ("class:selected", "public/shared") in focused_fragments
    assert ("class:selected", "READ") in focused_fragments
    assert _CONTEXT_PICKER_STYLE.get_attrs_for_style_str(
        "class:source-ownership"
    ).color == "f4f5f7"
    assert _CONTEXT_PICKER_STYLE.get_attrs_for_style_str(
        "class:source-capability"
    ).color == "8bd5ca"
    assert _CONTEXT_PICKER_STYLE.get_attrs_for_style_str(
        "class:report-neutral"
    ).color == "f4f5f7"


def test_picker_navigation_interleaves_read_only_memory_viewport_units():
    tree = build_context_tree(("alpha", "alpha/child", "beta"))
    rows = _visible_context_rows(tree, {"alpha"})
    memories = {
        "alpha/child": (
            ContextMemoryRow("memory 11111111", "first"),
            ContextMemoryRow("memory 22222222", "second"),
        )
    }

    units = context_picker_navigation_units(
        rows,
        memories_by_context=memories,
        visible_memory_contexts={"alpha/child"},
    )

    assert [(unit.kind, unit.context_name, unit.memory_index) for unit in units] == [
        ("CONTEXT", "alpha", None),
        ("CONTEXT", "alpha/child", None),
        ("MEMORY", "alpha/child", 0),
        ("MEMORY", "alpha/child", 1),
        ("CONTEXT", "beta", None),
    ]


def test_picker_memory_viewport_anchor_moves_focus_bar_without_selecting():
    tree = build_context_tree(("alpha",))
    rows = _visible_context_rows(tree, set())
    memories = {
        "alpha": (
            ContextMemoryRow("memory 11111111", "first"),
            ContextMemoryRow("memory 22222222", "second"),
        )
    }

    fragments = _render_context_options(
        rows,
        selected="alpha",
        current="alpha",
        memories_by_context=memories,
        visible_memory_contexts={"alpha"},
        memory_anchor=("alpha", 1),
    )
    marker_index = next(
        index
        for index, (style, _text) in enumerate(fragments)
        if style == "[SetCursorPosition]"
    )

    assert fragments[marker_index + 1] == (
        "class:focused",
        "  · [memory 22222222] second",
    )
    assert any(
        style == "class:memory-object" and "memory 11111111" in text
        for style, text in fragments
    )
    assert all(style != "class:selected" for style, _text in fragments)
    assert all(
        style != "class:selected" or "memory" not in text for style, text in fragments
    )
    focused_style = _CONTEXT_PICKER_STYLE.get_attrs_for_style_str("class:focused")
    assert focused_style.reverse


def test_picker_renders_typed_history_section_badges_and_focused_detail():
    history = ContextMemoryRow(
        "undo",
        "2026-08-19 14:22 · restored mem remove",
        style="report-neutral",
        selector="undo-checkpoint-full",
        badges=(
            ContextMemoryBadge("CHECKPOINT undo-che"),
            ContextMemoryBadge("RECEIPT receipt-", "history-receipt"),
            ContextMemoryBadge("SOURCE remove remove-c", "history-source"),
        ),
        section_label="DIRECT COMMANDS · practice/2",
        detail_title="UNDO · restored mem remove",
        details=(
            ContextMemoryDetail("Checkpoint", "undo-checkpoint-full"),
            ContextMemoryDetail(
                "Receipt",
                "receipt-full-uid",
                "history-receipt",
            ),
        ),
    )
    tree = build_context_tree(("practice/2",))
    fragments = _render_context_options(
        _visible_context_rows(tree, {"practice/2"}),
        selected="practice/2",
        current="practice/2",
        memories_by_context={"practice/2": (history,)},
        visible_memory_contexts={"practice/2"},
        memory_anchor=("practice/2", 0),
        selectable_memories=True,
    )
    rendered = "".join(text for _style, text in fragments)

    assert rendered.index("DIRECT COMMANDS · practice/2") < rendered.index(
        "[undo] [CHECKPOINT undo-che] [RECEIPT receipt-]"
    )
    detail = render_context_memory_detail(history)
    assert "".join(text for _style, text in detail) == (
        " SELECTED COMMAND · UNDO · restored mem remove\n"
        " Checkpoint  undo-checkpoint-full\n"
        " Receipt     receipt-full-uid"
    )
    assert ("class:history-receipt", "receipt-full-uid") in detail


def test_picker_selectable_memory_uses_pointer_and_returns_exact_receipt():
    memory = ContextMemoryRow(
        "memory abcdef12",
        "delete this",
        selector="abcdef12-1111-1111-1111-111111111111",
    )
    tree = build_context_tree(("alpha",))
    fragments = _render_context_options(
        _visible_context_rows(tree, set()),
        selected="alpha",
        current="alpha",
        memories_by_context={"alpha": (memory,)},
        visible_memory_contexts={"alpha"},
        memory_anchor=("alpha", 0),
        selectable_memories=True,
    )

    assert any("› [memory abcdef12] delete this" in text for _, text in fragments)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\r")
        selected = choose_context(
            ("alpha",),
            current="alpha",
            memory_loader=lambda _name: (memory,),
            initially_show_memories=True,
            selectable_memories=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == ContextMemorySelection(
        context_name="alpha",
        selector=memory.selector,
    )


def test_picker_rejects_selectable_memories_without_a_loader():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        try:
            choose_context(
                ("alpha",),
                current="alpha",
                selectable_memories=True,
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )
        except ValueError as error:
            assert "require a Memory loader" in str(error)
        else:  # pragma: no cover - assertion aid
            raise AssertionError("missing Memory loader was accepted")


def test_picker_wraps_memory_content_with_a_hanging_selector_indent():
    tree = build_context_tree(("alpha", "alpha/child"))
    rows = _visible_context_rows(tree, {"alpha"})
    memories = {
        "alpha/child": (
            ContextMemoryRow(
                "memory abcdef12",
                "A long participant-facing description that must wrap.",
            ),
        )
    }

    prefixes = context_option_continuation_prefixes(
        rows,
        memories_by_context=memories,
        visible_memory_contexts=frozenset({"alpha/child"}),
    )

    assert prefixes[0] == " " * 6
    assert prefixes[1] == " " * 8
    assert prefixes[2] == " " * len("    · [memory abcdef12] ")


def test_picker_wraps_memory_preview_at_spaces_before_character_boundaries():
    tree = build_context_tree(("task-1", "task-1/description"))
    rows = _visible_context_rows(tree, {"task-1"})
    memories = {
        "task-1/description": (
            ContextMemoryRow(
                "memory 2db26309",
                "Imagine that you are a campus facilities coordinator "
                "responsible for maintaining a university organizational wiki.",
            ),
        )
    }

    fragments = _render_context_options(
        rows,
        selected="task-1/description",
        current="task-1",
        memories_by_context=memories,
        visible_memory_contexts={"task-1/description"},
        wrap_width=79,
        memory_anchor=("task-1/description", 0),
    )
    rendered = "".join(text for _, text in fragments)
    memory_lines = rendered.splitlines()[2:]

    assert memory_lines[0].endswith("facilities coordinator")
    assert memory_lines[1] == (" " * 24 + "responsible for maintaining a university")
    assert memory_lines[2] == " " * 24 + "organizational wiki."
    assert "coordinator re\n" not in rendered
    assert sum(style == "class:focused" for style, _text in fragments) == 3


def test_picker_memory_clipboard_projection_is_one_logical_line():
    tree = build_context_tree(("task-1", "task-1/description"))
    rows = _visible_context_rows(tree, {"task-1"})
    memories = {
        "task-1/description": (
            ContextMemoryRow(
                "memory 2db26309",
                "Imagine that you are a campus facilities coordinator\n"
                "responsible   for maintaining the wiki.",
            ),
        )
    }

    projection = project_context_picker_clipboard(
        rows,
        selected="task-1/description",
        current="task-1",
        memories_by_context=memories,
        visible_memory_contexts={"task-1/description"},
        memory_anchor=("task-1/description", 0),
    )

    assert projection.scope == "ITEM"
    assert projection.context_count == 0
    assert projection.memory_count == 1
    assert projection.text == (
        "    · [memory 2db26309] Imagine that you are a campus facilities "
        "coordinator responsible for maintaining the wiki."
    )
    assert "\n" not in projection.text


def test_picker_context_clipboard_item_and_visible_branch_are_distinct():
    tree = build_context_tree(
        (
            "task-1",
            "task-1/description",
            "task-1/participant",
            "task-1/participant/route-changes",
            "task-1/campus-wiki",
            "task-2",
        )
    )
    rows = _visible_context_rows(tree, {"task-1"})
    memories = {
        "task-1/description": (
            ContextMemoryRow(
                "memory 2db26309",
                "A long description\nthat must remain one clipboard line.",
            ),
        )
    }
    common = {
        "selected": "task-1",
        "current": "task-1/participant",
        "annotations": {
            "task-1/campus-wiki": grant_navigation_annotation(("READ", "EXPORT")),
        },
        "memories_by_context": memories,
        "visible_memory_contexts": {"task-1/description"},
    }

    item = project_context_picker_clipboard(rows, visible_branch=False, **common)
    branch = project_context_picker_clipboard(rows, visible_branch=True, **common)

    assert item.scope == "ITEM"
    assert item.context_count == 1
    assert item.memory_count == 0
    assert item.text == "›   ▾ task-1"
    assert branch.scope == "VISIBLE_BRANCH"
    assert branch.context_count == 4
    assert branch.memory_count == 1
    assert branch.text.splitlines() == [
        "›   ▾ task-1",
        "      ▾ task-1/description",
        "    · [memory 2db26309] A long description that must remain one clipboard line.",
        "  *   ▸ task-1/participant",
        "      ▸ GRANT task-1/campus-wiki  READ + EXPORT",
    ]
    assert "task-1/participant/route-changes" not in branch.text
    assert "task-2" not in branch.text


def test_picker_y_copies_the_focused_context_without_closing():
    copied: list[str] = []
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("yq")
        selected = choose_context(
            ("alpha", "beta"),
            current="alpha",
            clipboard_writer=copied.append,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is None
    assert copied == ["› * · alpha"]


def test_picker_uppercase_y_copies_only_the_focused_visible_branch():
    copied: list[str] = []
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[CYq")
        selected = choose_context(
            ("alpha", "alpha/child", "alpha/child/deep", "beta"),
            current="alpha",
            clipboard_writer=copied.append,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is None
    assert copied == ["› * ▾ alpha\n      ▸ alpha/child"]
    assert "alpha/child/deep" not in copied[0]
    assert "beta" not in copied[0]


def test_picker_y_and_uppercase_y_match_for_a_focused_memory():
    copied: list[str] = []
    memory = ContextMemoryRow("memory abcdef12", "first\nsecond")
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[ByYq")
        selected = choose_context(
            ("alpha",),
            current="alpha",
            memory_loader=lambda _name: (memory,),
            initially_show_memories=True,
            clipboard_writer=copied.append,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is None
    assert copied == [
        "  · [memory abcdef12] first second",
        "  · [memory abcdef12] first second",
    ]


def test_picker_clipboard_failure_keeps_the_picker_open_for_cancellation():
    attempts: list[str] = []

    def fail_copy(text: str) -> None:
        attempts.append(text)
        raise ClipboardError("simulated clipboard unavailable")

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("yq")
        selected = choose_context(
            ("alpha",),
            current="alpha",
            clipboard_writer=fail_copy,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is None
    assert attempts == ["› * · alpha"]


def test_picker_leaf_uses_expand_marker_for_its_memory_layer():
    tree = build_context_tree(("alpha",))
    state = ContextTreeState.create(tree, selected="alpha")
    memories = {"alpha": (ContextMemoryRow("memory abcdef12", "content"),)}

    hidden = "".join(
        text
        for _, text in _render_context_options(
            state.visible_rows(),
            selected="alpha",
            current="alpha",
            memories_by_context=memories,
            visible_memory_contexts=frozenset(),
        )
    )
    state.expand_selected(include_leaf_memories=True)
    shown = "".join(
        text
        for _, text in _render_context_options(
            state.visible_rows(),
            selected="alpha",
            current="alpha",
            memories_by_context=memories,
            visible_memory_contexts=frozenset({"alpha"}),
        )
    )

    assert "▸ alpha" in hidden
    assert "▾ alpha" in shown
    assert "[memory abcdef12] content" in shown

    state.collapse_selected(include_leaf_memories=True)
    assert state.memories_visible_for("alpha") is False


def test_picker_leaf_memory_collapse_precedes_moving_to_parent():
    tree = build_context_tree(("alpha", "alpha/child"))
    state = ContextTreeState.create(tree, selected="alpha/child")
    state.show_memories = True

    state.collapse_selected(include_leaf_memories=True)
    assert state.selected_name == "alpha/child"
    assert state.memories_visible_for("alpha/child") is False

    state.collapse_selected(include_leaf_memories=True)
    assert state.selected_name == "alpha"


def test_picker_can_toggle_memories_for_only_the_selected_context():
    tree = build_context_tree(("alpha", "beta"))
    state = ContextTreeState.create(tree, selected="alpha")
    state.show_memories = True

    state.toggle_selected_memories()

    assert state.memories_visible_for("alpha") is False
    assert state.memories_visible_for("beta") is True
    state.selected_name = "beta"
    state.toggle_selected_memories()
    assert state.memories_visible_for("alpha") is False
    assert state.memories_visible_for("beta") is False

    state.toggle_memories()
    assert state.show_memories is False
    assert state.memory_visibility_overrides == {}


def test_picker_lowercase_m_loads_only_selected_context_memories():
    loaded: list[str] = []

    def load(name: str):
        loaded.append(name)
        return (ContextMemoryRow("memory abcdef12", "content"),)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("m\r")
        selected = choose_context(
            ("alpha", "beta"),
            current="alpha",
            memory_loader=load,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == "alpha"
    assert loaded == ["alpha"]


def test_picker_m_loads_visible_memories_and_still_accepts_context():
    loaded: list[str] = []

    def load(name: str):
        loaded.append(name)
        return (ContextMemoryRow("memory abcdef12", "content"),)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("M\r")
        selected = choose_context(
            ("alpha", "beta"),
            current="alpha",
            memory_loader=load,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == "alpha"
    assert loaded == ["alpha", "beta"]


def test_picker_pins_all_root_names_above_a_scrolled_current_branch():
    tree = _build_context_tree(
        (
            "granted-memory",
            "granted-memory/task-1",
            "task-1",
            "task-2",
            "task-3",
        )
    )

    assert _render_context_roots(tree) == (
        " Roots · granted-memory · task-1 · task-2 · task-3"
    )


def test_picker_does_not_invent_missing_namespace_parents():
    tree = _build_context_tree(("missing/parent/leaf", "root"))

    rows = _visible_context_rows(tree, set())

    assert [(row.name, row.depth) for row in rows] == [
        ("missing/parent/leaf", 0),
        ("root", 0),
    ]
    assert all(row.materialized for row in rows)
    assert "missing" not in tree.parent_by_name
    assert "missing/parent" not in tree.parent_by_name


def test_picker_renders_granted_views_below_owned_task_without_selecting_them():
    tree = _build_context_tree(
        (
            "task-1",
            "task-1/participant",
            "task-1/campus-wiki",
            "task-1/campus-wiki/route-changes",
        ),
        materialized_names={"task-1", "task-1/participant"},
    )
    rows = _visible_context_rows(
        tree,
        {"task-1", "task-1/campus-wiki"},
    )
    fragments = _render_context_options(
        rows,
        selected="task-1/campus-wiki",
        current="task-1/participant",
        annotations={
            "task-1/campus-wiki": ("[grant CREATE + READ + UPDATE + DELETE + QUERY]"),
            "task-1/campus-wiki/route-changes": (
                "[grant CREATE + READ + UPDATE + DELETE + QUERY]"
            ),
        },
    )
    rendered = "".join(
        text for style, text in fragments if style != "[SetCursorPosition]"
    )

    assert (
        "task-1/campus-wiki  [grant CREATE + READ + UPDATE + DELETE + QUERY]"
        in rendered
    )
    assert (
        "task-1/campus-wiki/route-changes  "
        "[grant CREATE + READ + UPDATE + DELETE + QUERY]" in rendered
    )
    assert "[unavailable]" not in rendered
    assert "task-1/campus-wiki" not in tree.materialized_names


def test_picker_can_select_an_orphaned_real_context_without_virtual_parents():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\r")
        selected = choose_context(
            ("missing/parent/leaf", "root"),
            current="missing/parent/leaf",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == "missing/parent/leaf"


def test_picker_enter_selects_a_read_granted_virtual_context():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\r")
        selected = choose_context(
            ("task-2",),
            current="task-2/advisor1",
            virtual_names=("task-2/advisor1",),
            selectable_virtual_names={"task-2/advisor1"},
            virtual_annotations={
                "task-2/advisor1": "[grant READ]",
            },
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == "task-2/advisor1"


def test_picker_enter_does_not_select_a_query_only_virtual_context():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\rq")
        selected = choose_context(
            ("task-2",),
            current="task-2/proposal-submission-guidelines",
            virtual_names=("task-2/proposal-submission-guidelines",),
            virtual_annotations={
                "task-2/proposal-submission-guidelines": (
                    "[grant QUERY]"
                ),
            },
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is None


def test_picker_right_expands_then_enters_first_child():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[C\x1b[C\x1b[C\r")
        selected = choose_context(
            ("alpha", "alpha/child", "alpha/child/deep", "beta"),
            current="alpha",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == "alpha/child"


def test_picker_right_expands_the_selected_subtree_one_depth_at_a_time():
    with create_pipe_input() as pipe_input:
        # The first Right reveals direct children and the second reveals their
        # children. Two Down presses can reach deep only after both levels.
        pipe_input.send_text("\x1b[C\x1b[C\x1b[B\x1b[B\r")
        selected = choose_context(
            ("alpha", "alpha/child", "alpha/child/deep", "beta"),
            current="alpha",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == "alpha/child/deep"


def test_context_tree_state_expands_and_collapses_one_complete_depth_per_key():
    tree = build_context_tree(
        (
            "1",
            "1/1",
            "1/1/1",
            "1/1/2",
            "1/1/3",
            "1/1/3/1",
            "1/2",
            "1/3",
            "1/4",
        )
    )
    state = ContextTreeState.create(tree, selected="1")

    state.expand_selected()
    assert [row.name for row in state.visible_rows()] == [
        "1",
        "1/1",
        "1/2",
        "1/3",
        "1/4",
    ]

    state.expand_selected()
    assert [row.name for row in state.visible_rows()] == [
        "1",
        "1/1",
        "1/1/1",
        "1/1/2",
        "1/1/3",
        "1/2",
        "1/3",
        "1/4",
    ]

    state.expand_selected()
    assert [row.name for row in state.visible_rows()] == [
        "1",
        "1/1",
        "1/1/1",
        "1/1/2",
        "1/1/3",
        "1/1/3/1",
        "1/2",
        "1/3",
        "1/4",
    ]

    state.collapse_selected()
    assert "1/1/3/1" not in [row.name for row in state.visible_rows()]
    state.collapse_selected()
    assert [row.name for row in state.visible_rows()] == [
        "1",
        "1/1",
        "1/2",
        "1/3",
        "1/4",
    ]
    state.collapse_selected()
    assert [row.name for row in state.visible_rows()] == ["1"]


def test_expandable_context_subtree_includes_every_nested_branch():
    tree = _build_context_tree(
        (
            "alpha",
            "alpha/child",
            "alpha/child/deep",
            "alpha/sibling",
            "beta",
        )
    )

    expanded = _expandable_context_subtree(tree, "alpha")
    rows = _visible_context_rows(tree, expanded)

    assert expanded == {"alpha", "alpha/child"}
    assert [row.name for row in rows] == [
        "alpha",
        "alpha/child",
        "alpha/child/deep",
        "alpha/sibling",
        "beta",
    ]
    assert [row.expanded for row in rows] == [True, True, False, False, False]


def test_picker_left_moves_to_parent_then_collapses_it():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[D\x1b[D\x1b[B\r")
        selected = choose_context(
            ("alpha", "alpha/child", "beta"),
            current="alpha/child",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == "beta"


def test_picker_a_expands_every_branch():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("A\x1b[B\x1b[B\r")
        selected = choose_context(
            ("alpha", "alpha/child", "alpha/child/deep", "beta"),
            current="alpha",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == "alpha/child/deep"


def test_picker_second_a_restores_the_compact_tree():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("AA\x1b[B\r")
        selected = choose_context(
            ("alpha", "alpha/child", "beta"),
            current="alpha",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == "beta"


def test_picker_restore_keeps_a_selection_from_expand_all_visible():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("A\x1b[B\x1b[BA\x1b[A\r")
        selected = choose_context(
            ("alpha", "alpha/child", "alpha/child/deep", "beta"),
            current="alpha",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == "alpha/child"


def test_picker_cancels_without_a_selection():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        selected = choose_context(
            ("alpha", "beta"),
            current="alpha",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is None


def test_picker_browse_mode_never_returns_the_focused_context():
    with create_pipe_input() as pipe_input:
        # Enter expands the focused branch; only the later q closes the view.
        pipe_input.send_text("\rq")
        selected = choose_context(
            ("alpha", "alpha/child", "beta"),
            current="alpha",
            browse_only=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is None


def test_bare_switch_uses_picker_result(
    isolated_store,
    monkeypatch,
):
    invoke("init", "alpha")
    invoke("init", "beta")
    observed: dict[str, object] = {}

    def select(names, *, current, accept_label, memory_loader):
        observed["names"] = names
        observed["current"] = current
        observed["accept_label"] = accept_label
        observed["memory_loader"] = memory_loader
        return "alpha"

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.switch.command.choose_context",
        select,
    )

    result = invoke("switch")

    assert result.exit_code == 0
    assert "Switched to context 'alpha'" in result.output
    assert observed["names"] == ["alpha", "beta"]
    assert observed["current"] == "beta"
    assert observed["accept_label"] == "switch"
    assert callable(observed["memory_loader"])
    assert MemoryStore().current_context_name() == "alpha"


def test_bare_checkout_uses_the_same_switch_picker(
    isolated_store,
    monkeypatch,
):
    invoke("init", "alpha")
    invoke("init", "beta")
    observed: dict[str, object] = {}

    def select(names, *, current, accept_label, memory_loader):
        observed["names"] = names
        observed["current"] = current
        observed["accept_label"] = accept_label
        return "alpha"

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.switch.command.choose_context",
        select,
    )

    result = invoke("checkout")

    assert result.exit_code == 0
    assert "Switched to context 'alpha'" in result.output
    assert observed == {
        "names": ["alpha", "beta"],
        "current": "beta",
        "accept_label": "switch",
    }
    assert MemoryStore().current_context_name() == "alpha"


def test_bare_switch_cancel_preserves_current(
    isolated_store,
    monkeypatch,
):
    invoke("init", "alpha")
    invoke("init", "beta")
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.switch.command.choose_context",
        lambda names, *, current, accept_label, memory_loader: None,
    )

    result = invoke("switch")

    assert result.exit_code == 0
    assert "Switch cancelled" in result.output
    assert MemoryStore().current_context_name() == "beta"


def test_picker_result_is_revalidated_before_switch(
    isolated_store,
    monkeypatch,
):
    invoke("init", "alpha")
    invoke("init", "beta")

    def delete_selected_then_return_it(names, *, current, accept_label, memory_loader):
        MemoryStore().delete("alpha")
        return "alpha"

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.switch.command.choose_context",
        delete_selected_then_return_it,
    )

    result = invoke("switch")

    assert result.exit_code == 1
    assert "does not exist" in result.output
    assert MemoryStore().current_context_name() == "beta"


def test_bare_switch_requires_a_tty_without_a_mock_picker(isolated_store):
    invoke("init", "alpha")

    result = invoke("switch")

    assert result.exit_code == 1
    assert "requires a terminal" in result.output
    assert MemoryStore().current_context_name() == "alpha"


def test_bare_switch_reports_an_empty_store(isolated_store):
    result = invoke("switch")

    assert result.exit_code == 1
    assert "no contexts exist" in result.output


def test_explicit_switch_remains_noninteractive(
    isolated_store,
    monkeypatch,
):
    invoke("init", "alpha")
    invoke("init", "beta")

    def unexpected_picker(*args, **kwargs):
        raise AssertionError("explicit switch must not open the picker")

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.switch.command.choose_context",
        unexpected_picker,
    )

    result = invoke("switch", "alpha")

    assert result.exit_code == 0
    assert MemoryStore().current_context_name() == "alpha"


def test_switch_dot_dot_moves_to_existing_lexical_namespace_parent(
    isolated_store,
):
    invoke("init", "organization/wiki")
    invoke("init", "organization/wiki/facilities")

    result = invoke("switch", "..")

    assert result.exit_code == 0
    assert "Switched to context 'organization/wiki'." in result.output
    assert MemoryStore().current_context_name() == "organization/wiki"


def test_switch_dot_dot_without_current_context_preserves_state(
    isolated_store,
):
    result = invoke("switch", "..")

    assert result.exit_code == 1
    assert "no current context is set" in result.output
    assert MemoryStore().current_context_name() is None


def test_switch_dot_dot_from_root_context_preserves_state(
    isolated_store,
):
    invoke("init", "campus")

    result = invoke("switch", "..")

    assert result.exit_code == 1
    assert "context 'campus' has no namespace parent" in result.output
    assert MemoryStore().current_context_name() == "campus"


def test_switch_dot_dot_requires_exact_parent_context(
    isolated_store,
):
    invoke("init", "organization/wiki")

    result = invoke("switch", "..")

    assert result.exit_code == 1
    assert "namespace parent context 'organization' does not exist" in result.output
    assert MemoryStore().current_context_name() == "organization/wiki"


def test_switch_dot_dot_does_not_infer_an_embedding_parent(
    isolated_store,
):
    invoke("init", "container")
    invoke("init", "topic/leaf")
    embedded = invoke("embed", "topic/leaf", "--into", "container")
    assert embedded.exit_code == 0
    invoke("switch", "topic/leaf")

    result = invoke("switch", "..")

    assert result.exit_code == 1
    assert "namespace parent context 'topic' does not exist" in result.output
    assert MemoryStore().current_context_name() == "topic/leaf"


def test_switch_dot_keeps_the_current_context(isolated_store):
    invoke("init", "organization/wiki")

    result = invoke("switch", ".")

    assert result.exit_code == 0
    assert "Already on 'organization/wiki'." in result.output
    assert MemoryStore().current_context_name() == "organization/wiki"


def test_switch_dot_child_resolves_below_current_context(isolated_store):
    invoke("init", "organization/wiki")
    invoke("init", "organization/wiki/facilities")
    invoke("switch", "organization/wiki")

    result = invoke("switch", "./facilities")

    assert result.exit_code == 0
    assert "Switched to context 'organization/wiki/facilities'." in result.output
    assert MemoryStore().current_context_name() == ("organization/wiki/facilities")


def test_switch_dot_dot_sibling_resolves_from_current_parent(
    isolated_store,
):
    invoke("init", "test/update/from")
    invoke("init", "test/update/to")
    invoke("switch", "test/update/from")

    result = invoke("switch", "../to")

    assert result.exit_code == 0
    assert "Switched to context 'test/update/to'." in result.output
    assert MemoryStore().current_context_name() == "test/update/to"


def test_switch_relative_trailing_slash_names_the_same_node(
    isolated_store,
):
    invoke("init", "test/update")
    invoke("init", "test/update/from")

    parent = invoke("switch", "../")
    current = invoke("switch", "./")

    assert parent.exit_code == 0
    assert "Switched to context 'test/update'." in parent.output
    assert current.exit_code == 0
    assert "Already on 'test/update'." in current.output
    assert MemoryStore().current_context_name() == "test/update"


def test_switch_relative_rejects_repeated_slash(isolated_store):
    invoke("init", "test/update/from")

    result = invoke("switch", "..//to")

    assert result.exit_code == 1
    assert "contains an empty segment" in result.output
    assert MemoryStore().current_context_name() == "test/update/from"


def test_switch_chained_relative_parent_segments(isolated_store):
    invoke("init", "test/update/from")
    invoke("init", "test/archive")
    invoke("switch", "test/update/from")

    result = invoke("switch", "../../archive")

    assert result.exit_code == 0
    assert "Switched to context 'test/archive'." in result.output
    assert MemoryStore().current_context_name() == "test/archive"


def test_switch_relative_selector_rejects_escape_above_namespace_root(
    isolated_store,
):
    invoke("init", "test/update")

    result = invoke("switch", "../../../outside")

    assert result.exit_code == 1
    assert "escapes above the namespace root" in result.output
    assert MemoryStore().current_context_name() == "test/update"


def test_switch_relative_selector_requires_current_context(isolated_store):
    result = invoke("switch", "./child")

    assert result.exit_code == 1
    assert "cannot switch to './child': no current context is set" in result.output
    assert MemoryStore().current_context_name() is None


def test_switch_missing_relative_target_preserves_current(isolated_store):
    invoke("init", "test/update/from")

    result = invoke("switch", "../missing")

    assert result.exit_code == 1
    assert "context 'test/update/missing' does not exist" in result.output
    assert MemoryStore().current_context_name() == "test/update/from"


def test_switch_unloadable_relative_target_preserves_current(isolated_store):
    invoke("init", "test/update")
    invoke("init", "test/update/to")
    invoke("switch", "test/update")
    target_file = (
        isolated_store / "contexts" / "test" / "update" / "to" / "context.json"
    )
    target_file.write_text("{not-json", encoding="utf-8")

    result = invoke("switch", "./to")

    assert result.exit_code == 1
    assert "cannot switch to context 'test/update/to'" in result.output
    assert MemoryStore().current_context_name() == "test/update"


def test_switch_malformed_relative_selector_preserves_current(isolated_store):
    invoke("init", "test/update")

    result = invoke("switch", "./child//leaf")

    assert result.exit_code == 1
    assert "contains an empty segment" in result.output
    assert MemoryStore().current_context_name() == "test/update"


def test_bare_name_remains_canonical_global_not_relative(isolated_store):
    invoke("init", "child")
    invoke("init", "organization/wiki")
    invoke("init", "organization/wiki/child")
    invoke("switch", "organization/wiki")

    result = invoke("switch", "child")

    assert result.exit_code == 0
    assert "Switched to context 'child'." in result.output
    assert MemoryStore().current_context_name() == "child"


def test_switch_does_not_overwrite_a_concurrent_current_change(
    isolated_store,
    monkeypatch,
):
    invoke("init", "test/update/from")
    invoke("init", "test/update/to")
    invoke("init", "other")
    invoke("switch", "test/update/from")
    original_switch = MemoryStore.set_current_context_if

    def switch_elsewhere_then_compare_and_set(
        self,
        expected_current,
        name,
        *,
        expected_context_uid,
        expected_context_digest,
    ):
        self.set_current("other")
        return original_switch(
            self,
            expected_current,
            name,
            expected_context_uid=expected_context_uid,
            expected_context_digest=expected_context_digest,
        )

    monkeypatch.setattr(
        MemoryStore,
        "set_current_context_if",
        switch_elsewhere_then_compare_and_set,
    )

    result = invoke("switch", "../to")

    assert result.exit_code == 1
    assert "current Context changed" in result.output
    assert MemoryStore().current_context_name() == "other"


def test_switch_rejects_a_target_changed_before_final_selection(
    isolated_store,
    monkeypatch,
):
    invoke("init", "test/update/from")
    invoke("init", "test/update/to")
    invoke("switch", "test/update/from")
    original_switch = MemoryStore.set_current_context_if

    def change_target_then_compare_and_set(
        self,
        expected_current,
        name,
        *,
        expected_context_uid,
        expected_context_digest,
    ):
        changed = self.load_direct(name)
        changed.add("concurrent change")
        self.save(changed)
        return original_switch(
            self,
            expected_current,
            name,
            expected_context_uid=expected_context_uid,
            expected_context_digest=expected_context_digest,
        )

    monkeypatch.setattr(
        MemoryStore,
        "set_current_context_if",
        change_target_then_compare_and_set,
    )

    result = invoke("switch", "../to")

    assert result.exit_code == 1
    assert "changed before it could be selected" in result.output
    assert MemoryStore().current_context_name() == "test/update/from"
