# Clean baseline Profile import design rationale

## Decision

`mem import NAME --from STORE` creates a new isolated managed Profile from the
durable content baseline of an existing MemoryStore. It is intentionally not an
archival clone and does not change the active Profile:

```bash
mem import rehearsal-01 --from ./template/.mem
mem profile rehearsal-01
```

The new Profile gets a fresh Profile UUID. Context and Memory UUIDs remain
unchanged so repeated studies can compare the same starting stimulus inside
different Profile namespaces. Provenance records `kind=BASELINE_IMPORT`, a
timezone-aware import timestamp, and a SHA-256 digest of the admitted baseline.
It does not retain an absolute source path.

## Baseline allowlist

Clean import copies only:

- `state.json`, including the template-selected current Context;
- every `contexts/**/context.json` record;
- `query-sources/` records required by legacy query references; and
- `translation-views/` records that represent baseline content identity.

Everything else is outside the baseline. In particular, clean import does not
copy Context checkpoints; undo/redo receipts; query, Ground, Meld, or Atomize
sessions; caches; staged updates; locks; lifecycle ledgers; or write-protection
state. An allowlist was selected so a new operational artifact cannot silently
leak into a participant run.

The source is validated as a link-free ordinary-file tree. Its admitted digest
is checked before and after copying and against the staged destination, so a
changing source cannot publish a mixed baseline.

## Study initialization

`mem init-study [NAME]` validates all three fixture packages first and then
atomically publishes `NAME-task-1`, `NAME-task-2`, and `NAME-task-3` with this
same clean copier. Omitting `NAME` produces a timestamped unique Study name.
Each Profile stores the shared Study UUID/name/timestamp, task number, fixture
manifest digest, and baseline digest. That metadata lets Profile inventory group
many runs without making Profiles hierarchical or sharing runtime state.

The active Profile and fixture source remain unchanged. If any validation,
copy, publication, or registry write fails, none of the three Profiles remains
registered. This all-or-nothing boundary is why `init-study` does not simply
invoke the public `mem import` command three times.

## Relationship to archival import

`mem profile import NAME --from STORE` remains the explicit archival operation:
it copies the complete validated store, including history. `mem profile
import-study` remains the legacy fixed-name archival fixture import. The
different command surfaces keep the history-retention choice visible.

## Alternatives and limitations

- A Profile fork was rejected for participant setup because inherited history
  makes authoring and participant actions difficult to distinguish.
- Copying then deleting known session directories was rejected because a new
  runtime artifact could be missed.
- Rebuilding Memories with fresh UUIDs was rejected because it would destroy
  stable cross-run stimulus identity.
- Clean import does not provide upstream synchronization, refresh, merge,
  replacement, or removal; those need separate recoverable workflows.
- The baseline digest proves which files were imported, not that their claims
  are correct or appropriate for a study.
