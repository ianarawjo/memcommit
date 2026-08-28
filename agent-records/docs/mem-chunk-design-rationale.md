# Mem Chunk Design Rationale

Chunk's implementation owner is now the `memcommit.application.operations.chunk` package:
`domain` owns mechanical text splitting, `application` owns direct-Memory
resolution and replacement construction, and `runtime` owns authorized
checkpointed publication. The former `memcommit.chunking` path is an identity
alias and `memcommit.application.capabilities.ops.chunk` is the same application function, preserving
public compatibility through a lazy adapter without retaining a second
behavior owner. See
`chunk-application-boundary-matrix.md` for the reviewed dependency boundary.

## Problem

`mem chunk` originally required one direct Memory UID and defaulted to
`paragraphs`. That made a Context already populated with paragraph-sized
Memories awkward to refine: the person had to discover and submit each UID,
and the default often returned one unchanged chunk. The mechanical operation
also looked narrower than its actual workflow role, which is to refine an
already-ingested Context into smaller reviewable units.

## Command contract

Chunk has one Context mutation boundary and two target ranges:

- `mem chunk` splits every splittable directly owned Memory in the current
  Context;
- `mem chunk --context CONTEXT` does the same in one explicit local Context or
  granted view;
- `mem chunk CONTEXT` splits every directly owned Memory in that existing
  Context without switching current;
- `mem chunk MEMORY_SELECTOR` finds one uniquely owned ordinary-local direct
  Memory even when its owner is not current;
- `mem chunk CONTEXT:MEMORY_SELECTOR` states that direct owner explicitly; and
- `mem chunk MEMORY_SELECTOR --context CONTEXT` selects one direct Memory in
  the explicit Context.

The positional operand uses the shared Context/direct-Memory classifier. A
Context-shaped value remains an existing Context locator; a bare public
UUID-shaped selector scans one strict ordinary-local direct graph and requires
one unique owner; and `CONTEXT:UID` or `--context CONTEXT` explicitly supplies
the owner. A granted Context can be selected explicitly through Chunk's normal
authority port, but bare Memory discovery does not enumerate Grants. When the
current pointer is itself a nonlocal public Grant selection, a bare Memory
selector retains that already explicit authority-bearing owner instead of
pretending the ordinary-local catalog could rediscover it. The current Context
is captured once and every relative owner is resolved against that snapshot.

A Context-scoped run freezes one ordered split plan, displays the canonical
public target, and immediately publishes every replacement in one Context save
and checkpoint. The command invocation is the complete approval boundary; the
displayed plan is useful effect visibility, not a second decision prompt.
Memories that produce zero or one chunk are retained with
their existing UID and position. Embedded Contexts, immutable Memory
references, query-only sources, and descendants are not traversed: their
presence in the visible Context does not transfer ownership to Chunk.

## Default unit and ingestion boundary

The default method is `sentences`. `--method paragraphs`, `--method
markdown_headers`, and `--method clauses` remain explicit structural
alternatives. Sentence recognition is intentionally mechanical and
language-neutral: terminal punctuation followed by whitespace is a boundary
even when the next character has no Latin uppercase form. This improves Korean
and other uncased scripts, but abbreviations and code can still produce
approximate boundaries; semantic claim separation remains Atomize's role.

Three independent refinements can be added to any method: `--break-on` names
literal punctuation or symbol boundaries, `--max-chars` sets a hard
Unicode-code-point ceiling, and `--min-chars` requests a preferred packing
floor. A short chunk is retained when absorbing it would cross the hard
maximum; the preview reports each such minimum miss before publication. These
controls are explicit because no one size or punctuation set is a safe
universal semantic unit.

`clauses` adds `.`, `!`, `?`, `;`, `:`, and the em dash (plus common full-width
sentence and clause forms) to the preferred boundary set, but deliberately
does not add comma. Its built-in punctuation must end the content or be
followed by whitespace, which avoids treating decimal points, URL punctuation,
and time colons as ordinary prose boundaries. `--break-on` is the explicit
escape hatch: every listed punctuation or symbol code point is literal,
additive, retained on the left chunk, and effective even without following
whitespace. It is not a regular expression.

When limits are present, adjacent preferred units are packed in Source order.
An oversized unit first breaks at the latest whitespace inside `--max-chars`;
a single token longer than the maximum is split at the exact code-point limit.
That last behavior is intentionally mechanical and visible in the preview.
The alternative—silently exceeding the stated maximum—would make the option
unreliable for downstream size budgets. `--min-chars` never overrides the hard
maximum and therefore cannot be a universal guarantee.

The intended refinement pipeline treats paragraph-sized Memory creation as an
upstream ingestion responsibility and sentence-sized Chunk as the ordinary
post-ingestion refinement. This is a design boundary, not a claim that every
legacy Add or Import path already enforces paragraph ingestion. Until all
ingestion adapters share that contract, an explicit `--method paragraphs`
remains useful for older multi-paragraph Memories.

## Authority, execution, and history

Loading and split-plan construction require the target's existing mutation
route and do not write state. Publication revalidates both `DELETE` and
`CREATE`, because each split removes one direct Memory and creates multiple
replacements. Any pre-save failure publishes no partial split.

Chunk no longer asks `Apply? [y/n]`. Like Clear, it is a deterministic,
single-Context command whose successful effect is captured as one checkpoint
and can be restored with `mem undo`, then reapplied with `mem redo`. Keeping a
second yes/no prompt would make interactive and scripted invocation differ
without adding a distinct judgment or recovery boundary. Permanent deletion
remains different because it destroys the history needed for Undo and retains
its separate confirmation contract.

Single-Memory checkpoints retain their historical `uid` field for compatible
Trace and restoration. Context-scoped checkpoints record every exact Source
UID and ordered replacement UID list. Both forms also record every non-default
literal and size control. Trace replays those settings and validates the
identity map, resulting order, and content before reporting a recorded or
reconstructed `SPLIT` event; it does not infer parentage from potentially
repeated content.

## Deliberate non-goals

- Chunk does not decide whether a sentence is an atomic claim.
- Context scope does not include lexical descendants or embedded traversal.
- Chunk does not consume quality-finding handoffs or redundancy evidence.
  Confirmed semantic redundancy belongs to Dedun, while conflict finding
  handoffs belong to Resolve.
- The change does not retroactively rewrite existing paragraph-based
  checkpoints or their reconstructed lineage.
