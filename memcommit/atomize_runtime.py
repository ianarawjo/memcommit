"""Production Store adapters for structural Atomize application."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from memcommit.atomize import (
    AppliedAtomizeItem,
    AtomizeAnalysisSession,
    AtomizeApplyResult,
    AtomizeImpactError,
    apply_atomize_analysis,
)
from memcommit.atomize_application import (
    AtomizeApplicationAudit,
    AtomizeApplicationError,
    AtomizeMaterialization,
    AtomizePersistedApplyRequest,
    AtomizePersistedApplyResult,
    AtomizeSessionSnapshot,
    run_atomize_session_apply,
)
from memcommit.atomize_workbench import AtomizeWorkbenchSession
from memcommit.context import AutoCheckpoint, Context, Memory, MemoryRef
from memcommit.store import (
    MemoryStore,
    _fsync_directory,
    _write_json_atomic,
    context_record_digest,
)


def _session_version_token(
    analysis: AtomizeAnalysisSession,
    workbench: AtomizeWorkbenchSession | None,
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
class MemoryStoreAtomizeSessionRepository:
    """Treat the saved analysis/workbench pair as one opaque CAS snapshot."""

    store: MemoryStore

    def _load_unlocked(
        self,
        expected: AtomizeAnalysisSession,
    ) -> AtomizeSessionSnapshot:
        analysis = self.store.load_atomize_analysis(expected.context_uid)
        if analysis is None or analysis.uid != expected.uid:
            raise AtomizeApplicationError(
                "The accepted Atomize analysis is no longer current."
            )
        workbench = self.store.load_atomize_workbench(analysis)
        return AtomizeSessionSnapshot(
            analysis=analysis,
            workbench=workbench,
            version_token=_session_version_token(analysis, workbench),
        )

    def load(
        self,
        analysis: AtomizeAnalysisSession,
    ) -> AtomizeSessionSnapshot:
        with self.store._atomize_session_write_lock(analysis.context_uid):  # noqa: SLF001
            return self._load_unlocked(analysis)

    def capture(
        self,
        analysis: AtomizeAnalysisSession,
        expected_workbench: AtomizeWorkbenchSession | None,
    ) -> AtomizeSessionSnapshot:
        """Freeze only the exact revision an interface actually accepted."""

        snapshot = self.load(analysis)
        if snapshot.analysis != analysis or snapshot.workbench != expected_workbench:
            raise AtomizeApplicationError(
                "The Atomize analysis or workbench changed before approval "
                "could be frozen. Reopen the review."
            )
        return snapshot

    def replace_application(
        self,
        workbench: AtomizeWorkbenchSession,
        *,
        analysis: AtomizeAnalysisSession,
        expected_version: str,
    ) -> AtomizeSessionSnapshot:
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
            if committed.workbench != workbench:
                raise AtomizeApplicationError(
                    "Atomize terminal persistence returned a different workbench."
                )
            return committed


@dataclass
class MemoryStoreAtomizeOutputPort:
    """Create, recover, or compensate one local in-place Atomize checkpoint."""

    store: MemoryStore

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
            **audit.checkpoint_fields(),
            "trace": result.trace_metadata(),
        }

    @staticmethod
    def _checkpoint_description(
        analysis: AtomizeAnalysisSession,
        result: AtomizeApplyResult,
        audit: AtomizeApplicationAudit,
    ) -> str:
        return (
            f"Applied atomize [{analysis.uid[:8]}]: "
            f"{result.split_count} splits -> {result.child_count} children; "
            f"{result.preserved_count} preserved; "
            f"{audit.unresolved_at_apply_count} unresolved at apply"
        )

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
        if not isinstance(trace, dict) or trace.get("schema_version") != 3:
            raise AtomizeApplicationError(
                "The recorded Atomize checkpoint has incompatible trace data."
            )
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
                result_contents = tuple(
                    output_memories[uid].content
                    for uid in result_uids
                    if uid in output_memories
                )
                if result_contents != tuple(child.content for child in item.children):
                    raise AtomizeApplicationError(
                        "The recorded Atomize split children changed."
                    )
            else:
                if result_uids != [item.memory_uid]:
                    raise AtomizeApplicationError(
                        "The recorded preserved Atomize identity changed."
                    )
                current = output_memories.get(item.memory_uid)
                if current is None or current.content != item.content:
                    raise AtomizeApplicationError(
                        "The recorded preserved Atomize Memory changed."
                    )
                result_contents = (item.content,)
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
        )

    def _matching_checkpoint(
        self,
        snapshot: AtomizeSessionSnapshot,
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
        if (
            checkpoint.get("args")
            != self._checkpoint_args(analysis, result, audit)
            or checkpoint.get("description")
            != self._checkpoint_description(analysis, result, audit)
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
        snapshot: AtomizeSessionSnapshot,
        audit: AtomizeApplicationAudit,
    ) -> AtomizeMaterialization | None:
        return self._matching_checkpoint(snapshot, audit)

    def _inbound_split_references(
        self,
        analysis: AtomizeAnalysisSession,
    ) -> list[tuple[str, MemoryRef]]:
        split_uids = {
            item.memory_uid
            for item in analysis.items
            if item.classification == "COMPOSITE"
        }
        if not split_uids:
            return []
        inbound: list[tuple[str, MemoryRef]] = []
        for context in self.store.load_direct_context_graph_strict():
            for item in context.iter_items():
                if (
                    isinstance(item, MemoryRef)
                    and item.target_context_uid == analysis.context_uid
                    and item.target_memory_uid in split_uids
                ):
                    inbound.append((context.name, item))
        return inbound

    def materialize(
        self,
        snapshot: AtomizeSessionSnapshot,
        audit: AtomizeApplicationAudit,
    ) -> AtomizeMaterialization:
        analysis = snapshot.analysis
        # The command lock makes the strict inbound-reference scan and the
        # target CAS one ordered Context command. It also prevents two
        # all-preserved applications from creating duplicate checkpoints even
        # though their Context bytes are extensionally identical.
        with self.store._command_write_lock():  # noqa: SLF001
            recovered = self._matching_checkpoint(snapshot, audit)
            if recovered is not None:
                return recovered
            inbound = self._inbound_split_references(analysis)
            if inbound:
                locations = ", ".join(
                    f"{owner}#{reference.uid[:8]}"
                    for owner, reference in inbound
                )
                raise AtomizeImpactError(
                    "Cannot split a Memory with inbound memory references in "
                    f"version 1: {locations}."
                )
            context = self.store.load_for_update(analysis.context_name)
            result = apply_atomize_analysis(context, analysis)
            checkpoint = self.store._save_command_locked(  # noqa: SLF001
                context,
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
                context_name=context.name,
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
                        current = self.store.load_direct(
                            materialization.context_name
                        )
                        if context_record_digest(current) != context_record_digest(
                            after
                        ):
                            raise AtomizeApplicationError(
                                "The atomized Context changed before compensation."
                            )
                        restored = Context.from_dict(before)
                        if (
                            restored.uid != current.uid
                            or restored.name != current.name
                        ):
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


def capture_atomize_session_snapshot(
    *,
    store: MemoryStore,
    analysis: AtomizeAnalysisSession,
    expected_workbench: AtomizeWorkbenchSession | None,
) -> AtomizeSessionSnapshot:
    """Freeze the exact saved revision accepted by CLI, TUI, or another adapter."""

    return MemoryStoreAtomizeSessionRepository(store).capture(
        analysis,
        expected_workbench,
    )


def execute_atomize_session_apply(
    request: AtomizePersistedApplyRequest,
    *,
    store: MemoryStore,
) -> AtomizePersistedApplyResult:
    """Apply one accepted revision through the production Store adapters."""

    return run_atomize_session_apply(
        request,
        repository=MemoryStoreAtomizeSessionRepository(store),
        output_port=MemoryStoreAtomizeOutputPort(store),
    )
