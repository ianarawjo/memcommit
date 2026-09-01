# `mem list` / `mem ls` Design Rationale

- Status: Implemented
- Scope: canonical `mem list` with the exact compact `mem ls` spelling,
  immediate namespace
  child navigation, recursive listing with `-R`, `--recursive`, or the
  beginner-facing `--expand` alias, and plain-text `--copy`

## 1. Purpose

`mem list`, also available through the compact `mem ls` spelling, is the
navigation command for a memcommit Context. It answers:

> Which materialized child Contexts can I navigate to, and what direct items
> are stored in this Context?

It does not expose memcommit's physical storage layout. The fact that a Context
is currently persisted in a local `context.json` file or read through an exact
authority grant is an implementation detail. Canonical public names determine
the visible hierarchy; a grant's attachment Context remains authorization
metadata rather than becoming the granted Context's semantic parent.

This distinction is similar to Git:

- the shell's `ls` lists physical filesystem entries;
- `git ls-tree` interprets Git objects and lists a logical tree;
- `mem list` / `mem ls` interprets a Context, derives its immediate materialized
  namespace children, and lists its logical Memory, MemoryRef, and embedded
  Context entries.

Consequently, `context.json`, `checkpoints/`, and other storage artifacts must
never be mixed into normal `mem list` output.

## 2. Command Surface

The supported forms are:

```bash
mem list [context]
mem ls [context]
mem list -R [context]
mem ls -R [context]
mem ls --recursive [context]
mem ls --expand [context]
mem ls [context] [-R] --copy [--with-ids]
```

`mem list` is the canonical discovery name and `mem ls` is its exact compact
spelling. Both forms retain identical behavior, options, and implementation;
they share one callback so the executable contracts cannot drift. Command
discovery shows one `list (ls)` entry rather than presenting one operation as
two separate rows. The root `ls` registration is hidden from generated command
inventories, not deprecated or behaviorally narrower.

When no Context is supplied, the current Context is used.

`--expand` is an exact alias for `--recursive`, not a separate traversal
mode. `recursive` preserves the conventional shell vocabulary and `-R`
preserves its compact spelling; `expand` describes the visible result for a
person who does not already know that convention. No `-e` alias is added:
another short spelling would add recall cost without making the scope clearer.
All three forms remain rooted at the selected Context and do not mean
"every Memory in the Profile" or cross a query-only boundary.

## 3. Default Listing Is Direct, Not Recursive

Without `-R`, only immediate navigation rows and direct persisted items are
listed. A navigation row is derived for every existing ordinary or effectively
READ-granted Context whose canonical public name is exactly one namespace
segment below the listed Context.

Given:

```text
parent
├── materialized Context: parent/child
│   └── Memory: Child fact.
└── direct Memory: Parent fact.
```

the default result is:

```text
Context: parent
  1 memory
  1 subcontext

  DESCENDANT · [context 12345678] parent/child
  [memory abcdef12] Parent fact.
```

`Child fact.` is intentionally absent. This follows the normal directory
navigation model: listing a directory shows the child directory entry, not all
of that child's descendants.

The visible child keeps its full canonical name instead of shortening to
`child/`. Bare Context operands are global in this CLI, so a basename would
incorrectly suggest that `mem ls child` selects `parent/child`; the explicit
relative spelling for that operation is `mem ls ./child`.

The child can be inspected explicitly:

```bash
mem ls parent/child
```

or recursively:

```bash
mem ls -R parent
```

## 4. Contexts Are Displayed Before Atomic Information

A Context behaves like a logical directory, so namespace children and direct
embedded Contexts are displayed before direct Memory and MemoryRef entries.

The summary deliberately does not add these heterogeneous rows into one
`items` total. It reports direct Memory-shaped rows and direct subcontext rows
independently. `Memory`, live Memory Embed, and immutable Memory Reference rows
contribute to the Memory count; namespace descendants, embedded Contexts,
Context References, and query-only Context views contribute to the subcontext
count. In a recursive listing, the header still describes the selected root's
direct rows, while the copy receipt reports the separately typed totals for
the complete visible occurrence tree.

