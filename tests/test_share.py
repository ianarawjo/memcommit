"""Grant-backed cross-Profile delivery behavior."""

from __future__ import annotations

import hashlib
import json
import importlib
import uuid

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

from memcommit.cli import app
from memcommit.commands.share.flow import choose_share_endpoint
from memcommit.commands.share.viewer import ShareViewerReceipt
from memcommit.commands.share.viewer import (
    run_share_unavailable_viewer,
    run_share_viewer,
    share_context_text,
    share_exact_command_text,
    share_memories_text,
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
    load_profile_registry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.store import MemoryStore, context_record_digest
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


def test_direct_share_preserves_version_one_consent_and_uid_identity(
    tmp_path,
    monkeypatch,
):
    _sender_store, _receiver_store, source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )
    registry = load_profile_registry()
    grant = registry.grants[0]
    source_digest = context_record_digest(source)
    record = {
        "endpoint_grant_uid": grant.uid,
        "recipient": grant.public_name,
        "sender_profile_uid": registry.active.uid,
        "source_context_uid": source.uid,
        "source_digest": source_digest,
        "memories": [
            {"source_memory_uid": memory.uid, "content": memory.content}
            for memory in source.iter_items()
            if isinstance(memory, Memory)
        ],
    }
    encoded = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    expected_consent_digest = hashlib.sha256(encoded).hexdigest()
    expected_uid = str(
        uuid.uuid5(
            uuid.UUID(grant.uid),
            "\0".join(
                (
                    registry.active.uid,
                    source.uid,
                    source_digest,
                    expected_consent_digest,
                )
            ),
        )
    )

    preview = prepare_share(source.name, grant.public_name)

    assert preview.consent_digest == expected_consent_digest
    assert preview.uid == expected_uid
    assert preview.include_descendants is False


def test_bare_share_opens_tty_flow_and_sends_selected_context(
    tmp_path,
    monkeypatch,
):
    _sender_store, receiver_store, source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )
    share_command = importlib.import_module("memcommit.commands.share.command")
    share_viewer = importlib.import_module("memcommit.commands.share.viewer")
    seen = {}

    monkeypatch.setattr(share_command, "_interactive_terminal", lambda: True)

    def send(preview, **_kwargs):
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


def test_viewer_endpoint_browse_refreezes_and_applies_the_updated_command(
    tmp_path,
    monkeypatch,
):
    _sender_store, receiver_store, source, receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )
    endpoint = Context(
        uid=str(uuid.uuid4()),
        name="remote/research/archive-agent",
    )
    receiver_store.create_context(endpoint)
    registry = load_profile_registry()
    original = registry.grants[0]
    alternate = AuthorityGrant(
        uid=str(uuid.uuid4()),
        revision=1,
        authority_profile_uid=receiver.uid,
        grantee_profile_uid=registry.active.uid,
        attachment_context_uid=original.attachment_context_uid,
        attachment_context_name=original.attachment_context_name,
        resource_kind=GRANT_RESOURCE_CONTEXT_TREE,
        resource_uid=endpoint.uid,
        resource_name=endpoint.name,
        public_name="research/archive-agent",
        permissions=("SHARE",),
        contexts=(GrantContextBinding(uid=endpoint.uid, name=endpoint.name),),
    )
    updated_registry = ProfileRegistry(
        generation=registry.generation + 1,
        active_uid=registry.active_uid,
        profiles=registry.profiles,
        grants=registry.grants + (alternate,),
    )
    profile_registry_file().write_text(
        json.dumps(updated_registry.to_dict()) + "\n",
        encoding="utf-8",
    )

    share_command = importlib.import_module("memcommit.commands.share.command")
    share_flow = importlib.import_module("memcommit.commands.share.flow")
    share_viewer = importlib.import_module("memcommit.commands.share.viewer")
    original_preview = prepare_share(source.name, "government/healthcare-agent")
    seen = []

    monkeypatch.setattr(share_command, "_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        share_flow,
        "choose_share_preview",
        lambda *_args, **_kwargs: original_preview,
    )
    monkeypatch.setattr(
        share_flow,
        "choose_share_endpoint",
        lambda **_kwargs: "research/archive-agent",
    )

    def review(preview, **_kwargs):
        seen.append(preview)
        return ShareViewerReceipt(
            action="browse_endpoint" if len(seen) == 1 else "send"
        )

    monkeypatch.setattr(share_viewer, "run_share_viewer", review)

    result = runner.invoke(app, ["share", source.name])

    assert result.exit_code == 0, result.stderr or result.output
    assert [preview.endpoint for preview in seen] == [
        "government/healthcare-agent",
        "research/archive-agent",
    ]
    assert "To: research/archive-agent" in result.output
    assert seen[0].consent_digest != seen[1].consent_digest
    delivered = receiver_store.load_direct(seen[1].receiver_context)
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
    share_command = importlib.import_module("memcommit.commands.share.command")
    share_viewer = importlib.import_module("memcommit.commands.share.viewer")
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


