# Historical full-height `mem branch` subtree TTY capture log

This set is retained as the pre-migration visual baseline for the former
persistent A/B tree workbench. It no longer describes the current bare Branch
surface. The refreshed compact interaction, exact Apply review, success
receipt, and collision-safety verification are recorded in
[`../mem-branch-compact-20260822/README.md`](../mem-branch-compact-20260822/README.md).

These images record a real 180-by-52 PTY run against the Task 1 study fixture.
They are terminal-state captures rendered at 2572 pixels wide so that the full
Branch workbench remains readable without cropping.

## Scenario

- Study profile: `study-alt-20260810-t1-branch-local`
- Source root: `task-1/participant/construction-updates`
- Source shape: 1 root plus 6 lexical descendants containing 75 Memories
- Successful subtree destination: `captures/task1-subtree-20260810`
- Collision destination: `captures/task1-conflict-20260810`
- Exact/shallow comparison destination: `captures/task1-exact-20260810`

## Successful subtree interaction

Starting from `mem branch`:

1. Select `task-1/participant/construction-updates` in `A · FROM CONTEXT`.
2. Press `Tab` to focus `RANGE`.
3. Press `Right` to select `INCLUDE DESCENDANTS`.
4. Press `Tab` to focus `B · TO · NEW CONTEXT`.
5. Move to `EXACT NEW CONTEXT NAME`, replace the default with
   `captures/task1-subtree-20260810`, and press `Enter`.
6. Press `Enter` on `APPLY`.

The command reported 7 newly branched Contexts and 6 descendants. A read-only
verification then found all 75 Memories and confirmed that all 6 root embedded
Context links point at the cloned descendants by both name and UID.

## Descendant collision interaction

The same sequence was repeated with `captures/task1-conflict-20260810` after
creating only its `building-access` child. Apply failed before publication with
the exact child collision. Verification found no new destination root, retained
the pre-existing child and its marker Memory, and left the current Context at
the source. This demonstrates that the subtree is published as one atomic unit.

## Exact/shallow comparison

The successful sequence was repeated with `THIS CONTEXT ONLY` selected and
`captures/task1-exact-20260810` as the destination. It created only the root
Context. No lexical descendants were copied, and the root's 6 embedded Context
links intentionally still point to their original source names and UIDs.

## Captures

1. `01-source-selection.png` — source hierarchy and root selection
2. `02-exact-scope.png` — compatibility default, `THIS CONTEXT ONLY`
3. `03-subtree-scope.png` — explicit `INCLUDE DESCENDANTS`
4. `04-destination-name.png` — exact destination-name entry
5. `05-apply-review.png` — final Apply review
6. `06-subtree-success-receipt.png` — successful command receipt
7. `07-subtree-result.png` — cloned hierarchy and aggregate verification
8. `08-descendant-collision.png` — atomic preflight failure
9. `09-exact-result.png` — exact/shallow behavior for comparison

The operating environment denied GUI automation access to Terminal.app, so the
captures come from the same real PTY byte stream used for the interaction rather
than from a synthetic UI fixture. The header added above each capture records
that provenance and the terminal dimensions.
