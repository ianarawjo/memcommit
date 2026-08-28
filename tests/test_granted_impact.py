"""Read-only directional impact planning against a granted target."""

from __future__ import annotations

import json
import uuid

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import memcommit.adapters.console.clipboard as clipboard
import memcommit.application.ops as ops
import memcommit.adapters.console.commands.meld.command as meld_command
import memcommit.adapters.console.commands.meld.setup as meld_setup_command
from memcommit.adapters.console.entrypoint import app
from memcommit.application.operations.compare.ledger.provider import (
    COMPARISON_PAYLOAD_MARKER,
)
from memcommit.application.operations.compare.ledger.store import (
    comparison_analysis_path,
)
from memcommit.application.authority.access import (
    freeze_granted_context_binding,
    resolve_context_access,
    revalidate_granted_context_binding,
)
from memcommit.adapters.console.commands.compare.sessions import (
    comparison_session_entries,
)
from memcommit.adapters.console.commands.compare.setup import choose_compare_setup
from memcommit.adapters.console.shared.endpoint_setup_flows import (
    _readable_endpoint_catalog,
    choose_update_setup,
)
from memcommit.adapters.console.commands.meld.setup import MeldSetupReceipt
from memcommit.core.context import AutoCheckpoint, Context, Memory
from memcommit.core.context_targeting.readable_catalog import ReadableContextCatalog
from memcommit.application.authority.derived_policy import (
    analysis_retention,
    authorize_analysis_save,
)
from memcommit.application.operations.compare.ledger.granted_store import (
    granted_comparison_analysis_path,
    load_granted_comparison_artifact,
)
from memcommit.application.operations.meld.provider import MELD_PAYLOAD_MARKER
from memcommit.application.operations.profile.config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.application.operations.profile.model import (
    ProfileError,
    create_authority_grant,
    delete_authority_grant,
)
from memcommit.persistence.store import MemoryStore
from memcommit.application.operations.summarize.application import SummarizeRequest
from memcommit.application.operations.summarize.runtime import execute_summarize
from memcommit.application.semantic.changes import RemoveChange
from memcommit.source_projection.model import SourceAccess
from memcommit.source_projection.presentation import source_display_text


runner = CliRunner(mix_stderr=False)
DETAIL_SECRET = "Concealed construction sequence must not enter impact planning."


class _GrantedDirectionalMeldProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "meld_contexts"
        payload = json.loads(prompt.split(MELD_PAYLOAD_MARKER, 1)[1])
        incoming = payload["frames"][0]["memories"][0]
        baseline = payload["frames"][1]["memories"][0]
        return json.dumps(
            {
                "overview": "The incoming correction replaces the baseline claim.",
                "relations": [
                    {
                        "relation_key": "location",
                        "left_memory_ids": [incoming["memory_id"]],
                        "right_memory_ids": [baseline["memory_id"]],
                        "kind": "CONFLICT",
                        "status": "RESOLVED",
                        "summary": "The service-desk locations conflict.",
                        "reason": "The incoming Memory is the reviewed correction.",
                    }
                ],
                "issues": [],
                "results": [
                    {
                        "result_key": "location_edit",
                        "operation": "EDIT",
                        "target_memory_ids": [baseline["memory_id"]],
                        "disposition": "SYNTHESIZE",
                        "content": incoming["content"],
                        "reason": "Apply the incoming correction to baseline.",
                        "relation_keys": ["location"],
                        "source_memory_ids": [
                            incoming["memory_id"],
                            baseline["memory_id"],
                        ],
                        "grounded_turn_ids": [],
                    }
                ],
                "ready_to_apply": True,
            }
        )


class _GrantedSubtreeDirectionalMeldProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "meld_contexts"
        payload = json.loads(prompt.split(MELD_PAYLOAD_MARKER, 1)[1])
        incoming = payload["frames"][0]["memories"][0]
        baseline_by_owner = {
            memory["owner_context_name"]: memory
            for memory in payload["frames"][1]["memories"]
        }
        assert set(baseline_by_owner) == {
            "campus-wiki",
            "campus-wiki/services",
        }
        target_ids = {
            item["context_name"]: item["target_context_id"]
            for item in payload["target"]["contexts"]
        }
        results = []
        for owner_name, suffix in (
            ("campus-wiki", "Root guidance now points east."),
            ("campus-wiki/services", "Service guidance now points east."),
        ):
            target = baseline_by_owner[owner_name]
            results.append(
                {
                    "result_key": owner_name.replace("/", "_"),
                    "operation": "EDIT",
                    "target_memory_ids": [target["memory_id"]],
                    "target_context_id": target_ids[owner_name],
                    "disposition": "SYNTHESIZE",
                    "content": suffix,
                    "reason": "Apply the incoming reviewed correction in place.",
                    "relation_keys": ["coverage"],
                    "source_memory_ids": [
                        incoming["memory_id"],
                        target["memory_id"],
                    ],
                    "grounded_turn_ids": [],
                }
            )
        return json.dumps(
            {
                "overview": "The correction updates both selected owners in place.",
                "paired_relations": [
                    {
                        "relation_key": "coverage",
                        "left_memory_ids": [incoming["memory_id"]],
                        "right_memory_ids": [
                            memory["memory_id"] for memory in baseline_by_owner.values()
                        ],
                        "kind": "CONFLICT",
                        "status": "RESOLVED",
                        "summary": "The selected baseline guidance is outdated.",
                        "reason": "The incoming reviewed correction governs both owners.",
                    }
                ],
                "distinct_relations": [],
                "issues": [],
                "results": results,
                "ready_to_apply": True,
            }
        )


class _GrantedFindProvider:
    def __init__(self):
        self.prompts = []

    def complete(self, prompt, *, operation, output_schema=None):
        self.prompts.append(prompt)
        if operation != "search":
            return json.dumps({"findings": []})
        payload = json.loads(prompt.split("SEARCH PAYLOAD:\n", 1)[1])
        matches = [
            {"candidate_id": candidate["candidate_id"]}
            for candidate in payload["candidates"]
            if "service desk" in candidate.get("content", "").casefold()
        ]
        return json.dumps(
            {
                "matches": matches,
                "related_query": "",
                "related_matches": [],
            }
        )


def _setup_granted_target(
    isolated_store,
    tmp_path,
    monkeypatch,
    *,
    parent_permissions=(
        "READ",
        "CREATE",
        "UPDATE",
        "DELETE",
        "QUERY",
        "DERIVE",
        "COMBINE",
        "EXPORT",
        "ACCEPT_DERIVED",
        "SAVE_BOUND_ANALYSIS",
        "SAVE_ANALYSIS",
    ),
    authority_name="run-granted-memory",
    authority_source=None,
    attachment_name="task-root",
    public_name="campus-wiki",
    extra_authority_baseline=False,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    active_store = MemoryStore()
    source = ops.init(attachment_name)
    ops.add(source, "Verified update: the public service desk moved east.")
    if "/" in attachment_name:
        active_store.save(ops.init(attachment_name.split("/", 1)[0]))
    active_store.save(source)
    active_store.set_current(source.name)

    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name=authority_name,
        kind="MANAGED",
        source=authority_source,
    )
    authoring = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    wiki = ops.init("campus-wiki")
    ops.add(wiki, "The public service desk is in the west lobby.")
    public_child = ops.init("campus-wiki/services")
    ops.add(public_child, "The service desk is open on weekdays.")
    details = ops.init("campus-wiki/construction-details")
    ops.add(details, DETAIL_SECRET)
    wiki.add(Context(uid=public_child.uid, name=public_child.name))
    wiki.add(Context(uid=details.uid, name=details.name))
    if extra_authority_baseline:
        extra_baseline = ops.init("campus-wiki/baseline")
        ops.add(extra_baseline, "The service desk is closed on weekdays.")
        wiki.add(Context(uid=extra_baseline.uid, name=extra_baseline.name))
        authority_store.save(extra_baseline)
    authority_store.save(public_child)
    authority_store.save(details)
    authority_store.save(wiki)
    authority_store.set_current(wiki.name)

    registry = ProfileRegistry(
        generation=1,
        active_uid=authoring.uid,
        profiles=(authoring, authority),
        grants=(),
    )
    path = profile_registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry.to_dict()) + "\n", encoding="utf-8")
    _registry, parent_grant = create_authority_grant(
        authority_name=authority.name,
        grantee_name=authoring.name,
        resource_name=wiki.name,
        attachment_name=source.name,
        public_name=public_name,
        permissions=parent_permissions,
        recursive=True,
    )
    create_authority_grant(
        authority_name=authority.name,
        grantee_name=authoring.name,
        resource_name=details.name,
        attachment_name=source.name,
        public_name=public_name + "/construction-details",
        permissions=("QUERY",),
        recursive=True,
    )
    return active_store, authority_store, source, wiki, parent_grant


