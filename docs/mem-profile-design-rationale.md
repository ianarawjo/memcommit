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
subcommands (`list`, its hidden `ls` alias, `current`, `create`, `use`, `import`,
`import-study`, `archive-study`, `rename`, and `grant`) take precedence, so a
Profile whose name equals one of those reserved command tokens must be selected
with the explicit `use` form. `mem profile list` remains an explicit inventory
command.

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
├── archives/studies/
│   └── <legacy-study-uid>/manifest.json
└── stores/
    ├── <stable-profile-uid>/         # study-baseline
    ├── <run-profile-uid>/            # participant Task branches
    ├── <run-authority-uid>/          # run-private granted Memory
    └── <archived-profile-uid>/       # detached but not moved or deleted
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

## Isolated two-Profile Study runs

`mem init-study [NAME] --scenario legacy-v1` is the repeatable legacy
run-oriented entry point. It snapshots the currently registered
`study-baseline` Profile, not the generated bundle,
and publishes two managed Profiles plus their grants in one registry generation:

```text
pilot-001                 Contexts 47 owned + 52 granted · Memories 375 owned + 675 granted
pilot-001-granted-memory  Contexts 85 owned + 0 granted · Memories 915 owned + 0 granted
```

The participant target is named exactly `NAME`; its run-private authority is
named `NAME-granted-memory`. Omitting `NAME` generates
`study-YYYYMMDDTHHMMSSZ-<uid-prefix>`, so two initializations in the same second
remain distinct. `--from-profile` selects another registered self-contained
source while the default remains the stable `study-baseline` name rather than
the globally active Profile.

The snapshot preserves every durable Context, Memory, and translation identity
while remapping placement. Participant content remains below `task-N`; source
content moves from baseline path `granted-memory/task-N/...` to authority path
`task-N/...`. Actual borrowed views appear directly below `task-N`, such as
`task-1/campus-wiki`. A narrower query-only grant overrides a readable
parent, so list/show/export access remains closed while `mem query` receives
only the frozen authority scope.

The authority store is copied for every run. Task 1's allowed add or edit saves
through the grant into that copy and cannot mutate `study-baseline` or another
run. This reuses the existing permission, most-specific override, grant
revocation, checkpoint provenance, and mutation revalidation boundaries rather
than introducing a second local ACL implementation.

Initialization uses the clean Profile-import allowlist. Checkpoints, command
receipts, workflow sessions, legacy Query-session records, caches, locks, lifecycle events,
clipboard state, and write-protection state do not cross into the run. The
admitted source files are digested before and after the staged copy and at the
destination. Profile-name collisions, including the derived authority name,
are case-insensitive. A duplicate name,
invalid/changing source, or registry failure before atomic replacement
publishes nothing. If replacement is already visible but the following
directory `fsync` cannot confirm durability, deleting the store would corrupt
the visible registry; the command instead reports the uncertain durability and
leaves the complete pair and grants registered with both stores intact.
The participant Profile becomes active in the same registry generation, so the
next `mem` process enters the isolated run without exposing a partial pair.

## Why initialized topology is a pair rather than six Profiles

Profile selection changes the complete experimental memory environment;
Context switching navigates within that environment. The current Study corpus
is still revised as one baseline, while a participant run must enforce the
different Task permission conditions. Two Profiles are the smallest topology
that permits real cross-Profile grants: one participant owner and one isolated
authority owner. Six per-task Profiles were rejected because Profile switching
would fragment a single run and duplicate its control-plane identity. One
physical Profile was rejected because ordinary local Context resolution would
bypass the grant engine.

Registries containing older
`STUDY_RUN_TASK`/`STUDY_RUN_AUTHORITY` Profiles remain readable and selectable;
the legacy six-Profile grouping UI is retained only for those persisted records.

Current `STUDY_RUN`/`STUDY_RUN_GRANTED_MEMORY` provenance is also projected as
one group in both the terminal picker and stable list:

```text
pilot-001  STUDY
├─ Participant     profile=pilot-001
└─ Granted memory  profile=pilot-001-granted-memory
```

