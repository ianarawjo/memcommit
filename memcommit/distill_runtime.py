"""Production MemoryStore and provider composition for Distill."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
from typing import Iterator, Protocol
import uuid

from memcommit.context import AutoCheckpoint, Context, Memory
from memcommit.context_naming import validate_portable_context_name
from memcommit.distill import (
    DistillAnalysis,
    DistillError,
    DistillProvider,
    ensure_distill_goal_fit_allows_add,
)
from memcommit.distill_application import (
    DistillApplyReceipt,
    DistillApplyRequest,
    DistillRequest,
    DistillResult,
    DistillPreparedLookup,
    apply_distill,
    run_distill,
)
from memcommit.distill_config import (
    DEFAULT_DISTILL_SEMANTIC_CONFIG,
    DistillSemanticConfig,
)
from memcommit.semantic_add_runtime import (
    FrozenSemanticAddTarget,
    SemanticAddReceipt,
    append_semantic_memories,
    freeze_semantic_add_target,
)
from memcommit.store import MemoryStore, context_record_digest
from memcommit.operations.summarize.application import (
    FrozenSummarySource,
    SummarizeRequest,
    SummarySourcePort,
)
from memcommit.operations.summarize.runtime import MemoryStoreSummarySourcePort


class DistillProviderFactory(Protocol):
    def __call__(self) -> DistillProvider:
        """Construct the configured provider lazily."""


@dataclass(frozen=True)
class _LocalDistillSourceToken:
    """Delegate binding plus exact local Context bytes used by Distill."""

    delegate: FrozenSummarySource
    local_bindings: tuple[tuple[str, str, str], ...]


@dataclass
class LocalMemoryStoreDistillSourcePort:
    """Keep the first Distill slice inside one locally owned Store."""

    store: MemoryStore
    delegate: MemoryStoreSummarySourcePort

    @classmethod
    def capture(cls, store: MemoryStore) -> "LocalMemoryStoreDistillSourcePort":
        return cls(store=store, delegate=MemoryStoreSummarySourcePort.capture(store))

    def freeze(self, request: SummarizeRequest) -> FrozenSummarySource:
        delegated = self.delegate.freeze(request)
        source = delegated
        names = {
            source.frame.context_name,
            *(item.context_name for item in source.frame.sources),
        }
        if any(not self.store.context_exists(name) for name in names):
            # READ alone is not permission to derive or retain new Rules. A
            # later grant adapter must authorize DERIVE/EXPORT and retention
            # before the provider sees authority-owned content.
            raise DistillError(
                "Distill currently requires an entirely local Source frame; "
                "granted Context distillation is not yet authorized."
            )
        bindings = tuple(
            (
                name,
                context.uid,
                context_record_digest(context),
            )
            for name in sorted(names)
            for context in (self.store.load_direct(name),)
        )
        # Rebuild once after binding every local record. If any visible input
        # changed during capture, the request fails before provider disclosure;
        # later unrelated local drift is caught by the retained record digests.
        current = self.delegate.revalidate(delegated)
        if current != delegated.frame:
            raise DistillError(
                "The Distill Source changed while it was being frozen."
            )
        return FrozenSummarySource(
            frame=delegated.frame,
            token=_LocalDistillSourceToken(
                delegate=delegated,
                local_bindings=bindings,
            ),
        )

    def revalidate(self, source: FrozenSummarySource):
        token = source.token
        if not isinstance(token, _LocalDistillSourceToken):
            raise DistillError("The frozen local Distill Source is invalid.")
        return self.delegate.revalidate(token.delegate)

    def source_bindings(
        self,
        source: FrozenSummarySource,
    ) -> tuple[tuple[str, str, str], ...]:
        token = source.token
        if not isinstance(token, _LocalDistillSourceToken):
            raise DistillError("The frozen local Distill Source is invalid.")
        return token.local_bindings


@dataclass(frozen=True)
class PreparedDistillAdd:
    """Exact Distill result paired with its pre-provider Target snapshot."""

    result: DistillResult
    target: FrozenSemanticAddTarget
    source_port: LocalMemoryStoreDistillSourcePort


def _goal_fit_record(analysis: DistillAnalysis) -> dict[str, object] | None:
    goal_fit = analysis.goal_fit
    if goal_fit is None:
        return None
    return {
        "contract_version": goal_fit.contract_version,
        "verdict": goal_fit.verdict,
        "reason": goal_fit.reason,
        "considered_rule_uids": list(goal_fit.considered_rule_uids),
        "material_rule_uids": list(goal_fit.material_rule_uids),
    }


def prepare_distill_add(
    request: DistillRequest,
    *,
    store: MemoryStore,
    target_name: str,
    provider_factory: DistillProviderFactory,
    config: DistillSemanticConfig = DEFAULT_DISTILL_SEMANTIC_CONFIG,
    prepared_lookup: DistillPreparedLookup | None = None,
) -> PreparedDistillAdd:
    """Freeze both endpoints, then prepare one non-mutating Add proposal."""

    source_port = LocalMemoryStoreDistillSourcePort.capture(store)
    # Target is captured before Source disclosure/provider construction. This
    # makes a successful publication refer to the exact destination the person
    # selected at command entry, including Source == Target.
    target = freeze_semantic_add_target(store, target_name)

    @contextmanager
    def provider_session() -> Iterator[DistillProvider]:
        yield provider_factory()

    result = run_distill(
        request,
        source_port=source_port,
        provider_session_factory=provider_session,
        config=config,
        prepared_lookup=prepared_lookup,
    )
    return PreparedDistillAdd(
        result=result,
        target=target,
        source_port=source_port,
    )


def apply_prepared_distill_add(
    prepared: PreparedDistillAdd,
    *,
    store: MemoryStore,
) -> SemanticAddReceipt:
    """Append the complete supported Rule set to one existing Context."""

    if not isinstance(prepared, PreparedDistillAdd):
        raise TypeError("Distill Add requires a prepared result.")
    analysis = prepared.result.analysis
    if not analysis.rules:
        raise DistillError("Distill produced no supported Rules to add.")
    ensure_distill_goal_fit_allows_add(analysis)
    current = prepared.source_port.revalidate(prepared.result.frozen_source)
    if current.digest != analysis.source.digest or current != analysis.source:
        raise DistillError(
            "The Distill Source changed before Add; no generated Memories "
            "were added."
        )
    source_bindings = prepared.source_port.source_bindings(
        prepared.result.frozen_source
    )
    result_records = [
        {
            "rule_uid": rule.uid,
            "content": rule.content,
            "support_memory_uids": list(rule.support_memory_uids),
            "boundary_memory_uids": list(rule.boundary_memory_uids),
            "rationale": rule.rationale,
        }
        for rule in analysis.rules
    ]
    goal_digest = (
        hashlib.sha256(analysis.goal.encode("utf-8")).hexdigest()
        if analysis.goal is not None
        else None
    )
    return append_semantic_memories(
        store=store,
        operation="distill",
        source_name=analysis.source.context_name,
        target=prepared.target,
        contents=tuple(rule.content for rule in analysis.rules),
        source_bindings=source_bindings,
        operation_args={
            "version": 3,
            "analysis_uid": analysis.uid,
            "analysis_digest": analysis.digest,
            "provider_contract_version": analysis.provider_contract_version,
            "origin": prepared.result.origin,
            "semantic_config": {
                "max_rules": analysis.semantic_config.max_rules,
                "rule_text_limit": analysis.semantic_config.rule_text_limit,
                "rationale_limit": analysis.semantic_config.rationale_limit,
                "overview_limit": analysis.semantic_config.overview_limit,
                "response_char_limit": analysis.semantic_config.response_char_limit,
            },
            "source_digest": analysis.source.digest,
            "overview": analysis.overview,
            "source_scope": (
                "INCLUDE_DESCENDANTS"
                if analysis.source.include_descendants
                else "THIS_CONTEXT_ONLY"
            ),
            "goal": analysis.goal,
            "goal_digest": goal_digest,
            "goal_fit": _goal_fit_record(analysis),
            "rules": result_records,
            "outside_memory_uids": list(analysis.outside_memory_uids),
        },
        description=(
            f"Added {len(analysis.rules)} distilled Rules from "
            f"'{analysis.source.context_name}' to "
            f"'{prepared.target.context_name}'"
        ),
    )


def execute_distill(
    request: DistillRequest,
    *,
    store: MemoryStore,
    provider_factory: DistillProviderFactory,
    config: DistillSemanticConfig = DEFAULT_DISTILL_SEMANTIC_CONFIG,
    prepared_lookup: DistillPreparedLookup | None = None,
) -> DistillResult:
    """Run Distill without importing CLI or terminal presentation."""

    source_port = LocalMemoryStoreDistillSourcePort.capture(store)

    @contextmanager
    def provider_session() -> Iterator[DistillProvider]:
        yield provider_factory()

    return run_distill(
        request,
        source_port=source_port,
        provider_session_factory=provider_session,
        config=config,
        prepared_lookup=prepared_lookup,
    )


def _rule_result_uid(rule_uid: str, analysis_digest: str) -> str:
    return str(uuid.uuid5(uuid.UUID(rule_uid), analysis_digest))


@dataclass
class MemoryStoreDistillOutputPort:
    """Create one local Result while the exact local Source frame stays valid."""

    store: MemoryStore

    def materialize(
        self,
        request: DistillApplyRequest,
        *,
        source_port: SummarySourcePort,
    ) -> DistillApplyReceipt:
        analysis = request.result.analysis
        validate_portable_context_name(request.output_name)
        if request.output_name == analysis.source.context_name:
            raise DistillError("Distill Result must be separate from its Source.")
        if self.store.context_exists(request.output_name):
            raise DistillError(
                f"Distill Result Context already exists: '{request.output_name}'."
            )
        current = source_port.revalidate(request.result.frozen_source)
        if current.digest != analysis.source.digest:
            raise DistillError(
                "The Distill Source changed before Apply; no Result was created."
            )

        # The first durable slice supports local Context frames only. Grant
        # output needs DERIVE/EXPORT plus retained-analysis authority and must
        # not silently fall back to a local copy without those checks.
        context_names = tuple(
            dict.fromkeys(
                [analysis.source.context_name]
                + [source.context_name for source in analysis.source.sources]
            )
        )
        local_bindings: list[tuple[str, str, str]] = []
        for name in context_names:
            if not self.store.context_exists(name):
                raise DistillError(
                    "Durable Distill Apply currently requires an entirely "
                    "local Source frame; granted analysis remains read-only."
                )
            context = self.store.load_direct(name)
            local_bindings.append(
                (name, context.uid, context_record_digest(context))
            )

        output = Context(uid=str(uuid.uuid4()), name=request.output_name)
        result_uids: list[str] = []
        result_records: list[dict[str, object]] = []
        for rule in analysis.rules:
            result_uid = _rule_result_uid(rule.uid, analysis.digest)
            output.add(Memory(uid=result_uid, content=rule.content))
            result_uids.append(result_uid)
            result_records.append(
                {
                    "result_memory_uid": result_uid,
                    "rule_uid": rule.uid,
                    "support_memory_uids": list(rule.support_memory_uids),
                    "boundary_memory_uids": list(rule.boundary_memory_uids),
                    "rationale": rule.rationale,
                }
            )
        goal_digest = (
            hashlib.sha256(analysis.goal.encode("utf-8")).hexdigest()
            if analysis.goal is not None
            else None
        )
        checkpoint = self.store.create_context_with_sources(
            output,
            AutoCheckpoint(
                command="distill",
                args={
                    "context_creation": {
                        "version": 2,
                        "context_uid": output.uid,
                        "context_name": output.name,
                    },
                    "distill": {
                        "version": 1,
                        "analysis_uid": analysis.uid,
                        "analysis_digest": analysis.digest,
                        "provider_contract_version": analysis.provider_contract_version,
                        "semantic_config": {
                            "max_rules": analysis.semantic_config.max_rules,
                            "rule_text_limit": analysis.semantic_config.rule_text_limit,
                            "rationale_limit": analysis.semantic_config.rationale_limit,
                            "overview_limit": analysis.semantic_config.overview_limit,
                            "response_char_limit": analysis.semantic_config.response_char_limit,
                        },
                        "source_context": analysis.source.context_name,
                        "overview": analysis.overview,
                        "source_digest": analysis.source.digest,
                        "source_scope": (
                            "INCLUDE_DESCENDANTS"
                            if analysis.source.include_descendants
                            else "THIS_CONTEXT_ONLY"
                        ),
                        "goal": analysis.goal,
                        "goal_digest": goal_digest,
                        "goal_fit": _goal_fit_record(analysis),
                        "result_context": output.name,
                        "rules": result_records,
                        "outside_memory_uids": list(analysis.outside_memory_uids),
                    },
                },
                description=(
                    f"Created Distill result '{output.name}' from "
                    f"'{analysis.source.context_name}'; source unchanged"
                ),
            ),
            source_bindings=tuple(local_bindings),
        )
        if checkpoint is None:
            raise DistillError("Distill Result creation produced no checkpoint.")
        return DistillApplyReceipt(
            output_name=output.name,
            output_context_uid=output.uid,
            checkpoint_uid=checkpoint.uid,
            result_memory_uids=tuple(result_uids),
        )


def execute_distill_apply(
    request: DistillApplyRequest,
    *,
    store: MemoryStore,
) -> DistillApplyReceipt:
    """Apply one exact Distill result through the require-new Store path."""

    return apply_distill(
        request,
        source_port=LocalMemoryStoreDistillSourcePort.capture(store),
        output_port=MemoryStoreDistillOutputPort(store),
    )
