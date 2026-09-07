# Exact Atomize Save As restoration

## Motivation and scope

Retained Atomize Save As checkpoints describe one command that created a final
Context, copied its analysis, recorded application on the Source workbench, and
could switch the current Context. Undo and Redo must restore those linked
effects together. Current in-place Atomize does not acquire a Save As route
from this compatibility handler; no provider is called and no Source frame is
re-executed during recovery.

The former `command_restoration/handlers/atomize.py` combined receipt decoding,
live-state validation, workbench transitions, locks, filesystem moves,
checkpoint publication, navigation, and manual rollback in one method. Its
single `moved` flag was set only after three renames, so failure of the second
or third move left earlier moves uncompensated. Undo also saved its checkpoint
before archive preparation entered the rollback scope. Redo consumed its
archive outside that scope, allowing cleanup failure after visible publication.

## Physical owners

All paths below are under `src/memcommit/persistence/store/command_restoration/`.

- `handlers/atomize/records.py` owns version-1 Save As receipt decoding and the
  Atomize archive manifest codec. The common `archive.py` delegates Atomize
  manifest validation here while retaining common path, Context, and history
  loading. Typed restoration fields do not make the recorded Source frame an
  executable input; the command unit's frozen after-image is authoritative.
- `handlers/atomize/preparation.py` reads and compares Context, analysis, and
  workbench records and prepares detached before/after workbench values.
  Domain `clear_application` and `record_application` methods still own their
  semantic transitions. Preparation performs no writes or lock acquisition.
- `handlers/atomize/restoration.py` retains the Store entry point and separate
  Undo/Redo workflows. It owns lock lifetimes, publication order, checkpoint
  effects, conditional navigation, archive consumption, and the inverse of
  every operation-specific write.
- `compensation.py` owns a process-local reverse-order callback stack. A move
  registers its own inverse immediately after success. Failed inverse calls
  are collected while the remaining inverses are attempted. An incomplete
  rollback reports its failures and retains the original execution exception
  as its cause. The helper has no Atomize policy or storage schema.

`command_restoration/__init__.py` and `record_restore_checkpoint.py` compose the
new physical owner directly. The latter continues forwarding root Store
atomic-write overrides to the module that performs the write.

## Invariants and failure boundary

- The command engine retains the command lock. The handler retains graph and
  target Context locks, then acquires Source/output session locks in sorted
  UID order. All preparation reads and ensuing writes/compensation share that
  lock boundary. The state lock is acquired for the final navigation phase and
  remains held through archive cleanup and any compensation; restoring an old
  whole-state record must not overwrite a concurrent navigation update.
- Undo archives the exact Context, complete checkpoint directory, and copied
  analysis, clears the Source application receipt when one existed, and only
  changes navigation when the output is still current. The no-workbench
  receipt variant remains supported.
- Redo restores the same Context UID, after-image, copied analysis UID,
  checkpoint lineage, and terminal Source receipt. It switches only if current
  still matches `current_before`. An unrelated current selection is preserved.
- Archive availability is checked and its directory prepared before Undo
  publishes a provisional checkpoint. That checkpoint is registered for
  compensation before any file move. Each rename has an independent inverse.
- Workbench and state inverses are registered before their writes, so an
  exception reported after replacement can still restore the original record.
  `_save_locked` retains its existing local checkpoint/write failure boundary;
  after it returns, the outer stack owns provisional checkpoint removal.
- Redo archive consumption stays inside compensation. Failure to unlink the
  manifest or remove the emptied archive restores its manifest, navigation,
  workbench, history, and files, leaving the command retryable when all inverses
  succeed. An empty shared parent is removed only on a best-effort basis.
- Redo cross-checks manifest identity and Source fields against the creation
  receipt, and refuses an already occupied output-analysis path. An absent
  Context alone must not authorize overwriting a newly saved analysis.
- Persisted field names and schema versions remain unchanged. Invalid nested
  workbench shapes and malformed digests fail at the shared operation codec.
  Existing histories are not migrated or regrouped.

## Alternatives and limitations

Splitting only Undo and Redo into two files would retain mixed abstraction
levels and duplicated record validation. Splitting every value and validator
into its own file would obscure the small set of owning concepts. The chosen
package keeps related types next to their codec or preparation code and leaves
Undo/Redo execution together for review of their symmetry and ordering.

A general transaction framework and a durable crash journal are outside this
change. Ordinary exceptions can be compensated; process termination, power
loss, noncooperating filesystem edits, or failed inverse writes can still leave
manual recovery necessary. Branch, Merge, and Sever keep their existing
mutation/rollback implementations; using a common archive reader does not
silently migrate their transaction policy.

## Verification evidence

- `tests/test_atomize_restoration.py` exercises repeated Undo/Redo against real
  isolated Store files, both workbench variants, every file-move failure,
  checkpoint and Context-write failure, workbench/state failure before and
  after write, archive preparation/manifest/cleanup failure, exact retry, and
  state-lock retention during compensation.
- `tests/test_atomize_restoration_records.py` checks version-1 manifest round
  trips and invalid receipt/manifest rejection through the common archive reader.
- `tests/test_atomize_restoration_preparation.py` checks write-free preparation,
  stale analysis/workbench/output rejection, and unrelated navigation retention.
- `tests/test_restoration_compensation.py` checks continued recovery after an
  inverse fails and preservation of the original error.
- `tests/test_checkpoint_restoration_package.py` checks single physical method
  ownership, Store composition, and root atomic-write failure injection.

Verification in the primary checkout passed 207 tests across these focused
tests and the related Undo, Branch, Merge, Sever, Atomize, and package-ownership
regressions, using `PYTHONPATH=src python -m pytest`. Ruff checks and formatting,
`git diff --check`, and `python scripts/verify_operation_evidence.py --check`
also passed.

The isolated commit snapshot, excluding unrelated working-tree changes, passed
217 tests in the same selected suite. Its one failure,
`test_operation_persistence_methods_have_one_focused_owner`, reports a Meld
method-ownership mismatch and was reproduced on unchanged parent `c2e88b73e`.
That pre-existing Meld discrepancy is outside this Atomize change. Evidence
generation and `--check` also passed against the isolated commit snapshot.

These are agent-authored implementation and test records, not human review or
approval evidence. Operation route classifications remain in their sole registry.
