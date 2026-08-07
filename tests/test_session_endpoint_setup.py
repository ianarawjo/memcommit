from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

import memcommit.ops as ops
from memcommit.commands.endpoint_setup_flows import (
    choose_atomize_setup,
    choose_meld_setup,
    choose_update_setup,
)
from memcommit.commands.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.commands.session_endpoint_setup import (
    _confirmed_new_context_row,
    _endpoint_row_styles,
    _new_context_action_hint,
    _new_context_label_style,
)
from memcommit.store import MemoryStore


def test_horizontal_choice_clamps_and_renders_active_value():
    state = HorizontalChoiceState(
        (
            HorizontalChoiceOption("LEFT", "LEFT MODE"),
            HorizontalChoiceOption("RIGHT", "RIGHT MODE", "Right-side meaning."),
        ),
        selected_uid="LEFT",
    )

    assert state.move(-1) is False
    assert state.selected_uid == "LEFT"
    assert state.move(1) is True
    assert state.move(1) is False
    assert state.selected_uid == "RIGHT"
    focused_fragments = render_horizontal_choice(
        state,
        title="MODE",
        focused=True,
        show_description=True,
    )
    rendered = "".join(text for _style, text in focused_fragments)
    assert "[ LEFT MODE ]" in rendered
    assert "[ RIGHT MODE ]" in rendered
    assert "●" not in rendered
    assert "←/→ SELECT" in rendered
    assert "MEANING · Right-side meaning." in rendered
    assert any(
        style == "class:memcommit.choice.active.focused"
        and text == "[ RIGHT MODE ]"
        for style, text in focused_fragments
    )

    inactive_fragments = render_horizontal_choice(
        state,
        title="MODE",
        focused=False,
    )
    assert any(
        style == "class:memcommit.choice.active"
        and text == "[ RIGHT MODE ]"
        for style, text in inactive_fragments
    )


def test_horizontal_choice_can_render_each_option_as_a_focused_box():
    state = HorizontalChoiceState(
        (
            HorizontalChoiceOption("KIND", "BY KIND"),
            HorizontalChoiceOption("A_Z", "A–Z"),
        ),
        selected_uid="KIND",
    )

    fragments = render_horizontal_choice(
        state,
        title="VIEW",
        focused=True,
        boxed=True,
    )
    rendered = "".join(text for _style, text in fragments)

    assert "VIEW · ←/→ SELECT" in rendered
    assert "┏━━━━━━━━━┓" in rendered
    assert "┃ BY KIND ┃" in rendered
    assert "┌─────┐" in rendered
    assert "│ A–Z │" in rendered
    assert any(
        style == "class:memcommit.choice.border.focused" and "┏" in text
        for style, text in fragments
    )


def test_endpoint_row_keeps_selection_but_drops_cursor_when_tree_loses_focus():
    assert _endpoint_row_styles(
        cursor=True,
        chosen=True,
        tree_focused=False,
    ) == ("", "class:memcommit.choice.active")
    assert _endpoint_row_styles(
        cursor=True,
        chosen=True,
        tree_focused=True,
    ) == (
        "class:memcommit.table.selected",
        "class:memcommit.choice.active.focused",
    )
    assert _endpoint_row_styles(
        cursor=True,
        chosen=False,
        tree_focused=True,
    ) == (
        "class:memcommit.table.selected",
        "class:memcommit.table.selected",
    )


def test_create_new_context_label_has_blue_surface_only_while_focused():
    assert _new_context_label_style(focused=False) == ""
    assert _new_context_action_hint(focused=False) == ""
    assert (
        _new_context_label_style(focused=True)
        == "class:memcommit.choice.active.focused"
    )
    assert _new_context_action_hint(focused=True) == " · ENTER CONFIRM"


def test_confirmed_new_context_is_projected_back_into_endpoint_selector():
    fragments = _confirmed_new_context_row("atomize/output", anchor=True)

    assert fragments[0] == ("[SetCursorPosition]", "")
    assert "".join(text for _style, text in fragments) == (
        "    + atomize/output  NEW · NOT CREATED"
    )
    assert all(
        style == "class:memcommit.choice.active"
        for style, _text in fragments[1:]
    )


