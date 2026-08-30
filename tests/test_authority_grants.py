"""Cross-Profile authority grants behave as permissioned views, not forks."""

from __future__ import annotations

import json
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
import memcommit.adapters.console.commands.search.command as find_command
import memcommit.adapters.console.commands.query.command as query_command
import memcommit.adapters.console.commands.rationale.command as rationale_command
from memcommit.adapters.python_api import MemCommitClient, ShowContextResult
from memcommit.adapters.console.entrypoint import app
from memcommit.application.capabilities.authority.context_access import (
    resolve_context_access,
)
from memcommit.adapters.console.terminal.components.memory_report_picker import (
    MemoryReportTargetSelection,
)
from memcommit.application.capabilities.authority.readable_contexts import (
    freeze_profile_readable_context_catalog,
)
from memcommit.core.context import Memory
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
    create_authority_grant,
    update_authority_grant,
)
from memcommit.persistence.store import MemoryStore
from memcommit.application.operations.summarize.application import SummarizeRequest
from memcommit.application.operations.summarize.runtime import execute_summarize


runner = CliRunner(mix_stderr=False)
PUBLIC = "The student centre remains open until 20:00."
SECRET = "The utility tunnel access code is 1937."


def _grant_fixture(isolated_store, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    task_store = MemoryStore()
    task_root = ops.init("task-root")
    task_store.save(task_root)
    task_store.set_current(task_root.name)

    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="task-1-campus-authority",
        kind="MANAGED",
    )
    authoring = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    campus = ops.init("campus-wiki")
    editable = ops.add(campus, "Original campus note.")
    public = ops.init("campus-wiki/public")
    ops.add(public, PUBLIC)
    details = ops.init("campus-wiki/construction-details")
    ops.add(details, SECRET)
    details_child = ops.init("campus-wiki/construction-details/internal")
    ops.add(details_child, "Additional concealed construction detail.")
    ops.embed(public, campus)
    ops.embed(details, campus)
    ops.embed(details_child, details)
    for context in (campus, public, details, details_child):
        authority_store.save(context)
    authority_store.set_current(campus.name)

    registry = ProfileRegistry(
        generation=1,
        active_uid=authoring.uid,
        profiles=(authoring, authority),
        grants=(),
    )
    path = profile_registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(registry.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    _registry, campus_grant = create_authority_grant(
        authority_name=authority.name,
        grantee_name=authoring.name,
        resource_name=campus.name,
        attachment_name=task_root.name,
        public_name=campus.name,
        permissions=("READ", "CREATE", "UPDATE"),
        recursive=True,
    )
    _registry, details_grant = create_authority_grant(
        authority_name=authority.name,
        grantee_name=authoring.name,
        resource_name=details.name,
        attachment_name=task_root.name,
        public_name=details.name,
        permissions=("QUERY",),
        recursive=True,
    )
    return authority_store, editable, campus_grant, details_grant


def test_unrelated_missing_context_is_not_reported_as_a_granted_view(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _grant_fixture(isolated_store, tmp_path, monkeypatch)
    store = MemoryStore()

    with pytest.raises(
        FileNotFoundError,
        match=r"Context 'practice/3' does not exist\.",
    ):
        resolve_context_access(
            store,
            "practice/3",
            current_name="task-root",
            required_permission="READ",
        )

    checkout = runner.invoke(app, ["checkout", "practice/3"])

    assert checkout.exit_code == 1
    assert "context 'practice/3' does not exist" in checkout.stderr
    assert "Granted view" not in checkout.stderr


def test_switch_navigation_reauthorizes_local_and_granted_history_targets(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _grant_fixture(isolated_store, tmp_path, monkeypatch)

    granted = runner.invoke(app, ["switch", "campus-wiki"])
    local = runner.invoke(app, ["switch", "--previous"])
    granted_again = runner.invoke(app, ["switch", "--next"])

    assert granted.exit_code == 0, granted.output
    assert local.exit_code == 0, local.output
    assert "Switched to context 'task-root'" in local.output
    assert granted_again.exit_code == 0, granted_again.output
    assert "Switched to context 'campus-wiki'" in granted_again.output
    assert MemoryStore().current_context_name() == "campus-wiki"


def test_ls_projects_read_view_and_masks_narrower_query_view(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _authority, _editable, campus_grant, _details_grant = _grant_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    root = runner.invoke(app, ["ls"])
    view = runner.invoke(app, ["ls", "campus-wiki", "--recursive"])
    shown = runner.invoke(app, ["show", "--context", "campus-wiki/public"])
    contexts = runner.invoke(app, ["contexts"])

    assert root.exit_code == 0, root.output
    assert "campus-wiki" in root.output
    assert "Authority views:" in root.output
    assert "task-1-campus-authority" in root.output
    assert "Permissions: CREATE + READ + UPDATE" in root.output
    assert (
        "Source boundary: DERIVE blocked · COMBINE blocked · EXPORT blocked"
        in root.output
    )
    assert (
        "Target/artifact boundary: ACCEPT_DERIVED blocked · "
        "SAVE_BOUND_ANALYSIS blocked · SAVE_ANALYSIS blocked" in root.output
    )
    assert view.exit_code == 0, view.output
    assert "Access: READ GRANT · PERMISSIONS CREATE + READ + UPDATE" in view.output
    assert "READ ONLY · FROM task-1-campus-authority" in view.output
    assert f"GRANT {campus_grant.uid[:8]} · REVISION 1" in view.output
    assert PUBLIC in view.output
    assert "[query view " in view.output
    assert "campus-wiki/construction-details" in view.output
    assert view.output.count("campus-wiki/construction-details") == 1
    assert SECRET not in view.output
    assert "Additional concealed construction detail" not in view.output
    assert shown.exit_code == 0, shown.output
    assert PUBLIC in shown.output
    assert contexts.exit_code == 0, contexts.output
    assert "GRANT  campus-wiki  READ + EDIT" in contexts.output
    assert "GRANT  campus-wiki/construction-details  QUERY" in contexts.output
    assert "PERMISSIONS" not in contexts.output
    assert "FROM task-1-campus-authority" in contexts.output


def test_public_show_reuses_the_same_read_grant_and_concealment_boundary(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _grant_fixture(isolated_store, tmp_path, monkeypatch)

    result = MemCommitClient().show(context_name="campus-wiki")

    assert isinstance(result, ShowContextResult)
    assert result.name == "campus-wiki"
    assert result.source.access == "READ_GRANT"
    assert result.source.states == ("READ_ONLY",)
    assert PUBLIC in [
        nested.content
        for item in result.items
        if item.kind == "context" and item.name == "campus-wiki/public"
        for nested in MemCommitClient().show(context_name=item.name).items
    ]
    assert "campus-wiki/construction-details" in [
        item.name for item in result.items if item.kind == "query_view"
    ]
    assert SECRET not in repr(result)


def test_status_keeps_read_only_projection_and_shows_granted_target_permissions(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _authority, _editable, campus_grant, details_grant = _grant_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    store = MemoryStore()
    store.set_current_virtual_context_if("task-root", "campus-wiki")

    short = runner.invoke(app, ["status", "--short"])
    detailed = runner.invoke(app, ["status"])

    assert short.exit_code == 0, short.output
    assert "READ GRANT · PERMISSIONS CREATE + READ + UPDATE · READ ONLY" in short.output
    assert detailed.exit_code == 0, detailed.output
    assert (
        "Access: READ GRANT · PERMISSIONS CREATE + READ + UPDATE · READ ONLY"
        in detailed.output
    )

    store.set_current("task-root")
    attached = runner.invoke(app, ["status"])

    assert attached.exit_code == 0, attached.output
    assert "Relationships:" in attached.output
    assert (
        f"GRANT [{campus_grant.uid[:8]} r1] campus-wiki · "
        "PERMISSIONS CREATE + READ + UPDATE"
    ) in attached.output
    assert (
        f"GRANT [{details_grant.uid[:8]} r1] "
        "campus-wiki/construction-details · PERMISSIONS QUERY"
    ) in attached.output
    assert "Original campus note." not in attached.output


def test_summarize_preserves_granted_read_projection_and_binding_freshness(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _authority, _editable, campus_grant, _details_grant = _grant_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    payloads: list[dict[str, object]] = []

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            payload = json.loads(prompt.split("SUMMARIZE CONTEXT PAYLOAD:\n", 1)[1])
            payloads.append(payload)
            memories = payload["memories"]
            assert isinstance(memories, list)
            return json.dumps(
                {
                    "text": "The readable campus notes retain public access rules.",
                    "source_ids": [item["source_id"] for item in memories],
                }
            )

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.summarize.command.connect_codex_chatgpt_provider",
        Provider,
    )

    direct = execute_summarize(
        SummarizeRequest(
            context_locator="campus-wiki",
            include_descendants=True,
            follow_embeds=True,
        ),
        store=MemoryStore(),
        provider_factory=Provider,
    )

    visible = runner.invoke(app, ["summarize", "campus-wiki", "-r"])

    assert direct.context_name == "campus-wiki"
    assert direct.source_count == 2
    assert visible.exit_code == 0, visible.output
    assert direct.understanding.text in visible.output
    assert payloads[0] == payloads[1]
    for payload in payloads:
        encoded = json.dumps(payload, ensure_ascii=False)
        assert PUBLIC in encoded
        assert SECRET not in encoded

    class RevisionChangingProvider(Provider):
        def complete(self, prompt, *, operation, output_schema=None):
            response = super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )
            update_authority_grant(
                campus_grant.uid,
                permissions=("READ", "CREATE", "UPDATE"),
            )
            return response

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.summarize.command.connect_codex_chatgpt_provider",
        RevisionChangingProvider,
    )

    stale = runner.invoke(app, ["summarize", "campus-wiki", "-r"])

    assert stale.exit_code == 1
    assert "authority grant changed" in stale.stderr.casefold()
    assert "WHAT MEM UNDERSTOOD" not in stale.stdout


def test_profile_readable_catalog_stays_profile_wide_from_a_granted_current_view(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _grant_fixture(isolated_store, tmp_path, monkeypatch)
    store = MemoryStore()
    access = resolve_context_access(
        store,
        "campus-wiki",
        current_name="task-root",
        required_permission="READ",
    )
    store.set_current_virtual_context_if("task-root", "campus-wiki")

    catalog = freeze_profile_readable_context_catalog(store, access)

    assert tuple(catalog.list_context_names()) == (
        "campus-wiki",
        "campus-wiki/public",
        "task-root",
    )
    assert catalog.access_for("task-root").is_granted is False
    assert catalog.access_for("campus-wiki").is_granted is True


def test_profile_target_workbenches_keep_all_readable_names_from_a_grant(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _grant_fixture(isolated_store, tmp_path, monkeypatch)
    store = MemoryStore()
    store.set_current_virtual_context_if("task-root", "campus-wiki")
    access = resolve_context_access(
        store,
        None,
        current_name="campus-wiki",
        required_permission="READ",
    )
    opened: dict[str, tuple[tuple[str, ...], str, str]] = {}

    def capture_query(context_names, **kwargs):
        opened["query"] = (
            tuple(context_names),
            kwargs["current_context"],
            kwargs["initial_context"],
        )

    def capture_find(context_names, **kwargs):
        opened["find"] = (
            tuple(context_names),
            kwargs["current"],
            kwargs["initial_target"],
        )

    monkeypatch.setattr(query_command, "run_query_workbench", capture_query)
    monkeypatch.setattr(find_command, "run_search_workbench", capture_find)

    query_command._open_query_workbench(
        store,
        context_name=None,
        language="en",
    )
    find_command._open_search_workbench(
        store,
        access,
        current_name="campus-wiki",
        include_descendants=True,
        follow_embeds=True,
        limit=5,
    )

    expected = ("campus-wiki", "campus-wiki/public", "task-root")
    assert opened == {
        "query": (expected, "campus-wiki", "campus-wiki"),
        "find": (expected, "campus-wiki", "campus-wiki"),
    }


def test_explicit_granted_rationale_picker_keeps_readable_descendants(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _authority, editable, _campus_grant, _details_grant = _grant_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    observed: dict[str, object] = {}

    def select_memory(items, *, context_name, catalog_context_names, **kwargs):
        observed["scope"] = tuple(catalog_context_names)
        assert any(item.uid == editable.uid for item in items)
        return MemoryReportTargetSelection(
            root_context_name=context_name,
            owner_context_name="campus-wiki",
            memory_uid=editable.uid,
            include_descendants=False,
        )

    monkeypatch.setattr(rationale_command, "interactive_report_terminal", lambda: True)
    monkeypatch.setattr(
        rationale_command,
        "choose_memory_report_target",
        select_memory,
    )
    result = runner.invoke(app, ["rationale", "--context", "campus-wiki"])

    assert result.exit_code == 0, result.output + result.stderr
    assert observed["scope"] == ("campus-wiki", "campus-wiki/public")
    assert "PROVENANCE — hidden by Grant" in result.output
    assert "APPARENT PURPOSE" not in result.output
    assert MemoryStore().current_context_name() == "task-root"


def test_granted_read_shows_current_trace_route_but_never_opens_history(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    authority_store, _editable, _campus_grant, _details_grant = _grant_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    target = next(
        item
        for item in authority_store.load_direct("campus-wiki/public").iter_items()
        if isinstance(item, Memory)
    )
    owner = authority_store.load_direct("campus-wiki/public")
    updated_content = "Current owner revision visible through READ."
    owner.replace(Memory(uid=target.uid, content=updated_content))
    authority_store.save(owner)

    def forbidden_history(*args, **kwargs):
        raise AssertionError("granted READ opened authority checkpoint history")

    monkeypatch.setattr(MemoryStore, "list_checkpoints", forbidden_history)

    shown = runner.invoke(app, ["show", target.uid[:8]])
    rationale = runner.invoke(app, ["rationale", target.uid[:8]])
    trace = runner.invoke(
        app,
        [
            "trace",
            target.uid[:8],
        ],
    )
    log_memory = runner.invoke(
        app,
        [
            "log",
            "--memory",
            target.uid[:8],
            "--context",
            "campus-wiki/public",
        ],
    )
    assert shown.exit_code == 0, shown.output + shown.stderr
    assert updated_content in shown.output
    assert rationale.exit_code == 0, rationale.output + rationale.stderr
    assert "PROVENANCE — hidden by Grant" in rationale.output
    assert "ACCESS ROUTE" in rationale.output
    assert "APPARENT PURPOSE" not in rationale.output
    assert SECRET not in rationale.output
    assert updated_content in rationale.output
    assert trace.exit_code == 0, trace.output
    assert "CURRENT GRANTED VIEW" in trace.output
    assert "ACCESS ROUTE" in trace.output
    assert "HISTORY — hidden by Grant" in trace.output
    assert updated_content in trace.output
    assert log_memory.exit_code == 1
    assert "READ does not expose authority checkpoint" in log_memory.stderr


@pytest.mark.parametrize("operation", ("show", "trace", "rationale"))
def test_bare_read_report_uid_rejects_local_and_granted_collision(
    isolated_store,
    tmp_path,
    monkeypatch,
    operation,
):
    authority_store, _editable, _campus_grant, _details_grant = _grant_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    granted = next(
        item
        for item in authority_store.load_direct("campus-wiki/public").iter_items()
        if isinstance(item, Memory)
    )
    store = MemoryStore()
    local = store.load_direct("task-root")
    local.add(Memory(uid=granted.uid, content="A distinct local occurrence."))
    store.save(local)

    result = runner.invoke(app, [operation, granted.uid])

    assert result.exit_code == 1
    assert "multiple current readable matches" in result.stderr
    assert f"task-root:{granted.uid}" in result.stderr
    assert f"campus-wiki/public:{granted.uid}" in result.stderr


def test_read_view_does_not_open_nested_query_authority_record(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    authority_store, _editable, _campus_grant, _details_grant = _grant_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    concealed_record = (
        authority_store.contexts_dir
        / "campus-wiki"
        / "construction-details"
        / "context.json"
    )
    concealed_record.write_text("not readable as context json\n", encoding="utf-8")

    selected = runner.invoke(app, ["profile", "use", AUTHORING_PROFILE_NAME])
    view = runner.invoke(app, ["ls", "campus-wiki", "--recursive"])

    assert selected.exit_code == 0, selected.output
    assert view.exit_code == 0, view.output
    assert PUBLIC in view.output
    assert "[query view " in view.output
    assert "campus-wiki/construction-details" in view.output


def test_granted_memory_create_and_update_write_authority_store_only(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    authority_store, editable, _campus_grant, _details_grant = _grant_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    added = runner.invoke(
        app,
        ["add", "Created through the task view.", "--context", "campus-wiki"],
    )
    edited = runner.invoke(
        app,
        [
            "edit",
            editable.uid,
            "Revised through the task view.",
            "--context",
            "campus-wiki",
        ],
    )

    assert added.exit_code == 0, added.output
    assert edited.exit_code == 0, edited.output
    authority = authority_store.load_direct("campus-wiki")
    assert [
        item.content for item in authority.iter_items() if isinstance(item, Memory)
    ] == [
        "Revised through the task view.",
        "Created through the task view.",
    ]
    task = MemoryStore().load_direct("task-root")
    assert list(task.iter_items()) == []


def test_delete_permission_and_view_revocation_fail_closed(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _store, editable, campus_grant, _details_grant = _grant_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    denied = runner.invoke(
        app,
        ["remove", editable.uid, "--context", "campus-wiki"],
    )
    revoked = runner.invoke(
        app,
        ["profile", "grant", "delete", campus_grant.uid],
    )
    missing = runner.invoke(app, ["ls", "campus-wiki"])

    assert denied.exit_code == 1
    assert "does not allow delete access" in denied.stderr
    assert revoked.exit_code == 0, revoked.output
    assert len(load_profile_registry().grants) == 1
    assert missing.exit_code == 1
    assert "Context 'campus-wiki' does not exist" in missing.stderr
    assert "Granted view" not in missing.stderr


def test_granted_delete_permission_removes_only_authority_memory(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    authority_store, editable, campus_grant, _details_grant = _grant_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    update_authority_grant(
        campus_grant.uid,
        permissions=("READ", "DELETE"),
    )

    removed = runner.invoke(
        app,
        ["remove", editable.uid, "--context", "campus-wiki"],
    )

    assert removed.exit_code == 0, removed.output
    assert editable.uid not in authority_store.load_direct("campus-wiki").memories
    assert list(MemoryStore().load_direct("task-root").iter_items()) == []


def test_profile_grant_cli_creates_and_updates_frozen_permission_record(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _store, _editable, campus_grant, _details_grant = _grant_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    updated = runner.invoke(
        app,
        [
            "profile",
            "grant",
            "update",
            campus_grant.uid[:8],
            "--allow",
            "READ",
            "--allow",
            "DELETE",
            "--root-only",
        ],
    )
    listed = runner.invoke(app, ["profile", "grant", "list"])

    assert updated.exit_code == 0, updated.output
    grant = next(
        item for item in load_profile_registry().grants if item.uid == campus_grant.uid
    )
    assert grant.revision == 2
    assert grant.permissions == ("READ", "DELETE")
    assert len(grant.contexts) == 1
    assert listed.exit_code == 0, listed.output
    assert "read,delete" in listed.output
    assert "task-1-campus-authority:campus-wiki" in listed.output