A subcontext's reach precedes its identity:

```text
DESCENDANT · [context 12345678] parent/child
VIA EMBED · [context 87654321] related/context
```

Reach answers why the row occurs beneath the selected Context; it is not a
property of the canonical Context name. Leading with that fact makes a tree's
namespace and embed edges scannable before the varying UID and name columns.
Only `VIA EMBED` receives the shared Embed color; `context`, its UID, and its
name stay neutral. Clean clipboard text keeps the same order without the
`[context UID]` selector.

This grouping is a presentation rule only. It does not rewrite the Context's
persisted `order` field.

Within each group:

- namespace-derived children are sorted by canonical name;
- embedded Contexts retain their relative Context order;
- Memory and MemoryRef entries retain their relative information order.

Namespace-derived children precede persisted logical items. If the same
canonical child with the same UID is also directly embedded, the derived row
is suppressed and the persisted occurrence retains its typed embed identity,
but it occupies that canonical name's sorted namespace-child position. This
is a display reorder only; the Context's persisted `order` is unchanged. A
same-named QueryContextRef is never deduplicated against an ordinary Context.

The catalog and Context records are separate filesystem reads. If a child is
deleted and recreated between them, the currently loadable child UID wins the
one canonical-name row and an already loaded stale embed occurrence is
suppressed. This avoids presenting one locator twice with conflicting
identities; it does not repair or save the stale parent record.

For example, if the persisted order is:

```text
Memory A -> Context B -> MemoryRef C -> Memory D
```

the displayed order is:

```text
Context B -> Memory A -> MemoryRef C -> Memory D
```

This makes navigation predictable without discarding the meaningful order
among atomic information entries.

## 5. Memory Content Is Its Human-Readable Name

An atomic Memory intentionally has only:

```text
uid + content
```

There is no separate title or filename. Adding a title would duplicate
information for short atomic memories and would make the minimal Memory model
more complex.

Therefore, `mem list` uses the Memory's content as its human-readable name:

```text
[memory  abcdef12] The north entrance is closed until Friday.
```

The short UID remains visible because it is the selector used by commands such
as `mem show`, `mem remove`, and `mem reference`. At command start, List freezes
a separate Profile-wide identity catalog containing every Context and direct
item UID in ordinary local and effectively READ-granted Contexts. Self-contained
Context snapshot descendants and visible MemoryRef Source UIDs participate as
well. QUERY-only routes are excluded: a
compact display requirement never authorizes their concealed Source content to
be opened. Every annotated rendering starts at eight characters. Only prefixes
that collide in that readable catalog grow one character at a time until they
differ, so `deadbeef-1111...` and
`deadbeef-2222...` appear as `deadbeef-1` and `deadbeef-2`, while unrelated
eight-character prefixes stay compact. Relationship-object UIDs and their
displayed Source Memory UIDs participate in the same screen-wide calculation.

List deliberately opens each readable Context's direct record once to freeze
that catalog. It walks content already retained inside an immutable Context
snapshot, but does not resolve live embedded Context pointers or open checkpoint
history. The shared projector sorts the distinct UIDs and compares
each value only with its adjacent prefix competitors, avoiding a quadratic
all-pairs scan after those reads. This makes a displayed prefix collision-safe
against an unlisted readable Context as well as the visible list. Distinct
owners that preserve the exact same full UID still require `CONTEXT:UID`, since
no longer UID prefix can separate them; command resolution continues to fail
closed and reports those full owner coordinates.

The copied annotated text stores only the chosen prefix for each UID already
visible in that invocation's frozen snapshot, not the unrelated readable UIDs
that caused it to grow. Copy is a one-way text output: it does not retain that
snapshot or UID catalog for later replay. A later `mem ls` freezes and renders
the then-current readable namespace again.

Normal terminal output begins the Memory content beside its selector. Long
content is wrapped to the current terminal width, and every continuation row
uses a hanging indent aligned with the first content character. At a recursive
depth where fewer than 20 columns would remain for content, rendering falls
back to a selector row followed by readable indented content rows.

