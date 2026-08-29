# Context-rooted Ground workspace

## Status

Physical creation, loading, typed Memory editing, the unified saved/draft
session launcher, in-session exact Save Location control, the read-only
workspace TUI, Ground-local Undo, and the Distill, Elaborate, and Fit semantic
projections are implemented. The CLI
retains a transitional legacy-session route only for an already existing
legacy name; a physical workspace never reads or writes that parallel JSON.
Existing prototype Ground session JSON is not a migration input for a new
workspace.

Last reviewed: 2026-08-28.

## Motivating correction

The first Ground prototype persisted one operation-specific JSON session whose
Goal, Rules, Examples, frame bindings, decisions, and revision lived beside
ordinary Context storage. That made a Ground look like a special durable object
even though its meaningful material has the same Memory and Context semantics
as the rest of MemCommit. It also encouraged strong whole-session and graph
digest registries before an operation had selected the material it actually
consumed.

A Ground is now modeled as one named physical Context workspace. Creating
`project111` creates this exact require-new namespace batch:

```text
project111
├── project111/goals
├── project111/rules
├── project111/examples
├── project111/contexts
└── project111/relations
```

Every row is an ordinary Context with its own UID, direct-item order, Context
record, and checkpoint history. Goal, Rule, Example, and relationship
statements are ordinary Memories. The `contexts` lane accepts the same Memory,
`memory_ref`, ordinary `context_ref`, query-only route, and granted Context link
shapes supported by the existing Context model. Ground does not define a
parallel Memory schema or a hidden metadata sidecar.

## Workspace identity and manifest

The root Context UID is the Ground workspace identity. Its exact name is the
user-selected Ground name and may itself be namespaced, such as
`research/project111`. The root contains one first-class manifest Memory with a
small canonical payload:

- kind `memcommit.ground-workspace`;
- workspace/root UID;
- workspace schema version;
- Ground-local revision; and
- status.

The manifest marks the root and carries only workspace-level state. It does not
duplicate lane membership: the five exact lexical children are the source of
truth. The aggregate loader requires the root, all five children, distinct
Context identities, and exactly one manifest Memory.

Slash-delimited children remain lexical namespace descendants. They are not
silently reinterpreted as embedded Context edges. Conversely, an embedded or
granted Context inside `project111/contexts` remains a direct typed pointer and
does not become a lexical child. Existing namespace and embed traversal axes
stay independent.

## Creation contract

Ground creation is the one intentional Context-lifecycle responsibility owned
by Ground. It creates only its own fixed workspace skeleton. Branch, Embed,
Reference, Grant, Import, rename, and deletion remain independent operations.
They may create or attach material under the `contexts` lane, but the Ground
TUI must not invoke them as hidden subcommands.

Creation:

1. validates the exact root and every fixed child name;
2. constructs one root manifest Memory and an optional initial Goal Memory;
3. publishes all six Contexts require-new under one Store command lock and one
   complete lock set;
4. rolls back every newly created Context if any member cannot be published;
5. creates one initial checkpoint per Context; and
6. does not read or change the process-global current Context.

The initial Goal is not a scalar manifest field. `--goal` and `--set-goal`
resolve the shared Goal operand as one existing Context Memory, one direct
Memory, or process-local text, then materialize exactly one new ordinary
Memory in `/goals`. The checkpoint retains the copied operand's exact
provenance, while the stored Goal remains independent rather than becoming a
live alias or synchronization link.

Opening, previewing, or typing a name is not creation. Terminal creation must
retain a separately approved exact action before invoking this application
boundary. The creation unit is the workspace genesis and is not removable by
the in-workspace Undo action; workspace deletion remains a separately reviewed
structural command.

### Interactive entry and Save Location

Bare interactive `mem ground` always opens the common Operation Launcher, even
when no saved Ground exists. The pinned action is
`START NEW GROUND WORKSPACE`. Physical workspaces and resumable
not-yet-created drafts appear in that same workspace list as independently
typed rows; there is no legacy-session or second draft launcher.

