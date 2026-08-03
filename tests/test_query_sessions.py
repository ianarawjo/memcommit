"""Authority-granted query views and explicit durable query sessions."""
from __future__ import annotations

import hashlib
import json
import re
import stat
import uuid

from typer.testing import CliRunner

import memcommit.ops as ops
import memcommit.query_sessions as query_sessions
from memcommit.cli import app
from memcommit.context import Memory
from memcommit.profile_config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.profiles import (
    create_authority_grant,
    delete_authority_grant,
)
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
    permissions: tuple[str, ...],
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
    _updated, grant = create_authority_grant(
        authority_name=authority.name,
        grantee_name=authoring.name,
        resource_name=source_context.name,
        attachment_name=task_context.name,
        public_name="construction-details",
        permissions=permissions,
    )
    return authority_store, source_context, source_memory, grant


def test_authority_query_without_question_lists_only_opaque_memory_shapes(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _authority_store, _context, source_memory, _grant = _authority_grant(
        isolated_store,
        tmp_path,
        monkeypatch,
        permissions=("QUERY",),
    )
    query_calls = 0

    class Provider:
        def query(self, *_args):
            nonlocal query_calls
            query_calls += 1
            return "must not run"

    monkeypatch.setattr(
        "memcommit.commands.query.connect_query_provider",
        lambda _provider: Provider(),
    )

    result = runner.invoke(app, ["query", "construction-details"])

    assert result.exit_code == 0, result.output
    assert "Query-only Memories: construction-details" in result.output
    assert "1 queryable Memory" in result.output
    assert "[q-" in result.output
    expected_shape = "".join(
        " " if character == " " else "●" for character in SECRET
    )
    assert expected_shape in result.output
    assert SECRET not in result.output
    assert source_memory.uid not in result.output
    assert "source text is not present" in result.output
    assert query_calls == 0


def test_opaque_memory_handle_queries_only_the_selected_memory(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    authority_store, source_context, _source_memory, _grant = _authority_grant(
        isolated_store,
        tmp_path,
        monkeypatch,
        permissions=("QUERY",),
    )
    second_content = "Blue badge required at the west entrance."
    current = authority_store.load_direct(source_context.name)
    ops.add(current, second_content)
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
    assert catalog.exit_code == 0, catalog.output
    assert len(handles) == 2

    result = runner.invoke(
        app,
        [
            "query",
            f"construction-details#{handles[1]}",
            "Which entrance?",
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.output == "Use the west entrance.\n"
    assert calls == [
        (
            f"construction-details#{handles[1]}",
            second_content,
            "Which entrance?",
        )
    ]
    assert SECRET not in calls[0][1]


def test_unknown_opaque_memory_handle_fails_without_querying_provider(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _authority_grant(
        isolated_store,
        tmp_path,
        monkeypatch,
        permissions=("QUERY",),
    )
    query_calls = 0

    class Provider:
        def query(self, *_args):
            nonlocal query_calls
            query_calls += 1
            return "must not run"

    monkeypatch.setattr(
        "memcommit.commands.query.connect_query_provider",
        lambda _provider: Provider(),
    )

    result = runner.invoke(
        app,
        [
            "query",
            "construction-details#q-000000000000",
            "Question?",
        ],
    )

    assert result.exit_code == 1
    assert "does not exist in this view" in result.stderr
    assert SECRET not in result.output
    assert query_calls == 0


def test_opaque_catalog_authenticates_before_loading_authority_memories(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _authority_grant(
        isolated_store,
        tmp_path,
        monkeypatch,
        permissions=("QUERY",),
    )
    opened = False

    def unavailable(_provider):
        raise QueryProviderError("not logged in")

    def track_open(*_args, **_kwargs):
        nonlocal opened
        opened = True
        raise AssertionError("catalog opened authority Memories before auth")

    monkeypatch.setattr(
        "memcommit.commands.query.connect_query_provider",
        unavailable,
    )
    monkeypatch.setattr(
        "memcommit.commands.query.load_authority_query_catalog",
        track_open,
    )

    result = runner.invoke(app, ["query", "construction-details"])

    assert result.exit_code == 1
    assert "not logged in" in result.stderr
    assert opened is False
    assert SECRET not in result.output


def test_authority_query_reads_ordinary_memories_without_saving_a_session(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _authority_grant(
        isolated_store,
        tmp_path,
        monkeypatch,
        permissions=("QUERY",),
    )
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
    assert calls == [
        ("construction-details", SECRET, "When can it open?")
    ]
    assert not (isolated_store / "query-sessions").exists()


def test_saved_authority_query_session_replays_only_visible_qa(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _authority_grant(
        isolated_store,
        tmp_path,
        monkeypatch,
        permissions=("QUERY", "SESSION_LOG"),
    )
    calls: list[tuple[str, str, str]] = []

    class Provider:
        def query(self, source_name, source_content, question):
            calls.append((source_name, source_content, question))
            return "First answer." if len(calls) == 1 else "Second answer."

    monkeypatch.setattr(
        "memcommit.commands.query.connect_query_provider",
        lambda _provider: Provider(),
    )

    first = runner.invoke(
        app,
        [
            "query",
            "construction-details",
            "First question?",
            "--session",
            "campus-review",
        ],
    )
    second = runner.invoke(
        app,
        [
            "query",
            "construction-details",
            "Follow-up question?",
            "--session",
            "campus-review",
        ],
    )

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert calls[0] == (
        "construction-details",
        SECRET,
        "First question?",
    )
    assert calls[1] == (
        "construction-details",
        SECRET,
        "Continue the saved query session using these prior visible turns.\n\n"
        "[Turn 1 question]\nFirst question?\n\n"
        "[Turn 1 answer]\nFirst answer.\n\n"
        "[Current question]\nFollow-up question?",
    )

    records = list((isolated_store / "query-sessions").glob("*.json"))
    assert len(records) == 1
    raw = records[0].read_text(encoding="utf-8")
    record = json.loads(raw)
    assert record["revision"] == 2
    assert record["turns"] == [
        {"question": "First question?", "answer": "First answer."},
        {"question": "Follow-up question?", "answer": "Second answer."},
    ]
    assert SECRET not in raw
    assert "Continue the saved query session" not in raw
    assert "source_digest" in record["binding"]
    assert "grant_digest" in record["binding"]
    assert stat.S_IMODE(records[0].stat().st_mode) == 0o600
    assert stat.S_IMODE(records[0].parent.stat().st_mode) == 0o700


def test_saved_query_session_can_be_listed_and_read_as_a_chat_log(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _authority_grant(
        isolated_store,
        tmp_path,
        monkeypatch,
        permissions=("QUERY", "SESSION_LOG"),
    )

    class Provider:
        def query(self, *_args):
            return "Visible saved answer."

    monkeypatch.setattr(
        "memcommit.commands.query.connect_query_provider",
        lambda _provider: Provider(),
    )
    saved = runner.invoke(
        app,
        [
            "query",
            "construction-details",
            "Visible saved question?",
            "--session",
            "campus-review",
        ],
    )

    listed = runner.invoke(app, ["query", "--sessions"])
    shown = runner.invoke(
        app,
        ["query", "--show-session", "campus-review"],
    )

    assert saved.exit_code == 0, saved.output
    assert listed.exit_code == 0, listed.output
    assert (
        "campus-review · view=construction-details · language=en · "
        "1 turn(s) · revision 1"
    ) in listed.output
    assert shown.exit_code == 0, shown.output
    assert "Query session: campus-review" in shown.output
    assert "Visible saved question?" in shown.output
    assert "Visible saved answer." in shown.output
    assert SECRET not in shown.output


def test_session_log_permission_is_distinct_from_query_permission(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _authority_grant(
        isolated_store,
        tmp_path,
        monkeypatch,
        permissions=("QUERY",),
    )
    calls: list[object] = []

    class Provider:
        def query(self, *_args):
            calls.append(object())
            return "must not run"

    monkeypatch.setattr(
        "memcommit.commands.query.connect_query_provider",
        lambda _provider: Provider(),
    )

    result = runner.invoke(
        app,
        [
            "query",
            "construction-details",
            "Question?",
            "--session",
            "not-authorized",
        ],
    )

    assert result.exit_code == 1
    assert "does not allow session_log access" in result.stderr.lower()
    assert calls == []
    assert not (isolated_store / "query-sessions").exists()


def test_saved_session_is_strictly_stale_after_authority_source_edit(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    authority_store, source_context, source_memory, _grant = _authority_grant(
        isolated_store,
        tmp_path,
        monkeypatch,
        permissions=("QUERY", "SESSION_LOG"),
    )
    calls = 0

    class Provider:
        def query(self, *_args):
            nonlocal calls
            calls += 1
            return "Saved answer."

    monkeypatch.setattr(
        "memcommit.commands.query.connect_query_provider",
        lambda _provider: Provider(),
    )
    first = runner.invoke(
        app,
        [
            "query",
            "construction-details",
            "Initial?",
            "--session",
            "strict-snapshot",
        ],
    )
    assert first.exit_code == 0, first.output
    current = authority_store.load_direct(source_context.name)
    assert isinstance(current.memories[source_memory.uid], Memory)
    current.memories[source_memory.uid].content = "Authority source changed."
    authority_store.save(current)

    second = runner.invoke(
        app,
        [
            "query",
            "construction-details",
            "Follow-up?",
            "--session",
            "strict-snapshot",
        ],
    )

    assert second.exit_code == 1
    assert "is stale" in second.stderr
    assert calls == 1
    record_path = next((isolated_store / "query-sessions").glob("*.json"))
    assert json.loads(record_path.read_text())["revision"] == 1


def test_revocation_during_provider_call_prevents_session_publication(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _store, _context, _memory, grant = _authority_grant(
        isolated_store,
        tmp_path,
        monkeypatch,
        permissions=("QUERY", "SESSION_LOG"),
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
        [
            "query",
            "construction-details",
            "Question?",
            "--session",
            "revoked",
        ],
    )

    assert result.exit_code == 1
    assert "does not exist" in result.stderr
    assert "Answer from a now-revoked view" not in result.output
    assert not (isolated_store / "query-sessions").exists()


def test_revocation_during_one_shot_query_prevents_answer_disclosure(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _store, _context, _memory, grant = _authority_grant(
        isolated_store,
        tmp_path,
        monkeypatch,
        permissions=("QUERY",),
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
    assert "does not exist" in result.stderr
    assert "Answer from a now-revoked view" not in result.output
    assert not (isolated_store / "query-sessions").exists()


def test_authority_query_uses_complete_root_bound_translation_catalog(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    authority_store, source_context, source_memory, _grant = _authority_grant(
        isolated_store,
        tmp_path,
        monkeypatch,
        permissions=("QUERY",),
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
    path = translations / (
        f"{source_context.uid}--{language_digest}--catalog.json"
    )
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
        [
            "query",
            "construction-details",
            "언제 열리나요?",
            "--language",
            "ko",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [
        (
            "construction-details",
            "북쪽 설비 터널은 오후 6시 이후에만 열린다.",
            "언제 열리나요?",
        )
    ]


def test_session_read_rejects_group_readable_storage_directory(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _authority_grant(
        isolated_store,
        tmp_path,
        monkeypatch,
        permissions=("QUERY", "SESSION_LOG"),
    )
    calls = 0

    class Provider:
        def query(self, *_args):
            nonlocal calls
            calls += 1
            return "Answer."

    monkeypatch.setattr(
        "memcommit.commands.query.connect_query_provider",
        lambda _provider: Provider(),
    )
    first = runner.invoke(
        app,
        [
            "query",
            "construction-details",
            "Initial?",
            "--session",
            "private-mode",
        ],
    )
    assert first.exit_code == 0, first.output
    sessions = isolated_store / "query-sessions"
    sessions.chmod(0o750)

    second = runner.invoke(
        app,
        [
            "query",
            "construction-details",
            "Follow-up?",
            "--session",
            "private-mode",
        ],
    )

    assert second.exit_code == 1
    assert "storage permissions are unsafe" in second.stderr
    assert calls == 1


def test_oversized_session_record_is_rejected_before_publication(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _authority_grant(
        isolated_store,
        tmp_path,
        monkeypatch,
        permissions=("QUERY", "SESSION_LOG"),
    )

    class Provider:
        def query(self, *_args):
            return "Provider answer that cannot fit in the bounded record."

    monkeypatch.setattr(
        "memcommit.commands.query.connect_query_provider",
        lambda _provider: Provider(),
    )
    monkeypatch.setattr(query_sessions, "_MAX_SESSION_BYTES", 200)

    result = runner.invoke(
        app,
        [
            "query",
            "construction-details",
            "Question?",
            "--session",
            "bounded",
        ],
    )

    assert result.exit_code == 1
    assert "storage limit" in result.stderr
    assert list((isolated_store / "query-sessions").glob("*.json")) == []
