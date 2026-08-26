"""Prewarm one exact full-Context Compare pair for an active Study run.

The participant-facing Compare command already reuses exact saved artifacts.
This setup-only runner moves the first production analysis before the measured
interaction.  It resolves the same local or granted Context accesses, loads
the same descendant projections, and publishes through the same atomic Compare
execution boundary.  It emits only a content-free preparation receipt; the
semantic artifact remains in the active Profile's authorized store.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Protocol
import uuid

from memcommit.operations.compare.ledger.execution import (
    ComparisonExecutionResult,
    ensure_comparison_analysis,
    load_comparison_context,
)
from memcommit.authority.access import ContextAccess, resolve_context_access
from memcommit.operations.compare.ledger.model import ComparisonAnalysis, ComparisonInput
from memcommit.operations.compare.ledger.provider import analyze_comparison
from memcommit.operations.compare.ledger.store import load_comparison_analysis
from memcommit.infrastructure.config import Config
from memcommit.context import Context
from memcommit.operations.compare.ledger.granted_store import load_granted_comparison_artifact
from memcommit.infrastructure.providers.policy import (
    resolve_codex_evaluation_policy,
)
from memcommit.operations.profile.config import load_profile_registry
from memcommit.operations.profile.model import authority_grant_snapshot_lock
from memcommit.infrastructure.providers.types import (
    CODEX_CHATGPT_PROVIDER,
    CODEX_REASONING_EFFORTS,
    CompletionRun,
    ProviderIdentity,
)
from memcommit.infrastructure.providers.subscription import CodexChatGPTProvider
from memcommit.store import MemoryStore


KIND = "STUDY_COMPARE_PREWARM"
SCHEMA_VERSION = 1
DEFAULT_REFERENCE = "task-2/advisor1"
DEFAULT_COMPARED = "task-2/advisor2"
DEFAULT_TIMEOUT_SECONDS = 900.0


class StudyComparePrewarmError(RuntimeError):
    """Safe setup-only prewarm failure."""


class _Provider(Protocol):
    identity: ProviderIdentity
    last_run: CompletionRun | None

    def complete(
        self,
        prompt: str,
        *,
        operation: str,
        output_schema: dict[str, object] | None = None,
    ) -> str: ...


def _json(value: object, *, pretty: bool = False) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
        sort_keys=pretty,
    )


def resolve_pair(
    store: MemoryStore,
    *,
    reference_name: str,
    compared_name: str,
    reference_descendants: bool,
    compared_descendants: bool,
) -> tuple[tuple[ContextAccess, ContextAccess], tuple[Context, Context]]:
    """Freeze and load the exact pair through Compare's production access path."""

    current_name = store.current_context_name()
    with authority_grant_snapshot_lock() as registry:
        reference_access = resolve_context_access(
            store,
            reference_name,
            current_name=current_name,
            required_permission="READ",
            registry=registry,
        )
        compared_access = resolve_context_access(
            store,
            compared_name,
            current_name=current_name,
            required_permission="READ",
            registry=registry,
        )
        reference = load_comparison_context(
            reference_access,
            include_descendants=reference_descendants,
        )
        compared = load_comparison_context(
            compared_access,
            include_descendants=compared_descendants,
        )
    return (reference_access, compared_access), (reference, compared)


def _reload_saved_uid(
    store: MemoryStore,
    accesses: tuple[ContextAccess, ContextAccess],
    contexts: tuple[Context, Context],
) -> str | None:
    reference, compared = contexts
    if any(access.is_granted for access in accesses):
        artifact = load_granted_comparison_artifact(
            store,
            reference.uid,
            compared.uid,
        )
        return artifact.analysis.uid if artifact is not None else None
    analysis = load_comparison_analysis(reference.uid, compared.uid)
    return analysis.uid if analysis is not None else None


