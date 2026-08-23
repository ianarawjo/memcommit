# Search, Find, and Replace naming and execution contract

## Problem

The original public `mem find` performed provider-backed semantic retrieval.
That name conflicts with the familiar terminal and editor meaning of Find:
locating literal text without interpretation. MemCommit also lacks one reviewed
deterministic operation for replacing every exact match in a frozen Context
scope, including redaction-like replacement with an explicit placeholder.

The three behaviors must remain distinguishable in Help, application code,
receipts, and agent contracts:

```text
search   natural-language relevance -> ranked evidence
find     literal or explicit-regex text -> exact matches
replace  reviewed exact matches + replacement -> atomic Context changes
```

## Naming migration

`search` becomes the canonical name of the existing semantic operation. During
the staged implementation, the former `mem find` spelling may remain hidden
only until the provider-free Find command takes that public name. Existing
durable history is never rewritten merely to normalize the spelling. A legacy
semantic Find checkpoint or evaluation record therefore keeps its recorded
operation name, while new Search materialization records use `search`.

Internal `FindSearch*` compatibility types and modules may remain temporarily
while their callers migrate. They do not authorize a second semantic execution
path. New adapters call the same typed Search application use cases rather than
invoking the old CLI through a subprocess.

## Provider-free Find

Find is a read-only exact-text operation. Its default match mode is literal;
regular expressions require an explicit option. One request freezes canonical
readable Context roots, lexical reach, embedded reach, case policy, and the
query before scanning. Query-only content remains concealed, and a MemoryRef
match identifies the owning Source rather than pretending the Target owns the
text.

Find creates no Context, checkpoint, semantic cache, visible session, or
provider request. Its typed result may be handed to another reviewed operation,
but presentation alone never mutates or materializes a result.

A supplied pattern is a complete one-shot request. Up to ten matches therefore
print directly and return to the shell. When an automatic TTY route has more
than ten matches, the same completed result opens a primary-screen compact
pager rather than the setup workbench or alternate screen. It shows one stable
ten-row page, reports an exact range such as `SHOWING 1–10 OF 64`, moves the
focused row with Up/Down, moves discrete pages with Left/Right or
PageUp/PageDown, reaches the result boundaries with Home/End, and leaves the
last inspected page in terminal history when Escape or `q` closes it.

The application result remains complete. `--plain` preserves a bounded static
projection for scripts or explicit noninteractive output, and pipes are always
plain; `--all` prints every row. Every human Source Reference row folds stored
whitespace but retains the complete Memory content and provenance; terminal
width may wrap one logical row onto multiple physical lines, but Find never
inserts an ellipsis or discards a content suffix. `--copy` and TUI whole-result
copy likewise retain every row and its complete content, so display paging
never changes execution or machine-facing span data. Operand-free `mem find`
and explicit `--tui` use a primary-screen compact `SCOPE → FIND → RESULTS`
form rather than an alternate full-screen setup. The exact Context field is
always visible; the complete Profile/multiple tree is rendered only while
Browse is open. See `find-search-compact-scope-design-rationale.md`.

Find and ordinary Query share the neutral `SourceReferenceRow` facts and its
two explicit arrangements, not one evidence model. Query retains its
content-first citation row. Find uses `N [UID] content, [Context mX]`: `N` is
stable match order while `mX` is the Memory-shaped item's position in the
complete frozen searchable corpus, so nonmatching earlier items are not erased
from the visible location identity. Find also owns complete spans, MemoryRef
provenance, and the ten-row page policy. Query owns first-use citation numbering
and its own temporary evidence aliases. Raw `start:end` spans remain in Find's
typed result and Replace planning but are omitted from the default human row.

## Deterministic Replace

Replace is a direct deterministic operation over directly owned ordinary
Memories. One execution internally freezes every Context and Memory identity,
content digest, exact match span, match mode, and replacement, then revalidates
that complete boundary before publishing. The frozen plan is a concurrency
primitive, not a human approval artifact: the CLI and compact TUI never expose
its digest or require a second Apply gesture. Execution preserves Memory UIDs
and order and publishes all affected Contexts as one Undoable command unit. A
stale Context, lost authority, lock, malformed expression, or write failure
publishes no partial replacement or checkpoint.

