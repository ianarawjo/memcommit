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

## Deterministic Replace

Replace is a plan/review/Apply operation over directly owned ordinary Memories.
The plan freezes every Context and Memory identity, content digest, exact match
span, match mode, and replacement. Apply revalidates that complete boundary,
preserves Memory UIDs and order, and publishes all affected Contexts as one
command unit. A stale Context, lost authority, lock, malformed expression, or
write failure publishes no partial replacement or checkpoint.

Literal replacement is the default. Regex, case-insensitive matching, and
match deletion are opt-in behaviors whose exact values enter the frozen plan.
Deleting an entire Memory remains `delete`; semantic KEEP/EDIT/DELETE decisions
remain `forget`. Redaction is an exact Replace whose replacement is an explicit
placeholder or whose reviewed mode explicitly deletes only the matched text.

References and query-only views are never edited through their displayed
content. Embedded and lexical reach locate eligible owning Contexts but do not
turn a pointer into a writable owner. A successful Apply records exact counts,
affected Contexts, before/after digests, and one operation-level Undo/Redo unit.

## Interface and evidence rollout

Each operation owns one terminal-independent application contract and projects
it independently through CLI, TUI, public Python, agent, and MCP adapters.
Shared Context targeting, focus, result viewing, exact review, and receipt
components remain presentation mechanics rather than operation policy.

The rollout is intentionally staged:

1. promote the existing semantic route to canonical Search without changing
   its result meaning;
2. add provider-free Find and verify it never constructs a provider;
3. add frozen-plan Replace and its atomic Apply/Undo boundary;
4. expose and verify every adapter, Help projection, and real-terminal flow.

Search retains the current route conclusion until its conversational controller
also enters the reviewed application boundary. Find and Replace begin
`UNREVIEWED` and receive their own focused matrices before any stronger route
claim is made.

## Intentional non-goals

- Find does not rank by meaning, answer a question, or silently broaden scope.
- Replace does not select matches semantically, rewrite prose, or mutate a
  referenced Source through a Target pointer.
- Forget is not overloaded with a second literal execution mode; exact removal
  is composed from Find with Delete or Replace.
- The naming migration does not reinterpret historical receipts or evaluation
  observations recorded under the old semantic `find` name.
