"""Frozen Meld Source snapshots, identities, and shared value primitives."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, replace
from typing import Literal

from memcommit.application.capabilities.memory_issue_analysis.peer_relations.model import (
    MEMORY_RELATION_RULESET_VERSION,
    MemoryRelationAnalysis,
    memory_relation_canonical_digest,
)
from memcommit.application.operations.semantic_updates.foundation.update.model import ContextFingerprint
from memcommit.application.capabilities.semantic.disclosure import (
    SemanticDisclosureError,
    require_semantic_disclosure_authority,
)
from memcommit.core.context import Context, Memory, QueryContextRef
from memcommit.application.capabilities.semantic.memory_scope import (
    MemoryScopeError,
    resolve_memory_scope,
)
from memcommit.persistence.store import context_record_digest


MELD_SCHEMA_VERSION = 3


MELD_GRANTED_SCHEMA_VERSION = 4


MELD_OWNER_AWARE_SCHEMA_VERSION = 5


MELD_DIRECTIONAL_PRESERVATION_SCHEMA_VERSION = 6


MELD_DIRECTIONAL_RELATION_SCHEMA_VERSION = 7


MELD_MEMORY_FOCUS_SCHEMA_VERSION = 8


MELD_INLINE_MEMORY_SCHEMA_VERSION = 9


MELD_RELATION_ANALYSIS_SCHEMA_VERSION = 2


MELD_LEGACY_SCHEMA_VERSION = 1


MELD_TEXT_LIMIT = 20_000


MELD_NAME_LIMIT = 500


MELD_ID_LIMIT = 240


INLINE_MELD_CONTEXT_NAME = "INLINE MEMORY"


MeldMode = Literal["DIRECTIONAL", "SYMMETRIC"]


MeldRole = Literal["INCOMING", "BASELINE", "PEER"]


MeldState = Literal[
    "PENDING_ANALYSIS",
    "AWAITING_REPLY",
    "READY_TO_APPLY",
    "KEPT_REVIEW_ONLY",
    "APPLIED",
]


MeldRevision = Literal[
    "INITIAL",
    "CONFIRM",
    "EXTEND",
    "CORRECT",
    "RETRACT",
]


MeldTurnScope = Literal["ISSUE", "REMAINING", "ALL"]


MeldRelationKind = Literal[
    "EQUIVALENT",
    "COMPATIBLE",
    "SCOPED",
    "CONFLICT",
    "DISTINCT",
    "UNCLEAR",
]


MeldRelationStatus = Literal["RESOLVED", "UNRESOLVED"]


MeldIssuePriority = Literal["REQUIRED", "HELPFUL"]


MeldDisposition = Literal[
    "COALESCE",
    "PRESERVE",
    "SYNTHESIZE",
    "USER_ADD",
]


MeldProposalOperation = Literal["ADD", "EDIT"]


_MODES = {"DIRECTIONAL", "SYMMETRIC"}


_ROLES = {"INCOMING", "BASELINE", "PEER"}


_STATES = {
    "PENDING_ANALYSIS",
    "AWAITING_REPLY",
    "READY_TO_APPLY",
    "KEPT_REVIEW_ONLY",
    "APPLIED",
}


_REVISIONS = {"INITIAL", "CONFIRM", "EXTEND", "CORRECT", "RETRACT"}


_SCOPES = {"ISSUE", "REMAINING", "ALL"}


_RELATIONS = {
    "EQUIVALENT",
    "COMPATIBLE",
    "SCOPED",
    "CONFLICT",
    "DISTINCT",
    "UNCLEAR",
}


_RELATION_STATUSES = {"RESOLVED", "UNRESOLVED"}


_PRIORITIES = {"REQUIRED", "HELPFUL"}


_DISPOSITIONS = {"COALESCE", "PRESERVE", "SYNTHESIZE", "USER_ADD"}


_OPERATIONS = {"ADD", "EDIT"}


class MeldError(ValueError):
    """Invalid, stale, or internally inconsistent meld state."""


class MeldRepairableAssessmentError(MeldError):
    """A decoded assessment violates a provider-repairable result invariant."""


def _exact_dict(
    value: object,
    keys: set[str],
    label: str,
) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise MeldError(f"Invalid {label}.")
    return value


def _array(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise MeldError(f"Invalid {label}.")
    return value


def _string(
    value: object,
    label: str,
    *,
    empty: bool = False,
    limit: int = MELD_TEXT_LIMIT,
) -> str:
    if (
        not isinstance(value, str)
        or (not empty and not value.strip())
        or len(value) > limit
    ):
        raise MeldError(f"Invalid {label}.")
    return value


def _identifier(value: object, label: str) -> str:
    return _string(value, label, limit=MELD_ID_LIMIT)


def _canonical_uuid(value: object, label: str) -> str:
    text = _string(value, label, limit=36)
    try:
        canonical = str(uuid.UUID(text))
    except ValueError as error:
        raise MeldError(f"Invalid {label}.") from error
    if canonical != text:
        raise MeldError(f"Invalid {label}.")
    return text


def _digest(value: object, label: str) -> str:
    text = _string(value, label, limit=64)
    if len(text) != 64 or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise MeldError(f"Invalid {label}.")
    return text


def _literal(value: object, allowed: set[str], label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise MeldError(f"Invalid {label}.")
    return value


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MeldError(f"Invalid {label}.")
    return value


def _unique_identifiers(
    value: object,
    label: str,
    *,
    empty: bool = False,
    uuids: bool = False,
) -> tuple[str, ...]:
    values = _array(value, label)
    if not empty and not values:
        raise MeldError(f"Invalid {label}.")
    parser = _canonical_uuid if uuids else _identifier
    result = tuple(parser(item, label) for item in values)
    if len(result) != len(set(result)):
        raise MeldError(f"Duplicate {label}.")
    return result


def meld_canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class MeldMemory:
    uid: str
    content: str
    position: int
    content_digest: str
    owner_context_uid: str | None = None
    owner_context_name: str | None = None

    @classmethod
    def create(
        cls,
        memory: Memory,
        position: int,
        *,
        owner: Context | None = None,
    ) -> "MeldMemory":
        value: dict[str, object] = {
                "uid": memory.uid,
                "content": memory.content,
                "position": position,
                "content_digest": hashlib.sha256(
                    memory.content.encode("utf-8")
                ).hexdigest(),
            }
        if owner is not None:
            value["owner_context"] = {"uid": owner.uid, "name": owner.name}
        return cls.from_dict(value)

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "uid": self.uid,
            "content": self.content,
            "position": self.position,
            "content_digest": self.content_digest,
        }
        if self.owner_context_uid is not None:
            result["owner_context"] = {
                "uid": self.owner_context_uid,
                "name": self.owner_context_name,
            }
        return result

    @classmethod
    def from_dict(cls, value: object) -> "MeldMemory":
        keys = {"uid", "content", "position", "content_digest"}
        if isinstance(value, dict) and "owner_context" in value:
            keys.add("owner_context")
        data = _exact_dict(value, keys, "meld Memory")
        owner_uid = None
        owner_name = None
        if "owner_context" in data:
            owner = _exact_dict(
                data["owner_context"],
                {"uid", "name"},
                "meld Memory owner",
            )
            owner_uid = _canonical_uuid(owner["uid"], "meld Memory owner Context uid")
            owner_name = _string(
                owner["name"],
                "meld Memory owner Context name",
                limit=MELD_NAME_LIMIT,
            )
        result = cls(
            uid=_canonical_uuid(data["uid"], "meld Memory uid"),
            content=_string(data["content"], "meld Memory content"),
            position=_integer(data["position"], "meld Memory position"),
            content_digest=_digest(
                data["content_digest"],
                "meld Memory content digest",
            ),
            owner_context_uid=owner_uid,
            owner_context_name=owner_name,
        )
        if (
            result.content_digest
            != hashlib.sha256(result.content.encode("utf-8")).hexdigest()
        ):
            raise MeldError("Meld Memory content digest does not match.")
        return result


@dataclass(frozen=True)
class MeldFrame:
    uid: str
    context_uid: str
    context_name: str
    context_digest: str
    role: MeldRole
    memories: tuple[MeldMemory, ...]
    include_descendants: bool | None = None
    contexts: tuple[ContextFingerprint, ...] | None = None
    context_evidence: tuple[MeldMemory, ...] = ()
    selected_memory_uid: str | None = None

    @classmethod
    def from_context(
        cls,
        ctx: Context,
        *,
        role: MeldRole,
        include_descendants: bool | None = None,
        owner_aware: bool = False,
        memory_selector: str | None = None,
    ) -> "MeldFrame":
        if not isinstance(ctx, Context):
            raise MeldError("Meld source must be a Context.")
        try:
            require_semantic_disclosure_authority(
                (ctx,),
                operation="Meld",
                follow_contexts=owner_aware and include_descendants is True,
            )
        except SemanticDisclosureError as error:
            raise MeldError(str(error)) from error
        contexts: list[Context] = []
        seen_contexts: set[str] = set()

        def visit(context: Context) -> None:
            if context.uid in seen_contexts:
                return
            seen_contexts.add(context.uid)
            contexts.append(context)
            if not (owner_aware and include_descendants is True):
                return
            for item in context.iter_items():
                if isinstance(item, Context):
                    visit(item)

        visit(ctx)
        non_memories = [
            uid
            for context in contexts
            for uid, item in context.iter_entries()
            if not isinstance(
                item,
                # Query-only routes are visible navigation metadata, not
                # ordinary readable evidence or writable target owners.
                (Memory, Context, QueryContextRef)
                if owner_aware
                else (Memory, Context),
            )
        ]
        if not owner_aware:
            non_memories.extend(
                uid
                for uid, item in ctx.iter_entries()
                if isinstance(item, Context)
            )
        if non_memories:
            raise MeldError(
                "Context-to-Context meld version 1 supports direct owned "
                "Memories only; unsupported direct item(s): "
                + ", ".join(uid[:8] for uid in non_memories)
                + "."
            )
        owned_memories = [
            (context, item)
            for context in (contexts if owner_aware else [ctx])
            for item in context.iter_items()
            if isinstance(item, Memory)
        ]
        complete_memories = tuple(
            MeldMemory.create(
                item,
                position,
                owner=context if owner_aware else None,
            )
            for position, (context, item) in enumerate(owned_memories)
        )
        if not complete_memories:
            raise MeldError(f"Source Context '{ctx.name}' has no direct Memories.")
        try:
            scope = resolve_memory_scope(
                complete_memories,
                memory_selector,
                label=f"{role} Memory",
            )
        except MemoryScopeError as error:
            raise MeldError(str(error)) from error
        memories = tuple(
            replace(memory, position=position)
            for position, memory in enumerate(scope.actionable)
        )
        fingerprints = (
            tuple(
                ContextFingerprint(
                    uid=context.uid,
                    name=context.name,
                    digest=context_record_digest(context),
                )
                for context in contexts
            )
            if owner_aware
            else None
        )
        value: dict[str, object] = {
                "uid": str(uuid.uuid4()),
                "context_uid": ctx.uid,
                "context_name": ctx.name,
                "context_digest": (
                    meld_canonical_digest(
                        [fingerprint.to_dict() for fingerprint in fingerprints]
                    )
                    if fingerprints is not None
                    else context_record_digest(ctx)
                ),
                "role": role,
                "memories": [memory.to_dict() for memory in memories],
            }
        if include_descendants is not None:
            value["include_descendants"] = include_descendants
        if fingerprints is not None:
            value["contexts"] = [item.to_dict() for item in fingerprints]
        if scope.context_only:
            value["context_evidence"] = [
                item.to_dict() for item in scope.context_only
            ]
        if scope.selected_uid is not None:
            # Persist selection identity independently of neighbor count: a
            # one-Memory Context is still narrower than an unrestricted target.
            value["selected_memory_uid"] = scope.selected_uid
        return cls.from_dict(value)

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "uid": self.uid,
            "context_uid": self.context_uid,
            "context_name": self.context_name,
            "context_digest": self.context_digest,
            "role": self.role,
            "memories": [memory.to_dict() for memory in self.memories],
        }
        if self.include_descendants is not None:
            result["include_descendants"] = self.include_descendants
        if self.contexts is not None:
            result["contexts"] = [context.to_dict() for context in self.contexts]
        if self.context_evidence:
            result["context_evidence"] = [
                memory.to_dict() for memory in self.context_evidence
            ]
        if self.selected_memory_uid is not None:
            result["selected_memory_uid"] = self.selected_memory_uid
        return result

    @classmethod
    def from_dict(cls, value: object) -> "MeldFrame":
        keys = {
                "uid",
                "context_uid",
                "context_name",
                "context_digest",
                "role",
                "memories",
            }
        if isinstance(value, dict) and "include_descendants" in value:
            keys.add("include_descendants")
        if isinstance(value, dict) and "contexts" in value:
            keys.add("contexts")
        if isinstance(value, dict) and "context_evidence" in value:
            keys.add("context_evidence")
        if isinstance(value, dict) and "selected_memory_uid" in value:
            keys.add("selected_memory_uid")
        data = _exact_dict(value, keys, "meld frame")
        memories = tuple(
            MeldMemory.from_dict(item)
            for item in _array(data["memories"], "meld frame Memories")
        )
        if (
            not memories
            or len({memory.uid for memory in memories}) != len(memories)
            or [memory.position for memory in memories] != list(range(len(memories)))
        ):
            raise MeldError("Invalid meld frame Memory order.")
        include_descendants = data.get("include_descendants")
        if include_descendants is not None and type(include_descendants) is not bool:
            raise MeldError("Invalid meld frame descendant scope.")
        contexts = None
        if "contexts" in data:
            try:
                contexts = tuple(
                    ContextFingerprint.from_dict(item)
                    for item in _array(data["contexts"], "meld frame Contexts")
                )
            except ValueError as error:
                raise MeldError("Invalid meld frame Context fingerprints.") from error
            identities = [(context.uid, context.name) for context in contexts]
            if (
                not contexts
                or len(identities) != len(set(identities))
                or len({context.uid for context in contexts}) != len(contexts)
                or len({context.name for context in contexts}) != len(contexts)
                or contexts[0].uid != data["context_uid"]
                or contexts[0].name != data["context_name"]
                or any(
                    memory.owner_context_uid is None
                    or (
                        memory.owner_context_uid,
                        memory.owner_context_name,
                    )
                    not in set(identities)
                    for memory in memories
                )
                or data["context_digest"]
                != meld_canonical_digest(
                    [context.to_dict() for context in contexts]
                )
            ):
                raise MeldError("Invalid owner-aware meld frame.")
        context_evidence = tuple(
            MeldMemory.from_dict(item)
            for item in _array(
                data.get("context_evidence", []),
                "meld Context evidence",
            )
        )
        selected_memory_uid = (
            _canonical_uuid(
                data["selected_memory_uid"],
                "selected meld Memory uid",
            )
            if "selected_memory_uid" in data
            else None
        )
        if (
            len({memory.uid for memory in context_evidence})
            != len(context_evidence)
            or {memory.uid for memory in memories}
            & {memory.uid for memory in context_evidence}
            or (
                context_evidence
                and any(
                    memory.owner_context_uid is None
                    or memory.owner_context_name is None
                    or (
                        contexts is not None
                        and (
                            memory.owner_context_uid,
                            memory.owner_context_name,
                        )
                        not in {
                            (context.uid, context.name)
                            for context in contexts
                        }
                    )
                    for memory in context_evidence
                )
            )
            or (
                selected_memory_uid is None
                and bool(context_evidence)
            )
            or (
                selected_memory_uid is not None
                and (
                    len(memories) != 1
                    or memories[0].uid != selected_memory_uid
                )
            )
        ):
            raise MeldError("Invalid meld Context evidence.")
        return cls(
            uid=_canonical_uuid(data["uid"], "meld frame uid"),
            context_uid=_canonical_uuid(
                data["context_uid"],
                "meld frame Context uid",
            ),
            context_name=_string(
                data["context_name"],
                "meld frame Context name",
                limit=MELD_NAME_LIMIT,
            ),
            context_digest=_digest(
                data["context_digest"],
                "meld frame Context digest",
            ),
            role=_literal(data["role"], _ROLES, "meld frame role"),  # type: ignore[arg-type]
            memories=memories,
            include_descendants=include_descendants,  # type: ignore[arg-type]
            contexts=contexts,
            context_evidence=context_evidence,
            selected_memory_uid=selected_memory_uid,
        )


@dataclass(frozen=True)
class MeldTarget:
    context_uid: str
    context_name: str
    context_digest: str

    @classmethod
    def from_context(cls, ctx: Context) -> "MeldTarget":
        """Bind the empty result Context required by a symmetric meld."""
        if tuple(ctx.iter_items()):
            raise MeldError(
                "Symmetric Context meld version 1 requires an empty active "
                "target Context."
            )
        return cls.from_baseline_context(ctx)

    @classmethod
    def from_baseline_context(
        cls,
        ctx: Context,
        *,
        context_digest: str | None = None,
    ) -> "MeldTarget":
        """Bind an existing Context as a directional meld baseline/target."""
        if not isinstance(ctx, Context):
            raise MeldError("Meld target must be a Context.")
        return cls.from_dict(
            {
                "context_uid": ctx.uid,
                "context_name": ctx.name,
                "context_digest": context_digest or context_record_digest(ctx),
            }
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "context_uid": self.context_uid,
            "context_name": self.context_name,
            "context_digest": self.context_digest,
        }

    @classmethod
    def from_dict(cls, value: object) -> "MeldTarget":
        data = _exact_dict(
            value,
            {"context_uid", "context_name", "context_digest"},
            "meld target",
        )
        return cls(
            context_uid=_canonical_uuid(
                data["context_uid"],
                "meld target Context uid",
            ),
            context_name=_string(
                data["context_name"],
                "meld target Context name",
                limit=MELD_NAME_LIMIT,
            ),
            context_digest=_digest(
                data["context_digest"],
                "meld target Context digest",
            ),
        )


@dataclass(frozen=True)
class MeldRelationAnalysisSeed:
    """Wire-compatible peer-relation snapshot that supplied turn zero."""

    analysis_digest: str
    analysis: MemoryRelationAnalysis

    @classmethod
    def create(
        cls,
        analysis: MemoryRelationAnalysis,
    ) -> "MeldRelationAnalysisSeed":
        if not isinstance(analysis, MemoryRelationAnalysis):
            raise MeldError("Meld relation seed must be a relation analysis.")
        restored = MemoryRelationAnalysis.from_dict(analysis.to_dict())
        if restored.ruleset_version != MEMORY_RELATION_RULESET_VERSION:
            raise MeldError(
                "Meld requires analysis from the current relation ruleset."
            )
        return cls.from_dict(
            {
                "analysis_digest": memory_relation_canonical_digest(restored.to_dict()),
                "analysis": restored.to_dict(),
            }
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "analysis_digest": self.analysis_digest,
            "analysis": self.analysis.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: object) -> "MeldRelationAnalysisSeed":
        data = _exact_dict(
            value,
            {"analysis_digest", "analysis"},
            "meld relation-analysis seed",
        )
        try:
            analysis = MemoryRelationAnalysis.from_dict(data["analysis"])
        except (TypeError, ValueError) as error:
            raise MeldError("Invalid meld relation-analysis seed.") from error
        result = cls(
            analysis_digest=_digest(
                data["analysis_digest"],
                "meld relation-analysis seed digest",
            ),
            analysis=analysis,
        )
        if result.analysis_digest != memory_relation_canonical_digest(
            result.analysis.to_dict()
        ):
            raise MeldError(
                "Meld relation-analysis seed digest does not match its analysis."
            )
        return result


# Existing sessions and external callers keep the schema-era vocabulary while
# new Meld code names the capability it actually consumes.
MeldComparisonSeed = MeldRelationAnalysisSeed
MELD_COMPARISON_SCHEMA_VERSION = MELD_RELATION_ANALYSIS_SCHEMA_VERSION
MELD_DIRECTIONAL_COMPARISON_SCHEMA_VERSION = MELD_DIRECTIONAL_RELATION_SCHEMA_VERSION
