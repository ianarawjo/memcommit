"""Interactive retained References from exact READ-granted Sources."""

from __future__ import annotations

import json
import uuid

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.commands.reference.workbench import (
    ReferenceTuiSetup,
    build_reference_tui_setup,
    choose_reference_setup,
)
from memcommit.application.operations.profile.config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.application.operations.profile.model import (
    create_authority_grant,
    update_authority_grant,
)
from memcommit.application.operations.reference.application import (
    FrozenReferencePlan,
    ReferenceRequest,
)
from memcommit.application.operations.reference.runtime import MemoryStoreReferencePort
from memcommit.source_projection.presentation import source_display_text
from memcommit.persistence.store import MemoryStore


_REQUIRED = ("READ",)


def _fixture(isolated_store, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    store = MemoryStore()
    workspace = ops.init("workspace")
    ops.add(workspace, "Participant-owned note.")
    store.save(workspace)
    store.set_current(workspace.name)

    grantee = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="reference-tui-authority",
        kind="MANAGED",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    source = ops.init("authority/source")
    memory = ops.add(source, "Retain this exact readable version.")
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
        attachment_name=workspace.name,
        public_name="shared/source",
        permissions=_REQUIRED,
    )
    return store, workspace, source, memory, grant


def _granted_port(store: MemoryStore) -> MemoryStoreReferencePort:
    return MemoryStoreReferencePort.capture(
        store,
        allow_granted_sources=True,
    )


def test_granted_memory_reference_tui_separates_source_and_local_roles(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, workspace, _source, memory, _grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    port = _granted_port(store)

    setup = build_reference_tui_setup(port)
    annotation = source_display_text(
        dict(setup.memory_source_annotations)["shared/source"]
    )
    inspected = port.inspect_memory_source("shared/source")

    assert setup.selected_source == "shared/source"
    assert setup.target_names == (workspace.name,)
    assert setup.memory_source_names == ("shared/source", workspace.name)
    assert setup.memory_source_selectable_names == frozenset(
        {"shared/source", workspace.name}
    )
    assert setup.selected_memory_source == "shared/source"
    assert "GRANT" in annotation
    assert "READ" in annotation
    assert "REFERENCE" in annotation
    assert inspected.name == "shared/source"
    assert inspected.memories[memory.uid].content == memory.content


def test_granted_memory_reference_tui_excludes_query_only_source(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, workspace, _source, _memory, grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    update_authority_grant(
        grant.uid,
        permissions=("QUERY",),
    )

    setup = build_reference_tui_setup(_granted_port(store))

    assert setup.memory_source_names == (workspace.name,)
    assert setup.memory_source_selectable_names == frozenset({workspace.name})
    assert setup.memory_source_annotations == ()


def test_local_only_reference_tui_does_not_consult_active_profile_grants(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, workspace, _source, _memory, _grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    port = MemoryStoreReferencePort.capture(store)

    setup = build_reference_tui_setup(port)

    assert setup.memory_source_names == (workspace.name,)
    with pytest.raises(FileNotFoundError, match="does not exist"):
        port.inspect_memory_source("shared/source")


def test_granted_memory_reference_tui_freezes_qualified_source_and_local_target(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, workspace, _source, memory, _grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    with create_pipe_input() as pipe_input:
        # Local Target → qualified public Source → exact direct Memory →
        # proposed command.
        pipe_input.send_text("\x1b[B\r\r\r\x1b[B\r")
        result = choose_reference_setup(
            _granted_port(store),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert isinstance(result, FrozenReferencePlan)
    assert result.request == ReferenceRequest(
        memory.uid,
        "shared/source",
        workspace.name,
    )
    assert result.source_name == "shared/source"
    assert result.into_name == workspace.name
    # Setup freezes only; Apply remains the separate runtime boundary.
    assert store.list_checkpoints(workspace.name) == []


def test_reference_tui_model_rejects_a_granted_target_role() -> None:
    with pytest.raises(ValueError, match="initial Target Context is unavailable"):
        ReferenceTuiSetup(
            names=("workspace",),
            selected_source="workspace",
            selected_target="shared/source",
            memory_source_names=("shared/source", "workspace"),
            memory_source_selectable_names=frozenset({"shared/source", "workspace"}),
            selected_memory_source="shared/source",
        )
