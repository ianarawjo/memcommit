"""Durable, visible transcripts for authority-granted query views.

Query sessions belong to the active (grantee) store.  They retain only the
question/answer transcript and opaque freshness bindings; authority source
text and provider-facing prompts are deliberately reconstructed in memory and
never serialized here.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid
from typing import Iterator

from memcommit.context import Context, Memory
from memcommit.profile_config import load_profile_registry
from memcommit.profiles import GrantedContextView
from memcommit.store import MemoryStore
from memcommit.translation_view import (
    TranslationCatalog,
    TranslationViewError,
)


QUERY_SESSION_SCHEMA_VERSION = 1
_SESSION_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_LANGUAGE = re.compile(r"[a-z]{2,8}(?:-[a-z0-9]{1,8})*\Z")
_MAX_TURNS = 200
_MAX_TEXT_CHARS = 200_000
_MAX_SESSION_BYTES = 8 * 1024 * 1024


class QuerySessionError(RuntimeError):
    """A saved query session is invalid, stale, or concurrently changed."""


def _canonical_json_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_query_session_name(value: object) -> str:
    if not isinstance(value, str) or _SESSION_NAME.fullmatch(value) is None:
        raise QuerySessionError(
            "Query session name must be one 1-64 character segment containing "
            "only letters, digits, '.', '_', or '-'."
        )
    return value


def _text(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > _MAX_TEXT_CHARS
    ):
        raise QuerySessionError(
            f"Query session {field} must be non-empty text no longer than "
            f"{_MAX_TEXT_CHARS} characters."
        )
    return value


def _uuid(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise QuerySessionError(f"Query session {field} is invalid.")
    try:
        canonical = str(uuid.UUID(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise QuerySessionError(f"Query session {field} is invalid.") from error
    if canonical != value:
        raise QuerySessionError(f"Query session {field} is invalid.")
    return canonical


def _digest(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise QuerySessionError(f"Query session {field} is invalid.")
    return value


def _language(value: object) -> str:
    if not isinstance(value, str) or _LANGUAGE.fullmatch(value) is None:
        raise QuerySessionError(
            "Query language must be a normalized lowercase language identifier."
        )
    return value


def _exact_dict(
    value: object,
    fields: set[str],
    *,
    label: str,
) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != fields:
        raise QuerySessionError(f"Saved query session {label} is invalid.")
    return value


@dataclass(frozen=True)
class QueryTurn:
    question: str
    answer: str

    def __post_init__(self) -> None:
        _text(self.question, field="question")
        _text(self.answer, field="answer")

    def to_dict(self) -> dict[str, str]:
        return {"question": self.question, "answer": self.answer}

    @classmethod
    def from_dict(cls, value: object) -> "QueryTurn":
        data = _exact_dict(
            value,
            {"question", "answer"},
            label="turn",
        )
        return cls(
            question=_text(data["question"], field="question"),
            answer=_text(data["answer"], field="answer"),
        )


@dataclass(frozen=True)
class QuerySessionBinding:
    """Freshness identity for one exact granted view and source projection."""

    grant_uid: str
    grant_revision: int
    grant_digest: str
    grantee_profile_uid: str
    authority_profile_uid: str
    attachment_context_uid: str
    attachment_context_name: str
    resource_uid: str
    resource_name: str
    public_name: str
    requested_name: str
    language: str
    source_digest: str

    def __post_init__(self) -> None:
        _uuid(self.grant_uid, field="grant uid")
        if (
            not isinstance(self.grant_revision, int)
            or isinstance(self.grant_revision, bool)
            or self.grant_revision < 1
        ):
            raise QuerySessionError("Query session grant revision is invalid.")
        _digest(self.grant_digest, field="grant digest")
        _uuid(self.grantee_profile_uid, field="grantee Profile uid")
        _uuid(self.authority_profile_uid, field="authority Profile uid")
        _uuid(self.attachment_context_uid, field="attachment Context uid")
        _uuid(self.resource_uid, field="resource Context uid")
        for field, value in (
            ("attachment Context name", self.attachment_context_name),
            ("resource name", self.resource_name),
            ("public name", self.public_name),
            ("requested name", self.requested_name),
        ):
            if not isinstance(value, str) or not value:
                raise QuerySessionError(f"Query session {field} is invalid.")
        _language(self.language)
        _digest(self.source_digest, field="source digest")

    def to_dict(self) -> dict[str, object]:
        return {
            "grant_uid": self.grant_uid,
            "grant_revision": self.grant_revision,
            "grant_digest": self.grant_digest,
            "grantee_profile_uid": self.grantee_profile_uid,
            "authority_profile_uid": self.authority_profile_uid,
            "attachment_context_uid": self.attachment_context_uid,
            "attachment_context_name": self.attachment_context_name,
            "resource_uid": self.resource_uid,
            "resource_name": self.resource_name,
            "public_name": self.public_name,
            "requested_name": self.requested_name,
            "language": self.language,
            "source_digest": self.source_digest,
        }

    @classmethod
    def from_dict(cls, value: object) -> "QuerySessionBinding":
        fields = {
            "grant_uid",
            "grant_revision",
            "grant_digest",
            "grantee_profile_uid",
            "authority_profile_uid",
            "attachment_context_uid",
            "attachment_context_name",
            "resource_uid",
            "resource_name",
            "public_name",
            "requested_name",
            "language",
            "source_digest",
        }
        data = _exact_dict(value, fields, label="binding")
        return cls(**data)  # type: ignore[arg-type]


@dataclass(frozen=True)
class QuerySession:
    uid: str
    revision: int
    name: str
    binding: QuerySessionBinding
    turns: tuple[QueryTurn, ...]

    def __post_init__(self) -> None:
        _uuid(self.uid, field="uid")
        if (
            not isinstance(self.revision, int)
            or isinstance(self.revision, bool)
            or self.revision < 0
        ):
            raise QuerySessionError("Query session revision is invalid.")
        validate_query_session_name(self.name)
        if not isinstance(self.binding, QuerySessionBinding):
            raise QuerySessionError("Query session binding is invalid.")
        if (
            not isinstance(self.turns, tuple)
            or len(self.turns) > _MAX_TURNS
            or any(not isinstance(turn, QueryTurn) for turn in self.turns)
        ):
            raise QuerySessionError("Query session turns are invalid.")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": QUERY_SESSION_SCHEMA_VERSION,
            "uid": self.uid,
            "revision": self.revision,
            "name": self.name,
            "binding": self.binding.to_dict(),
            "turns": [turn.to_dict() for turn in self.turns],
        }

    @classmethod
    def from_dict(cls, value: object) -> "QuerySession":
        data = _exact_dict(
            value,
            {"schema_version", "uid", "revision", "name", "binding", "turns"},
            label="record",
        )
        if data["schema_version"] != QUERY_SESSION_SCHEMA_VERSION:
            raise QuerySessionError("Unsupported query session schema version.")
        raw_turns = data["turns"]
        if not isinstance(raw_turns, list) or len(raw_turns) > _MAX_TURNS:
            raise QuerySessionError("Saved query session turns are invalid.")
        return cls(
            uid=_uuid(data["uid"], field="uid"),
            revision=data["revision"],  # type: ignore[arg-type]
            name=validate_query_session_name(data["name"]),
            binding=QuerySessionBinding.from_dict(data["binding"]),
            turns=tuple(QueryTurn.from_dict(turn) for turn in raw_turns),
        )


@dataclass(frozen=True)
class AuthorityQuerySource:
    """Ephemeral provider input derived from an exact grant scope."""

    name: str
    content: str
    digest: str


def _strict_json_object(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise QuerySessionError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_translation_catalog_at_root(
    authority_root: Path,
    context: Context,
    language: str,
) -> TranslationCatalog:
    """Load one catalog without consulting the active Profile's global root."""

    directory = authority_root / "translation-views"
    if directory.is_symlink() or not directory.is_dir():
        raise QuerySessionError(
            "Requested authority-view translation is unavailable."
        )
    language_digest = hashlib.sha256(language.encode("utf-8")).hexdigest()
    path = directory / f"{context.uid}--{language_digest}--catalog.json"
    if path.is_symlink() or not path.is_file():
        raise QuerySessionError(
            "Requested authority-view translation is unavailable."
        )
    try:
        if path.stat().st_size > _MAX_SESSION_BYTES:
            raise QuerySessionError(
                "Requested authority-view translation is unavailable."
            )
        with open(path, encoding="utf-8") as file:
            raw = json.load(file, object_pairs_hook=_strict_json_object)
        catalog = TranslationCatalog.from_dict(raw)
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        TranslationViewError,
        ValueError,
    ) as error:
        raise QuerySessionError(
            "Requested authority-view translation is unavailable."
        ) from error
    if (
        catalog.context_uid != context.uid
        or catalog.context_name != context.name
        or catalog.target_language != language
        or not catalog.covers(context)
    ):
        raise QuerySessionError(
            "Requested authority-view translation is unavailable."
        )
    return catalog


