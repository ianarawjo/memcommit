"""Grant-backed cross-Profile delivery behavior."""

from __future__ import annotations

import json
import importlib
import uuid

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

from memcommit.cli import app
from memcommit.commands.share_viewer import ShareViewerReceipt
from memcommit.commands.share_viewer import (
    run_share_unavailable_viewer,
    run_share_viewer,
    share_context_text,
)
from memcommit.context import AutoCheckpoint, Context, Memory
from memcommit.session_workbench_navigation import SessionWorkbenchNavigation
from memcommit.profile_config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    GRANT_RESOURCE_CONTEXT_TREE,
    AuthorityGrant,
    GrantContextBinding,
    ProfileEntry,
    ProfileRegistry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.store import MemoryStore
from memcommit.share import (
    ShareError,
    deliver_prepared_share,
    list_share_sources,
    prepare_share,
)


runner = CliRunner(mix_stderr=False)


def _study_share_topology(tmp_path, monkeypatch, *, allow_share: bool = True):
    monkeypatch.setenv("HOME", str(tmp_path))
    sender = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="study-task-3",
        kind="MANAGED",
    )
    receiver = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="study-granted-memory",
        kind="MANAGED",
    )
    sender_store = MemoryStore(root=profile_store_dir(sender))
    receiver_store = MemoryStore(root=profile_store_dir(receiver))

    attachment = Context(uid=str(uuid.uuid4()), name="local/personal-memory")
    sender_store.create_context(attachment)
    source = Context(
        uid=str(uuid.uuid4()),
        name="local/personal-memory/severed",
    )
    source.add(Memory(uid=str(uuid.uuid4()), content="Use a text reminder."))
    source.add(
        Memory(uid=str(uuid.uuid4()), content="Avoid appointments before 09:00.")
    )
    sender_store.create_context(
        source,
        AutoCheckpoint(
            command="sever",
            args={"sever": {"output": source.name}},
            description="Created reviewed local outbound draft; not sent.",
        ),
    )
    sender_store.set_current(source.name)

    endpoint = Context(
        uid=str(uuid.uuid4()),
        name="remote/government/healthcare-agent",
    )
    receiver_store.create_context(endpoint)
    grant = AuthorityGrant(
        uid=str(uuid.uuid4()),
        revision=1,
        authority_profile_uid=receiver.uid,
        grantee_profile_uid=sender.uid,
        attachment_context_uid=attachment.uid,
        attachment_context_name=attachment.name,
        resource_kind=GRANT_RESOURCE_CONTEXT_TREE,
        resource_uid=endpoint.uid,
        resource_name=endpoint.name,
        public_name="government/healthcare-agent",
        permissions=(("SHARE",) if allow_share else ("QUERY",)),
        contexts=(GrantContextBinding(uid=endpoint.uid, name=endpoint.name),),
    )
    authoring = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    registry = ProfileRegistry(
        generation=1,
        active_uid=sender.uid,
        profiles=(authoring, sender, receiver),
        grants=(grant,),
    )
    path = profile_registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry.to_dict()) + "\n", encoding="utf-8")
    return sender_store, receiver_store, source, receiver


def test_share_creates_real_receiver_memories_and_is_idempotent(
    tmp_path,
    monkeypatch,
):
    _sender_store, receiver_store, source, receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )

    first = runner.invoke(
        app,
        ["share", source.name, "--to", "government/healthcare-agent"],
    )
    assert first.exit_code == 0, first.stderr or first.output
    assert "Shared Context." in first.output
    receiver_line = next(
        line for line in first.output.splitlines() if line.startswith("Receiver: ")
    )
    receiver_name = receiver_line.split(":", 2)[2]
    delivered = receiver_store.load_direct(receiver_name)
    assert [
        item.content for item in delivered.iter_items() if isinstance(item, Memory)
    ] == ["Use a text reminder.", "Avoid appointments before 09:00."]
    receipt = receiver_store.list_checkpoints(receiver_name)[0]
    assert receipt["command"] == "share-receive"
    assert receipt["args"]["share"]["sender_profile_name"] == "study-task-3"
    assert receipt["args"]["share"]["endpoint"] == "government/healthcare-agent"
    assert receiver.name in receiver_line

    second = runner.invoke(
        app,
        ["share", source.name, "--to", "government/healthcare-agent"],
    )
    assert second.exit_code == 0, second.stderr or second.output
    assert "already shared" in second.output
    assert second.output.count("Share: ") == 1