The group and roles come from stable Study UID/source-kind provenance, not from
the current display names. A Profile rename therefore keeps the same Study
label and role, while an explicit Study rename can change that shared label
without changing either Profile name. These two current roles also opt into the
Study action ledger; only the Participant adds complete command text and
focused Help wording/results, while the granted-memory role remains
content-free within that detailed ledger. Every Profile's separate generic
command-attempt ledger retains its complete command. The baseline, ordinary
Profiles, and legacy six-Profile runs do not opt into detailed Study actions.
Initialization selects the new participant Profile in the same
atomic registry generation that publishes the complete pair and grants. Its
detailed ledger is seeded explicitly because the `init-study` root attempt
began in the previous Profile.

## Recoverable legacy Study archive

`mem profile archive-study NAME` applies only to a complete persisted split
Study group created by the older initialization model. It does not archive an
ordinary single-Profile Study. The command validates the group as one unit,
rejects it when any member is the active Profile, and rejects any grant whose
other endpoint lies outside the group. Internal grants are archived together
with the member Profile records.

The archive manifest records the Study identity and creation time, archive
time, source registry generation, exact ordered Profile and internal-grant
records, and `control_relative_path` store locators relative to
`profile_control_dir()` (normally `~/.mem-profiles`). It contains no
host-absolute store paths. The manifest is fsynced and published below
`archives/studies/<study-uid>/` before one registry generation removes all
members and internal grants from the live selector.

The member managed stores deliberately remain at their stable
`stores/<profile-uid>/` paths. No Memory, checkpoint, session, or other store
byte is moved or deleted. This preserves the process-snapshot rule: a command
that resolved an old root before the registry detach can finish against the
same path. It also leaves all data and the exact control-plane records
available for a future restore command. This is a durable control-plane detach,
not a point-in-time immutable store snapshot: a process that resolved an old
root before `archived_at` may still finish a write to that unchanged path.
Restore is not implicit and is not yet implemented.

If registry publication fails before replacement, the original registry
remains authoritative and the prepared manifest remains for retry. Deleting a
published directory in place was rejected because an interrupted recursive
rollback could turn a valid retry point into a partial, occupied destination.
An exact matching manifest left by a failed invocation or a process that
stopped between manifest publication and registry detach is validated,
re-fsynced, and reused; a foreign or modified destination fails closed. If
replacement is already visible but its final durability cannot be confirmed,
the command keeps the manifest and detached registry state rather than
manufacturing a dangling rollback. Archiving and
`mem init-study NAME` remain two explicit commands: the first preserves the
old run, while the second allocates a new ordinary Profile UID from the current
baseline together with its run-private granted-memory Profile and grants.

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

## Empty managed Profile creation

`mem profile create NAME` publishes the smallest valid managed store: one
private `contexts/` directory, one `state.json` with no current Context, a fresh
Profile UID, and `EMPTY_PROFILE` creation provenance. It deliberately creates
no Context, Memory, Grant, checkpoint, command history, session, cache, lock, or
write-protection record. The active Profile remains unchanged; selecting the
new row with `mem profile use NAME` and creating its first Context with `mem init
CONTEXT` are separate visible actions.

Creation belongs to the Profile namespace rather than overloading top-level
`mem init`, whose established resource is a Context inside the already active
Profile. It also differs from both import routes: clean Profile import copies an
allowlisted content baseline, while archival `mem profile import` copies a
complete store. A source-free empty Profile must not silently inherit either
content or operational history.

In the Profile picker, `N` opens the shared exact one-line name field. Enter
freezes `mem profile create NAME` and its effects for review; only the common
approval key applies it. The command revalidates the frozen registry generation
and name under the registry lock, then stages the complete empty store before
publishing its stable UID directory and replacement registry. A failure before
registry publication removes the staged or rolled-back store. If registry
replacement is visible but its durability confirmation fails, the store remains
present and the receipt reports the uncertain durability boundary rather than
deleting a possibly registered root.

Successful picker creation reloads the registry and focuses the appended new
row without selecting it. Automatic selection was rejected because creation
and whole-store switching are independent control-plane effects, and Profile
import already preserves the active selection. The person can inspect the zero
inventory row and press Enter to switch explicitly.

Names retain the portable one-segment contract. Creation rejects
case-insensitive collisions with live or removed Profile identities, fixed
`authoring` and `study-baseline` anchors, and live legacy Study headings. The
retained-name boundary keeps tombstones and Study grouping unambiguous.

## Stable-identity Profile rename