def test_share_viewer_presents_from_to_memories_and_exact_apply(
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
    assert "government/healthcare-agent" not in context_text
    assert "CONSENT DIGEST" not in context_text
    memory_text = share_memories_text(preview)
    assert "M1" not in memory_text
    for memory in preview.memories:
        assert memory.uid in memory_text
        assert memory.content in memory_text
    assert share_exact_command_text(preview) == (
        "mem share local/personal-memory/severed --direct "
        "--to government/healthcare-agent"
    )

    with create_pipe_input() as pipe_input:
        # FROM -> TO -> MEMORIES -> APPLY, then explicitly apply.
        pipe_input.send_text("\t\t\t\r")
        receipt = run_share_viewer(
            preview,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt.action == "send"


def test_share_endpoint_surface_enter_requests_browse_without_sending(
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
        pipe_input.send_text("\t\r")
        receipt = run_share_viewer(
            preview,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
            navigation=navigation,
        )

    assert receipt.action == "browse_endpoint"
    assert navigation.pane == "responses"


def test_explicit_endpoint_browse_opens_even_for_one_available_endpoint(
    tmp_path,
    monkeypatch,
):
    _study_share_topology(tmp_path, monkeypatch)
    seen = {}

    def choose(names, **kwargs):
        seen["names"] = names
        seen["current"] = kwargs["current"]
        return names[0]

    selected = choose_share_endpoint(
        current="government/healthcare-agent",
        chooser=choose,
    )

    assert selected == "government/healthcare-agent"
    assert seen == {
        "names": ("government/healthcare-agent",),
        "current": "government/healthcare-agent",
    }


def test_share_source_boundary_moves_to_the_separate_endpoint_surface(
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
    assert navigation.section_uid == "SHARE:CONTEXT"
    assert navigation.pane == "responses"


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
        # FROM -> TO -> MEMORIES first -> MEMORIES second.
        # Tab enters APPLY and Shift-Tab must restore the second Memory.
        pipe_input.send_text("\x1b[B\x1b[B\x1b[B\t\x1b[Zq")
        receipt = run_share_viewer(
            preview,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
            navigation=navigation,
        )

    assert receipt.action == "close"
    assert navigation.section_uid == "SHARE:CONTEXT"
    assert navigation.pane == "items"
    assert navigation.row_index == 1


def test_share_arrow_boundaries_reach_apply_before_enter_sends(
    tmp_path,
    monkeypatch,
):
    _sender_store, _receiver_store, source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )
    preview = prepare_share(source.name, "government/healthcare-agent")

    with create_pipe_input() as pipe_input:
        # FROM, TO, two Memory rows, then the APPLY Surface.
        pipe_input.send_text("\x1b[B\x1b[B\x1b[B\x1b[B\r")
        receipt = run_share_viewer(
            preview,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt.action == "send"


def test_share_enter_outside_to_and_apply_does_not_send(
    tmp_path,
    monkeypatch,
):
    _sender_store, _receiver_store, source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )
    preview = prepare_share(source.name, "government/healthcare-agent")

    with create_pipe_input() as pipe_input:
        # Enter is inert in FROM and MEMORIES. TO and APPLY own activation.
        pipe_input.send_text("\r\t\t\rq")
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


def _add_share_subtree(
    sender_store: MemoryStore, source: Context
) -> tuple[Context, ...]:
    child = Context(uid=str(uuid.uuid4()), name=source.name + "/preferences")
    child.add("Use a written follow-up after every appointment.")
    empty = Context(uid=str(uuid.uuid4()), name=source.name + "/empty-lane")
    grandchild = Context(
        uid=str(uuid.uuid4()),
        name=source.name + "/preferences/medication",
    )
    grandchild.add("Confirm medication changes with the prescribing clinician.")
    for context in (child, empty, grandchild):
        sender_store.create_context(context)
    return child, empty, grandchild


def test_recursive_share_preserves_the_complete_lexical_context_bundle(
    tmp_path,
    monkeypatch,
):
    sender_store, receiver_store, source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )
    child, empty, grandchild = _add_share_subtree(sender_store, source)

    first = runner.invoke(
        app,
        [
            "share",
            source.name,
            "-r",
            "--to",
            "government/healthcare-agent",
        ],
    )

    assert first.exit_code == 0, first.stderr or first.output
    assert "Shared Context bundle." in first.output
    assert "Contexts: 4" in first.output
    assert "Memories: 4" in first.output
    receiver_line = next(
        line for line in first.output.splitlines() if line.startswith("Receiver: ")
    )
    receiver_root = receiver_line.split(":", 2)[2]
    expected = {
        source.name: receiver_root,
        child.name: receiver_root + "/preferences",
        empty.name: receiver_root + "/empty-lane",
        grandchild.name: receiver_root + "/preferences/medication",
    }
    for source_name, receiver_name in expected.items():
        received = receiver_store.load_direct(receiver_name)
        receipt = receiver_store.list_checkpoints(receiver_name)[0]
        share = receipt["args"]["share"]
        assert share["schema_version"] == 2
        assert share["include_descendants"] is True
        assert share["context_count"] == 4
        assert share["source_context_name"] == source_name
        assert share["receiver_root_context_name"] == receiver_root
        assert len(share["contexts"]) == 4
        if source_name == empty.name:
            assert tuple(received.iter_items()) == ()

    second = runner.invoke(
        app,
        [
            "share",
            source.name,
            "--recursive",
            "--to",
            "government/healthcare-agent",
        ],
    )
    assert second.exit_code == 0, second.stderr or second.output
    assert "bundle was already shared" in second.output


def test_direct_share_excludes_lexical_descendants(tmp_path, monkeypatch):
    sender_store, receiver_store, source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )
    child, _empty, _grandchild = _add_share_subtree(sender_store, source)

    result = runner.invoke(
        app,
        [
            "share",
            source.name,
            "-d",
            "--to",
            "government/healthcare-agent",
        ],
    )

    assert result.exit_code == 0, result.stderr or result.output
    assert "Shared Context." in result.output
    assert "Contexts:" not in result.output
    receiver_line = next(
        line for line in result.output.splitlines() if line.startswith("Receiver: ")
    )
    receiver_root = receiver_line.split(":", 2)[2]
    root = receiver_store.load_direct(receiver_root)
    assert len(tuple(root.iter_items())) == 2
    with pytest.raises(FileNotFoundError):
        receiver_store.load_direct(receiver_root + child.name[len(source.name) :])
    assert (
        receiver_store.list_checkpoints(receiver_root)[0]["args"]["share"][
            "schema_version"
        ]
        == 1
    )


def test_share_rejects_conflicting_direct_and_recursive_flags(
    tmp_path,
    monkeypatch,
):
    _sender_store, _receiver_store, source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )

    result = runner.invoke(
        app,
        [
            "share",
            source.name,
            "-d",
            "-r",
            "--to",
            "government/healthcare-agent",
        ],
    )

    assert result.exit_code == 1
    assert "Choose either --direct or --recursive" in result.stderr