def test_bare_share_opens_tty_flow_and_sends_selected_context(
    tmp_path,
    monkeypatch,
):
    _sender_store, receiver_store, source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )
    share_command = importlib.import_module("memcommit.commands.share")
    share_viewer = importlib.import_module("memcommit.commands.share_viewer")
    seen = {}

    monkeypatch.setattr(share_command, "_interactive_terminal", lambda: True)

    def send(preview):
        seen["preview"] = preview
        return ShareViewerReceipt(action="send")

    monkeypatch.setattr(share_viewer, "run_share_viewer", send)

    result = runner.invoke(app, ["share"])

    assert result.exit_code == 0, result.stderr or result.output
    assert "Shared Context." in result.output
    preview = seen["preview"]
    assert preview.source_context == source.name
    delivered = receiver_store.load_direct(preview.receiver_context)
    assert [memory.content for memory in delivered.iter_items()] == [
        "Use a text reminder.",
        "Avoid appointments before 09:00.",
    ]


def test_complete_share_operands_bypass_tty_viewer(
    tmp_path,
    monkeypatch,
):
    _sender_store, _receiver_store, source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )
    share_command = importlib.import_module("memcommit.commands.share")
    share_viewer = importlib.import_module("memcommit.commands.share_viewer")
    monkeypatch.setattr(share_command, "_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        share_viewer,
        "run_share_viewer",
        lambda _preview: pytest.fail("explicit Share must bypass the TUI"),
    )

    result = runner.invoke(
        app,
        ["share", source.name, "--to", "government/healthcare-agent"],
    )

    assert result.exit_code == 0, result.stderr or result.output
    assert "Shared Context." in result.output


def test_changed_ordinary_context_remains_eligible_for_fresh_share_review(
    tmp_path,
    monkeypatch,
):
    sender_store, _receiver_store, source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )
    changed = sender_store.load_direct(source.name)
    changed.add("A newly added direct Memory.")
    sender_store.save(
        changed,
        AutoCheckpoint(
            command="add",
            args={"content": "A newly added direct Memory."},
            description="Change an ordinary Context before fresh Share selection.",
        ),
    )
    current, choices = list_share_sources()

    assert current == source.name
    assert source.name in choices
    assert len(tuple(sender_store.load_direct(source.name).iter_items())) == 3


def test_unavailable_share_surface_is_read_only_and_closable():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\t\r\x1b")
        receipt = run_share_unavailable_viewer(
            "No eligible Context.",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt.action == "close"


def test_share_viewer_presents_context_then_memories_and_only_send_action(
    tmp_path,
    monkeypatch,
):
    _sender_store, _receiver_store, source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )
    preview = prepare_share(source.name, "government/healthcare-agent")

    context_text = share_context_text(preview)
    assert "CONTEXT TO SEND" in context_text
    assert source.name in context_text
    assert "MEMORIES · 2" in context_text
    assert "TO · government/healthcare-agent" in context_text
    assert "CONSENT DIGEST" not in context_text

    with create_pipe_input() as pipe_input:
        # CONTEXT -> MEMORIES -> ACTION, then explicitly send.
        pipe_input.send_text("\t\t\r")
        receipt = run_share_viewer(
            preview,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt.action == "send"


def test_share_context_moves_between_stable_semantic_sections(
    tmp_path,
    monkeypatch,
):
    _sender_store, _receiver_store, source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )
    preview = prepare_share(source.name, "government/healthcare-agent")
    navigation = SessionWorkbenchNavigation()

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[Bq")
        receipt = run_share_viewer(
            preview,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
            navigation=navigation,
        )

    assert receipt.action == "close"
    assert navigation.section_uid == "SHARE:DESTINATION"


def test_share_arrow_boundaries_cross_surfaces_and_tab_preserves_memory_cursor(
    tmp_path,
    monkeypatch,
):
    _sender_store, _receiver_store, source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )
    preview = prepare_share(source.name, "government/healthcare-agent")
    navigation = SessionWorkbenchNavigation()

    with create_pipe_input() as pipe_input:
        # CONTEXT title -> destination -> MEMORIES first -> MEMORIES second.
        # Tab enters ACTION and Shift-Tab must restore the second Memory.
        pipe_input.send_text("\x1b[B\x1b[B\x1b[B\t\x1b[Zq")
        receipt = run_share_viewer(
            preview,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
            navigation=navigation,
        )

    assert receipt.action == "close"
    assert navigation.section_uid == "SHARE:DESTINATION"
    assert navigation.pane == "items"
    assert navigation.row_index == 1


