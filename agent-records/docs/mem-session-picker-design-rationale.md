# Saved-work session picker design rationale

## Neutral launcher ownership

The visual catalog is now owned by
`memcommit.adapters.console.tui.components.operation_launcher`. Its public model
contains frozen entry identity and display metadata, an optional pinned action,
orientation rows, and a returned entry/action identity. It deliberately has no
argv, Store object, session repository, provider, cache handle, or callback.

Saved work remains one adapter of that component. The session adapter retains
`SessionPickerEntry`, exact reopen/New argv receipts, and the compatibility
`choose_session()` function, but translates them before and after the neutral
screen. Every production caller imports that interface adapter directly;
`commands.session_picker` is an import-only compatibility facade. This split
lets content-free recent reports use the same visible catalog without falsely
claiming that a recent execution is a durable session.

The alternative—generalizing `SessionPickerEntry.reopen_argv` to every report
and operation—was rejected because it would make a presentation component an
execution dispatcher and would preserve the incorrect implication that all
launcher rows reopen persisted sessions. The launcher returns identity only;
the operation adapter must revalidate it and decide what happens next.

## Motivation

Memcommit now retains several kinds of work that can be reopened: named
Grounds, target-bound Meld sessions, Context-bound Atomize analyses and
workbenches, and ordered Compare analyses. Requiring a person to remember the
exact Ground name, Meld source/target route, Atomize Context, or Compare pair
makes persistence difficult to discover and makes a mistyped Ground name
particularly risky because the historical named form is create-or-resume.

The picker is a read-only launcher. It is intentionally not an active-session
pointer analogous to the current Context. Choosing an entry opens that one
artifact; it does not change global session state, switch Contexts, refresh a
semantic analysis, call a provider, or authorize a mutation. This preserves
parallel terminal and agent safety.

## Shared presentation contract

Each operation projects its durable record into the same presentation-only
entry:

```text
kind + stable local key + title + status + summary
+ Context grouping label + modification sort value + detail
```

The entry also carries an exact internal reopen receipt. The picker returns
that receipt to the operation adapter after selection but does not render it.
It is control data, not useful saved-work description.

`Summary` is the user-facing label for the compact row description; the
internal compatibility field remains `subtitle` so existing adapters and
serialized test fixtures do not need a semantic migration.

Picker rows use the shared adaptive terminal text policy rather than fixed
30/12/38-cell Title, Status, and Summary columns. The current list Window width
is measured on every render. Status reaches its content width first, Title uses
only the width needed by the visible catalog slice, and Summary receives the
remaining space. A narrow viewport may omit the row timestamp and elide lower
priority text, while Detail retains every complete field. Widening or resizing
the terminal can therefore reveal the original text because the catalog entry
itself is never truncated.

The shared terminal component owns only arrows, scrolling, filtering, recent
or name sorting, Context grouping, detail rendering, and a local selection
receipt. Operation adapters continue to own discovery, parsing,
freshness checks, provider behavior, and reopening. All untrusted labels,
detail text, and status values pass through the terminal display-escape
boundary. The stable catalog key and the operation adapter's reload checks are
authoritative. The exact receipt remains process-local because rendering its
zero-based argv elements exposed implementation structure without adding a
useful recognition or review decision.

Frozen Profile/Store orientation discovery is owned beside that component in
`memcommit.adapters.console.tui.components.operation_launcher.location`. The former
`memcommit.adapters.console.shared.operation_launcher_location` path is a module-identity
compatibility alias, including for callers that patch its Store or profile
globals. This is an ownership-only relocation: Profile-before-Store row order,
frozen-root matching, registry-unavailable handling, and read-only behavior are
unchanged.

Trace and Rationale reuse these frozen catalog mechanics only when completed
recent report targets exist. Their pinned `SELECT A MEMORY` row is a navigation
action, not a fabricated new session. When no recent target exists, the catalog
screen is skipped and the common Context/Memory target picker opens directly.
This preserves the useful list/filter/focus mechanics without making an empty
report history look like durable saved work.

`Enter` returns the selected receipt. `PageUp`/`PageDown` scroll a long detail
preview without moving the selected entry. `S` switches between recently modified
and name order, `G` switches between a flat list and Context grouping, `/`
filters the frozen projection including detail and secondary Context names,
and Escape cancels. When an adapter supplies an explicit new-session receipt,
the picker pins an operation-specific `Add new <Operation> session` row above
the saved catalog. It is a launcher row rather than a synthetic saved session:
sorting, Context grouping, and filtering do not move or remove it. With saved
work present the newest saved row retains initial focus and Up reaches Add-new;
with an empty or no-match catalog Add-new receives focus. Enter on that row and
`N` both return the exact same new-session receipt. Ground, Compare, Meld,
Atomize, Update, and Sever adapters use it to leave the read-only launcher and
collect the operation-specific Contexts or setup fields. The list reserves one
of its visible lines for the pinned row so scrolling around a saved selection
cannot hide the explicit creation path. An empty catalog therefore remains an
actionable screen instead of short-circuiting before the picker opens. No
picker executes its internal receipt argv. When a grouped list scrolls into
the middle of one Context, it repeats that Context heading with `CONTINUED`;
the visible slice is budgeted by rendered lines rather than item count so
headings cannot hide the selected session.

