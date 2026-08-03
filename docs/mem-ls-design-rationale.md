# `mem ls` Design Rationale

- Status: Implemented
- Scope: the co-equal `mem list` and `mem ls` spellings, immediate namespace
  child navigation, recursive listing with `-R`, and dual text/structured
  `--copy` and `--paste`

## 1. Purpose

`mem ls` is the navigation command for a memcommit Context. It answers:

> Which materialized child Contexts can I navigate to, and what direct items
> are stored in this Context?

It does not expose memcommit's physical storage layout. The fact that a Context
is currently persisted in a `context.json` file is an implementation detail.

This distinction is similar to Git:

- the shell's `ls` lists physical filesystem entries;
- `git ls-tree` interprets Git objects and lists a logical tree;
- `mem ls` interprets a Context, derives its immediate materialized namespace
  children, and lists its logical Memory, MemoryRef, and embedded Context
  entries.

Consequently, `context.json`, `checkpoints/`, and other storage artifacts must
never be mixed into normal `mem ls` output.

## 2. Command Surface

The supported forms are:

```bash
mem list [context]
mem ls [context]
mem list -R [context]
mem ls -R [context]
mem ls --recursive [context]
mem ls [context] [-R] --copy [--with-ids]
mem ls --paste
```

`mem list` and `mem ls` are co-equal public spellings. Both forms have
identical behavior, options, implementation level, and short help
description. They share one callback internally so the two contracts cannot
drift, but the implementation detail does not make either spelling
subordinate in participant-facing documentation.

When no Context is supplied, the current Context is used.

## 3. Default Listing Is Direct, Not Recursive

Without `-R`, only immediate navigation rows and direct persisted items are
listed. A navigation row is derived for every existing ordinary Context whose
canonical name is exactly one namespace segment below the listed Context.

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
  2 items

  [context 12345678] parent/child
  [memory  abcdef12] Parent fact.
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

Therefore, `mem ls` uses the Memory's content as its human-readable name:

```text
[memory  abcdef12] The north entrance is closed until Friday.
```

The short UID remains visible because it is the selector used by commands such
as `mem show`, `mem remove`, and `mem reference`.

For compact terminal output, whitespace is normalized to one line. This
normalization affects display only; the stored content is not changed.
Whitespace-only content is displayed as `(empty)`.

## 6. Root Context Paths and Memory Content Are Separate

The following direct items can coexist in one parent Context:

```text
embedded Context name: aaa/ab
atomic Memory content: aaa
```

They are different logical types, so the listing is unambiguous:

```text
[context 12345678] aaa/ab
[memory  abcdef12] aaa
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

## 7. MemoryRef Listing

A resolved MemoryRef represents an atomic memory view, so its current target
content is also used as the human-readable name. Its source locator remains
visible to preserve reference provenance:

```text
[ref     12345678] Current target content. -> source-context#abcdef12
```

A dangling reference has no content to use as a name, so the locator is shown
with an explicit state:

```text
[ref     12345678] (dangling) source-context#abcdef12
```

Detailed reference metadata remains the responsibility of `mem show <ref-uid>`.

## 8. Recursive Listing

`-R` and `--recursive` traverse both namespace-derived children and embedded
Contexts to the deepest loaded level. Every visited Context receives the same
union view it would receive as the root of its own recursive list. The
traversal is depth-first and preserves the same Context-first rule at each
level:

```text
Context: parent
  2 items

  [context 11111111] child
    [context 22222222] grandchild
      [memory  33333333] Grandchild fact.
    [memory  44444444] Child fact.
  [memory  55555555] Parent fact.
```

An empty embedded Context is explicit:

```text
[context 11111111] child
  (no items)
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

## 10. Relationship to `mem show`

The intended conceptual split is:

- `mem ls`: compact immediate namespace navigation and one-line names for
  direct logical items;
- `mem ls -R`: recursive navigation through namespace children and embedded
  Contexts;
- `mem show <selector>`: full detail for one selected Memory, MemoryRef, or
  embedded Context.

`mem show` without a selector currently also renders all direct contents of a
Context. That existing behavior is retained for compatibility, although it
overlaps with the compact listing use case. Raw storage JSON is not the normal
output of either command; a future export or developer command would be a
better place for raw JSON.

## 11. Copy and paste as a frozen result boundary

`mem ls --copy` creates two synchronized representations of the same list
result:

1. a human-oriented text rendering is written to the macOS system clipboard;
   and
2. a versioned structured snapshot is written to the private mem store.

The default clipboard rendering omits `[kind uid]` annotations. Context names
end in `/`, query-only names end in `/ (query-only)`, and MemoryRef lines retain
their content-to-Context arrow without object UIDs. This keeps the text useful
when pasted into prose, chat, or another tool. `--copy --with-ids` instead puts
the exact unstyled indexed rendering in the clipboard, including the same
annotations shown by the normal terminal list. Ordinary command stdout remains
indexed in both modes so a copy operation does not remove the local selection
cues.

`--with-ids` is a modifier of `--copy`, not an independent list mode. Using it
without `--copy`, including with `--paste`, is rejected. The success receipt is
not part of either copied representation. Copy does not save a Context, change
the current Context, or create a checkpoint. This makes it an output action
rather than an early target mutation.

