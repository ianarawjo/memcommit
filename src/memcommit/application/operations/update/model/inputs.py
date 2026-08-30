"""Frozen Update Source/Target bindings and candidate collection."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from memcommit.application.operations.profile.config import (
    ProfileConfigError,
    canonical_grant_permissions,
)
from memcommit.application.capabilities.semantic.disclosure import (
    SemanticDisclosureError,
    require_semantic_disclosure_authority,
)
from memcommit.core.context import Context, Memory, MemoryRef
from memcommit.application.capabilities.semantic.memory_scope import (
    MemoryScopeError,
    resolve_memory_scope,
)

from .changes import (
    SourceReference,
    UpdateError,
    _is_sha256,
    _require_exact_keys,
    _require_string,
    _require_uuid,
    _sha256_json,
    _sha256_text,
)
from .receipts import ContextFingerprint


INLINE_UPDATE_CONTEXT_NAME = "INLINE UPDATE MEMORY"
_INLINE_UPDATE_NAMESPACE = uuid.UUID("a9e29d5e-4768-4a33-9f9b-77b6020b2d72")


def inline_update_context(content: str) -> Context:
    """Build the stable process-local Source frame for one exact text value.

    Deterministic identities let an exact repeated command resume the same
    staged session without publishing a synthetic Context to the Store.
    """

    if not isinstance(content, str) or not content.strip():
        raise UpdateError("Inline Update Memory content must be nonblank text.")
    context_uid = str(uuid.uuid5(_INLINE_UPDATE_NAMESPACE, "context\0" + content))
    memory_uid = str(uuid.uuid5(_INLINE_UPDATE_NAMESPACE, "memory\0" + content))
    context = Context(uid=context_uid, name=INLINE_UPDATE_CONTEXT_NAME)
    context.add(Memory(uid=memory_uid, content=content))
    return context
@dataclass(frozen=True)
class GrantedUpdateTarget:
    """Frozen control-plane identity for one granted update target."""

    public_name: str
    grantee_profile_uid: str
    authority_profile_uid: str
    attachment_context_uid: str
    attachment_context_name: str
    grant_uid: str
    grant_revision: int
    grant_digest: str
    resource_uid: str
    resource_name: str
    authority_context_name: str
    permissions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "GRANTED_CONTEXT",
            "public_name": self.public_name,
            "grantee_profile_uid": self.grantee_profile_uid,
            "authority_profile_uid": self.authority_profile_uid,
            "attachment": {
                "uid": self.attachment_context_uid,
                "name": self.attachment_context_name,
            },
            "grant": {
                "uid": self.grant_uid,
                "revision": self.grant_revision,
                "digest": self.grant_digest,
                "permissions": list(self.permissions),
            },
            "resource": {
                "uid": self.resource_uid,
                "name": self.resource_name,
            },
            "authority_context_name": self.authority_context_name,
        }

    @classmethod
    def from_dict(cls, value: object) -> GrantedUpdateTarget:
        data = _require_exact_keys(
            value,
            {
                "kind",
                "public_name",
                "grantee_profile_uid",
                "authority_profile_uid",
                "attachment",
                "grant",
                "resource",
                "authority_context_name",
            },
            "granted update target",
        )
        if data["kind"] != "GRANTED_CONTEXT":
            raise ValueError("Invalid granted update target kind.")
        attachment = _require_exact_keys(
            data["attachment"],
            {"uid", "name"},
            "granted update attachment",
        )
        grant = _require_exact_keys(
            data["grant"],
            {"uid", "revision", "digest", "permissions"},
            "granted update grant",
        )
        resource = _require_exact_keys(
            data["resource"],
            {"uid", "name"},
            "granted update resource",
        )
        revision = grant["revision"]
        permissions = grant["permissions"]
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            raise ValueError("Invalid granted update grant revision.")
        if (
            not isinstance(permissions, list)
            or not permissions
            or any(not isinstance(item, str) or not item for item in permissions)
            or len(set(permissions)) != len(permissions)
        ):
            raise ValueError("Invalid granted update permissions.")
        try:
            canonical_permissions = canonical_grant_permissions(permissions)
        except ProfileConfigError as error:
            raise ValueError("Invalid granted update permissions.") from error
        if tuple(permissions) != canonical_permissions:
            raise ValueError("Invalid granted update permission order.")
        if not _is_sha256(grant["digest"]):
            raise ValueError("Invalid granted update grant digest.")
        return cls(
            public_name=_require_string(
                data["public_name"],
                "granted update public name",
            ),
            grantee_profile_uid=_require_uuid(
                data["grantee_profile_uid"],
                "granted update grantee Profile uid",
            ),
            authority_profile_uid=_require_uuid(
                data["authority_profile_uid"],
                "granted update authority Profile uid",
            ),
            attachment_context_uid=_require_string(
                attachment["uid"],
                "granted update attachment Context uid",
            ),
            attachment_context_name=_require_string(
                attachment["name"],
                "granted update attachment Context name",
            ),
            grant_uid=_require_uuid(
                grant["uid"],
                "granted update grant uid",
            ),
            grant_revision=revision,
            grant_digest=grant["digest"],
            resource_uid=_require_string(
                resource["uid"],
                "granted update resource uid",
            ),
            resource_name=_require_string(
                resource["name"],
                "granted update resource name",
            ),
            authority_context_name=_require_string(
                data["authority_context_name"],
                "granted update authority Context name",
            ),
            permissions=canonical_permissions,
        )


def granted_target_digest(value: object) -> str:
    """Digest one validated registry grant record for a saved target binding."""

    return _sha256_json(value)
@dataclass(frozen=True)
class SourceCandidate:
    candidate_id: str
    context_uid: str
    context_name: str
    memory_uid: str
    content: str

    @property
    def uid(self) -> str:
        return self.memory_uid

    @property
    def reference(self) -> SourceReference:
        return SourceReference(
            context_uid=self.context_uid,
            context_name=self.context_name,
            memory_uid=self.memory_uid,
            content_digest=_sha256_text(self.content),
        )


@dataclass(frozen=True)
class TargetContextCandidate:
    candidate_id: str
    context_uid: str
    context_name: str


@dataclass(frozen=True)
class TargetMemoryCandidate:
    candidate_id: str
    context_id: str
    context_uid: str
    context_name: str
    memory_uid: str
    content: str

    @property
    def uid(self) -> str:
        return self.memory_uid


@dataclass(frozen=True)
class UpdateInputs:
    source_candidates: tuple[SourceCandidate, ...]
    target_contexts: tuple[TargetContextCandidate, ...]
    target_memories: tuple[TargetMemoryCandidate, ...]
    source_digest: str
    target_digest: str
    source_contexts: tuple[ContextFingerprint, ...]
    target_context_fingerprints: tuple[ContextFingerprint, ...]
    source_context_only: tuple[SourceCandidate, ...] = ()
    target_context_only: tuple[TargetMemoryCandidate, ...] = ()
    source_memory_uid: str | None = None
    target_memory_uid: str | None = None


def _walk_contexts(root: Context) -> list[Context]:
    contexts: list[Context] = []
    visited: set[str] = set()

    def visit(context: Context) -> None:
        if context.uid in visited:
            return
        visited.add(context.uid)
        contexts.append(context)
        for item in context.iter_items():
            if isinstance(item, Context):
                visit(item)

    visit(root)
    return contexts


def _fingerprint_contexts(
    contexts: list[Context],
) -> tuple[ContextFingerprint, ...]:
    return tuple(
        ContextFingerprint(
            uid=context.uid,
            name=context.name,
            digest=_sha256_json(context.to_dict()),
        )
        for context in contexts
    )


def _inline_update_source_digest(context: Context) -> str:
    """Return the same Source digest used by ``collect_update_inputs``."""

    return _sha256_json(
        [
            {
                "context_uid": context.uid,
                "context_name": context.name,
                "memory_uid": memory.uid,
                "content": memory.content,
            }
            for memory in context.memories.values()
        ]
    )


def collect_update_inputs(
    source: Context,
    target: Context,
    *,
    source_memory_selector: str | None = None,
    target_memory_selector: str | None = None,
) -> UpdateInputs:
    """Collect readable source facts and directly writable target Memories."""
    try:
        require_semantic_disclosure_authority(
            (source, target),
            operation="Update",
        )
    except SemanticDisclosureError as error:
        raise UpdateError(str(error)) from error
    source_contexts = _walk_contexts(source)
    target_contexts = _walk_contexts(target)
    overlap = {context.uid for context in source_contexts} & {
        context.uid for context in target_contexts
    }
    if overlap:
        raise UpdateError(
            "Source and target Context graphs overlap; update requires "
            "independent Contexts."
        )

    source_candidates: list[SourceCandidate] = []
    seen_sources: set[tuple[str, str]] = set()
    for context in source_contexts:
        for item in context.iter_items():
            if isinstance(item, Memory):
                identity = (context.uid, item.uid)
                source_uid = context.uid
                source_name = context.name
                memory_uid = item.uid
                content = item.content
            elif isinstance(item, MemoryRef) and item.target is not None:
                identity = (
                    item.target_context_uid,
                    item.target_memory_uid,
                )
                source_uid = item.target_context_uid
                source_name = item.target_context_name
                memory_uid = item.target_memory_uid
                content = item.target.content
            else:
                continue
            if identity in seen_sources:
                continue
            seen_sources.add(identity)
            source_candidates.append(
                SourceCandidate(
                    candidate_id=f"s{len(source_candidates) + 1:06d}",
                    context_uid=source_uid,
                    context_name=source_name,
                    memory_uid=memory_uid,
                    content=content,
                )
            )

    target_context_candidates = tuple(
        TargetContextCandidate(
            candidate_id=f"k{index:06d}",
            context_uid=context.uid,
            context_name=context.name,
        )
        for index, context in enumerate(target_contexts, 1)
    )
    context_id_by_uid = {
        candidate.context_uid: candidate.candidate_id
        for candidate in target_context_candidates
    }
    target_memories: list[TargetMemoryCandidate] = []
    for context in target_contexts:
        for item in context.iter_items():
            if not isinstance(item, Memory):
                continue
            target_memories.append(
                TargetMemoryCandidate(
                    candidate_id=f"t{len(target_memories) + 1:06d}",
                    context_id=context_id_by_uid[context.uid],
                    context_uid=context.uid,
                    context_name=context.name,
                    memory_uid=item.uid,
                    content=item.content,
                )
            )

    source_payload = [
        {
            "context_uid": candidate.context_uid,
            "context_name": candidate.context_name,
            "memory_uid": candidate.memory_uid,
            "content": candidate.content,
        }
        for candidate in source_candidates
    ]
    target_payload = {
        "contexts": [
            {
                "context_uid": candidate.context_uid,
                "context_name": candidate.context_name,
            }
            for candidate in target_context_candidates
        ],
        "memories": [
            {
                "context_uid": candidate.context_uid,
                "memory_uid": candidate.memory_uid,
                "content": candidate.content,
            }
            for candidate in target_memories
        ],
    }
    try:
        source_scope = resolve_memory_scope(
            source_candidates,
            source_memory_selector,
            label="Source Memory",
        )
        target_scope = resolve_memory_scope(
            target_memories,
            target_memory_selector,
            label="Target Memory",
        )
    except MemoryScopeError as error:
        raise UpdateError(str(error)) from error
    return UpdateInputs(
        source_candidates=source_scope.actionable,
        # A focused target is an exact existing Memory operation. Its owner is
        # not exposed as an ADD target, preventing a sibling result from
        # escaping the selected Memory scope.
        target_contexts=(
            () if target_scope.selected_uid is not None else target_context_candidates
        ),
        target_memories=target_scope.actionable,
        source_digest=_sha256_json(source_payload),
        target_digest=_sha256_json(target_payload),
        source_contexts=_fingerprint_contexts(source_contexts),
        target_context_fingerprints=_fingerprint_contexts(target_contexts),
        source_context_only=source_scope.context_only,
        target_context_only=target_scope.context_only,
        source_memory_uid=source_scope.selected_uid,
        target_memory_uid=target_scope.selected_uid,
    )