def prewarm_pair(
    *,
    store: MemoryStore,
    accesses: tuple[ContextAccess, ContextAccess],
    contexts: tuple[Context, Context],
    include_descendants: tuple[bool, bool],
    analyze: Callable[[ComparisonInput], ComparisonAnalysis],
    profile_name: str,
    requested_model: str,
    requested_reasoning: str,
    refresh: bool = False,
    clock: Callable[[], float] = time.monotonic,
) -> tuple[ComparisonExecutionResult, dict[str, object]]:
    """Publish or reuse one exact artifact and return a content-free receipt."""

    reference_access, compared_access = accesses
    reference, compared = contexts
    provider_calls = 0
    provider_seconds = 0.0
    provider_identity: ProviderIdentity | None = None
    provider_run: CompletionRun | None = None

    def measured_analyze(comparison_input: ComparisonInput) -> ComparisonAnalysis:
        nonlocal provider_calls, provider_seconds, provider_identity, provider_run
        provider_calls += 1
        started = clock()
        analysis = analyze(comparison_input)
        semantic_seconds = max(0.0, clock() - started)
        observed_provider = getattr(analyze, "provider", None)
        observed_seconds = getattr(observed_provider, "provider_seconds", None)
        provider_seconds += (
            float(observed_seconds)
            if isinstance(observed_seconds, (int, float))
            else semantic_seconds
        )
        observed_identity = getattr(observed_provider, "identity", None)
        if isinstance(observed_identity, ProviderIdentity):
            provider_identity = observed_identity
        observed_run = getattr(observed_provider, "last_run", None)
        if isinstance(observed_run, CompletionRun):
            provider_run = observed_run
        return analysis

    started = clock()
    execution = ensure_comparison_analysis(
        store=store,
        reference_access=reference_access,
        compared_access=compared_access,
        reference=reference,
        compared=compared,
        current_name=store.current_context_name(),
        include_descendants=include_descendants,
        refresh=refresh,
        require_durable=True,
        analyze=measured_analyze,
    )
    elapsed = max(0.0, clock() - started)
    if not execution.durable:
        raise StudyComparePrewarmError("Study Compare prewarm was not durable.")
    if not execution.analysis.matches(reference, compared):
        raise StudyComparePrewarmError("Saved prewarm does not match the frozen pair.")
    if execution.analysis.include_descendants != include_descendants:
        raise StudyComparePrewarmError("Saved prewarm has the wrong descendant scope.")
    reloaded_uid = _reload_saved_uid(store, accesses, contexts)
    if reloaded_uid != execution.analysis.uid:
        raise StudyComparePrewarmError("Saved prewarm could not be reloaded exactly.")

    return execution, {
        "kind": KIND,
        "schema_version": SCHEMA_VERSION,
        "receipt_uid": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "profile_name": profile_name,
        "reference": {
            "name": reference.name,
            "context_uid": reference.uid,
            "context_digest": execution.analysis.frames[0].context_digest,
            "memory_count": len(execution.analysis.frames[0].memories),
            "include_descendants": include_descendants[0],
            "granted": reference_access.is_granted,
        },
        "compared": {
            "name": compared.name,
            "context_uid": compared.uid,
            "context_digest": execution.analysis.frames[1].context_digest,
            "memory_count": len(execution.analysis.frames[1].memories),
            "include_descendants": include_descendants[1],
            "granted": compared_access.is_granted,
        },
        "analysis_uid": execution.analysis.uid,
        "ruleset_version": execution.analysis.ruleset_version,
        "reused": execution.reused,
        "durable": execution.durable,
        "retention": execution.retention,
        "provider_calls": provider_calls,
        "requested_provider": CODEX_CHATGPT_PROVIDER,
        "requested_model": requested_model,
        "requested_reasoning": requested_reasoning,
        "observed_provider": (
            asdict(provider_identity) if provider_identity is not None else None
        ),
        "provider_run": asdict(provider_run) if provider_run is not None else None,
        "provider_seconds": provider_seconds,
        "host_seconds": max(0.0, elapsed - provider_seconds),
        "elapsed_seconds": elapsed,
        "refresh_requested": refresh,
        "semantic_content_in_receipt": False,
    }


class _ProviderAnalyzer:
    """Expose provider evidence while remaining a plain analyzer callback."""

    def __init__(self, provider: _Provider):
        self.provider = provider

    def __call__(self, comparison_input: ComparisonInput) -> ComparisonAnalysis:
        return analyze_comparison(comparison_input, self.provider)


class _TimedProvider:
    """Measure only the provider completion inside host analysis and decoding."""

    def __init__(self, provider: _Provider):
        self._provider = provider
        self.identity = provider.identity
        self.last_run: CompletionRun | None = None
        self.provider_seconds = 0.0

    def complete(
        self,
        prompt: str,
        *,
        operation: str,
        output_schema: dict[str, object] | None = None,
    ) -> str:
        started = time.monotonic()
        response = self._provider.complete(
            prompt,
            operation=operation,
            output_schema=output_schema,
        )
        self.provider_seconds += max(0.0, time.monotonic() - started)
        self.last_run = self._provider.last_run
        return response


def write_receipt(path: Path, receipt: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as file:
            file.write(_json(receipt, pretty=True))
            file.write("\n")
    except FileExistsError as error:
        raise StudyComparePrewarmError(
            f"Refusing to overwrite prewarm receipt: {path}"
        ) from error


def _default_output_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("agent-records/outputs/compare-prewarm") / f"{stamp}-task2-full-medium.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prewarm the active Study run's exact full Task 2 Compare artifact."
        )
    )
    parser.add_argument("--reference", default=DEFAULT_REFERENCE)
    parser.add_argument("--compared", default=DEFAULT_COMPARED)
    parser.add_argument(
        "--reference-descendants",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--compared-descendants",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--reasoning",
        choices=CODEX_REASONING_EFFORTS,
        default=None,
    )
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.timeout is not None and args.timeout <= 0:
        print("--timeout must be positive.", file=sys.stderr)
        return 2
    config = Config()
    policy = resolve_codex_evaluation_policy(
        "compare_contexts",
        config=config,
        model=args.model,
        reasoning_effort=args.reasoning,
        timeout_seconds=args.timeout,
    )
    model = policy.model
    reasoning = policy.reasoning_effort
    if not model:
        print("No Codex model configured; pass --model explicitly.", file=sys.stderr)
        return 2
    try:
        registry = load_profile_registry()
        store = MemoryStore(create=False)
        accesses, contexts = resolve_pair(
            store,
            reference_name=args.reference,
            compared_name=args.compared,
            reference_descendants=args.reference_descendants,
            compared_descendants=args.compared_descendants,
        )
        print(
            "PREWARM "
            f"{contexts[0].name} {len(contexts[0].memories)} -> "
            f"{contexts[1].name} {len(contexts[1].memories)} "
            f"model={model} reasoning={reasoning}",
            flush=True,
        )
        provider = _TimedProvider(CodexChatGPTProvider.connect(
            timeout=policy.timeout_seconds,
            model=model,
            reasoning_effort=reasoning,
        ))
        analyzer = _ProviderAnalyzer(provider)
        _, receipt = prewarm_pair(
            store=store,
            accesses=accesses,
            contexts=contexts,
            include_descendants=(
                args.reference_descendants,
                args.compared_descendants,
            ),
            analyze=analyzer,
            profile_name=registry.active.name,
            requested_model=model,
            requested_reasoning=reasoning,
            refresh=args.refresh,
        )
        output = args.output or _default_output_path()
        write_receipt(output, receipt)
    except Exception as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(_json({"output": str(output), **receipt}, pretty=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
