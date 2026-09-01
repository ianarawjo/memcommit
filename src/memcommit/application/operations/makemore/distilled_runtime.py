"""Compose evidence-bound Distill with unverified Makemore generation."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Protocol

from memcommit.application.capabilities.semantic.goal_focus import FrozenGoalFocus
from memcommit.application.capabilities.semantic.goal_focus_runtime import (
    revalidate_goal_focus,
)
from memcommit.application.capabilities.semantic_result_memorization import (
    SemanticResultMemorizationReceipt,
    freeze_memorization_target,
    memorize_semantic_result,
)
from memcommit.application.operations.distill.application import (
    DistillRequest,
    DistillResult,
    run_distill,
)
from memcommit.application.operations.distill.config import (
    DEFAULT_DISTILL_SEMANTIC_CONFIG,
    DistillSemanticConfig,
)
from memcommit.application.operations.distill.model import (
    DistillProvider,
    ensure_distill_goal_fit_allows_add,
)
from memcommit.application.operations.distill.runtime import (
    LocalMemoryStoreDistillSourcePort,
)
from memcommit.application.operations.makemore.add_runtime import (
    PreparedMakemoreAdd,
    makemore_checkpoint_payload,
    makemore_result_contents,
    prepare_makemore_add_to_frozen_target,
)
from memcommit.application.operations.makemore.application import (
    MakemoreRequest,
    MakemoreResult,
)
from memcommit.application.operations.makemore.model import (
    MakemoreError,
    MakemoreProvider,
)
from memcommit.application.operations.makemore.target_context import (
    GRANTED_MAKEMORE_ADD_PERMISSIONS,
    authorized_frozen_makemore_target,
)
from memcommit.persistence.store import MemoryStore


DISTILLED_MAKEMORE_PIPELINE_CONTRACT_VERSION = 1
DISTILLED_MAKEMORE_CHECKPOINT_VERSION = 6


class DistilledMakemoreProviderFactory(Protocol):
    def __call__(self) -> DistillProvider | MakemoreProvider:
        """Construct one provider session for either pipeline stage."""


@dataclass(frozen=True)
class PreparedDistilledMakemoreAdd:
    """One frozen Source→distilled-Rules→Cases plan with no intermediate write."""

    distill: DistillResult
    makemore: PreparedMakemoreAdd
    source_port: LocalMemoryStoreDistillSourcePort

    @property
    def result(self) -> MakemoreResult:
        return self.makemore.result

    @property
    def source_name(self) -> str:
        return self.distill.analysis.source.context_name

    @property
    def target_name(self) -> str:
        return self.makemore.target.context_name


def _assert_source_unchanged(
    prepared: PreparedDistilledMakemoreAdd,
) -> None:
    current = prepared.source_port.revalidate(prepared.distill.frozen_source)
    if (
        current != prepared.distill.analysis.source
        or current.digest != prepared.distill.analysis.source.digest
    ):
        raise MakemoreError(
            "The Context Source changed while Distill→Makemore was running; "
            "no generated Memories were added."
        )


def _goal_bindings(focus: FrozenGoalFocus | None) -> tuple[tuple[str, str, str], ...]:
    if focus is None or focus.kind == "INLINE":
        return ()
    assert focus.context_name is not None
    assert focus.context_uid is not None
    assert focus.context_digest is not None
    return ((focus.context_name, focus.context_uid, focus.context_digest),)


def _distillation_checkpoint_payload(result: DistillResult) -> dict[str, object]:
    analysis = result.analysis
    goal_fit = analysis.goal_fit
    return {
        "pipeline_contract_version": DISTILLED_MAKEMORE_PIPELINE_CONTRACT_VERSION,
        "analysis_uid": analysis.uid,
        "analysis_digest": analysis.digest,
        "provider_contract_version": analysis.provider_contract_version,
        "origin": result.origin,
        "source_digest": analysis.source.digest,
        "overview": analysis.overview,
        "goal": analysis.goal,
        "goal_fit": (
            None
            if goal_fit is None
            else {
                "contract_version": goal_fit.contract_version,
                "verdict": goal_fit.verdict,
                "reason": goal_fit.reason,
                "considered_rule_uids": list(goal_fit.considered_rule_uids),
                "material_rule_uids": list(goal_fit.material_rule_uids),
            }
        ),
        "rules": [
            {
                "rule_uid": rule.uid,
                "content": rule.content,
                "rationale": rule.rationale,
                "support_memory_uids": list(rule.support_memory_uids),
                "boundary_memory_uids": list(rule.boundary_memory_uids),
            }
            for rule in analysis.rules
        ],
        "outside_memory_uids": list(analysis.outside_memory_uids),
    }


def prepare_distilled_makemore_add(
    *,
    store: MemoryStore,
    source_name: str,
    target_name: str,
    provider_factory: DistilledMakemoreProviderFactory,
    goal_focus: FrozenGoalFocus | None = None,
    number: int | None = None,
    strict: bool = False,
    will_apply: bool = False,
    distill_config: DistillSemanticConfig = DEFAULT_DISTILL_SEMANTIC_CONFIG,
) -> PreparedDistilledMakemoreAdd:
    """Distill one exact Context and feed its transient Rules into Makemore."""

    source_port = LocalMemoryStoreDistillSourcePort.capture(store)
    # Freeze the final destination before either provider stage. A target that
    # drifts during Distill must not be silently adopted by the later stage.
    target = freeze_memorization_target(store, target_name)

    @contextmanager
    def distill_provider_session() -> Iterator[DistillProvider]:
        provider = provider_factory()
        yield provider  # type: ignore[misc]

    if goal_focus is not None:
        revalidate_goal_focus(store, goal_focus)
    distill = run_distill(
        DistillRequest(context_locator=source_name, goal_focus=goal_focus),
        source_port=source_port,
        provider_session_factory=distill_provider_session,
        config=distill_config,
    )
    ensure_distill_goal_fit_allows_add(distill.analysis)
    if not distill.analysis.rules:
        raise MakemoreError(
            "Distill found no evidence-supported Rules for Makemore; "
            "no generated Memories were added."
        )

    request = MakemoreRequest(
        rules=tuple(rule.content for rule in distill.analysis.rules),
        goal_focus=goal_focus,
        number=number,
        strict=strict,
    )
    excluded_root_memory_uids = tuple(
        source.memory_uid
        for source in distill.analysis.source.sources
        if source.context_uid == target.context_uid
    )
    staged = PreparedDistilledMakemoreAdd(
        distill=distill,
        makemore=prepare_makemore_add_to_frozen_target(
            store=store,
            request=request,
            target=target,
            provider_factory=provider_factory,  # type: ignore[arg-type]
            excluded_root_memory_uids=excluded_root_memory_uids,
            will_apply=will_apply,
        ),
        source_port=source_port,
    )
    _assert_source_unchanged(staged)
    return staged


def apply_prepared_distilled_makemore_add(
    prepared: PreparedDistilledMakemoreAdd,
    *,
    store: MemoryStore,
) -> SemanticResultMemorizationReceipt:
    """Publish only final Cases and retain the transient Distill evidence."""

    if not isinstance(prepared, PreparedDistilledMakemoreAdd):
        raise TypeError("Distill→Makemore Add requires a prepared pipeline result.")
    ensure_distill_goal_fit_allows_add(prepared.distill.analysis)
    _assert_source_unchanged(prepared)
    goal_focus = prepared.distill.goal_focus
    if goal_focus is not None:
        revalidate_goal_focus(store, goal_focus)
    source_bindings = prepared.source_port.source_bindings(
        prepared.distill.frozen_source
    )
    ambient_bindings = tuple(
        (item.context_name, item.context_uid, item.context_digest)
        for item in prepared.makemore.target_context.local_contexts
    )
    bindings = tuple(
        dict.fromkeys(
            (*source_bindings, *_goal_bindings(goal_focus), *ambient_bindings)
        )
    )
    contents = makemore_result_contents(prepared.result)
    with authorized_frozen_makemore_target(
        store,
        prepared.makemore.target_context,
        revalidate_after=False,
        required_granted_permissions=GRANTED_MAKEMORE_ADD_PERMISSIONS,
    ):
        _assert_source_unchanged(prepared)
        return memorize_semantic_result(
            store=store,
            operation="makemore",
            source_name=prepared.source_name,
            target=prepared.makemore.target,
            contents=contents,
            source_bindings=bindings,
            operation_args={
                "version": DISTILLED_MAKEMORE_CHECKPOINT_VERSION,
                "source_mode": "DISTILL_THEN_MAKEMORE",
                "distillation": _distillation_checkpoint_payload(prepared.distill),
                **makemore_checkpoint_payload(prepared.result),
            },
            description=(
                f"Added {len(contents)} Makemore Cases from "
                f"{len(prepared.distill.analysis.rules)} transient distilled Rules "
                f"to '{prepared.target_name}'"
            ),
        )


__all__ = [
    "DISTILLED_MAKEMORE_CHECKPOINT_VERSION",
    "DISTILLED_MAKEMORE_PIPELINE_CONTRACT_VERSION",
    "DistilledMakemoreProviderFactory",
    "PreparedDistilledMakemoreAdd",
    "apply_prepared_distilled_makemore_add",
    "prepare_distilled_makemore_add",
]
