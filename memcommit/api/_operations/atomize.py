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
    AtomizeReviewUpdateResult,
    AtomizeReviewedApplyResult,
    AtomizeSaveAsApplyResult,
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
from memcommit.operations.atomize.application import (
    AtomizeApplicationError,
    AtomizeOutputPlanRequest,
    AtomizePersistedApplyRequest,
    AtomizeResponseUpdateRequest,
    AtomizeSaveAsRequest,
    AtomizeSessionSnapshot,
)
from memcommit.operations.atomize.runtime import (
    capture_current_atomize_session_snapshot_at_version,
    capture_atomize_session_snapshot,
    capture_atomize_session_snapshot_at_version,
    execute_atomize_output_plan_update,
    execute_atomize_response_update,
    execute_atomize_save_as,
    execute_atomize_session_apply,
)
from memcommit.atomize_workbench import (
    ATOMIZE_WORKBENCH_RESPONSE_CHAR_LIMIT,
    AtomizeWorkbenchError,
    atomize_workbench_declared_frames,
    atomize_workbench_response_digest,
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

    def response_for(issue_uid):
        return workbench.responses.get(issue_uid)

    review_edit_allowed = workbench.application is None
    response_reanalysis_allowed = False
    if review_edit_allowed:
        try:
            declared_frames, _declared_origins = atomize_workbench_declared_frames(
                workbench,
                analysis,
            )
        except AtomizeWorkbenchError:
            # Readiness is a projection, not an alternate validator. The exact
            # reanalysis use case retains the actionable failure explanation.
            pass
        else:
            response_reanalysis_allowed = bool(declared_frames)

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
                selected_reading_uid=(
                    None
                    if response_for(finding.uid) is None
                    else response_for(finding.uid).selected_choice_uid
                ),
                response_text=(
                    ""
                    if response_for(finding.uid) is None
                    else response_for(finding.uid).text
                ),
            )
            for finding in findings
        ),
        workbench_uid=workbench.uid,
        output_context_name=workbench.output_context_name,
        review_edit_allowed=review_edit_allowed,
        response_reanalysis_allowed=response_reanalysis_allowed,
        application_completed=workbench.application is not None,
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


def _validate_version(expected_version: object) -> str:
    if (
        not isinstance(expected_version, str)
        or len(expected_version) != 64
        or any(character not in "0123456789abcdef" for character in expected_version)
    ):
        raise AtomizeInputError(
            "expected_version must be a 64-character lowercase hexadecimal token."
        )
    return expected_version


def _saved_snapshot(
    runtime: ClientRuntime,
    context_name: str | None,
    *,
    expected_version: str,
    terminal_retry: bool = False,
):
    validated_version = _validate_version(expected_version)
    context = _load_context(runtime, context_name)
    try:
        analysis = runtime.store.load_atomize_analysis(context.uid)
        if analysis is None:
            raise FileNotFoundError(
                f"No saved atomize analysis exists for {context.name!r}."
            )
        capture = (
            capture_atomize_session_snapshot_at_version
            if terminal_retry
            else capture_current_atomize_session_snapshot_at_version
        )
        snapshot = capture(
            store=runtime.store,
            analysis=analysis,
            expected_version=validated_version,
        )
        if snapshot.workbench is None:
            raise FileNotFoundError(
                f"No saved atomize workbench exists for {context.name!r}."
            )
        return context, snapshot
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


def _saved_proposal(snapshot, *, origin="SAVED") -> AtomizeAnalysisResult:
    return _project(
        SimpleNamespace(
            analysis=snapshot.analysis,
            workbench=snapshot.workbench,
            origin=origin,
        ),
        snapshot,
    )


def _applied_items(result) -> tuple[AtomizeAppliedItemResult, ...]:
    return tuple(
        AtomizeAppliedItemResult(
            source_memory_uid=item.source_uid,
            classification=item.classification,
            result_memory_uids=item.result_uids,
            result_contents=item.result_contents,
            reason=item.reason,
            reason_codes=item.reason_codes,
        )
        for item in result.items
    )