def test_directional_meld_updates_granted_baseline_authority_context(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, authority, incoming, _wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    provider = _GrantedDirectionalMeldProvider()
    monkeypatch.setattr(
        meld_command,
        "connect_codex_chatgpt_provider",
        lambda: provider,
    )

    started = runner.invoke(
        app,
        ["meld", incoming.name, "--into", "campus-wiki/services"],
    )
    assert started.exit_code == 0, (
        started.output,
        started.stderr,
        repr(started.exception),
    )
    authority_target = authority.load_direct("campus-wiki/services")
    session = active.load_meld_session(authority_target.uid)
    assert session is not None
    assert session.granted_target is not None
    assert session.state == "READY_TO_APPLY"

    accepted = runner.invoke(
        app,
        [
            "meld",
            incoming.name,
            "--into",
            "campus-wiki/services",
            "--accept",
        ],
    )
    assert accepted.exit_code == 0, accepted.output
    assert [
        memory.content
        for memory in authority.load_direct("campus-wiki/services").iter_items()
    ][0] == "Verified update: the public service desk moved east."
    # The attachment remains participant-owned authorization metadata; Meld
    # must not materialize an authority baseline copy into it.
    assert active.load_direct(incoming.name).uid == incoming.uid


def test_directional_meld_applies_granted_target_subtree_to_exact_owners(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, authority, incoming, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    monkeypatch.setattr(
        meld_command,
        "connect_codex_chatgpt_provider",
        lambda: _GrantedSubtreeDirectionalMeldProvider(),
    )

    started = runner.invoke(
        app,
        [
            "meld",
            incoming.name,
            "--into",
            "campus-wiki",
            "--right-descendants",
        ],
    )
    assert started.exit_code == 0, started.output + started.stderr
    session = active.load_meld_session(wiki.uid)
    assert session is not None and session.state == "READY_TO_APPLY"
    assert [context.name for context in session.frames[1].contexts or ()] == [
        "campus-wiki",
        "campus-wiki/services",
    ]

    accepted = runner.invoke(
        app,
        [
            "meld",
            incoming.name,
            "--into",
            "campus-wiki",
            "--right-descendants",
            "--accept",
        ],
    )
    assert accepted.exit_code == 0, accepted.output + accepted.stderr
    root_memories = [
        item.content
        for item in authority.load_direct("campus-wiki").iter_items()
        if isinstance(item, Memory)
    ]
    child_memories = [
        item.content
        for item in authority.load_direct("campus-wiki/services").iter_items()
        if isinstance(item, Memory)
    ]
    assert root_memories == ["Root guidance now points east."]
    assert child_memories == ["Service guidance now points east."]
    assert session.application is None
    applied = active.load_meld_session(wiki.uid)
    assert applied is not None and applied.application is not None
    assert [receipt.context_name for receipt in applied.application.checkpoints] == [
        "campus-wiki",
        "campus-wiki/services",
    ]


def test_directional_meld_rejects_narrower_grant_for_proposed_child_owner(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, _authority, incoming, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    create_authority_grant(
        authority_name="run-granted-memory",
        grantee_name=AUTHORING_PROFILE_NAME,
        resource_name="campus-wiki/services",
        attachment_name=incoming.name,
        public_name="campus-wiki/services",
        permissions=(
            "READ",
            "CREATE",
            "DERIVE",
            "COMBINE",
            "ACCEPT_DERIVED",
            "SAVE_ANALYSIS",
        ),
        recursive=True,
    )
    monkeypatch.setattr(
        meld_command,
        "connect_codex_chatgpt_provider",
        lambda: _GrantedSubtreeDirectionalMeldProvider(),
    )

    started = runner.invoke(
        app,
        [
            "meld",
            incoming.name,
            "--into",
            "campus-wiki",
            "--right-descendants",
        ],
    )

    assert started.exit_code == 1
    assert "does not allow update access" in started.stderr.casefold()
    assert active.load_meld_session(wiki.uid) is None


def test_directional_meld_reads_granted_incoming_into_local_baseline(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, _authority, attachment, _wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    baseline = ops.init("local-baseline")
    ops.add(baseline, "The public service desk is in the central lobby.")
    active.save(baseline)
    provider = _GrantedDirectionalMeldProvider()
    monkeypatch.setattr(
        meld_command,
        "connect_codex_chatgpt_provider",
        lambda: provider,
    )

    started = runner.invoke(
        app,
        ["meld", "campus-wiki/services", "--into", baseline.name],
    )
    assert started.exit_code == 0, (
        started.output,
        started.stderr,
        repr(started.exception),
    )
    session = active.load_meld_session(baseline.uid)
    assert session is not None
    assert session.granted_incoming is not None
    assert session.granted_target is None

    accepted = runner.invoke(
        app,
        [
            "meld",
            "campus-wiki/services",
            "--into",
            baseline.name,
            "--accept",
        ],
    )
    assert accepted.exit_code == 0, accepted.output
    assert [
        memory.content for memory in active.load_direct(baseline.name).iter_items()
    ] == ["The service desk is open on weekdays."]


def test_directional_meld_combines_granted_contexts_in_one_authority_profile(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, authority, _attachment, _wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        extra_authority_baseline=True,
    )
    baseline = authority.load_direct("campus-wiki/baseline")
    monkeypatch.setattr(
        meld_command,
        "connect_codex_chatgpt_provider",
        lambda: _GrantedDirectionalMeldProvider(),
    )

    started = runner.invoke(
        app,
        [
            "meld",
            "campus-wiki/services",
            "--into",
            "campus-wiki/baseline",
        ],
    )
    assert started.exit_code == 0, started.output + started.stderr
    session = active.load_meld_session(baseline.uid)
    assert session is not None
    assert session.granted_incoming is not None
    assert session.granted_target is not None

    accepted = runner.invoke(
        app,
        [
            "meld",
            "campus-wiki/services",
            "--into",
            "campus-wiki/baseline",
            "--accept",
        ],
    )
    assert accepted.exit_code == 0, accepted.output + accepted.stderr
    assert [
        item.content for item in authority.load_direct(baseline.name).iter_items()
    ] == ["The service desk is open on weekdays."]


def test_directional_meld_revoked_target_fails_closed_before_baseline_acceptance(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, authority, incoming, _wiki, grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    target = authority.load_direct("campus-wiki/services")
    original = target.to_dict()
    monkeypatch.setattr(
        meld_command,
        "connect_codex_chatgpt_provider",
        lambda: _GrantedDirectionalMeldProvider(),
    )
    started = runner.invoke(
        app,
        ["meld", incoming.name, "--into", "campus-wiki/services"],
    )
    assert started.exit_code == 0, started.output + started.stderr

    delete_authority_grant(grant.uid)
    accepted = runner.invoke(
        app,
        [
            "meld",
            incoming.name,
            "--into",
            "campus-wiki/services",
            "--accept",
        ],
    )
    assert accepted.exit_code == 1
    assert "Context 'campus-wiki/services' does not exist" in accepted.stderr
    assert "Granted view" not in accepted.stderr
    assert authority.load_direct(target.name).to_dict() == original
    session = active.load_meld_session(target.uid)
    assert session is not None and session.state == "READY_TO_APPLY"


def test_directional_meld_rejects_ungranted_baseline_edit(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, _authority, incoming, _wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        parent_permissions=(
            "READ",
            "CREATE",
            "DERIVE",
            "COMBINE",
            "EXPORT",
            "ACCEPT_DERIVED",
            "SAVE_BOUND_ANALYSIS",
        ),
    )
    target_access = resolve_context_access(
        active,
        "campus-wiki/services",
        current_name=incoming.name,
        required_permission="READ",
    )
    monkeypatch.setattr(
        meld_command,
        "connect_codex_chatgpt_provider",
        lambda: _GrantedDirectionalMeldProvider(),
    )

    started = runner.invoke(
        app,
        ["meld", incoming.name, "--into", "campus-wiki/services"],
    )
    assert started.exit_code == 1
    assert "does not authorize UPDATE" in started.stderr
    assert (
        active.load_meld_session(
            target_access.store.load_direct(target_access.context_name).uid
        )
        is None
    )


def test_directional_meld_rolls_back_granted_baseline_when_receipt_save_fails(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, authority, incoming, _wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    target = authority.load_direct("campus-wiki/services")
    original = target.to_dict()
    checkpoints_before = tuple(authority.list_checkpoints(target.name))
    monkeypatch.setattr(
        meld_command,
        "connect_codex_chatgpt_provider",
        lambda: _GrantedDirectionalMeldProvider(),
    )
    started = runner.invoke(
        app,
        ["meld", incoming.name, "--into", "campus-wiki/services"],
    )
    assert started.exit_code == 0, started.output + started.stderr

    def fail_receipt(*_args, **_kwargs):
        raise RuntimeError("participant receipt write failed")

    monkeypatch.setattr(active, "save_meld_session", fail_receipt)
    monkeypatch.setattr(meld_command, "MemoryStore", lambda: active)
    accepted = runner.invoke(
        app,
        [
            "meld",
            incoming.name,
            "--into",
            "campus-wiki/services",
            "--accept",
        ],
    )
    assert accepted.exit_code == 1
    assert authority.load_direct(target.name).to_dict() == original
    assert tuple(authority.list_checkpoints(target.name)) == checkpoints_before


def test_local_namespace_root_reads_granted_and_owned_descendants_together(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, _authority, attachment, _wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        attachment_name="task-root/participant",
        public_name="task-root/campus-wiki",
    )
    active.set_current("task-root")
    provider = _GrantedFindProvider()
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.search.command.connect_search_provider",
        lambda: provider,
    )

    found = runner.invoke(app, ["search", "service desk", "--limit", "10", "-r"])
    listed = runner.invoke(app, ["ls", "-R", "task-root"])
    mixed_copy = runner.invoke(app, ["ls", "-R", "task-root", "--copy"])

    assert found.exit_code == 0, found.output + found.stderr
    assert attachment.name in found.output
    assert "task-root/campus-wiki" in found.output
    assert "west lobby" in found.output
    assert listed.exit_code == 0, listed.output + listed.stderr
    assert "task-root/participant" in listed.output
    assert "task-root/campus-wiki" in listed.output
    assert mixed_copy.exit_code == 1
    assert "mixed local and granted recursive list" in mixed_copy.stderr
    assert DETAIL_SECRET not in "\n".join(provider.prompts)


def test_recursive_summarize_uses_one_local_and_granted_public_namespace(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, _authority, _attachment, _wiki, grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        attachment_name="task-root/participant",
        public_name="task-root/campus-wiki",
    )
    active.set_current("task-root")
    payloads: list[dict[str, object]] = []

    def forbidden_provider():
        raise AssertionError("a direct empty root must not connect")

    direct = execute_summarize(
        SummarizeRequest(
            context_locator="task-root",
            include_descendants=False,
            follow_embeds=False,
        ),
        store=active,
        provider_factory=forbidden_provider,
    )
    assert direct.source_count == 0

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            payload = json.loads(prompt.split("SUMMARIZE CONTEXT PAYLOAD:\n", 1)[1])
            payloads.append(payload)
            return json.dumps(
                {
                    "text": "The readable namespace combines local and granted notes.",
                    "source_ids": [item["source_id"] for item in payload["memories"]],
                }
            )

    result = execute_summarize(
        SummarizeRequest(
            context_locator="task-root",
            include_descendants=True,
            follow_embeds=False,
        ),
        store=active,
        provider_factory=Provider,
    )

    assert result.source_count == 3
    encoded = json.dumps(payloads[0], ensure_ascii=False)
    assert "public service desk moved east" in encoded
    assert "public service desk is in the west lobby" in encoded
    assert "service desk is open on weekdays" in encoded
    assert DETAIL_SECRET not in encoded

    class RevokingProvider(Provider):
        def complete(self, prompt, *, operation, output_schema=None):
            response = super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )
            delete_authority_grant(grant.uid)
            return response

    with pytest.raises(ProfileError, match="grant|Grant"):
        execute_summarize(
            SummarizeRequest(
                context_locator="task-root",
                include_descendants=True,
                follow_embeds=False,
            ),
            store=active,
            provider_factory=RevokingProvider,
        )


def test_rationale_local_root_does_not_analyze_granted_neighbor_subtree(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, _authority, attachment, _wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        attachment_name="task-root/participant",
        public_name="task-root/campus-wiki",
    )
    active.set_current("task-root")
    target = next(item for item in attachment.iter_items() if isinstance(item, Memory))
    result = runner.invoke(
        app,
        ["rationale", target.uid[:8], "--context", "task-root"],
    )
    structured = runner.invoke(
        app,
        [
            "rationale",
            target.uid[:8],
            "--context",
            "task-root",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert structured.exit_code == 0, structured.output + structured.stderr
    assert target.content in result.output
    assert "APPARENT PURPOSE" not in result.output
    assert "Context(s)" not in result.output
    payload = json.loads(structured.output)
    assert payload["inference"] is None
    assert payload["fallback_evidence"] == []
    assert DETAIL_SECRET not in structured.output


def test_rationale_mixed_subtree_needs_no_combination_permission_for_provenance(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, _authority, attachment, _wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        parent_permissions=("READ",),
        attachment_name="task-root/participant",
        public_name="task-root/campus-wiki",
    )
    active.set_current("task-root")
    target = next(item for item in attachment.iter_items() if isinstance(item, Memory))
    result = runner.invoke(
        app,
        ["rationale", target.uid[:8], "--context", "task-root"],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert "PROVENANCE" in result.output
    assert "APPARENT PURPOSE" not in result.output


def _empty_plan() -> str:
    return json.dumps({"edits": [], "additions": [], "removals": []})


def test_find_and_quality_finders_read_granted_current_projection(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, _authority, source, _wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        # Provider-backed quality analysis is derived use even when the
        # command publishes only a read-only report.
        parent_permissions=("READ", "DERIVE"),
    )
    active.set_current_virtual_context_if(source.name, "campus-wiki")
    provider = _GrantedFindProvider()
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.search.command.connect_search_provider",
        lambda: provider,
    )
    for module in (
        "find_duplicates",
        "find_ambiguities",
        "find_conflicts",
    ):
        monkeypatch.setattr(
            f"memcommit.adapters.console.commands.{module}.command.connect_codex_chatgpt_provider",
            lambda: provider,
        )

    result = runner.invoke(app, ["find", "service desk", "-r"])

    assert result.exit_code == 0, result.output
    assert "west lobby" in result.output
    assert "open on weekdays" in result.output
    assert DETAIL_SECRET not in "\n".join(provider.prompts)

    active.set_current(source.name)
    for command in ("dedun", "find-ambiguities", "find-conflicts"):
        quality = runner.invoke(app, [command, "--context", "campus-wiki"])
        assert quality.exit_code == 0, quality.output + quality.stderr


def test_recursive_dedun_rejects_granted_boundaries_before_provider(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, _authority, _source, _wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        parent_permissions=("READ", "DERIVE", "DELETE"),
        attachment_name="task-root/participant",
        public_name="task-root/campus-wiki",
    )
    active.set_current("task-root")
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.find_duplicates.command.connect_codex_chatgpt_provider",
        lambda: (_ for _ in ()).throw(
            AssertionError("authority rejection must precede provider connection")
        ),
    )

    crossing = runner.invoke(app, ["dedun", "task-root", "--recursive"])
    granted_root = runner.invoke(
        app,
        ["dedun", "task-root/campus-wiki", "--recursive"],
    )

    assert crossing.exit_code == 1
    assert "cannot cross granted Context boundaries" in crossing.stderr
    assert granted_root.exit_code == 1
    assert "cannot start from a granted Context" in granted_root.stderr


def test_temporal_find_rejects_granted_view_without_history_access(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, _authority, _source, _wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        parent_permissions=("READ",),
    )
    active.set_current_virtual_context_if(
        active.current_context_name(),
        "campus-wiki",
    )

    result = runner.invoke(app, ["search", "the last updated Memory"])

    assert result.exit_code == 1
    assert "does not expose authority checkpoint history" in result.stderr


def test_granted_chunk_requires_create_and_delete_before_authority_save(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, authority, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        parent_permissions=("READ", "DELETE"),
    )
    original = ops.add(wiki, "First paragraph.\n\nSecond paragraph.")
    authority.save(wiki)
    active.set_current_virtual_context_if(source.name, "campus-wiki")

    denied = runner.invoke(
        app,
        ["chunk", original.uid, "--method", "paragraphs"],
    )

    assert denied.exit_code == 1
    assert "does not allow CREATE" in denied.stderr
    unchanged = authority.load_direct(wiki.name)
    assert original.uid in unchanged.memories


def test_granted_chunk_and_clear_apply_to_authority_with_effect_permissions(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, authority, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        parent_permissions=("READ", "CREATE", "DELETE"),
    )
    original = ops.add(wiki, "First paragraph.\n\nSecond paragraph.")
    item_count_before = len(wiki.memories)
    authority.save(wiki)
    active.set_current_virtual_context_if(source.name, "campus-wiki")

    chunked = runner.invoke(
        app,
        ["chunk", original.uid, "--method", "paragraphs"],
    )

    assert chunked.exit_code == 0, chunked.output + chunked.stderr
    after_chunk = authority.load_direct(wiki.name)
    assert original.uid not in after_chunk.memories
    assert len(after_chunk.memories) == item_count_before + 1

    cleared = runner.invoke(app, ["clear", "campus-wiki", "--force"])

    assert cleared.exit_code == 0, cleared.output + cleared.stderr
    assert not authority.load_direct(wiki.name).memories


def test_granted_chunk_without_selector_applies_one_context_batch(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, authority, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        parent_permissions=("READ", "CREATE", "DELETE"),
    )
    first = ops.add(wiki, "First sentence. Second sentence.")
    second = ops.add(wiki, "Third sentence. Fourth sentence.")
    authority.save(wiki)
    active.set_current_virtual_context_if(source.name, "campus-wiki")

    result = runner.invoke(app, ["chunk"])

    assert result.exit_code == 0, result.output + result.stderr
    assert "2 direct Memories / 4 chunks (method=sentences)" in result.output
    after = authority.load_direct(wiki.name)
    assert first.uid not in after.memories
    assert second.uid not in after.memories
    assert [item.content for item in after.iter_items() if isinstance(item, Memory)][
        -4:
    ] == [
        "First sentence.",
        "Second sentence.",
        "Third sentence.",
        "Fourth sentence.",
    ]


def test_granted_forget_rejects_delete_when_only_update_is_granted(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, authority, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        parent_permissions=("READ", "UPDATE"),
    )
    active.set_current_virtual_context_if(source.name, "campus-wiki")
    original = next(item for item in wiki.iter_items() if isinstance(item, Memory))
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.forget.command.connect_codex_chatgpt_provider",
        lambda: object(),
    )

    authority_boundaries = []

    def approve_remove(ctx, _info, _llm, **kwargs):
        authority_boundaries.append(kwargs["mutates_granted_authority"])
        changes = [
            RemoveChange(
                uid=original.uid,
                content=original.content,
                reason="Requested",
            )
        ]
        return changes

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.forget.command._run_interactive_forget",
        approve_remove,
    )

    result = runner.invoke(app, ["forget", "Forget the service desk"])

    assert result.exit_code == 1
    assert "does not allow DELETE" in result.stderr
    assert authority_boundaries == [True]
    assert original.uid in authority.load_direct(wiki.name).memories


def test_merge_supports_granted_source_and_target_without_copying_pointers(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, authority, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        parent_permissions=(
            "READ",
            "CREATE",
            "DERIVE",
            "EXPORT",
            "ACCEPT_DERIVED",
        ),
    )

    from_grant = runner.invoke(app, ["merge", "campus-wiki"])

    assert from_grant.exit_code == 0, from_grant.output + from_grant.stderr
    local_after = active.load_direct(source.name)
    assert any(
        isinstance(item, Memory) and "west lobby" in item.content
        for item in local_after.iter_items()
    )
    assert not any(isinstance(item, Context) for item in local_after.iter_items())

    active.set_current_virtual_context_if(source.name, "campus-wiki")
    into_grant = runner.invoke(app, ["merge", "task-root"])

    assert into_grant.exit_code == 0, into_grant.output + into_grant.stderr
    authority_after = authority.load_direct(wiki.name)
    assert any(
        isinstance(item, Memory) and "Verified update" in item.content
        for item in authority_after.iter_items()
    )


def test_granted_context_binding_revalidates_exact_view_and_rejects_revocation(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, _authority, source, wiki, grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    access = resolve_context_access(
        active,
        wiki.name,
        current_name=source.name,
        required_permission="READ",
    )
    binding = freeze_granted_context_binding(access)

    restored = revalidate_granted_context_binding(binding)

    assert restored.display_name == wiki.name
    assert restored.view is not None
    assert restored.view.grant.uid == grant.uid
    assert DETAIL_SECRET not in json.dumps(binding.to_dict())

    delete_authority_grant(grant.uid)
    with pytest.raises(ProfileError, match="does not exist"):
        revalidate_granted_context_binding(binding)


def test_granted_list_copy_stages_no_source_text_and_paste_requires_live_grant(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, _authority, source, wiki, grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        parent_permissions=("READ",),
    )
    system_clipboard = {"text": ""}
    monkeypatch.setattr(
        clipboard,
        "write_system_clipboard",
        lambda text: system_clipboard.__setitem__("text", text),
    )
    monkeypatch.setattr(
        clipboard,
        "read_system_clipboard",
        lambda: system_clipboard["text"],
    )

    copied = runner.invoke(
        app,
        ["ls", wiki.name, "--copy", "--with-ids"],
    )

    assert copied.exit_code == 0, copied.output
    assert "Access: READ GRANT · PERMISSIONS READ · READ ONLY" in copied.output
    assert "FROM run-granted-memory" in copied.output
    assert "Permissions: READ" in copied.output
    assert (
        "Source boundary: DERIVE blocked · COMBINE blocked · EXPORT blocked"
        in copied.output
    )
    assert "Source boundary:" not in system_clipboard["text"]
    assert "west lobby" in system_clipboard["text"]
    record = json.loads(
        (active.store_dir / "clipboard.json").read_text(encoding="utf-8")
    )
    serialized = json.dumps(record)
    assert record["schema_version"] == 2
    assert record["plain_text"] is None
    assert record["selection"]["kind"] == "GRANTED_LIST_RECEIPT"
    assert "uid_prefixes" not in record["selection"]
    assert "west lobby" not in serialized
    assert "open on weekdays" not in serialized

    pasted = runner.invoke(app, ["ls", "--paste"])
    assert pasted.exit_code == 0, pasted.output
    assert "west lobby" in pasted.output
    assert active.current_context_name() == source.name

    delete_authority_grant(grant.uid)
    blocked = runner.invoke(app, ["ls", "--paste"])
    assert blocked.exit_code == 1
    assert "no longer available under its exact grant" in blocked.stderr


def test_list_uid_prefixes_span_local_and_all_readable_granted_contexts(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, authority, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        parent_permissions=("READ",),
    )
    local = active.load_direct(source.name)
    local.add(
        Memory(
            uid="deadbeef-1111-1111-1111-111111111111",
            content="Visible local collision.",
        )
    )
    active.save(local)
    granted = authority.load_direct(wiki.name)
    granted.add(
        Memory(
            uid="deadbeef-2222-2222-2222-222222222222",
            content="Visible granted collision.",
        )
    )
    authority.save(granted)
    opened_public_names: list[str] = []
    original_load_direct = ReadableContextCatalog.load_direct

    def record_load_direct(self, public_name):
        opened_public_names.append(public_name)
        return original_load_direct(self, public_name)

    monkeypatch.setattr(
        ReadableContextCatalog,
        "load_direct",
        record_load_direct,
    )

    local_listed = runner.invoke(app, ["ls", source.name])
    granted_listed = runner.invoke(app, ["ls", wiki.name])

    assert local_listed.exit_code == 0, local_listed.output
    assert "[memory deadbeef-1] Visible local collision." in local_listed.output
    assert "Visible granted collision." not in local_listed.output
    assert granted_listed.exit_code == 0, granted_listed.output
    assert "[memory deadbeef-2] Visible granted collision." in granted_listed.output
    assert "Visible local collision." not in granted_listed.output
    assert DETAIL_SECRET not in local_listed.output + granted_listed.output
    assert wiki.name + "/construction-details" not in opened_public_names


def test_compare_reads_recursive_grant_excludes_query_override_and_saves_nothing(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, authority, _source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        parent_permissions=("READ", "DERIVE"),
    )
    service = authority.load_direct("campus-wiki/services")
    payloads = []

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            assert operation == "compare_contexts"
            payload = json.loads(prompt.split(COMPARISON_PAYLOAD_MARKER, 1)[1])
            payloads.append(payload)
            reference, compared = payload["frames"]
            return json.dumps(
                {
                    "overview": "The granted views share service guidance.",
                    "reports": {
                        "both": "Both frames contain related service guidance.",
                        "differences": "",
                        "reference_only": "",
                        "compared_only": "",
                    },
                    "relations": [
                        {
                            "relation_key": "all",
                            "reference_memory_ids": [
                                item["memory_id"] for item in reference["memories"]
                            ],
                            "compared_memory_ids": [
                                item["memory_id"] for item in compared["memories"]
                            ],
                            "kind": "COMPATIBLE",
                            "status": "RESOLVED",
                            "summary": "The service guidance can coexist.",
                            "reason": "The supplied claims address service access.",
                        }
                    ],
                    "issues": [],
                }
            )

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.compare.command.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )
    switched = runner.invoke(app, ["switch", wiki.name])
    compared = runner.invoke(
        app,
        ["compare", "--to", "./services", "--ledger"],
    )

    assert switched.exit_code == 0, switched.output
    assert compared.exit_code == 0, compared.output + compared.stderr
    assert "TEMPORARY · READ GRANT" in compared.output
    assert len(payloads) == 1
    encoded = json.dumps(payloads[0])
    assert "west lobby" in encoded
    assert "open on weekdays" in encoded
    assert DETAIL_SECRET not in encoded
    assert not comparison_analysis_path(wiki.uid, service.uid).exists()
    assert active.current_context_name() == wiki.name


def _edit_and_add_plan(prompt: str) -> str:
    payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
    source_id = payload["source"]["memories"][0]["source_id"]
    target = next(
        item
        for item in payload["target"]["memories"]
        if "west lobby" in item["content"]
    )
    services = next(
        item
        for item in payload["target"]["contexts"]
        if item["name"].endswith("/services")
    )
    return json.dumps(
        {
            "edits": [
                {
                    "target_id": target["target_id"],
                    "new_content": "The public service desk is in the east lobby.",
                    "source_ids": [source_id],
                    "reason": "The verified move supersedes the west-lobby location.",
                }
            ],
            "additions": [
                {
                    "target_context_id": services["context_id"],
                    "new_content": "Visitors should follow signs to the east lobby.",
                    "source_ids": [source_id],
                    "reason": "The relocated desk needs visitor guidance.",
                }
            ],
            "removals": [],
        }
    )


def _removal_plan(prompt: str) -> str:
    payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
    source_id = payload["source"]["memories"][0]["source_id"]
    target = next(
        item
        for item in payload["target"]["memories"]
        if "west lobby" in item["content"]
    )
    return json.dumps(
        {
            "edits": [],
            "additions": [],
            "removals": [
                {
                    "target_id": target["target_id"],
                    "source_ids": [source_id],
                    "reason": "The verified move makes the standalone old location obsolete.",
                }
            ],
        }
    )


def _source_grant_addition_plan(prompt: str) -> str:
    payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
    return json.dumps(
        {
            "edits": [],
            "additions": [
                {
                    "target_context_id": payload["target"]["contexts"][0]["context_id"],
                    "new_content": "Advisor-derived campus note.",
                    "source_ids": [payload["source"]["memories"][0]["source_id"]],
                    "reason": "The granted source supports this addition.",
                }
            ],
            "removals": [],
        }
    )


def test_granted_source_impact_and_update_apply_to_local_target(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, authority, _source, wiki, grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        parent_permissions=("READ", "DERIVE", "EXPORT"),
    )
    local_target = ops.init("participant-proposal")
    ops.add(local_target, "Existing participant draft.")
    active.save(local_target)
    calls = 0

    class Provider:
        def complete(self, prompt, **_kwargs):
            nonlocal calls
            calls += 1
            return _source_grant_addition_plan(prompt)

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.update.command.connect_codex_chatgpt_provider",
        lambda: pytest.fail("matching impact plan must be reused"),
    )

    impact = runner.invoke(
        app,
        ["impact", "--from", wiki.name, "--to", local_target.name],
    )
    planned = active.load_impact_plan()
    assert impact.exit_code == 0, impact.output + impact.stderr
    assert planned is not None
    assert planned.to_dict()["schema_version"] == 6
    assert planned.granted_source is not None
    assert planned.granted_source.grant_uid == grant.uid
    assert planned.granted_target is None
    update = runner.invoke(
        app,
        ["update", "--from", wiki.name, "--to", local_target.name],
    )
    diff = runner.invoke(app, ["diff", "--stat"])

    assert update.exit_code == 0, update.output + update.stderr
    assert diff.exit_code == 0, diff.output + diff.stderr
    assert "Applied granted update" in diff.stdout
    assert "STALE" not in diff.stderr
    assert "REVOKED" not in diff.stderr
    assert calls == 1
    assert any(
        isinstance(item, Memory) and item.content == "Advisor-derived campus note."
        for item in active.load_direct(local_target.name).iter_items()
    )
    assert authority.load_direct(wiki.name).to_dict() == wiki.to_dict()
    delete_authority_grant(grant.uid)
    revoked_diff = runner.invoke(app, ["diff", "--stat"])
    assert revoked_diff.exit_code == 1
    assert "REVOKED" in revoked_diff.stderr
    assert "remains inspectable" in revoked_diff.stderr


def test_new_compare_and_update_setup_include_a_granted_target(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, _authority, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    names, first, second, annotations = _readable_endpoint_catalog(active)

    assert first == source.name
    assert second == wiki.name
    assert wiki.name in names
    assert f"{wiki.name}/services" in names
    assert f"{wiki.name}/construction-details" not in names
    assert annotations[wiki.name].access is SourceAccess.READ_GRANT
    assert "READ" in annotations[wiki.name].permissions
    assert source_display_text(annotations[wiki.name]) == "READ GRANT"

    with create_pipe_input() as pipe_input:
        # Shared Compare setup crosses A Context/Range/Memory and then the
        # corresponding B surfaces before its read-only action.
        pipe_input.send_text("\t\t\t\t\t\t\r")
        compare = choose_compare_setup(
            active,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\t\t\t\r")
        update = choose_update_setup(
            active,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert compare is not None
    assert compare.reference_name == source.name
    assert compare.compared_name == wiki.name
    assert update is not None
    assert update.source_name == source.name
    assert update.target_name == wiki.name


def test_derived_transfer_permissions_fail_before_provider_or_write(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, authority, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        parent_permissions=("READ",),
    )
    local_target = ops.init("participant-proposal")
    active.save(local_target)
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: pytest.fail("provider must not run without derivation consent"),
    )

    source_denied = runner.invoke(
        app,
        ["impact", "--from", wiki.name, "--to", local_target.name],
    )
    target_denied = runner.invoke(
        app,
        ["impact", "--from", source.name, "--to", wiki.name],
    )

    assert source_denied.exit_code == 1
    assert "DERIVE + EXPORT" in source_denied.stderr
    assert target_denied.exit_code == 1
    assert "ACCEPT_DERIVED" in target_denied.stderr
    assert authority.load_direct(wiki.name).to_dict() == wiki.to_dict()


def test_cross_domain_compare_requires_combine_and_saved_analysis_consent(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, _authority, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        parent_permissions=("READ", "DERIVE"),
    )
    active.set_current(source.name)
    denied = runner.invoke(app, ["compare", "--to", wiki.name])

    assert denied.exit_code == 1
    assert "COMBINE" in denied.stderr
    granted_access = resolve_context_access(
        active,
        wiki.name,
        current_name=source.name,
        required_permission="READ",
    )
    with pytest.raises(ProfileError, match="SAVE_ANALYSIS"):
        authorize_analysis_save((granted_access,))


def test_analysis_retention_uses_weakest_granted_storage_mode(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, _authority, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        parent_permissions=(
            "READ",
            "DERIVE",
            "COMBINE",
            "EXPORT",
            "SAVE_BOUND_ANALYSIS",
        ),
    )
    source_access = resolve_context_access(
        active,
        source.name,
        current_name=source.name,
        required_permission="READ",
    )
    granted_access = resolve_context_access(
        active,
        wiki.name,
        current_name=source.name,
        required_permission="READ",
    )

    assert analysis_retention((source_access, granted_access)) == "GRANT_BOUND"


def test_symmetric_meld_requires_durable_grant_basis_before_provider(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, _authority, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        parent_permissions=(
            "READ",
            "DERIVE",
            "COMBINE",
            "EXPORT",
        ),
    )
    active.set_current(source.name)
    result_name = "participant/unsavable-meld"
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.meld.command.connect_codex_chatgpt_provider",
        lambda: pytest.fail("provider must not run without analysis retention"),
    )

    result = runner.invoke(
        app,
        ["meld", source.name, wiki.name, "--to", result_name],
    )

    assert result.exit_code == 1
    assert "SAVE_ANALYSIS or SAVE_BOUND_ANALYSIS" in result.stderr
    assert not active.context_exists(result_name)


def test_granted_compare_is_retained_and_seeds_local_symmetric_meld(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, _authority, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    setup = meld_setup_command.build_meld_tui_setup(active)
    source_names = setup.names
    annotations = dict(setup.annotations)
    assert source.name in source_names
    assert wiki.name in source_names
    assert annotations[wiki.name].access is SourceAccess.READ_GRANT
    assert source_display_text(annotations[wiki.name]) == "READ GRANT"
    assert "campus-wiki/construction-details" not in source_names
    calls = 0

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            nonlocal calls
            calls += 1
            payload = json.loads(prompt.split(COMPARISON_PAYLOAD_MARKER, 1)[1])
            reference, compared = payload["frames"]
            return json.dumps(
                {
                    "overview": "The participant update and campus guidance align.",
                    "reports": {
                        "both": "Both concern the public service location.",
                        "differences": "",
                        "reference_only": "",
                        "compared_only": "",
                    },
                    "relations": [
                        {
                            "relation_key": "all",
                            "reference_memory_ids": [
                                item["memory_id"] for item in reference["memories"]
                            ],
                            "compared_memory_ids": [
                                item["memory_id"] for item in compared["memories"]
                            ],
                            "kind": "COMPATIBLE",
                            "status": "RESOLVED",
                            "summary": "The location guidance can coexist.",
                            "reason": "Both sources address the public service desk.",
                        }
                    ],
                    "issues": [],
                }
            )

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.compare.command.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )
    compared = runner.invoke(
        app,
        ["compare", "--to", wiki.name, "--ledger"],
    )

    assert compared.exit_code == 0, compared.output + compared.stderr
    assert "SAVED · RETAINED" in compared.output
    assert calls == 1
    artifact = load_granted_comparison_artifact(active, source.uid, wiki.uid)
    assert artifact is not None
    assert artifact.retention == "RETAINED"
    saved_entries = comparison_session_entries(active)
    assert [entry.key for entry in saved_entries] == [artifact.analysis.uid]
    assert saved_entries[0].title == f"{source.name} ↔ {wiki.name}"

    # Symmetric Meld owns the same exact-basis creation path. Removing the
    # isolated test artifact proves the setup does not depend on a separate
    # Compare command or a hidden current-Context switch.
    granted_comparison_analysis_path(active, source.uid, wiki.uid).unlink()
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.meld.command.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )

    target = ops.init("participant-meld")
    active.save(target)
    active.set_current(target.name)
    monkeypatch.setattr(
        meld_command,
        "choose_meld_setup",
        lambda selected_store: (
            MeldSetupReceipt(
                "symmetric",
                source.name,
                wiki.name,
                target.name,
                create_target=False,
            )
            if selected_store is active
            else pytest.fail("Meld setup received another store")
        ),
    )
    meld_command._start_new_meld_from_setup(active)
    assert calls == 2
    meld_artifact = load_granted_comparison_artifact(active, source.uid, wiki.uid)
    assert meld_artifact is not None
    assert meld_artifact.retention == "RETAINED"

    melded = runner.invoke(
        app,
        ["meld", source.name, wiki.name, target.name],
    )

    assert melded.exit_code == 0, melded.output + melded.stderr
    assert "MELD NEEDS INPUT · SYMMETRIC · participant-meld" in melded.output
    assert source.name in melded.output
    assert wiki.name in melded.output
    assert active.load_meld_session(target.uid) is not None

    delete_authority_grant(_grant.uid)
    resumed = runner.invoke(
        app,
        ["meld", source.name, wiki.name, target.name],
    )

    assert resumed.exit_code == 0, resumed.output + resumed.stderr
    assert "MELD NEEDS INPUT · SYMMETRIC" in resumed.output
    assert "Resumed without calling the semantic provider." in resumed.output


def test_update_between_distinct_grants_writes_only_accepting_target(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, source_authority, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        parent_permissions=("READ", "DERIVE", "EXPORT"),
    )
    registry = load_profile_registry()
    target_authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="run-advisor-authority",
        kind="MANAGED",
    )
    target_store = MemoryStore(root=profile_store_dir(target_authority))
    advisor = ops.init("advisor2")
    ops.add(advisor, "Existing authority-owned advisor note.")
    target_store.save(advisor)
    target_store.set_current(advisor.name)
    expanded = ProfileRegistry(
        generation=registry.generation + 1,
        active_uid=registry.active_uid,
        profiles=(*registry.profiles, target_authority),
        grants=registry.grants,
    )
    profile_registry_file().write_text(
        json.dumps(expanded.to_dict()) + "\n",
        encoding="utf-8",
    )
    create_authority_grant(
        authority_name=target_authority.name,
        grantee_name=AUTHORING_PROFILE_NAME,
        resource_name=advisor.name,
        attachment_name=source.name,
        public_name="advisor2",
        permissions=("READ", "CREATE", "ACCEPT_DERIVED"),
        recursive=True,
    )
    source_before = source_authority.load_direct(wiki.name).to_dict()

    class Provider:
        def complete(self, prompt, **_kwargs):
            return _source_grant_addition_plan(prompt)

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.update.command.connect_codex_chatgpt_provider",
        lambda: pytest.fail("Update must reuse the exact impact plan"),
    )

    impact = runner.invoke(
        app,
        ["impact", "--from", wiki.name, "--to", "advisor2"],
    )
    update = runner.invoke(
        app,
        ["update", "--from", wiki.name, "--to", "advisor2"],
    )

    assert impact.exit_code == 0, impact.output + impact.stderr
    assert update.exit_code == 0, update.output + update.stderr
    assert any(
        isinstance(item, Memory) and item.content == "Advisor-derived campus note."
        for item in target_store.load_direct(advisor.name).iter_items()
    )
    assert source_authority.load_direct(wiki.name).to_dict() == source_before


