"""Ephemeral Source projections for one-shot authority-granted Query."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import uuid

from memcommit.core.context import Context, Memory
from memcommit.core.memory_translation import (
    MemoryTranslationCatalog,
    TranslationCatalogError,
)
from memcommit.application.operations.profile.config import (
    GrantContextBinding,
    load_profile_registry,
)
from memcommit.application.context_access.granted_view import GrantedContextView
from memcommit.persistence.store import MemoryStore
from memcommit.persistence.store.context_memory.records import context_record_digest
from memcommit.persistence.store.translation_catalog import (
    decode_translation_catalog_record,
)


_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_LANGUAGE = re.compile(r"[a-z]{2,8}(?:-[a-z0-9]{1,8})*\Z")
_MAX_CATALOG_BYTES = 8 * 1024 * 1024


class GrantedQuerySourceError(RuntimeError):
    """A granted Query Source is invalid, unavailable, or changed."""


def _canonical_json_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_uuid(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise GrantedQuerySourceError(f"Granted Query {field} is invalid.")
    try:
        canonical = str(uuid.UUID(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise GrantedQuerySourceError(f"Granted Query {field} is invalid.") from error
    if canonical != value:
        raise GrantedQuerySourceError(f"Granted Query {field} is invalid.")
    return value


def _language(value: object) -> str:
    if not isinstance(value, str) or _LANGUAGE.fullmatch(value) is None:
        raise GrantedQuerySourceError(
            "Query language must be a normalized lowercase language identifier."
        )
    return value


@dataclass(frozen=True)
class AuthorityQuerySource:
    """Ephemeral provider input derived from an exact grant scope."""

    name: str
    content: str
    digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise GrantedQuerySourceError("Granted Query Source name is invalid.")
        if not isinstance(self.content, str) or not self.content:
            raise GrantedQuerySourceError("Granted Query Source content is empty.")
        if not isinstance(self.digest, str) or _DIGEST.fullmatch(self.digest) is None:
            raise GrantedQuerySourceError("Granted Query Source digest is invalid.")


@dataclass(frozen=True)
class GrantedQuerySourceBinding:
    """Frozen Grant and Source identity used for post-provider revalidation."""

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
        for field, value in (
            ("Grant uid", self.grant_uid),
            ("grantee Profile uid", self.grantee_profile_uid),
            ("authority Profile uid", self.authority_profile_uid),
            ("attachment Context uid", self.attachment_context_uid),
            ("resource Context uid", self.resource_uid),
        ):
            _canonical_uuid(value, field=field)
        if (
            not isinstance(self.grant_revision, int)
            or isinstance(self.grant_revision, bool)
            or self.grant_revision < 1
        ):
            raise GrantedQuerySourceError("Granted Query revision is invalid.")
        for field, value in (
            ("Grant digest", self.grant_digest),
            ("Source digest", self.source_digest),
        ):
            if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
                raise GrantedQuerySourceError(f"Granted Query {field} is invalid.")
        for field, value in (
            ("attachment Context name", self.attachment_context_name),
            ("resource name", self.resource_name),
            ("public name", self.public_name),
            ("requested name", self.requested_name),
        ):
            if not isinstance(value, str) or not value:
                raise GrantedQuerySourceError(f"Granted Query {field} is invalid.")
        _language(self.language)


@dataclass(frozen=True)
class _AuthorityQueryMemory:
    """Process-local authority material; never persist or render this object."""

    context_uid: str
    context_name: str
    memory_uid: str
    content: str


def _strict_json_object(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise GrantedQuerySourceError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_translation_catalog_at_root(
    authority_root: Path,
    context: Context,
    language: str,
) -> MemoryTranslationCatalog:
    """Load one catalog without consulting the active Profile's global root."""

    directory = authority_root / "translation-views"
    if directory.is_symlink() or not directory.is_dir():
        raise GrantedQuerySourceError(
            "Requested authority-view translation is unavailable."
        )
    language_digest = hashlib.sha256(language.encode("utf-8")).hexdigest()
    path = directory / f"{context.uid}--{language_digest}--catalog.json"
    if path.is_symlink() or not path.is_file():
        raise GrantedQuerySourceError(
            "Requested authority-view translation is unavailable."
        )
    try:
        if path.stat().st_size > _MAX_CATALOG_BYTES:
            raise GrantedQuerySourceError(
                "Requested authority-view translation is unavailable."
            )
        with open(path, encoding="utf-8") as file:
            raw = json.load(file, object_pairs_hook=_strict_json_object)
        catalog = decode_translation_catalog_record(raw)
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        TranslationCatalogError,
        ValueError,
    ) as error:
        raise GrantedQuerySourceError(
            "Requested authority-view translation is unavailable."
        ) from error
    if (
        catalog.context_uid != context.uid
        or catalog.context_name != context.name
        or catalog.target_language != language
        or not catalog.covers(context, context_record_digest(context))
    ):
        raise GrantedQuerySourceError(
            "Requested authority-view translation is unavailable."
        )
    return catalog