The structured half preserves full UIDs, full Memory text, MemoryRef pointer
metadata and its frozen resolved display content, embedded Context pointer
identity, QueryContextRef routing metadata, and canonical object order.
Namespace-derived rows use a distinct `namespace_context` kind so a frozen
navigation edge is never later mistaken for a persisted embed. Snapshot schema
version 2 introduces that kind; incompatible older staged list records fail
closed. Replay also verifies that each typed namespace row is exactly one
segment below its containing Context, so a validly rehashed malformed stage
cannot move an unrelated Context under that parent. Rendering reapplies the
Context-first presentation rule. A
non-recursive copy does not include the contents of a child Context. A
recursive copy stores only the traversed occurrence tree, including repeated
diamond paths and finite cycle markers.

The clean rendering is intentionally human-readable rather than parseable.
A Memory whose text resembles a Context name or reference can therefore be
textually ambiguous after annotations are omitted. No object reconstruction
depends on that text: the structured stage remains authoritative, while normal
stdout and `--with-ids` retain visible selectors when a person needs them.

Query-only source content is never opened or copied. A QueryContextRef's public
name and local routing metadata can be staged because they are already part of
the parent Context record, but the concealed source text is outside this
clipboard contract.

`mem ls --paste` is a read-only consumer of a structured list snapshot. It
replays the frozen list in the clean or annotated form selected by the
producing copy, even if its source Context has since changed or been deleted.
It can therefore run without a current Context. A positional Context and `-R`
are rejected with `--paste`: the source and traversal depth were fixed by the
producing copy. `--copy --paste` is also rejected rather than silently
overwriting its own input.

The structured record stores SHA-256 digests of both the exact
system-clipboard text and a canonical serialization of the structured
selection. Paste rereads the clipboard and accepts the object snapshot only
when its text, text digest, selection digest, and one of the two permitted
renderings of the snapshot agree. This detects corruption of non-rendered
identity and routing fields as well as visible content without storing a
second presentation flag.

A dedicated inter-process lock spans each complete copy transaction and each
stage-plus-clipboard validation. Copy invalidates the previous structured
record before writing either new half; a failed replacement therefore cannot
reactivate an older object selection that happens to render the same text or
delete another concurrent copy's newer stage. Arbitrary external clipboard
text is not guessed into Memory objects.

This content-equivalence check cannot distinguish an external overwrite whose
bytes are exactly identical to the copied text. A platform-specific clipboard
change token or custom MIME type could tighten that boundary later, but the
prototype intentionally uses dependency-free `/usr/bin/pbcopy` and
`/usr/bin/pbpaste` on macOS.

The word `--paste` remains command-local. Existing `mem add --paste` is the
interactive bracketed-paste intake flow described in
[`mem-add-paste-design-rationale.md`](mem-add-paste-design-rationale.md); it
does not silently switch to structured clipboard consumption. General
`show/find/add --paste` inputs and actual materialization of staged objects
need their own command contracts.

## 12. Deliberate Non-Goals

This change does not:

- add a title field to Memory;
- change the persisted item order;
- persist namespace navigation rows as automatic embeds or logical
  parent-child relationships;
- recursively expand children without `-R`;
- expose raw `context.json` data;
- change the behavior of `mem show`;
- automatically embed a path descendant into a Root Context;
- paste staged objects into a Context or choose new UIDs;
- add structured `--copy` or `--paste` to `show`, `find`, or other commands;
- support non-macOS system clipboards.

The current prototype discovers children by validating the complete ordinary
Context catalog once per invocation. Listing cost therefore grows with the
number of stored Contexts, even though each recursive level filters that frozen
catalog in memory. A future indexed or namespace-local catalog can improve
large-store performance without changing the visible contract.

## 13. Validation Scenarios

The implementation is covered by tests for:

- content-as-name for direct Memory entries;
- Context-first rendering when a Memory was inserted first;
- `aaa/ab` Context and `aaa` Memory content coexisting without ambiguity;
- relative ordering of Memory and MemoryRef entries;
- default listing not leaking child content;
- sorted immediate namespace children alongside current direct Memories;
- no synthesized child when an intermediate Context is missing;
- namespace recursion and explicit-embed deduplication;
- relative existing-Context locators such as `mem ls ../sibling`;
- recursion through two or more Context levels;
- parity among `list -R`, `ls -R`, and `ls --recursive`;
- finite output for an indirect persisted cycle;
- repeated traversal of a shared Context along both sides of a diamond;
- resolved MemoryRef content and provenance;
- existing non-recursive list and embed behavior;
- clean-by-default and `--with-ids` text/structured dual copy for both
  `list` and `ls`;
- embedded Context, namespace Context, query-only, MemoryRef, and recursive
  clean rendering;
- rejection of `--with-ids` outside `--copy`;
- frozen direct and recursive snapshot replay after source mutation/deletion;
- query-only source non-disclosure;
- stale, missing, corrupt, and failed clipboard states;
- argument conflicts and operation without a current Context;
- macOS adapter command, UTF-8, and failure boundaries.

Implementation:

- [`memcommit/commands/list_memories.py`](../memcommit/commands/list_memories.py)
- [`memcommit/clipboard.py`](../memcommit/clipboard.py)
- [`memcommit/store.py`](../memcommit/store.py)
- [`tests/test_commands.py`](../tests/test_commands.py)
- [`tests/test_list_clipboard.py`](../tests/test_list_clipboard.py)
- [`Root Context design rationale`](root-context-design-rationale.md)
