"""Interactive Copy/Move setup and editable exact-command contracts."""

from __future__ import annotations

from tests.grant_placement_support import create_authority_grant_with_placement

import json
import uuid

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
import pytest
from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.commands.copy import command as copy_command
from memcommit.adapters.console.commands.copy.setup import (
    build_copy_tui_setup,
    choose_copy_setup,
)
from memcommit.adapters.console.commands.move import command as move_command
from memcommit.adapters.console.commands.move.setup import (
    build_move_tui_setup,
    choose_move_setup,
)
from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.commands.copy_and_move.command_codec import (
    copy_and_move_exact_command_review,
    parse_copy_and_move_command_argv,
)
from memcommit.core.context import Context, Memory, MemoryRef
from memcommit.adapters.console.terminal.components.direct_item_placement import DirectItemGap
from memcommit.application.operations.profile.config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.source_projection.presentation import source_display_text
from memcommit.application.capabilities.memory_transfer.application import (
    CopyMemoriesRequest,
    MoveMemoriesRequest,
)
from memcommit.application.operations.copy.application import run_copy
from memcommit.application.capabilities.memory_transfer.runtime import MemoryStoreCopyAndMovePort
from memcommit.application.operations.move.application import run_move
from memcommit.persistence.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _context(store: MemoryStore, name: str, *contents: str) -> tuple[Context, tuple[Memory, ...]]:
    context = ops.init(name)
    memories = tuple(ops.add(context, content) for content in contents)
    store.save(context)
    return context, memories


def _granted_copy_fixture(isolated_store, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    store = MemoryStore()
    workspace, _ = _context(store, "workspace")
    local_source, _ = _context(store, "local-source", "owned source")
    target, (marker,) = _context(store, "target", "target marker")
    store.set_current(workspace.name)

    grantee = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="copy-authority",
        kind="MANAGED",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    source = ops.init("authority/source")
    memory = ops.add(source, "Export-authorized source")
    no_retention = ops.init("authority/no-retention")
    ops.add(no_retention, "Readable but not retainable")
    authority_store.save(source)
    authority_store.save(no_retention)

    registry = ProfileRegistry(
        generation=1,
        active_uid=grantee.uid,
        profiles=(grantee, authority),
        grants=(),
    )
    path = profile_registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry.to_dict(), indent=2) + "\n")
    create_authority_grant_with_placement(
        authority_name=authority.name,
        grantee_name=grantee.name,
        resource_name=source.name,
        access_name="shared/source",
        permissions=("READ",),
    )
    create_authority_grant_with_placement(
        authority_name=authority.name,
        grantee_name=grantee.name,
        resource_name=no_retention.name,
        access_name="shared/no-retention",
        permissions=("READ",),
    )
    return store, source, memory, target, marker, local_source


