# `mem ls` Design Rationale

- Status: Implemented
- Scope: the co-equal `mem list` and `mem ls` spellings, recursive listing
  with `-R`, and dual text/structured `--copy` and `--paste`

## 1. Purpose

`mem ls` is the navigation command for the logical contents of a memcommit
Context. It answers:

> What are the direct items in this Context?

It does not expose memcommit's physical storage layout. The fact that a Context
is currently persisted in a `context.json` file is an implementation detail.

This distinction is similar to Git:

- the shell's `ls` lists physical filesystem entries;
- `git ls-tree` interprets Git objects and lists a logical tree;
- `mem ls` interprets a Context and lists logical Memory, MemoryRef, and
  embedded Context entries.

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
mem ls [context] [-R] --copy
mem ls --paste
```

`mem list` and `mem ls` are co-equal public spellings. Both forms have
identical behavior, options, implementation level, and short help
description. They share one callback internally so the two contracts cannot
drift, but the implementation detail does not make either spelling
subordinate in participant-facing documentation.

When no Context is supplied, the current Context is used.

## 3. Default Listing Is Direct, Not Recursive

Without `-R`, only direct items are listed.

Given:

```text
parent
├── embedded Context: child
│   └── Memory: Child fact.
└── Memory: Parent fact.
```

the default result is:

```text
Context: parent
  2 items

  [context 12345678] child
  [memory  abcdef12] Parent fact.
```

`Child fact.` is intentionally absent. This follows the normal directory
navigation model: listing a directory shows the child directory entry, not all
of that child's descendants.

The child can be inspected explicitly:

```bash
mem ls child
```

or recursively:

```bash
mem ls -R parent
```

## 4. Contexts Are Displayed Before Atomic Information

A Context behaves like a logical directory, so direct embedded Contexts are
displayed before direct Memory and MemoryRef entries.

This grouping is a presentation rule only. It does not rewrite the Context's
persisted `order` field.

Within each group:

- embedded Contexts retain their relative Context order;
- Memory and MemoryRef entries retain their relative information order.

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

Path coexistence does not create a logical parent-child relationship. The
descendant appears in `mem ls aaa` only after it has been explicitly embedded
in the Root Context. A Memory whose content is `aaa` is independent of both
Context paths.

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

`-R` and `--recursive` traverse embedded Contexts to the deepest loaded level.
The traversal is depth-first and preserves the same Context-first rule at each
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

### Embedded graph, not slash namespace

Recursive listing follows explicit embedded Context references. It does not
scan every stored Context whose name happens to share a slash prefix.

For example, the existence of both:

```text
construction-updates
construction-updates/building-access
```

does not by itself make `building-access` a child of `main`. It appears below
the `construction-updates` Root Context only after it has been explicitly
embedded.

This prevents physical naming conventions from silently changing logical
Context membership.

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

- `mem ls`: compact navigation and one-line names for direct logical items;
- `mem ls -R`: recursive navigation through embedded Contexts;
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

1. the exact unstyled text printed by `mem ls` is written to the macOS system
   clipboard; and
2. a versioned structured snapshot is written to the private mem store.

The success receipt is not part of the copied text. Copy does not save a
Context, change the current Context, or create a checkpoint. This makes it an
output action rather than an early target mutation.

The structured half preserves full UIDs, full Memory text, MemoryRef pointer
metadata and its frozen resolved display content, embedded Context pointer
identity, QueryContextRef routing metadata, and canonical object order.
Rendering reapplies the Context-first presentation rule. A non-recursive copy
does not include the contents of an embedded Context. A recursive copy stores
only the traversed occurrence tree, including repeated diamond paths and
finite cycle markers.

Query-only source content is never opened or copied. A QueryContextRef's public
name and local routing metadata can be staged because they are already part of
the parent Context record, but the concealed source text is outside this
clipboard contract.

`mem ls --paste` is a read-only consumer of a structured list snapshot. It
replays the frozen list even if its source Context has since changed or been
deleted, and it can therefore run without a current Context. A positional
Context and `-R` are rejected with `--paste`: the source and traversal depth
were fixed by the producing copy. `--copy --paste` is also rejected rather than
silently overwriting its own input.

The structured record stores SHA-256 digests of both the exact
system-clipboard text and a canonical serialization of the structured
selection. Paste rereads the clipboard and accepts the object snapshot only
when its text, text digest, selection digest, and rendered snapshot agree.
This detects corruption of non-rendered identity and routing fields as well as
visible content.

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
- turn slash namespace prefixes into automatic parent-child relationships;
- recursively expand children without `-R`;
- expose raw `context.json` data;
- change the behavior of `mem show`;
- automatically embed a path descendant into a Root Context;
- paste staged objects into a Context or choose new UIDs;
- add structured `--copy` or `--paste` to `show`, `find`, or other commands;
- support non-macOS system clipboards.

## 13. Validation Scenarios

The implementation is covered by tests for:

- content-as-name for direct Memory entries;
- Context-first rendering when a Memory was inserted first;
- `aaa/ab` Context and `aaa` Memory content coexisting without ambiguity;
- relative ordering of Memory and MemoryRef entries;
- default listing not leaking child content;
- recursion through two or more Context levels;
- parity among `list -R`, `ls -R`, and `ls --recursive`;
- finite output for an indirect persisted cycle;
- repeated traversal of a shared Context along both sides of a diamond;
- resolved MemoryRef content and provenance;
- existing non-recursive list and embed behavior;
- exact text/structured dual copy for both `list` and `ls`;
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