def test_granted_impact_projects_only_readable_target_scope(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active_store, authority_store, _source, wiki, parent_grant = _setup_granted_target(
        isolated_store, tmp_path, monkeypatch
    )
    prompts: list[str] = []

    class Provider:
        def complete(self, prompt, **_kwargs):
            prompts.append(prompt)
            return _empty_plan()

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )

    result = runner.invoke(
        app,
        ["impact", "--from", "task-root", "--to", "campus-wiki"],
    )

    assert result.exit_code == 0, result.output
    assert len(prompts) == 1
    assert "The public service desk is in the west lobby." in prompts[0]
    assert "The service desk is open on weekdays." in prompts[0]
    assert DETAIL_SECRET not in prompts[0]
    session = active_store.load_impact_plan()
    assert session is not None
    assert session.to_dict()["schema_version"] == 6
    assert session.granted_target is not None
    assert session.granted_target.grant_uid == parent_grant.uid
    assert session.granted_target.permissions == (
        "CREATE",
        "READ",
        "UPDATE",
        "DELETE",
        "QUERY",
        "DERIVE",
        "COMBINE",
        "EXPORT",
        "ACCEPT_DERIVED",
        "SAVE_BOUND_ANALYSIS",
        "SAVE_ANALYSIS",
    )
    assert {context.name for context in session.target_contexts} == {
        "campus-wiki",
        "campus-wiki/services",
    }
    assert "GRANTED TARGET · campus-wiki" in result.output
    assert "REQUIRED TO APPLY · READ" in result.output
    assert "GRANT PERMISSIONS · READY" in result.output
    assert authority_store.load_direct(wiki.name).to_dict() == wiki.to_dict()


