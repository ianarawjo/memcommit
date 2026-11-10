"""Production Store adapters for structural Atomize application."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from memcommit.core.json_objects import canonical_json_digest
from memcommit.application.operations.atomize.domain import (
    AppliedAtomizeItem,
    AtomizeAnalysisSession,
    AtomizeApplyResult,
    AtomizeImpactError,
    AtomizeNormalFormAudit,
    AtomizeProvider,
)
from memcommit.application.operations.atomize.normal_form import (
    project_atomize_normal_form,
)
from memcommit.application.operations.atomize.application import (
    AtomizeApplicationAudit,
    AtomizeApplicationError,
    AtomizeInPlaceRequest,
    AtomizeInPlaceResult,
    AtomizeMaterialization,
    AtomizeRecordApplyRequest,
    AtomizeRecordApplyResult,
    AtomizeExecutionSnapshot,
    run_atomize_record_apply,
)
from memcommit.application.operations.atomize.analysis_application import (
    AtomizeAnalysisOpenRequest,
)
from memcommit.application.operations.atomize.analysis_runtime import (
    execute_atomize_analysis_open,
    requested_atomize_memory_uids,
)
from memcommit.application.operations.atomize.records import (
    AtomizeReviewRecord,
)
from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest
from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.application.operations.review.model import direct_context_digest
from memcommit.persistence.store import (
    ProfileStore,
    _fsync_directory,
    _write_json_atomic,
    context_record_digest,
)


def _session_version_token(
    analysis: AtomizeAnalysisSession,
    workbench: AtomizeReviewRecord | None,
) -> str:
    payload = {
        "analysis": analysis.to_dict(),
        "workbench": None if workbench is None else workbench.to_dict(),
    }
    return canonical_json_digest(payload)


@dataclass
class MemoryStoreAtomizeRecordRepository:
    """Treat the saved analysis/workbench pair as one opaque CAS snapshot."""

    store: ProfileStore

    def _load_unlocked(
        self,
        expected: AtomizeAnalysisSession,
    ) -> AtomizeExecutionSnapshot:
        analysis = self.store.load_atomize_analysis(expected.context_uid)
        if analysis is None or analysis.uid != expected.uid:
            raise AtomizeApplicationError(
                "The accepted Atomize analysis is no longer current."
            )
        workbench = self.store.load_atomize_workbench(analysis)
        return AtomizeExecutionSnapshot(
            analysis=analysis,
            review_record=workbench,
            version_token=_session_version_token(analysis, workbench),
        )

    def load(
        self,
        analysis: AtomizeAnalysisSession,
    ) -> AtomizeExecutionSnapshot:
        with self.store._atomize_session_write_lock(analysis.context_uid):  # noqa: SLF001
            return self._load_unlocked(analysis)

    def capture(
        self,
        analysis: AtomizeAnalysisSession,
        expected_review_record: AtomizeReviewRecord | None,
    ) -> AtomizeExecutionSnapshot:
        """Freeze only the exact revision an interface actually accepted."""

        snapshot = self.load(analysis)
        if (
            snapshot.analysis != analysis
            or snapshot.review_record != expected_review_record
        ):
            raise AtomizeApplicationError(
                "The Atomize analysis or workbench changed before approval "
                "could be frozen. Reopen the review."
            )
        return snapshot

    def replace_application(
        self,
        workbench: AtomizeReviewRecord,
        *,
        analysis: AtomizeAnalysisSession,
        expected_version: str,
    ) -> AtomizeExecutionSnapshot:
        with self.store._atomize_session_write_lock(analysis.context_uid):  # noqa: SLF001
            current = self._load_unlocked(analysis)
            if current.version_token != expected_version:
                raise AtomizeApplicationError(
                    "The Atomize session changed before its terminal receipt "
                    "could be saved."
                )
            if workbench.application is None:
                raise AtomizeApplicationError(
                    "Atomize terminal persistence requires an application receipt."
                )
            self.store._save_atomize_workbench_locked(workbench)  # noqa: SLF001
            committed = self._load_unlocked(analysis)
            if committed.review_record != workbench:
                raise AtomizeApplicationError(
                    "Atomize terminal persistence returned a different workbench."
                )
            return committed


@dataclass
class MemoryStoreAtomizeOutputPort:
    """Create, recover, or compensate one local in-place Atomize checkpoint."""

    store: ProfileStore
    provider_factory: Callable[[], AtomizeProvider]

    @staticmethod
    def _checkpoint_command_details(
        analysis: AtomizeAnalysisSession,
        result: AtomizeApplyResult,
        audit: AtomizeApplicationAudit,
    ) -> dict[str, object]:
        return {
            "analysis_uid": analysis.uid,
            "ruleset_version": analysis.ruleset_version,
            "source_review_uid": analysis.source_review_uid,
            "source_review_digest": analysis.source_review_digest,
            "declared_frame_count": len(analysis.declared_frames),
            "split_count": result.split_count,
            "child_count": result.child_count,
            "preserved_count": result.preserved_count,
            **(
                {
                    "normal_form_verified": True,
                    "dedun_group_count": result.normal_form.dedun_group_count,
                    "absorbed_count": result.normal_form.absorbed_count,
                }
                if result.normal_form is not None
                else {}
            ),
            **audit.checkpoint_fields(),
            "trace": result.trace_metadata(),
        }


    @staticmethod
    def _result_from_checkpoint(
        analysis: AtomizeAnalysisSession,
        checkpoint: dict[str, object],
    ) -> AtomizeApplyResult:
        args = checkpoint.get("command_details")
        snapshot = checkpoint.get("snapshot")
        if not isinstance(args, dict) or not isinstance(snapshot, dict):
            raise AtomizeApplicationError(
                "The recorded Atomize checkpoint is incomplete."
            )
        trace = args.get("trace")
        if not isinstance(trace, dict) or trace.get("schema_version") not in {3, 4}:
            raise AtomizeApplicationError(
                "The recorded Atomize checkpoint has incompatible trace data."
            )
        trace_schema = trace["schema_version"]
        changes = trace.get("changes")
        if not isinstance(changes, list) or len(changes) != len(analysis.items):
            raise AtomizeApplicationError(
                "The recorded Atomize checkpoint does not cover the analysis."
            )
        try:
            output = Context.from_dict(snapshot)
        except (KeyError, TypeError, ValueError) as error:
            raise AtomizeApplicationError(
                "The recorded Atomize checkpoint Context is invalid."
            ) from error
        if output.uid != analysis.context_uid or output.name != analysis.context_name:
            raise AtomizeApplicationError(
                "The recorded Atomize checkpoint targets a different Context."
            )
        output_memories = {
            item.uid: item
            for item in output.iter_memories()
            if isinstance(item, Memory)
        }
        normal_form: AtomizeNormalFormAudit | None = None
        absorbed_to_survivor: dict[str, str] = {}
        if trace_schema == 4:
            try:
                normal_form = AtomizeNormalFormAudit.from_dict(trace.get("normal_form"))
            except AtomizeImpactError as error:
                raise AtomizeApplicationError(str(error)) from error
            if normal_form.validation_context_digest != direct_context_digest(output):
                raise AtomizeApplicationError(
                    "The recorded Atomize normal-form digest changed."
                )
            absorbed_to_survivor = dict(normal_form.absorbed_to_survivor)
            if any(
                absorbed_uid in output_memories or survivor_uid not in output_memories
                for absorbed_uid, survivor_uid in absorbed_to_survivor.items()
            ):
                raise AtomizeApplicationError(
                    "The recorded Atomize absorption result changed."
                )
            if any(
                uid not in output_memories for uid in normal_form.validation_memory_uids
            ):
                raise AtomizeApplicationError(
                    "The recorded Atomize validation scope changed."
                )
        declared_frames = {
            frame.memory_uid: frame for frame in analysis.declared_frames
        }
        applied_items: list[AppliedAtomizeItem] = []
        for item, change in zip(analysis.items, changes, strict=True):
            if not isinstance(change, dict):
                raise AtomizeApplicationError(
                    "The recorded Atomize checkpoint change is invalid."
                )
            result_uids = change.get("result_uids")
            if (
                change.get("classification") != item.classification
                or change.get("source_uids") != [item.memory_uid]
                or not isinstance(result_uids, list)
                or any(not isinstance(uid, str) for uid in result_uids)
            ):
                raise AtomizeApplicationError(
                    "The recorded Atomize checkpoint differs from the analysis."
                )
            expected_kind = (
                "SPLIT"
                if item.classification == "COMPOSITE"
                else "KEEP"
                if item.classification == "ATOMIC"
                else "PRESERVE"
            )
            if change.get("kind") != expected_kind:
                raise AtomizeApplicationError(
                    "The recorded Atomize checkpoint has an invalid change kind."
                )
            if item.classification == "COMPOSITE":
                if len(result_uids) != len(item.children):
                    raise AtomizeApplicationError(
                        "The recorded Atomize split has an invalid child count."
                    )
                raw_result_contents = change.get("result_contents")
                if trace_schema == 4 and (
                    not isinstance(raw_result_contents, list)
                    or any(
                        not isinstance(content, str) for content in raw_result_contents
                    )
                ):
                    raise AtomizeApplicationError(
                        "The recorded Atomize split contents are invalid."
                    )
                result_contents = (
                    tuple(raw_result_contents)
                    if trace_schema == 4
                    else tuple(
                        output_memories[uid].content
                        for uid in result_uids
                        if uid in output_memories
                    )
                )
                if result_contents != tuple(child.content for child in item.children):
                    raise AtomizeApplicationError(
                        "The recorded Atomize split children changed."
                    )
                if any(
                    uid not in output_memories and uid not in absorbed_to_survivor
                    for uid in result_uids
                ) or any(
                    uid in output_memories and output_memories[uid].content != content
                    for uid, content in zip(
                        result_uids,
                        result_contents,
                        strict=True,
                    )
                ):
                    raise AtomizeApplicationError(
                        "The recorded Atomize split disposition changed."
                    )
            else:
                if result_uids != [item.memory_uid]:
                    raise AtomizeApplicationError(
                        "The recorded preserved Atomize identity changed."
                    )
                current = output_memories.get(item.memory_uid)
                if (
                    current is None and item.memory_uid not in absorbed_to_survivor
                ) or (current is not None and current.content != item.content):
                    raise AtomizeApplicationError(
                        "The recorded preserved Atomize Memory changed."
                    )
                result_contents = (item.content,)
                if trace_schema == 4 and change.get("result_contents") != [
                    item.content
                ]:
                    raise AtomizeApplicationError(
                        "The recorded preserved Atomize content changed."
                    )
            applied_items.append(
                AppliedAtomizeItem(
                    source_uid=item.memory_uid,
                    classification=item.classification,
                    result_uids=tuple(result_uids),
                    result_contents=result_contents,
                    reason=item.reason,
                    reason_codes=item.reason_codes,
                    children=item.children,
                    declared_frame=declared_frames.get(item.memory_uid),
                    source_review_uid=analysis.source_review_uid,
                    source_review_digest=analysis.source_review_digest,
                )
            )
        if normal_form is not None:
            affected_uids = {
                uid for applied in applied_items for uid in applied.result_uids
            }
            expected_final_uids = {
                absorbed_to_survivor.get(uid, uid) for uid in affected_uids
            }
            if set(normal_form.validation_memory_uids) != expected_final_uids:
                raise AtomizeApplicationError(
                    "The recorded Atomize validation scope is incomplete."
                )
        return AtomizeApplyResult(
            analysis_uid=analysis.uid,
            split_count=sum(
                item.classification == "COMPOSITE" for item in analysis.items
            ),
            child_count=sum(
                len(item.children)
                for item in analysis.items
                if item.classification == "COMPOSITE"
            ),
            preserved_count=sum(
                item.classification != "COMPOSITE" for item in analysis.items
            ),
            items=tuple(applied_items),
            normal_form=normal_form,
        )

    def _matching_checkpoint(
        self,
        snapshot: AtomizeExecutionSnapshot,
        audit: AtomizeApplicationAudit,
    ) -> AtomizeMaterialization | None:
        analysis = snapshot.analysis
        matches = [
            checkpoint
            for checkpoint in self.store.list_checkpoints(analysis.context_name)
            if checkpoint.get("command") == "atomize"
            and isinstance(checkpoint.get("command_details"), dict)
            and checkpoint["command_details"].get("analysis_uid") == analysis.uid
        ]
        if not matches:
            return None
        if len(matches) != 1:
            raise AtomizeApplicationError(
                "The Atomize analysis has multiple application checkpoints."
            )
        checkpoint = matches[0]
        checkpoint_uid = checkpoint.get("uid")
        if not isinstance(checkpoint_uid, str):
            raise AtomizeApplicationError(
                "The recorded Atomize checkpoint identity is invalid."
            )
        result = self._result_from_checkpoint(analysis, checkpoint)
        if checkpoint.get("command_details") != self._checkpoint_command_details(
            analysis, result, audit
        ):
            raise AtomizeApplicationError(
                "The prior Atomize checkpoint belongs to a different reviewed "
                "workbench state."
            )
        return AtomizeMaterialization(
            result=result,
            context_name=analysis.context_name,
            checkpoint_uid=checkpoint_uid,
            created=False,
        )

    def recover_materialization(
        self,
        snapshot: AtomizeExecutionSnapshot,
        audit: AtomizeApplicationAudit,
    ) -> AtomizeMaterialization | None:
        return self._matching_checkpoint(snapshot, audit)

    def materialize(
        self,
        snapshot: AtomizeExecutionSnapshot,
        audit: AtomizeApplicationAudit,
    ) -> AtomizeMaterialization:
        analysis = snapshot.analysis
        source = self.store.load_for_update(analysis.context_name)
        source_digest = context_record_digest(source)
        normal_form = project_atomize_normal_form(
            source,
            analysis,
            self.provider_factory,
        )
        projected = normal_form.context
        result = normal_form.result
        # Provider work stays on an unpublished projection until Source
        # revalidation and checkpoint publication.
        recovered = self._matching_checkpoint(snapshot, audit)
        if recovered is not None:
            return recovered
        current = self.store.load_for_update(analysis.context_name)
        if context_record_digest(current) != source_digest:
            raise AtomizeImpactError(
                "The Atomize Source changed during normal-form planning; "
                "no Context change was published."
            )
        checkpoint = self.store.save(
            projected,
            AutoCheckpointRequest(
                command="atomize",
                command_details=self._checkpoint_command_details(analysis, result, audit),
            ),
        )
        if checkpoint is None:
            raise AtomizeApplicationError(
                "Atomize application produced no Context checkpoint."
            )
        return AtomizeMaterialization(
            result=result,
            context_name=projected.name,
            checkpoint_uid=checkpoint.uid,
            created=True,
        )

    def rollback_materialization(
        self,
        materialization: AtomizeMaterialization,
    ) -> None:
        if not materialization.created:
            raise AtomizeApplicationError(
                "A recovered Atomize checkpoint cannot be compensated."
            )
        with self.store._context_graph_lock(exclusive=False):  # noqa: SLF001
            with self.store._context_write_lock(  # noqa: SLF001
                materialization.context_name
            ):
                checkpoints = self.store.list_checkpoints(
                    materialization.context_name
                )
                if (
                    not checkpoints
                    or checkpoints[0].get("uid")
                    != materialization.checkpoint_uid
                ):
                    raise AtomizeApplicationError(
                        "The Atomize checkpoint is no longer the newest "
                        "Context effect."
                    )
                checkpoint = checkpoints[0]
                before = checkpoint.get("command_before")
                after = checkpoint.get("snapshot")
                if not isinstance(before, dict) or not isinstance(after, dict):
                    raise AtomizeApplicationError(
                        "The Atomize checkpoint lacks compensation state."
                    )
                current = self.store.load_direct(materialization.context_name)
                if context_record_digest(current) != context_record_digest(
                    after
                ):
                    raise AtomizeApplicationError(
                        "The atomized Context changed before compensation."
                    )
                restored = Context.from_dict(before)
                if restored.uid != current.uid or restored.name != current.name:
                    raise AtomizeApplicationError(
                        "The Atomize compensation state targets a "
                        "different Context."
                    )
                _write_json_atomic(
                    self.store._context_file(materialization.context_name),
                    before,
                )
                try:
                    self.store._remove_checkpoint_uid_locked(  # noqa: SLF001
                        materialization.context_name,
                        materialization.checkpoint_uid,
                    )
                    _fsync_directory(
                        self.store._checkpoints_dir(  # noqa: SLF001
                            materialization.context_name
                        )
                    )
                except Exception:
                    # Restore the exact post-Apply record if checkpoint
                    # removal itself fails, preserving the pair rather
                    # than reporting a compensated state that is not.
                    _write_json_atomic(
                        self.store._context_file(  # noqa: SLF001
                            materialization.context_name
                        ),
                        after,
                    )
                    raise


def capture_atomize_execution_snapshot(
    *,
    store: ProfileStore,
    analysis: AtomizeAnalysisSession,
    expected_review_record: AtomizeReviewRecord | None,
) -> AtomizeExecutionSnapshot:
    """Freeze the exact saved revision accepted by CLI, TUI, or another adapter."""

    return MemoryStoreAtomizeRecordRepository(store).capture(
        analysis,
        expected_review_record,
    )


def atomize_application_checkpoint_uid(
    store: ProfileStore,
    context: Context,
    analysis_uid: str,
) -> str | None:
    """Return the exact in-place checkpoint belonging to one Atomize analysis."""

    for checkpoint in store.list_checkpoints(context.name):
        args = checkpoint.get("command_details")
        trace = args.get("trace") if isinstance(args, dict) else None
        if not (
            checkpoint.get("command") == "atomize"
            and isinstance(trace, dict)
            and args.get("analysis_uid") == analysis_uid
            and trace.get("operation_id") == analysis_uid
        ):
            continue
        snapshot = checkpoint.get("snapshot")
        if not isinstance(snapshot, dict):
            continue
        try:
            checkpoint_context = Context.from_dict(snapshot)
        except (KeyError, TypeError):
            continue
        if (
            checkpoint_context.uid == context.uid
            and checkpoint_context.name == context.name
            and isinstance(checkpoint.get("uid"), str)
        ):
            return checkpoint["uid"]
    return None


def atomize_analysis_was_applied(
    store: ProfileStore,
    context: Context,
    analysis_uid: str,
) -> bool:
    """Return whether one analysis identity already crossed its Apply boundary."""

    return atomize_application_checkpoint_uid(store, context, analysis_uid) is not None


def _analysis_scope_matches_request(
    analysis: AtomizeAnalysisSession,
    request: AtomizeInPlaceRequest,
) -> bool:
    """Compare scope shape without mistaking an applied preimage for current input."""

    if request.memory_selector is None:
        return analysis.evidence_digest is None
    requested_uids = requested_atomize_memory_uids(
        request.context,
        request.memory_selector,
    )
    return (
        analysis.evidence_digest is not None
        and tuple(item.memory_uid for item in analysis.items) == requested_uids
    )


def execute_atomize_in_place(
    request: AtomizeInPlaceRequest,
    *,
    store: ProfileStore,
    provider_factory: Callable[[], AtomizeProvider],
) -> AtomizeInPlaceResult:
    """Analyze or reuse one exact scope and apply it as one in-place outcome."""

    if not isinstance(request, AtomizeInPlaceRequest):
        raise TypeError("In-place Atomize requires a typed request.")

    existing = store.load_atomize_analysis(request.context.uid)
    if (
        existing is not None
        and not request.refresh
        and _analysis_scope_matches_request(existing, request)
        and atomize_analysis_was_applied(store, request.context, existing.uid)
    ):
        snapshot = capture_atomize_execution_snapshot(
            store=store,
            analysis=existing,
            expected_review_record=store.load_atomize_workbench(existing),
        )
        applied = execute_atomize_record_apply(
            AtomizeRecordApplyRequest(snapshot=snapshot),
            store=store,
            provider_factory=provider_factory,
        )
        return AtomizeInPlaceResult(
            analysis=existing,
            application=applied,
            analysis_origin="SAVED",
        )

    opened = execute_atomize_analysis_open(
        AtomizeAnalysisOpenRequest(
            context=request.context,
            refresh=request.refresh,
            # Console Atomize always binds its Output plan to the Source.
            output_context_name=request.context.name,
            memory_selector=request.memory_selector,
        ),
        store=store,
        provider_factory=provider_factory,
    )
    snapshot = capture_atomize_execution_snapshot(
        store=store,
        analysis=opened.analysis,
        expected_review_record=opened.review_record,
    )
    applied = execute_atomize_record_apply(
        AtomizeRecordApplyRequest(snapshot=snapshot),
        store=store,
        provider_factory=provider_factory,
    )
    return AtomizeInPlaceResult(
        analysis=opened.analysis,
        application=applied,
        analysis_origin=opened.origin,
    )


def execute_atomize_record_apply(
    request: AtomizeRecordApplyRequest,
    *,
    store: ProfileStore,
    provider_factory: Callable[[], AtomizeProvider],
) -> AtomizeRecordApplyResult:
    """Apply one accepted revision through the production Store adapters."""

    return run_atomize_record_apply(
        request,
        repository=MemoryStoreAtomizeRecordRepository(store),
        output_port=MemoryStoreAtomizeOutputPort(
            store,
            provider_factory=provider_factory,
        ),
    )