def load_authority_query_source(
    view: GrantedContextView,
    *,
    language: str,
) -> AuthorityQuerySource:
    """Serialize only direct ordinary Memories admitted by the frozen grant."""

    canonical_language = _language(language)
    authority_store = MemoryStore(root=view.authority_root, create=False)
    prefix = view.authority_context_name + "/"
    candidate_bindings = tuple(
        binding
        for binding in view.grant.contexts
        if binding.name == view.authority_context_name
        or binding.name.startswith(prefix)
    )
    registry = load_profile_registry()
    overrides = tuple(
        grant
        for grant in registry.grants
        if grant.uid != view.grant.uid
        and grant.grantee_profile_uid == view.grant.grantee_profile_uid
        and grant.attachment_context_uid == view.grant.attachment_context_uid
        and grant.attachment_context_name
        == view.grant.attachment_context_name
        and grant.public_name.startswith(view.grant.public_name + "/")
    )

    # A more-specific view is an authorization boundary, not merely a second
    # alias. Parent queries must not absorb its data even when the parent
    # grant's frozen authority scope happens to include the same path.
    bindings = tuple(
        binding
        for binding in candidate_bindings
        if not any(
            (
                view.grant.public_name
                + binding.name[len(view.grant.resource_name) :]
                == override.public_name
            )
            or (
                view.grant.public_name
                + binding.name[len(view.grant.resource_name) :]
            ).startswith(override.public_name + "/")
            for override in overrides
        )
    )
    if not bindings:
        raise QuerySessionError("Granted authority Context scope is empty.")

    contents: list[str] = []
    digest_contexts: list[dict[str, object]] = []
    for binding in bindings:
        try:
            context = authority_store.load_direct(binding.name)
        except (FileNotFoundError, OSError, ValueError) as error:
            raise QuerySessionError(
                "Granted authority Context identity changed."
            ) from error
        if context.uid != binding.uid:
            raise QuerySessionError("Granted authority Context identity changed.")
        memories = tuple(
            item for item in context.iter_items() if isinstance(item, Memory)
        )
        if canonical_language == "en":
            selected = tuple(memory.content for memory in memories)
        elif memories:
            catalog = _load_translation_catalog_at_root(
                view.authority_root,
                context,
                canonical_language,
            )
            effective = {
                item.source_uid: item.translated_content
                for item in catalog.effective_entries(context)
            }
            if any(memory.uid not in effective for memory in memories):
                raise QuerySessionError(
                    "Requested authority-view translation is unavailable."
                )
            selected = tuple(effective[memory.uid] for memory in memories)
        else:
            selected = ()
        contents.extend(selected)
        digest_contexts.append(
            {
                "uid": context.uid,
                "name": context.name,
                "memories": [
                    {"uid": memory.uid, "content": content}
                    for memory, content in zip(memories, selected, strict=True)
                ],
            }
        )
    if not contents:
        raise QuerySessionError("Granted authority query view has no Memories.")
    digest = _canonical_json_digest(
        {"language": canonical_language, "contexts": digest_contexts}
    )
    return AuthorityQuerySource(
        name=view.requested_name,
        content="\n\n".join(contents),
        digest=digest,
    )


