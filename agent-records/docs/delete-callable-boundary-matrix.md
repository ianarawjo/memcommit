# Delete callable and effect boundary matrix

Last verified: 2026-08-24.

## Scope

`delete` is one Help operation with two deliberately different durable effects.
`mem delete` and `mem remove` remain complete CLI aliases; this review does not
rename either spelling or split their selector grammar. It moves both effects
behind the same terminal-independent operation package while retaining their
different approval, receipt, and recovery contracts.

Delete's console-specific adapters are co-located under
`memcommit.adapters.console.commands.direct_changes.delete`: `command.py` owns orchestration,
`review.py` owns the irreversible Context warning, `receipt.py` owns direct-item
and Context success projections, and `picker.py` owns the operation-specific
composition over the shared Context/Memory picker. The former
`interfaces/cli/delete.py` and `interfaces/tui/operations/delete.py` paths are
removed without compatibility facades. This is an ownership relocation only;
selector resolution, approval, mutation, receipt text, picker behavior, and
existing PTY evidence are unchanged.

## Callable ownership

| Callable | Owner | Input → output | Allowed effects | Required invariant | State |
| --- | --- | --- | --- | --- | --- |
| `memcommit.application.operations.direct_changes.delete.application.run_direct_item_delete` | application | selector + frozen runtime → `DirectItemDeleteResult` | delegates exactly one authorized mutation | full item UID is frozen before mutation; complete receipt names one checkpoint | `VERIFIED` |
| `memcommit.application.operations.direct_changes.delete.application.prepare_context_delete` | application | existing Context locator + runtime → `FrozenContextDeletePlan` | target identity and record read only | canonical name, UID, record digest, irreversible effects, and plan digest form one review identity | `VERIFIED` |
| `memcommit.application.operations.direct_changes.delete.application.apply_context_delete` | application | reviewed plan + owning runtime → `ContextDeleteResult` | delegates one exact permanent deletion | approval is not a boolean application input; Apply consumes the reviewed exact identity or fails stale | `VERIFIED` |
| `memcommit.application.capabilities.local_target_lookup.resolve_local_direct_item_locator` | shared targeting | bare or qualified local UID selector → exact `DirectItemTarget` | strict ordinary-local direct-record reads | bare lookup has no Current priority; exactly one direct owner coordinate; no nested, snapshot, or Grant content | `VERIFIED` |
| `memcommit.application.operations.direct_changes.delete.runtime.MemoryStoreDeletePort.freeze_item` | infrastructure | direct-item selector → authorized frozen target | Store/Profile/Grant reads | bare local UID and picker paths converge on one exact shared coordinate; ambiguity fails closed; explicit Grant owners retain DELETE authorization | `VERIFIED` |
| `memcommit.application.operations.direct_changes.delete.runtime.MemoryStoreDeletePort.remove_item` | infrastructure | frozen item → checkpointed result | one authorized Context save and `remove` checkpoint | full UID, owner UID/digest, Grant revision, protection, and Store CAS remain valid through save | `VERIFIED` |
| `memcommit.application.operations.direct_changes.delete.runtime.MemoryStoreDeletePort.freeze_context` | infrastructure | ordinary local locator → frozen plan | local Store read | relative locator resolves once; a Grant never authorizes deletion of the authority Context | `VERIFIED` |
| `memcommit.application.operations.direct_changes.delete.runtime.MemoryStoreDeletePort.delete_context` | infrastructure | frozen plan → lifecycle result | exact Context/history deletion, artifact cleanup, Profile lifecycle event | `delete_context_if` compares name, UID, and digest; descendants survive; committed cleanup failure returns a non-retryable committed receipt | `VERIFIED` |
| `commands.delete.review` / `commands.delete.receipt` | console presentation | typed plan/result → warning or terminal receipt | stdout/stderr only | human warning lists every irreversible effect; a committed cleanup warning still says deletion happened | `VERIFIED` |
| `commands.delete.picker` | console picker composition | frozen local catalog + typed callback → picker receipt | terminal interaction and process-local focus only | display text is never re-parsed as a target; shared picker owns navigation mechanics | `VERIFIED` |
| `commands.delete.cmd` | console composition | variadic argv/TTY → ordered application requests and presentation | interface intake, optional shared human confirmation, independently committed application effects | every selector is frozen before Apply; one current snapshot resolves every relative Context spelling; duplicates and owner/child overlap fail before mutation; `--force` skips only the human Context confirmation | `VERIFIED` |
| `commands.remove.cmd` | compatibility facade | alias dispatch → canonical command composition | none independently | contains no behavior and preserves complete command parity | `VERIFIED` |
| `api.client.MemCommitClient.remove_item` | public Python facade | exact selector + optional owner → immutable receipt | same checkpointed application mutation | stable typed error and no terminal import | `VERIFIED` |
| `api.client.MemCommitClient.plan_context_delete` / `apply_context_delete` | public Python facade | Context locator → reviewed plan → lifecycle receipt | read-only plan, then exact permanent Apply | plan is client-bound and tamper-evident; caller chooses when to Apply | `VERIFIED` |
| `adapters.agent.delete.DeleteAgentAdapter` | agent adapter | three strict version-1 JSON contracts → bounded envelopes | read-only plan, checkpointed item removal, or permanent Context delete | apply re-freezes the target and requires the exact prior plan digest; no automatic mutation retry | `VERIFIED` |
| default Agent registry bindings | agent registry | public Help guidance + schema + handler + effect hints → frozen definitions | discovery only | item removal is mutable/non-destructive, plan is read-only, Context Apply is destructive | `VERIFIED` |

