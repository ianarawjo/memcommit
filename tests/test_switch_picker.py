"""Contracts for interactive Context selection in ``mem switch``."""

from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

from memcommit.cli import app
from memcommit.commands.context_picker import (
    _CONTEXT_NAVIGATION_HINT,
    _build_context_tree,
    _context_ancestors,
    _expandable_context_subtree,
    _render_context_options,
    _render_context_roots,
    _visible_context_rows,
    choose_context,
)
from memcommit.store import MemoryStore


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
            "task-1/campus-wiki": (
                "[grant CREATE + READ + UPDATE + DELETE + QUERY]"
            ),
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
        "[grant CREATE + READ + UPDATE + DELETE + QUERY]"
        in rendered
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
                    "[grant QUERY + SAVE QUERY SESSION]"
                ),
            },
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is None


def test_picker_right_expands_then_enters_first_child():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[C\x1b[C\r")
        selected = choose_context(
            ("alpha", "alpha/child", "alpha/child/deep", "beta"),
            current="alpha",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == "alpha/child"


def test_picker_right_recursively_expands_the_selected_subtree():
    with create_pipe_input() as pipe_input:
        # Right opens alpha recursively, so two Down presses reach deep rather
        # than skipping from the one visible child to the beta root.
        pipe_input.send_text("\x1b[C\x1b[B\x1b[B\r")
        selected = choose_context(
            ("alpha", "alpha/child", "alpha/child/deep", "beta"),
            current="alpha",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == "alpha/child/deep"


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


def test_bare_switch_uses_picker_result(
    isolated_store,
    monkeypatch,
):
    invoke("init", "alpha")
    invoke("init", "beta")
    observed: dict[str, object] = {}

    def select(names, *, current):
        observed["names"] = names
        observed["current"] = current
        return "alpha"

    monkeypatch.setattr(
        "memcommit.commands.switch.choose_context",
        select,
    )

    result = invoke("switch")

    assert result.exit_code == 0
    assert "Switched to context 'alpha'" in result.output
    assert observed == {
        "names": ["alpha", "beta"],
        "current": "beta",
    }
    assert MemoryStore().current_context_name() == "alpha"


def test_bare_switch_cancel_preserves_current(
    isolated_store,
    monkeypatch,
):
    invoke("init", "alpha")
    invoke("init", "beta")
    monkeypatch.setattr(
        "memcommit.commands.switch.choose_context",
        lambda names, *, current: None,
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

    def delete_selected_then_return_it(names, *, current):
        MemoryStore().delete("alpha")
        return "alpha"

    monkeypatch.setattr(
        "memcommit.commands.switch.choose_context",
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
        "memcommit.commands.switch.choose_context",
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