## Operation adapters

### Impact

`mem impact --sessions` is a read-only aggregate launcher for every durable
artifact that an existing Impact route can inspect: Atomize analyses, Meld
assessments, Sever results, and the singleton Update/Impact plan.  Selecting a
row redispatches its frozen operation kind and exact artifact UID through that
operation's existing Impact loader.  The aggregate does not introduce a
common persistence schema, call a provider, refresh an analysis, or apply a
Memory change.  An operation-owned Impact surface may still offer its existing
explicit Apply handoff after the saved artifact has been reopened.

The aggregate is a catalog of *Impact-inspectable saved artifacts*, not an
invocation log.  Current schemas do not record whether an Atomize, Meld,
Sever, or Update artifact was first produced by an `impact` spelling or its
owning operation.  Forget, Distill, Elaborate, and Resolve are absent because
their Impact proposals are intentionally process-local; listing them would
fabricate durable history that does not exist.

`mem impact atomize --sessions` uses the same catalog filtered to Atomize.
`mem impact atomize --session UID` reopens one exact saved analysis without a
Context fallback, provider construction, or implicit refresh.  This keeps a
displayed analysis UID actionable while preventing a replaced Context-scoped
analysis from silently turning an exact reopen request into new semantic work.

### Ground

In an interactive terminal, bare `mem ground` always shows the launcher,
including for an empty catalog. Its pinned action is `CREATE NEW GROUND
CONTEXT`: it opens the common exact Save Location control and then starts a
blank Goal dialogue with that physical root fixed. It does not ask a provider
to recommend an existing Context or invent the root. `mem ground --sessions`
opens the same launcher explicitly, while `mem ground NAME` remains direct. A
selected saved name is loaded again after the picker closes and must still
exist; the selection never passes through the create-or-resume fallback.
Non-TTY bare output remains the stable unsaved Ground frame. The Ground
launcher also shows the frozen process profile and store root above the list.
It identifies the profile by matching that root against every registered
profile rather than by trusting the registry's live active pointer, which
another process can change after this command has imported and frozen its
store.

### Meld

Bare `mem meld` opens the role-based new-Meld setup directly. It does not
browse target-bound Meld sessions or let a retained target slot choose the new
request. `mem meld --sessions` is the explicit saved-work launcher. Its adapter
reloads the selected target slot, checks session identity and digest, and
revalidates its persisted source and target Context frames before opening it.
Explicit source, target, and action forms retain their existing behavior. The
launcher's `N` action delegates to the same role-based setup as bare entry.

### Atomize

In an interactive terminal, `mem atomize --sessions` opens the cross-Context
session launcher. Bare `mem atomize` remains the direct create-or-resume route
for the current Context, matching its non-TTY automation-compatible behavior.
Explicit `mem atomize --context INPUT` names that direct route's input.
Saved selection may render or resume only a still-current
analysis/workbench/grounding artifact; it must not silently regenerate stale
work or switch the current Context.
`N` opens the common role-based setup as `INPUT A → OUTPUT B`. Input is an
ordinary local Context. Output is either that same Context for in-place
application or a validated new exact name that preserves Input. The typed
receipt then hands both names to the normal create-or-resume path; it does not
create Output or apply the proposal.

Like Ground, Atomize supplies the shared launcher with the frozen process
profile and store root. The profile label is derived by matching the already
frozen store root against the registry, not by rereading a mutable active
profile pointer. New and reopened Atomize sessions therefore remain visibly
scoped to the storage namespace that actually owns them. The Atomize adapter
also enumerates analyses from that exact store boundary, so a session in any
other profile is not a catalog entry and cannot be selected by UID through the
launcher.

### Compare

Bare `mem compare` opens the role-based A/B endpoint setup for a new analysis.
`mem compare --sessions` alone browses saved ordered-pair analyses; explicit
`--to` behavior is unchanged. Compare entries are labelled as saved analyses
rather than conversations. Selection reloads both Contexts and renders the
existing analysis only if its source frames and ruleset remain current. The
detail preview embeds the same complete compact report shown after opening and
omits the generic metadata envelope, so entering the workbench is progressive
disclosure rather than a replacement of the result the person just inspected.
Refresh remains an explicit `mem compare --to ... --refresh` action. The
launcher's `N` action delegates to the same two-endpoint setup as bare entry;
cancelling setup creates no analysis.

### Update

Bare `mem update` opens the role-based Source/Target setup for one new Update.
`mem update --sessions` opens the singleton saved Update receipt, or an empty
launcher before the first receipt exists. Its `N` action delegates to the same
setup as bare entry. The typed receipt then invokes the normal explicit-endpoint
Update path; provider planning, replacement checks, application, and receipts
remain authoritative there. Opening a saved row reloads the singleton and
requires its complete serialized value to remain unchanged before opening the
same state-aware interactive Impact Workbench used by saved Update inspection.
Applied and undone receipts reopen read-only; impact and staged receipts may
offer only a handoff back through Update's normal endpoint, authority,
freshness, and exact application review boundary. The launcher never replaces
the Workbench with a long static operation dump in a TTY.

