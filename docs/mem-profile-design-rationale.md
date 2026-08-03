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
    └── <run-profile-uid>/...         # initialized Study members
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

The first three branches contain participant-owned starting state. The
`granted-memory` branches contain editable source material that becomes
permissioned authority views only when a Study is initialized. Keeping the
authoring source in one Profile makes incomplete Memory sets easy to inspect,
import, and revise without coordinating six live Profile identities.

## Timestamped Study groups

`mem init-study [NAME]` is the repeatable run-oriented entry point. It snapshots
the currently registered `study-baseline` Profile, not the generated bundle,
then publishes fresh namespaced copies under one timestamped heading:

```text
pilot-001  STUDY   created=2026-08-03T20:34:05+00:00
  ├─ Task 1  profile=pilot-001-task-1
  ├─ Authority 1  profile=pilot-001-task-1-campus-authority
  ├─ Task 2  profile=pilot-001-task-2
  ├─ Authority 2  profile=pilot-001-task-2-proposal-authority
  ├─ Task 3  profile=pilot-001-task-3
  └─ Authority 3  profile=pilot-001-task-3-healthcare-authority
```

Omitting `NAME` generates `study-YYYYMMDDTHHMMSSZ-<uid-prefix>`, so two
initializations in the same second remain distinct. The timezone-aware UTC
`created_at`, Study UUID, task number, source-manifest digest, and canonical
language, exact branch digest, and source baseline Profile UID/name are frozen
into each child Profile's provenance. This is a display group, not a parent
MemoryStore: every Task retains its own `state.json`, Context graph,
translations, and query boundary, while operational history begins empty at
Study creation.

The baseline's `granted-memory/task-N` branches create namespaced authority
Profiles and run-specific grant UIDs in the same transaction. Those authority
Profiles remain explicit,
switchable registry owners and appear beneath the same Study heading beside
the three participant-facing Task Profiles. Keeping them visible lets a
researcher inspect or revise source data without bypassing Profile isolation;
participants still work in the Task Profiles.

Initialization locks one registry generation and one complete baseline Context
snapshot, splits the six logical branches into clean staged stores, resolves
grants, publishes the stores, and atomically replaces the registry. A duplicate
Study name or any topology, copy, grant, or registry failure publishes none of
the new Profiles.
The previously active Profile intentionally remains active, so creating a
Study never silently redirects an unrelated terminal's next `mem` command.

## Why the source is merged but initialized runs are split

The study needs two kinds of navigation with different meanings:

- Profile selection changes the entire experimental memory environment.
- Context switching navigates within one selected environment.

The baseline is an authoring template, not a participant execution boundary.
Merging it keeps Task 1--3 and their granted source material in one selectable,
copyable unit while the corpus is still changing. Its prefixes are part of a
validated template contract and are stripped only during initialization.

Initialized Task Profiles remain separate because their `state.json`, history,
query sessions, write policy, and granted capabilities are experimental state.
Authority branches are also split into ordinary source-owner Profiles so a
grant remains a real cross-Profile permission view. Thus one baseline snapshot
is convenient to edit without weakening isolation in a run.

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
Profile. Initialization later snapshots only allowlisted baseline data and
publishes all required staged roots before atomically publishing one registry
generation. A failure leaves the authoring store, package sources,
and prior registry unchanged.

Profile names are portable single segments. Managed storage uses stable UUID
directories so a future display-name rename need not move the data. The fixed
`authoring` profile cannot be imported over or replaced.

## Authority, query-only, and translation boundaries

New study query-only data is an ordinary Context tree in its task-specific
authority Profile. A task receives only `QUERY`, so `mem ls` and `mem show`
render public view metadata without opening the tree. Selecting the authority
Profile gives the owner normal CRUD. Legacy concealed `query-sources/` remain
supported but are no longer the study bundle's source model. Korean
representations remain same-UID translation catalogs rather than additional
Contexts or Memories.

See `profile-authority-grant-design-rationale.md` and
`query-session-design-rationale.md` for permission, precedence, and optional
transcript retention contracts.

This is a research-prototype UI boundary, not operating-system access control.
The local account can still read its files.

## Alternatives considered

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
- Study creation records provenance and a creation timestamp. Whole-session
  command/event logging and Study completion/archive state remain a separate
  lifecycle boundary; ordinary checkpoint and opt-in query-session history
  retain their existing narrower contracts.
- `mem profile import-study` is a checkout-oriented research convenience; a
  packaged installation must pass `--from` when generated bundles are not
  shipped with the Python package.