def test_share_arrow_boundaries_reach_action_before_enter_sends(
    tmp_path,
    monkeypatch,
):
    _sender_store, _receiver_store, source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )
    preview = prepare_share(source.name, "government/healthcare-agent")

    with create_pipe_input() as pipe_input:
        # Two Context stops, two Memory rows, then the ACTION Surface.
        pipe_input.send_text("\x1b[B\x1b[B\x1b[B\x1b[B\r")
        receipt = run_share_viewer(
            preview,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt.action == "send"


def test_share_enter_outside_action_does_not_send(
    tmp_path,
    monkeypatch,
):
    _sender_store, _receiver_store, source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )
    preview = prepare_share(source.name, "government/healthcare-agent")

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\r\t\rq")
        receipt = run_share_viewer(
            preview,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt.action == "close"


@pytest.mark.parametrize("close_key", ["\x1b", "\x7f"])
def test_closing_share_viewer_does_not_deliver(
    tmp_path,
    monkeypatch,
    close_key,
):
    _sender_store, receiver_store, source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )
    preview = prepare_share(source.name, "government/healthcare-agent")

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(close_key)
        receipt = run_share_viewer(
            preview,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt.action == "close"
    with pytest.raises(FileNotFoundError):
        receiver_store.load_direct(preview.receiver_context)


def test_prepared_share_rejects_context_changed_after_review(
    tmp_path,
    monkeypatch,
):
    sender_store, _receiver_store, source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )
    preview = prepare_share(source.name, "government/healthcare-agent")
    changed = sender_store.load_direct(source.name)
    changed.add("Changed while the Share viewer was open.")
    sender_store.save(
        changed,
        AutoCheckpoint(
            command="add",
            args={"content": "Changed while the Share viewer was open."},
            description="Changed the reviewed outbound Context.",
        ),
    )

    with pytest.raises(ShareError, match="selected Share content changed"):
        deliver_prepared_share(preview)


def test_share_requires_endpoint_capability(tmp_path, monkeypatch):
    _sender_store, _receiver_store, source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
        allow_share=False,
    )
    result = runner.invoke(
        app,
        ["share", source.name, "--to", "government/healthcare-agent"],
    )
    assert result.exit_code == 1
    assert (
        "Share endpoint 'government/healthcare-agent' does not exist" in result.stderr
    )


def test_share_accepts_ordinary_context_without_sever_provenance(tmp_path, monkeypatch):
    sender_store, _receiver_store, _source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )
    ordinary = Context(uid=str(uuid.uuid4()), name="local/personal-memory/manual")
    ordinary.add("Unreviewed private content")
    sender_store.create_context(ordinary)
    result = runner.invoke(
        app,
        ["share", ordinary.name, "--to", "government/healthcare-agent"],
    )
    assert result.exit_code == 0, result.stderr or result.output
    assert "Shared Context." in result.output


def test_share_reviews_current_context_even_when_it_changed_after_sever(
    tmp_path,
    monkeypatch,
):
    sender_store, _receiver_store, source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )
    changed = sender_store.load_direct(source.name)
    changed.add("Added after the reviewed consent unit")
    sender_store.save(
        changed,
        AutoCheckpoint(
            command="add",
            args={"content": "Added after the reviewed consent unit"},
            description="Changed the outbound draft after review.",
        ),
    )

    result = runner.invoke(
        app,
        ["share", source.name, "--to", "government/healthcare-agent"],
    )

    assert result.exit_code == 0, result.stderr or result.output
    assert "Shared Context." in result.output
