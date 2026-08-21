# Directional `mem impact` and `mem update`

`mem impact` now also exposes the unary preview
`mem impact atomize`. That form classifies and proposes splits inside one
Context; it does not target another Context, create an `UpdateSession`, or
write `impact-plan.json`. It saves a separate analysis under the source Context
UID for `mem atomize`, `mem trace`, and `mem rationale`; Context contents and
checkpoints remain unchanged. Its separate evidence and trust boundary is
documented in
[`mem-atomize-design-rationale.md`](mem-atomize-design-rationale.md).
This document specifies only the directional A-to-B form.

## Intent

These commands express a directional semantic operation with independently
selectable endpoints:

```text
update target Context B from source Context A
```

Context A is verified evidence. Context B is a writable local working target.
This is not a symmetric merge and it is not a command for manually replacing
one Memory by UID.

## Task 1 authority boundary: ordinary wiki and concealed details

Task 1 keeps task-owned change evidence separate from authority-owned campus
data. The task sees permissioned views rather than a local wiki copy.
The canonical identifiers follow
[`task-1-naming-contract.md`](task-1-naming-contract.md):

| Role | Task 1 example | Authority |
| --- | --- | --- |
| campus wiki | `campus-wiki` | authority-owned graph granted `READ+CREATE+UPDATE+DELETE+QUERY` |
| construction details | `campus-wiki/construction-details` | narrower `QUERY` view; never a mutation target |
| verified change source | `participant/construction-updates` | task-owned readable evidence |

`task-1-campus-authority` provisions the complete wiki and details before the
participant begins. A broader read/edit grant and narrower query grant expose
the intended subsets without copying them into the task store.

Fixture review must separately verify that the ordinary wiki covers the
complete authorized candidate scope. Otherwise a missing affected page is
indistinguishable from a correct no-change judgment, and Task 1 could not claim
that all affected parts were updated.

This separation makes the mutation boundary explicit:

```text
query campus-wiki/construction-details when detail context is needed
→ preview verified changes against campus-wiki
→ apply them to campus-wiki
→ inspect the local diff
```

`mem impact` now accepts that granted ordinary wiki view as a read-only target
for planning. It freezes the exact grantee, authority, attachment, resource,
grant identity, grant revision, grant digest, and permission set into a
schema-v6 plan. The target projection excludes any descendant covered by the
narrower `QUERY`-only grant, so concealed construction details cannot enter the
ordinary impact corpus. Provider authentication happens before authority-owned
content is opened. After the provider turn, the command reloads the source,
grant, and projected target under the grant registry lock and saves nothing if
any identity or digest changed.

The preview reports the permissions implied by its actual operations:
`READ`, plus `CREATE` for additions, `UPDATE` for edits, and `DELETE` for
removals. `READY` means only that the frozen grant contains those permissions;
it does not mean that the plan has been applied. `mem impact` remains
non-mutating. `mem update` can promote that exact schema-v6 plan and apply it
to the run-private authority store. It holds the grant registry snapshot,
rechecks the active grantee and complete frozen binding, resolves every owner
through the same grant, and requires `UPDATE`, `CREATE`, or `DELETE` for the
corresponding operation before the first write. The fixed `study-baseline`
Profile is rejected explicitly. A `-fork` suffix would still imply a
divergent-copy model that this design deliberately avoids.

## Usage

```bash
mem switch participant/construction-updates
mem ls campus-wiki
mem impact --to campus-wiki
```

Either endpoint may instead be explicit. An omitted endpoint is filled by the
single current-Context snapshot captured when the command starts:

```bash
# Explicit target: current A → B (backward-compatible form)
mem impact --to B

# Explicit source: A → current B
mem impact --from A

# Both explicit: A → B, independent of current Context
mem impact --from A --to B
```

### Reusable Impact and the TTY Apply boundary

The exact saved operations now project through a provider-free
`ImpactController`. The controller is reusable by the standalone Impact
workbench and by an owning operation TUI; it does not resolve endpoints, call a
provider, save a session, or apply changes. Its view must match the active
Update UID and operation digest revision, preventing a stale preview from
appearing above a newer Apply action.

