# MemoryStore profile design rationale

## Decision

`mem profile` selects one complete local MemoryStore. It is deliberately a
different namespace from `mem switch`:

```text
mem profile use study-baseline  # select the editable source store
mem profile study-baseline      # concise spelling of the same selection
mem switch              # select a Context inside that store
```

In a terminal, the bare `mem profile` command is the primary Profile browser.
It opens a full-height list at the current Profile, labels that row `CURRENT`,
labels the selected non-current candidate `USE`, and changes the selector
only after Enter. Arrow keys move the candidate and Escape or `q` exits
without a mutation. This makes the whole-store boundary visible before a
Context-level command such as `mem ls` or `mem switch` is run. `mem profile
use NAME` remains the explicit form for scripts, while `mem profile NAME` is
the concise interactive spelling requested to parallel `mem switch NAME`.
Both forms reach the same validation, locking, and atomic selector update;
the shorthand is parser routing rather than a second mutation path. Known
subcommands (`list`, its hidden `ls` alias, `current`, `use`, `import`,
`import-study`, and `grant`) take precedence, so a Profile whose name equals
one of those reserved command tokens must be selected with the explicit `use`
form. `mem profile list` remains an explicit inventory command.

When standard input or output is not a TTY, bare `mem profile` prints that
inventory instead of opening a picker or emitting help. This gives logs,
shell pipelines, and agent-driven diagnostics a stable read-only result. The
picker returns only a registered display name; the normal `use_profile`
boundary re-loads and validates the registry and selected store before the
active selector is changed, so a stale screen is not authority to switch.

Each Profile row also displays its incoming granted public view names. A view
name is registry routing metadata; displaying it neither opens nor copies the
authority source. Legacy `QueryContextRef` sources may still appear as a
separate `query=...` annotation. Neither kind is offered to `mem switch`:
granted views are per-command capabilities, and legacy query sources are not
ordinary Contexts in the selected Profile.

Each row reports both Context and Memory cardinality, with ownership kept
explicit:

```text
Contexts 14 owned + 1 granted · Memories 375 owned + 75 granted
```

`owned` means an ordinary Context or direct `Memory` record physically stored
inside that Profile. `granted` means a distinct authority-owned Context or
direct Memory reachable through an incoming grant that includes `READ`.
Repeated public aliases do not increase either count: the inventory
deduplicates by authority Profile and stable Context identity. Memory refs,
embedded Context refs, legacy query refs, checkpoints, and translation views
are not counted as Memories. A query-only authority grant is listed as a view
but does not add to the `READ`-granted cardinality. This separation prevents a
concise inventory from silently equating storage, delegated read access, and
query reachability.

The name *profile* was chosen instead of *account* because no authentication
or remote identity changes. A Profile is a locally registered store root; an
authority grant is a separate relationship between two such roots.

The backward-compatible `~/.mem` remains the fixed `authoring` profile.
Managed profiles are editable copies under an external control plane:

```text
~/.mem/                              # authoring store, never moved
~/.mem-profiles/
├── registry.json                    # active profile selector
├── registry.lock
└── stores/
    ├── <stable-profile-uid>/         # study-baseline
    └── <run-profile-uid>/            # one complete initialized Profile
```

`mem profile import-study` validates the three generated packages once and
publishes one editable `study-baseline` Profile. Package sources remain
unchanged. The baseline uses one explicit Context contract:

```text
study-baseline
├── task-1/...
├── task-2/...
├── task-3/...
└── granted-memory/
    ├── task-1/...
    ├── task-2/...
    └── task-3/...
```

The first three branches contain participant starting state. The
`granted-memory` branches contain the associated source material as ordinary
Contexts. Keeping all six branches in one Profile makes incomplete Memory sets
easy to inspect, import, revise, and copy without coordinating identities that
are not yet stable.

Every slash-delimited branch is completed with real empty ordinary Contexts
for lexical prefixes absent from an older fixture package. For example,
`task-1/participant` exists even when the package began at
`participant/construction-updates`. These navigation Contexts neither create
embed edges nor copy Memory. They ensure `mem switch ..` reaches every parent
and `mem ls -R task-1` cannot lose a valid deeper subtree behind a missing
intermediate name. `init-study` copies those real structural parents together
with every descendant, so upward navigation and recursive listing have the
same topology in the initialized Profile as in the baseline.

## Single-Profile Study snapshots

`mem init-study [NAME]` is the repeatable run-oriented entry point. It snapshots
the currently registered `study-baseline` Profile, not the generated bundle,
and publishes exactly one ordinary managed Profile:

```text
pilot-001  USE  Contexts 130 owned + 0 granted · Memories 1278 owned + 0 granted
```

The target is named exactly `NAME`; no `-task-N` or authority suffix is added
and no synthetic STUDY heading is created. Omitting `NAME` generates
`study-YYYYMMDDTHHMMSSZ-<uid-prefix>`, so two initializations in the same second
remain distinct. `--from-profile` selects another registered self-contained
source while the default remains the stable `study-baseline` name rather than
the globally active Profile.

The snapshot preserves the complete canonical Context names, every
Context/Memory/reference identity, declared query sources and translation
views, and `state.json.current`. In particular, `task-1`, `task-2`, `task-3`,
and `granted-memory/task-{1,2,3}` remain branches of the same Profile. It does
not split, rename, remap, synthesize, or grant those branches. Registry grants
are relationships outside a MemoryStore; because silently dropping them would
change the source's capabilities, `init-study` rejects a source Profile that
participates in an incoming or outgoing grant.

