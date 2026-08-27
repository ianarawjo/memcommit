"""Operation-owned assembly for the public Compare lifecycle."""

from __future__ import annotations

from memcommit.adapters.python_api._runtime import ClientRuntime
from memcommit.adapters.python_api._support.errors import raise_public
from memcommit.adapters.python_api.compare import (
    ComparisonFrameResult,
    ComparisonIssueResult,
    ComparisonMemberResult,
    ComparisonOptionResult,
    ComparisonRelationResult,
    ComparisonReportsResult,
    ComparisonResult,
)
from memcommit.adapters.python_api.errors import (
    CompareAuthorityError,
    CompareConflictError,
    CompareContextError,
    CompareExecutionError,
    CompareInputError,
    CompareProviderFailure,
    CompareStorageError,
)
from memcommit.application.authority.access import resolve_context_access
from memcommit.application.operations.compare.ledger.model import (
    ComparisonError,
    comparison_canonical_digest,
)
from memcommit.application.operations.compare.ledger.execution import (
    ComparisonExecutionResult,
    connect_comparison_provider,
    ensure_comparison_analysis,
    load_comparison_context,
)
from memcommit.application.operations.compare.ledger.provider import (
    ComparisonProviderError,
    analyze_comparison,
)
from memcommit.application.operations.compare.ledger.session_application import (
    ComparisonSessionConflictError,
    ComparisonSessionInputError,
    ComparisonSessionUnavailableError,
    open_comparison_session,
    prepare_comparison_refresh,
)
from memcommit.application.operations.compare.ledger.store import (
    ConcurrentComparisonUpdateError,
)
from memcommit.application.context_locator import resolve_context_locator
from memcommit.application.operations.compare.ledger.granted_store import (
    load_granted_comparison_artifact,
)
from memcommit.application.operations.profile.model import (
    ProfileError,
    authority_grant_snapshot_lock,
)
from memcommit.study_scenarios.legacy.prewarm.compare import (
    EquivalentComparePrewarmMatch,
    find_declared_equivalent_compare_analysis,
    installed_compare_prewarm_origin,
    project_declared_compare_analysis,
    record_equivalent_compare_prewarm,
    record_exact_compare_prewarm,
)
from memcommit.study_scenarios.legacy.prewarm.registry import StudyPrewarmRegistryError


def _raise(error_type: type[Exception], error: BaseException) -> None:
    raise_public(error_type, error)


def _current_context_name(runtime: ClientRuntime) -> str | None:
    if not runtime.store.state_file.exists():
        return None
    try:
        return runtime.store.current_context_name()
    except (OSError, ValueError) as error:
        _raise(CompareStorageError, error)


def _project_comparison(
    execution: ComparisonExecutionResult,
    *,
    origin: str | None = None,
) -> ComparisonResult:
    analysis = execution.analysis
    reports = analysis.reports
    return ComparisonResult(
        analysis_uid=analysis.uid,
        version=comparison_canonical_digest(analysis.to_dict()),
        ruleset_version=analysis.ruleset_version,
        frames=tuple(  # type: ignore[arg-type]
            ComparisonFrameResult(
                uid=frame.uid,
                side=frame.side,
                context_name=frame.context_name,
                memory_uids=tuple(memory.uid for memory in frame.memories),
                selected_memory_uid=frame.selected_memory_uid,
            )
            for frame in analysis.frames
        ),
        include_descendants=analysis.include_descendants,
        overview=analysis.overview,
        reports=(
            ComparisonReportsResult(
                both=reports.both,
                differences=reports.differences,
                reference_only=reports.reference_only,
                compared_only=reports.compared_only,
            )
            if reports is not None
            else None
        ),
        relations=tuple(
            ComparisonRelationResult(
                uid=relation.uid,
                kind=relation.kind,
                status=relation.status,
                members=tuple(
                    ComparisonMemberResult(
                        frame_uid=member.frame_uid,
                        memory_uid=member.memory_uid,
                    )
                    for member in relation.members
                ),
                summary=relation.summary,
                reason=relation.reason,
            )
            for relation in analysis.relations
        ),
        issues=tuple(
            ComparisonIssueResult(
                uid=issue.uid,
                relation_uids=issue.relation_uids,
                priority=issue.priority,
                title=issue.title,
                question=issue.question,
                why_it_matters=issue.why_it_matters,
                options=tuple(
                    ComparisonOptionResult(
                        uid=option.uid,
                        label=option.label,
                        text=option.text,
                    )
                    for option in issue.options
                ),
            )
            for issue in analysis.issues
        ),
        origin=origin or execution.origin,
        durable=execution.durable,
        retention=execution.retention,
    )