In a TTY, `mem update` saves or reuses the staged receipt first, displays that
revision-bound Impact when review is required. A decision-free local Target
applies through the existing exact staged plan without opening that surface and
records its ordinary checkpoint for `mem undo`. A granted Source does not alter
that local mutation boundary. A granted Target instead opens exact final review
before the authority write; closing leaves the receipt staged and every target
owner unchanged. A validated zero-operation proposal records its applied
session receipt without changing a Context or creating an Undo checkpoint, so
its mutation boundary is `NONE` even when the selected Target is granted.
Non-TTY explicit update retains the
existing scriptable application behavior; adding an interactive approval to a
pipeline would make the command unusable rather than safer.

The embedded Impact is a located Memory diff. Each change names its exact
target owner and Memory UID, then uses the same frozen `- before` / `+ after`
contract as semantic `mem diff`. The Viewer summarizes the planned-change set
once instead of repeating every Item before the Impact ledger; Items remains
available for full reason and source-reference inspection.
The diff calculation is mechanical rather than provider-authored: identical
strings render `=`, partial edits retain equal spans and emphasize only changed
word spans, and additions or removals remain one-sided. Update's validation
rejects an exact no-op EDIT, so equality is available to shared consumers such
as Sever without creating a meaningless Update mutation.

The same saved `UpdateSession` also supplies `mem review update`. Review keeps
the existing detailed ADD/EDIT/REMOVE presentation, including OWNER, Memory
UID, BEFORE/AFTER, REASON, and SOURCE REFERENCES. It is a read-only explanation
of the plan and exposes no Accept or Apply capability. Impact remains the
separate exact-effect surface adjacent to application; its `APPLY?` route is a
handoff to the owning operation rather than an application capability on the
Impact projection itself.

The default TTY grammar is `mem diff [CONTEXT]`. Bare `mem diff` first opens
the same complete Context tree used by other Context-selecting flows; a Context
operand resolves directly to that location and skips only this first selector.
The second screen is the shared checkpoint browser owned by interactive
history inspection flows.
Tree annotations count command units rather than physical checkpoint files:
`N direct · M inherited · K descendant commands`. Copied Branch lineage stays
visible under its Source but is not attributed to the branch as a direct
command. A multi-Context Update shares its
session/digest identity across every owner and therefore counts once in every
covering subtree; one Undo or Redo likewise shares its restoration receipt and
counts once. `init` is the baseline for later transitions and is not presented
as a Diff operation. Direct and descendant counts remain separate so a parent
does not falsely appear to own its children's independently restorable history.
Diff and Revert use this same location controller rather than maintaining separate
catalog, count, or scrolling implementations. Their Context rows and inline
operation rows therefore form the same navigation-unit sequence: `m` toggles
the focused Context's operations, `M` toggles all visible operation rows, and
Up/Down traverses both without turning a preview into a Context selection.
Operation previews use neutral report styling, not the lavender reserved for
actual Memory objects. Every compact identifier is role-labelled; focusing a
command exposes its exact typed identifiers in a passive detail region. Revert
retains checkpoint restoration review while Diff adds the directional
before/after renderer. Static `mem log` does not enter this controller and
retains its existing terminal-independent compatibility output.
Local Contexts expose their recorded checkpoint history even when no saved
Update exists. A currently saved Update additionally contributes its frozen
target catalog and granted affected locations, so its authority-owned
checkpoint receipts remain inspectable without opening the authority store.
The selected checkpoint names its actual command (`ACTION update`, `add`,
`edit`, and so on); one Update checkpoint may contain several EDIT, ADD, or
REMOVE transitions. A catalog parent with changed Update owners below it offers
`Enter open changed descendants`; because that catalog-only row has no exact
history of its own, the unmodified key introduces no competing action. Arrow
keys continue to own tree expansion. That explicit selection opens one
read-only history whose rows remain location-owned and whose detail continues
to name each exact Context and checkpoint. It includes only affected owners
already frozen in the saved Update, not every readable or local descendant, so
subtree convenience cannot widen authority or invent an aggregate checkpoint.
A Context with no checkpoints remains in an explicit empty history TUI rather
than returning immediately. In location-first Diff, Escape and Backspace
return one level to the Context selector and preserve its selected location;
`q` or `Ctrl-C` closes the command. An explicit Context operand has no selector
to return to, so its close keys exit normally. Outside a TTY, operand-free Diff
retains the deterministic saved-Update snapshot used by automation. The
checkpoint detail preserves directional diff semantics:
unchanged text and markers are white, text that disappears is red and
underlined, and text that appears is green and underlined. The mechanical span
classification—not whether text is on an upper, lower, or wrapped continuation
line—determines the directional color.
ADD and REMOVE show only their applicable side. `--raw` remains the exact
unified-diff escape hatch, `--stat` the compact count-only form, and `--verbose`
the diagnostic identity view. Opening the selector is inspection only: staged,
applied, and undone receipts remain in their recorded lifecycle state, and no
Apply or Undo capability is introduced by Diff.

