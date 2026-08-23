"""One-shot authority-granted Query Source boundaries."""

from __future__ import annotations

import hashlib
import json
import re
import uuid

import pytest
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
from memcommit.query_provider import QueryProviderError
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
    *,
    public_name="construction-details",
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
        public_name=public_name,
        permissions=("QUERY",),
    )
    return authority_store, source_context, source_memory, grant


def _read_authority_grants(
    isolated_store,
    tmp_path,
    monkeypatch,
    *,
    permissions=("READ", "DERIVE", "COMBINE"),
):
    """Create two readable Sources attached to one distracting local workspace."""

    monkeypatch.setenv("HOME", str(tmp_path))
    task_store = MemoryStore()
    attachment = ops.init("task-2/participant/proposal-workspace")
    local_distraction = "A local draft that must not enter an exact granted Query."
    ops.add(attachment, local_distraction)
    task_store.save(attachment)
    task_store.set_current(attachment.name)

    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="task-2-advisors",
        kind="MANAGED",
    )
    authoring = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    source_specs = (
        (
            "advisor1/budget",
            "task-2/advisor1/budget",
            "Advisor one requires budget totals in the main body.",
        ),
        (
            "advisor2/budget",
            "task-2/advisor2/budget",
            "Advisor two allows detailed arithmetic in an appendix.",
        ),
    )
    for source_name, _public_name, content in source_specs:
        source = ops.init(source_name)
        ops.add(source, content)
        authority_store.save(source)
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
    for source_name, public_name, _content in source_specs:
        create_authority_grant(
            authority_name=authority.name,
            grantee_name=authoring.name,
            resource_name=source_name,
            attachment_name=attachment.name,
            public_name=public_name,
            permissions=permissions,
        )
    return attachment, local_distraction, source_specs


class _OrdinaryAnswerProvider:
    def __init__(self, calls):
        self.calls = calls

    def complete(self, prompt, *, operation, output_schema):
        assert operation == "ordinary query"
        payload = json.loads(prompt.split("ORDINARY QUERY PAYLOAD:\n", 1)[1])
        corpus = payload["complete_frozen_corpus"]
        self.calls.append(tuple((item["context"], item["content"]) for item in corpus))
        return json.dumps(
            {
                "outcome_kind": "ANSWER",
                "blocks": [
                    {
                        "role": "SUPPORTED_CLAIM",
                        "text": "The authorized budget Sources support this answer.",
                        "source_aliases": [item["alias"] for item in corpus],
                    }
                ],
            }
        )


@pytest.mark.parametrize(
    "public_name",
    (
        "task-1/campus-wiki/construction-details",
        "task-2/proposal/submission-guidelines",
        "task-3/medical/recipient-requirements",
    ),
)
def test_canonical_query_view_name_does_not_depend_on_current_context(
    isolated_store,
    tmp_path,
    monkeypatch,
    public_name,
):
    _authority_grant(
        isolated_store,
        tmp_path,
        monkeypatch,
        public_name=public_name,
    )
    store = MemoryStore()
    unrelated = ops.init("practice/unrelated")
    ops.add(unrelated, "This current Context is not a query attachment.")
    store.save(unrelated)
    store.set_current(unrelated.name)
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
        ["query", public_name, "When can it open?"],
    )

    assert result.exit_code == 0, result.output
    assert result.output == "Use the tunnel after 18:00.\n"
    assert calls == [(public_name, SECRET, "When can it open?")]
    assert store.current_context_name() == unrelated.name


@pytest.mark.parametrize("context_option", (False, True))
def test_canonical_query_target_does_not_open_authority_before_provider(
    isolated_store,
    tmp_path,
    monkeypatch,
    context_option,
):
    public_name = "task-3/medical/recipient-requirements"
    _authority_grant(
        isolated_store,
        tmp_path,
        monkeypatch,
        public_name=public_name,
    )
    opened = False

    def unavailable(_provider):
        raise QueryProviderError("not logged in")

    def forbidden(*_args, **_kwargs):
        nonlocal opened
        opened = True
        raise AssertionError("authority content opened before provider connection")

    monkeypatch.setattr(
        "memcommit.commands.query.connect_query_provider",
        unavailable,
    )
    monkeypatch.setattr(
        "memcommit.operations.query.granted_runtime.resolve_granted_context_view",
        forbidden,
    )
    argv = (
        ["query", "What may be disclosed?", "--context", public_name]
        if context_option
        else ["query", public_name, "What may be disclosed?"]
    )
    result = runner.invoke(app, argv)

    assert result.exit_code == 1
    assert "not logged in" in result.stderr
    assert opened is False


