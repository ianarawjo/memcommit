"""Contracts for interactive Context selection in ``mem switch``."""
from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

from memcommit.cli import app
from memcommit.commands.context_picker import (
    _render_context_options,
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


def test_picker_renders_every_context_instead_of_a_fixed_height_slice():
    options = tuple(f"namespace/context-{index:02}" for index in range(25))

    fragments = _render_context_options(
        options,
        selected=19,
        current=options[3],
    )
    rendered_lines = "".join(
        text for style, text in fragments if style != "[SetCursorPosition]"
    ).splitlines()

    assert len(rendered_lines) == len(options)
    for option in options:
        assert sum(option in line for line in rendered_lines) == 1


def test_picker_anchors_the_viewport_at_exactly_the_selected_context():
    options = tuple(f"namespace/context-{index:02}" for index in range(25))

    fragments = _render_context_options(
        options,
        selected=19,
        current=options[3],
    )
    cursor_markers = [
        index
        for index, fragment in enumerate(fragments)
        if fragment[0] == "[SetCursorPosition]"
    ]

    assert len(cursor_markers) == 1
    selected_fragment = fragments[cursor_markers[0] + 1]
    assert selected_fragment[0] == "class:selected"
    assert selected_fragment[1].endswith(options[19])
    assert selected_fragment[1].startswith("›")


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
    assert MemoryStore().current_context_name() == (
        "organization/wiki/facilities"
    )


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
        isolated_store
        / "contexts"
        / "test"
        / "update"
        / "to"
        / "context.json"
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