Whitespace inside the content is still normalized to one logical line. This
normalization affects display only; the stored content is not changed.
Whitespace-only content is displayed as `(empty)`. The compact annotated
clipboard rendering remains one physical line per Memory:

```text
[memory  abcdef12] The north entrance is closed until Friday.
```

The visual wrap uses structural newlines, which a mouse selection may include.
`mem ls --copy --with-ids` uses a separate compact renderer and therefore puts
each annotation and its normalized Memory content on one physical clipboard
line regardless of the visible wrapping.

## 6. Root Context Paths and Memory Content Are Separate

The following direct items can coexist in one parent Context:

```text
embedded Context name: aaa/ab
atomic Memory content: aaa
```

They are different logical types, so the listing is unambiguous:

```text
VIA EMBED · [context 12345678] aaa/ab
[memory abcdef12] aaa
```

A stored Root Context named `aaa` and a stored descendant Context named
`aaa/ab` can also coexist. The root owns `aaa/context.json`, while the
descendant owns `aaa/ab/context.json`. Their histories and direct items remain
independent.

Path coexistence still does not create a persisted logical parent-child
relationship. However, `mem ls aaa` derives a read-only navigation row for an
existing immediate child such as `aaa/ab`; this does not add it to `aaa`'s
items. A deeper name is not synthesized through a missing intermediate
Context. Thus `aaa/ab/c` alone does not create a visible `aaa/ab` row. A
Memory whose content is `aaa` is independent of both Context paths.

## 7. Memory relationship listing

A resolved live Memory Embed and immutable Memory Reference both show Source
identity before their human-readable content. Their relationship noun makes
the different time semantics visible:

```text
[embedded 12345678] [source-context][memory abcdef12] Current Source content.  READ ONLY
[reference 87654321] [source-context][memory abcdef12] Retained snapshot content.  READ ONLY
```

Only `embedded` is yellow and only `reference` is mauve in a color-capable
terminal. UIDs, Context, content, and state remain neutral, and stripping ANSI
produces exactly the same text. A dangling relationship has no content to use
as a name, so the same leading identities are followed by `DANGLING`.

The Source identity is also an executable owner locator for
`mem edit source-context:abcdef12 CONTENT`; the relationship row's first UID
remains read-only. Detailed relationship metadata remains the responsibility
of `mem show <relationship-uid>`.

## 8. Recursive Listing

`-R` and `--recursive` traverse both namespace-derived children and embedded
Contexts to the deepest loaded level. Every visited Context receives the same
union view it would receive as the root of its own recursive list. The
traversal is depth-first and preserves the same Context-first rule at each
level:

```text
Context: parent
  1 memory
  1 subcontext

  VIA EMBED · [context 11111111] child
    VIA EMBED · [context 22222222] grandchild
      [memory 33333333] Grandchild fact.
    [memory 44444444] Child fact.
  [memory 55555555] Parent fact.
```

When a recursive level contains multiple Context children, one empty display
line separates their rendered blocks. The separator appears only between
sibling Context blocks, never before the first or after the last, and direct
listings retain their compact layout. This makes the end of one expanded
Context's Memories visually distinct from the next Context header without
changing traversal order or snapshot contents.

An empty embedded Context is explicit:

```text
VIA EMBED · [context 11111111] child
  (empty)
```

### Materialized namespace edges, not implicit embeds

Recursive listing follows exact immediate namespace children in addition to
explicit embedded Context references. The ordinary Context catalog is frozen
once per invocation; matching is one segment at a time rather than an
unbounded prefix scan.

For example, the existence of both:

```text
construction-updates
construction-updates/building-access
```

creates a read-only navigation edge from `construction-updates` to the
materialized immediate child `construction-updates/building-access`. It does
not add an embedded item to either Context, change either history, or make a
missing intermediate Context real.

This separates shell-like discovery from logical membership. Explicit embeds
still define the persisted graph used by mutation, checkpoints, and other
semantic operations; namespace rows exist only in this list result.

## 9. Cycle and Shared-Context Behavior

Indirect embed cycles can exist:

```text
A -> B -> A
```