The History detail and semantic Impact viewer use the same shared report and
directional Memory-diff style roles. History does not own a second copy of the
red, green, neutral, or label palette; changing the common roles therefore
changes both projections together. Their navigation and data models remain
separate because sharing presentation must not give History any Impact action.
History follows the common read-only workbench topology with `VIEWER` above
`ITEMS` while retaining Items as the initial hub. Enter from Items focuses the
selected checkpoint detail in Viewer; Tab switches the two frames; Up/Down
moves items or scrolls Viewer according to focus. Escape or Backspace from
Viewer returns to Items first, and only the next back action leaves History for
the owning Context selector. The shared focused-frame chrome communicates this
layering without changing the checkpoint or operation projection.

Selecting the singleton receipt from the interactive bare `mem update`
launcher uses this same state-aware workbench instead of printing the complete
operation list as terminal prose. Applied and undone receipts have no handoff;
an impact or staged receipt may hand control to the normal Update command, but
the read-only workbench itself still cannot apply anything.

The reusable controller also supports provider-free reopening through the
standalone command surface:

```text
mem impact update [--session UID]
mem impact meld [--session UID]
mem impact sever [--session UID]
```

These forms inspect an already-saved operation artifact; opening the Impact
ledger never creates a new plan, requests a semantic response, or changes a
Context. In a TTY, Meld and Sever select from their frozen session catalogs and
reload the selected artifact before projection. Outside a TTY, a sole saved
artifact opens directly, while multiple artifacts require `--session UID`.
Update retains its existing singleton receipt but accepts `--session` as an
exact-identity check.
All three use the same operation/artifact/revision match enforced by
`ImpactController`. An applicable saved artifact also shows `APPLY?` in To Do.
Selecting it leaves the immutable Impact host and re-enters the owning Update,
Meld, or Sever workflow, which reloads or resolves live state, repeats its
normal grant, binding, freshness, and CAS checks, and still requires its real
Apply action. Thus `APPLY?` is a transition for deciding after inspection, not
authorization and not a second application implementation. If the person
backs out of the owning workflow's final Apply without mutating anything, the
caller reloads the same saved artifact and returns to its Impact/`APPLY?`
surface. This stack behavior is shared by Update, Meld, and Sever; a successful
or otherwise terminal application ends the loop. Closing Impact leaves the
session and every Context unchanged. Terminal artifacts omit the handoff.

### Named Impact route registry and process-local artifacts

The public named routes are now composed through one typed registry rather
than a command-local enum or whitelist. The registry records only discovery,
Help text, and the way each route obtains its artifact:

| Lifecycle | Routes | Meaning |
|---|---|---|
| `PREPARE_DURABLE` | `atomize` | Prepare or reopen the operation-owned durable analysis, then project it read-only. |
| `PREPARE_PROCESS_LOCAL` | `forget`, `distill`, `resolve` | Run the owning application analysis and project its process-local result without inventing persistence. |
| `OPEN_SAVED` | `meld`, `sever`, `update` | Reload an existing operation-owned artifact before projection. |

This registry is deliberately not a universal semantic-operation interface.
It does not own provider construction, authority, cache identity, review state,
CAS, checkpointing, or Apply. Every handler calls the operation's application
or runtime boundary and then adapts the returned artifact to the immutable
`ImpactController`. Registry installation requires an exact handler set, so a
Help entry cannot silently exist without a callable route and a callable route
cannot silently bypass the authored list.

`mem impact forget` shows one complete batch of in-place KEEP, TRANSFORM, and
DROP transitions over the frozen direct Source. `mem impact distill` shows the
Memories a fresh Result would contain and labels the proposed Result
`NOT CREATED`. `mem impact resolve` shows the exact before/after effects when
there is one selected verified candidate. If Resolve returns multiple mutually
exclusive candidates, the first Impact view shows the candidate set instead of
flattening the alternatives into one false combined effect plan; an exact
`--candidate` selects the diff projection.

