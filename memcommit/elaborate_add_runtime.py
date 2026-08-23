"""Context-backed preparation and atomic Add for standalone Elaborate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from memcommit.context import Memory
from memcommit.elaborate import ElaborateError, ElaborateMode
from memcommit.elaborate_application import ElaborateRequest, ElaborateResult
from memcommit.elaborate_runtime import (
    ElaborateProviderFactory,
    execute_elaborate,
)
from memcommit.elaborate_target_context import (
    FrozenElaborateTargetContext,
    GRANTED_ELABORATE_ADD_PERMISSIONS,
    GRANTED_ELABORATE_AMBIENT_PERMISSIONS,
    authorized_frozen_elaborate_target,
    freeze_elaborate_target_context,
)
from memcommit.semantic_add_runtime import (
    FrozenSemanticAddTarget,
    SemanticAddReceipt,
    append_semantic_memories,
    freeze_semantic_add_target,
)
from memcommit.store import MemoryStore, context_record_digest


ElaborateContextRole = Literal["goal", "rules"]


@dataclass(frozen=True)
class FrozenElaborateSource:
    """One exact ordinary Context pre-image projected into Elaborate."""

    context_name: str
    context_uid: str
    context_digest: str
    role: ElaborateContextRole
    request: ElaborateRequest
    memory_uids: tuple[str, ...]


@dataclass(frozen=True)
class PreparedElaborateAdd:
    """Exact provider result paired with its already-frozen Add Target."""

    result: ElaborateResult
    target: FrozenSemanticAddTarget
    target_context: FrozenElaborateTargetContext
    source: FrozenElaborateSource | None = None


def freeze_elaborate_context_source(
    store: MemoryStore,
    *,
    context_name: str,
    role: ElaborateContextRole,
    number: int | None = None,
) -> FrozenElaborateSource:
    """Interpret ordinary direct Memories by invocation role, never by name."""

    if role not in {"goal", "rules"}:
        raise ElaborateError("Elaborate --as must be 'goal' or 'rules'.")
    context = store.load_direct(context_name)
    items = tuple(context.iter_items())
    if any(not isinstance(item, Memory) for item in items):
        raise ElaborateError(
            "Context-backed Elaborate requires only directly owned ordinary "
            "Memories in its Source."
        )
    memories = tuple(item for item in items if isinstance(item, Memory))
    if role == "goal":
        if len(memories) != 1:
            raise ElaborateError(
                "Elaborate --as goal requires exactly one direct Source Memory."
            )
        request = ElaborateRequest(goal=memories[0].content, number=number)
    else:
        if not memories:
            raise ElaborateError(
                "Elaborate requires at least one direct Source Memory."
            )
        request = ElaborateRequest(
            rules=tuple(item.content for item in memories),
            number=number,
        )
    return FrozenElaborateSource(
        context_name=context.name,
        context_uid=context.uid,
        context_digest=context_record_digest(context),
        role=role,
        request=request,
        memory_uids=tuple(item.uid for item in memories),
    )


def _revalidate_source(
    store: MemoryStore,
    source: FrozenElaborateSource,
) -> None:
    current = store.load_direct(source.context_name)
    if (
        current.uid != source.context_uid
        or context_record_digest(current) != source.context_digest
    ):
        raise ElaborateError(
            f"Source Context '{source.context_name}' changed while Elaborate "
            "was running; no generated Memories were added."
        )


def prepare_elaborate_add(
    *,
    store: MemoryStore,
    request: ElaborateRequest,
    target_name: str,
    provider_factory: ElaborateProviderFactory,
    source: FrozenElaborateSource | None = None,
    will_apply: bool = False,
) -> PreparedElaborateAdd:
    """Freeze Target before inference and return one non-mutating exact plan."""

    if source is not None and source.request != request:
        raise ElaborateError("Elaborate Source does not match its request.")
    target = freeze_semantic_add_target(store, target_name)
    excluded_root_memory_uids = (
        source.memory_uids
        if source is not None and source.context_uid == target.context_uid
        else ()
    )
    target_context = freeze_elaborate_target_context(
        store,
        target=target,
        excluded_root_memory_uids=excluded_root_memory_uids,
        required_granted_permissions=(
            GRANTED_ELABORATE_ADD_PERMISSIONS
            if will_apply
            else GRANTED_ELABORATE_AMBIENT_PERMISSIONS
        ),
    )
    if source is not None:
        _revalidate_source(store, source)
    with authorized_frozen_elaborate_target(store, target_context):
        if source is not None:
            _revalidate_source(store, source)
        result = execute_elaborate(
            request,
            provider_factory=provider_factory,
            target_context=(
                target_context.semantic if target_context.semantic.items else None
            ),
        )
        if source is not None:
            _revalidate_source(store, source)
    return PreparedElaborateAdd(
        result=result,
        target=target,
        target_context=target_context,
        source=source,
    )


def apply_prepared_elaborate_add(
    prepared: PreparedElaborateAdd,
    *,
    store: MemoryStore,
) -> SemanticAddReceipt:
    """Append the complete generated proposal set as one Context checkpoint."""

    if not isinstance(prepared, PreparedElaborateAdd):
        raise TypeError("Elaborate Add requires a prepared result.")
    analysis = prepared.result.analysis
    contents = (
        tuple(item.content for item in analysis.rules)
        if analysis.mode is ElaborateMode.GOAL_TO_RULES
        else tuple(item.proposition for item in analysis.cases)
    )
    source = prepared.source
    source_bindings = (
        ()
        if source is None
        else ((source.context_name, source.context_uid, source.context_digest),)
    )
    proposal_records = (
        [
            {
                "proposal_uid": item.uid,
                "content": item.content,
                "rationale": item.rationale,
                "target_context_refs": list(item.target_context_refs),
            }
            for item in analysis.rules
        ]
        if analysis.mode is ElaborateMode.GOAL_TO_RULES
        else [
            {
                "proposal_uid": item.uid,
                "content": item.proposition,
                "expected": item.expected,
                "rationale": item.rationale,
                "case_role": item.case_role,
                "rule_checks": [
                    {
                        "source_rule_index": check.source_rule_index,
                        "evidence": check.evidence,
                    }
                    for check in item.rule_checks
                ],
                "validation": {
                    "source_fit": item.validation.source_fit,
                    "source_fit_reason": item.validation.source_fit_reason,
                    "rule_conformance": item.validation.rule_conformance,
                    "conforming_source_rule_indexes": list(
                        item.validation.conforming_source_rule_indexes
                    ),
                }
                if item.validation is not None
                else None,
                "target_context_refs": list(item.target_context_refs),
            }
            for item in analysis.cases
        ]
    )
    ambient_bindings = tuple(
        (item.context_name, item.context_uid, item.context_digest)
        for item in prepared.target_context.local_contexts
    )
    all_source_bindings = tuple(
        dict.fromkeys((*source_bindings, *ambient_bindings))
    )
    with authorized_frozen_elaborate_target(
        store,
        prepared.target_context,
        revalidate_after=False,
        required_granted_permissions=GRANTED_ELABORATE_ADD_PERMISSIONS,
    ):
        return append_semantic_memories(
            store=store,
            operation="elaborate",
            source_name=source.context_name if source is not None else None,
            target=prepared.target,
            contents=contents,
            source_bindings=all_source_bindings,
            operation_args={
                "version": 3,
                "analysis_uid": analysis.uid,
                "analysis_digest": analysis.digest,
                "mode": analysis.mode.value,
                "number": analysis.number,
                "verification": "UNVERIFIED",
                "case_validation": (
                    "INDEPENDENT_SOURCE_RULE_CONFORMANCE_AND_SOURCE_FIT"
                    if analysis.mode is ElaborateMode.RULES_TO_CASES
                    else None
                ),
                "origin": prepared.result.origin,
                "overview": analysis.overview,
                "inputs": list(analysis.inputs),
                "target_ambient": analysis.target_context.prompt_record()
                if analysis.target_context is not None
                else None,
                "proposals": proposal_records,
            },
            description=(
                f"Added {len(contents)} Elaborate "
                f"{'Rules' if analysis.mode is ElaborateMode.GOAL_TO_RULES else 'Cases'} "
                f"to '{prepared.target.context_name}'"
            ),
        )


__all__ = [
    "ElaborateContextRole",
    "FrozenElaborateSource",
    "PreparedElaborateAdd",
    "apply_prepared_elaborate_add",
    "freeze_elaborate_context_source",
    "prepare_elaborate_add",
]