Loading already cuts persisted back-edges, and recursive rendering also keeps
a path-local ancestor set as a defensive guard. `mem ls -R` must terminate
instead of recursing forever.

The guard is path-local rather than global. This matters for a diamond graph:

```text
root -> left  -> shared
     -> right -> shared
```

`shared` is listed once under `left` and once under `right`, because both are
valid embed paths. A global "visited" set would incorrectly suppress the
second path.

## 10. Terminal-independent listing

`mem list` and `mem ls` always render the frozen target-rooted snapshot. A
terminal does not open a second Profile-wide browser. Bare List resolves the
current Context; an explicit operand resolves that Context; `-r` / `-R`
expands the same recursive namespace and embed scope represented in the
output.

This keeps visible navigation equal to requested scope. The earlier browser
experiment showed unrelated Profile roots beside one exact List result, so a
person could not tell whether List described the current Context or offered a
Profile navigation action. Dim or grayscale styling would only weaken those
rows visually while leaving the competing scope in place. Interactive Profile
navigation now belongs to bare `mem switch`.

TTY and non-TTY output therefore share the same text format, authorization,
and snapshot construction. Embedded Context occurrences, repeated embeds,
cycles, MemoryRef resolution, opaque query pointers, and readable granted
descendants continue to use the existing snapshot contract. `--copy`,
and `--with-ids` never depend on terminal state. List has no `--paste` mode.
The cross-command rationale is recorded in
[`context-listing-design-rationale.md`](context-listing-design-rationale.md).

## 11. Relationship to `mem show`

The intended conceptual split is:

- `mem list` (or `mem ls`): compact immediate namespace navigation and
  hanging-indent Memory rows whose selectors remain beside their content;
- `mem list -R`, `mem list --recursive`, or `mem list --expand`: recursive
  navigation through namespace children and embedded Contexts;
- `mem show <selector>`: full detail for one selected Memory, MemoryRef, or
  embedded Context.

`mem show` without a selector currently also renders all direct contents of a
Context. That existing behavior is retained for compatibility, although it
overlaps with the compact listing use case. Raw storage JSON is not the normal
output of either command; a future export or developer command would be a
better place for raw JSON.

## 12. Copy as a plain-text output boundary

`mem ls --copy` writes one human-oriented text rendering of the current List
result to the macOS system clipboard. It does not create a private staged
payload, `clipboard.json`, or replayable List snapshot.

The default clipboard rendering omits `[kind uid]` annotations. Context names
end in `/`, with `DESCENDANT ·` or `VIA EMBED ·` still leading the row;
query-only names remain explicitly typed, and MemoryRef lines retain their
content-to-Context arrow without object UIDs. This keeps the text useful when
pasted into prose, chat, or another tool. `--copy --with-ids` instead puts
the compact inline indexed rendering in the clipboard. It contains the same
annotations shown by the normal terminal list, but keeps each Memory selector
and its normalized content on one physical line. Ordinary command stdout uses
the terminal-width-aware hanging-indent layout in both copy modes so a copy
operation does not remove the local selection cues.

`--with-ids` is a modifier of `--copy`, not an independent list mode. Using it
without `--copy` is rejected. The success receipt is not copied. Copy does not
save a Context, change the current Context, create a checkpoint, or write any
MemCommit-owned clipboard state. It reports Memory and subcontext occurrence
totals separately rather than recreating a mixed `items` count.

The clean rendering is intentionally human-readable rather than parseable.
A Memory whose text resembles a Context name or reference can therefore be
textually ambiguous after annotations are omitted. No object reconstruction
depends on that text. Normal stdout and `--with-ids` retain visible selectors
when a person needs them, and the compact clipboard renderer keeps each Memory
on one physical line instead of reproducing terminal-width wrapping.

Query-only source content is never opened or copied. READ-visible granted text
may be copied, including as part of a mixed local and granted recursive result,
because invoking `--copy` is an explicit user-controlled disclosure of the
authorized rendered text. Revocation cannot retract plaintext already placed
on the operating-system clipboard, and MemCommit retains no hidden replay
receipt afterward.