def _authority_query_bindings(
    view: GrantedContextView,
) -> tuple[GrantContextBinding, ...]:
    """Apply nested QUERY overrides before any authority Memory is opened."""

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
        and grant.attachment_context_name == view.grant.attachment_context_name
        and grant.public_name.startswith(view.grant.public_name + "/")
    )

    # A more-specific public view is an authorization boundary. Parent Query
    # must not absorb its data merely because the parent scope contains it.
    return tuple(
        binding
        for binding in candidate_bindings
        if not any(
            (
                view.grant.public_name + binding.name[len(view.grant.resource_name) :]
                == override.public_name
            )
            or (
                view.grant.public_name + binding.name[len(view.grant.resource_name) :]
            ).startswith(override.public_name + "/")
            for override in overrides
        )
    )


def _load_authority_query_memories(
    view: GrantedContextView,
    *,
    language: str,
) -> tuple[_AuthorityQueryMemory, ...]:
    """Load process-local query material from the exact frozen grant scope."""

    canonical_language = _language(language)
    authority_store = MemoryStore(root=view.authority_root, create=False)
    bindings = _authority_query_bindings(view)
    if not bindings:
        raise GrantedQuerySourceError("Granted authority Context scope is empty.")

    loaded: list[_AuthorityQueryMemory] = []
    for binding in bindings:
        try:
            context = authority_store.load_direct(binding.name)
        except (FileNotFoundError, OSError, ValueError) as error:
            raise GrantedQuerySourceError(
                "Granted authority Context identity changed."
            ) from error
        if context.uid != binding.uid:
            raise GrantedQuerySourceError("Granted authority Context identity changed.")
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
                for item in catalog.effective_entries(
                    context,
                    context_record_digest(context),
                )
            }
            if any(memory.uid not in effective for memory in memories):
                raise GrantedQuerySourceError(
                    "Requested authority-view translation is unavailable."
                )
            selected = tuple(effective[memory.uid] for memory in memories)
        else:
            selected = ()
        for memory, content in zip(memories, selected, strict=True):
            loaded.append(
                _AuthorityQueryMemory(
                    context_uid=context.uid,
                    context_name=context.name,
                    memory_uid=memory.uid,
                    content=content,
                )
            )
    if not loaded:
        raise GrantedQuerySourceError("Granted authority query view has no Memories.")
    return tuple(loaded)


def load_authority_query_source(
    view: GrantedContextView,
    *,
    language: str,
) -> AuthorityQuerySource:
    """Serialize the complete authorized Memory frame for one QUERY View."""

    canonical_language = _language(language)
    selected = _load_authority_query_memories(view, language=canonical_language)

    digest_contexts: list[dict[str, object]] = []
    for memory in selected:
        if not digest_contexts or digest_contexts[-1]["uid"] != memory.context_uid:
            digest_contexts.append(
                {
                    "uid": memory.context_uid,
                    "name": memory.context_name,
                    "memories": [],
                }
            )
        raw_memories = digest_contexts[-1]["memories"]
        assert isinstance(raw_memories, list)
        raw_memories.append({"uid": memory.memory_uid, "content": memory.content})
    digest = _canonical_json_digest(
        {"language": canonical_language, "contexts": digest_contexts}
    )
    return AuthorityQuerySource(
        name=view.requested_name,
        content="\n\n".join(memory.content for memory in selected),
        digest=digest,
    )


def freeze_granted_query_source_binding(
    view: GrantedContextView,
    source: AuthorityQuerySource,
    *,
    language: str,
) -> GrantedQuerySourceBinding:
    """Freeze the complete public and concealed identity of one Source read."""

    grant = view.grant
    return GrantedQuerySourceBinding(
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
        requested_name=source.name,
        language=_language(language),
        source_digest=source.digest,
    )


__all__ = [
    "AuthorityQuerySource",
    "GrantedQuerySourceBinding",
    "GrantedQuerySourceError",
    "freeze_granted_query_source_binding",
    "load_authority_query_source",
]
