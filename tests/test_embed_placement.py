"""Ordered Embed CLI and interactive insertion-gap contracts."""

from __future__ import annotations

from pathlib import Path

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import memcommit.application.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.tui.components.direct_item_placement import (
    DirectItemGap,
    DirectItemGapState,
    direct_item_gap,
    direct_item_placement_rows,
    render_direct_item_tree_fragments,
)
from memcommit.application.operations.embed.application import (
    EmbedPlacement,
    EmbedRequest,
    FrozenMemoryEmbedPlan,
    MemoryEmbedRequest,
    run_embed,
)
from memcommit.application.operations.embed.runtime import MemoryStoreEmbedPort
from memcommit.adapters.console.commands.embed import command as embed_command
from memcommit.adapters.console.commands.embed.workbench import (
    choose_embed_setup,
    embed_exact_command_review,
    parse_embed_command_argv,
)
from memcommit.core.context import Context, Memory
from memcommit.core.context_targeting.tui.tree import ContextTreeRow
from memcommit.source_projection.model import SourceForm, SourceReach
from memcommit.persistence.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def test_embed_console_owns_command_receipt_and_workbench_without_facades() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    command_root = repository_root / "src/memcommit/adapters/console/commands/embed"
    retired_tui_root = (
        repository_root / "src/memcommit/adapters/interfaces/tui/operations/embed"
    )

    assert (command_root / "command.py").is_file()
    assert (command_root / "receipt.py").is_file()
    assert (command_root / "workbench/model.py").is_file()
    assert (command_root / "workbench/setup.py").is_file()
    assert (command_root / "workbench/screen.py").is_file()
    assert not tuple(retired_tui_root.glob("*.py"))
    assert not (
        repository_root / "src/memcommit/adapters/interfaces/cli/embed.py"
    ).exists()


def _placement_tree_row() -> ContextTreeRow:
    return ContextTreeRow(
        name="parent",
        depth=0,
        has_children=False,
        expanded=False,
        materialized=True,
    )


def _ordered_store() -> tuple[MemoryStore, Context, Context, Memory, Memory]:
    store = MemoryStore()
    child = ops.init("embed/child")
    ops.add(child, "Child-owned detail remains live and independent.")
    parent = ops.init("embed/target")
    first = ops.add(parent, "First target Memory.")
    second = ops.add(parent, "Second target Memory.")
    store.save(child)
    store.save(parent)
    store.set_current(parent.name)
    return store, child, parent, first, second


def test_ops_embed_accepts_one_exact_direct_item_position() -> None:
    child = ops.init("child")
    parent = ops.init("parent")
    first = ops.add(parent, "first")
    second = ops.add(parent, "second")

    ops.embed(child, parent, position=1)

    assert parent.ordered_uids() == [first.uid, child.uid, second.uid]


def test_ops_embed_rejects_a_position_outside_the_direct_order() -> None:
    child = ops.init("child")
    parent = ops.init("parent")

    try:
        ops.embed(child, parent, position=1)
    except ValueError as error:
        assert "between 0 and 0" in str(error)
    else:
        raise AssertionError("out-of-range Embed position was accepted")
    assert parent.ordered_uids() == []


def test_gap_state_keeps_hover_separate_from_the_staged_separator() -> None:
    parent = ops.init("parent")
    first = ops.add(parent, "first")
    second = ops.add(parent, "second")
    state = DirectItemGapState.create(direct_item_placement_rows(parent))

    assert state.selected_gap.position == 2
    assert state.move(-1)
    assert state.selected_gap.position == 2
    assert state.choose_cursor()
    assert state.selected_gap == direct_item_gap(
        direct_item_placement_rows(parent),
        1,
    )
    assert state.selected_gap.previous_uid == first.uid
    assert state.selected_gap.next_uid == second.uid


def test_editable_embed_command_parser_preserves_context_and_memory_modes() -> None:
    assert parse_embed_command_argv(
        ("mem", "embed", "examples", "--into", "guide", "--after", "abc1234")
    ) == EmbedRequest("examples", "guide", after="abc1234")
    assert parse_embed_command_argv(
        (
            "mem",
            "embed",
            "def5678",
            "--from",
            "examples",
            "--into",
            "guide",
            "--before",
            "abc1234",
        )
    ) == MemoryEmbedRequest(
        "def5678",
        "examples",
        "guide",
        before="abc1234",
    )