List deliberately has no `--paste`. To inspect current state again, run
`mem ls` against the Context. To keep a live Context relationship, use
`mem embed`; to preserve a durable point-in-time snapshot, use `mem reference`.
`mem add --paste` remains a separate intake contract that reads arbitrary
UTF-8 system-clipboard text and creates one Memory per non-empty physical line,
as described in
[`mem-add-paste-design-rationale.md`](mem-add-paste-design-rationale.md).

## 13. Deliberate Non-Goals

This change does not:

- add a title field to Memory;
- change the persisted item order;
- persist namespace navigation rows as automatic embeds or logical
  parent-child relationships;
- recursively expand children without `-R`;
- expose raw `context.json` data;
- change the behavior of `mem show`;
- automatically embed a path descendant into a Root Context;
- reconstruct MemCommit objects from copied List text;
- add List-style `--copy` to `show`, `find`, or other commands;
- support non-macOS system clipboards.

The current prototype discovers children by validating the complete ordinary
Context catalog once per invocation. Listing cost therefore grows with the
number of stored Contexts, even though each recursive level filters that frozen
catalog in memory. A future indexed or namespace-local catalog can improve
large-store performance without changing the visible contract.

## 14. Validation Scenarios

The implementation is covered by tests for:

- content-as-name for direct Memory entries;
- hanging-indent Memory rows at direct and recursive depths;
- Context-first rendering when a Memory was inserted first;
- separate Memory and subcontext counts at the selected root and in recursive
  copy receipts;
- leading `DESCENDANT` and `VIA EMBED` reach markers in annotated and clean
  Context rows;
- `aaa/ab` Context and `aaa` Memory content coexisting without ambiguity;
- relative ordering of Memory and MemoryRef entries;
- default listing not leaking child content;
- TTY `ls` rooted browsing with Memory rows initially visible;
- TTY `ls -R` beginning fully expanded while retaining repeated embedded
  occurrences;
- sorted immediate namespace children alongside current direct Memories;
- no synthesized child when an intermediate Context is missing;
- namespace recursion and explicit-embed deduplication;
- relative existing-Context locators such as `mem ls ../sibling`;
- recursion through two or more Context levels;
- parity among `list -R`, `ls -R`, `ls --recursive`, and `ls --expand`;
- finite output for an indirect persisted cycle;
- repeated traversal of a shared Context along both sides of a diamond;
- resolved MemoryRef content and provenance;
- existing non-recursive list and embed behavior;
- clean-by-default and `--with-ids` plain-text copy for both `list` and `ls`;
- inline annotated clipboard text distinct from wrapped terminal stdout;
- embedded Context, namespace Context, query-only, MemoryRef, and recursive
  clean rendering;
- rejection of `--with-ids` outside `--copy`;
- rejection of the removed `--paste` option;
- query-only source non-disclosure;
- mixed local and READ-granted recursive copy;
- failed system-clipboard writes without private stage creation;
- argument conflicts and operation without a current Context;
- macOS adapter command, UTF-8, and failure boundaries.

Implementation:

- [`memcommit/application/operations/list/application.py`](../../src/memcommit/application/operations/list/application.py)
- [`memcommit/application/operations/list/runtime.py`](../../src/memcommit/application/operations/list/runtime.py)
- [`memcommit/adapters/console/commands/list/command.py`](../../src/memcommit/adapters/console/commands/list/command.py)
- [`memcommit/adapters/console/clipboard.py`](../../src/memcommit/adapters/console/clipboard.py)
- [`memcommit/persistence/store/context_memory/`](../../src/memcommit/persistence/store/context_memory/)
- [`tests/test_commands.py`](../../tests/test_commands.py)
- [`tests/test_list_clipboard.py`](../../tests/test_list_clipboard.py)
- [`Root Context design rationale`](root-context-design-rationale.md)

The console package owns command grammar, clipboard I/O, and rendering.
`application.operations.list` owns readable-source authority,
command-start-stable scope freezing, and recursive materialization. This keeps
`list` as the canonical Help
operation name instead of retaining the former implementation-only
`list_memories` package name.
