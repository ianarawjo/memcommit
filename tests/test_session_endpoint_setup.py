from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
import pytest

import memcommit.application.ops as ops
import memcommit.commands.shared.endpoint_setup_flows as endpoint_setup_flows
import memcommit.commands.meld.setup as meld_setup_command
from memcommit.commands.compare.setup import choose_compare_setup
from memcommit.commands.shared.endpoint_setup_flows import (
    choose_atomize_setup,
    choose_meld_setup,
    choose_update_setup,
)
from memcommit.commands.shared.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.commands.shared.session_endpoint_setup import (
    EndpointModeSpec,
    EndpointRoleSpec,
    _confirmed_new_context_row,
    _endpoint_checked_names,
    _endpoint_row_styles,
    _new_context_action_hint,
    _new_context_label_style,
    choose_session_endpoints,
)
from memcommit.adapters.interfaces.tui.operations.meld import MeldEndpointSelection
from memcommit.commands.shared.context_picker import ContextMemoryRow, context_memory_rows
from memcommit.context_targeting.tui.reach import ContextReachState
from memcommit.context_targeting.tui.selection import ContextSelectionState
from memcommit.context_targeting.tui.tree import ContextTreeState, build_context_tree
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
        style == "class:memcommit.choice.active.focused" and text == "[ RIGHT MODE ]"
        for style, text in focused_fragments
    )

    inactive_fragments = render_horizontal_choice(
        state,
        title="MODE",
        focused=False,
    )
    assert any(
        style == "class:memcommit.choice.active" and text == "[ RIGHT MODE ]"
        for style, text in inactive_fragments
    )


def test_horizontal_choice_can_choose_an_exact_typed_value():
    state = HorizontalChoiceState(
        (
            HorizontalChoiceOption("ORDINARY", "CONTEXTS"),
            HorizontalChoiceOption("GRANTED", "QUERY-ONLY VIEW"),
        ),
        selected_uid="ORDINARY",
    )

    assert state.choose("GRANTED") is True
    assert state.selected_uid == "GRANTED"
    assert state.selected_index == 1
    assert state.choose("GRANTED") is False

    with pytest.raises(ValueError, match="unavailable"):
        state.choose("MISSING")


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
    assert "┏━━━━━━━━━━━┓" in rendered
    assert "┃ ✓ BY KIND ┃" in rendered
    assert "┌───────┐" in rendered
    assert "│   A–Z │" in rendered
    assert any(
        style == "class:memcommit.choice.border.focused" and "┏" in text
        for style, text in fragments
    )

    state.move(1)
    inactive = render_horizontal_choice(
        state,
        title="VIEW",
        focused=False,
        boxed=True,
    )
    inactive_text = "".join(text for _style, text in inactive)
    assert "│   BY KIND │" in inactive_text
    assert "│ ✓ A–Z │" in inactive_text


