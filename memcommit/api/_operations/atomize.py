"""Public structural Atomize assembly without command or TUI dependencies."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from memcommit.api._runtime import ClientRuntime
from memcommit.api._support.errors import raise_public
from memcommit.api.atomize import (
    AtomizeAnalysisResult,
    AtomizeAppliedItemResult,
    AtomizeChildResult,
    AtomizeIssueResult,
    AtomizeItemResult,
    AtomizeOverviewResult,
    AtomizeOverviewSectionResult,
    AtomizeReadingResult,
    AtomizeStructuralApplyResult,
)
from memcommit.api.errors import (
    AtomizeConflictError,
    AtomizeContextError,
    AtomizeExecutionError,
    AtomizeInputError,
    AtomizeProviderFailure,
    AtomizeStorageError,
)
from memcommit.atomize import AtomizeImpactError
from memcommit.atomize_analysis_application import (
    AtomizeAnalysisApplicationError,
    AtomizeAnalysisOpenRequest,
)
from memcommit.atomize_analysis_runtime import execute_atomize_analysis_open
from memcommit.atomize_application import (
    AtomizeApplicationError,
    AtomizePersistedApplyRequest,
    AtomizeSessionSnapshot,
)
from memcommit.atomize_runtime import (
    capture_atomize_session_snapshot,
    capture_atomize_session_snapshot_at_version,
    execute_atomize_session_apply,
)
from memcommit.atomize_workbench import (
    AtomizeWorkbenchError,
    project_atomize_workbench_findings,
)
from memcommit.context_locator import resolve_context_locator
from memcommit.query_provider import QueryProviderError
from memcommit.store import ConcurrentContextUpdateError


class _SafeProvider:
    """Keep caller-owned endpoint failures inside Atomize's public taxonomy."""

    def __init__(self, delegate: object) -> None:
        self._delegate = delegate

    def complete(self, prompt, *, operation, output_schema=None):
        try:
            complete = getattr(self._delegate, "complete")
            return complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )
        except AtomizeProviderFailure:
            raise
        except Exception as error:
            raise_public(AtomizeProviderFailure, error)


def _provider(runtime: ClientRuntime) -> _SafeProvider:
    try:
        return _SafeProvider(runtime.semantic_provider_factory())
    except AtomizeProviderFailure:
        raise
    except Exception as error:
        raise_public(AtomizeProviderFailure, error)


def _load_context(runtime: ClientRuntime, context_name: str | None):
    store = runtime.store
    try:
        current_name = (
            store.current_context_name() if store.state_file.exists() else None
        )
        operand = context_name or current_name
        if operand is None:
            raise FileNotFoundError(
                "No current Context; pass context_name or initialize one."
            )
        # Resolve every relative spelling against the one current-name snapshot
        # captured above. A later global switch must not retarget this call.
        canonical = resolve_context_locator(operand, current=current_name)
        return store.load_direct(canonical)
    except FileNotFoundError as error:
        raise_public(AtomizeContextError, error)
    except OSError as error:
        raise_public(AtomizeStorageError, error)
    except (TypeError, ValueError) as error:
        raise_public(AtomizeInputError, error)


def _overview(analysis) -> AtomizeOverviewResult:
    overview = analysis.overview
    if overview is None:  # pragma: no cover - durable v4 analyses always carry it
        raise AtomizeExecutionError("Atomize analysis has no overview.")

    def section(value) -> AtomizeOverviewSectionResult:
        return AtomizeOverviewSectionResult(
            text=value.text,
            source_memory_uids=value.source_uids,
        )

    return AtomizeOverviewResult(
        understood=section(overview.understood),
        changed=section(overview.changed),
        unresolved=section(overview.unresolved),
    )


