# Context Init application boundary

## Purpose

Ordinary `mem init` was selected as the first durable-write slice after the
read-only Summarize extraction. The command already had a strong Store
transaction: one require-new Context or one missing-parent batch is created,
checkpointed, and selected under a current-Context compare-and-swap. The
problem was ownership rather than missing safety. CLI arguments, optional TUI
name input, creation planning, checkpoint policy, Store execution, and console
rendering all lived in `commands/init.py`.

This extraction moves the use case behind one typed application request and
result while preserving that Store transaction. It does not change the
ordinary Context schema, checkpoint schema, name grammar, CLI text, or terminal
name editor.

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
| CLI argument parsing and cancellation text | `commands/init.py` | No request is executed after TUI cancellation. |
| Suggested exact-name editing | `interfaces/tui/operations/context_init` over the shared Context name editor | Returns a request only; creates, loads, switches, and persists nothing. |
| Successful human-readable output | `interfaces/cli/context_init.py` | Preserves the established single and `--parents` receipts. |
| Parent-prefix expansion | `context_init_application.py` | Ordered lexical prefixes end at the requested leaf. No embedded-Context relation is created. |
| Require-new versus reuse policy | `context_init_application.py` | Exact mode requires the sole Context to be new; `--parents` may reuse any valid existing prefix, including the leaf. |
| Initial checkpoint arguments and descriptions | `context_init_application.py` | Exact mode records `name`; parent mode additionally records `parents` and `requested_name` for every created prefix. |
| Context construction and name validation | `context_init_runtime.py` | Production uses the existing in-memory `ops.init` factory and ordinary Store name validator. |
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

The TUI still delegates to the same shared `ContextNameView` and
`choose_context_name` implementation with the same label, `NOT CREATED` state,
detail, suggestion, validator, catalog, and current marker. No visible or
interaction-semantic TUI change was introduced, so the prior flow remains the
visual contract and no replacement screenshot set was generated for this
structural extraction.

## Study routing and command compatibility

`mem init --study` is a console-level route to the existing Study Init use
case. The positional name becomes the Study Profile name and
`--from-profile` keeps its established Study-baseline meaning. The historical
`mem init-study` command remains public for study scripts, demonstrations, and
recorded procedures. Both spellings execute `commands/init_study.py`; the new
route does not copy Profile-pair creation, hidden prepared-receipt, or action
ledger behavior into ordinary Context Init.

This routing intentionally occurs before constructing an ordinary
`MemoryStore` or taking a Context snapshot. Consequently Study mode cannot
create or switch an ordinary Context as an accidental side effect.
`--parents` remains exclusive to ordinary Context Init and fails when combined
with `--study`. Conversely, `--from-profile` fails without `--study`, rather
than being silently ignored.

Verification covers both a spy-level routing contract and a real initialized
Study bundle. The latter proves that `mem init NAME --study` publishes the
participant and granted-memory Profiles through the established path with one
shared Study UID. Thirteen existing `init-study` regression cases and the
hidden-prewarm initialization test also pass unchanged, preserving the old
spelling and its durable behavior.

The shared Study implementation is still a command-owned use case. Moving it
behind its own typed application/runtime boundary remains later work; command
unification is not evidence that Context Init and Study Init share a domain
request.

## Remaining boundaries

- The callable is internal and requires an explicitly supplied `MemoryStore`;
  store-root ownership and public error/version contracts remain undecided.
- A machine-readable or agent adapter has not been added.
- New-Context name validation remains a pure function physically owned by the
  Store module. It stays in the runtime adapter until a broader Context-domain
  extraction proves a better common owner.
- Ordinary Init has no provider or cache boundary. Sever or another semantic
  durable operation is still needed to validate those axes.
- Study initialization owns Profile-pair creation, hidden prepared receipts,
  action-ledger writes, and wider rollback behavior; it must remain a separate
  use case even if the console spelling moves under `mem init --study`.
