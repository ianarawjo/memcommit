# Switch navigation history design rationale

Last reviewed: 2026-08-25.

## Motivation

Repeatedly moving among recently used Contexts required reopening the full
picker or retyping a canonical name. `mem switch` therefore supports browser-like
back/forward traversal while preserving explicit Context selection and its
authorization and compare-and-set boundaries.

## Command contract

- `mem switch -p` and `mem switch --previous` move to the most recent back
  entry.
- `mem switch -n` and `mem switch --next` move to the most recent forward
  entry after backward traversal.
- `NAME`, `--previous`, and `--next` are mutually exclusive. Bare `mem switch`
  still opens the unchanged interactive picker.
- Direct selection after moving backward clears the forward branch. Traversal
  does not wrap at either end.
- A missing saved target or a target that is no longer READ-authorized fails
  without moving the current pointer or consuming the history entry.

The order is actual pointer-transition history, not lexical catalog order.
Creation, deletion, rename, or Grant changes can reorder a catalog even when a
person's navigation path did not change.

## State contract

`state.json` retains its existing `current` field and may additionally contain:

```json
{
  "context_navigation": {
    "version": 1,
    "back": ["context/a"],
    "forward": ["context/c"]
  }
}
```

The field is optional, so an existing state file remains valid. The first real
pointer transition creates it lazily. Each stack is bounded to 64 canonical
public names. The bound keeps a navigation convenience from becoming an
unbounded Profile activity record.

All Store-owned current-pointer transitions record through the same pure state
transition, including Init and Branch selection. A direct transition appends
the prior non-null current name and clears forward history. Previous/next pops
one exact side and pushes the prior current name onto the other. A Context
rename rewrites retained names with the same namespace mapping instead of
recording a false visit to a different identity.

## Safety and authority

The Switch application request contains exactly one lexical selector or one
typed `PREVIOUS`/`NEXT` direction. Runtime resolves the saved target, then uses
the same local/Grant READ resolution and target loading as an explicit Switch.
Local targets remain bound to UID and digest; granted targets are reauthorized
under the Grant registry lock.

Final publication still compares the command-start current pointer. For a
history traversal it also requires the requested target to remain the exact
top entry for that direction. A concurrent direct switch or traversal therefore
cannot silently consume a different navigation path.

History is navigation state, not Context history: it creates no checkpoint and
does not participate in `mem undo` or `mem redo` selection.

## Alternatives considered

- **Previous/next lexical catalog row:** rejected because catalog order changes
  with local Context and Grant membership and would not mean "go back."
- **Magic positional `-` and `+`:** rejected because both are currently valid
  Context names; reserving them would break explicit-name compatibility.
- **A Switch-only sidecar file:** rejected because Init, Branch, and other
  current-pointer transitions would make it diverge, and a second file would
  lose the atomic state replacement boundary.
- **Unbounded history:** rejected because navigation does not justify retaining
  an indefinite Profile activity trail.

## Limits

- History is local to one Profile Store and is not a cross-Profile navigation
  mechanism.
- Version 1 fails on an unavailable top entry rather than silently skipping it;
  this keeps the displayed failure and durable stack aligned. A later explicit
  prune action could adopt different reviewed semantics.
- The interactive picker is unchanged. The new flags are non-interactive CLI
  routes and do not add TUI focus, key, or rendering state.