Literal replacement is the default. Regex, case-insensitive matching, and
match deletion are opt-in behaviors whose exact values enter the frozen plan.
Deleting an entire Memory remains `delete`; semantic KEEP/EDIT/DELETE decisions
remain `forget`. Redaction is an exact Replace whose replacement is an explicit
placeholder or whose reviewed mode explicitly deletes only the matched text.

References and query-only views are never edited through their displayed
content. Embedded and lexical reach locate eligible owning Contexts but do not
turn a pointer into a writable owner. A successful Apply records exact counts,
affected Contexts, before/after digests, and one operation-level Undo/Redo unit.

The implemented application/runtime core keeps the plan process-local but
reproducible: its public digest excludes the opaque runtime token, so a later
adapter can rebuild the same plan from exact request values and compare the
digest before Apply. The token binds one in-process Apply to the Store instance,
all scanned Context identities and digests, and one operation UID used only to
group checkpoints for Undo/Redo.

`mem replace PATTERN REPLACEMENT` is a complete command and executes
immediately in both interactive and noninteractive terminals. `--plain`
changes only receipt styling; it is not a preview mode. Operand-free Replace,
an incomplete interactive request, and explicit `--tui` use a primary-screen
compact `SCOPE → FIND → REPLACE WITH` form. Enter on `REPLACE WITH` executes
the same direct application path, closes the form, and leaves only the concise
success or no-change receipt in terminal history. The form deliberately has no
Review, To Do, plan digest, or exact-command approval surface. Machine adapters
may retain typed plan/apply handles for compatibility and remote review, but
that two-call protocol does not broaden or delay the human command contract.

Completeness includes Contexts that contained no match during planning. Apply
holds those read-only source bindings through every changed-Context write, so
a newly matching sibling makes the plan stale instead of being silently
missed. Version 1 also freezes the complete local Context-name catalog. This is
deliberately conservative: creating or deleting an unrelated Context requires
replanning, but it closes descendant-membership races without teaching the
Store transaction about Replace-specific lexical or embedded scope semantics.

Regex controls which spans match; replacement text itself remains literal and
does not expand backreferences. Empty replacement removes only the matched
text and retains the Memory identity. Checkpoint metadata stores hashes of the
pattern and replacement rather than duplicating potentially redacted text;
the ordinary before/after snapshots remain the recovery source of truth.

## Interface and evidence rollout

Each operation owns one terminal-independent application contract and projects
it independently through CLI, TUI, public Python, agent, and MCP adapters.
Shared Context targeting, focus, result viewing, exact review, and receipt
components remain presentation mechanics rather than operation policy.

The rollout is intentionally staged:

1. promote the existing semantic route to canonical Search without changing
   its result meaning;
2. add provider-free Find and verify it never constructs a provider (complete;
   see `find-application-boundary-matrix.md`);
3. add direct Replace over an internal frozen-plan atomic Apply/Undo boundary
   (complete);
4. expose and verify every adapter, Help projection, and real-terminal flow
   (complete; see `replace-callable-boundary-matrix.md`).

Search retains the current route conclusion until its conversational controller
also enters the reviewed application boundary. Find is now `CLOSED`: every
implemented CLI, TUI, Python, agent, and MCP route enters its reviewed
application/runtime boundary. Replace is now `CLOSED`: its CLI, TUI, Python,
agent, and MCP routes share the reviewed plan, stale-scope rejection, atomic
Apply, and operation-unit recovery boundary.

## Intentional non-goals

- Find does not rank by meaning, answer a question, or silently broaden scope.
- Replace does not select matches semantically, rewrite prose, or mutate a
  referenced Source through a Target pointer.
- Forget is not overloaded with a second literal execution mode; exact removal
  is composed from Find with Delete or Replace.
- The naming migration does not reinterpret historical receipts or evaluation
  observations recorded under the old semantic `find` name.
