# Search, Find, and Replace naming and execution contract

> **Authorization contract updated 2026-08-30.** Permission claims below that use `EMBED`, `DERIVE`, `COMBINE`, `EXPORT`, `ACCEPT_DERIVED`, or `SAVE_*` describe the retired contract preserved for design history. The current contract uses `QUERY`, `CREATE`, `READ`, `UPDATE`, and `DELETE`; `READ` covers readable semantic use and Embed traversal, while `SHARE` remains a separate endpoint capability. See `granted-derived-ownership-design-rationale.md`.

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

The internal migration is now complete: semantic retrieval uses `Search*`
types and functions, while provider-free matching uses `Find*`. No
`FindSearch*`, `LiteralFind*`, or inverse adapter compatibility facade remains.
Historical root-module import paths are handled only by the centralized lazy
compatibility finder; production code imports the canonical operation owners.

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

A supplied pattern is a complete one-shot request. It always prints the same
bounded ten-row projection and returns to the shell, regardless of TTY state;
`--all-results` prints every row. The application result remains complete.
Every human Source Reference row folds
stored whitespace but retains the complete Memory content and provenance; terminal
width may wrap one logical row onto multiple physical lines, but Find never
inserts an ellipsis or discards a content suffix. `--copy` and TUI whole-result
copy likewise retain every row and its complete content. Operand-free
interactive `mem find` uses a primary-screen compact `SCOPE → FIND → RESULTS`
input form. The exact Context field is
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

Find and Search share one command-line breadth spelling: `-a/--all` expands the
request to every Context in one frozen Profile-readable catalog. It cannot be
combined with explicit `-c/--context` roots, and the virtual word `PROFILE`
never enters an application request or storage lookup. The exact canonical
names are frozen once and remain subject to the operation's independent
descendant and Embed choices. This makes the one-shot CLI match the existing
interactive `PROFILE · ALL READABLE CONTEXTS` target. Semantic Search also
authorizes the complete frozen contributor set for `DERIVE` and cross-domain
`COMBINE` before constructing its provider; provider-free literal Find needs
only the already-frozen READ bindings. Human Find and Search report chrome
projects that virtual target as `ALL READABLE CONTEXTS` instead of enumerating
the frozen names. The names remain explicit in the application request and in
per-result provenance; compact presentation must not weaken the execution or
evidence boundary.

Find formerly used `--all`, and briefly `-a`, for presentation completeness.
That spelling was reassigned because a retrieval command's unqualified “all”
is expected to describe what is searched, while a bounded preview changes only
what is printed. Complete static output remains available through the explicit
`--all-results` name. Keeping the old overload or assigning `--all` different
meanings in Find and Search was rejected because the same scope family would
then disclose different Context sets for identical flags.

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

The Replace command package retains a separate human-readable proposal
projection for the planned proposal workflow. It is intentionally distinct
from the completed-command receipt and is not yet wired into the direct CLI or
compact TUI route. Preserving that projection does not expose the process-local
token, turn the current digest into a human approval artifact, or add a second
Apply gesture before the proposal contract is reviewed.

`mem replace PATTERN REPLACEMENT` is a complete command and executes
immediately in both interactive and noninteractive terminals. Operand-free
Replace or an incomplete interactive request uses a primary-screen
compact `SCOPE → FIND → REPLACE WITH` form. Enter on `REPLACE WITH` executes
the same direct application path, closes the form, and leaves only the concise
success or no-change receipt in terminal history. The form deliberately has no
Review, To Do, plan digest, or exact-command approval surface. Machine adapters
may retain typed plan/apply handles for compatibility and remote review, but
that two-call protocol does not broaden or delay the human command contract.
The retired `--plain` and `--tui` flags are rejected; input completeness, not a
presentation mode, selects the editor.

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
