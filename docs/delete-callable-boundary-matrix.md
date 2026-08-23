# Delete callable and effect boundary matrix

Last verified: 2026-08-22.

## Scope

`delete` is one Help operation with two deliberately different durable effects.
`mem delete` and `mem remove` remain complete CLI aliases; this review does not
rename either spelling or split their selector grammar. It moves both effects
behind the same terminal-independent operation package while retaining their
different approval, receipt, and recovery contracts.

## Callable ownership

| Callable | Owner | Input → output | Allowed effects | Required invariant | State |
| --- | --- | --- | --- | --- | --- |
| `delete_application.run_direct_item_delete` | application | selector + frozen runtime → `DirectItemDeleteResult` | delegates exactly one authorized mutation | full item UID is frozen before mutation; complete receipt names one checkpoint | `VERIFIED` |
| `delete_application.prepare_context_delete` | application | existing Context locator + runtime → `FrozenContextDeletePlan` | target identity and record read only | canonical name, UID, record digest, irreversible effects, and plan digest form one review identity | `VERIFIED` |
| `delete_application.apply_context_delete` | application | reviewed plan + owning runtime → `ContextDeleteResult` | delegates one exact permanent deletion | approval is not a boolean application input; Apply consumes the reviewed exact identity or fails stale | `VERIFIED` |
| `delete_runtime.MemoryStoreDeletePort.freeze_item` | infrastructure | direct-item selector → authorized frozen target | Store/Profile/Grant reads | one command-start current snapshot; local or DELETE-granted owner; ambiguous selector fails closed | `VERIFIED` |
| `delete_runtime.MemoryStoreDeletePort.remove_item` | infrastructure | frozen item → checkpointed result | one authorized Context save and `remove` checkpoint | full UID, owner UID/digest, Grant revision, protection, and Store CAS remain valid through save | `VERIFIED` |
| `delete_runtime.MemoryStoreDeletePort.freeze_context` | infrastructure | ordinary local locator → frozen plan | local Store read | relative locator resolves once; a Grant never authorizes deletion of the authority Context | `VERIFIED` |
| `delete_runtime.MemoryStoreDeletePort.delete_context` | infrastructure | frozen plan → lifecycle result | exact Context/history deletion, artifact cleanup, Profile lifecycle event | `delete_context_if` compares name, UID, and digest; descendants survive; committed cleanup failure returns a non-retryable committed receipt | `VERIFIED` |
| `interfaces.cli.delete` | CLI adapter | typed plan/result → warning or terminal receipt | stdout/stderr only | human warning lists every irreversible effect; a committed cleanup warning still says deletion happened | `VERIFIED` |
| `interfaces.tui.operations.delete` | TUI adapter | frozen local catalog + typed callback → picker receipt | terminal interaction and process-local focus only | display text is never re-parsed as a target; shared picker owns navigation mechanics | `VERIFIED` |
| `commands.delete.cmd` | console composition | argv/TTY → application request and presentation | interface intake, optional human confirmation, application effects | one current snapshot; `--force` skips only the human Context confirmation; item removal never adds a second prompt | `VERIFIED` |
| `commands.remove.cmd` | compatibility facade | alias dispatch → canonical command composition | none independently | contains no behavior and preserves complete command parity | `VERIFIED` |
| `api.client.MemCommitClient.remove_item` | public Python facade | exact selector + optional owner → immutable receipt | same checkpointed application mutation | stable typed error and no terminal import | `VERIFIED` |
| `api.client.MemCommitClient.plan_context_delete` / `apply_context_delete` | public Python facade | Context locator → reviewed plan → lifecycle receipt | read-only plan, then exact permanent Apply | plan is client-bound and tamper-evident; caller chooses when to Apply | `VERIFIED` |
| `interfaces.agent.delete.DeleteAgentAdapter` | agent adapter | three strict version-1 JSON contracts → bounded envelopes | read-only plan, checkpointed item removal, or permanent Context delete | apply re-freezes the target and requires the exact prior plan digest; no automatic mutation retry | `VERIFIED` |
| default Agent registry bindings | agent registry | public Help guidance + schema + handler + effect hints → frozen definitions | discovery only | item removal is mutable/non-destructive, plan is read-only, Context Apply is destructive | `VERIFIED` |
| `McpRegistryProjection` | MCP adapter | frozen definitions → MCP Tools | none during discovery; calls delegate once | standard annotations preserve the three effect classes so the host can approve only the destructive call | `VERIFIED` |

## Route and effect matrix

| Route | Review/approval owner | Durable success | Undo/retry contract |
| --- | --- | --- | --- |
| explicit CLI direct item | none beyond invocation | item removed and one `remove` checkpoint | Undoable; no y/N prompt |
| picker direct item | Enter on exact row | same checkpointed removal per Enter | each accepted row is independently Undoable |
| explicit or picker Context in human CLI | CLI prints exact frozen effects and asks `Continue? [y/N]`, unless `--force` | Context record/history deleted; matching artifacts cleaned; lifecycle event retained | not Undoable; stale plan must be reselected; committed cleanup warning must not be retried as if deletion failed |
| public Python item | caller invokes `remove_item` | same checkpointed removal | typed `undoable=True` receipt |
| public Python Context | caller reviews plan object and separately invokes Apply | same exact permanent deletion | typed `undoable=False` lifecycle receipt |
| agent/MCP item | host normal mutable-tool policy | same checkpointed removal | `destructiveHint=false`; no implicit retry |
| agent/MCP Context | read-only plan first; host policy approves the separately exposed destructive Apply tool | same exact permanent deletion | `destructiveHint=true`; expected digest prevents approval retargeting |

An MCP server does not read stdin or emit its own y/N prompt. The host decides
whether to ask the person based on tool annotations and its configured approval
policy. A host running in full-access or approval-never mode may intentionally
skip that prompt; the application still enforces exact identity/digest review,
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

This slice does not make Context deletion checkpoint-restorable, group a picker
session into one Undo unit, permit authority-Context destruction through a
Grant, or reinterpret `delete` and `remove` as different operations. A future
cross-operation approval abstraction should be extracted only after another
destructive operation demonstrates the same plan/Apply and host-annotation
meaning.