def test_editable_embed_command_parser_accepts_to_as_into_alias() -> None:
    assert parse_embed_command_argv(
        ("mem", "embed", "examples", "--to", "guide")
    ) == EmbedRequest("examples", "guide")
    assert parse_embed_command_argv(
        ("mem", "embed", "--from", "examples", "--to", "guide")
    ) == EmbedRequest("examples", "guide")


def test_editable_embed_command_parser_rejects_both_target_spellings() -> None:
    try:
        parse_embed_command_argv(
            (
                "mem",
                "embed",
                "examples",
                "--into",
                "guide",
                "--to",
                "other",
            )
        )
    except ValueError as error:
        assert "only one of --into or --to" in str(error)
    else:
        raise AssertionError("two Embed target spellings were accepted together")


def test_gap_state_defaults_to_the_explicit_last_choice() -> None:
    parent = ops.init("parent")
    ops.add(parent, "first")
    ops.add(parent, "second")
    state = DirectItemGapState.create(
        direct_item_placement_rows(parent),
        insertion_label="INSERT EMBED HERE",
    )

    rendered = "".join(
        text
        for _style, text in render_direct_item_tree_fragments(
            state,
            row=_placement_tree_row(),
            editing=False,
            focused=False,
            width=120,
        )
    )

    assert state.selected_position == 2
    assert "FIRST" not in rendered
    assert "✓ ───────── LAST · DEFAULT · 3/3" in rendered
    assert rendered.count("LAST · DEFAULT") == 1
    assert "POSITION ·" not in rendered


def test_gap_renderer_places_a_visible_separator_between_memory_rows() -> None:
    parent = ops.init("parent")
    ops.add(parent, "first")
    ops.add(parent, "second")
    state = DirectItemGapState.create(
        direct_item_placement_rows(parent),
        position=1,
        insertion_label="INSERT EMBED HERE",
    )

    rendered = "".join(
        text
        for _style, text in render_direct_item_tree_fragments(
            state,
            row=_placement_tree_row(),
            editing=True,
            focused=True,
            width=100,
        )
    )
    lines = [line for line in rendered.splitlines() if line]

    assert "[memory" in lines[0] and "first" in lines[0]
    assert "POSITION · 2/3" in lines[1]
    assert lines[1].startswith("  › ✓ ─")
    assert "[memory" in lines[2] and "second" in lines[2]
    assert rendered.count("POSITION ·") == 1
    assert "FIRST" not in rendered and "LAST" not in rendered


def test_embedded_context_is_one_visible_direct_item_with_gaps_on_both_sides(
    isolated_store,
) -> None:
    store = MemoryStore()
    parent = ops.init("parent")
    first = ops.add(parent, "first")
    nested = ops.init("parent/nested")
    ops.embed(nested, parent)
    last = ops.add(parent, "last")
    for context in (nested, parent):
        store.save(context)

    rows = direct_item_placement_rows(parent)

    assert [row.uid for row in rows] == [first.uid, nested.uid, last.uid]
    assert rows[1].preview.content == nested.name
    assert rows[1].preview.source.form is SourceForm.CONTEXT
    assert rows[1].preview.source.reach is SourceReach.VIA_EMBED
    assert direct_item_gap(rows, 1).next_uid == nested.uid
    assert direct_item_gap(rows, 2).previous_uid == nested.uid


def test_cli_embed_accepts_before_and_after_an_embedded_context_name(
    isolated_store,
) -> None:
    store = MemoryStore()
    parent = ops.init("parent")
    nested = ops.init("parent/nested")
    before_child = ops.init("before-child")
    after_child = ops.init("after-child")
    ops.embed(nested, parent)
    for context in (nested, before_child, after_child, parent):
        store.save(context)
    store.set_current(parent.name)

    before_result = runner.invoke(
        app,
        [
            "embed",
            before_child.name,
            "--into",
            parent.name,
            "--before",
            nested.name,
        ],
    )
    after_result = runner.invoke(
        app,
        [
            "embed",
            after_child.name,
            "--into",
            parent.name,
            "--after",
            nested.name,
        ],
    )

    assert before_result.exit_code == 0, before_result.output + before_result.stderr
    assert after_result.exit_code == 0, after_result.output + after_result.stderr
    assert store.load_direct(parent.name).ordered_uids() == [
        before_child.uid,
        nested.uid,
        after_child.uid,
    ]