`mem profile rename` changes one live managed Profile's display name without
changing which complete MemoryStore it identifies. Its one- and two-argument
forms deliberately have different target selection:

```text
mem profile rename NEW       # rename the current Profile
mem profile rename OLD NEW   # rename this explicitly named Profile
```

Interactive `mem profile` places the same operation beside its target. `R` on
an eligible Profile opens the shared exact one-line name field prefilled with
the current display name. Enter produces an exact
`mem profile rename OLD NEW` review; a second Enter or `A` applies it. Escape
returns from review to the name field, then from the field to the picker.
Study headers route to the separate whole-Study rename described below. Fixed
anchors and individually protected legacy Study members fail in the picker
before the Profile-name field opens.

The picker receipt freezes the target Profile UID and registry generation.
Application checks both under the registry lock, then reloads the complete
picker catalog and restores the renamed row's visual position. A concurrent
Profile use, Grant mutation, removal, or rename therefore cannot redirect the
reviewed action to a same-named replacement. Context pickers deliberately do
not expose rename because Context namespace relocation is a graph migration,
but the reviewed line-oriented `mem rename OLD NEW` command exposes that
separate Context operation. Keeping the resource-qualified Profile spelling
prevents slash-delimited Context operands from entering Profile-name
validation.

In the one-argument form, `NEW` is never interpreted as an existing Profile
selector. The command acquires the Profile registry lock and then captures the
current Profile from that locked registry generation. The two-argument form
resolves `OLD` from the same locked generation. For a real rename, both forms
validate the target store before publishing one atomic registry generation, so
a concurrent `profile use`, grant mutation, archive, or rename cannot change
the target or interleave a partial control-plane update.

A rename replaces only the selected `ProfileEntry.name`. The Profile UID,
managed `stores/<profile-uid>/` directory, kind, source provenance, registry
order, grants, and active UID remain unchanged. If the renamed Profile is
active, the same UID remains selected under the new display name; otherwise
the previously active Profile remains active. Because grants bind Profile UIDs,
their capabilities and revisions do not change, although later human-readable
grant output uses the new live display name. Context names, Memories, current
Context state, checkpoints, sessions, and every other store byte are untouched.
The cooperative `mem lock profile` policy protects writes inside that store,
not administrative registry metadata, so it does not block display-name
rename. Because the UID and root remain stable, the protection state remains
attached to the same Profile after rename.

Source provenance and archive manifests are historical snapshots, not live
display-name indexes. A Profile rename therefore does not rewrite an earlier
`source_profile_name`, legacy Study provenance, or an archived Profile record.
Those records retain the name observed when they were created, while their
stable UIDs preserve identity. Archived names do not reserve a live display
name; only the current registry and live legacy Study groups participate in
rename collision checks.

Profile names retain the portable one-segment contract. Existing Profile-name
collisions and live legacy Study-group-name collisions are checked
case-insensitively. An exact same-name request, where the resolved target name
already equals `NEW`, is a successful no-op: it does not inspect the store,
publish a new registry generation, or turn a fixed anchor into an error. A
case-only change such as `Pilot` to `pilot` is a real rename and is allowed
when the same Profile owns both spellings.

The fixed `authoring` and `study-baseline` names are protected both as rename
sources and destinations. `authoring` is the backward-compatible store anchor;
`study-baseline` is the default `init-study` and bootstrap anchor. Members of a
live legacy split Study are also protected from individual rename because their
task/authority names are validated against immutable grouping provenance. A
whole legacy-group rename would need to revise all member identities and is not
an ordinary Profile rename.

CLI subcommand tokens remain legal Profile names for compatibility with import
and the existing shorthand contract. Registered subcommands and their supported
hyphen-omitted input aliases take precedence over shorthand selection. A
Profile named `archive-study` or `archivestudy`, for example, must be selected
with `mem profile use NAME`; rename success output always prints that explicit
form. An existing Profile named `rename` can itself be renamed with
`mem profile rename rename NEW`.

Success output distinguishes an active target from an inactive one, prints the
unchanged Profile UID and store path, and states that store data, grants, and
provenance were not modified. An exact no-op reports that the Profile already
has that name. If registry publication fails and the old registry is still
visible, the rename fails with the old name intact. If replacement is visible
but the following durability confirmation fails, the command reports that
durability is uncertain and that the Profile remains renamed. If registry
state cannot be classified, it directs the person to `mem profile list`
instead of claiming either name won.

