"""Production MemoryStore and provider composition for Distill."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
from typing import Iterator, Protocol
import uuid

from memcommit.context import AutoCheckpoint, Context, Memory
from memcommit.distill import DistillError, DistillProvider
from memcommit.distill_application import (
    DistillApplyReceipt,
    DistillApplyRequest,
    DistillRequest,
    DistillResult,
    apply_distill,
    run_distill,
)
from memcommit.store import MemoryStore, context_record_digest, validate_context_name
from memcommit.summarize_application import (
    FrozenSummarySource,
    SummarizeRequest,
    SummarySourcePort,
)
from memcommit.summarize_runtime import MemoryStoreSummarySourcePort


class DistillProviderFactory(Protocol):
    def __call__(self) -> DistillProvider:
        """Construct the configured provider lazily."""


@dataclass
class LocalMemoryStoreDistillSourcePort:
    """Keep the first Distill slice inside one locally owned Store."""

    store: MemoryStore
    delegate: MemoryStoreSummarySourcePort

    @classmethod
    def capture(cls, store: MemoryStore) -> "LocalMemoryStoreDistillSourcePort":
        return cls(store=store, delegate=MemoryStoreSummarySourcePort.capture(store))

    def freeze(self, request: SummarizeRequest) -> FrozenSummarySource:
        source = self.delegate.freeze(request)
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
        return source

    def revalidate(self, source: FrozenSummarySource):
        return self.delegate.revalidate(source)


def execute_distill(
    request: DistillRequest,
    *,
    store: MemoryStore,
    provider_factory: DistillProviderFactory,
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
        validate_context_name(request.output_name)
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
                    "goal_support": rule.goal_support,
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
                        "version": 1,
                        "context_uid": output.uid,
                        "context_name": output.name,
                    },
                    "distill": {
                        "version": 1,
                        "analysis_uid": analysis.uid,
                        "analysis_digest": analysis.digest,
                        "provider_contract_version": analysis.provider_contract_version,
                        "source_context": analysis.source.context_name,
                        "source_digest": analysis.source.digest,
                        "source_scope": (
                            "INCLUDE_DESCENDANTS"
                            if analysis.source.include_descendants
                            else "THIS_CONTEXT_ONLY"
                        ),
                        "goal": analysis.goal,
                        "goal_digest": goal_digest,
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