def query_session_binding(
    view: GrantedContextView,
    source: AuthorityQuerySource,
    *,
    language: str,
) -> QuerySessionBinding:
    grant = view.grant
    return QuerySessionBinding(
        grant_uid=grant.uid,
        grant_revision=grant.revision,
        grant_digest=_canonical_json_digest(grant.to_dict()),
        grantee_profile_uid=grant.grantee_profile_uid,
        authority_profile_uid=grant.authority_profile_uid,
        attachment_context_uid=grant.attachment_context_uid,
        attachment_context_name=grant.attachment_context_name,
        resource_uid=grant.resource_uid,
        resource_name=grant.resource_name,
        public_name=grant.public_name,
        requested_name=view.requested_name,
        language=_language(language),
        source_digest=source.digest,
    )


def render_session_question(
    turns: tuple[QueryTurn, ...],
    question: str,
) -> str:
    """Reconstruct provider dialogue from the same Q/A visible to the user."""

    current = _text(question, field="question")
    if not turns:
        return current
    sections = [
        "Continue the saved query session using these prior visible turns."
    ]
    for index, turn in enumerate(turns, start=1):
        sections.extend(
            (
                f"[Turn {index} question]\n{turn.question}",
                f"[Turn {index} answer]\n{turn.answer}",
            )
        )
    sections.append(f"[Current question]\n{current}")
    return "\n\n".join(sections)