def _project(opened, snapshot) -> AtomizeAnalysisResult:
    analysis = opened.analysis
    workbench = opened.workbench
    findings = project_atomize_workbench_findings(analysis)
    return AtomizeAnalysisResult(
        analysis_uid=analysis.uid,
        version=snapshot.version_token,
        origin=opened.origin,
        context_uid=analysis.context_uid,
        context_name=analysis.context_name,
        context_digest=analysis.context_digest,
        ruleset_version=analysis.ruleset_version,
        memory_count=analysis.memory_count,
        projected_memory_count=analysis.projected_memory_count,
        overview=_overview(analysis),
        items=tuple(
            AtomizeItemResult(
                memory_uid=item.memory_uid,
                content=item.content,
                position=item.position,
                classification=item.classification,
                action=item.action,
                reason_codes=item.reason_codes,
                children=tuple(
                    AtomizeChildResult(
                        content=child.content,
                        source_spans=child.source_spans,
                        frame_spans=child.frame_spans,
                    )
                    for child in item.children
                ),
                reason=item.reason,
                lint=item.lint,
            )
            for item in analysis.items
        ),
        issues=tuple(
            AtomizeIssueResult(
                uid=finding.uid,
                kind=finding.kind,
                source_memory_uids=finding.source_uids,
                priority=finding.priority,
                classification=finding.classification,
                reason=finding.reason,
                question=finding.question,
                readings=tuple(
                    AtomizeReadingResult(
                        uid=reading.uid,
                        role=reading.role,
                        label=reading.label,
                        text=reading.text,
                    )
                    for reading in finding.readings
                ),
                answered=(
                    finding.uid in workbench.responses
                    and workbench.responses[finding.uid].answered
                ),
            )
            for finding in findings
        ),
        workbench_uid=workbench.uid,
        output_context_name=workbench.output_context_name,
        in_place_apply_allowed=(
            workbench.output_context_name == analysis.context_name
        ),
        _snapshot=snapshot,
    )


def _raise_execution(error: BaseException) -> None:
    message = str(error).casefold()
    if any(
        marker in message
        for marker in (
            "changed",
            "stale",
            "no longer current",
            "no longer matches",
            "concurrent",
        )
    ):
        raise_public(AtomizeConflictError, error)
    raise_public(AtomizeExecutionError, error)


