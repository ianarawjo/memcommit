"""Operation assembly for public deterministic Dedun planning and Apply."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from memcommit.adapters.python_api._runtime import ClientRuntime
from memcommit.adapters.python_api._support.errors import raise_public
from memcommit.adapters.python_api.dedup import ExactDedupGroupResult
from memcommit.adapters.python_api.dedun import (
    DedunApplyResult,
    DedunComponentResult,
    DedunEvidenceResult,
    DedunMemberResult,
    DedunPlanResult,
)
from memcommit.adapters.python_api.errors import (
    SemanticAuthorityError,
    SemanticConflictError,
    SemanticContextError,
    SemanticExecutionError,
    SemanticInputError,
    SemanticStorageError,
)
from memcommit.application.operations.dedun.application import (
    DedunAuthorityError,
    DedunConflictError,
    DedunError,
    DedunRequest,
    DedunSelection,
    apply_dedun as apply_core_dedun,
    prepare_dedun,
)
from memcommit.application.operations.dedun.runtime import MemoryStoreDedunPort
from memcommit.application.operations.profile.config import (
    ProfileConfigError,
    load_profile_registry,
    profile_store_dir,
)
from memcommit.application.operations.profile.model import ProfileError
from memcommit.application.reviewing.quality.handoff import (
    QualityFindingHandoff,
    QualityFindingHandoffError,
)
from memcommit.persistence.store import ConcurrentContextUpdateError


def _port(runtime: ClientRuntime) -> MemoryStoreDedunPort:
    try:
        current_name = runtime.store.current_context_name()
    except FileNotFoundError:
        current_name = None
    except (OSError, ValueError) as error:
        raise_public(SemanticStorageError, error)
    registry = None
    allow_grants = False
    if runtime.registry is not None:
        try:
            live_registry = load_profile_registry()
            allow_grants = bool(
                runtime.profile is not None
                and runtime.profile.uid == live_registry.active.uid
                and runtime.store_root
                == profile_store_dir(live_registry.active).resolve()
            )
            if allow_grants:
                registry = live_registry
        except (ProfileConfigError, ProfileError) as error:
            raise_public(SemanticAuthorityError, error)
        except OSError as error:
            raise_public(SemanticStorageError, error)
    return MemoryStoreDedunPort(
        runtime.store,
        current_name=current_name,
        registry=registry,
        allow_grants=allow_grants,
    )


def _public(plan) -> DedunPlanResult:
    return DedunPlanResult(
        context_name=plan.display_name,
        context_uid=plan.context_uid,
        revision=plan.revision,
        components=tuple(
            DedunComponentResult(
                uid=component.uid,
                members=tuple(
                    DedunMemberResult(
                        uid=member.uid,
                        content=member.content,
                        ordinal=member.ordinal,
                        recommended=(member.uid == component.recommended_survivor_uid),
                    )
                    for member in component.members
                ),
                evidence=tuple(
                    DedunEvidenceResult(
                        finding_uid=evidence.finding_uid,
                        relation=evidence.relation,
                        left_uid=evidence.left_uid,
                        right_uid=evidence.right_uid,
                        reason=evidence.reason,
                    )
                    for evidence in component.evidence
                ),
                recommended_survivor_uid=component.recommended_survivor_uid,
            )
            for component in plan.components
        ),
        exact_item_groups=tuple(
            ExactDedupGroupResult(
                survivor_uid=group.survivor_uid,
                absorbed_uids=group.absorbed_uids,
                content=group.content,
                item_kind=group.item_kind,
                summary=group.summary,
            )
            for group in plan.exact_item_groups
        ),
        _application_plan=plan,
    )


def plan_dedun(
    runtime: ClientRuntime,
    evidence: Sequence[QualityFindingHandoff],
    *,
    expected_revision: str | None = None,
) -> DedunPlanResult:
    """Freeze typed exact-plus-semantic redundancy evidence into components."""

    try:
        if isinstance(evidence, (str, bytes)):
            raise TypeError(
                "Dedun evidence must be a sequence of typed redundancy receipts."
            )
        handoffs = tuple(evidence)
        first = handoffs[0] if handoffs else None
        request = DedunRequest(
            handoffs,
            exact_source=(first.sources[0] if first is not None else None),
            exact_source_frame_digest=(
                first.source_frame_digest if first is not None else None
            ),
        )
        plan = prepare_dedun(request, port=_port(runtime))
        if expected_revision is not None and plan.revision != expected_revision:
            raise DedunConflictError("The reviewed Dedun revision was not regenerated.")
    except DedunAuthorityError as error:
        raise_public(SemanticAuthorityError, error)
    except DedunConflictError as error:
        raise_public(SemanticConflictError, error)
    except (QualityFindingHandoffError, DedunError, TypeError, ValueError) as error:
        raise_public(SemanticInputError, error)
    except (FileNotFoundError, KeyError) as error:
        raise_public(SemanticContextError, error)
    except (ProfileConfigError, ProfileError) as error:
        raise_public(SemanticAuthorityError, error)
    except OSError as error:
        raise_public(SemanticStorageError, error)
    return _public(plan)


def apply_dedun(
    runtime: ClientRuntime,
    plan: DedunPlanResult,
    *,
    survivors: Mapping[str, str],
) -> DedunApplyResult:
    """Apply one exact complete survivor mapping from a reviewed plan."""

    if not isinstance(plan, DedunPlanResult):
        raise SemanticInputError("Dedun Apply requires a DedunPlanResult.")
    if not isinstance(survivors, Mapping) or any(
        not isinstance(component_uid, str)
        or not component_uid
        or not isinstance(survivor_uid, str)
        or not survivor_uid
        for component_uid, survivor_uid in survivors.items()
    ):
        raise SemanticInputError("Dedun survivors must map group UIDs to Memory UIDs.")
    try:
        receipt = apply_core_dedun(
            plan._application_plan,
            tuple(
                DedunSelection(component_uid, survivor_uid)
                for component_uid, survivor_uid in survivors.items()
            ),
            port=_port(runtime),
        )
    except DedunAuthorityError as error:
        raise_public(SemanticAuthorityError, error)
    except (DedunConflictError, ConcurrentContextUpdateError) as error:
        raise_public(SemanticConflictError, error)
    except (ProfileConfigError, ProfileError) as error:
        raise_public(SemanticAuthorityError, error)
    except DedunError as error:
        raise_public(SemanticInputError, error)
    except OSError as error:
        raise_public(SemanticStorageError, error)
    except (RuntimeError, TypeError, ValueError) as error:
        raise_public(SemanticExecutionError, error)
    return DedunApplyResult(
        context_name=receipt.context_name,
        context_uid=receipt.context_uid,
        revision=receipt.revision,
        checkpoint_uid=receipt.checkpoint_uid,
        survivor_uids=receipt.survivor_uids,
        absorbed_uids=receipt.absorbed_uids,
    )


# Compatibility aliases for the pre-Dedun public Python surface.
plan_consolidation = plan_dedun
apply_consolidation = apply_dedun
plan_dedup = plan_dedun
apply_dedup = apply_dedun


__all__ = [
    "apply_consolidation",
    "apply_dedun",
    "apply_dedup",
    "plan_consolidation",
    "plan_dedun",
    "plan_dedup",
]