These three process-local routes expose no `APPLY?` handoff. Their artifacts
are not durable sessions, so leaving the Impact host must not imply that a later
owning command can reuse the same provider result or revision. The person may
run the owning command separately, which repeats its normal analysis and Apply
checks. A future in-process handoff would require an operation-owned controller
that retains the exact artifact and revalidates it; the registry alone is not
that controller.

The policy records two deliberate exclusions: `translate` changes a
representation rather than previewing a Memory state transition, and `ground`
retains its exact-command approval protocol. `dedun` is recorded as
deferred while its command split and reviewed candidate adapter stabilize. It
is semantically eligible, but Impact must not infer a proposal contract from an
in-progress command refactor.

`mem update` accepts the same three forms. `--from` and `--to` are therefore
composable endpoint selectors, not mutually exclusive modes. At least one must
be supplied. If an omitted endpoint has no current Context, the command fails
and asks for that endpoint explicitly. Source and target must resolve to
different canonical ordinary Context names.

### Optional descendant scopes

The interactive Update setup puts an independent, default-off checkbox below
each Source and Target tree: `INCLUDE ALL DESCENDANT CONTEXTS (OWNED OR
GRANTED)`. Unchecked retains the selected Context graph used before this
control was added. Checked also freezes every lexical descendant exposed by
that endpoint's same owned store or effective READ Grant view. Thus an empty
namespace root such as `task-1/participant` can deliberately supply Memories
from `task-1/participant/...` without making recursive input an invisible
default.

The equivalent canonical pairs are
`--source-descendants/--source-root-only` and
`--target-descendants/--target-root-only`. The older `--source-only` and
`--target-only` spellings remain accepted compatibility aliases for the
root-only values. Source and Target scopes are independent. Query-only
overrides remain excluded, and a local endpoint does not absorb a separately
attached Grant merely because the attachment happens to sit below it: the
selected endpoint's ownership or Grant identity remains the authorization
boundary.

The graph-widening rule itself lives in the shared `load_context_scope`
utility used by Update, Compare, and eligible Meld roles. Presentation remains
in the shared endpoint shell, while each operation declares which roles may
offer the control and persists the resulting booleans in its own artifact.
This shares the mechanical lexical-descendant and UID-deduplication contract
without pretending that the operations share mutation authority.

Schema v6 records both booleans with the endpoint fingerprints. Cache reuse,
staged-session matching, Grant revalidation, and application reload the same
scope. A descendant added, removed, or changed after planning therefore makes
the receipt stale before a write; an unchecked plan cannot be silently reused
as a checked one even when the two graphs happen to be momentarily identical.

Planning and saved-session inspection forms are mutually exclusive:

```text
mem impact [--from A] [--to B] directional update preview
mem impact atomize      unary atomization preview
mem impact forget       process-local in-place Forget preview
mem impact distill      process-local fresh-Result preview
mem impact resolve      process-local verified repair preview
mem impact update       saved Update effect inspection
mem impact meld         saved Meld effect inspection
mem impact sever        saved Sever effect inspection
```

Supplying a named operation together with directional `--from` or `--to`, or
supplying no directional endpoint and no operation, is a usage error. Typer
subcommands give each named route an operation-specific option grammar:
`--all`, `--with-review`, and `--refresh` belong only to Atomize; `--session`
belongs only to saved Update, Meld, or Sever inspection; and Forget, Distill,
and Resolve expose only the operands accepted by their prepare adapters.

`impact` plans and previews the edits, additions, and explicitly supported
whole-Memory removals that would make B reflect A. It does not change either
Context. The validated plan is cached locally so an immediately following
`update` can reuse exactly what the participant reviewed.

In a terminal, directional `impact` presents the saved plan through the shared
Resolution Workbench: arrows select a planned change and Enter expands its
exact owner, before/after content, reason, and source-reference digests.
Outside a terminal it prints the deterministic projection. These rows are
labelled `PLANNED CHANGES` and do not claim that the current operations-only
provider assessed an exhaustive unresolved-issue list. Standalone `impact`
remains read-only and exposes no comment or acceptance capability. The owning
staged `update` workflow uses the same projection but allows a whole-proposal
comment or a comment on one exact expanded change before its separate Apply.