def test_granted_impact_revocation_during_provider_turn_discards_preview(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active_store, _authority_store, _source, _wiki, parent_grant = (
        _setup_granted_target(isolated_store, tmp_path, monkeypatch)
    )

    class Provider:
        def complete(self, *_args, **_kwargs):
            delete_authority_grant(parent_grant.uid)
            return _empty_plan()

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )

    result = runner.invoke(
        app,
        ["impact", "--from", "task-root", "--to", "campus-wiki"],
    )

    assert result.exit_code == 1
    assert "no preview was saved" in result.stderr or "does not exist" in result.stderr
    assert active_store.load_impact_plan() is None


def test_granted_impact_query_only_target_fails_before_provider(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _setup_granted_target(isolated_store, tmp_path, monkeypatch)
    connections = 0

    def connect():
        nonlocal connections
        connections += 1
        raise AssertionError("provider must not connect")

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.impact.command.connect_codex_chatgpt_provider",
        connect,
    )

    result = runner.invoke(
        app,
        [
            "impact",
            "--from",
            "task-root",
            "--to",
            "campus-wiki/construction-details",
        ],
    )

    assert result.exit_code == 1
    assert "does not allow read access" in result.stderr
    assert connections == 0


def test_switch_to_read_grant_makes_it_current_without_materializing_copy(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, authority, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        parent_permissions=("READ",),
    )
    assert active.current_context_name() == source.name
    assert not active.context_exists(wiki.name)

    switched = runner.invoke(app, ["switch", wiki.name])
    listed = runner.invoke(app, ["ls"])
    status = runner.invoke(app, ["status"])
    contexts = runner.invoke(app, ["contexts"])
    profile_current = runner.invoke(app, ["profile", "current"])
    switched_child = runner.invoke(app, ["switch", "campus-wiki/services"])
    switched_parent = runner.invoke(app, ["switch", ".."])
    blocked_add = runner.invoke(app, ["add", "must not persist"])
    blocked_query_switch = runner.invoke(
        app,
        ["switch", "campus-wiki/construction-details"],
    )

    assert switched.exit_code == 0, switched.output
    assert "Switched to context 'campus-wiki'" in switched.output
    assert active.current_context_name() == wiki.name
    assert not active.context_exists(wiki.name)
    assert listed.exit_code == 0, listed.output
    assert "The public service desk is in the west lobby." in listed.output
    assert status.exit_code == 0, status.output
    assert "On context: campus-wiki" in status.output
    assert "Access: READ GRANT · PERMISSIONS READ · READ ONLY" in status.output
    assert contexts.exit_code == 0, contexts.output
    assert "* GRANT  campus-wiki  READ · FROM run-granted-memory" in contexts.output
    assert "GRANT  campus-wiki/services  READ" in contexts.output
    assert "ANALYSIS" not in contexts.output
    assert profile_current.exit_code == 0, profile_current.output
    assert "Current Context: campus-wiki" in profile_current.output
    assert switched_child.exit_code == 0, switched_child.output
    assert switched_parent.exit_code == 0, switched_parent.output
    assert active.current_context_name() == wiki.name
    assert blocked_add.exit_code == 1
    assert "does not allow create access" in blocked_add.stderr
    assert blocked_query_switch.exit_code == 1
    assert "does not allow read access" in blocked_query_switch.stderr
    assert authority.load_direct(wiki.name).name == wiki.name