def test_cli_embed_inserts_before_one_direct_memory(isolated_store) -> None:
    store, child, parent, first, second = _ordered_store()

    result = runner.invoke(
        app,
        [
            "embed",
            child.name,
            "--into",
            parent.name,
            "--before",
            second.uid[:8],
        ],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert store.load_direct(parent.name).ordered_uids() == [
        first.uid,
        child.uid,
        second.uid,
    ]
    assert f"between [{first.uid[:8]}] and [{second.uid[:8]}]" in result.output
    checkpoint_args = store.list_checkpoints(parent.name)[-1]["args"]
    assert checkpoint_args["position"] == 1
    assert checkpoint_args["after_uid"] == first.uid
    assert checkpoint_args["before_uid"] == second.uid


def test_cli_embed_can_choose_the_explicit_first_gap(isolated_store) -> None:
    store, child, parent, first, second = _ordered_store()

    result = runner.invoke(
        app,
        [
            "embed",
            child.name,
            "--into",
            parent.name,
            "--before",
            first.uid,
        ],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert store.load_direct(parent.name).ordered_uids() == [
        child.uid,
        first.uid,
        second.uid,
    ]
    assert f"before [{first.uid[:8]}] at the start" in result.output


def test_cli_embed_accepts_to_as_into_alias(isolated_store) -> None:
    store, child, parent, first, second = _ordered_store()

    result = runner.invoke(
        app,
        ["embed", child.name, "--to", parent.name],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert store.load_direct(parent.name).ordered_uids() == [
        first.uid,
        second.uid,
        child.uid,
    ]
    assert f"into '{parent.name}'" in result.output


def test_cli_embed_accepts_from_as_a_complete_context_source(
    isolated_store,
) -> None:
    store, child, parent, first, second = _ordered_store()

    result = runner.invoke(
        app,
        ["embed", "--from", child.name, "--to", parent.name],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert store.load_direct(parent.name).ordered_uids() == [
        first.uid,
        second.uid,
        child.uid,
    ]


def test_cli_embed_help_keeps_into_canonical_and_lists_to_alias() -> None:
    result = runner.invoke(app, ["embed", "--help"])

    assert result.exit_code == 0, result.output + result.stderr
    assert "--into" in result.output
    assert "--to" in result.output
    assert "Compatibility alias for --into" in result.output
    assert "Source Context when ITEM is omitted" in result.output


def test_cli_embed_rejects_into_and_to_without_mutation(isolated_store) -> None:
    store, child, parent, _first, _second = _ordered_store()
    before = store.load_direct(parent.name).to_dict()

    result = runner.invoke(
        app,
        [
            "embed",
            child.name,
            "--into",
            parent.name,
            "--to",
            parent.name,
        ],
    )

    assert result.exit_code == 2
    assert "--into and --to" in result.stderr
    assert store.load_direct(parent.name).to_dict() == before
    assert store.list_checkpoints(parent.name) == []


def test_cli_embed_defaults_to_current_target_and_last_gap(
    isolated_store,
) -> None:
    store, child, parent, first, second = _ordered_store()

    result = runner.invoke(
        app,
        ["embed", child.name],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert store.load_direct(parent.name).ordered_uids() == [
        first.uid,
        second.uid,
        child.uid,
    ]
    assert f"after [{second.uid[:8]}] at the end" in result.output


def test_cli_embed_without_into_requires_a_current_context(isolated_store) -> None:
    store = MemoryStore()
    child = ops.init("embed/child")
    store.save(child)

    result = runner.invoke(app, ["embed", child.name])

    assert result.exit_code == 1
    assert "no current Context" in result.stderr
    assert "Pass --into" in result.stderr


def test_cli_embed_inserts_after_one_direct_memory(isolated_store) -> None:
    store, child, parent, first, second = _ordered_store()

    result = runner.invoke(
        app,
        [
            "embed",
            child.name,
            "--into",
            parent.name,
            "--after",
            first.uid,
        ],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert store.load_direct(parent.name).ordered_uids() == [
        first.uid,
        child.uid,
        second.uid,
    ]


def test_cli_embed_rejects_two_position_anchors_without_mutation(
    isolated_store,
) -> None:
    store, child, parent, first, second = _ordered_store()
    before = store.load_direct(parent.name).to_dict()

    result = runner.invoke(
        app,
        [
            "embed",
            child.name,
            "--into",
            parent.name,
            "--before",
            second.uid,
            "--after",
            first.uid,
        ],
    )

    assert result.exit_code == 2
    assert "only one of --before or --after" in result.stderr
    assert store.load_direct(parent.name).to_dict() == before


def test_flagless_embed_requires_a_terminal(isolated_store) -> None:
    _ordered_store()

    result = runner.invoke(app, ["embed"])

    assert result.exit_code == 1
    assert "an item is required outside a terminal" in result.stderr
    assert "mem embed MEMORY" in result.stderr
    assert "mem embed CONTEXT:MEMORY" in result.stderr


def test_embed_setup_stages_the_gap_between_two_memories(isolated_store) -> None:
    store, child, parent, first, second = _ordered_store()
    with create_pipe_input() as pipe_input:
        # Child → Into → Position; move from append to the middle gap, stage it,
        # then advance to the exact-command action and approve the receipt.
        pipe_input.send_text("\t\t\t\x1b[A\r\t\r")
        receipt = choose_embed_setup(
            MemoryStoreEmbedPort.capture(store),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt is not None
    assert receipt.child_name == child.name
    assert receipt.into_name == parent.name
    assert receipt.placement.position == 1
    assert receipt.placement.previous_uid == first.uid
    assert receipt.placement.next_uid == second.uid
    assert receipt.request.before == second.uid
    assert embed_exact_command_review(
        receipt.child_name,
        receipt.into_name,
        DirectItemGap(
            position=receipt.placement.position,
            previous_uid=receipt.placement.previous_uid,
            next_uid=receipt.placement.next_uid,
        ),
        item_count=receipt.item_count,
    ).argv == (
        "mem",
        "embed",
        child.name,
        "--into",
        parent.name,
        "--before",
        second.uid,
    )
    assert (
        embed_exact_command_review(
            receipt.child_name,
            receipt.into_name,
            DirectItemGap(
                position=receipt.placement.position,
                previous_uid=receipt.placement.previous_uid,
                next_uid=receipt.placement.next_uid,
            ),
            item_count=receipt.item_count,
            placement_selector=second.uid[:7],
        ).argv[-1]
        == second.uid[:7]
    )


def test_embed_proposed_command_updates_the_visible_gap_before_freeze(
    isolated_store,
) -> None:
    store, child, parent, first, second = _ordered_store()
    arguments = f"{child.name} --into {parent.name} --before {second.uid[:7]}"
    with create_pipe_input() as pipe_input:
        # Reach the always-editable command, replace it, and approve once. Each
        # complete valid buffer change already synchronized the checked gap.
        pipe_input.send_text("\t\t\t\t\x15" + arguments + "\r")
        receipt = choose_embed_setup(
            MemoryStoreEmbedPort.capture(store),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt is not None
    assert receipt.child_name == child.name
    assert receipt.into_name == parent.name
    assert receipt.placement.position == 1
    assert receipt.placement.previous_uid == first.uid
    assert receipt.placement.next_uid == second.uid


def test_embed_proposed_command_can_switch_the_visible_link_type_to_memory(
    isolated_store,
) -> None:
    store, child, parent, _first, second = _ordered_store()
    memory_uid = store.load_direct(child.name).ordered_uids()[0]
    arguments = (
        f"{memory_uid[:7]} --from {child.name} "
        f"--into {parent.name} --before {second.uid[:7]}"
    )
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\t\t\t\x15" + arguments + "\r")
        receipt = choose_embed_setup(
            MemoryStoreEmbedPort.capture(store),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert isinstance(receipt, FrozenMemoryEmbedPlan)
    assert receipt.source_name == child.name
    assert receipt.memory_uid == memory_uid
    assert receipt.into_name == parent.name
    assert receipt.placement.next_uid == second.uid


def test_embed_enter_applies_only_the_returned_frozen_plan_once(
    isolated_store,
) -> None:
    store, child, parent, first, second = _ordered_store()
    port = MemoryStoreEmbedPort.capture(store)
    before = store.load_direct(parent.name).to_dict()

    with create_pipe_input() as pipe_input:
        # Review the middle gap and approve the focused exact command with
        # Enter. The TUI may freeze the plan, but it must not apply it itself.
        pipe_input.send_text("\t\t\t\x1b[A\r\t\r")
        plan = choose_embed_setup(
            port,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert plan is not None
    assert store.load_direct(parent.name).to_dict() == before
    assert store.list_checkpoints(parent.name) == []

    result = run_embed(plan.request, port=port, frozen_plan=plan)

    assert result.placement == plan.placement
    assert store.load_direct(parent.name).ordered_uids() == [
        first.uid,
        child.uid,
        second.uid,
    ]
    assert len(store.list_checkpoints(parent.name)) == 1

    # Reusing the reviewed plan after its first commit must fail closed: the
    # target digest changed, and no second checkpoint may be published.
    try:
        run_embed(plan.request, port=port, frozen_plan=plan)
    except RuntimeError as error:
        assert "changed after" in str(error)
    else:
        raise AssertionError("an already-applied Embed plan was applied twice")
    assert len(store.list_checkpoints(parent.name)) == 1


def test_embed_escape_cancels_before_freeze_or_application(isolated_store) -> None:
    store, _child, parent, _first, _second = _ordered_store()
    port = MemoryStoreEmbedPort.capture(store)
    before = store.load_direct(parent.name).to_dict()

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        plan = choose_embed_setup(
            port,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert plan is None
    assert store.load_direct(parent.name).to_dict() == before
    assert store.list_checkpoints(parent.name) == []


def test_embed_ctrl_c_cancels_before_freeze_or_application(isolated_store) -> None:
    store, _child, parent, _first, _second = _ordered_store()
    port = MemoryStoreEmbedPort.capture(store)
    before = store.load_direct(parent.name).to_dict()

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x03")
        plan = choose_embed_setup(
            port,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert plan is None
    assert store.load_direct(parent.name).to_dict() == before
    assert store.list_checkpoints(parent.name) == []


def test_flagless_embed_applies_only_the_exact_reviewed_gap(
    isolated_store,
    monkeypatch,
) -> None:
    store, child, parent, first, second = _ordered_store()
    port = MemoryStoreEmbedPort.capture(store)
    gap = direct_item_gap(
        direct_item_placement_rows(store.load_direct(parent.name)),
        1,
    )
    receipt = port.freeze_exact_gap(
        child.name,
        parent.name,
        EmbedPlacement(gap.position, gap.previous_uid, gap.next_uid),
    )
    monkeypatch.setattr(embed_command, "_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        embed_command.MemoryStoreEmbedPort,
        "capture",
        lambda _store, **_kwargs: port,
    )
    monkeypatch.setattr(embed_command, "choose_embed_setup", lambda _port: receipt)

    result = runner.invoke(app, ["embed"])

    assert result.exit_code == 0, result.output + result.stderr
    assert store.load_direct(parent.name).ordered_uids() == [
        first.uid,
        child.uid,
        second.uid,
    ]


def test_flagless_embed_rejects_target_order_drift_after_review(
    isolated_store,
    monkeypatch,
) -> None:
    store, child, parent, _first, _second = _ordered_store()
    port = MemoryStoreEmbedPort.capture(store)
    gap = direct_item_gap(
        direct_item_placement_rows(store.load_direct(parent.name)),
        1,
    )
    receipt = port.freeze_exact_gap(
        child.name,
        parent.name,
        EmbedPlacement(gap.position, gap.previous_uid, gap.next_uid),
    )

    def choose_and_race(_store):
        changed = store.load_direct(parent.name)
        ops.add(changed, "Concurrent target Memory.")
        store.save(changed)
        return receipt

    monkeypatch.setattr(embed_command, "_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        embed_command.MemoryStoreEmbedPort,
        "capture",
        lambda _store, **_kwargs: port,
    )
    monkeypatch.setattr(embed_command, "choose_embed_setup", choose_and_race)

    result = runner.invoke(app, ["embed"])

    assert result.exit_code == 1
    assert (
        "direct-item order changed after the insertion gap was reviewed"
        in result.stderr
    )
    assert child.uid not in store.load_direct(parent.name).ordered_uids()
