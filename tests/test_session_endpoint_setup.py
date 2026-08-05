from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

import memcommit.ops as ops
from memcommit.commands.endpoint_setup_flows import (
    choose_meld_setup,
    choose_update_setup,
)
from memcommit.commands.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.store import MemoryStore


def test_horizontal_choice_clamps_and_renders_active_value():
    state = HorizontalChoiceState(
        (
            HorizontalChoiceOption("LEFT", "LEFT MODE"),
            HorizontalChoiceOption("RIGHT", "RIGHT MODE"),
        ),
        selected_uid="LEFT",
    )

    assert state.move(-1) is False
    assert state.selected_uid == "LEFT"
    assert state.move(1) is True
    assert state.move(1) is False
    assert state.selected_uid == "RIGHT"
    rendered = "".join(
        text
        for _style, text in render_horizontal_choice(
            state,
            title="MODE",
            focused=True,
        )
    )
    assert "[  LEFT MODE]" in rendered
    assert "[● RIGHT MODE]" in rendered
    assert "←/→ SELECT" in rendered


def test_fixed_update_setup_returns_both_initial_roles(isolated_store):
    store = MemoryStore()
    store.create_context(ops.init("setup/a"))
    store.create_context(ops.init("setup/b"))

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("f")
        receipt = choose_update_setup(
            store,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt is not None
    assert receipt.source_name == "setup/a"
    assert receipt.target_name == "setup/b"


def test_meld_directional_receipt_has_no_third_target(isolated_store):
    store = MemoryStore()
    store.create_context(ops.init("meld-setup/a"))
    store.create_context(ops.init("meld-setup/b"))

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("f")
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


def test_meld_symmetric_mode_collects_new_result_c(isolated_store):
    store = MemoryStore()
    store.create_context(ops.init("meld-setup/a"))
    store.create_context(ops.init("meld-setup/b"))

    with create_pipe_input() as pipe_input:
        # Right selects symmetric. Four Tabs reach C's exact new-name editor.
        pipe_input.send_text("\x1b[C\t\t\t\tfaq/result\nf")
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