def test_granted_impact_then_update_changes_only_run_authority(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active_store, authority_store, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    source_before = active_store.load_direct(source.name).to_dict()
    details_before = authority_store.load_direct(
        "campus-wiki/construction-details"
    ).to_dict()
    provider_calls = 0

    class Provider:
        def complete(self, prompt, **_kwargs):
            nonlocal provider_calls
            provider_calls += 1
            return _edit_and_add_plan(prompt)

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.update.command.connect_codex_chatgpt_provider",
        lambda: pytest.fail("the matching impact plan must be reused"),
    )

    impact = runner.invoke(
        app,
        ["impact", "--from", source.name, "--to", wiki.name],
    )
    update = runner.invoke(
        app,
        ["update", "--from", source.name, "--to", wiki.name],
    )
    repeated = runner.invoke(
        app,
        ["update", "--from", source.name, "--to", wiki.name],
    )

    assert impact.exit_code == 0, impact.output
    assert update.exit_code == 0, update.output
    assert repeated.exit_code == 0, repeated.output
    assert "UPDATE APPLIED · task-root → campus-wiki" in update.output
    assert "RECOVERY · governed by the granted authority owner" in update.output
    assert "This Update receipt was already applied." in repeated.output
    assert provider_calls == 1
    assert active_store.load_direct(source.name).to_dict() == source_before
    assert (
        authority_store.load_direct("campus-wiki/construction-details").to_dict()
        == details_before
    )
    authority_root = authority_store.load_direct(wiki.name)
    assert any(
        getattr(item, "content", "") == "The public service desk is in the east lobby."
        for item in authority_root.iter_items()
    )
    authority_services = authority_store.load_direct("campus-wiki/services")
    assert any(
        getattr(item, "content", "")
        == "Visitors should follow signs to the east lobby."
        for item in authority_services.iter_items()
    )
    applied = active_store.load_staged_update()
    assert applied.status == "applied"
    assert applied.granted_target is not None
    assert len(applied.application.checkpoints) == 2
    assert len(authority_store.list_checkpoints(wiki.name)) == 1
    assert len(authority_store.list_checkpoints("campus-wiki/services")) == 1


