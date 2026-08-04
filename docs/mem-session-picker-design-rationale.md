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
and Escape cancels. `N` exists only when an
adapter supplies an explicit new-session receipt; initially Ground alone does
so. No picker executes the displayed argv. When a grouped list scrolls into
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
target, and action forms retain their existing behavior.

### Atomize

Bare `mem atomize` retains its current-Context create-or-resume behavior.
`mem atomize --sessions` is the cross-Context browser. Selection may render or
resume only a still-current saved analysis/workbench/grounding artifact; it
must not silently regenerate stale work or switch the current Context.

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
single records. Compare and translation artifacts may eventually share a
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
- The first implementation loads complete records to build summaries. A
  rebuildable derived index may replace that scan if scale requires it; such
  an index must never become the source of session truth.
- Session deletion, archive, rename, cross-operation search, and true project
  grouping remain separate operations.