def _analyze(runtime: ClientRuntime, comparison_input):
    try:
        provider = connect_comparison_provider(runtime.semantic_provider_factory)
        return analyze_comparison(comparison_input, provider)
    except ComparisonProviderError:
        raise
    except Exception as error:
        raise ComparisonProviderError(str(error)) from error


def _execute(
    runtime: ClientRuntime,
    reference_name: str,
    compared_name: str,
    *,
    reference_descendants: bool,
    compared_descendants: bool,
    reference_memory: str | None,
    compared_memory: str | None,
    refresh: bool,
    expected_version: str | None,
) -> ComparisonResult:
    current_name = _current_context_name(runtime)
    reference = resolve_context_locator(reference_name, current=current_name)
    compared = resolve_context_locator(compared_name, current=current_name)
    with authority_grant_snapshot_lock() as registry:
        reference_access = resolve_context_access(
            runtime.store,
            reference,
            current_name=current_name,
            required_permission="READ",
            registry=registry,
        )
        compared_access = resolve_context_access(
            runtime.store,
            compared,
            current_name=current_name,
            required_permission="READ",
            registry=registry,
        )
        reference_context = load_comparison_context(
            reference_access,
            include_descendants=reference_descendants,
            registry=registry,
        )
        compared_context = load_comparison_context(
            compared_access,
            include_descendants=compared_descendants,
            registry=registry,
        )
        registry_snapshot = registry

    equivalent_match: EquivalentComparePrewarmMatch | None = None

    def equivalent(comparison_input):
        nonlocal equivalent_match
        equivalent_match = find_declared_equivalent_compare_analysis(
            store=runtime.store,
            comparison_input=comparison_input,
            current_name=current_name,
            registry_snapshot=registry_snapshot,
        )
        return equivalent_match.analysis if equivalent_match is not None else None

    execution = ensure_comparison_analysis(
        store=runtime.store,
        reference_access=reference_access,
        compared_access=compared_access,
        reference=reference_context,
        compared=compared_context,
        current_name=current_name,
        include_descendants=(reference_descendants, compared_descendants),
        memory_selectors=(reference_memory, compared_memory),
        refresh=refresh,
        expected_version=expected_version,
        analyze=lambda comparison_input: _analyze(runtime, comparison_input),
        equivalent=(
            equivalent if reference_memory is None and compared_memory is None else None
        ),
        project=(
            (
                lambda comparison_input: project_declared_compare_analysis(
                    store=runtime.store,
                    comparison_input=comparison_input,
                    current_name=current_name,
                    registry_snapshot=registry_snapshot,
                )
            )
            if reference_memory is None and compared_memory is None
            else None
        ),
    )
    if execution.origin == "EQUIVALENT_SCOPE_PREWARM" and equivalent_match is not None:
        if equivalent_match.origin == "EXACT_PREWARM":
            record_exact_compare_prewarm(
                runtime.store,
                entry_key=equivalent_match.entry_key,
                analysis=execution.analysis,
            )
        else:
            record_equivalent_compare_prewarm(
                runtime.store,
                entry_key=equivalent_match.entry_key,
                analysis=execution.analysis,
                prepared_context_names=equivalent_match.prepared_context_names,
            )
    return _project_comparison(
        execution,
        origin=(
            installed_compare_prewarm_origin(runtime.store, execution.analysis)
            or execution.origin
        ),
    )


def _validate_request(
    reference_context: str,
    compared_context: str,
    *,
    reference_descendants: bool,
    compared_descendants: bool,
    reference_memory: str | None,
    compared_memory: str | None,
) -> None:
    if any(
        not isinstance(value, str) or not value.strip()
        for value in (reference_context, compared_context)
    ):
        raise CompareInputError("Compare Context locators must be nonblank text.")
    if (
        type(reference_descendants) is not bool
        or type(compared_descendants) is not bool
    ):
        raise CompareInputError("Compare descendant controls must be booleans.")
    for value, label in (
        (reference_memory, "reference_memory"),
        (compared_memory, "compared_memory"),
    ):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise CompareInputError(f"{label} must be nonblank text when supplied.")
    if reference_memory is not None and reference_descendants:
        raise CompareInputError(
            "reference_memory cannot be combined with reference_descendants."
        )
    if compared_memory is not None and compared_descendants:
        raise CompareInputError(
            "compared_memory cannot be combined with compared_descendants."
        )


