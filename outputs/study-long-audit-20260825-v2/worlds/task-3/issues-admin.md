# task-3 ADMIN findings

## T3V2-RENAME-BRANCH-STACK-OWNER-MISMATCH · P1

Renaming B1 changed the checkpoint owner name without changing its creation membership. Exact inverse Rename restored the B2 stack and allowed Undo2/Redo2.

## T3V2-BRANCH-INHERITS-CREATION-RECEIPT · P1

Branching B1 into B3 and then co3 copied historical Branch creation receipts into new owners. Six later Undo/Redo calls failed closed; the malformed audit Contexts remain as a negative control.

## Audit limitations

- Checkout M5 was interrupted after invocation and retained once as exit 130.
- UUID-shaped Study names are valid; the M5 negative control created a full Study. The new Profile/Store remain intact and only active_uid was restored.
- Context Import M1/M2 collided with identities already present in the combined Store.
- Recovery adapted Rename/Lock targets while retaining 21×5 counted calls.
- Init without --parents correctly created only the exact nested leaf; the protocol's expected missing-parent failure was an input assumption.