## Stable-identity Study rename

The Study heading in the Profile picker is a separately editable display label.
Pressing `R` on that heading, or running
`mem profile rename-study OLD NEW`, freezes the selected Study UID and registry
generation, accepts one exact portable name, shows the exact command for
approval, and publishes one replacement registry generation. The Study UID,
member Profile UIDs, store directories, active Profile, Contexts, Memories, and
Grants remain unchanged. Study-label collisions are checked case-insensitively;
an exact same-name request is a successful no-op and a case-only change is a
real rename.

Current two-Profile runs deliberately keep their independently editable
participant and granted-memory Profile names. Renaming `pilot` to `trial-a`,
for example, changes only the `STUDY trial-a` heading; the child rows may still
be named `pilot` and `pilot-granted-memory`. Renaming both Profile rows
implicitly was rejected because it would collapse the separate Study and
Profile controls that the picker exposes and surprise anyone who had already
renamed one child independently.

Legacy six-Profile Studies are the compatibility exception. Their validator
derives every task and authority Profile name from `source.study_name`, so
changing only the heading would make the persisted group unreadable. A legacy
Study rename therefore rewrites the shared provenance label and all six derived
Profile display names atomically, after validating every generated name and
collision. It still does not move or rewrite a store, and the exact review says
that member names will change before approval.

Current Study action events retain the Study label observed when each event was
written. Readers bind historical events by Study UID, Profile UID, and role, so
earlier actions remain readable after a rename and later actions can carry the
new label without rewriting append-only telemetry. Treating the mutable label
as the ledger identity was rejected because it would either invalidate the
history or require rewriting the research record.

If another process changes the registry after picker selection, or if the
frozen Study UID no longer matches, Apply fails before publication. Registry
replacement uses the same fsynced temporary-file transaction as Profile rename.
A failure is reported as old, newly visible but durability-uncertain, or
unclassifiable based on the registry that can actually be read; no message
claims a rollback that cannot be proven.

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
directories, so a display-name rename does not move the data. The fixed
`authoring` profile cannot be imported over, replaced, or renamed.

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
- **Delete legacy Study stores after hiding their rows:** rejected because it
  destroys recoverability and can invalidate an already running process's
  frozen root.
- **Silently switch away from an active legacy Study:** rejected because an
  archive request must not redirect another terminal's next command.
- **Archive and initialize the replacement in one command:** rejected because
  preserving old state and allocating a new run are independently reviewable
  mutations with different failure boundaries.
- **Move or rename a managed Store directory with its display name:** rejected
  because stable UID paths are the Profile identity boundary and an already
  running process may be using the resolved root.
- **Rewrite prior provenance, grants, and archive manifests after rename:**
  rejected because grants already bind stable UIDs, while provenance and
  archives must retain the historical name observed when they were recorded.
- **Rename one member of a legacy split Study:** rejected because its derived
  task or authority name is part of the grouping provenance contract. A future
  whole-group workflow would be a separate multi-record mutation.

## Current limitations

- Profile selection takes effect for the next CLI process, not an operation
  already running in another terminal.
- Editing a managed profile does not rewrite `docs/fixtures/` or refresh the
  generated package. Re-import refuses to overwrite the edited profile.
- Generic Profile removal, replacement, backup, and reset remain deferred. The
  narrow legacy split-Study archive has an explicit recoverable manifest, but a
  matching restore command remains future work.
- Profile rename is limited to live ordinary managed Profiles. It does not
  rename the fixed authoring/baseline anchors, individual legacy Study members,
  archived records, historical provenance, or any Context inside the Store.
- `archive-study` does not promise repeated-success acknowledgement. After the
  registry detach commits, repeating the old Study name reports that the live
  legacy Study does not exist; the durable manifest remains the completion
  record until a dedicated archive-status surface exists.
- Study Profile creation records source Profile identity, a baseline digest,
  and an import timestamp. Whole-session command/event logging and ordinary
  single-Profile Study completion/archive state remain a separate lifecycle
  boundary; ordinary checkpoint and opt-in query-session history retain their
  existing narrower contracts.
- `mem profile import-study` is a checkout-oriented research convenience; a
  packaged installation must pass `--from` when generated bundles are not
  shipped with the Python package.
