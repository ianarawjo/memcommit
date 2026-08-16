# Short status and Context lineage

## Problem

`mem status` is useful for inspecting recent content but too tall for a shell
orientation check. Git's `status -sb` convention is familiar, yet a Mem
Context is not a Git branch pointer and should not be mislabeled as one.

## Contract

- `mem status` and `mem status -d` retain the existing detailed, current-only
  output. Direct remains the compatibility default.
- `mem status -r` keeps that current-Context detail and adds a recursive total
  plus one direct-count row per readable lexical descendant or embedded
  Context. It does not repeat descendant Memory bodies; `mem ls -r` remains the
  content-oriented expansion.
- `mem status -s` emits exactly one line with the canonical current Context,
  local/granted access kind, and direct visible item counts.
- `mem status -sr` emits the same compact line for every Context in the
  recursive scope. Each row retains direct counts so a parent with zero direct
  Memories cannot conceal populated children or imply that their Memories are
  physically owned by the parent.
- `mem status -b` adds the active Profile and a `>`-separated rendering of the
  Context namespace lineage to the detailed view.
- `mem status -sb` combines both flags into one Git-like `##` orientation line:
  `Profile :: Context lineage [access] · counts`.

The `b` flag means branch-style orientation, not that Mem serializes a Context
as a Git branch. Profile identifies the store boundary; the Context namespace
is shown as lineage because each slash-separated prefix is the navigational
ancestry relevant to the current Memory workspace.

Granted short status shows the short grant identity and revision but not its
full capability set. `mem ls` remains the detailed permission-boundary surface.
The short counts use the same projected READ view as detailed status, and
authority checkpoints remain hidden from granted views.

Recursive status freezes one `ReadableContextCatalog` at command start. The
shared scope preset expands canonical public-name descendants and follows
explicit embedded-Context edges as independent axes. Context UID
de-duplication prevents a Context that is both a namespace descendant and an
embed from being counted twice, and Grant attachment metadata never becomes a
hierarchy edge. Query-only routes may contribute opaque `Query Views` counts
but their concealed source content is never opened.
