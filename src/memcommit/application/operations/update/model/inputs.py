"""Frozen Update Source/Target bindings and candidate collection."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.capabilities.semantic.goal_focus import FrozenGoalFocus
from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.application.capabilities.semantic.memory_scope import (
    MemoryScopeError,
    resolve_memory_scope,
)

from .changes import (
    SourceReference,
    UpdateError,
    _sha256_text,
)


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
class UpdatePlanningInputs:
    """Provider candidates and the execution inputs captured alongside them."""

    source_candidates: tuple[SourceCandidate, ...]
    target_contexts: tuple[TargetContextCandidate, ...]
    target_memories: tuple[TargetMemoryCandidate, ...]
    execution_inputs: UpdateExecutionInputs
    source_context_only: tuple[SourceCandidate, ...] = ()
    target_context_only: tuple[TargetMemoryCandidate, ...] = ()


def collect_update_inputs(
    source_contexts: tuple[Context, ...],
    target_contexts: tuple[Context, ...],
    *,
    source_include_descendants: bool = False,
    target_include_descendants: bool = False,
    source_memory_selector: str | None = None,
    target_memory_selector: str | None = None,
    goal_focus: FrozenGoalFocus | None = None,
    instruction: str | None = None,
) -> UpdatePlanningInputs:
    """Collect readable source facts and directly writable target Memories."""
    if not target_contexts:
        raise UpdateError("Update requires a Target Context.")
    if (
        type(source_include_descendants) is not bool
        or type(target_include_descendants) is not bool
    ):
        raise ValueError("Update descendant scopes must be booleans.")
    if goal_focus is not None and not isinstance(goal_focus, FrozenGoalFocus):
        raise UpdateError("Update Goal focus must be a typed frozen frame.")
    if source_memory_selector is not None and source_include_descendants:
        raise UpdateError(
            "A Source Memory selector cannot be combined with descendant scope."
        )
    if target_memory_selector is not None and target_include_descendants:
        raise UpdateError(
            "A Target Memory selector cannot be combined with descendant scope."
        )
    if instruction is not None and (
        not isinstance(instruction, str) or not instruction.strip()
    ):
        raise UpdateError("An Update instruction must be nonblank text.")
    if source_contexts and source_contexts[0].uid == target_contexts[0].uid:
        raise UpdateError("A Context cannot update itself.")
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
        for item in context.iter_memories():
            if isinstance(item, Memory):
                identity = (context.uid, item.uid)
                source_uid = context.uid
                source_name = context.name
                memory_uid = item.uid
                content = item.content
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
        for item in context.iter_memories():
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
        if source_contexts and (
            len(source_scope.actionable) != 1
            or source_scope.actionable[0].content != instruction
        ):
            raise UpdateError(
                "Update instruction does not match its single frozen input."
            )
    elif not source_scope.actionable:
        raise UpdateError("Update Source has no readable Memories.")
    return UpdatePlanningInputs(
        source_candidates=source_scope.actionable,
        # A focused target is an exact existing Memory operation. Its owner is
        # not exposed as an ADD target, preventing a sibling result from
        # escaping the selected Memory scope.
        target_contexts=(
            () if target_scope.selected_uid is not None else target_context_candidates
        ),
        target_memories=target_scope.actionable,
        execution_inputs=UpdateExecutionInputs(
            source_uid=source_contexts[0].uid if source_contexts else None,
            source_name=source_contexts[0].name if source_contexts else None,
            source_contexts=tuple(
                (context.uid, context.name) for context in source_contexts
            ),
            target_uid=target_contexts[0].uid,
            target_name=target_contexts[0].name,
            target_contexts=tuple(
                (context.uid, context.name) for context in target_contexts
            ),
            source_include_descendants=source_include_descendants,
            target_include_descendants=target_include_descendants,
            source_memory_uid=source_scope.selected_uid,
            target_memory_uid=target_scope.selected_uid,
            goal_focus=goal_focus,
            instruction=instruction,
        ),
        source_context_only=()
        if instruction is not None
        else source_scope.context_only,
        target_context_only=target_scope.context_only,
    )


@dataclass(frozen=True, slots=True)
class UpdateExecutionInputs:
    """Frozen instruction, identities and scope for publication and evidence."""

    source_uid: str | None
    source_name: str | None
    source_contexts: tuple[tuple[str, str], ...]
    target_uid: str
    target_name: str
    target_contexts: tuple[tuple[str, str], ...]
    source_include_descendants: bool = False
    target_include_descendants: bool = False
    source_memory_uid: str | None = None
    target_memory_uid: str | None = None
    goal_focus: FrozenGoalFocus | None = None
    instruction: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            **{
                name: getattr(self, name)
                for name in (
                    "source_uid",
                    "source_name",
                    "target_uid",
                    "target_name",
                    "source_include_descendants",
                    "target_include_descendants",
                    "source_memory_uid",
                    "target_memory_uid",
                )
            },
            "source_contexts": [
                {"uid": uid, "name": name} for uid, name in self.source_contexts
            ],
            "target_contexts": [
                {"uid": uid, "name": name} for uid, name in self.target_contexts
            ],
            "goal_focus": self.goal_focus.receipt_record() if self.goal_focus else None,
            "instruction": self.instruction,
        }

    @classmethod
    def from_dict(cls, value: object) -> UpdateExecutionInputs:
        from dataclasses import fields
        from .changes import (
            _require_exact_keys,
            _require_string,
            _require_uuid,
        )

        # Older completed evidence predates instruction-based direct execution.
        if isinstance(value, dict) and "instruction" not in value:
            value = {**value, "instruction": None}
        data = dict(
            _require_exact_keys(value, {f.name for f in fields(cls)}, "Update inputs")
        )
        for role in ("source", "target"):
            for field in ("uid", "name"):
                value = data[f"{role}_{field}"]
                if role != "source" or value is not None:
                    _require_string(value, f"{role} {field}")
            if type(data[f"{role}_include_descendants"]) is not bool:
                raise ValueError("Invalid Update scope.")
            selected = data[f"{role}_memory_uid"]
            if selected is not None:
                _require_uuid(selected, "selected Memory")
                if data[f"{role}_include_descendants"]:
                    raise ValueError("Focused Update cannot include descendants.")
            records = data[f"{role}_contexts"]
            if not isinstance(records, list):
                raise ValueError("Invalid Update Context identities.")
            context_identities = []
            for record in records:
                if isinstance(record, dict):
                    record = {
                        key: item for key, item in record.items() if key != "digest"
                    }
                identity = _require_exact_keys(
                    record, {"uid", "name"}, "Update Context identity"
                )
                context_identities.append(
                    (
                        _require_string(identity["uid"], "Context uid"),
                        _require_string(identity["name"], "Context name"),
                    )
                )
            data[f"{role}_contexts"] = tuple(context_identities)
        data["goal_focus"] = (
            FrozenGoalFocus.from_receipt_record(data["goal_focus"])
            if data["goal_focus"] is not None
            else None
        )
        if data["instruction"] is not None:
            _require_string(data["instruction"], "Update instruction")
        return cls(**data)