def test_fixed_update_setup_returns_both_initial_roles(isolated_store):
    store = MemoryStore()
    store.create_context(ops.init("setup/a"))
    store.create_context(ops.init("setup/b"))

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\t\t\t\r")
        receipt = choose_update_setup(
            store,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt is not None
    assert receipt.source_name == "setup/a"
    assert receipt.target_name == "setup/b"
    assert receipt.source_descendants is False
    assert receipt.target_descendants is False


def test_atomize_setup_collects_input_and_new_output(isolated_store):
    store = MemoryStore()
    store.create_context(ops.init("atomize/input"))

    with create_pipe_input() as pipe_input:
        # Input tree → Output tree ↓ editor; Enter confirms and advances.
        pipe_input.send_text("\t\x1b[Batomize/output\n\r")
        receipt = choose_atomize_setup(
            store,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt is not None
    assert receipt.input_name == "atomize/input"
    assert receipt.output_name == "atomize/output"
    assert receipt.create_output is True


def test_atomize_setup_down_enters_the_common_new_output_control(isolated_store):
    store = MemoryStore()
    store.create_context(ops.init("atomize/input"))

    with create_pipe_input() as pipe_input:
        # Output's last row ↓ NEW; ↑ returns, ↓ re-enters the editor.
        pipe_input.send_text(
            "\t\x1b[B\x1b[A\x1b[Batomize/down-output\r\r"
        )
        receipt = choose_atomize_setup(
            store,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt is not None
    assert receipt.output_name == "atomize/down-output"
    assert receipt.create_output is True


def test_atomize_setup_does_not_apply_an_unconfirmed_new_output(isolated_store):
    store = MemoryStore()
    store.create_context(ops.init("atomize/input"))

    with create_pipe_input() as pipe_input:
        # Type a name, Tab away without Enter, then try Apply before cancelling.
        pipe_input.send_text("\t\x1b[Batomize/unconfirmed\t\r\x1b")
        receipt = choose_atomize_setup(
            store,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt is None


def test_atomize_setup_allows_explicit_in_place_output(isolated_store):
    store = MemoryStore()
    store.create_context(ops.init("atomize/input"))

    with create_pipe_input() as pipe_input:
        # Input tree → Output tree (select Input) → Apply.
        pipe_input.send_text("\t\r\t\r")
        receipt = choose_atomize_setup(
            store,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt is not None
    assert receipt.input_name == "atomize/input"
    assert receipt.output_name == "atomize/input"
    assert receipt.create_output is False


def test_update_setup_toggles_each_endpoint_descendant_scope_independently(
    isolated_store,
):
    store = MemoryStore()
    store.create_context(ops.init("setup/a"))
    store.create_context(ops.init("setup/a/child"))
    store.create_context(ops.init("setup/b"))
    store.create_context(ops.init("setup/b/child"))

    with create_pipe_input() as pipe_input:
        # A tree → A checkbox (toggle) → B tree → B checkbox → Apply.
        pipe_input.send_text("\t\r\t\t\t\r")
        receipt = choose_update_setup(
            store,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt is not None
    assert receipt.source_descendants is True
    assert receipt.target_descendants is False


def test_endpoint_setup_arrows_cross_tree_and_scope_boundaries(isolated_store):
    store = MemoryStore()
    store.create_context(ops.init("nav/a"))
    store.create_context(ops.init("nav/b"))
    store.create_context(ops.init("nav/c"))

    with create_pipe_input() as pipe_input:
        # A's last row ↓ A scope ↓ B's first row, then reverse the same path.
        down = "\x1b[B"
        up = "\x1b[A"
        pipe_input.send_text(
            down * 4
            + up * 2
            + "\r"
            + down * 2
            + "\r"
            + "\t\t\r"
        )
        receipt = choose_update_setup(
            store,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt is not None
    assert receipt.source_name == "nav/c"
    assert receipt.target_name == "nav/a"


def test_meld_directional_option_has_no_third_target(isolated_store):
    store = MemoryStore()
    store.create_context(ops.init("meld-setup/a"))
    store.create_context(ops.init("meld-setup/b"))

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[C\t\t\r\t\t\r")
        receipt = choose_meld_setup(
            store,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt is not None
    assert receipt.mode == "directional"
    assert receipt.left_name != receipt.right_name
    assert receipt.target_name is None
    assert receipt.create_target is False
    assert receipt.left_descendants is True
    assert receipt.right_descendants is False


def test_meld_symmetric_mode_collects_new_result_c(isolated_store):
    store = MemoryStore()
    left = ops.init("meld-setup/a")
    right = ops.init("meld-setup/b")
    ops.add(left, "Left source")
    ops.add(right, "Right source")
    store.create_context(left)
    store.create_context(right)

    with create_pipe_input() as pipe_input:
        # Five Tabs reach C; two Downs cross its two leaves into NEW.
        pipe_input.send_text(
            "\t\t\t\t\t\x1b[B\x1b[Bfaq/result\n\r"
        )
        receipt = choose_meld_setup(
            store,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt is not None
    assert receipt.mode == "symmetric"
    assert receipt.target_name == "faq/result"
    assert receipt.create_target is True
    assert receipt.left_descendants is False
    assert receipt.right_descendants is False
