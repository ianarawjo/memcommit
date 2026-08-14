# Interactive Find search and scope rationale

## Problem

The one-shot `mem find QUERY` contract required a person to know both the query
and the search frame before entering the command. Its default frame originally
combined three different ideas: one selected Context, lexical namespace
descendants, and explicitly embedded Contexts. `--direct` disabled both
descendant and embed traversal together, and the CLI exposed only one root even
though the candidate collector already accepted multiple roots. The help text
described the result type but did not make that provider-disclosure boundary
legible. Later repeatable roots still left the two scope axes implicit, while
the workbench displayed them independently.

## Decision

In a TTY, operand-free `mem find` opens one process-local search
workbench. It starts with an empty one-line `SEARCH` field focused, the current
or explicit Context checked, and no provider call. `mem find QUERY` remains the
non-interactive one-shot route and retains stable grouped output for scripts,
redirection, and existing callers. Operand-free Find outside a TTY fails with
an explicit query-required message rather than blocking on terminal input.

The workbench presents four setup/search controls in interaction order, then
adds three outcome controls only after a completed search returns at least one
result:

1. `SEARCH`, a one-line query submitted with Enter;
2. `TARGETS`, a process-local `PROFILE` row followed by the frozen readable
   Context tree, with Enter or Space changing the checked range while focus
   remains in the tree;
3. `SCOPE`, with independent `TARGET SELECTION`, `CONTEXT RANGE`, and
   `EMBEDDED CONTEXTS` choices; and
4. `RESULTS`, one checkable row per canonical ranked result;
5. `SAVE AS`, with an exact `COPY` or `REFERENCE` mode;
6. `SAVE LOCATION`, the shared direct exact-name field and frozen local parent
   browser; and
7. `TO DO`, the explicit create action for the checked set.

The one-shot CLI exposes the same two scope axes. `--descendants` and
`--context-only` choose lexical reach; `--follow-embeds` and
`--exclude-embeds` independently choose embedded-Context traversal. Both
positive choices remain the compatibility defaults. Repeatable `--context`
operands apply that shared scope to every selected root. The older `--direct`
form remains a compatibility shorthand that forces both axes off and takes
precedence when supplied, so existing scripts retain their exact disclosure
boundary.

Every peer frame is composed through the service-wide vertical workbench rule:
`SEARCH → TARGETS → SCOPE → RESULTS`, followed conditionally by
`SAVE AS → SAVE LOCATION → TO DO`. Find does not use side-by-side frame
columns. This keeps visible order, Tab order, and vertical arrow traversal
identical across viewport sizes and matches Review, Atomize, and the common
Resolution Session. The Save Location field is the first focus stop in its
editor; Up enters the parent tree rendered above it, and Enter on a parent
reparents the current final name segment without creating anything.

Before a successful nonempty search, the Save As group is absent from both the
canvas and focus topology, and Tab and Shift-Tab retain the original
four-control loop. Once results exist, they include the Save As controls in
that same order while preserving the internal
cursor of each Surface. Up and Down first move inside the focused Surface;
crossing its first or last row moves to the adjacent visible Surface without
wrapping the screen. Vertical entry into TARGETS or SCOPE selects the adjacent
edge row. Enter is routed through the same Surface declaration but retains the
operation-owned meaning of running Search, checking a Target, checking a
Result, reviewing the exact Save Location, or creating the displayed output.
An empty Results surface still returns to Search. The search field owns initial
focus so opening Find feels like opening a search engine rather than entering
a setup wizard. An empty query is UI state, not a request to rank every item.

`PROFILE` is a virtual Find target above the ordinary namespace. It means every
name in the frozen readable catalog for this workbench; it is not a persisted
Context, a locator accepted by storage, or a new authority boundary. Selecting
it replaces other roots. Acting on an individual Context afterward converts the
shortcut into ordinary namespace roots before applying that edit, so a checked
Profile marker never misleadingly means “all” after part of it was removed.
When the initial Context is a granted READ view, it remains the initially
checked row but does not narrow this catalog: local Contexts and all other valid
READ grants remain available under Profile.

Target cardinality starts in `MULTIPLE` to preserve the fast path of checking
peers on the first visit to the tree. It counts selected target ranges rather
than the number of concrete Contexts produced by a subtree. `SINGLE` makes the
next checked row replace the current target. Changing an existing multi-root
selection to `SINGLE` retains the most recently explicitly checked root rather
than silently returning to the initial current Context. Enter and Space are
selection keys in `TARGETS`; `/`, Escape, and Backspace are the explicit paths
back to `SEARCH`. Escape on the root Search field closes the workbench, so a
person can always leave with Escape after at most one retreat. Backspace stays
ordinary deletion in Search. This prevents Enter from appearing to accept a
row while actually abandoning the tree unchanged.

`CONTEXT RANGE` chooses how a Context row behaves. `THIS CONTEXT ONLY` changes
only that row. `INCLUDE DESCENDANTS` checks or clears its complete readable
lexical subtree, including descendants that are currently collapsed. Descendant
rows remain independently editable after a group action. The selected roots
and any process-local subtree exclusions derive one effective checked set;
changing the range clears stale exclusions so the newly visible policy starts
from the explicit roots. The legacy default starts on `INCLUDE DESCENDANTS`,
matching the one-shot `--descendants` default. `FOLLOW` under
`EMBEDDED CONTEXTS` remains an independent graph-traversal choice and matches
the one-shot `--follow-embeds` default. `--direct` starts both workbench axes in
their restricted state when it seeds an operand-free TTY launch.