A staged change comment is guidance, not a direct local edit of an operation.
The workbench binds it to the operation-backed item UID, including when it was
opened from the located Impact row, and changes the next action from Apply to
`INCORPORATE RESPONSES`. The provider then receives the complete frozen Source,
Target, current proposal expressed only through public candidate aliases, and
the reviewed comments. It must return one complete replacement operation set
through the existing strict Update schema. The revised staged receipt replaces
only the exact receipt reviewed through record CAS and returns to review; it is
not applied implicitly. An empty comment batch leaves the original Apply path
unchanged.

Update's initial provider plan uses the shared transient one-line progress
contract; there is no report or review to occupy a full-screen surface yet.
During a comment-driven replacement, the previously reviewed staged report
remains visible in the shared interactive wait and the submitted comment is
marked not yet incorporated. `C` can inspect the frozen read-only Context
catalog, `I` shows the submitted Source→Target route and comment, and `H` or
`?` opens Help without restarting that replacement turn. Provider completion
alone still publishes nothing: the existing record CAS must replace the
reviewed staged receipt before the revised report can return to review.

The `--from` and `--to` operands locate existing Contexts through the shared
Context locator contract. Bare names remain canonical global names; `.`,
`..`, `./...`, and `../...` resolve lexically against the same one
current-Context snapshot captured at command start. The resolved canonical
pair—not the input spelling—drives Context loading, equality checks, provider
planning, impact-cache reuse, staged-session identity, application receipts,
and output.

The **current implementation** of `update` promotes a matching impact plan to
a staged intent and then materializes its validated edits, additions, and
constrained removals in B. It changes only directly owned `Memory` values in
either an ordinary local target or the exact run-private authority Contexts
covered by a frozen editable grant. `MemoryRef`, `QueryContextRef`,
embedded-Context pointers, the verified source, concealed query-only
descendants, and `study-baseline` remain unchanged. Repository terminology
reserves `delete` for a whole Context, so removing one target Memory is
represented as `RemoveOperation`.

A removal is permitted only when readable, verified source evidence explicitly
states that the entire standalone target Memory is obsolete and should no
longer be represented. Absence from the source never authorizes removal. If a
target Memory mixes obsolete and still-valid facts, the planner must emit an
edit that preserves the valid facts instead. Every removal carries source
references, a reason, and the target's locally captured `old_content`; the
provider selects a supplied target ID but cannot author that old-content
snapshot. The same target cannot be both edited and removed.

This deliberately narrow removal contract supports a developer smoke case
without turning update into general-purpose semantic deletion. The full Task 1
Study Gold contains no removal: its 75 source Memories produce 77 patches,
specifically 34 modifications and 43 additions. A real ambiguity such
as “remove this listing or retain it as a cancellation notice” must block the
plan and enter the future issue-scoped directional Meld path described below.

Before the first write, application reloads the complete recorded A/B graph,
checks its identities and fingerprints, validates every operation and old
content value, and prepares detached post-images for all affected direct owner
Contexts. Granted application additionally holds the registry snapshot, the
participant source locks, the participant update-record lock, and the
authority command and Context locks through receipt publication. It saves one
post-image per affected authority owner and creates one authority-side
automatic checkpoint per owner. Every checkpoint carries the same update
session UID, ordered-operation digest, public owner, and grant identity. Only
after all owners have been saved does the participant's active record become
`applied` and receive projected result fingerprints and checkpoint receipts.

`mem diff` renders the captured baseline-to-result operations deterministically
after application. It does not recompute a model result or compare arbitrary
Contexts. Publication still requires a later `push` or PR.

If the cached impact plan is stale because A or B changed, `update` plans again
instead of promoting stale operations. Running `update` repeatedly with the
same A and applied B is idempotent: it recognizes the result receipt and
neither reconnects to the provider nor creates another checkpoint. A
different, stale, or diverged active update record is preserved unless the
participant explicitly supplies `--replace-stage`.

An ordinary exception during a multi-owner write restores every owner already
written and removes the checkpoints created by that attempt, leaving the
staged record available for inspection or retry. Per-file writes are atomic,
but there is not yet a durable transaction journal. A process or machine crash
between owner writes can therefore leave a partial local application. This is
an explicit prototype limitation to resolve before remote publication.

