"""Frozen Update Source/Target bindings and candidate collection."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from memcommit.application.context_access import (
    GrantedContextBinding,
    granted_context_binding_digest,
)
from memcommit.application.capabilities.semantic.disclosure import (
    SemanticDisclosureError,
    require_semantic_disclosure_authority,
)
from memcommit.application.capabilities.semantic.goal_focus import FrozenGoalFocus
from memcommit.core.context import Context, Memory, MemoryRef
from memcommit.application.capabilities.semantic.memory_scope import (
    MemoryScopeError,
    resolve_memory_scope,
)

from .changes import (
    SourceReference,
    UpdateError,
    _sha256_json,
    _sha256_text,
)
from .fingerprints import ContextFingerprint
from .instruction import UpdateInstruction


INLINE_UPDATE_CONTEXT_NAME = "INLINE UPDATE MEMORY"
_INLINE_UPDATE_NAMESPACE = uuid.UUID("a9e29d5e-4768-4a33-9f9b-77b6020b2d72")


def inline_update_context(content: str) -> Context:
    """Build the stable process-local Source frame for one exact text value.

    Deterministic identities preserve exact inline-source provenance without
    publishing a synthetic Context to the Store.
    """

    if not isinstance(content, str) or not content.strip():
        raise UpdateError("Inline Update Memory content must be nonblank text.")
    context_uid = str(uuid.uuid5(_INLINE_UPDATE_NAMESPACE, "context\0" + content))
    memory_uid = str(uuid.uuid5(_INLINE_UPDATE_NAMESPACE, "memory\0" + content))
    context = Context(uid=context_uid, name=INLINE_UPDATE_CONTEXT_NAME)
    context.add(Memory(uid=memory_uid, content=content))
    return context


# Historical imports remain valid while operation packages migrate to the
# operation-neutral Context-access owner.
GrantedUpdateTarget = GrantedContextBinding
granted_target_digest = granted_context_binding_digest


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
    instruction: UpdateInstruction | None = None


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
    instruction: UpdateInstruction | None = None,
) -> UpdateInputs:
    """Collect readable source facts and directly writable target Memories."""
    try:
        require_semantic_disclosure_authority(
            (source, target),
            operation="Update",
        )
    except SemanticDisclosureError as error:
        raise UpdateError(str(error)) from error
    # An instruction changes one Context; embedded Contexts remain independent.
    source_contexts = (source,) if instruction is not None else _walk_contexts(source)
    target_contexts = (target,) if instruction is not None else _walk_contexts(target)
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
    if instruction is not None:
        if not isinstance(instruction, UpdateInstruction):
            raise TypeError("Update requires a typed instruction.")
        if (
            len(source_scope.actionable) != 1
            or source_scope.actionable[0].content != instruction.text
        ):
            raise UpdateError(
                "Update instruction does not match its single frozen input."
            )
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
        source_context_only=()
        if instruction is not None
        else source_scope.context_only,
        target_context_only=target_scope.context_only,
        source_memory_uid=source_scope.selected_uid,
        target_memory_uid=target_scope.selected_uid,
        instruction=instruction,
    )


@dataclass(frozen=True, slots=True)
class UpdateContextInputs:
    """Frozen execution inputs; never a saved or resumable work slot."""

    source_uid: str
    source_name: str
    source_digest: str
    source_contexts: tuple[ContextFingerprint, ...]
    target_uid: str
    target_name: str
    target_digest: str
    target_contexts: tuple[ContextFingerprint, ...]
    source_include_descendants: bool = False
    target_include_descendants: bool = False
    source_memory_uid: str | None = None
    target_memory_uid: str | None = None
    inline_source_content: str | None = None
    granted_source: GrantedContextBinding | None = None
    granted_target: GrantedContextBinding | None = None
    goal_focus: FrozenGoalFocus | None = None
    instruction: UpdateInstruction | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            **{
                name: getattr(self, name)
                for name in (
                    "source_uid",
                    "source_name",
                    "source_digest",
                    "target_uid",
                    "target_name",
                    "target_digest",
                    "source_include_descendants",
                    "target_include_descendants",
                    "source_memory_uid",
                    "target_memory_uid",
                    "inline_source_content",
                )
            },
            "source_contexts": [item.to_dict() for item in self.source_contexts],
            "target_contexts": [item.to_dict() for item in self.target_contexts],
            "granted_source": self.granted_source.to_dict()
            if self.granted_source
            else None,
            "granted_target": self.granted_target.to_dict()
            if self.granted_target
            else None,
            "goal_focus": self.goal_focus.receipt_record() if self.goal_focus else None,
            "instruction": self.instruction.text
            if self.instruction is not None
            else None,
        }

    @classmethod
    def from_dict(cls, value: object) -> UpdateContextInputs:
        from dataclasses import fields
        from .changes import (
            _require_exact_keys,
            _require_string,
            _require_uuid,
            _is_sha256,
        )

        # Older completed evidence predates instruction-based direct execution.
        if isinstance(value, dict) and "instruction" not in value:
            value = {**value, "instruction": None}
        data = dict(
            _require_exact_keys(value, {f.name for f in fields(cls)}, "Update inputs")
        )
        for role in ("source", "target"):
            for field in ("uid", "name"):
                _require_string(data[f"{role}_{field}"], f"{role} {field}")
            if not _is_sha256(data[f"{role}_digest"]):
                raise ValueError("Invalid Update input digest.")
            if type(data[f"{role}_include_descendants"]) is not bool:
                raise ValueError("Invalid Update scope.")
            selected = data[f"{role}_memory_uid"]
            if selected is not None:
                _require_uuid(selected, "selected Memory")
                if data[f"{role}_include_descendants"]:
                    raise ValueError("Focused Update cannot include descendants.")
            records = data[f"{role}_contexts"]
            if not isinstance(records, list):
                raise ValueError("Invalid Update fingerprints.")
            data[f"{role}_contexts"] = tuple(
                ContextFingerprint.from_dict(item) for item in records
            )
            binding = data[f"granted_{role}"]
            data[f"granted_{role}"] = (
                GrantedContextBinding.from_dict(binding)
                if binding is not None
                else None
            )
        data["goal_focus"] = (
            FrozenGoalFocus.from_receipt_record(data["goal_focus"])
            if data["goal_focus"] is not None
            else None
        )
        data["instruction"] = (
            UpdateInstruction(data["instruction"])
            if data["instruction"] is not None
            else None
        )
        result = cls(**data)
        inline_update_source(result)
        return result


def freeze_update_context_inputs(
    source: Context,
    target: Context,
    *,
    source_include_descendants: bool = False,
    target_include_descendants: bool = False,
    granted_source: GrantedContextBinding | None = None,
    granted_target: GrantedContextBinding | None = None,
    source_memory_selector: str | None = None,
    target_memory_selector: str | None = None,
    inline_source_content: str | None = None,
    goal_focus: FrozenGoalFocus | None = None,
    instruction: UpdateInstruction | None = None,
) -> UpdateContextInputs:
    collected = collect_update_inputs(
        source,
        target,
        source_memory_selector=source_memory_selector,
        target_memory_selector=target_memory_selector,
        instruction=instruction,
    )
    return UpdateContextInputs(
        source.uid,
        source.name,
        collected.source_digest,
        collected.source_contexts,
        target.uid,
        target.name,
        collected.target_digest,
        collected.target_context_fingerprints,
        source_include_descendants,
        target_include_descendants,
        collected.source_memory_uid,
        collected.target_memory_uid,
        inline_source_content,
        granted_source,
        granted_target,
        goal_focus,
        instruction,
    )


def inline_update_source(inputs: UpdateContextInputs) -> Context | None:
    """Reconstruct and validate a process-local Update Source."""

    if not isinstance(inputs, UpdateContextInputs):
        raise TypeError("Inline Update reconstruction requires an UpdateContextInputs.")
    if inputs.inline_source_content is None:
        return None
    source = inline_update_context(inputs.inline_source_content)
    if (
        source.uid != inputs.source_uid
        or source.name != inputs.source_name
        or inputs.source_digest != _inline_update_source_digest(source)
        or inputs.source_contexts != _fingerprint_contexts([source])
        or inputs.source_include_descendants
        or inputs.source_memory_uid is not None
        or inputs.granted_source is not None
    ):
        raise UpdateError("Inline Update Source no longer matches its frozen frame.")
    return source


def update_inputs_match(
    inputs: UpdateContextInputs,
    source: Context,
    target: Context,
    *,
    granted_source: GrantedContextBinding | None = None,
    granted_target: GrantedContextBinding | None = None,
) -> bool:
    """Return whether an impact plan still describes the exact A/B inputs."""
    if (
        inputs.source_uid != source.uid
        or inputs.source_name != source.name
        or inputs.target_uid != target.uid
        or inputs.target_name != target.name
        or inputs.granted_source != granted_source
        or inputs.granted_target != granted_target
    ):
        return False
    try:
        collected = collect_update_inputs(
            source,
            target,
            source_memory_selector=inputs.source_memory_uid,
            target_memory_selector=inputs.target_memory_uid,
            instruction=inputs.instruction,
        )
    except UpdateError:
        return False
    return (
        inputs.source_memory_uid == collected.source_memory_uid
        and inputs.target_memory_uid == collected.target_memory_uid
        and inputs.source_digest == collected.source_digest
        and inputs.target_digest == collected.target_digest
        and inputs.source_contexts == collected.source_contexts
        and inputs.target_contexts == collected.target_context_fingerprints
    )