def _adopt_terminal_retry(
    runtime: ClientRuntime,
    snapshot: AtomizeSessionSnapshot,
) -> AtomizeSessionSnapshot:
    """Adopt only the terminal receipt added to one exact reviewed snapshot."""

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
        return capture_atomize_session_snapshot(
            store=runtime.store,
            analysis=current_analysis,
            expected_workbench=current_workbench,
        )
    return snapshot


def open_atomize_analysis(
    runtime: ClientRuntime,
    context_name: str | None = None,
    *,
    refresh: bool = False,
    use_prepared: bool = True,
    memory_selector: str | None = None,
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
    if memory_selector is not None and (
        not isinstance(memory_selector, str) or not memory_selector.strip()
    ):
        raise AtomizeInputError(
            "memory_selector must be nonblank text when supplied."
        )
    context = _load_context(runtime, context_name)
    try:
        opened = execute_atomize_analysis_open(
            AtomizeAnalysisOpenRequest(
                context=context,
                refresh=refresh,
                memory_selector=memory_selector,
                # Refresh is an explicit provider request. It dominates the
                # general cache preference instead of exposing an invalid
                # refresh+prepared combination to callers.
                allow_prepared=(
                    use_prepared and not refresh and memory_selector is None
                ),
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
            "This Atomize review has a different Output Context plan. Use "
            "save_saved_atomize_as with the exact reviewed version; this call "
            "applies only in place."
        )
    try:
        # The first call may have committed both effect and receipt before its
        # response was lost. No other workbench extension is accepted.
        snapshot = _adopt_terminal_retry(runtime, snapshot)
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
            provider_factory=lambda: _provider(runtime),
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
        dedun_group_count=(
            0 if result.normal_form is None else result.normal_form.dedun_group_count
        ),
        absorbed_count=(
            0 if result.normal_form is None else result.normal_form.absorbed_count
        ),
        normal_form_verified=result.normal_form is not None,
        application_mode=applied.audit.application_mode,
        unresolved_at_apply_count=applied.audit.unresolved_at_apply_count,
        items=_applied_items(result),
        recovered=applied.recovered,
    )


def update_atomize_response(
    runtime: ClientRuntime,
    context_name: str | None = None,
    *,
    expected_version: str,
    issue_uid: str,
    option_uid: str | None,
    comment: str,
) -> AtomizeReviewUpdateResult:
    """Replace or clear one exact saved issue response without a provider."""

    if not isinstance(issue_uid, str) or not issue_uid.strip():
        raise AtomizeInputError("issue_uid must be nonblank text.")
    if option_uid is not None and (
        not isinstance(option_uid, str) or not option_uid.strip()
    ):
        raise AtomizeInputError("option_uid must be nonblank text when supplied.")
    if not isinstance(comment, str):
        raise AtomizeInputError("comment must be text.")
    if len(comment) > ATOMIZE_WORKBENCH_RESPONSE_CHAR_LIMIT:
        raise AtomizeInputError(
            "comment exceeds the Atomize workbench character limit."
        )
    _context, snapshot = _saved_snapshot(
        runtime,
        context_name,
        expected_version=expected_version,
    )
    workbench = snapshot.workbench
    assert workbench is not None
    issue = next(
        (candidate for candidate in workbench.issues if candidate.uid == issue_uid),
        None,
    )
    if issue is None:
        raise AtomizeInputError("issue_uid is not present in this Atomize review.")
    if option_uid is not None and option_uid not in issue.choice_uids:
        raise AtomizeInputError("option_uid does not belong to the selected issue.")
    try:
        updated = execute_atomize_response_update(
            AtomizeResponseUpdateRequest(
                snapshot=snapshot,
                issue_uid=issue_uid,
                option_uid=option_uid,
                comment=comment,
            ),
            store=runtime.store,
        )
        return AtomizeReviewUpdateResult(
            kind="RESPONSE",
            changed=updated.changed,
            proposal=_saved_proposal(updated.snapshot),
        )
    except OSError as error:
        raise_public(AtomizeStorageError, error)
    except (AtomizeApplicationError, AtomizeWorkbenchError) as error:
        _raise_execution(error)
    except (RuntimeError, TypeError, ValueError) as error:
        raise_public(AtomizeExecutionError, error)


def plan_atomize_output(
    runtime: ClientRuntime,
    context_name: str | None = None,
    *,
    expected_version: str,
    output_context_name: str,
) -> AtomizeReviewUpdateResult:
    """Set one exact in-place or require-new Output plan without a provider."""

    if not isinstance(output_context_name, str) or not output_context_name.strip():
        raise AtomizeInputError("output_context_name must be nonblank text.")
    context, snapshot = _saved_snapshot(
        runtime,
        context_name,
        expected_version=expected_version,
    )
    if output_context_name != context.name:
        try:
            runtime.store.assert_context_creatable(output_context_name)
        except (FileExistsError, TypeError, ValueError) as error:
            raise_public(AtomizeInputError, error)
        except OSError as error:
            raise_public(AtomizeStorageError, error)
        except RuntimeError as error:
            raise_public(AtomizeInputError, error)
    try:
        updated = execute_atomize_output_plan_update(
            AtomizeOutputPlanRequest(
                snapshot=snapshot,
                output_context_name=output_context_name,
            ),
            store=runtime.store,
        )
        return AtomizeReviewUpdateResult(
            kind="OUTPUT",
            changed=updated.changed,
            proposal=_saved_proposal(updated.snapshot),
        )
    except OSError as error:
        raise_public(AtomizeStorageError, error)
    except (AtomizeApplicationError, AtomizeWorkbenchError) as error:
        _raise_execution(error)
    except (RuntimeError, TypeError, ValueError) as error:
        raise_public(AtomizeExecutionError, error)


def reanalyze_atomize_responses(
    runtime: ClientRuntime,
    context_name: str | None = None,
    *,
    expected_version: str,
) -> AtomizeAnalysisResult:
    """Incorporate exact saved unary responses through one provider turn."""

    context, snapshot = _saved_snapshot(
        runtime,
        context_name,
        expected_version=expected_version,
    )
    workbench = snapshot.workbench
    assert workbench is not None
    if workbench.application is not None:
        raise AtomizeInputError("An applied Atomize review cannot be reanalyzed.")
    try:
        declared_frames, declared_origins = atomize_workbench_declared_frames(
            workbench,
            snapshot.analysis,
        )
    except AtomizeWorkbenchError as error:
        raise_public(AtomizeInputError, error)
    if not declared_frames:
        raise AtomizeInputError(
            "The Atomize review has no answered unary response to incorporate."
        )
    source_review_digest = atomize_workbench_response_digest(workbench)

    try:
        opened = execute_atomize_analysis_open(
            AtomizeAnalysisOpenRequest(
                context=context,
                refresh=True,
                declared_frames=declared_frames,
                declared_frame_origins=declared_origins,
                source_review_uid=workbench.uid,
                source_review_digest=source_review_digest,
                output_context_name=workbench.output_context_name,
                allow_prepared=False,
            ),
            store=runtime.store,
            provider_factory=lambda: _provider(runtime),
            expected_session=snapshot,
        )
        committed = capture_atomize_session_snapshot(
            store=runtime.store,
            analysis=opened.analysis,
            expected_workbench=opened.workbench,
        )
        return _project(opened, committed)
    except AtomizeProviderFailure:
        raise
    except QueryProviderError as error:
        raise_public(AtomizeProviderFailure, error)
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


def save_saved_atomize_as(
    runtime: ClientRuntime,
    context_name: str | None = None,
    *,
    expected_version: str,
) -> AtomizeSaveAsApplyResult:
    """Publish or recover the exact reviewed require-new Output plan."""

    context, snapshot = _saved_snapshot(
        runtime,
        context_name,
        expected_version=expected_version,
        terminal_retry=True,
    )
    workbench = snapshot.workbench
    assert workbench is not None
    destination = workbench.output_context_name
    if destination == context.name:
        raise AtomizeInputError(
            "The reviewed Atomize Output is in place; use apply_as_is instead."
        )
    expected_current = (
        runtime.store.current_context_name()
        if runtime.store.state_file.exists()
        else None
    )
    try:
        snapshot = _adopt_terminal_retry(runtime, snapshot)
        applied = execute_atomize_save_as(
            AtomizeSaveAsRequest(
                snapshot=snapshot,
                destination_name=destination,
                expected_current=expected_current,
            ),
            store=runtime.store,
            provider_factory=lambda: _provider(runtime),
        )
        result = applied.materialization.result
        return AtomizeSaveAsApplyResult(
            analysis_uid=result.analysis_uid,
            source_context_uid=context.uid,
            source_context_name=context.name,
            context_uid=applied.output_analysis.context_uid,
            context_name=applied.materialization.context_name,
            checkpoint_uid=applied.materialization.checkpoint_uid,
            split_count=result.split_count,
            child_count=result.child_count,
            preserved_count=result.preserved_count,
            dedun_group_count=(
                0
                if result.normal_form is None
                else result.normal_form.dedun_group_count
            ),
            absorbed_count=(
                0
                if result.normal_form is None
                else result.normal_form.absorbed_count
            ),
            normal_form_verified=result.normal_form is not None,
            application_mode=applied.audit.application_mode,
            unresolved_at_apply_count=applied.audit.unresolved_at_apply_count,
            items=_applied_items(result),
            recovered=applied.recovered,
            current_context_name=runtime.store.current_context_name(),
        )
    except ConcurrentContextUpdateError as error:
        raise_public(AtomizeConflictError, error)
    except OSError as error:
        raise_public(AtomizeStorageError, error)
    except (AtomizeApplicationError, AtomizeImpactError) as error:
        _raise_execution(error)
    except (RuntimeError, TypeError, ValueError) as error:
        raise_public(AtomizeExecutionError, error)


def incorporate_and_apply_atomize(
    runtime: ClientRuntime,
    context_name: str | None = None,
    *,
    expected_version: str,
) -> AtomizeReviewedApplyResult:
    """Reanalyze exact responses and immediately apply the resulting plan."""

    proposal = reanalyze_atomize_responses(
        runtime,
        context_name,
        expected_version=expected_version,
    )
    if proposal.in_place_apply_allowed:
        application = apply_atomize_as_is(runtime, proposal)
    else:
        application = save_saved_atomize_as(
            runtime,
            proposal.context_name,
            expected_version=proposal.version,
        )
    return AtomizeReviewedApplyResult(
        proposal=proposal,
        application=application,
    )


def apply_saved_atomize_as_is(
    runtime: ClientRuntime,
    context_name: str | None = None,
    *,
    expected_version: str,
) -> AtomizeStructuralApplyResult:
    """Apply one saved proposal by opaque version without provider access."""

    _context, snapshot = _saved_snapshot(
        runtime,
        context_name,
        expected_version=expected_version,
        terminal_retry=True,
    )
    proposal = _saved_proposal(snapshot)
    return apply_atomize_as_is(runtime, proposal)


__all__ = [
    "apply_atomize_as_is",
    "apply_saved_atomize_as_is",
    "incorporate_and_apply_atomize",
    "open_atomize_analysis",
    "plan_atomize_output",
    "reanalyze_atomize_responses",
    "save_saved_atomize_as",
    "update_atomize_response",
]