def test_query_only_context_option_uses_the_named_view_not_its_local_attachment(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    public_name = "task-3/medical/recipient-requirements"
    _authority_grant(
        isolated_store,
        tmp_path,
        monkeypatch,
        public_name=public_name,
    )
    task_store = MemoryStore()
    attachment = task_store.load_direct("task-root")
    local_distraction = "Private local patient notes must remain outside this Query."
    ops.add(attachment, local_distraction)
    task_store.save(attachment)
    calls: list[tuple[str, str, str]] = []

    class Provider:
        def query(self, source_name, source_content, question):
            calls.append((source_name, source_content, question))
            return "Use only the authorized recipient requirements."

    monkeypatch.setattr(
        "memcommit.commands.query.connect_query_provider",
        lambda _provider: Provider(),
    )
    monkeypatch.setattr(
        "memcommit.commands.query.connect_codex_chatgpt_provider",
        lambda: (_ for _ in ()).throw(
            AssertionError("QUERY-only --context must not use ordinary Query")
        ),
    )
    result = runner.invoke(
        app,
        ["query", "What may be disclosed?", "--context", public_name],
    )

    assert result.exit_code == 0, result.output
    assert calls == [(public_name, SECRET, "What may be disclosed?")]
    assert local_distraction not in result.output


def test_explicit_read_grant_remains_the_ordinary_query_source(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    attachment, local_distraction, source_specs = _read_authority_grants(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    calls = []
    monkeypatch.setattr(
        "memcommit.commands.query.connect_codex_chatgpt_provider",
        lambda: _OrdinaryAnswerProvider(calls),
    )

    _source_name, public_name, content = source_specs[0]
    result = runner.invoke(
        app,
        ["query", "Where must totals appear?", "--context", public_name],
    )

    assert result.exit_code == 0, result.output
    assert calls == [((public_name, content),)]
    assert public_name in result.output
    assert attachment.name not in result.output
    assert local_distraction not in result.output


def test_repeated_read_grants_freeze_exactly_the_named_ordinary_sources(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    attachment, local_distraction, source_specs = _read_authority_grants(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    calls = []
    monkeypatch.setattr(
        "memcommit.commands.query.connect_codex_chatgpt_provider",
        lambda: _OrdinaryAnswerProvider(calls),
    )
    expected = tuple((public_name, content) for _, public_name, content in source_specs)

    result = runner.invoke(
        app,
        [
            "query",
            "How can the budget policies be reconciled?",
            "--context",
            source_specs[0][1],
            "--context",
            source_specs[1][1],
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [expected]
    assert all(public_name in result.output for _, public_name, _ in source_specs)
    assert attachment.name not in result.output
    assert local_distraction not in result.output


@pytest.mark.parametrize(
    ("permissions", "multiple", "expected_permission"),
    (
        (("READ",), False, "DERIVE"),
        (("READ", "DERIVE"), True, "COMBINE"),
    ),
)
def test_read_grant_query_fails_before_provider_without_derived_authority(
    isolated_store,
    tmp_path,
    monkeypatch,
    permissions,
    multiple,
    expected_permission,
):
    _attachment, _local_distraction, source_specs = _read_authority_grants(
        isolated_store,
        tmp_path,
        monkeypatch,
        permissions=permissions,
    )
    monkeypatch.setattr(
        "memcommit.commands.query.connect_codex_chatgpt_provider",
        lambda: (_ for _ in ()).throw(
            AssertionError("authority failure must precede provider construction")
        ),
    )
    argv = ["query", "What do the authorized Sources say?"]
    for _source_name, public_name, _content in source_specs[: 2 if multiple else 1]:
        argv.extend(("--context", public_name))

    result = runner.invoke(app, argv)

    assert result.exit_code == 1
    assert expected_permission in result.stderr


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


def test_legacy_explicit_attachment_form_keeps_the_same_granted_target(
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
        [
            "query",
            "construction-details",
            "When can it open?",
            "--context",
            "task-root",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [("construction-details", SECRET, "When can it open?")]


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
