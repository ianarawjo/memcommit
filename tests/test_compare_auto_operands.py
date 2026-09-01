from __future__ import annotations

import json
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.adapters.console.commands.compare.command as compare_command
import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.core.context import Memory
from memcommit.providers.policy import ResolvedProviderPolicy
from memcommit.application.operations.profile.config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.application.operations.profile.model import authority_grant_snapshot_lock
from tests.grant_placement_support import create_authority_grant_with_placement
from memcommit.persistence.store import MemoryStore
from memcommit.adapters.console.commands.compare.targeting import (
    CompareTargetingError,
    resolve_compare_cli_targets,
)


runner = CliRunner()


class _CapturingSummaryProvider:
    def __init__(self) -> None:
        self.payloads: list[dict[str, object]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "compare_summary"
        payload = json.loads(prompt.split("COMPARISON SUMMARY PAYLOAD:\n", 1)[1])
        self.payloads.append(payload)
        primary_ids = [
            row["id"]
            for frame in payload["frames"]
            for row in frame["memories"]
            if row["role"] == "PRIMARY"
        ]
        return json.dumps(
            {
                "text": "The selected peer Memories express different policies.",
                "source_ids": primary_ids,
            }
        )


def _patch_summary_provider(monkeypatch, provider):
    policy = ResolvedProviderPolicy(
        operation="compare_summary",
        mode="PRODUCTION",
        provider_id="codex_chatgpt",
        model="test-model",
        reasoning_effort="none",
        timeout_seconds=30.0,
        source="GLOBAL_DEFAULT",
    )
    monkeypatch.setattr(
        compare_command,
        "connect_operation_provider",
        lambda _operation: (provider, policy),
    )


def _contents(frame: dict[str, object], role: str) -> list[str]:
    return [row["content"] for row in frame["memories"] if row["role"] == role]


def test_compare_auto_types_two_bare_memory_operands_without_current(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    reference = ops.init("auto/reference")
    reference_focus = Memory(
        uid="084b1111-1111-4111-8111-111111111111",
        content="Use short descriptive headings.",
    )
    reference.add(reference_focus)
    reference.add(
        Memory(
            uid="11111111-1111-4111-8111-111111111111",
            content="Reference-only neighboring guidance.",
        )
    )
    compared = ops.init("auto/compared")
    compared_focus = Memory(
        uid="084f2222-2222-4222-8222-222222222222",
        content="Use continuous paragraph transitions.",
    )
    compared.add(compared_focus)
    compared.add(
        Memory(
            uid="22222222-2222-4222-8222-222222222222",
            content="Compared-only neighboring guidance.",
        )
    )
    store.create_context(reference)
    store.create_context(compared)
    provider = _CapturingSummaryProvider()
    _patch_summary_provider(monkeypatch, provider)

    result = runner.invoke(
        app,
        ["compare", reference_focus.uid[:4], compared_focus.uid[:4], "--snapshot"],
    )

    assert result.exit_code == 0, result.output
    assert f"Compare · {reference.name} ↔ {compared.name}" in result.output
    assert len(provider.payloads) == 1
    frames = provider.payloads[0]["frames"]
    assert _contents(frames[0], "PRIMARY") == [reference_focus.content]
    assert _contents(frames[0], "CONTEXT") == ["Reference-only neighboring guidance."]
    assert _contents(frames[1], "PRIMARY") == [compared_focus.content]
    assert _contents(frames[1], "CONTEXT") == ["Compared-only neighboring guidance."]


def test_compare_mixes_context_and_memory_positionals(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    reference = ops.init("mixed/reference")
    first = ops.add(reference, "Reference claim one.")
    second = ops.add(reference, "Reference claim two.")
    compared = ops.init("mixed/compared")
    compared_focus = ops.add(compared, "Compared focused claim.")
    ops.add(compared, "Compared neighboring claim.")
    store.create_context(reference)
    store.create_context(compared)
    provider = _CapturingSummaryProvider()
    _patch_summary_provider(monkeypatch, provider)

    result = runner.invoke(
        app,
        ["compare", reference.name, compared_focus.uid[:8]],
    )

    assert result.exit_code == 0, result.output
    frames = provider.payloads[0]["frames"]
    assert _contents(frames[0], "PRIMARY") == [first.content, second.content]
    assert _contents(frames[1], "PRIMARY") == [compared_focus.content]


def test_compare_from_and_to_accept_context_uid_prefixes(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    reference = ops.init("uid/reference")
    ops.add(reference, "Reference claim.")
    compared = ops.init("uid/compared")
    ops.add(compared, "Compared claim.")
    store.create_context(reference)
    store.create_context(compared)
    provider = _CapturingSummaryProvider()
    _patch_summary_provider(monkeypatch, provider)

    result = runner.invoke(
        app,
        [
            "compare",
            "--from",
            reference.uid[:8],
            "--to",
            compared.uid[:8],
            "--snapshot",
        ],
    )

    assert result.exit_code == 0, result.output
    assert f"Compare · {reference.name} ↔ {compared.name}" in result.output
    assert len(provider.payloads) == 1


def test_compare_bare_branch_memory_uid_is_unique_and_qualified_owner_is_exact(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("branch/source")
    shared = ops.add(source, "Shared lineage claim.")
    branch = ops.branch(source, "branch/copy")
    peer = ops.init("branch/peer")
    peer_memory = ops.add(peer, "Peer claim.")
    for context in (source, branch, peer):
        store.create_context(context)
    provider = _CapturingSummaryProvider()
    _patch_summary_provider(monkeypatch, provider)

    bare = runner.invoke(
        app,
        ["compare", shared.uid[:8], peer_memory.uid[:8]],
    )
    qualified = runner.invoke(
        app,
        ["compare", f"{source.name}:{shared.uid[:8]}", peer_memory.uid[:8]],
    )

    assert bare.exit_code == 0, bare.output
    assert f"Compare · {source.name} ↔ {peer.name}" in bare.output
    assert qualified.exit_code == 0, qualified.output
    assert f"Compare · {source.name} ↔ {peer.name}" in qualified.output
    assert len(provider.payloads) == 2


def test_compare_rejects_duplicate_or_recursive_auto_memory_roles(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("auto/source")
    source.add(
        Memory(
            uid="abcdef12-1111-4111-8111-111111111111",
            content="Focused source.",
        )
    )
    peer = ops.init("peer")
    ops.add(peer, "Peer claim.")
    store.create_context(source)
    store.create_context(peer)
    duplicate = runner.invoke(
        app,
        [
            "compare",
            "abcdef12",
            "peer",
            "--reference-memory",
            "abcdef12",
        ],
    )
    recursive = runner.invoke(
        app,
        ["compare", "abcdef12", "peer", "--reference-descendants"],
    )

    assert duplicate.exit_code == 1
    assert "both positionally and with --reference-memory" in duplicate.output
    assert recursive.exit_code == 1
    assert "REFERENCE Memory selection cannot be combined" in recursive.output


def test_compare_qualified_granted_memory_uses_public_owner(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    active_store = MemoryStore()
    attachment = ops.init("grant/attachment")
    peer = ops.init("grant/peer")
    ops.add(peer, "Local peer claim.")
    active_store.save(attachment)
    active_store.save(peer)

    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="compare-auto-authority",
        kind="MANAGED",
    )
    authoring = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    source = ops.init("authority/source")
    granted_memory = ops.add(source, "Granted focused claim.")
    authority_store.save(source)
    registry = ProfileRegistry(
        generation=1,
        active_uid=authoring.uid,
        profiles=(authoring, authority),
        grants=(),
    )
    registry_path = profile_registry_file()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry.to_dict()) + "\n", encoding="utf-8")
    create_authority_grant_with_placement(
        authority_name=authority.name,
        grantee_name=authoring.name,
        resource_name=source.name,
        access_name="shared/source",
        permissions=("READ",),
    )

    with authority_grant_snapshot_lock() as frozen_registry:
        with pytest.raises(
            CompareTargetingError,
            match="Bare Memory operands do not enumerate Grants",
        ):
            resolve_compare_cli_targets(
                active_store,
                reference_operand=granted_memory.uid[:8],
                compared_operand=peer.name,
                reference_is_auto_memory=True,
                compared_is_auto_memory=False,
                reference_memory_selector=None,
                compared_memory_selector=None,
                current_name=None,
                registry=frozen_registry,
            )
        targets = resolve_compare_cli_targets(
            active_store,
            reference_operand=f"shared/source:{granted_memory.uid[:8]}",
            compared_operand=peer.name,
            reference_is_auto_memory=True,
            compared_is_auto_memory=False,
            reference_memory_selector=None,
            compared_memory_selector=None,
            current_name=None,
            registry=frozen_registry,
        )

    assert targets.reference_access.is_granted
    assert targets.reference_access.access_name == "shared/source"
    assert targets.reference_memory_uid == granted_memory.uid
    assert not targets.compared_access.is_granted


def test_compare_help_advertises_auto_typed_endpoints():
    result = runner.invoke(app, ["compare", "--help"])

    assert result.exit_code == 0
    assert "[ENDPOINT]..." in result.output
    assert "auto-typed PEER Context/Memory" in result.output