## Task 1 resolution boundary and incomplete general path

Task 1 stipulates that Context A contains already verified local memory. Its
directional impact is expected to be reasonable and conflict-free, so the
participant path does not open a clarification or reconciliation dialogue:

```text
verified local A
→ impact preview against granted run-private authority B
→ optional provenance review
→ update applies B through the frozen editable grant
→ future grant-aware diff and recovery inspection
```

This is an intentional **Task 1 scenario boundary**, not a general invariant
of semantic updates. Introducing an artificial ambiguity or conflict into this
study path could change participant trust independently of the intended
questions about provenance, responsibility, and review behavior.

### Audience intent in a future update preview

Task 1 fixture design requires every proposed wiki operation to display both
its semantic subject and its intended disclosure audiences. The initial
review matrix is:

```text
EVERYONE | VISITOR | STUDENT | STAFF | CONSTRUCTION_OR_BUILDING_PERSONNEL
```

The update workbench should show the target page, `EDIT`/`ADD`/`NOOP`/
`BLOCKED` outcome, old and proposed content, and the complete audience matrix
on the same review row. Public closure information and restricted access
mechanics must be separate rows: everyone may read that an entrance is
closed, while only an authorized operator should receive the exception or
credential detail. A change to content and a change to intended disclosure
are independently reviewable effects.

This is a display and future-policy requirement, not current behavior.
`Memory` has only `uid` and `content`; `EditOperation`, `AddOperation`, and
`RemoveOperation` have no audience policy; and ordinary `ls`, `show`,
provider planning, and apply paths do not establish a principal or filter by
role. Manually adding unrecognized JSON fields is not a safe prototype
because canonical serialization will discard them. Query-only hides one
complete source from ordinary traversal but neither authenticates campus
roles nor filters individual Memories.

The safe current fixture representation is therefore a designer-only
sidecar, exemplified by
[`examples/task-1-wiki-update-access-preview-ko.md`](examples/task-1-wiki-update-access-preview-ko.md).
An enforced version requires a versioned policy schema, an authenticated
principal at a trusted service boundary, fail-closed filtering across every
read and provider path, policy-preserving update operations, and
non-interference tests. Until those exist, the UI must label the matrix
`INTENDED DISCLOSURE · NOT ENFORCED` and must not imply that a content prefix
or audience-specific ordinary Context provides confidentiality.

The absence of a general semantic Update-resolution adapter is nevertheless an
**incomplete prototype boundary and explicit TODO**. The current
`UpdateSession` has no named-Ground binding, Goal–Rules–Memories ledger,
unresolved-issue state, or directional-Meld turns. It cannot suspend staging
for a human grounding round, promote an accepted clarification explicitly, or
recompute a complete proposal from that turn.

A future adapter should stop on a required ambiguity, conflict, placement
question, or missing scope; bind the update to an exact Ground revision; use an
issue-scoped directional Meld to incorporate the person's resolution; and
recompute the complete bounded plan before staging. That future contract is
recorded in
[`cross-operation-grounding-design-rationale.md`](cross-operation-grounding-design-rationale.md).
It is documented design work, not behavior advertised by the current command.

The same missing state currently prevents Update from adopting the exhaustive
common semantic-result workbench defined in
[`semantic-result-workbench-design-rationale.md`](semantic-result-workbench-design-rationale.md).
An edits/additions/removals plan can explain exact proposed changes, but it cannot
say whether an omitted source was already present, irrelevant, overlooked, or
unresolved. Update must first record exhaustive source disposition,
source-linked understanding and outcome sections, unresolved findings, and
traceable inspection cases. Until then, displaying “no unresolved finding”
would fabricate evidence rather than reuse a presentation asset honestly.
The separate Resolution Workbench may still display exact planned operations
read-only because it makes no unresolved-completeness claim. That boundary is
defined in
[`semantic-resolution-workbench-design-rationale.md`](semantic-resolution-workbench-design-rationale.md).

## Method

Both commands use one planner:

1. Recursively visit explicitly embedded Contexts in A and the writable local
   fork B.
2. Treat directly owned `Memory` values in B as writable only because B is the
   participant-owned fork; never use the query-only organizational origin as
   B.