def test_granted_target_empty_update_records_only_an_idempotent_receipt(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active_store, authority_store, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    authority_before = {
        name: authority_store.load_direct(name).to_dict()
        for name in (wiki.name, "campus-wiki/services")
    }
    checkpoints_before = {
        name: tuple(authority_store.list_checkpoints(name)) for name in authority_before
    }
    provider_calls = 0

    class Provider:
        def complete(self, _prompt, **_kwargs):
            nonlocal provider_calls
            provider_calls += 1
            return _empty_plan()

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.update.command.connect_codex_chatgpt_provider",
        lambda: pytest.fail("the matching empty impact plan must be reused"),
    )

    impact = runner.invoke(
        app,
        ["impact", "--from", source.name, "--to", wiki.name],
    )
    update = runner.invoke(
        app,
        ["update", "--from", source.name, "--to", wiki.name],
    )
    receipt_bytes = (isolated_store / "staged-update.json").read_bytes()
    repeated = runner.invoke(
        app,
        ["update", "--from", source.name, "--to", wiki.name],
    )

    assert impact.exit_code == 0, impact.output
    assert update.exit_code == 0, update.output
    assert repeated.exit_code == 0, repeated.output
    assert "This Update receipt was already applied." in repeated.output
    assert provider_calls == 1
    applied = active_store.load_staged_update()
    assert applied.status == "applied"
    assert applied.operations == ()
    assert applied.application.checkpoints == ()
    assert (isolated_store / "staged-update.json").read_bytes() == receipt_bytes
    for name, before in authority_before.items():
        assert authority_store.load_direct(name).to_dict() == before
        assert tuple(authority_store.list_checkpoints(name)) == checkpoints_before[name]