## Route and effect matrix

| Route | Review/approval owner | Durable success | Undo/retry contract |
| --- | --- | --- | --- |
| explicit CLI direct item batch | none beyond invocation | each item removed in argv order with one `remove` checkpoint | independently Undoable in reverse order; no y/N prompt |
| picker direct item | Enter on exact row | same checkpointed removal per Enter | each accepted row is independently Undoable |
| explicit mixed/Context batch in human CLI | CLI freezes the complete target set, prints every Context's exact effects, and asks once `Continue? [y/N]`, unless `--force` | effects apply in argv order; each Context record/history is deleted, matching artifacts cleaned, and one lifecycle event retained | each Context is not Undoable; batch is not atomic; stale pre-Apply revalidation publishes nothing, while a later Apply failure retains earlier truthful receipts |
| picker Context in human CLI | CLI prints one exact frozen effect and asks `Continue? [y/N]`, unless `--force` | Context record/history deleted; matching artifacts cleaned; lifecycle event retained | not Undoable; stale plan must be reselected; committed cleanup warning must not be retried as if deletion failed |
| public Python item | caller invokes `remove_item` | same checkpointed removal | typed `undoable=True` receipt |
| public Python Context | caller reviews plan object and separately invokes Apply | same exact permanent deletion | typed `undoable=False` lifecycle receipt |
| agent item | host normal mutable-tool policy | same checkpointed removal | host-neutral `destructive=false`; no implicit retry |
| agent Context | read-only plan first; host policy approves the separately exposed destructive Apply tool | same exact permanent deletion | host-neutral `destructive=true`; expected digest prevents approval retargeting |

An embedding host decides whether to ask the person based on the registry's
effect hints and its configured approval policy. A host may intentionally skip
that prompt; the application still enforces exact identity/digest review,
authority, write protection, and Store CAS, but it cannot override the host's
chosen approval policy.

## Failure and partial-commit boundary

Direct-item publication is a normal Context CAS and exposes no success receipt
without its checkpoint. Context deletion has a narrower unavoidable boundary:
the primary record, history, and lifecycle event can commit before ancillary
artifact cleanup finishes. `ContextDeletionCommittedError` is therefore
projected as `APPLIED_WITH_CLEANUP_WARNING`, not as an ordinary retryable
failure. The human CLI retains its historical nonzero exit status for operator
attention; public and agent adapters return a success-shaped committed receipt
so automation cannot blindly repeat a deletion that already happened.

## Dependencies and non-goals

The dependency direction is CLI/TUI/public/agent → application → runtime →
domain/Store. Application and runtime import no Typer, prompt-toolkit, command,
or interface module. The public facade does not call the CLI, and the
application does not call the public facade.

The implementation is owned by `memcommit.application.operations.direct_changes.delete.application` and
`memcommit.application.operations.direct_changes.delete.runtime`. The former top-level module paths are
intentionally unavailable after the repository-wide historical Python import
cleanup; internal callers and monkeypatch targets use these canonical owners.

This slice does not make Context deletion checkpoint-restorable, group a picker
session or variadic argv batch into one atomic Undo unit, permit
authority-Context destruction through a Grant, or reinterpret `delete` and
`remove` as different operations. A future
cross-operation approval abstraction should be extracted only after another
destructive operation demonstrates the same plan/Apply and host-annotation
meaning.