def compare_contexts(
    runtime: ClientRuntime,
    reference_context: str,
    compared_context: str,
    *,
    reference_descendants: bool = False,
    compared_descendants: bool = False,
    reference_memory: str | None = None,
    compared_memory: str | None = None,
) -> ComparisonResult:
    """Reuse or create one complete ordered read-only Compare analysis."""

    _validate_request(
        reference_context,
        compared_context,
        reference_descendants=reference_descendants,
        compared_descendants=compared_descendants,
        reference_memory=reference_memory,
        compared_memory=compared_memory,
    )
    try:
        return _execute(
            runtime,
            reference_context,
            compared_context,
            reference_descendants=reference_descendants,
            compared_descendants=compared_descendants,
            reference_memory=reference_memory,
            compared_memory=compared_memory,
            refresh=False,
            expected_version=None,
        )
    except CompareProviderFailure:
        raise
    except ComparisonProviderError as error:
        _raise(CompareProviderFailure, error)
    except FileNotFoundError as error:
        _raise(CompareContextError, error)
    except ProfileError as error:
        _raise(CompareAuthorityError, error)
    except ConcurrentComparisonUpdateError as error:
        _raise(CompareConflictError, error)
    except OSError as error:
        _raise(CompareStorageError, error)
    except (ComparisonError, TypeError, ValueError) as error:
        _raise(CompareExecutionError, error)
    except StudyPrewarmRegistryError as error:
        _raise(CompareExecutionError, error)


def open_comparison(
    runtime: ClientRuntime,
    analysis_uid: str,
) -> ComparisonResult:
    """Open one exact current durable analysis without provider or mutation."""

    try:
        snapshot = open_comparison_session(analysis_uid, store=runtime.store)
        analysis = snapshot.analysis
        granted = load_granted_comparison_artifact(
            runtime.store,
            analysis.frames[0].context_uid,
            analysis.frames[1].context_uid,
        )
        return _project_comparison(
            ComparisonExecutionResult(
                analysis=analysis,
                reused=True,
                durable=True,
                retention=granted.retention if granted is not None else None,
                origin="SAVED_OPEN",
            )
        )
    except ComparisonSessionInputError as error:
        _raise(CompareInputError, error)
    except ComparisonSessionUnavailableError as error:
        _raise(CompareContextError, error)
    except ComparisonSessionConflictError as error:
        _raise(CompareConflictError, error)
    except ProfileError as error:
        _raise(CompareAuthorityError, error)
    except OSError as error:
        _raise(CompareStorageError, error)
    except (ComparisonError, TypeError, ValueError) as error:
        _raise(CompareExecutionError, error)


def refresh_comparison(
    runtime: ClientRuntime,
    analysis_uid: str,
    *,
    expected_version: str,
) -> ComparisonResult:
    """Refresh exactly one reviewed latest-pair slot and replace it by CAS."""

    try:
        snapshot = prepare_comparison_refresh(
            analysis_uid,
            expected_version,
            store=runtime.store,
        )
        analysis = snapshot.analysis
        selectors = tuple(frame.selected_memory_uid for frame in analysis.frames)
        return _execute(
            runtime,
            analysis.frames[0].context_name,
            analysis.frames[1].context_name,
            reference_descendants=analysis.include_descendants[0],
            compared_descendants=analysis.include_descendants[1],
            reference_memory=selectors[0],
            compared_memory=selectors[1],
            refresh=True,
            expected_version=snapshot.version_token,
        )
    except CompareProviderFailure:
        raise
    except ComparisonSessionInputError as error:
        _raise(CompareInputError, error)
    except (ComparisonSessionConflictError, ConcurrentComparisonUpdateError) as error:
        _raise(CompareConflictError, error)
    except ComparisonProviderError as error:
        _raise(CompareProviderFailure, error)
    except FileNotFoundError as error:
        _raise(CompareContextError, error)
    except ProfileError as error:
        _raise(CompareAuthorityError, error)
    except OSError as error:
        _raise(CompareStorageError, error)
    except (ComparisonError, TypeError, ValueError) as error:
        _raise(CompareExecutionError, error)
    except StudyPrewarmRegistryError as error:
        _raise(CompareExecutionError, error)


__all__ = ["compare_contexts", "open_comparison", "refresh_comparison"]