def open_atomize_analysis(
    runtime: ClientRuntime,
    context_name: str | None = None,
    *,
    refresh: bool = False,
    use_prepared: bool = True,
) -> AtomizeAnalysisResult:
    """Open one exact saved, prepared, or provider-backed analysis pair."""

    if context_name is not None and (
        not isinstance(context_name, str) or not context_name.strip()
    ):
        raise AtomizeInputError(
            "context_name must be nonblank text when supplied."
        )
    if not isinstance(refresh, bool) or not isinstance(use_prepared, bool):
        raise AtomizeInputError("Atomize analysis controls must be booleans.")
    context = _load_context(runtime, context_name)
    try:
        opened = execute_atomize_analysis_open(
            AtomizeAnalysisOpenRequest(
                context=context,
                refresh=refresh,
                # Refresh is an explicit provider request. It dominates the
                # general cache preference instead of exposing an invalid
                # refresh+prepared combination to callers.
                allow_prepared=use_prepared and not refresh,
            ),
            store=runtime.store,
            provider_factory=lambda: _provider(runtime),
        )
        snapshot = capture_atomize_session_snapshot(
            store=runtime.store,
            analysis=opened.analysis,
            expected_workbench=opened.workbench,
        )
        return _project(opened, snapshot)
    except AtomizeProviderFailure:
        raise
    except QueryProviderError as error:
        raise_public(AtomizeProviderFailure, error)
    except FileNotFoundError as error:
        raise_public(AtomizeContextError, error)
    except ConcurrentContextUpdateError as error:
        raise_public(AtomizeConflictError, error)
    except OSError as error:
        raise_public(AtomizeStorageError, error)
    except (
        AtomizeAnalysisApplicationError,
        AtomizeApplicationError,
        AtomizeImpactError,
        AtomizeWorkbenchError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        _raise_execution(error)


def apply_atomize_as_is(
    runtime: ClientRuntime,
    analysis: AtomizeAnalysisResult,
) -> AtomizeStructuralApplyResult:
    """Apply or recover one exact saved structural proposal in place."""

    if not isinstance(analysis, AtomizeAnalysisResult):
        raise AtomizeInputError("analysis must be an AtomizeAnalysisResult.")
    snapshot = analysis._snapshot
    if (
        not isinstance(snapshot, AtomizeSessionSnapshot)
        or analysis.origin not in {"SAVED", "EXACT_PREWARM", "PROVIDER"}
    ):
        raise AtomizeInputError(
            "analysis is not an accepted structural Atomize proposal."
        )
    try:
        expected = _project(
            SimpleNamespace(
                analysis=snapshot.analysis,
                workbench=snapshot.workbench,
                origin=analysis.origin,
            ),
            snapshot,
        )
    except (
        AtomizeExecutionError,
        AtomizeWorkbenchError,
        AttributeError,
        TypeError,
        ValueError,
    ) as error:
        raise_public(AtomizeInputError, error)
    if expected != analysis:
        # Apply is bound to the complete visible proposal, not only a hidden
        # snapshot or caller-controlled eligibility flag.
        raise AtomizeInputError(
            "analysis does not match its accepted Atomize revision."
        )
    if not analysis.in_place_apply_allowed:
        raise AtomizeInputError(
            "This Atomize review has a different Output Context plan. Reopen "
            "it with the CLI/TUI to review Save As; this call applies only in place."
        )
    try:
        current_analysis = runtime.store.load_atomize_analysis(
            snapshot.analysis.context_uid
        )
        current_workbench = (
            runtime.store.load_atomize_workbench(current_analysis)
            if current_analysis is not None
            else None
        )
        if (
            current_analysis == snapshot.analysis
            and snapshot.workbench is not None
            and snapshot.workbench.application is None
            and current_workbench is not None
            and current_workbench.application is not None
            and replace(current_workbench, application=None) == snapshot.workbench
        ):
            # The first call may have committed both effect and receipt before
            # its response was lost. Adopt only the terminal extension of the
            # exact accepted workbench; any other edit remains a conflict.
            snapshot = capture_atomize_session_snapshot(
                store=runtime.store,
                analysis=current_analysis,
                expected_workbench=current_workbench,
            )
    except OSError as error:
        raise_public(AtomizeStorageError, error)
    except (
        AtomizeApplicationError,
        AtomizeImpactError,
        AtomizeWorkbenchError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        _raise_execution(error)
    try:
        applied = execute_atomize_session_apply(
            AtomizePersistedApplyRequest(snapshot=snapshot),
            store=runtime.store,
        )
    except ConcurrentContextUpdateError as error:
        raise_public(AtomizeConflictError, error)
    except OSError as error:
        raise_public(AtomizeStorageError, error)
    except (AtomizeApplicationError, AtomizeImpactError) as error:
        _raise_execution(error)
    except (RuntimeError, TypeError, ValueError) as error:
        raise_public(AtomizeExecutionError, error)

    result = applied.materialization.result
    return AtomizeStructuralApplyResult(
        analysis_uid=result.analysis_uid,
        context_uid=applied.snapshot.analysis.context_uid,
        context_name=applied.materialization.context_name,
        checkpoint_uid=applied.materialization.checkpoint_uid,
        split_count=result.split_count,
        child_count=result.child_count,
        preserved_count=result.preserved_count,
        application_mode=applied.audit.application_mode,
        unresolved_at_apply_count=applied.audit.unresolved_at_apply_count,
        items=tuple(
            AtomizeAppliedItemResult(
                source_memory_uid=item.source_uid,
                classification=item.classification,
                result_memory_uids=item.result_uids,
                result_contents=item.result_contents,
                reason=item.reason,
                reason_codes=item.reason_codes,
            )
            for item in result.items
        ),
        recovered=applied.recovered,
    )


def apply_saved_atomize_as_is(
    runtime: ClientRuntime,
    context_name: str | None = None,
    *,
    expected_version: str,
) -> AtomizeStructuralApplyResult:
    """Apply one saved proposal by opaque version without provider access."""

    if (
        not isinstance(expected_version, str)
        or len(expected_version) != 64
        or any(character not in "0123456789abcdef" for character in expected_version)
    ):
        raise AtomizeInputError(
            "expected_version must be a 64-character lowercase hexadecimal token."
        )
    if context_name is not None and (
        not isinstance(context_name, str) or not context_name.strip()
    ):
        raise AtomizeInputError(
            "context_name must be nonblank text when supplied."
        )
    context = _load_context(runtime, context_name)
    try:
        analysis = runtime.store.load_atomize_analysis(context.uid)
        if analysis is None:
            raise FileNotFoundError(
                f"No saved atomize analysis exists for {context.name!r}."
            )
        snapshot = capture_atomize_session_snapshot_at_version(
            store=runtime.store,
            analysis=analysis,
            expected_version=expected_version,
        )
        if snapshot.workbench is None:
            raise FileNotFoundError(
                f"No saved atomize workbench exists for {context.name!r}."
            )
        proposal = _project(
            SimpleNamespace(
                analysis=snapshot.analysis,
                workbench=snapshot.workbench,
                origin="SAVED",
            ),
            snapshot,
        )
    except FileNotFoundError as error:
        raise_public(AtomizeContextError, error)
    except OSError as error:
        raise_public(AtomizeStorageError, error)
    except (
        AtomizeApplicationError,
        AtomizeImpactError,
        AtomizeWorkbenchError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        _raise_execution(error)
    return apply_atomize_as_is(runtime, proposal)


__all__ = [
    "apply_atomize_as_is",
    "apply_saved_atomize_as_is",
    "open_atomize_analysis",
]