def test_editable_memory_transfer_parser_keeps_copy_simple_and_move_explicit() -> None:
    assert parse_copy_and_move_command_argv(
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
        parse_copy_and_move_command_argv(
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
    assert parse_copy_and_move_command_argv(
        ("mem", "move", "aaaaaaa", "--from", "source", "--into", "target"),
        kind="MOVE",
    ) == MoveMemoriesRequest(
        ("aaaaaaa",),
        "target",
        "source",
        link_policy="RETARGET",
    )
    assert parse_copy_and_move_command_argv(
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

    review = copy_and_move_exact_command_review(
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
    port = MemoryStoreCopyAndMovePort.capture(store)
    before = {
        source.name: store.load_direct(source.name).to_dict(),
        target.name: store.load_direct(target.name).to_dict(),
    }

    with create_pipe_input() as pipe_input:
        # Check both nested Memories, choose Target, stage the gap before its
        # marker, then approve the compact exact command.
        pipe_input.send_text("\x1b[B\r\x1b[B\r\t\x1b[B\r\t\x1b[A\r\t\r")
        plan = choose_copy_setup(
            port,
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
        plan = choose_copy_setup(
            MemoryStoreCopyAndMovePort.capture(store),
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


def test_granted_copy_tui_separates_readable_sources_from_local_roles(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, _source, _memory, target, _marker, local_source = (
        _granted_copy_fixture(isolated_store, tmp_path, monkeypatch)
    )
    port = MemoryStoreCopyAndMovePort.capture(
        store,
        allow_granted_sources=True,
    )

    copy_setup = build_copy_tui_setup(port)
    move_setup = build_move_tui_setup(port)
    copy_annotations = dict(copy_setup.source_annotations)

    assert "shared/source" in copy_setup.source_names
    assert "shared/no-retention" in copy_setup.source_names
    assert "shared/source" not in copy_setup.local_source_names
    assert "shared/source" not in copy_setup.into_names
    assert set(copy_setup.into_names) == {
        "workspace",
        local_source.name,
        target.name,
    }
    assert "GRANT" in source_display_text(copy_annotations["shared/source"])
    assert "COPY + RETAIN" in source_display_text(
        copy_annotations["shared/source"]
    )
    assert "COPY + RETAIN" in source_display_text(
        copy_annotations["shared/no-retention"]
    )
    assert "shared/source" not in move_setup.source_names
    assert move_setup.source_names == move_setup.local_source_names
    assert move_setup.source_names == move_setup.into_names


def test_local_only_copy_tui_does_not_consult_active_profile_grants(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, _source, _memory, target, _marker, local_source = (
        _granted_copy_fixture(isolated_store, tmp_path, monkeypatch)
    )
    port = MemoryStoreCopyAndMovePort.capture(store)

    setup = build_copy_tui_setup(port)

    assert port.allows_granted_sources is False
    assert set(setup.source_names) == {
        "workspace",
        local_source.name,
        target.name,
    }
    assert setup.source_names == setup.local_source_names
    assert setup.source_annotations == ()
    assert "shared/source" not in setup.source_names
    with pytest.raises(FileNotFoundError):
        port.inspect_local_context("shared/source")


def test_granted_copy_exact_command_requires_an_explicit_public_owner(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, source, memory, target, marker, _local_source = (
        _granted_copy_fixture(isolated_store, tmp_path, monkeypatch)
    )
    port = MemoryStoreCopyAndMovePort.capture(
        store,
        allow_granted_sources=True,
    )
    command = (
        f"shared/source:{memory.uid[:7]} --into {target.name} "
        f"--before {marker.uid[:7]}"
    )

    with create_pipe_input() as pipe_input:
        # Source → Into Context → position → exact command. Replacing the
        # command proves the edited public owner is resolved only in the
        # frozen Copy Source role and never in the local Target role.
        pipe_input.send_text("\t\t\t\x15" + command + "\r")
        plan = choose_copy_setup(
            port,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert plan is not None
    assert plan.request.memory_locators == (
        f"shared/source:{memory.uid[:7]}",
    )
    assert plan.memories[0].source_context_name == "shared/source"
    assert plan.memories[0].source_context_uid == source.uid
    assert plan.into_name == target.name
    assert plan.placement.next_uid == marker.uid


def test_granted_copy_exact_command_keeps_source_and_target_role_catalogs(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, source, memory, target, _marker, local_source = (
        _granted_copy_fixture(isolated_store, tmp_path, monkeypatch)
    )
    port = MemoryStoreCopyAndMovePort.capture(
        store,
        allow_granted_sources=True,
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(
            "\t\t\t\x15"
            f"{memory.uid[:7]} --from shared/source --into {target.name}"
            "\r"
        )
        plan = choose_copy_setup(
            port,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert plan is not None
    assert plan.request.memory_locators == (
        f"shared/source:{memory.uid[:7]}",
    )
    assert plan.memories[0].source_context_uid == source.uid

    local_uid = next(iter(local_source.memories))
    with create_pipe_input() as pipe_input:
        pipe_input.send_text(
            "\t\t\t\x15"
            f"{local_source.name}:{local_uid[:7]} --into shared/source"
            "\r\x1b"
        )
        rejected = choose_copy_setup(
            port,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert rejected is None
    assert not any(
        item["command"] == "copy" for item in store.list_checkpoints(target.name)
    )


def test_granted_copy_tui_does_not_scan_grants_for_a_bare_uid(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, _source, memory, target, _marker, _local_source = (
        _granted_copy_fixture(isolated_store, tmp_path, monkeypatch)
    )
    port = MemoryStoreCopyAndMovePort.capture(
        store,
        allow_granted_sources=True,
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(
            "\t\t\t\x15"
            f"{memory.uid[:7]} --into {target.name}"
            "\r\x1b"
        )
        plan = choose_copy_setup(
            port,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert plan is None
    assert store.load_direct(target.name).ordered_uids()


def test_move_tui_defaults_to_atomic_live_embed_retarget(isolated_store) -> None:
    store = MemoryStore()
    source, (memory,) = _context(store, "source", "move me")
    target, _ = _context(store, "target")
    watcher, _ = _context(store, "watcher")
    reference = ops.embed_memory(memory, source, watcher)
    store.save(watcher)
    store.set_current(source.name)
    port = MemoryStoreCopyAndMovePort.capture(store)

    with create_pipe_input() as pipe_input:
        # Check one Source, choose Target, retain append, then approve.
        pipe_input.send_text("\x1b[B\r\t\x1b[B\r\t\t\r")
        plan = choose_move_setup(
            port,
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
    port = MemoryStoreCopyAndMovePort.capture(store)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        plan = choose_move_setup(
            port,
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
    port = MemoryStoreCopyAndMovePort.capture(store)
    plan = port.freeze_copy(
        CopyMemoriesRequest(
            (f"{source.name}:{memory.uid[:8]}",),
            into_locator=target.name,
        )
    )
    monkeypatch.setattr(copy_command, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        copy_command.MemoryStoreCopyPort,
        "capture",
        lambda _store, **_kwargs: port,
    )
    monkeypatch.setattr(
        copy_command,
        "choose_copy_setup",
        lambda _port: plan,
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
    port = MemoryStoreCopyAndMovePort.capture(store)
    plan = port.freeze_move(
        MoveMemoriesRequest(
            (f"{source.name}:{memory.uid[:8]}",),
            into_locator=target.name,
        )
    )
    monkeypatch.setattr(move_command, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        move_command.MemoryStoreMovePort,
        "capture",
        lambda _store, **_kwargs: port,
    )
    monkeypatch.setattr(
        move_command,
        "choose_move_setup",
        lambda _port: plan,
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