def test_recursive_prepared_share_rejects_new_descendant_after_review(
    tmp_path,
    monkeypatch,
):
    sender_store, receiver_store, source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )
    _add_share_subtree(sender_store, source)
    preview = prepare_share(
        source.name,
        "government/healthcare-agent",
        include_descendants=True,
    )
    late = Context(uid=str(uuid.uuid4()), name=source.name + "/late")
    late.add("Added after recursive review.")
    sender_store.create_context(late)

    with pytest.raises(ShareError, match="selected Share content changed"):
        deliver_prepared_share(preview)
    with pytest.raises(FileNotFoundError):
        receiver_store.load_direct(preview.receiver_context)


def test_recursive_receiver_creation_rolls_back_an_earlier_bundle_member(
    tmp_path,
    monkeypatch,
):
    sender_store, receiver_store, source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )
    child = Context(uid=str(uuid.uuid4()), name=source.name + "/child")
    child.add("Child content.")
    sender_store.create_context(child)
    preview = prepare_share(
        source.name,
        "government/healthcare-agent",
        include_descendants=True,
    )
    original_save = MemoryStore._save_locked

    def fail_second_receiver_member(self, context, checkpoint, **kwargs):
        if "/received-shares/" in context.name and context.name.endswith("/child"):
            raise OSError("simulated receiver write failure")
        return original_save(self, context, checkpoint, **kwargs)

    monkeypatch.setattr(MemoryStore, "_save_locked", fail_second_receiver_member)

    with pytest.raises(OSError, match="simulated receiver write failure"):
        deliver_prepared_share(preview)
    for context in preview.contexts:
        with pytest.raises(FileNotFoundError):
            receiver_store.load_direct(context.receiver_context)