Initialization uses the clean Profile-import allowlist. Checkpoints, command
receipts, workflow and query sessions, caches, locks, lifecycle events,
clipboard state, and write-protection state do not cross into the run. The
admitted source files are digested before and after the staged copy and at the
destination. Profile-name collisions are case-insensitive. A duplicate name,
invalid/changing source, or registry failure before atomic replacement
publishes nothing. If replacement is already visible but the following
directory `fsync` cannot confirm durability, deleting the store would corrupt
the visible registry; the command instead reports the uncertain durability and
leaves the new Profile registered with its store intact.
The previously active Profile intentionally remains active, so initialization
never silently redirects an unrelated terminal's next `mem` command.

## Why initialized topology now remains merged

Profile selection changes the complete experimental memory environment;
Context switching navigates within that environment. The current Study corpus
is still being revised, so Task 1--3 and the `granted-memory` material do not
yet justify six independently managed run identities. Copying the whole
baseline keeps the unit being reviewed identical to the unit being initialized
and makes the source/clone relationship verifiable with one baseline digest.

This deliberately does not provide per-task permission isolation in a newly
initialized Profile: a user of that Profile can navigate all of its ordinary
branches. If a later stabilized experiment needs participant/authority
separation, that is a separate explicit grant workflow rather than an implicit
side effect of `init-study`. Registries containing older
`STUDY_RUN_TASK`/`STUDY_RUN_AUTHORITY` Profiles remain readable and selectable;
the legacy grouping UI is retained only for those persisted records and new
initializations do not add to it.

## Process snapshot and concurrency

The profile registry lives outside every MemoryStore. When
`memcommit.store` is imported, it validates the registry and resolves one root
for that process. `mem profile use` atomically replaces only the registry
selector, so it affects the next `mem` invocation.

An already running process intentionally remains bound to the root it opened.
This avoids moving a directory underneath a writer and avoids a global
directory-swap lock that existing commands do not share. The registry uses an
external file lock, generation number, fsynced temporary file, and atomic
replacement. A corrupt existing registry fails closed; only an absent registry
falls back to the legacy `authoring` store without creating metadata.

## Import boundary

`mem profile import` is an archival whole-store copy. The top-level `mem
import` instead creates a clean baseline Profile through an allowlist:
`state.json`, ordinary `context.json` records, query-source records, and
translation views. It deliberately excludes checkpoints, command receipts,
sessions, semantic workbenches, caches, locks, lifecycle ledgers, clipboard
state, and write-protection state. The baseline digest and timezone-aware
import timestamp remain in Profile provenance instead of carrying authoring
history into the new run.

Both forms reject symbolic links and special files, validate Context path/name
agreement, current-Context state, query-reference/source identity, and
translation-catalog ownership, and stage on the destination filesystem. Study
bootstrap additionally validates Profile roles, grant permissions, exclusions,
frozen scopes, and attachment identities before composing the single baseline
Profile. Initialization later copies that complete baseline through the same
allowlist and publishes one new Profile in one registry generation. A
pre-publication failure leaves the authoring store, source Profile, package
sources, and prior registry unchanged; a post-replacement durability error
preserves the already-visible Profile/store pair rather than creating a dangling
registry entry.

Profile names are portable single segments. Managed storage uses stable UUID
directories so a future display-name rename need not move the data. The fixed
`authoring` profile cannot be imported over or replaced.

## Authority, query-only, and translation boundaries

Generated study packages still model query-only data in separate authority
stores and grant templates, and `profile import-study` validates that package
contract before composing the baseline. A new single-Profile snapshot does not
activate those grants: its merged `granted-memory` branches are ordinary owned
Contexts. Legacy split Study Profiles keep their existing grant behavior.
Korean representations remain same-UID translation catalogs rather than
additional Contexts or Memories.

See `profile-authority-grant-design-rationale.md` and
`query-session-design-rationale.md` for permission, precedence, and optional
transcript retention contracts.

This is a research-prototype UI boundary, not operating-system access control.
The local account can still read its files.

## Alternatives considered

- **Split each initialization into Task and Authority Profiles:** retained only
  for legacy registry compatibility, not new creation. It changed the baseline
  topology during copy and required six identities plus grants before the
  underlying Memory sets and boundaries were stable.
- **Merge all task stores into `~/.mem`:** rejected because it collapses study
  isolation and creates mixed state and routing semantics.
- **Physically rename or swap `~/.mem`:** rejected because an already running
  writer could continue against a directory that had been moved underneath
  it.
- **Point `~/.mem` at profiles with a symlink:** rejected because it weakens
  existing path and symbolic-link safety checks.
- **Make `mem switch` scan package output directories:** rejected because it
  would list targets that are not members of the active store and cannot be
  switched to by the existing command contract.

## Current limitations

- Profile selection takes effect for the next CLI process, not an operation
  already running in another terminal.
- Editing a managed profile does not rewrite `docs/fixtures/` or refresh the
  generated package. Re-import refuses to overwrite the edited profile.
- Profile removal, replacement, rename, backup, and reset are intentionally
  deferred until they have explicit recoverable workflows.
- Study Profile creation records source Profile identity, a baseline digest,
  and an import timestamp. Whole-session command/event logging and Study
  completion/archive state remain a separate lifecycle boundary; ordinary
  checkpoint and opt-in query-session history retain their existing narrower
  contracts.
- `mem profile import-study` is a checkout-oriented research convenience; a
  packaged installation must pass `--from` when generated bundles are not
  shipped with the Python package.
