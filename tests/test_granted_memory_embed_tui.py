"""Interactive granted direct-Memory Embed role and exact-command contracts."""

from __future__ import annotations

import json
import uuid

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

import memcommit.ops as ops
from memcommit.context import MemoryRef
from memcommit.embed_application import (
    FrozenMemoryEmbedPlan,
    MemoryEmbedRequest,
    run_memory_embed,
)
from memcommit.embed_runtime import MemoryStoreEmbedPort
from memcommit.interfaces.tui.components.direct_item_placement import DirectItemGap
from memcommit.interfaces.tui.operations.embed import (
    build_embed_tui_setup,
    choose_embed_setup,
    memory_embed_exact_command_review,
    parse_embed_command_argv,
)
from memcommit.profile_config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.profiles import create_authority_grant, update_authority_grant
from memcommit.source_projection.presentation import source_display_text
from memcommit.store import MemoryStore


def _fixture(isolated_store, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    local = MemoryStore()
    target = ops.init("guide")
    first_marker = ops.add(target, "Keep this local opening marker.")
    second_marker = ops.add(target, "Keep this local closing marker.")
    local.save(target)
    local.set_current(target.name)

    grantee = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="advisor-authority",
        kind="MANAGED",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    source = ops.init("private-advice")
    memory = ops.add(source, "Use the authority's live reviewed guidance.")
    authority_store.save(source)

    registry = ProfileRegistry(
        generation=1,
        active_uid=grantee.uid,
        profiles=(grantee, authority),
        grants=(),
    )
    path = profile_registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry.to_dict(), indent=2) + "\n")
    _registry, grant = create_authority_grant(
        authority_name=authority.name,
        grantee_name=grantee.name,
        resource_name=source.name,
        attachment_name=target.name,
        public_name="advisor",
        permissions=("READ", "EMBED"),
    )
    return local, target, first_marker, second_marker, source, memory, grant


def test_granted_memory_source_catalog_is_authorized_without_broadening_into(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, target, _first, _second, source, memory, _grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    port = MemoryStoreEmbedPort.capture(store, allow_granted_sources=True)

    setup = build_embed_tui_setup(port)
    annotations = dict(setup.memory_source_annotations)

    assert setup.into_names == (target.name,)
    assert "advisor" not in setup.into_names
    assert "advisor" in setup.memory_source_names
    assert "advisor" in setup.memory_source_selectable_names
    assert "advisor" in setup.memory_source_granted_names
    assert source_display_text(annotations["advisor"]) == "GRANT · READ · EMBED"
    preview = port.inspect_memory_source("advisor")
    assert preview.name == "advisor"
    assert preview.uid == source.uid
    assert preview.memories[memory.uid].content == memory.content

    local_only = build_embed_tui_setup(MemoryStoreEmbedPort.capture(store))
    assert "advisor" not in local_only.child_names
    assert "advisor" not in local_only.memory_source_names


def test_read_only_grant_is_visible_but_not_a_memory_embed_source(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, _target, _first, _second, _source, _memory, grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    update_authority_grant(grant.uid, permissions=("READ",))

    setup = build_embed_tui_setup(
        MemoryStoreEmbedPort.capture(store, allow_granted_sources=True)
    )

    assert "advisor" in setup.memory_source_names
    assert "advisor" not in setup.memory_source_selectable_names
    assert "advisor" not in setup.memory_source_granted_names
    assert source_display_text(dict(setup.memory_source_annotations)["advisor"]) == (
        "GRANT · READ"
    )


def test_granted_memory_review_uses_qualified_locator_and_round_trips() -> None:
    gap = DirectItemGap(position=0, previous_uid=None, next_uid=None)

    review = memory_embed_exact_command_review(
        "advisor",
        "12345678-1234-1234-1234-123456789abc",
        "guide",
        gap,
        item_count=0,
        memory_selector="1234567",
        qualified_locator=True,
    )

    assert review.argv == (
        "mem",
        "embed",
        "advisor:1234567",
        "--into",
        "guide",
    )
    assert parse_embed_command_argv(review.argv) == MemoryEmbedRequest(
        "1234567",
        "advisor",
        "guide",
    )


def test_exact_command_rejects_qualified_and_from_owner_spellings_together() -> None:
    try:
        parse_embed_command_argv(
            (
                "mem",
                "embed",
                "advisor:1234567",
                "--from",
                "other",
                "--into",
                "guide",
            )
        )
    except ValueError as error:
        assert "either CONTEXT:UID or an explicit Context option" in str(error)
    else:
        raise AssertionError("two Memory owner spellings were accepted together")


def test_interactive_granted_memory_embed_returns_exact_local_gap_plan(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, target, first, second, _source, memory, _grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    port = MemoryStoreEmbedPort.capture(store, allow_granted_sources=True)

    with create_pipe_input() as pipe_input:
        # Memory mode → public Source → direct Memory → local Target → middle
        # gap → exact qualified command. The TUI only freezes; Apply is below.
        pipe_input.send_text("\x1b[C\t\x1b[A\r\x1b[B\r\t\t\x1b[A\r\t\r")
        plan = choose_embed_setup(
            port,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert isinstance(plan, FrozenMemoryEmbedPlan)
    assert plan.source_name == "advisor"
    assert plan.memory_uid == memory.uid
    assert plan.into_name == target.name
    assert plan.placement.previous_uid == first.uid
    assert plan.placement.next_uid == second.uid
    assert store.load_direct(target.name).ordered_uids() == [first.uid, second.uid]

    result = run_memory_embed(plan.request, port=port, frozen_plan=plan)
    direct = store.load_direct(target.name)
    assert direct.ordered_uids() == [first.uid, result.embed_uid, second.uid]
    link = direct.memories[result.embed_uid]
    assert isinstance(link, MemoryRef) and link.is_granted and link.is_live
