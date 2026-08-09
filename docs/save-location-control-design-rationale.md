# Save Location control design rationale

## Motivation

Resolution workbenches already expose one independent `SAVE LOCATION` frame
between `ITEMS` and `TO DO`. The compact state is useful for confirming the
exact operation-owned destination, and direct one-line editing is necessary for
creating a name that does not exist yet. Direct editing alone, however, makes a
person remember and reproduce the service's Context namespace even when the
desired parent is already visible elsewhere in Mem.

## Interaction contract

The resting frame remains one compact exact-value row with `Enter to change`.
Enter expands the same frame and keeps focus in `EDIT DIRECTLY`, prefilled with
the current exact value. A shared Context tree is rendered above that field when
the operation supplies a frozen local Context catalog:

```text
PARENT CONTEXT · ↑/↓ MOVE · ←/→ EXPAND · ENTER USE
  ... existing local Context namespace ...
EDIT DIRECTLY · ENTER SAVES EXACT NAME
  task-1/description/atomized
```

Up or Tab from the direct field enters the tree. The tree reuses
`ContextTreeState` for cursor and expansion, `ContextSelectionState` for the
checked parent, and the common Context row renderer for geometry and escaping.
Enter explicitly chooses the cursor row as the parent, preserves the final
segment of the direct value, and returns focus to the direct field. Choosing
`practice` while editing `task-1/description/atomized`, for example, prepares
`practice/atomized`. Cursor movement alone never rewrites the draft.

The direct field remains authoritative. It starts focused, may be edited without
opening the tree, and submits the complete exact name through the operation's
existing validator. Escape from the field, or Escape/Backspace from the
read-only tree, cancels the whole edit and restores the compact frame.

## Semantic and safety boundaries

The tree is a process-local naming aid, not an authority or materialization
boundary. Opening it does not load Context records, change the current Context,
create a namespace, rename anything, or persist a preference. Atomize and Sever
still require a fresh output; symmetric Meld still interprets a changed name as
a reviewed rename. Their existing validators and their final Apply or rename
boundaries remain authoritative.

The catalog is frozen for one shell invocation and contains ordinary local
Context names supplied by the operation. A selected existing Context is treated
as a parent prefix, not silently submitted as the output itself. This avoids
offering an occupied Context as though it were a valid new Atomize or Sever
result. If the composed child collides or violates an operation rule, final
exact-name validation fails and leaves the direct editor open for correction.

The non-full-screen `save_location_review` compatibility prompt remains a direct
exact-name editor. It has no persistent prompt-toolkit frame in which to host the
tree; adopting the full-screen control there would require a separate migration,
not a second tree implementation.

## Alternatives considered

- Replacing direct input with a tree was rejected because new Context names do
  not yet exist in the catalog and exact leaf editing remains necessary.
- Updating the path on every arrow movement was rejected because browsing would
  mutate the draft and make cancellation or comparison difficult.
- Treating the selected existing Context as the complete destination was
  rejected because fresh-output operations would immediately point at occupied
  names. Parent selection plus a preserved leaf works across creation and rename
  semantics without weakening their validators.
