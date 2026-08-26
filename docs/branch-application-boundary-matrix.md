# Branch Application Boundary Matrix

## Reviewed operation

Branch copies one exact local Context or one frozen lexical subtree into a
require-new target hierarchy, assigns fresh Context and Memory identities,
records exact ancestry, and switches current when the command-start pointer
still permits that transition.

| Current route | Application entry | Runtime/materialization | Presentation |
| --- | --- | --- | --- |
| `mem branch NAME` | `BranchRequest` → `run_branch` | `BranchStorePort` / `execute_branch` | `memcommit.commands.branch.command` |
| Interactive `mem branch` setup | Same request after frozen Source/name selection | Same runtime | Branch setup TUI then CLI receipt |
| `mem checkout -b NAME` | Delegates to `commands.branch.cmd` | Same runtime | Checkout-compatible CLI syntax |
| Direct/recursive Source range | `include_descendants` in the typed request | One exact or subtree transaction | Shared range controls |
| Undo/Redo | Recorded `branch_tree` command unit | Command-history restoration | Shared restoration receipt |

## Closure evidence

- The application plans every Source-to-target lexical mapping before Store
  materialization and rejects target collisions as a complete set.
- The runtime revalidates Source records, histories, namespace membership,
  require-new targets, and the command-start current pointer under one graph
  transaction.
- Interactive setup chooses values only; it does not create, copy, switch, or
  persist a Context before the typed request executes.
- Checkout `-b` is syntax delegation, not a separate Branch implementation.
- No Python, agent, or MCP Branch callable is currently exposed; their absence
  is not a hidden legacy route.

## Boundary and limitation

Branch follows lexical descendants, never embedded edges. Host-crash journaling
between filesystem writes remains outside the prototype; cooperative-process
CAS, exception rollback, and Undo/Redo are the reviewed boundary.
