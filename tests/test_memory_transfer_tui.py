"""Interactive Copy/Move setup and editable exact-command contracts."""

from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.context import Context, Memory, MemoryRef
from memcommit.interfaces.tui.components.direct_item_placement import DirectItemGap
from memcommit.interfaces.tui.operations.memory_transfer import (
    choose_memory_transfer_setup,
    memory_transfer_exact_command_review,
    parse_memory_transfer_command_argv,
)
from memcommit.memory_transfer_application import (
    CopyMemoriesRequest,
    MoveMemoriesRequest,
    run_copy,
    run_move,
)
from memcommit.memory_transfer_runtime import MemoryStoreMemoryTransferPort
from memcommit.store import MemoryStore
from memcommit.interfaces.cli import memory_transfer as transfer_command


runner = CliRunner(mix_stderr=False)


def _context(store: MemoryStore, name: str, *contents: str) -> tuple[Context, tuple[Memory, ...]]:
    context = ops.init(name)
    memories = tuple(ops.add(context, content) for content in contents)
    store.save(context)
    return context, memories


def test_editable_memory_transfer_parser_keeps_copy_simple_and_move_explicit() -> None:
    assert parse_memory_transfer_command_argv(
        (
            "mem",
            "copy",
            "source:aaaaaaa",
            "other:bbbbbbb",
            "--into",
            "target",
            "--before",
            "ccccccc",
        ),
        kind="COPY",
    ) == CopyMemoriesRequest(
        ("source:aaaaaaa", "other:bbbbbbb"),
        "target",
        before="ccccccc",
    )
    with pytest.raises(ValueError, match="Unknown Copy flag '--preserve-uids'"):
        parse_memory_transfer_command_argv(
            (
                "mem",
                "copy",
                "source:aaaaaaa",
                "--into",
                "target",
                "--preserve-uids",
            ),
            kind="COPY",
        )
    assert parse_memory_transfer_command_argv(
        ("mem", "move", "aaaaaaa", "--from", "source", "--into", "target"),
        kind="MOVE",
    ) == MoveMemoriesRequest(
        ("aaaaaaa",),
        "target",
        "source",
        link_policy="RETARGET",
    )
    assert parse_memory_transfer_command_argv(
        (
            "mem",
            "move",
            "source:aaaaaaa",
            "--into",
            "target",
            "--break-links",
        ),
        kind="MOVE",
    ).link_policy == "BREAK"


def test_move_review_states_live_follow_and_snapshot_boundary() -> None:
    request = MoveMemoriesRequest(("source:aaaaaaa",), "target")

    review = memory_transfer_exact_command_review(
        request,
        DirectItemGap(0, None, "bbbbbbbb-0000-0000-0000-000000000000"),
        item_count=1,
        placement_selector="bbbbbbb",
    )

    assert review.argv == (
        "mem",
        "move",
        "source:aaaaaaa",
        "--into",
        "target",
        "--before",
        "bbbbbbb",
    )
    assert "Every local live Memory Embed follows atomically" in review.effects[1]
    assert "snapshots stay unchanged" in review.effects[1]


