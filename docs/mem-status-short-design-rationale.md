# Short status and Context lineage

## Problem

`mem status` is useful for inspecting recent content but too tall for a shell
orientation check. Git's `status -sb` convention is familiar, yet a Mem
Context is not a Git branch pointer and should not be mislabeled as one.

## Contract

- `mem status` retains its existing detailed output.
- `mem status -s` emits exactly one line with the canonical current Context,
  local/granted access kind, and direct visible item counts.
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
