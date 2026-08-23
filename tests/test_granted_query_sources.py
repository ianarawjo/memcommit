"""One-shot authority-granted Query Source boundaries."""

from __future__ import annotations

import hashlib
import json
import re
import uuid

from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.flow_placeholder import render_flow_circular_placeholder
from memcommit.profile_config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.profiles import create_authority_grant, delete_authority_grant
from memcommit.store import MemoryStore
from memcommit.translation_view import (
    TRANSLATION_ORIGIN_IMPORTED,
    TranslationCatalog,
)


runner = CliRunner(mix_stderr=False)
SECRET = "The north utility tunnel opens only after 18:00."


def _authority_grant(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    task_store = MemoryStore()
    task_context = ops.init("task-root")
    task_store.save(task_context)
    task_store.set_current(task_context.name)

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
    source_context = ops.init("construction-details")
    source_memory = ops.add(source_context, SECRET)
    authority_store.save(source_context)
    authority_store.set_current(source_context.name)
    registry = ProfileRegistry(
        generation=1,
        active_uid=authoring.uid,
        profiles=(authoring, authority),
        grants=(),
    )
    registry_path = profile_registry_file()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(registry.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    _registry, grant = create_authority_grant(
        authority_name=authority.name,
        grantee_name=authoring.name,
        resource_name=source_context.name,
        attachment_name=task_context.name,
        public_name="construction-details",
        permissions=("QUERY",),
    )
    return authority_store, source_context, source_memory, grant


def _federated_authority_grants(isolated_store, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    task_store = MemoryStore()
    task_context = ops.init("task-root")
    task_store.save(task_context)
    task_store.set_current(task_context.name)
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
    wiki = ops.init("campus-wiki")
    ops.add(wiki, "The public campus wiki lists service hours.")
    details = ops.init("campus-wiki/construction-details")
    ops.add(details, "Electrical testing is required before final inspection.")
    authority_store.save(wiki)
    authority_store.save(details)
    authority_store.set_current(wiki.name)
    registry = ProfileRegistry(
        generation=1,
        active_uid=authoring.uid,
        profiles=(authoring, authority),
        grants=(),
    )
    registry_path = profile_registry_file()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(registry.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    _registry, parent = create_authority_grant(
        authority_name=authority.name,
        grantee_name=authoring.name,
        resource_name=wiki.name,
        attachment_name=task_context.name,
        public_name="campus-wiki",
        permissions=("QUERY",),
    )
    _registry, child = create_authority_grant(
        authority_name=authority.name,
        grantee_name=authoring.name,
        resource_name=details.name,
        attachment_name=task_context.name,
        public_name="campus-wiki/construction-details",
        permissions=("QUERY",),
    )
    return parent, child


def test_granted_query_is_one_shot_and_creates_no_transcript_storage(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _authority_grant(isolated_store, tmp_path, monkeypatch)
    calls: list[tuple[str, str, str]] = []

    class Provider:
        def query(self, source_name, source_content, question):
            calls.append((source_name, source_content, question))
            return "Use the tunnel after 18:00."

    monkeypatch.setattr(
        "memcommit.commands.query.connect_query_provider",
        lambda _provider: Provider(),
    )
    result = runner.invoke(
        app,
        ["query", "construction-details", "When can it open?"],
    )

    assert result.exit_code == 0, result.output
    assert result.output == "Use the tunnel after 18:00.\n"
    assert calls == [("construction-details", SECRET, "When can it open?")]
    assert not (isolated_store / "query-sessions").exists()


def test_granted_query_catalog_contains_only_opaque_memory_shapes(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _store, _context, source_memory, _grant = _authority_grant(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    class Provider:
        def query(self, *_args):
            raise AssertionError("catalog mode must not query the provider")

    monkeypatch.setattr(
        "memcommit.commands.query.connect_query_provider",
        lambda _provider: Provider(),
    )
    result = runner.invoke(app, ["query", "construction-details"])

    assert result.exit_code == 0, result.output
    assert "Query view Memories: construction-details" in result.output
    assert "[q-" in result.output
    for expected_shape in render_flow_circular_placeholder(SECRET):
        assert expected_shape in result.output
    assert SECRET not in result.output
    assert source_memory.uid not in result.output


def test_opaque_memory_handle_queries_only_the_selected_memory(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    authority_store, source_context, _memory, _grant = _authority_grant(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    second = "Blue badge required at the west entrance."
    current = authority_store.load_direct(source_context.name)
    ops.add(current, second)
    authority_store.save(current)
    calls: list[tuple[str, str, str]] = []

    class Provider:
        def query(self, source_name, source_content, question):
            calls.append((source_name, source_content, question))
            return "Use the west entrance."

    monkeypatch.setattr(
        "memcommit.commands.query.connect_query_provider",
        lambda _provider: Provider(),
    )
    catalog = runner.invoke(app, ["query", "construction-details"])
    handles = re.findall(r"\[(q-[0-9a-f]{12})\]", catalog.output)
    result = runner.invoke(
        app,
        ["query", f"construction-details#{handles[1]}", "Which entrance?"],
    )

    assert result.exit_code == 0, result.output
    assert calls == [(f"construction-details#{handles[1]}", second, "Which entrance?")]
    assert SECRET not in calls[0][1]


def test_parent_query_federates_only_provider_selected_descendants(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _federated_authority_grants(isolated_store, tmp_path, monkeypatch)
    calls: list[tuple[str, str, str]] = []

    class Provider:
        def complete(self, prompt, *, operation, output_schema):
            assert operation == "query view routing"
            assert "Electrical testing" not in prompt
            assert output_schema["properties"]["selected_views"]["items"]["enum"] == [
                "campus-wiki/construction-details"
            ]
            return json.dumps({"selected_views": ["campus-wiki/construction-details"]})

        def query(self, source_name, source_content, question):
            calls.append((source_name, source_content, question))
            return "Answer."

    monkeypatch.setattr(
        "memcommit.commands.query.connect_query_provider",
        lambda _provider: Provider(),
    )
    result = runner.invoke(
        app,
        ["query", "-r", "campus-wiki", "What construction test is required?"],
    )

    assert result.exit_code == 0, result.output
    source = json.loads(calls[0][1])
    assert [item["name"] for item in source["views"]] == [
        "campus-wiki",
        "campus-wiki/construction-details",
    ]


def test_revocation_during_provider_call_prevents_answer_disclosure(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _store, _context, _memory, grant = _authority_grant(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    class Provider:
        def query(self, *_args):
            delete_authority_grant(grant.uid)
            return "Answer from a now-revoked view."

    monkeypatch.setattr(
        "memcommit.commands.query.connect_query_provider",
        lambda _provider: Provider(),
    )
    result = runner.invoke(
        app,
        ["query", "construction-details", "Question?"],
    )

    assert result.exit_code == 1
    assert "Answer from a now-revoked view" not in result.output
    assert not (isolated_store / "query-sessions").exists()


def test_granted_query_uses_complete_root_bound_translation_catalog(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    authority_store, source_context, source_memory, _grant = _authority_grant(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    catalog = TranslationCatalog.empty(source_context, "ko").with_curated(
        source_context,
        source_memory.uid,
        "북쪽 설비 터널은 오후 6시 이후에만 열린다.",
        origin=TRANSLATION_ORIGIN_IMPORTED,
        evidence_sha256=hashlib.sha256(b"fixture").hexdigest(),
    )
    translations = authority_store.store_dir / "translation-views"
    translations.mkdir()
    language_digest = hashlib.sha256(b"ko").hexdigest()
    path = translations / f"{source_context.uid}--{language_digest}--catalog.json"
    path.write_text(
        json.dumps(catalog.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    calls: list[tuple[str, str, str]] = []

    class Provider:
        def query(self, source_name, source_content, question):
            calls.append((source_name, source_content, question))
            return "오후 6시 이후입니다."

    monkeypatch.setattr(
        "memcommit.commands.query.connect_query_provider",
        lambda _provider: Provider(),
    )
    result = runner.invoke(
        app,
        ["query", "construction-details", "언제 열리나요?", "--language", "ko"],
    )

    assert result.exit_code == 0, result.output
    assert calls == [
        (
            "construction-details",
            "북쪽 설비 터널은 오후 6시 이후에만 열린다.",
            "언제 열리나요?",
        )
    ]