### Sever

Bare `mem sever` enters Sever's Source–Criteria–Output setup directly.
Interactive `mem sever --sessions` browses retained Sever reviews through the
shared launcher, whose `N` action delegates to that same setup. Opening a saved
row reloads the exact session and compares its complete digest before entering
the provider-free Resolution Workbench. Outside a terminal, bare Sever retains
its explicit-operand guidance and `--sessions` retains the stable plain listing
for automation.

## Time and grouping semantics

Ground and Meld records do not yet serialize creation or update timestamps.
Their first picker projection therefore uses the JSON file modification time
and labels it *modified* or *last saved*, never *created* or *last opened*.
Merely viewing a session does not touch the file. Copying or restoring a store
can change this physical time, so a later schema migration may add durable
`created_at` and `updated_at` fields. Atomize and Compare use their existing
analysis timestamps where they accurately describe the saved artifact.

There is also no project identity in the current schemas. `G` is therefore
`BY CONTEXT`, not `BY PROJECT`. A Ground appears exactly once: it uses its first
`RAW_EVIDENCE` frame, falls back to its first `WORKING_CANDIDATES` frame, and
otherwise belongs to `Unbound`. Its detail still lists every bound Context and
the filter can match those secondary names. Meld uses its target; Atomize uses
its source Context; Compare uses its reference Context. Inferring a project
from the first slash-delimited name segment was rejected because participant,
temporary, and task namespaces do not consistently encode project identity. A
future explicit project/tag catalog can add that view without changing session
identity.

The shared picker remains configurable rather than imposing one initial view
on every operation. Ground opens `BY CONTEXT` because a Ground's bound Context
is the clearest orientation for otherwise opaque session names, with the most
recently saved Ground first inside each Context. Meld, Atomize, and Compare
retain the neutral recent-first flat view. `G` and `S` still let the person
switch grouping and ordering without persisting presentation state.

## Review aggregate launcher

In a TTY, bare `mem review` is a read-only union of the saved artifacts that
the Review host can already render: Atomize, Compare, Meld, Sever, Update, and
the older global `ReviewSession`. The union does not introduce a common Review
schema or lifecycle. Each row retains its operation-owned state, stable key,
Context grouping, summary, activity timestamp, and exact reopen validation;
Enter dispatches to that operation's existing Review controller.

The launcher contains every retained state that remains honestly viewable,
including in-progress, awaiting-response, ready, applied, completed, and stale
artifacts. It is not a completed-work ledger. Recent activity is the default
ordering because most non-applying Review artifacts have no checkpoint.
Applied artifacts may report their operation-owned checkpoint receipt, but a
checkpoint is not fabricated for analysis or review-only work.

The ambiguity Review still uses one global `~/.mem/review-session.json`. It is
therefore projected as exactly one singleton row, not as invented historical
records. Update's global staged/Impact receipt follows the same rule. A future
multi-record migration may add real history only after defining replacement,
archive, timestamp, and concurrency behavior.

The aggregate detail view deliberately omits the shared picker's defensive
argv-index rendering such as `[0] mem` and `[1] review`. Those indexes identify
argument-vector positions and are useful to host validation, but they are not
part of a person's Review decision. The frozen argv remains on the local
selection receipt and is compared after selection without being rendered or
executed.

The launcher has no generic New row because starting Atomize, Compare, Meld,
Sever, Update, or Ambiguities requires different operation-owned setup and may
call different semantic producers. Explicit operation commands retain those
creation paths. Non-TTY bare Review, `--snapshot`, response staging, and an
explicit Context retain the prior direct compatibility behavior.

## Safety and limitations

- Catalog discovery may use file modification time only as presentation
  metadata. Stable UID/name/digest and live Context checks remain authoritative.
- Every selected record is reloaded after the picker closes. Deletion,
  replacement, corruption, stale Contexts, or a changed ruleset fails closed.
- Atomize freezes its analysis identity but intentionally resumes the latest
  valid mutable workbench/grounding state under that analysis; its frozen row
  can lag a concurrently saved subordinate turn.
- The internal reopen receipt is compared as argv elements but is neither
  rendered nor executed by the shared picker and is never interpolated through
  a shell. Selection uses the opaque catalog key, not the receipt as identity.
- The Add-new row is derived only from the adapter's validated
  `SessionNewReceipt`. It never enters the saved catalog, does not acquire a
  fake timestamp or Context group, and returns no open-session key.
- The first implementation loads complete records to build summaries. A
  rebuildable derived index may replace that scan if scale requires it; such
  an index must never become the source of session truth.
- Session deletion, archive, rename, cross-operation search, and true project
  grouping remain separate operations.