def test_granted_diff_revalidates_authority_and_keeps_public_names(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _active, _authority, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    class Provider:
        def complete(self, prompt, **_kwargs):
            return _edit_and_add_plan(prompt)

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )
    assert (
        runner.invoke(
            app,
            ["impact", "--from", source.name, "--to", wiki.name],
        ).exit_code
        == 0
    )
    assert (
        runner.invoke(
            app,
            ["update", "--from", source.name, "--to", wiki.name],
        ).exit_code
        == 0
    )

    result = runner.invoke(app, ["diff", "--stat"])

    assert result.exit_code == 0, result.output
    assert "Applied granted update" in result.stdout
    assert "task-root → campus-wiki" in result.stdout
    assert "2 changes · 1 edited · 1 added" in result.stdout
    assert "STALE" not in result.stderr
    assert "REVOKED" not in result.stderr


def test_granted_diff_remains_inspectable_after_revocation(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _active, _authority, source, wiki, grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    class Provider:
        def complete(self, prompt, **_kwargs):
            return _edit_and_add_plan(prompt)

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )
    assert (
        runner.invoke(
            app,
            ["impact", "--from", source.name, "--to", wiki.name],
        ).exit_code
        == 0
    )
    assert (
        runner.invoke(
            app,
            ["update", "--from", source.name, "--to", wiki.name],
        ).exit_code
        == 0
    )
    delete_authority_grant(grant.uid)

    result = runner.invoke(app, ["diff", "--stat"])

    assert result.exit_code == 1
    assert "Applied granted update" in result.stdout
    assert "2 changes · 1 edited · 1 added" in result.stdout
    assert "REVOKED" in result.stderr
    assert "remains inspectable" in result.stderr


def test_granted_diff_marks_authority_drift_stale_but_keeps_receipts(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, authority, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    class Provider:
        def complete(self, prompt, **_kwargs):
            return _edit_and_add_plan(prompt)

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )
    assert (
        runner.invoke(
            app,
            ["impact", "--from", source.name, "--to", wiki.name],
        ).exit_code
        == 0
    )
    assert (
        runner.invoke(
            app,
            ["update", "--from", source.name, "--to", wiki.name],
        ).exit_code
        == 0
    )
    changed = authority.load_direct(wiki.name)
    ops.add(changed, "A later authority correction.")
    authority.save(changed)

    result = runner.invoke(app, ["diff", "--verbose", "--stat"])

    assert result.exit_code == 1
    assert "STALE" in result.stderr
    assert "2 changes · 1 edited · 1 added" in result.stdout
    assert "Checkpoint  campus-wiki" in result.stdout
    assert "Checkpoint  campus-wiki/services" in result.stdout


