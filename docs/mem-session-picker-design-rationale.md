# Saved-work session picker design rationale

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
+ visible public-route hint
```

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
detail text, and route-hint elements pass through the terminal display-escape
boundary. The route hint helps a person recognize an operation, but it is
explicitly labelled `NOT EXECUTED`: some saved artifacts have no public CLI
operand that identifies one immutable record. The stable catalog key and the
operation adapter's reload checks are authoritative.

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
picker executes the displayed argv. When a grouped list scrolls into
the middle of one Context, it repeats that Context heading with `CONTINUED`;
the visible slice is budgeted by rendered lines rather than item count so
headings cannot hide the selected session.

## Operation adapters

### Ground

In an interactive terminal, bare `mem ground` shows saved Grounds when any
exist and retains the existing blank flow through `N`. `mem ground --sessions`
opens the launcher explicitly, while `mem ground NAME` remains direct. A
selected name is loaded again after the picker closes and must still exist;
the selection never passes through the create-or-resume fallback. Non-TTY bare
output remains the stable unsaved Ground frame. The Ground launcher also shows
the frozen process profile and store root above the list. It identifies the
profile by matching that root against every registered profile rather than by
trusting the registry's live active pointer, which another process can change
after this command has imported and frozen its store.

### Meld

Bare `mem meld`, which previously had no complete no-operand operation, and
`mem meld --sessions` show target-bound Meld sessions. The adapter reloads the
selected target slot, checks session identity and digest, and revalidates its
persisted source and target Context frames before opening it. Explicit source,
target, and action forms retain their existing behavior. `N` asks for the Meld
mode and two distinct ordinary Contexts. Directional setup enters the normal
INCOMING-to-BASELINE path; symmetric setup additionally requires an existing
ordered Compare analysis and the existing reviewed result-target picker.

### Atomize

In an interactive terminal, bare `mem atomize` and
`mem atomize --sessions` open the cross-Context session launcher. A person
chooses an existing session or the pinned New Session row instead of being
dropped directly into the current Context's result. Explicit
`mem atomize --context INPUT` remains the direct create-or-resume route, and
non-TTY bare invocation retains that stable automation-compatible behavior.
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

Bare `mem compare` and `mem compare --sessions` browse saved ordered-pair
analyses; explicit `--to` behavior is unchanged. Compare entries are labelled
as saved analyses rather than conversations. Selection reloads both Contexts
and renders the existing analysis only if its source frames and ruleset remain
current. The detail preview embeds the same complete compact report shown after
opening and omits the generic metadata envelope, so entering the workbench is
progressive disclosure rather than a replacement of the result the person just
inspected. Refresh remains an
explicit `mem compare --to ... --refresh` action.

`N` selects one ordinary peer for the frozen current reference Context, then
hands that exact pair to the normal Compare path. Cancelling peer selection
creates no analysis.

### Update

Bare `mem update` opens the singleton saved Update receipt, or an empty
launcher before the first receipt exists. `N` collects distinct ordinary
source and target Contexts and then invokes the normal explicit-endpoint
Update path; provider planning, replacement checks, application, and receipts
remain authoritative there. Opening a saved row reloads the singleton and
requires its complete serialized value to remain unchanged before opening the
same state-aware interactive Impact Workbench used by saved Update inspection.
Applied and undone receipts reopen read-only; impact and staged receipts may
offer only a handoff back through Update's normal endpoint, authority,
freshness, and exact application review boundary. The launcher never replaces
the Workbench with a long static operation dump in a TTY.

### Sever

Bare `mem sever` and interactive `mem sever --sessions` browse retained Sever
reviews through the shared launcher. `N` leaves the launcher for Sever's
Source–Criteria–Output setup. Opening a saved row reloads the exact session and
compares its complete digest before entering the provider-free Resolution
Workbench. Outside a terminal, bare Sever retains its explicit-operand guidance
and `--sessions` retains the stable plain listing for automation.

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

## Review follow-up plan

The current ambiguity Review uses one global `~/.mem/review-session.json` and
bare `mem review` already resumes that singleton. It therefore has no honest
collection for this picker to browse. After Review gains independent durable
records—at minimum a stable key, Context and review-kind binding, status, and
created/updated metadata—it should implement the same adapter contract and
join the saved-work launcher. That migration must first define replacement,
archive, and concurrency behavior; the picker must not manufacture apparent
history from the current single overwrite slot.

Find conversations remain process-local, while Impact/Update retain global
single records. The Update launcher exposes that honest singleton rather than
implying an append-only session history. Compare and translation artifacts may eventually share a
broader saved-view browser, but only Compare is in this implementation slice.

## Safety and limitations

- Catalog discovery may use file modification time only as presentation
  metadata. Stable UID/name/digest and live Context checks remain authoritative.
- Every selected record is reloaded after the picker closes. Deletion,
  replacement, corruption, stale Contexts, or a changed ruleset fails closed.
- Atomize freezes its analysis identity but intentionally resumes the latest
  valid mutable workbench/grounding state under that analysis; its frozen row
  can lag a concurrently saved subordinate turn.
- A public route hint is displayed and compared as argv elements, not executed
  by the shared picker and never interpolated through a shell. Selection uses
  the opaque catalog key, not that hint.
- The Add-new row is derived only from the adapter's validated
  `SessionNewReceipt`. It never enters the saved catalog, does not acquire a
  fake timestamp or Context group, and returns no open-session key.
- The first implementation loads complete records to build summaries. A
  rebuildable derived index may replace that scan if scale requires it; such
  an index must never become the source of session truth.
- Session deletion, archive, rename, cross-operation search, and true project
  grouping remain separate operations.