3. Treat resolved `MemoryRef` values in A as readable evidence.
4. Never open `QueryContextRef` sources and never edit `MemoryRef` values.
5. Give a temporary Codex process only per-run candidate IDs and visible text.
6. Require strict JSON containing full-content edits, additions, and
   source-backed whole-Memory removals.
7. Map every returned ID back to canonical local objects and reject unknown,
   duplicate, empty, conflicting, or unsupported operations.
8. Generate new Memory UUIDs locally and record source provenance plus source
   and target fingerprints.

An edit preserves the target Memory UID and replaces its string content with a
complete revised version. The planner must preserve unrelated target facts. An
addition receives a new local UUID and names its owning target Context. A
removal preserves the selected target's old-content snapshot and provenance in
the update session while removing only that directly owned Memory from the
authorized target.

## Compact executable Task 1 fixture

[`../memcommit/eval/fixtures/update.json`](../memcommit/eval/fixtures/update.json)
contains a small regression/example set rather than the complete
participant-facing study corpus. It provisions five verified source Memories
and five target-baseline Memories. The expected result is:

```text
2 edits + 1 addition + 1 removal
2 target Memories unchanged
5 final target Memories
```

This five-by-five case is only a smoke fixture for operation mechanics and
rollback. It is not a quality target for the Study planner. The full harness
must record a disposition for all 75/75 source Memories and compare the
resulting operation set with the authoritative 77-patch sidecar (34
modifications and 43 additions), while retaining provider, resolved model,
reasoning effort, and runtime identity for reproducibility.

The source includes one already-present fact to test no-op recognition, while
an unrelated health-hours Memory tests impact scoping. Its removal source
explicitly instructs removal of a standalone expired detour notice; this keeps
the case conflict-free and therefore outside the future Meld resolution
branch. The fixture also retains all six canonical construction-update child
Context slots, with one empty slot, so Context structure is not confused with
Memory count.

## Diff

```bash
mem diff
mem diff --raw
mem diff --stat
mem diff --verbose
```

`diff` makes no model or network call. Its default semantic view uses yellow
operation headings, red deleted text, green added text, dim unchanged lines,
and cyan provenance. It shows collision-safe short UID prefixes and hides
low-level Git headers and terminal-newline markers. `--verbose` shows complete
UIDs and the source/target fingerprints.

`--raw` renders the exact Git-style `---`, `+++`, and `@@` representation,
including additions from `/dev/null`, removals to `/dev/null`, and
terminal-newline markers. `--stat` shows only the edit/addition/removal counts.
Raw and stat modes are mutually exclusive.

Every detailed mode prints each operation's source provenance and reason. The
command does not depend on the currently selected Context and it does not write
Contexts, checkpoints, state, or session files.

Before rendering, the command reloads the recorded A and B Context graphs. For
a staged record it verifies the captured base; for an applied record it
verifies the captured source and the receipt's result fingerprints. If those
identities or planner-visible contents changed, the captured diff is still
shown but marked stale and the command exits with a failure status. A future
push must refuse a stale applied result.

## Local artifacts

```text
~/.mem/impact-plan.json
~/.mem/staged-update.json
```

These files contain canonical operation records, owner Context identities,
applicable old and new content, provenance hashes, and source/target base
fingerprints. The
impact file remains read-only planning evidence. During `update`, the active
file first records the staged intent and, after successful local application,
records status `applied`, the operation digest, applied target fingerprints,
the application time, and one checkpoint receipt per affected owner. An empty
plan has no affected owners or checkpoints but still records an applied result.
Each individual JSON file replacement is atomic.

The automatic checkpoint recorded by the current application transaction is a
post-update checkpoint. It supports audit and repeatability but is not, by
itself, a pre-update restore point for a completed removal. Task 1 provisioning
must retain its local-fork baseline, and a general publication-ready removal
workflow still needs an explicit pre-update recovery contract. Ordinary
in-process application failure already restores the saved owner records,
including a removed Memory and its order.

`mem impact atomize` deliberately neither reads nor overwrites these files.
Its one-shot result is provisional but is cached separately at
`~/.mem/atomize-analyses/<context-uid>.json`. Only `mem atomize` consumes that
artifact for explicit in-place or save-as application; it is not interchangeable
with a directional update plan.

This is a research-prototype trust boundary, not remote collaboration or an
access-control system. A later push implementation must separately verify the
fork's upstream binding, remote base, and publication authority before
contributing anything to `campus-wiki`.