def test_revoked_granted_update_cannot_be_undone_by_participant(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _active, authority, source, wiki, grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    class Provider:
        def complete(self, prompt, **_kwargs):
            return _edit_and_add_plan(prompt)

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )
    assert (
        runner.invoke(
            app,
            ["impact", "--from", source.name, "--to", wiki.name],
        ).exit_code
        == 0
    )
    assert (
        runner.invoke(
            app,
            ["update", "--from", source.name, "--to", wiki.name],
        ).exit_code
        == 0
    )
    authority_after = {
        name: authority.load_direct(name).to_dict()
        for name in (wiki.name, "campus-wiki/services")
    }
    delete_authority_grant(grant.uid)

    result = runner.invoke(app, ["undo"])

    assert result.exit_code == 1
    assert "Undo error" in result.stderr
    assert {
        name: authority.load_direct(name).to_dict() for name in authority_after
    } == authority_after


def test_granted_undo_does_not_substitute_newer_authority_command(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _active, authority, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    class Provider:
        def complete(self, prompt, **_kwargs):
            return _edit_and_add_plan(prompt)

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )
    assert (
        runner.invoke(
            app,
            ["impact", "--from", source.name, "--to", wiki.name],
        ).exit_code
        == 0
    )
    assert (
        runner.invoke(
            app,
            ["update", "--from", source.name, "--to", wiki.name],
        ).exit_code
        == 0
    )
    later = authority.load_direct(wiki.name)
    ops.add(later, "A later independent authority command.")
    authority.save(
        later,
        AutoCheckpoint(
            command="add",
            args={},
            description="Later authority addition.",
        ),
    )
    authority_before_undo = authority.load_direct(wiki.name).to_dict()

    result = runner.invoke(app, ["undo"])

    assert result.exit_code == 1
    assert "not the next Context command to undo" in result.stderr
    assert authority.load_direct(wiki.name).to_dict() == authority_before_undo


def test_granted_update_undo_and_redo_restore_exact_authority_unit(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, authority, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    root_before = authority.load_direct(wiki.name).to_dict()
    services_before = authority.load_direct("campus-wiki/services").to_dict()

    class Provider:
        def complete(self, prompt, **_kwargs):
            return _edit_and_add_plan(prompt)

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )
    assert (
        runner.invoke(
            app,
            ["impact", "--from", source.name, "--to", wiki.name],
        ).exit_code
        == 0
    )
    assert (
        runner.invoke(
            app,
            ["update", "--from", source.name, "--to", wiki.name],
        ).exit_code
        == 0
    )
    root_after = authority.load_direct(wiki.name).to_dict()
    services_after = authority.load_direct("campus-wiki/services").to_dict()

    undone = runner.invoke(app, ["undo"])

    assert undone.exit_code == 0, undone.output
    assert (
        f"Undid command: mem update --from {source.name} --to {wiki.name}"
        in undone.stdout
    )
    assert authority.load_direct(wiki.name).to_dict() == root_before
    assert authority.load_direct("campus-wiki/services").to_dict() == services_before
    undone_session = active.load_staged_update()
    assert undone_session.status == "undone"
    assert undone_session.application is not None

    redone = runner.invoke(app, ["redo"])

    assert redone.exit_code == 0, redone.output
    assert (
        f"Redid command: mem update --from {source.name} --to {wiki.name}"
        in redone.stdout
    )
    assert authority.load_direct(wiki.name).to_dict() == root_after
    assert authority.load_direct("campus-wiki/services").to_dict() == services_after
    redone_session = active.load_staged_update()
    assert redone_session.status == "applied"
    assert redone_session.application == undone_session.application


def test_granted_update_checks_create_permission_before_first_write(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active_store, authority_store, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        parent_permissions=(
            "READ",
            "UPDATE",
            "DELETE",
            "QUERY",
            "ACCEPT_DERIVED",
        ),
    )
    authority_before = {
        name: authority_store.load_direct(name).to_dict()
        for name in (wiki.name, "campus-wiki/services")
    }

    class Provider:
        def complete(self, prompt, **_kwargs):
            return _edit_and_add_plan(prompt)

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )
    assert (
        runner.invoke(
            app,
            ["impact", "--from", source.name, "--to", wiki.name],
        ).exit_code
        == 0
    )

    update = runner.invoke(
        app,
        ["update", "--from", source.name, "--to", wiki.name],
    )

    assert update.exit_code == 1
    assert "does not contain every permission" in update.stderr
    assert {
        name: authority_store.load_direct(name).to_dict() for name in authority_before
    } == authority_before
    assert authority_store.list_checkpoints(wiki.name) == []
    assert authority_store.list_checkpoints("campus-wiki/services") == []
    assert active_store.load_staged_update().status == "staged"


def test_granted_update_requires_explicit_delete_for_removal(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active_store, authority_store, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        parent_permissions=(
            "READ",
            "CREATE",
            "UPDATE",
            "QUERY",
            "ACCEPT_DERIVED",
        ),
    )
    root_before = authority_store.load_direct(wiki.name).to_dict()

    class Provider:
        def complete(self, prompt, **_kwargs):
            return _removal_plan(prompt)

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )
    impact = runner.invoke(
        app,
        ["impact", "--from", source.name, "--to", wiki.name],
    )
    update = runner.invoke(
        app,
        ["update", "--from", source.name, "--to", wiki.name],
    )

    assert impact.exit_code == 0, impact.output
    assert "REQUIRED TO APPLY · READ + DELETE" in impact.output
    assert "GRANT PERMISSIONS · BLOCKED" in impact.output
    assert update.exit_code == 1
    assert "does not contain every permission" in update.stderr
    assert authority_store.load_direct(wiki.name).to_dict() == root_before
    assert authority_store.list_checkpoints(wiki.name) == []
    assert active_store.load_staged_update().status == "staged"


def test_granted_update_does_not_special_case_a_legacy_baseline_name(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active_store, authority_store, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        authority_name="study-baseline",
        authority_source={"kind": "STUDY_BASELINE", "schema_version": 1},
    )
    root_before = authority_store.load_direct(wiki.name).to_dict()

    class Provider:
        def complete(self, prompt, **_kwargs):
            return _edit_and_add_plan(prompt)

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )
    assert (
        runner.invoke(
            app,
            ["impact", "--from", source.name, "--to", wiki.name],
        ).exit_code
        == 0
    )

    update = runner.invoke(
        app,
        ["update", "--from", source.name, "--to", wiki.name],
    )

    assert update.exit_code == 0, update.stderr or update.output
    assert authority_store.load_direct(wiki.name).to_dict() != root_before
    assert authority_store.list_checkpoints(wiki.name)
    assert active_store.load_staged_update().status == "applied"


def test_granted_multi_owner_write_failure_rolls_back_authority(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active_store, authority_store, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    class Provider:
        def complete(self, prompt, **_kwargs):
            return _edit_and_add_plan(prompt)

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.impact.command.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )
    assert (
        runner.invoke(
            app,
            ["impact", "--from", source.name, "--to", wiki.name],
        ).exit_code
        == 0
    )
    authority_before = {
        name: authority_store.load_direct(name).to_dict()
        for name in (wiki.name, "campus-wiki/services")
    }
    original_save_locked = MemoryStore._save_locked
    writes = 0

    def fail_second_write(self, context, auto_checkpoint, **kwargs):
        nonlocal writes
        if auto_checkpoint is not None and auto_checkpoint.command == "update":
            writes += 1
            if writes == 2:
                raise OSError("simulated granted second-owner failure")
        return original_save_locked(self, context, auto_checkpoint, **kwargs)

    monkeypatch.setattr(MemoryStore, "_save_locked", fail_second_write)

    update = runner.invoke(
        app,
        ["update", "--from", source.name, "--to", wiki.name],
    )

    assert update.exit_code == 1
    assert "simulated granted second-owner failure" in update.stderr
    assert {
        name: authority_store.load_direct(name).to_dict() for name in authority_before
    } == authority_before
    assert authority_store.list_checkpoints(wiki.name) == []
    assert authority_store.list_checkpoints("campus-wiki/services") == []
    assert active_store.load_staged_update().status == "staged"