def query_session_record_digest(session: QuerySession) -> str:
    return _canonical_json_digest(session.to_dict())


class QuerySessionStore:
    """CAS persistence rooted in the active grantee MemoryStore."""

    def __init__(self, root: Path):
        self.root = Path(root).absolute()
        self.directory = self.root / "query-sessions"
        self.locks = self.directory / ".locks"

    @staticmethod
    def _filename(name: str) -> str:
        canonical = validate_query_session_name(name)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest() + ".json"

    def _path(self, name: str) -> Path:
        return self.directory / self._filename(name)

    def _check_directory(self, *, create: bool) -> None:
        if self.directory.is_symlink():
            raise QuerySessionError("Query session storage is unsafe.")
        created = False
        if self.directory.exists():
            if not self.directory.is_dir():
                raise QuerySessionError("Query session storage is invalid.")
            if stat.S_IMODE(self.directory.stat().st_mode) & 0o077:
                raise QuerySessionError(
                    "Query session storage permissions are unsafe."
                )
        elif create:
            self.directory.mkdir(mode=0o700, parents=False)
            created = True
        else:
            return
        if created:
            os.chmod(self.directory, 0o700)

    def _read(self, name: str) -> QuerySession | None:
        self._check_directory(create=False)
        path = self._path(name)
        if path.is_symlink():
            raise QuerySessionError("Query session storage is unsafe.")
        if not path.exists():
            return None
        if not path.is_file() or path.stat().st_size > _MAX_SESSION_BYTES:
            raise QuerySessionError("Saved query session is invalid.")
        if stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise QuerySessionError("Saved query session permissions are unsafe.")
        try:
            with open(path, encoding="utf-8") as file:
                raw = json.load(file, object_pairs_hook=_strict_json_object)
            session = QuerySession.from_dict(raw)
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            QuerySessionError,
            ValueError,
        ) as error:
            raise QuerySessionError("Saved query session is invalid.") from error
        if session.name != name or path != self._path(session.name):
            raise QuerySessionError("Saved query session identity is invalid.")
        return session

    def load(self, name: str) -> QuerySession:
        """Load one task-owned transcript without reopening authority data."""

        canonical = validate_query_session_name(name)
        session = self._read(canonical)
        if session is None:
            raise QuerySessionError(
                f"Saved query session {canonical!r} does not exist."
            )
        return session

    def list_sessions(self) -> tuple[QuerySession, ...]:
        """List validated task-owned transcripts in stable name order."""

        self._check_directory(create=False)
        if not self.directory.exists():
            return ()
        sessions: list[QuerySession] = []
        for path in sorted(self.directory.glob("*.json")):
            if path.is_symlink() or not path.is_file():
                raise QuerySessionError("Query session storage is unsafe.")
            if path.stat().st_size > _MAX_SESSION_BYTES:
                raise QuerySessionError("Saved query session is invalid.")
            if stat.S_IMODE(path.stat().st_mode) & 0o077:
                raise QuerySessionError("Saved query session permissions are unsafe.")
            try:
                with open(path, encoding="utf-8") as file:
                    raw = json.load(file, object_pairs_hook=_strict_json_object)
                session = QuerySession.from_dict(raw)
            except (
                OSError,
                UnicodeError,
                json.JSONDecodeError,
                QuerySessionError,
                ValueError,
            ) as error:
                raise QuerySessionError("Saved query session is invalid.") from error
            if path != self._path(session.name):
                raise QuerySessionError("Saved query session identity is invalid.")
            sessions.append(session)
        if len({session.name for session in sessions}) != len(sessions):
            raise QuerySessionError("Saved query session identity is duplicated.")
        return tuple(sorted(sessions, key=lambda session: session.name))

    def load_or_start(
        self,
        name: str,
        binding: QuerySessionBinding,
    ) -> tuple[QuerySession, str | None]:
        canonical = validate_query_session_name(name)
        session = self._read(canonical)
        if session is None:
            return (
                QuerySession(
                    uid=str(uuid.uuid4()),
                    revision=0,
                    name=canonical,
                    binding=binding,
                    turns=(),
                ),
                None,
            )
        if session.binding != binding:
            raise QuerySessionError(
                f"Saved query session {canonical!r} is stale or belongs to "
                "another granted view. Start a new session name."
            )
        return session, query_session_record_digest(session)

    @contextmanager
    def _lock(self, name: str) -> Iterator[None]:
        self._check_directory(create=True)
        if self.locks.is_symlink():
            raise QuerySessionError("Query session lock storage is unsafe.")
        if self.locks.exists() and not self.locks.is_dir():
            raise QuerySessionError("Query session lock storage is invalid.")
        if self.locks.exists():
            if stat.S_IMODE(self.locks.stat().st_mode) & 0o077:
                raise QuerySessionError(
                    "Query session lock storage permissions are unsafe."
                )
        else:
            self.locks.mkdir(mode=0o700)
            os.chmod(self.locks, 0o700)
        lock_path = self.locks / (self._filename(name) + ".lock")
        if lock_path.is_symlink():
            raise QuerySessionError("Query session lock storage is unsafe.")
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags, 0o600)
        os.fchmod(descriptor, 0o600)
        try:
            with os.fdopen(descriptor, "a+", encoding="utf-8") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except Exception:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise

    def append_turn(
        self,
        session: QuerySession,
        *,
        expected_record_digest: str | None,
        question: str,
        answer: str,
    ) -> QuerySession:
        turn = QueryTurn(
            question=_text(question, field="question"),
            answer=_text(answer, field="answer"),
        )
        if len(session.turns) >= _MAX_TURNS:
            raise QuerySessionError("Query session has reached its turn limit.")
        if expected_record_digest is not None:
            _digest(expected_record_digest, field="expected record digest")
        store = MemoryStore(root=self.root, create=False)
        with store.profile_write_guard():
            with self._lock(session.name):
                current = self._read(session.name)
                current_digest = (
                    None
                    if current is None
                    else query_session_record_digest(current)
                )
                if current_digest != expected_record_digest:
                    raise QuerySessionError(
                        "Query session changed while the provider was "
                        "answering; the new turn was not saved."
                    )
                if current is not None and current != session:
                    raise QuerySessionError(
                        "Query session changed while the provider was "
                        "answering; the new turn was not saved."
                    )
                saved = QuerySession(
                    uid=session.uid,
                    revision=session.revision + 1,
                    name=session.name,
                    binding=session.binding,
                    turns=(*session.turns, turn),
                )
                self._write(saved)
                return saved

    def _write(self, session: QuerySession) -> None:
        path = self._path(session.name)
        payload = (
            json.dumps(
                session.to_dict(),
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
        if len(payload.encode("utf-8")) > _MAX_SESSION_BYTES:
            raise QuerySessionError(
                "Query session has reached its storage limit; the new turn "
                "was not saved."
            )
        temporary = self.directory / f".{path.name}.write-{uuid.uuid4().hex}"
        descriptor: int | None = None
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(temporary, flags, 0o600)
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                descriptor = None
                file.write(payload)
                file.flush()
                os.fsync(file.fileno())
            if path.is_symlink() or (path.exists() and not path.is_file()):
                raise QuerySessionError("Query session storage is unsafe.")
            os.replace(temporary, path)
            os.chmod(path, 0o600)
            directory_fd = os.open(self.directory, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if descriptor is not None:
                os.close(descriptor)
            if temporary.exists() and not temporary.is_symlink():
                temporary.unlink()