Search executes the exact visible checked set rather than re-expanding a parent
behind the UI; otherwise an independently unchecked child would still be
searched. The virtual Profile row likewise resolves to the exact frozen
readable catalog at this boundary and never enters a request as a fake Context
name.

While provider-backed search is running, the same animated `SEARCHING` state is
shown in both the `RESULTS` frame title and the footer. The upper copy keeps the
work visibly active next to the surface awaiting output; the footer copy remains
available as the global close and frozen-scope status line. Both disappear when
the background turn completes or fails.

Every workbench submission freezes the query, ordered exact checked targets,
embed choice, and limit into one `FindSearchRequest` with descendant expansion
disabled. Changes to query, targets, or scope invalidate the visible result set
and clear its checked set before requiring another Enter; stale rows must never
appear to describe a new frame. Result checks default to empty and follow the
frozen ranked order rather than interaction history. Search work runs outside
the prompt-toolkit event-loop thread while the exact request stays visible and
immutable. Closing during a search waits for that read-only turn to complete.

`COPY` and `REFERENCE` are intentionally Save As modes, not semantic
keep/drop decisions. `COPY` creates one fresh Memory identity per checked
source using the exact reviewed value. `REFERENCE` delegates to the same live,
read-only pointer primitive as `mem reference`: it stores the directly owned
source Context UID and Memory UID, not a content copy. Both modes create one
new local Context, leave every Source unchanged, preserve ranked selection
order, and write one automatic `find` checkpoint containing the query, mode,
source identities, and output identities. Save Location is require-new and
never changes the current Context.

Immediately before publication, each checked row is resolved from its frozen
source Context UID and Memory UID and its current content must still equal the
value displayed by Find. Local sources are then rechecked under the same lock
set as the require-new output write. Granted sources retain their exact locked
authority snapshots until local COPY publication commits. Failure publishes
no partial result.

## Authority and privacy boundaries

The target tree comes from `ReadableContextCatalog`. Each public name retains
its exact `ContextAccess`; a Grant attachment is never treated as a namespace
edge. Query-only views are not selectable ordinary roots. Their already-public
names may still appear as current-state candidates where the selected readable
parent exposes them, but their concealed contents are never opened.

Overlapping checked targets and embeds are deduplicated by Context identity
and logical item identity before ranking. READ-granted roots
may contribute authorized Memory content but never the authority Profile's
private checkpoints, sessions, traces, or rationale artifacts. Temporal
queries remain unavailable for a selected granted root because READ authority
does not expose checkpoint history.

Search, target, scope, tree expansion, provider results, and checked state stay
process-local unless the person activates the exact `TO DO` row. The stored
checkpoint records source identities and the query needed to explain the
curation, but no search preference or provider dialogue is persisted. Existing
one-shot current/history routing and provider output validation remain the
semantic execution boundaries.

Only current-state owned Memory and resolved MemoryRef rows can be saved as a
new Context. History, query-only, and retained-artifact rows remain evidence
views. REFERENCE is restricted to locally owned sources because the durable
pointer contract does not grant the destination continuing authority over a
remote Grant resource. COPY from a granted source requires `DERIVE`, `EXPORT`,
`SAVE_ANALYSIS`, and `COMBINE` when multiple authority domains contribute;
grant identity and permission are revalidated through the write boundary.

The user-facing operation is consistently named `SAVE AS`. The existing
`find_materialization` checkpoint field and Python compatibility symbols remain
unchanged so previously written checkpoints and callers retain their exact
schema; those tokens are implementation history, not terminal language.

The workbench now submits one `FindMaterializationRequest` to the
terminal-independent application boundary. That boundary validates the exact
CURRENT response, checked row set, mode, destination, prepared-plan identity,
and final receipt shape without importing Store, provider, CLI, or TUI code.
`MemoryStoreFindMaterializationPort` owns live source resolution, derived-use
authority, output construction, source locks, require-new publication,
checkpointing, and rollback. The workbench no longer invokes persistence
mechanics directly, while `commands.find_materialization` remains a thin
compatibility facade over the same use case.

## Reuse and limitations

The workbench reuses the common Surface focus controller, Context tree,
horizontal-choice renderer, shared exact Context-name/parent control, focused
Frame styling, terminal escaping, and close-safe background-turn controller.
The flat selection family now includes a reusable multiple-check state whose
cursor and ordered checked set stay independent; Find renders result rows
through that shared state rather than cloning checkbox mechanics.
`ContextTreeState` continues to own only cursor and expansion, while the shared
`ContextSelectionState` owns checked values. Find is the only current operation
that configures that state for multiple roots; the common endpoint and Sever
setups use the same state in single-selection mode. Multi-selection semantics
are not added to the full-screen generic picker or exposed to those operations.

The one-shot `--context` option is repeatable, but its two scope choices apply
uniformly to every supplied root. Per-root mixtures such as subtree A plus
exact B, and TUI-only independent descendant exclusions, are intentionally not
encoded in the one-shot flag grammar. Result inspection and conversational
follow-up remain separate from this Google-like search surface; the retained
legacy Find chat shell is not silently reactivated. The result action is
explicit curation only: it does not save the provider's ranking explanation or
turn selected rows into proof that the query was answered. Query-only routes
remain a separate authorized interface and never become selectable ordinary
roots.

Multiple-target editing may temporarily leave zero rows checked. Clearing the
last row changes only process-local UI state; pressing Search then fails before
provider connection because `FindSearchRequest` requires at least one distinct
readable Context. Switching that empty control to SINGLE selects the visible
tree cursor so single-cardinality state cannot become invalid.
