# Context Init application boundary

## Purpose

Ordinary `mem init` was selected as the first durable-write slice after the
read-only Summarize extraction. The command already had a strong Store
transaction: one require-new Context or one missing-parent batch is created,
checkpointed, and selected under a current-Context compare-and-swap. The
problem was ownership rather than missing safety. CLI arguments, optional TUI
name input, creation planning, checkpoint policy, Store execution, and console
rendering all lived in `commands/init/command.py`.

This extraction moves the use case behind one typed application request and
result while preserving that Store transaction. Its implementation is now
owned by `memcommit.application.operations.context_init`; the former top-level application
and runtime paths remain true module aliases for compatibility. This ownership
relocation changes no request, result, validation, checkpoint, transaction,
output, or interaction behavior. A later shared naming update
reserves complete root names that have the public Memory UUID/prefix-selector
shape; it changes neither the ordinary Context schema nor checkpoint schema,
and existing legacy names remain readable.

## Call path

```text
explicit CLI name ──────────────────────────────┐
                                                │
frozen local catalog → exact-name TUI → request ├─ ContextInitRequest
                                                │          │
                                                └──────────v
                                                   application plan
                                                          │
                                                          v
                                             MemoryStoreContextInitPort
                                                          │
                                                          v
                                            atomic batch + current CAS
                                                          │
                                                          v
                                                 ContextInitResult
                                                          │
                                                          v
                                                   CLI presenter
```

`ContextInitRequest` freezes the exact name, whether missing lexical parents
may be created, and the current Context observed before optional interactive
editing. `ContextInitResult` reports the requested name, exact created Context
identities, reused parent names, and selected current name. It is process-local
typed data; it is not yet a stable public Python API.

## Responsibility matrix

| Concern | Owner after extraction | Contract |
| --- | --- | --- |
| CLI argument parsing and cancellation text | `commands/init/command.py` | No request is executed after TUI cancellation. |
| Suggested exact-name editing | `interfaces/tui/operations/context_init` over the shared Context name editor | Returns a request only; creates, loads, switches, and persists nothing. |
| Successful human-readable output | `interfaces/cli/context_init.py` | Preserves the established single and `--parents` receipts. |
| Parent-prefix expansion | `operations/context_init/application.py` | Ordered lexical prefixes end at the requested leaf. No embedded-Context relation is created. |
| Require-new versus reuse policy | `operations/context_init/application.py` | Exact mode requires the sole Context to be new; `--parents` may reuse any valid existing prefix, including the leaf. |
| Initial checkpoint arguments and descriptions | `operations/context_init/application.py` | Exact mode records `name`; parent mode additionally records `parents` and `requested_name` for every created prefix. |
| Context construction and name validation | `operations/context_init/runtime.py` over `context_naming.py` | Production uses the existing in-memory `ops.init` factory and the shared new-identity validator, including the UUID-selector reservation. |
| Locks, symlink checks, atomic batch rollback, and current CAS | `MemoryStore.create_missing_contexts` | All names remain locked through creation, rollback, and the final state write. |

## Durable invariants

1. Exact mode never reuses or overwrites an existing Context.
2. Parent mode creates only missing lexical prefixes and records reused names
   without adding checkpoints to them.
3. The requested leaf becomes current only if the current pointer still equals
   the snapshot captured before optional name editing.
4. A current-pointer race or a failure in any batch member rolls back every
   Context created by that request.
5. Each newly created Context receives the same `init` checkpoint arguments
   and description as before extraction.
6. Application and runtime execution write no stdout or stderr. Presentation
   is an adapter concern.
7. A new complete root name cannot have the eight-or-more-character canonical
   UUID-prefix shape accepted by automatic Memory operands. Nested names retain
   their slash distinction; existing legacy roots are not deleted or hidden.

## Verified evidence

The focused boundary and regression suite covers the new application tests,
the complete command suite, Store transaction tests, Context command-safety
tests, and TUI architecture tests. It includes explicit cases for
complete-hierarchy reuse and exact-name collision.
The latest combined run passed 213 tests. Targeted Ruff, `py_compile`, and
isolated MyPy checks pass for the new boundary and its adapters; whole-import
MyPy remains a repository-wide cleanup concern outside this slice.
Two broader partitions containing every test file that directly invokes
`mem init` also passed: 308 and 228 tests, for 536 adjacent-consumer tests in
total.

The test set proves:

- typed exact and parent creation plans;
- application independence from Typer, prompt-toolkit, command modules, and
  interface modules;
- runtime independence from terminal frameworks;
- terminal-free real-Store execution;
- exact checkpoint payloads for single and parent creation;
- ordered created/reused receipts;
- complete existing-hierarchy reuse;
- exact-mode collision without current or Context mutation;
- current-CAS failure with complete new-batch rollback;
- TUI request construction and cancellation without storage execution; and
- unchanged CLI success, error, cancellation, and initial-checkpoint behavior.
- UID-shaped root rejection before publication, followed by successful
  slash-qualified creation and read-only verification in an isolated Store.

The TUI still delegates to the same shared `ContextNameView` and
`choose_context_name` implementation with the same label, `NOT CREATED` state,
detail, suggestion, validator, catalog, and current marker. The later naming
rule adds one visible validation branch without changing those mechanics;
`agent-records/docs/screenshots/context-init-uid-name-reservation-20260820` records entry,
rejection, corrected input, success, and read-only verification at `180×52`.

## Study initialization is a separate operation

Ordinary `mem init` creates and selects an ordinary Context. It deliberately
does not accept `--study` or `--from-profile`: Study initialization creates a
participant/authority Profile pair, installs hidden prepared receipts, and
writes a study action ledger, so it is not another mode of Context Init.

`mem init-study` remains the sole public Study-run entry point for study
scripts, demonstrations, and recorded procedures. Keeping the commands
separate makes their resource boundary visible in both CLI discovery and
callable classification instead of presenting unrelated use cases as options
of one command.

## Remaining boundaries

- The callable is internal and requires an explicitly supplied `MemoryStore`;
  store-root ownership and public error/version contracts remain undecided.
- A machine-readable or agent adapter has not been added.
- New-Context name validation is a pure function in the shared Context naming
  module and remains invoked by the runtime adapter and Store publication
  boundaries.
- Ordinary Init has no provider or cache boundary. Sever or another semantic
  durable operation is still needed to validate those axes.
- Study initialization owns Profile-pair creation, hidden prepared receipts,
  action-ledger writes, and wider rollback behavior; it remains available only
  through the separate `mem init-study` operation.
