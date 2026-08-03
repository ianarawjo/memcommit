# MemoryStore profile design rationale

## Decision

`mem profile` selects one complete local MemoryStore. It is deliberately a
different namespace from `mem switch`:

```text
mem profile use task-1  # select a whole local store
mem switch              # select a Context inside that store
```

In a terminal, the bare `mem profile` command is the primary Profile browser.
It opens a full-height list at the current Profile, labels that row `CURRENT`,
labels the selected non-current candidate `USE`, and changes the selector
only after Enter. Arrow keys move the candidate and Escape or `q` exits
without a mutation. This makes the whole-store boundary visible before a
Context-level command such as `mem ls` or `mem switch` is run. `mem profile
use NAME` remains the explicit form for scripts, and `mem profile list`
remains an explicit inventory command.

When standard input or output is not a TTY, bare `mem profile` prints that
inventory instead of opening a picker or emitting help. This gives logs,
shell pipelines, and agent-driven diagnostics a stable read-only result. The
picker returns only a registered display name; the normal `use_profile`
boundary re-loads and validates the registry and selected store before the
active selector is changed, so a stale screen is not authority to switch.

Each Profile row also displays the public locator names of its routed
query-only references, such as `query=campus-wiki`, before the potentially
long current Context locator. A count alone made an included source look
absent and was often clipped at ordinary terminal widths. The name is routing
metadata that is already used by `mem query`; displaying it neither reads nor
reveals the concealed source. An orphaned concealed record without an ordinary
`QueryContextRef` may contribute to a diagnostic count but its name is not
publicized. Query-only sources remain absent from `mem switch` because they
cannot become an ordinary current Context.

The name *profile* was chosen instead of *account* because no authentication,
remote identity, or user ownership changes. A profile is only a locally
registered set of Contexts, checkpoints, translation views, query-only
sources, and store state.

The backward-compatible `~/.mem` remains the fixed `authoring` profile.
Managed profiles are editable copies under an external control plane:

```text
~/.mem/                              # authoring store, never moved
~/.mem-profiles/
├── registry.json                    # active profile selector
├── registry.lock
└── stores/
    ├── <stable-profile-uid>/         # for example, task-1
    ├── <stable-profile-uid>/         # task-2
    └── <stable-profile-uid>/         # task-3
```

`mem profile import-study` copies the three generated study packages into
managed roots in one all-or-nothing operation. The package sources remain
unchanged. The resulting copies may be edited with ordinary `mem` commands,
and their changes persist when another profile is selected and the person
later returns.

## Why profiles are not merged Contexts

The study needs two kinds of navigation with different meanings:

- Profile selection changes the entire experimental memory environment.
- Context switching navigates within one selected environment.

Putting all task Contexts into one active graph would make `mem switch` look
convenient during fixture authoring, but it would also mix three independent
`state.json` files, query routing, translation catalogs, histories, and study
conditions. It creates semantic collisions even where filesystem names do not
collide: for example, the Task 1 query-only name `campus-wiki` can coexist with
an older ordinary Context of the same name, and new task subtrees resemble
older development subtrees without sharing identity.

Profiles satisfy the underlying authoring need without that ambiguity: all
four stores are present locally and editable, while only one store is active
in any new CLI process. `mem profile list` is the cross-store inventory;
`mem switch` remains an honest inventory of the active store only.

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

Profile import rejects symbolic links and special files, validates Context
path/name agreement, current-Context state, query-reference/source identity,
and translation-catalog ownership, and copies into hidden same-filesystem
staging. Study import publishes all three staged roots before atomically
publishing their registry entries. A failure leaves the authoring store,
package sources, and prior registry unchanged.

Profile names are portable single segments. Managed storage uses stable UUID
directories so a future display-name rename need not move the data. The fixed
`authoring` profile cannot be imported over or replaced.

## Query-only and translation boundaries

Query-only sources travel with their complete profile but remain absent from
`mem switch`, `mem ls`, and ordinary Context editing. They are accessed only
through `mem query`. Korean ordinary representations remain same-UID
translation catalogs rather than additional Contexts or Memories.

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
- `mem profile import-study` is a checkout-oriented research convenience; a
  packaged installation must pass `--from` when generated bundles are not
  shipped with the Python package.
