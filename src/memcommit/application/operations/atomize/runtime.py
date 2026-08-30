"""Production Store adapters for structural Atomize application."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from typing import Callable

import memcommit.application.capabilities.ops as ops
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
    AtomizeOutputPlanRequest,
    AtomizeSaveAsRequest,
    AtomizeSaveAsResult,
    AtomizeExecutionSnapshot,
    AtomizeReviewRecordUpdateResult,
    run_atomize_output_plan_update,
    run_atomize_record_apply,
    run_atomize_save_as,
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
    atomize_review_record_digest,
)
from memcommit.core.context import AutoCheckpoint, Context, Memory, MemoryRef
from memcommit.application.operations.review.model import direct_context_digest
from memcommit.persistence.store import (
    MemoryStore,
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
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


@dataclass
class MemoryStoreAtomizeRecordRepository:
    """Treat the saved analysis/workbench pair as one opaque CAS snapshot."""

    store: MemoryStore

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

    def replace_review_record(
        self,
        review_record: AtomizeReviewRecord,
        *,
        analysis: AtomizeAnalysisSession,
        expected_version: str,
    ) -> AtomizeExecutionSnapshot:
        """Replace one complete review record only under its opaque revision."""

        with self.store._atomize_session_write_lock(analysis.context_uid):  # noqa: SLF001
            current = self._load_unlocked(analysis)
            if current.version_token != expected_version:
                raise AtomizeApplicationError(
                    "The Atomize session changed before the review update."
                )
            self.store._save_atomize_workbench_locked(review_record)  # noqa: SLF001
            committed = self._load_unlocked(analysis)
            if committed.review_record != review_record:
                raise AtomizeApplicationError(
                    "Atomize review persistence returned a different workbench."
                )
            return committed


@dataclass
class MemoryStoreAtomizeOutputPort:
    """Create, recover, or compensate one local in-place Atomize checkpoint."""

    store: MemoryStore
    provider_factory: Callable[[], AtomizeProvider]

    @staticmethod
    def _checkpoint_args(
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
    def _checkpoint_description(
        analysis: AtomizeAnalysisSession,
        result: AtomizeApplyResult,
        audit: AtomizeApplicationAudit,
    ) -> str:
        base = (
            f"Applied atomize [{analysis.uid[:8]}]: "
            f"{result.split_count} splits -> {result.child_count} children; "
            f"{result.preserved_count} preserved; "
        )
        if result.normal_form is not None:
            base += (
                f"{result.normal_form.dedun_group_count} Dedun groups; "
                f"{result.normal_form.absorbed_count} absorbed; "
            )
        return base + f"{audit.unresolved_at_apply_count} unresolved at apply"

    @staticmethod
    def _result_from_checkpoint(
        analysis: AtomizeAnalysisSession,
        checkpoint: dict[str, object],
    ) -> AtomizeApplyResult:
        args = checkpoint.get("args")
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
            item.uid: item for item in output.iter_items() if isinstance(item, Memory)
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
            and isinstance(checkpoint.get("args"), dict)
            and checkpoint["args"].get("analysis_uid") == analysis.uid
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
        if checkpoint.get("args") != self._checkpoint_args(
            analysis, result, audit
        ) or checkpoint.get("description") != self._checkpoint_description(
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

    def _inbound_removed_references(
        self,
        analysis: AtomizeAnalysisSession,
        removed_uids: set[str],
    ) -> list[tuple[str, MemoryRef]]:
        if not removed_uids:
            return []
        inbound: list[tuple[str, MemoryRef]] = []
        for context in self.store.load_direct_context_graph_strict():
            for item in context.iter_items():
                if (
                    isinstance(item, MemoryRef)
                    and item.target_context_uid == analysis.context_uid
                    and item.target_memory_uid in removed_uids
                ):
                    inbound.append((context.name, item))
        return inbound

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
        removed_uids = {
            item.memory_uid
            for item in analysis.items
            if item.classification == "COMPOSITE"
        } | set(normal_form.absorbed_uids)

        # Provider work completes on an unpublished projection. The command
        # lock then makes the strict inbound-reference scan, Source CAS, and
        # sole checkpoint one ordered Context command.
        with self.store._command_write_lock():  # noqa: SLF001
            recovered = self._matching_checkpoint(snapshot, audit)
            if recovered is not None:
                return recovered
            current = self.store.load_for_update(analysis.context_name)
            if context_record_digest(current) != source_digest:
                raise AtomizeImpactError(
                    "The Atomize Source changed during normal-form planning; "
                    "no Context change was published."
                )
            inbound = self._inbound_removed_references(
                analysis,
                removed_uids,
            )
            if inbound:
                locations = ", ".join(
                    f"{owner}#{reference.uid[:8]}" for owner, reference in inbound
                )
                raise AtomizeImpactError(
                    "Cannot replace or absorb a Memory with inbound memory "
                    "references in "
                    f"version 1: {locations}."
                )
            checkpoint = self.store._save_command_locked(  # noqa: SLF001
                projected,
                AutoCheckpoint(
                    command="atomize",
                    args=self._checkpoint_args(analysis, result, audit),
                    description=self._checkpoint_description(
                        analysis,
                        result,
                        audit,
                    ),
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
        with self.store._command_write_lock():  # noqa: SLF001
            with self.store._context_graph_lock(exclusive=False):  # noqa: SLF001
                with self.store._context_write_lock(  # noqa: SLF001
                    materialization.context_name
                ):
                    with self.store.profile_write_guard():
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


@dataclass
class MemoryStoreAtomizeSaveAsOutputPort:
    """Publish a final derived Context once, with no visible baseline copy."""

    store: MemoryStore
    provider_factory: Callable[[], AtomizeProvider]

    @staticmethod
    def _source_workbench_record(
        workbench: AtomizeReviewRecord | None,
    ) -> dict[str, object] | None:
        if workbench is None:
            return None
        return {
            "uid": workbench.uid,
            "output_context_name": workbench.output_context_name,
            "record_digest": atomize_review_record_digest(workbench),
        }

    @classmethod
    def _save_as_record(
        cls,
        snapshot: AtomizeExecutionSnapshot,
        *,
        source: Context,
        expected_current: str | None,
    ) -> dict[str, object]:
        return {
            "version": 1,
            "source_context": {
                "uid": source.uid,
                "name": source.name,
                "digest": context_record_digest(source),
            },
            # The unmodified branch is not a checkpoint, but direct-Memory
            # lineage still needs an exact pre-transform frame for Trace.
            "source_frame": [
                {
                    "uid": item.uid,
                    "content": item.content,
                    "position": position,
                }
                for position, item in enumerate(
                    candidate
                    for candidate in source.iter_items()
                    if isinstance(candidate, Memory)
                )
            ],
            "source_frame_digest": direct_context_digest(source),
            "source_analysis_uid": snapshot.analysis.uid,
            "source_workbench": cls._source_workbench_record(snapshot.review_record),
            "current_before": expected_current,
        }

    @staticmethod
    def _context_creation_record(output: Context) -> dict[str, object]:
        return {
            "version": 1,
            "context_uid": output.uid,
            "context_name": output.name,
        }

    @classmethod
    def _checkpoint_args(
        cls,
        snapshot: AtomizeExecutionSnapshot,
        output_analysis: AtomizeAnalysisSession,
        output: Context,
        result: AtomizeApplyResult,
        audit: AtomizeApplicationAudit,
        *,
        source: Context,
        expected_current: str | None,
    ) -> dict[str, object]:
        return {
            **MemoryStoreAtomizeOutputPort._checkpoint_args(
                output_analysis,
                result,
                audit,
            ),
            "context_creation": cls._context_creation_record(output),
            "atomize_save_as": cls._save_as_record(
                snapshot,
                source=source,
                expected_current=expected_current,
            ),
        }

    @staticmethod
    def _checkpoint_description(
        output_analysis: AtomizeAnalysisSession,
        result: AtomizeApplyResult,
        audit: AtomizeApplicationAudit,
    ) -> str:
        return MemoryStoreAtomizeOutputPort._checkpoint_description(
            output_analysis,
            result,
            audit,
        )

    @staticmethod
    def _workbench_matches_record(
        workbench: AtomizeReviewRecord | None,
        record: object,
        *,
        destination_name: str,
        checkpoint_uid: str,
    ) -> bool:
        if record is None:
            return workbench is None
        if not isinstance(record, dict) or set(record) != {
            "uid",
            "output_context_name",
            "record_digest",
        }:
            return False
        if workbench is None or workbench.uid != record.get("uid"):
            return False
        reviewing = AtomizeReviewRecord.from_dict(
            workbench.to_dict(),
            issues=workbench.issues,
        )
        if reviewing.application is not None:
            try:
                reviewing.clear_application(
                    output_context_name=destination_name,
                    checkpoint_uid=checkpoint_uid,
                    restore_output_context_name=record.get("output_context_name"),
                )
            except (TypeError, ValueError):
                return False
        return atomize_review_record_digest(reviewing) == record.get("record_digest")

    def _matching_checkpoint(
        self,
        snapshot: AtomizeExecutionSnapshot,
        audit: AtomizeApplicationAudit,
        destination_name: str,
    ) -> tuple[AtomizeAnalysisSession, AtomizeMaterialization] | None:
        if not self.store.context_exists(destination_name):
            return None
        output = self.store.load_direct(destination_name)
        output_analysis = self.store.load_atomize_analysis(output.uid)
        if (
            output_analysis is None
            or output_analysis.uid != snapshot.analysis.uid
            or output_analysis.context_uid != output.uid
            or output_analysis.context_name != destination_name
        ):
            raise AtomizeApplicationError(
                f"Planned atomize Output '{destination_name}' already exists "
                "and is not the exact applied result of this session."
            )
        matches = [
            checkpoint
            for checkpoint in self.store.list_checkpoints(destination_name)
            if checkpoint.get("command") == "atomize"
            and isinstance(checkpoint.get("args"), dict)
            and checkpoint["args"].get("analysis_uid") == output_analysis.uid
        ]
        if len(matches) != 1:
            raise AtomizeApplicationError(
                "The planned Atomize output has incompatible checkpoint history."
            )
        checkpoint = matches[0]
        checkpoint_uid = checkpoint.get("uid")
        args = checkpoint.get("args")
        snapshot_record = checkpoint.get("snapshot")
        if (
            not isinstance(checkpoint_uid, str)
            or not isinstance(args, dict)
            or not isinstance(snapshot_record, dict)
            or context_record_digest(output) != context_record_digest(snapshot_record)
        ):
            raise AtomizeApplicationError(
                "The planned Atomize output changed after publication."
            )
        creation = args.get("context_creation")
        save_as = args.get("atomize_save_as")
        if (
            creation != self._context_creation_record(output)
            or not isinstance(save_as, dict)
            or set(save_as)
            != {
                "version",
                "source_context",
                "source_frame",
                "source_frame_digest",
                "source_analysis_uid",
                "source_workbench",
                "current_before",
            }
            or save_as.get("version") != 1
            or save_as.get("source_analysis_uid") != snapshot.analysis.uid
        ):
            raise AtomizeApplicationError(
                "The planned Atomize output has incompatible creation provenance."
            )
        source_record = save_as.get("source_context")
        if (
            not isinstance(source_record, dict)
            or set(source_record) != {"uid", "name", "digest"}
            or source_record.get("uid") != snapshot.analysis.context_uid
            or source_record.get("name") != snapshot.analysis.context_name
        ):
            raise AtomizeApplicationError(
                "The planned Atomize output belongs to a different Source."
            )
        source_frame = save_as.get("source_frame")
        expected_selected = [
            {
                "uid": item.memory_uid,
                "content": item.content,
                "position": item.position,
            }
            for item in sorted(snapshot.analysis.items, key=lambda item: item.position)
        ]
        if not isinstance(source_frame, list) or any(
            not isinstance(item, dict)
            or set(item) != {"uid", "content", "position"}
            or item.get("position") != position
            or not isinstance(item.get("uid"), str)
            or not isinstance(item.get("content"), str)
            for position, item in enumerate(source_frame)
        ):
            raise AtomizeApplicationError(
                "The planned Atomize output has incompatible Source lineage."
            )
        selected_by_position = {item["position"]: item for item in expected_selected}
        if any(
            position >= len(source_frame) or source_frame[position] != item
            for position, item in selected_by_position.items()
        ):
            raise AtomizeApplicationError(
                "The planned Atomize output has incompatible Source lineage."
            )
        expected_frame_digest = hashlib.sha256(
            json.dumps(
                [
                    {"uid": item["uid"], "content": item["content"]}
                    for item in source_frame
                ],
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        analysis_evidence_digest = getattr(
            snapshot.analysis,
            "evidence_digest",
            None,
        )
        if save_as.get(
            "source_frame_digest"
        ) != expected_frame_digest or expected_frame_digest != (
            analysis_evidence_digest or snapshot.analysis.context_digest
        ):
            raise AtomizeApplicationError(
                "The planned Atomize output has incompatible Source lineage."
            )
        result = MemoryStoreAtomizeOutputPort._result_from_checkpoint(
            output_analysis,
            checkpoint,
        )
        expected_common = MemoryStoreAtomizeOutputPort._checkpoint_args(
            output_analysis,
            result,
            audit,
        )
        if any(args.get(key) != value for key, value in expected_common.items()):
            raise AtomizeApplicationError(
                "The planned Atomize output belongs to a different review state."
            )
        if not self._workbench_matches_record(
            snapshot.review_record,
            save_as.get("source_workbench"),
            destination_name=destination_name,
            checkpoint_uid=checkpoint_uid,
        ):
            raise AtomizeApplicationError(
                "The planned Atomize output belongs to a different workbench state."
            )
        return output_analysis, AtomizeMaterialization(
            result=result,
            context_name=destination_name,
            checkpoint_uid=checkpoint_uid,
            created=False,
        )

    def recover_materialization(
        self,
        snapshot: AtomizeExecutionSnapshot,
        audit: AtomizeApplicationAudit,
        destination_name: str,
    ) -> tuple[AtomizeAnalysisSession, AtomizeMaterialization] | None:
        return self._matching_checkpoint(snapshot, audit, destination_name)

    def materialize(
        self,
        snapshot: AtomizeExecutionSnapshot,
        audit: AtomizeApplicationAudit,
        destination_name: str,
        expected_current: str | None,
    ) -> tuple[AtomizeAnalysisSession, AtomizeMaterialization]:
        source = self.store.load_for_update(snapshot.analysis.context_name)
        source_digest = context_record_digest(source)
        analysis_evidence_digest = getattr(
            snapshot.analysis,
            "evidence_digest",
            None,
        )
        if source.uid != snapshot.analysis.context_uid or direct_context_digest(
            source
        ) != (analysis_evidence_digest or snapshot.analysis.context_digest):
            raise AtomizeApplicationError(
                "The Atomize Source changed before Save As. Reopen the review."
            )
        # Atomize applies a source-UID-keyed reviewed analysis to this
        # process-local projection before assigning its result identities.
        # This is not the durable Branch command: its final Save As receipt
        # owns the independently materialized output and provenance.
        output = ops._atomize_projection(source, destination_name)
        output_fields: dict[str, object] = {
            "context_uid": output.uid,
            "context_name": output.name,
            "context_digest": (
                snapshot.analysis.context_digest
                if analysis_evidence_digest is not None
                else direct_context_digest(output)
            ),
        }
        if hasattr(snapshot.analysis, "evidence_digest"):
            output_fields["evidence_digest"] = (
                direct_context_digest(output)
                if analysis_evidence_digest is not None
                else None
            )
        output_analysis = replace(snapshot.analysis, **output_fields)
        # The complete semantic normal form remains unpublished until the one
        # final Context creation below. The output port requires a provider so
        # no adapter can publish the legacy structural-only intermediate form.
        normal_form = project_atomize_normal_form(
            output,
            output_analysis,
            self.provider_factory,
        )
        output = normal_form.context
        result = normal_form.result
        checkpoint_args = self._checkpoint_args(
            snapshot,
            output_analysis,
            output,
            result,
            audit,
            source=source,
            expected_current=expected_current,
        )
        self.store.save_atomize_analysis(output_analysis)
        try:
            checkpoint = self.store.create_context_with_sources(
                output,
                AutoCheckpoint(
                    command="atomize",
                    args=checkpoint_args,
                    description=self._checkpoint_description(
                        output_analysis,
                        result,
                        audit,
                    ),
                ),
                source_bindings=((source.name, source.uid, source_digest),),
            )
        except Exception as error:
            self.store.delete_atomize_analysis(output.uid)
            recovered = self._matching_checkpoint(
                snapshot,
                audit,
                destination_name,
            )
            if recovered is not None:
                return recovered
            raise error
        if checkpoint is None:
            self.store.delete_atomize_analysis(output.uid)
            raise AtomizeApplicationError(
                "Atomize Save As produced no Context checkpoint."
            )
        return output_analysis, AtomizeMaterialization(
            result=result,
            context_name=output.name,
            checkpoint_uid=checkpoint.uid,
            created=True,
        )

    def select_output(
        self,
        materialization: AtomizeMaterialization,
        *,
        expected_current: str | None,
    ) -> None:
        output = self.store.load_direct(materialization.context_name)
        self.store.set_current_context_if(
            expected_current,
            output.name,
            expected_context_uid=output.uid,
            expected_context_digest=context_record_digest(output),
        )


def capture_atomize_execution_snapshot(
    *,
    store: MemoryStore,
    analysis: AtomizeAnalysisSession,
    expected_review_record: AtomizeReviewRecord | None,
) -> AtomizeExecutionSnapshot:
    """Freeze the exact saved revision accepted by CLI, TUI, or another adapter."""

    return MemoryStoreAtomizeRecordRepository(store).capture(
        analysis,
        expected_review_record,
    )


def atomize_application_checkpoint_uid(
    store: MemoryStore,
    context: Context,
    analysis_uid: str,
) -> str | None:
    """Return the exact in-place checkpoint belonging to one Atomize analysis."""

    for checkpoint in store.list_checkpoints(context.name):
        args = checkpoint.get("args")
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
    store: MemoryStore,
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
    store: MemoryStore,
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
            # Console Atomize is always in place, even when a compatible
            # historical prewarm carried a now-retired Save As destination.
            output_context_name=request.context.name,
            memory_selector=request.memory_selector,
            allow_prepared=not request.refresh,
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


def capture_atomize_execution_snapshot_at_version(
    *,
    store: MemoryStore,
    analysis: AtomizeAnalysisSession,
    expected_version: str,
) -> AtomizeExecutionSnapshot:
    """Recover one exact accepted revision without provider or interface state.

    A transport retry can arrive after Apply committed its terminal receipt.
    Accept only the current revision or the exact preterminal form of that
    receipt; every other saved-session change remains a conflict.
    """

    repository = MemoryStoreAtomizeRecordRepository(store)
    with store._atomize_session_write_lock(analysis.context_uid):  # noqa: SLF001
        current = repository._load_unlocked(analysis)  # noqa: SLF001
        if current.version_token == expected_version:
            return current
        workbench = current.review_record
        if workbench is not None and workbench.application is not None:
            accepted_workbench = replace(workbench, application=None)
            accepted_version = _session_version_token(
                current.analysis,
                accepted_workbench,
            )
            if accepted_version == expected_version:
                return AtomizeExecutionSnapshot(
                    analysis=current.analysis,
                    review_record=accepted_workbench,
                    version_token=accepted_version,
                )
        raise AtomizeApplicationError(
            "The accepted Atomize version changed before application. Reopen the review."
        )


def capture_current_atomize_execution_snapshot_at_version(
    *,
    store: MemoryStore,
    analysis: AtomizeAnalysisSession,
    expected_version: str,
) -> AtomizeExecutionSnapshot:
    """Capture only the current exact revision, never a terminal retry form."""

    snapshot = MemoryStoreAtomizeRecordRepository(store).load(analysis)
    if snapshot.version_token != expected_version:
        raise AtomizeApplicationError(
            "The accepted Atomize version changed. Reopen the review."
        )
    return snapshot


def execute_atomize_output_plan_update(
    request: AtomizeOutputPlanRequest,
    *,
    store: MemoryStore,
) -> AtomizeReviewRecordUpdateResult:
    """Persist one exact Output-plan update through the production repository."""

    return run_atomize_output_plan_update(
        request,
        repository=MemoryStoreAtomizeRecordRepository(store),
    )


def execute_atomize_record_apply(
    request: AtomizeRecordApplyRequest,
    *,
    store: MemoryStore,
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


def execute_atomize_save_as(
    request: AtomizeSaveAsRequest,
    *,
    store: MemoryStore,
    provider_factory: Callable[[], AtomizeProvider],
) -> AtomizeSaveAsResult:
    """Create or recover one final Save As output through Store adapters."""

    return run_atomize_save_as(
        request,
        repository=MemoryStoreAtomizeRecordRepository(store),
        output_port=MemoryStoreAtomizeSaveAsOutputPort(
            store,
            provider_factory=provider_factory,
        ),
    )