def test_copy_tui_checks_multiple_memories_and_freezes_one_exact_gap(
    isolated_store,
) -> None:
    store = MemoryStore()
    source, (first, second) = _context(store, "source", "first", "second")
    target, (marker,) = _context(store, "target", "target marker")
    store.set_current(source.name)
    port = MemoryStoreMemoryTransferPort.capture(store)
    before = {
        source.name: store.load_direct(source.name).to_dict(),
        target.name: store.load_direct(target.name).to_dict(),
    }

    with create_pipe_input() as pipe_input:
        # Check both nested Memories, choose Target, stage the gap before its
        # marker, then approve the compact exact command.
        pipe_input.send_text("\x1b[B\r\x1b[B\r\t\x1b[B\r\t\x1b[A\r\t\r")
        plan = choose_memory_transfer_setup(
            port,
            kind="COPY",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert plan is not None
    assert [item.source_memory_uid for item in plan.memories] == [first.uid, second.uid]
    assert plan.into_name == target.name
    assert plan.placement.position == 0
    assert plan.placement.next_uid == marker.uid
    assert store.load_direct(source.name).to_dict() == before[source.name]
    assert store.load_direct(target.name).to_dict() == before[target.name]

    result = run_copy(plan.request, port=port, frozen_plan=plan)

    assert result.count == 2
    assert store.load_direct(source.name).to_dict() == before[source.name]
    assert store.load_direct(target.name).ordered_uids()[-1] == marker.uid


def test_copy_editable_command_replaces_the_visible_batch_order_atomically(
    isolated_store,
) -> None:
    store = MemoryStore()
    source, (first, second) = _context(store, "source", "first", "second")
    target, _ = _context(store, "target")
    store.set_current(source.name)
    command = (
        f"{source.name}:{second.uid[:7]} {source.name}:{first.uid[:7]} "
        f"--into {target.name}"
    )

    with create_pipe_input() as pipe_input:
        # Reach the compact command with no checked Source, then replace its
        # arguments. One complete parse moves every upper control together.
        pipe_input.send_text("\t\t\t\x15" + command + "\r")
        plan = choose_memory_transfer_setup(
            MemoryStoreMemoryTransferPort.capture(store),
            kind="COPY",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert plan is not None
    assert [item.source_memory_uid for item in plan.memories] == [
        second.uid,
        first.uid,
    ]
    assert store.load_direct(target.name).memories == {}


def test_move_tui_defaults_to_atomic_live_embed_retarget(isolated_store) -> None:
    store = MemoryStore()
    source, (memory,) = _context(store, "source", "move me")
    target, _ = _context(store, "target")
    watcher, _ = _context(store, "watcher")
    reference = ops.embed_memory(memory, source, watcher)
    store.save(watcher)
    store.set_current(source.name)
    port = MemoryStoreMemoryTransferPort.capture(store)

    with create_pipe_input() as pipe_input:
        # Check one Source, choose Target, retain append, then approve.
        pipe_input.send_text("\x1b[B\r\t\x1b[B\r\t\t\r")
        plan = choose_memory_transfer_setup(
            port,
            kind="MOVE",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert plan is not None
    assert plan.request.link_policy == "RETARGET"
    assert len(plan.inbound_links) == 1
    assert list(store.load_direct(source.name).memories) == [memory.uid]
    assert store.load_direct(target.name).memories == {}

    result = run_move(plan.request, port=port, frozen_plan=plan)

    assert result.retargeted_link_count == 1
    moved_reference = store.load_direct(watcher.name).memories[reference.uid]
    assert isinstance(moved_reference, MemoryRef)
    assert moved_reference.target_context_uid == target.uid


def test_memory_transfer_tui_escape_does_not_freeze_or_apply(isolated_store) -> None:
    store = MemoryStore()
    source, _ = _context(store, "source", "leave me")
    _context(store, "target")
    store.set_current(source.name)
    port = MemoryStoreMemoryTransferPort.capture(store)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        plan = choose_memory_transfer_setup(
            port,
            kind="MOVE",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert plan is None
    assert len(store.list_checkpoints(source.name)) == 0


def test_bare_copy_cli_applies_only_the_tui_returned_frozen_plan(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    source, (memory,) = _context(store, "source", "copy me")
    target, _ = _context(store, "target")
    store.set_current(source.name)
    port = MemoryStoreMemoryTransferPort.capture(store)
    plan = port.freeze_copy(
        CopyMemoriesRequest(
            (f"{source.name}:{memory.uid[:8]}",),
            into_locator=target.name,
        )
    )
    monkeypatch.setattr(transfer_command, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        transfer_command.MemoryStoreMemoryTransferPort,
        "capture",
        lambda _store: port,
    )
    monkeypatch.setattr(
        transfer_command,
        "choose_memory_transfer_setup",
        lambda _port, *, kind: plan,
    )

    result = runner.invoke(app, ["copy"])

    assert result.exit_code == 0, result.output + result.stderr
    assert "COPIED" in result.output
    assert list(store.load_direct(source.name).memories) == [memory.uid]
    assert len(store.load_direct(target.name).memories) == 1


def test_bare_move_cli_applies_only_the_tui_returned_frozen_plan(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    source, (memory,) = _context(store, "source", "move me")
    target, _ = _context(store, "target")
    store.set_current(source.name)
    port = MemoryStoreMemoryTransferPort.capture(store)
    plan = port.freeze_move(
        MoveMemoriesRequest(
            (f"{source.name}:{memory.uid[:8]}",),
            into_locator=target.name,
        )
    )
    monkeypatch.setattr(transfer_command, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        transfer_command.MemoryStoreMemoryTransferPort,
        "capture",
        lambda _store: port,
    )
    monkeypatch.setattr(
        transfer_command,
        "choose_memory_transfer_setup",
        lambda _port, *, kind: plan,
    )

    result = runner.invoke(app, ["move"])

    assert result.exit_code == 0, result.output + result.stderr
    assert "MOVED" in result.output
    assert store.load_direct(source.name).memories == {}
    assert list(store.load_direct(target.name).memories) == [memory.uid]


def test_bare_transfer_cli_prints_stable_non_tty_locator_guidance(
    isolated_store,
) -> None:
    _context(MemoryStore(), "source", "value")

    copied = runner.invoke(app, ["copy"])
    moved = runner.invoke(app, ["move"])

    assert copied.exit_code == 1
    assert "mem copy CONTEXT:MEMORY --into TARGET" in copied.stderr
    assert moved.exit_code == 1
    assert "mem move CONTEXT:MEMORY --into TARGET" in moved.stderr