def test_horizontal_choice_can_render_checked_boxes_on_one_line():
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
        inline_boxed=True,
    )
    rendered = "".join(text for _style, text in fragments)

    assert rendered == "› VIEW · [ ✓ BY KIND ]  [   A–Z ] · ←/→ TO SELECT"
    assert "\n" not in rendered
    assert any(
        style == "class:memcommit.choice.active.focused" and text == " ✓ BY KIND "
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


def test_endpoint_checked_rows_project_the_selected_descendant_range():
    names = ("task", "task/a", "task/a/deep", "other")
    tree = ContextTreeState.create(build_context_tree(names), selected="task")
    selection = ContextSelectionState.create(
        names,
        selected=("task",),
        mode="SINGLE",
    )
    reach = ContextReachState.create(include_descendants=True)

    assert _endpoint_checked_names(
        tree,
        selection,
        reach,
        descendants_active=True,
        selectable_names=frozenset(names),
        existing_selected=True,
    ) == frozenset({"task", "task/a", "task/a/deep"})
    assert _endpoint_checked_names(
        tree,
        selection,
        reach,
        descendants_active=False,
        selectable_names=frozenset(names),
        existing_selected=True,
    ) == frozenset({"task"})
    assert not _endpoint_checked_names(
        tree,
        selection,
        reach,
        descendants_active=True,
        selectable_names=frozenset(names),
        existing_selected=False,
    )


def test_common_endpoint_memory_preview_cannot_choose_its_parent_context():
    loaded: list[str] = []

    def load(name: str):
        loaded.append(name)
        return (ContextMemoryRow("memory abcdef12", f"{name} content"),)

    with create_pipe_input() as pipe_input:
        # Open alpha's Memory, enter its read-only row, then Apply. If Enter
        # leaked through to endpoint selection it would replace the staged new
        # Context with alpha.
        pipe_input.send_text("m\x1b[B\r\t\r")
        draft = choose_session_endpoints(
            ("alpha", "beta"),
            title="MEMORY PREVIEW TEST",
            modes=(
                EndpointModeSpec(
                    "TEST",
                    "A → B",
                    ("A",),
                    {"A": "A · ENDPOINT"},
                ),
            ),
            roles=(
                EndpointRoleSpec(
                    "A",
                    frozenset({"alpha", "beta"}),
                    "alpha",
                    allow_new=True,
                    initial_new_name="new-output",
                    prefer_new=True,
                ),
            ),
            initial_mode_uid="TEST",
            memory_loader=load,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert draft is not None
    assert draft.value("A").context_name == "new-output"
    assert draft.value("A").create is True
    assert loaded == ["alpha"]


def test_common_endpoint_selectable_memory_returns_exact_typed_value():
    memory_uid = "abcdef12-1111-4111-8111-111111111111"

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("m\x1b[B\r\t\r")
        draft = choose_session_endpoints(
            ("alpha",),
            title="SELECTABLE MEMORY TEST",
            modes=(
                EndpointModeSpec(
                    "TEST",
                    "A",
                    ("A",),
                    {"A": "A"},
                    memory_focus_roles=frozenset({"A"}),
                ),
            ),
            roles=(
                EndpointRoleSpec(
                    "A",
                    frozenset({"alpha"}),
                    "alpha",
                    allow_memory_focus=True,
                ),
            ),
            initial_mode_uid="TEST",
            memory_loader=lambda _name: (
                ContextMemoryRow(
                    "memory abcdef12",
                    "select this",
                    selector=memory_uid,
                ),
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert draft is not None
    assert draft.value("A").context_name == "alpha"
    assert draft.value("A").memory_uid == memory_uid
    assert draft.value("A").include_descendants is False


def test_common_endpoint_context_choice_clears_retained_memory_focus():
    memory_uid = "abcdef12-1111-4111-8111-111111111111"

    with create_pipe_input() as pipe_input:
        # Select the Memory, move back to its owner Context, select the whole
        # Context explicitly, then Apply.
        pipe_input.send_text("m\x1b[B\r\x1b[A\r\t\r")
        draft = choose_session_endpoints(
            ("alpha",),
            title="CLEAR MEMORY TEST",
            modes=(
                EndpointModeSpec(
                    "TEST",
                    "A",
                    ("A",),
                    {"A": "A"},
                    memory_focus_roles=frozenset({"A"}),
                ),
            ),
            roles=(
                EndpointRoleSpec(
                    "A",
                    frozenset({"alpha"}),
                    "alpha",
                    allow_memory_focus=True,
                ),
            ),
            initial_mode_uid="TEST",
            memory_loader=lambda _name: (
                ContextMemoryRow("memory abcdef12", "select this", selector=memory_uid),
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert draft is not None
    assert draft.value("A").memory_uid is None


def test_common_endpoint_hiding_preview_clears_retained_memory_focus():
    memory_uid = "abcdef12-1111-4111-8111-111111111111"

    with create_pipe_input() as pipe_input:
        # Select the Memory, hide its preview, then Apply. The exact UID must
        # not survive invisibly after the checked row leaves the screen.
        pipe_input.send_text("m\x1b[B\rm\t\r")
        draft = choose_session_endpoints(
            ("alpha",),
            title="HIDDEN MEMORY TEST",
            modes=(
                EndpointModeSpec(
                    "TEST",
                    "A",
                    ("A",),
                    {"A": "A"},
                    memory_focus_roles=frozenset({"A"}),
                ),
            ),
            roles=(
                EndpointRoleSpec(
                    "A",
                    frozenset({"alpha"}),
                    "alpha",
                    allow_memory_focus=True,
                ),
            ),
            initial_mode_uid="TEST",
            memory_loader=lambda _name: (
                ContextMemoryRow("memory abcdef12", "content", selector=memory_uid),
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert draft is not None
    assert draft.value("A").memory_uid is None


def test_common_endpoint_descendant_scope_clears_memory_focus():
    memory_uid = "abcdef12-1111-4111-8111-111111111111"

    with create_pipe_input() as pipe_input:
        # Memory selection → RANGE → descendants → Apply.
        pipe_input.send_text("m\x1b[B\r\t\x1b[C\t\r")
        draft = choose_session_endpoints(
            ("alpha", "alpha/child"),
            title="MEMORY RANGE TEST",
            modes=(
                EndpointModeSpec(
                    "TEST",
                    "A",
                    ("A",),
                    {"A": "A"},
                    descendant_roles=frozenset({"A"}),
                    memory_focus_roles=frozenset({"A"}),
                ),
            ),
            roles=(
                EndpointRoleSpec(
                    "A",
                    frozenset({"alpha", "alpha/child"}),
                    "alpha",
                    allow_descendants=True,
                    allow_memory_focus=True,
                ),
            ),
            initial_mode_uid="TEST",
            memory_loader=lambda name: (
                ContextMemoryRow(
                    "memory abcdef12",
                    f"{name} content",
                    selector=memory_uid if name == "alpha" else None,
                ),
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert draft is not None
    assert draft.value("A").include_descendants is True
    assert draft.value("A").memory_uid is None


def test_common_endpoint_mode_change_clears_unsupported_memory_focus():
    memory_uid = "abcdef12-1111-4111-8111-111111111111"

    with create_pipe_input() as pipe_input:
        # MODE → A, select Memory, return to MODE, choose whole-frame mode,
        # then move through A to Apply.
        pipe_input.send_text("\x1b[Bm\x1b[B\r\x1b[Z\x1b[C\x1b[B\t\r")
        draft = choose_session_endpoints(
            ("alpha",),
            title="MODE MEMORY TEST",
            modes=(
                EndpointModeSpec(
                    "FOCUSED",
                    "FOCUSED",
                    ("A",),
                    {"A": "A"},
                    memory_focus_roles=frozenset({"A"}),
                ),
                EndpointModeSpec(
                    "WHOLE",
                    "WHOLE",
                    ("A",),
                    {"A": "A"},
                ),
            ),
            roles=(
                EndpointRoleSpec(
                    "A",
                    frozenset({"alpha"}),
                    "alpha",
                    allow_memory_focus=True,
                ),
            ),
            initial_mode_uid="FOCUSED",
            memory_loader=lambda _name: (
                ContextMemoryRow("memory abcdef12", "content", selector=memory_uid),
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert draft is not None
    assert draft.mode_uid == "WHOLE"
    assert draft.value("A").memory_uid is None


def test_common_endpoint_uppercase_m_loads_all_visible_context_memories():
    loaded: list[str] = []

    def load(name: str):
        loaded.append(name)
        return (ContextMemoryRow("memory abcdef12", f"{name} content"),)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("Mq")
        draft = choose_session_endpoints(
            ("alpha", "beta"),
            title="MEMORY PREVIEW TEST",
            modes=(EndpointModeSpec("TEST", "A", ("A",), {"A": "A"}),),
            roles=(
                EndpointRoleSpec(
                    "A",
                    frozenset({"alpha", "beta"}),
                    "alpha",
                ),
            ),
            initial_mode_uid="TEST",
            memory_loader=load,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert draft is None
    assert loaded == ["alpha", "beta"]


@pytest.mark.parametrize(
    ("operation", "keys", "expected_names"),
    (
        ("update", "mq", ("preview/a",)),
        (
            "meld",
            "\x1b[C" + "\t" * 4 + "\r" + "\t" * 4 + "\rq",
            ("preview/a", "preview/b"),
        ),
        ("atomize", "mq", ("preview/a",)),
    ),
)
def test_operation_endpoint_adapters_enable_memory_previews(
    isolated_store,
    monkeypatch,
    operation,
    keys,
    expected_names,
):
    store = MemoryStore()
    first = ops.init("preview/a")
    second = ops.init("preview/b")
    ops.add(first, "Alpha Memory content.")
    ops.add(second, "Beta Memory content.")
    store.create_context(first)
    store.create_context(second)
    store.set_current(first.name)
    projected: list[str] = []

    def observe(context):
        projected.append(context.name)
        return context_memory_rows(context)

    monkeypatch.setattr(endpoint_setup_flows, "context_memory_rows", observe)
    monkeypatch.setattr(meld_setup_command, "context_memory_rows", observe)
    chooser = {
        "update": choose_update_setup,
        "meld": choose_meld_setup,
        "atomize": choose_atomize_setup,
    }[operation]

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(keys)
        receipt = chooser(
            store,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt is None
    assert tuple(projected) == expected_names


@pytest.mark.parametrize(
    ("chooser", "memory_field", "keys"),
    (
        (
            choose_compare_setup,
            "reference_memory_uid",
            "\t\t\x1b[B\r\t\t\t\t\r",
        ),
        (
            choose_update_setup,
            "source_memory_uid",
            "m\x1b[B\r\t\t\t\t\r",
        ),
    ),
)
def test_binary_endpoint_adapters_return_selected_first_role_memory(
    isolated_store,
    chooser,
    memory_field,
    keys,
):
    store = MemoryStore()
    first = ops.init("focused/a")
    first_memory = ops.add(first, "Focused A Memory.")
    second = ops.init("focused/b")
    ops.add(second, "Whole B Memory.")
    store.create_context(first)
    store.create_context(second)
    store.set_current(first.name)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(keys)
        receipt = chooser(
            store,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt is not None
    assert getattr(receipt, memory_field) == first_memory.uid


def test_directional_meld_setup_returns_selected_incoming_memory(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    incoming = ops.init("focused/incoming")
    incoming_memory = ops.add(incoming, "Focused incoming Memory.")
    baseline = ops.init("focused/baseline")
    ops.add(baseline, "Whole baseline Memory.")
    store.create_context(incoming)
    store.create_context(baseline)
    store.set_current(incoming.name)

    monkeypatch.setattr(
        meld_setup_command,
        "choose_meld_endpoint_setup",
        lambda *_args, **_kwargs: MeldEndpointSelection(
            "directional",
            incoming.name,
            baseline.name,
            left_memory_uid=incoming_memory.uid,
        ),
    )
    receipt = choose_meld_setup(store, require_tty=False)

    assert receipt is not None
    assert receipt.mode == "directional"
    assert receipt.left_memory_uid == incoming_memory.uid


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
        "    + atomize/output  NEW · CREATE ON START"
    )
    assert all(
        style == "class:memcommit.choice.active" for style, _text in fragments[1:]
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
    context = ops.init("atomize/input")
    ops.add(context, "One direct Memory.")
    store.create_context(context)

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
    context = ops.init("atomize/input")
    ops.add(context, "One direct Memory.")
    store.create_context(context)

    with create_pipe_input() as pipe_input:
        # Output's last row ↓ NEW; ↑ returns, ↓ re-enters the editor.
        pipe_input.send_text("\t\x1b[B\x1b[A\x1b[Batomize/down-output\r\r")
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
    context = ops.init("atomize/input")
    ops.add(context, "One direct Memory.")
    store.create_context(context)

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


def test_atomize_setup_ctrl_c_cancels_without_a_receipt(isolated_store):
    store = MemoryStore()
    context = ops.init("atomize/input")
    ops.add(context, "One direct Memory.")
    store.create_context(context)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\x1b[Batomize/unfinished\x03")
        receipt = choose_atomize_setup(
            store,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt is None


def test_atomize_setup_allows_explicit_in_place_output(isolated_store):
    store = MemoryStore()
    context = ops.init("atomize/input")
    ops.add(context, "One direct Memory.")
    store.create_context(context)

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


def test_atomize_setup_selects_one_exact_input_memory(isolated_store):
    store = MemoryStore()
    context = ops.init("atomize/input")
    memory = ops.add(context, "Split this Memory. Keep its neighbor.")
    store.create_context(context)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("m\x1b[B\r\t\x1b[Batomize/focused-output\r\r")
        receipt = choose_atomize_setup(
            store,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt is not None
    assert receipt.input_name == context.name
    assert receipt.input_memory_uid == memory.uid
    assert receipt.output_name == "atomize/focused-output"


def test_atomize_setup_blocks_a_context_with_zero_direct_memories(isolated_store):
    store = MemoryStore()
    store.create_context(ops.init("atomize/empty"))

    with create_pipe_input() as pipe_input:
        # Choose in-place output, attempt Apply, then cancel after validation.
        pipe_input.send_text("\t\r\t\r\x1b")
        receipt = choose_atomize_setup(
            store,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt is None


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
        pipe_input.send_text(down * 4 + up * 2 + "\r" + down * 2 + "\r" + "\t\t\r")
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
        # Directional mode exposes independent A and B reach/Memory controls
        # but no C surface. Broaden only B, then continue to the action.
        pipe_input.send_text("\x1b[C" + "\t" * 7 + " \t\t\r")
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
    assert receipt.left_descendants is False
    assert receipt.right_descendants is True


def test_meld_symmetric_mode_collects_new_result_c(isolated_store):
    store = MemoryStore()
    left = ops.init("meld-setup/a")
    right = ops.init("meld-setup/b")
    ops.add(left, "Left source")
    ops.add(right, "Right source")
    store.create_context(left)
    store.create_context(right)

    with create_pipe_input() as pipe_input:
        # A/B each expose an explicit Browse stop before compact C.
        pipe_input.send_text("\t" * 7 + "faq/result\n\r")
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