def test_recursive_share_viewer_names_every_context_in_the_consent_unit(
    tmp_path,
    monkeypatch,
):
    sender_store, _receiver_store, source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )
    _add_share_subtree(sender_store, source)
    preview = prepare_share(
        source.name,
        "government/healthcare-agent",
        include_descendants=True,
    )

    rendered = share_context_text(preview)

    lines = rendered.splitlines()
    assert lines[0].endswith("· 4 CONTEXTS · 4 MEMORIES")
    assert len(lines) == len(preview.contexts) + 1
    assert "" not in lines
    for index, context in enumerate(preview.contexts, start=1):
        assert lines[index].startswith(f"C{index} · {context.source_context} · ")
        assert lines[index].endswith((" Memory", " Memories"))
    assert share_exact_command_text(preview) == (
        "mem share local/personal-memory/severed --recursive "
        "--to government/healthcare-agent"
    )


def test_recursive_share_compact_context_roster_crosses_to_endpoint_surface(
    tmp_path,
    monkeypatch,
):
    sender_store, _receiver_store, source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )
    for index in range(15):
        child = Context(
            uid=str(uuid.uuid4()),
            name=f"{source.name}/lane-{index:02d}",
        )
        child.add(f"Memory for recursive lane {index:02d}.")
        sender_store.create_context(child)
    preview = prepare_share(
        source.name,
        "government/healthcare-agent",
        include_descendants=True,
    )
    navigation = SessionWorkbenchNavigation()

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B" * (len(preview.contexts) + 1) + "q")
        receipt = run_share_viewer(
            preview,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
            navigation=navigation,
        )

    assert receipt.action == "close"
    assert navigation.section_uid == f"SHARE:CONTEXT:{len(preview.contexts)}"
    assert navigation.pane == "responses"


def test_incomplete_recursive_cli_keeps_range_through_tty_review(
    tmp_path,
    monkeypatch,
):
    sender_store, _receiver_store, source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )
    _add_share_subtree(sender_store, source)
    share_command = importlib.import_module("memcommit.commands.share.command")
    share_viewer = importlib.import_module("memcommit.commands.share.viewer")
    seen = {}
    monkeypatch.setattr(share_command, "_interactive_terminal", lambda: True)

    def close(preview, **_kwargs):
        seen["preview"] = preview
        return ShareViewerReceipt(action="close")

    monkeypatch.setattr(share_viewer, "run_share_viewer", close)

    result = runner.invoke(app, ["share", source.name, "-r"])

    assert result.exit_code == 0, result.stderr or result.output
    assert "nothing was sent" in result.output
    assert seen["preview"].include_descendants is True
    assert len(seen["preview"].contexts) == 4


def test_share_help_exposes_direct_and_recursive_range_flags():
    result = runner.invoke(app, ["share", "-h"])

    assert result.exit_code == 0, result.stderr or result.output
    assert "--direct" in result.output
    assert "-d" in result.output
    assert "--recursive" in result.output
    assert "-r" in result.output