Choosing New opens the blank Ground workbench immediately. `LOCATION` is a
persistent compact pane above `GOAL`. It begins `NOT SET`, may display a
provider-proposed name as `SUGGESTED · NOT CREATED`, and remains changeable with
`L`. `L` opens the shared exact Context-name and frozen parent-tree control.
Selecting a parent rewrites the unedited leaf; it does not select that existing
Context as Ground input. Location editing validates the root and all five fixed
child names but writes nothing, binds nothing, and does not switch global
Current. The workbench starts on `GOAL`. `LOCATION` is also a real focus
surface: `Shift-Tab` reaches it immediately from Goal, ordinary Tab reaches it
when the top-to-bottom sequence wraps, and Enter expands the shared tree.
`L` remains the direct shortcut from every read surface.

The provider receives an intentionally empty Context catalog. It may clarify
or propose the Goal, a candidate Save Location, and provisional Rule or Example
material, but it cannot rank existing Contexts or treat a Context name as
evidence. A person-selected Location overrides later provider naming and may be
changed again until final approval. The creation review therefore has one
locally owned command identity:

```text
mem ground <exact-save-location> --goal <reviewed-goal>
```

Leaving a workbench after it has a Goal proposal retains one typed, private
resume receipt under the active profile. The receipt preserves the proposed
Goal, provisional Rule and Example previews, submitted turns, exact planned
Location, revision, and CAS identity. It creates no ordinary Context,
checkpoint, manifest, binding, or current-Context change. Its launcher row is
explicitly `DRAFT · NOT CREATED`, and reopening it restores the proposal
without replaying provider inference. A completely untouched blank workbench
has no useful identity and is not retained.

The exact command approval atomically materializes the root and fixed children,
then removes the draft receipt. If receipt cleanup fails after successful
creation, the physical workspace is authoritative and catalog discovery hides
the stale duplicate. The draft is an interruption-recovery mechanism, not a
second Ground source of truth.

The earlier blank-TUI flow that asked a model to rank locator-only Context
names conflated two decisions: where this new physical object lives and what
external material it may later reference. It is not a production entry route.
External material enters `/contexts` later through an explicit typed
relationship or structural operation.

## External material

External structure is prepared outside Ground through existing commands. For
example, a person may:

- create a branch under `project111/contexts/...`;
- add a `memory_ref` to `project111/contexts`; or
- use an authorized Embed to add a local or granted Context link to that lane.

A Grant alone grants authority; it does not make the resource a workspace
member. The resulting typed reference or branch Context is the durable member.
Ground preserves that type and never treats visibility as mutation, combine,
export, or provider-disclosure permission.

Semantic adapters consume directly owned ordinary Memories and
local lexical descendants under `/contexts`. If a consumed lane contains a
`memory_ref`, embedded Context, query-only route, or granted link, Distill,
Elaborate, and Fit fail before provider construction. This is intentional:
durable membership is already supported, but semantic disclosure requires an
authority-aware projection that revalidates the referenced source and the
operation's DERIVE/EXPORT/retention permissions. Silently omitting such an item
would make the visible workspace and provider input disagree.

The earlier `RAW_EVIDENCE`, `WORKING_CANDIDATES`, `PUBLICATION_TARGET`, and
`PLACEMENT_TARGET` frame roles are not part of this model. An operation that
needs an output destination selects and authorizes it through its own
application contract rather than storing a universal Ground role.

## Freshness and semantic receipts

The workspace does not maintain a whole-graph, projection, checkpoint-history,
or all-member digest registry. Those stronger digests would invalidate work
that did not consume the changed material and would duplicate existing Context
CAS behavior.

The selected boundaries are:

- a write freezes the existing record digest of every Context it actually
  changes;
- one Ground-local command advances the workspace revision and records the
  complete affected Context set; and
- Fit, Distill, Elaborate, and other semantic operations freeze only the exact
  Memory and reference inputs they actually disclose or consume.

Distill and Elaborate proposals do not mutate the workspace by default. Their
explicit `--adopt` forms add the complete reviewed proposal to `/rules` or
`/examples` all-or-none, advance the manifest once, retain the semantic
analysis digest, and create one Ground-local command unit. Proposal generation
continues to stale only on consumed input; adoption also freezes the
whole-Ground revision and destination lane because it is the mutation boundary.

