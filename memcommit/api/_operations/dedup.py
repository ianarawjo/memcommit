"""Operation assembly for public deterministic Dedup planning and Apply."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from memcommit.api._runtime import ClientRuntime
from memcommit.api._support.errors import raise_public
from memcommit.api.dedup import (
    DedupApplyResult,
    DedupComponentResult,
    DedupEvidenceResult,
    DedupMemberResult,
    DedupPlanResult,
)
from memcommit.api.errors import (
    SemanticAuthorityError,
    SemanticConflictError,
    SemanticContextError,
    SemanticExecutionError,
    SemanticInputError,
    SemanticStorageError,
)
from memcommit.dedup_application import (
    DedupAuthorityError,
    DedupConflictError,
    DedupError,
    DedupRequest,
    DedupSelection,
    apply_dedup as apply_core_dedup,
    prepare_dedup,
)
from memcommit.dedup_runtime import MemoryStoreDedupPort
from memcommit.profile_config import (
    ProfileConfigError,
    load_profile_registry,
    profile_store_dir,
)
from memcommit.profiles import ProfileError
from memcommit.quality_finding_handoff import (
    QualityFindingHandoff,
    QualityFindingHandoffError,
)
from memcommit.store import ConcurrentContextUpdateError


def _port(runtime: ClientRuntime) -> MemoryStoreDedupPort:
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
                and runtime.store_root == profile_store_dir(live_registry.active).resolve()
            )
            if allow_grants:
                registry = live_registry
        except (ProfileConfigError, ProfileError) as error:
            raise_public(SemanticAuthorityError, error)
        except OSError as error:
            raise_public(SemanticStorageError, error)
    return MemoryStoreDedupPort(
        runtime.store,
        current_name=current_name,
        registry=registry,
        allow_grants=allow_grants,
    )


def _public(plan) -> DedupPlanResult:
    return DedupPlanResult(
        context_name=plan.display_name,
        context_uid=plan.context_uid,
        revision=plan.revision,
        components=tuple(
            DedupComponentResult(
                uid=component.uid,
                members=tuple(
                    DedupMemberResult(
                        uid=member.uid,
                        content=member.content,
                        ordinal=member.ordinal,
                        recommended=(
                            member.uid == component.recommended_survivor_uid
                        ),
                    )
                    for member in component.members
                ),
                evidence=tuple(
                    DedupEvidenceResult(
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
        _application_plan=plan,
    )


def plan_dedup(
    runtime: ClientRuntime,
    handoffs: Sequence[QualityFindingHandoff],
    *,
    expected_revision: str | None = None,
) -> DedupPlanResult:
    """Freeze confirmed finder receipts into deterministic components."""

    try:
        if isinstance(handoffs, (str, bytes)):
            raise TypeError("Dedup handoffs must be a sequence of typed receipts.")
        request = DedupRequest(tuple(handoffs))
        plan = prepare_dedup(request, port=_port(runtime))
        if expected_revision is not None and plan.revision != expected_revision:
            raise DedupConflictError(
                "The reviewed Dedup revision was not regenerated."
            )
    except DedupAuthorityError as error:
        raise_public(SemanticAuthorityError, error)
    except DedupConflictError as error:
        raise_public(SemanticConflictError, error)
    except (QualityFindingHandoffError, DedupError, TypeError, ValueError) as error:
        raise_public(SemanticInputError, error)
    except (FileNotFoundError, KeyError) as error:
        raise_public(SemanticContextError, error)
    except (ProfileConfigError, ProfileError) as error:
        raise_public(SemanticAuthorityError, error)
    except OSError as error:
        raise_public(SemanticStorageError, error)
    return _public(plan)


def apply_dedup(
    runtime: ClientRuntime,
    plan: DedupPlanResult,
    *,
    survivors: Mapping[str, str],
) -> DedupApplyResult:
    """Apply one exact complete survivor mapping from a reviewed plan."""

    if not isinstance(plan, DedupPlanResult):
        raise SemanticInputError("Dedup Apply requires a DedupPlanResult.")
    if not isinstance(survivors, Mapping) or any(
        not isinstance(component_uid, str)
        or not component_uid
        or not isinstance(survivor_uid, str)
        or not survivor_uid
        for component_uid, survivor_uid in survivors.items()
    ):
        raise SemanticInputError(
            "Dedup survivors must map component UIDs to Memory UIDs."
        )
    try:
        receipt = apply_core_dedup(
            plan._application_plan,
            tuple(
                DedupSelection(component_uid, survivor_uid)
                for component_uid, survivor_uid in survivors.items()
            ),
            port=_port(runtime),
        )
    except DedupAuthorityError as error:
        raise_public(SemanticAuthorityError, error)
    except (DedupConflictError, ConcurrentContextUpdateError) as error:
        raise_public(SemanticConflictError, error)
    except (ProfileConfigError, ProfileError) as error:
        raise_public(SemanticAuthorityError, error)
    except DedupError as error:
        raise_public(SemanticInputError, error)
    except OSError as error:
        raise_public(SemanticStorageError, error)
    except (RuntimeError, TypeError, ValueError) as error:
        raise_public(SemanticExecutionError, error)
    return DedupApplyResult(
        context_name=receipt.context_name,
        context_uid=receipt.context_uid,
        revision=receipt.revision,
        checkpoint_uid=receipt.checkpoint_uid,
        survivor_uids=receipt.survivor_uids,
        absorbed_uids=receipt.absorbed_uids,
    )


__all__ = ["apply_dedup", "plan_dedup"]
