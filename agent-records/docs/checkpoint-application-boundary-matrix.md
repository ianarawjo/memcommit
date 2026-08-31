# Checkpoint application boundary matrix

| Concern | Owner | Boundary |
| --- | --- | --- |
| Operand grammar and text receipt | `memcommit.adapters.console.commands.history_recovery.recovery.checkpoint` | Preserves the compatibility positional grammar, captures current once, constructs a typed request, and renders the result |
| Request, plan, and result invariants | `memcommit.application.operations.history_recovery.recovery.checkpoint.application` | Distinguishes DIRECT/RECURSIVE, validates frozen member identity/digests, and requires one physical checkpoint per planned member |
| Existing-Context resolution and Store execution | `memcommit.application.operations.history_recovery.recovery.checkpoint.runtime` | Resolves the canonical root, freezes lexical membership, plans physical UIDs, and invokes one direct or atomic recursive Store primitive |
| Durable history | `memcommit.persistence.store` | Appends manual checkpoints and version-2 grouped metadata with exception rollback |

The console no longer performs direct Store checkpoint calls. Recursive
membership, atomicity, retained schema, and receipt behavior remain unchanged.

