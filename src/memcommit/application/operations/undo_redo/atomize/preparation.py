"""Validate live restoration preconditions and prepare unpublished state.

The caller retains the graph, Context, and ordered Atomize session locks from
these reads through publication or compensation. Preparation never writes.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from memcommit.models.context import Context

from memcommit.persistence.store.context_memory.models import (
    ConcurrentContextUpdateError,
)
from memcommit.persistence.store.context_memory.records import context_record_digest
from memcommit.persistence.store.loading.command_archives import (
    load_archived_atomize_analysis,
)
from memcommit.persistence.store.loading.atomize_archive_records import (
    AtomizeArchiveManifest,
    AtomizeCreationReceipt,
)

if TYPE_CHECKING:
    from memcommit.application.capabilities.command_recovery.model import (
        CommandContextChange,
        ContextCommandUnit,
    )
    from memcommit.application.operations.atomize.records import AtomizeReviewRecord
    from memcommit.persistence.store import ProfileStore


@dataclass(frozen=True)
class PreparedAtomizeRestore:
    context: Context
    manifest: AtomizeArchiveManifest
    workbench_before: AtomizeReviewRecord | None
    workbench_after: AtomizeReviewRecord | None


def load_undo_context(store: ProfileStore, change: CommandContextChange) -> Context:
    try:
        current = store.load_direct(change.context_name)
    except FileNotFoundError as error:
        raise ConcurrentContextUpdateError(
            f"Affected Context '{change.context_name}' no longer exists."
        ) from error
    if current.uid != change.context_uid or context_record_digest(
        current
    ) != context_record_digest(change.after):
        raise ConcurrentContextUpdateError(
            f"Affected Context '{change.context_name}' changed after the "
            "Atomize Save As selected for undo."
        )
    return current


def prepare_undo(
    store: ProfileStore,
    unit: ContextCommandUnit,
    current: Context,
    receipt: AtomizeCreationReceipt,
) -> PreparedAtomizeRestore:
    from memcommit.application.operations.atomize.records import (
        atomize_review_record_digest,
    )

    change = unit.changes[0]
    source_analysis = store.load_atomize_analysis(receipt.source_context_uid)
    output_analysis = store.load_atomize_analysis(change.context_uid)
    if (
        source_analysis is None
        or output_analysis is None
        or source_analysis.uid != receipt.analysis_uid
        or output_analysis.uid != receipt.analysis_uid
        or output_analysis.context_uid != change.context_uid
        or output_analysis.context_name != change.context_name
    ):
        raise ValueError("Atomize analyses do not match the restored Save As command.")
    terminal = store.load_atomize_workbench(source_analysis)
    reviewing = None
    reviewing_digest = terminal_digest = None
    source_workbench = receipt.source_workbench
    if source_workbench is None:
        if terminal is not None:
            raise ConcurrentContextUpdateError(
                "The Source Atomize workbench changed before Undo."
            )
    else:
        if terminal is None or terminal.uid != source_workbench.uid:
            raise ValueError("Atomize Source workbench receipt is invalid.")
        terminal_digest = atomize_review_record_digest(terminal)
        reviewing = copy.deepcopy(terminal)
        reviewing.clear_application(
            output_context_name=change.context_name,
            checkpoint_uid=change.checkpoint_uid,
            restore_output_context_name=source_workbench.output_context_name,
        )
        reviewing_digest = atomize_review_record_digest(reviewing)
        if reviewing_digest != source_workbench.record_digest:
            raise ConcurrentContextUpdateError(
                "The Source Atomize workbench changed before Undo."
            )
    manifest = AtomizeArchiveManifest(
        unit_uid=unit.uid,
        context_uid=change.context_uid,
        context_name=change.context_name,
        checkpoint_uid=change.checkpoint_uid,
        analysis_uid=receipt.analysis_uid,
        source_context_uid=receipt.source_context_uid,
        source_context_name=receipt.source_context_name,
        source_workbench=source_workbench,
        reviewing_workbench_digest=reviewing_digest,
        terminal_workbench_digest=terminal_digest,
        current_before=receipt.current_before,
    )
    return PreparedAtomizeRestore(current, manifest, terminal, reviewing)


def prepare_redo(
    store: ProfileStore,
    unit: ContextCommandUnit,
    archive: Path,
    archived_context: Context,
    manifest: AtomizeArchiveManifest,
    receipt: AtomizeCreationReceipt,
) -> PreparedAtomizeRestore:
    from memcommit.application.operations.atomize.records import (
        atomize_review_record_digest,
    )

    change = unit.changes[0]
    if (
        manifest.unit_uid != unit.uid
        or manifest.context_uid != change.context_uid
        or manifest.context_name != change.context_name
        or manifest.checkpoint_uid != change.checkpoint_uid
        or archived_context.uid != change.context_uid
        or archived_context.name != change.context_name
        or context_record_digest(archived_context)
        != context_record_digest(change.after)
        or manifest.source_context_uid != receipt.source_context_uid
        or manifest.source_context_name != receipt.source_context_name
        or manifest.analysis_uid != receipt.analysis_uid
        or manifest.source_workbench != receipt.source_workbench
        or manifest.current_before != receipt.current_before
    ):
        raise ConcurrentContextUpdateError(
            "The archived Atomize result changed before Redo."
        )
    source_analysis = store.load_atomize_analysis(manifest.source_context_uid)
    if source_analysis is None or source_analysis.uid != manifest.analysis_uid:
        raise ConcurrentContextUpdateError(
            "The Source Atomize analysis changed before Redo."
        )
    reviewing = store.load_atomize_workbench(source_analysis)
    terminal = None
    if manifest.source_workbench is None:
        if reviewing is not None:
            raise ConcurrentContextUpdateError(
                "The Source Atomize workbench changed before Redo."
            )
    else:
        if (
            reviewing is None
            or atomize_review_record_digest(reviewing)
            != manifest.reviewing_workbench_digest
        ):
            raise ConcurrentContextUpdateError(
                "The Source Atomize workbench changed before Redo."
            )
        terminal = copy.deepcopy(reviewing)
        terminal.output_context_name = change.context_name
        terminal.record_application(
            output_context_name=change.context_name,
            checkpoint_uid=change.checkpoint_uid,
        )
        if atomize_review_record_digest(terminal) != manifest.terminal_workbench_digest:
            raise ConcurrentContextUpdateError(
                "The terminal Atomize workbench changed before Redo."
            )
    output_analysis = load_archived_atomize_analysis(archive)
    if (
        output_analysis.uid != manifest.analysis_uid
        or output_analysis.context_uid != change.context_uid
        or output_analysis.context_name != change.context_name
    ):
        raise ValueError("Archived Atomize analysis identity is invalid.")
    store._assert_context_storage_available(change.context_name)
    analysis_path = store._atomize_analysis_path(change.context_uid)
    if analysis_path.exists() or analysis_path.is_symlink():
        # An absent Context does not authorize overwriting a newly saved artifact.
        raise ConcurrentContextUpdateError("Output Atomize analysis already exists.")
    return PreparedAtomizeRestore(archived_context, manifest, reviewing, terminal)