Cache and receipt validity therefore follows operation-local input identity,
not the mere existence of an unrelated workspace descendant or checkpoint.

## Ground-local command history

Ground edits may span Goals, Rules, Examples, relationships, and the root
manifest. Their checkpoints share one Ground command identity and the exact
root UID. The local `mem ground NAME --undo` action reconstructs a LIFO stack
containing only commands owned by that root. It does not consume or reorder the
global `mem undo` stack, and global Undo does not consume Ground-local commands.
A TUI key for the same use case remains presentation work rather than a second
Undo implementation.

Undo restores every Context touched by the selected Ground command as one
command unit. It never restores an external source merely because a relation,
reference, Embed, Grant, or branch points to that source. Drift after the
selected command fails closed rather than overwriting a later external edit.

The shared operand, projection, and adoption rationale is recorded in
[`goal-focus-operand-design-rationale.md`](goal-focus-operand-design-rationale.md).

## Presentation and component ownership

The Ground launcher reuses the operation-neutral saved-work catalog, and New
reuses the common Context parent locator plus exact-name field. The Ground
workbench's top navigator then displays the real workspace Context subtree. It
reuses common Context tree/list, cursor, scrolling, focus, row, and clipboard
mechanics. It does not call or import the Switch operation. The current
physical-workspace view is deliberately read-only; exact CLI edit actions
exercise the application boundary while the future conversational editor is
rebuilt over the same use cases.

Ground-specific terminal surfaces are grouped under
`adapters.console.commands.ground.workspace` by semantic role rather than by
the generic `interfaces.cli` and `interfaces.tui` transport labels. The
launcher projection and its stale-selection checks live in `catalog.py`; the
non-interactive `--snapshot` projection lives in `snapshot.py`; the uncreated
Save Location contract and chooser live in `location.py`; and the read-only
interactive surface keeps its state in `viewer/model.py` and prompt-toolkit
mechanics in `viewer/screen.py`. The command workflow decides which surface to
invoke, while shared TUI components remain outside Ground.

The former `interfaces.cli.ground_workspace`,
`interfaces.tui.operations.ground_workspace`, and
`commands.ground.workspace_picker` paths are removed rather than retained as
internal compatibility facades. Repository callers and tests use the
role-owning modules directly. This preserves snapshot text, picker ordering and
freshness checks, Save Location validation, viewer navigation, mutation
timing, and global-current behavior; the change is ownership-only.

- `commands.switch.setup` interprets a row as a requested global
  current-Context change.
- `commands.ground.workspace.viewer` interprets a row as a process-local
  workspace surface change.

The common component owns navigation mechanics; each operation adapter owns
catalog breadth, Enter meaning, labels, mutation, and receipts. Selecting a
Ground row must not write `state.json`.

## Compatibility and non-goals

The earlier prototype Ground session JSON has no migration contract. The
prototype was never distributed, the local development Store held no such
records, and no import requirement remains. `mem ground NAME` therefore has
one meaning: create or open the physical Context-rooted workspace. The
launcher lists only physical workspaces and unmaterialized drafts, and the CLI
no longer exposes JSON-session binding, proposal, review, replacement, or
version-guard options. New Ground code neither scans nor writes
`ground-sessions/`.

Keeping a dormant reader or same-name collision check was rejected because it
would preserve two product identities without any data to protect. Fit,
Distill, Elaborate, and Conformance now consume only the physical workspace;
the `GroundSession` model, persistence owner, locking path, and Store-wide
rename/write-protection hooks have been deleted.

This slice does not make a Ground-owned branch, Embed, Reference, Grant, Import,
or Delete operation. It does not make lexical descendants equivalent to
embedded traversal. It does not make all workspace Contexts provider-readable
or mutable merely because they appear in one navigator. Distill and Elaborate
still have no durable hidden receipt/cache; their existing prepared-lookup
ports are not a claim that the Ground adapters persist or reuse one.
