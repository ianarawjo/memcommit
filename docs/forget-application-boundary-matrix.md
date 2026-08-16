# Forget application-boundary matrix

Last reviewed: 2026-08-16.

## Status

`MIGRATING` while public and interface adapters are completed. The semantic,
review, authority, freshness, and Apply owners are terminal-independent and
the existing command route enters them.

## Motivation

Forget already shared a strict whole-frame selective-curation decoder with
Sever, and its immutable review model was independent of the terminal. The
complete operation nevertheless existed only in `commands/forget.py`: that
module selected the provider, initiated semantic analysis, interpreted review
actions, calculated mutation permissions, edited the Source, and created the
checkpoint. A non-terminal caller therefore had to invoke command behavior or
reimplement the most safety-sensitive part of the operation.

The extracted lifecycle is:

```text
Context locator + instruction
          |
          v
ForgetAnalysisRequest
          |
          v
MemoryStoreForgetSourcePort.freeze
  READ/Grant resolution + complete direct Source
          |
          v
run_forget_analysis
  one whole-frame provider turn
          |
          v
ForgetSessionSnapshot
  process-local review + opaque version
      |              |
      | select       | provider feedback
      v              v
run_forget_selection / run_forget_revision
          |
          v
run_forget_apply
  explicit no-op, or authority + Source CAS + one checkpoint
```

## Boundary matrix

| Concern | Application owner | Production adapter | Invariant |
| --- | --- | --- | --- |
| Input | `ForgetAnalysisRequest` | CLI setup or Python adapter | One canonical direct Source and one nonblank instruction |
| Source freeze | `ForgetSourcePort` | `MemoryStoreForgetSourcePort` | READ/Grant resolution and complete direct loading finish before provider construction |
| Semantic analysis | `run_forget_analysis` | `forget_provider` plus injected provider factory | The complete Source and instruction run in one bounded provider turn; no hidden partitioning |
| Decoder | `forget_provider` and shared `selective_curation` | none | Exactly one KEEP/TRANSFORM/DROP disposition per direct Source Memory |
| Review | `ForgetReview` inside `ForgetSessionSnapshot` | interface projection only | Review changes are immutable and retain every Source Memory, including KEEP |
| Review version | `forget_snapshot_version` | none | Selection and provider revision return a new opaque version under the same process-local review UID |
| Provider revision | `run_forget_revision` | injected provider factory | The original frozen Source, instruction, and role-ordered dialogue are reused as one whole frame |
| No-op | `run_forget_apply` | none | An all-KEEP accepted review creates no checkpoint and does not enter mutation authority |
| Apply | `run_forget_apply` | `MemoryStoreForgetSourcePort.apply` | Only sparse reviewed edits/removals enter the exact frozen Source mutation boundary |
| Authority | runtime adapter | `authorized_context_mutation` | Local writes use Context CAS; granted writes retain required UPDATE/DELETE permissions through the authority save |
| Receipt | `ForgetApplyReceipt` | Store checkpoint | Source identity, removed/edited counts, checkpoint, Grant state, and local Undo availability must match the reviewed effect |
| Presentation | none | `interfaces.tui.operations.forget` plus the CLI adapter | Terminal wording, focus, review choices, and cancellation do not decide authority or mutate the Source |

## Process-local review decision

Forget had no durable session before this extraction. Creating one merely to
support adapters would add visible state, cleanup rules, resume semantics, and
a new privacy surface unrelated to the current operation. The review therefore
remains process-local:

- `ForgetSessionSnapshot` contains the frozen Source binding, complete review,
  and provider dialogue only in memory;
- its version is an opaque digest over that exact state;
- local selections and provider feedback advance the same review identity;
- closing or losing the process loses the review and creates no durable
  artifact; and
- only an accepted nonempty Apply writes the Source and one checkpoint.

An agent adapter may retain these typed values inside its own process, but it
must label that lifetime and must not serialize Source contents or provider
dialogue as a portable token.

## Compatibility and safety boundaries

- `ops.analyze_forget`, `ops.forget`, and `ops.revise_forget` remain lazy
  compatibility facades over `forget_provider`; eval callers keep their sparse
  proposal and message-list shapes.
- `prepare_forget_snapshot` is a compatibility boundary for historical command
  tests returning sparse changes. It reconstructs an exhaustive KEEP ledger
  and rejects duplicate, unavailable, or source-mismatched changes before
  application.
- The CLI freezes the selected local or granted Source before constructing the
  provider. Its existing setup, review, cancel, all-KEEP, Apply, checkpoint,
  and Undo/Redo behavior remains unchanged.
- A provider cannot choose authority, Context names, checkpoint arguments, or
  executable operations. It returns only the strict curation decision ledger.
- A changed local Context fails Store CAS without publishing the reviewed
  removal. Granted authority remains frozen through the authority-store save.
- Forget has no prepared-result cache. This extraction does not introduce one
  or treat another operation's cache proof as applicable.

## Verification evidence

The current application/runtime, TUI-owner, and compatibility run passes 87
tests covering:

- Source freeze before provider construction;
- provider-free empty Source handling;
- exact complete-frame decoding and missing-decision rejection;
- immutable selection and provider-revision version advancement;
- explicit all-KEEP no-op without Apply or checkpoint;
- exact Apply receipt validation;
- real Store removal, preservation of unrelated Memories, and one checkpoint;
- stale Source rejection without partial publication;
- local and granted command behavior, frozen setup selection, direct Context
  references, and operation-unit Undo/Redo; and
- AST-level absence of `commands.*`, Typer, and prompt-toolkit imports from the
  application, runtime, and provider modules; plus absence of `commands.*`
  reverse imports from the Forget-specific TUI owner.

The existing ordered Forget PTY sets remain the visual baseline because this
stage changes execution ownership and physical module placement, not terminal
topology or key behavior. Legacy setup and Resolution import paths are thin
identity-preserving facades over `interfaces.tui.operations.forget`.

## Remaining work and non-goals

1. Add a versioned process-local agent/MCP projection over the same
   Analyze/Select/Revise/Apply use cases. The stable Python facade is recorded
   in `forget-public-python-api-design-rationale.md`.
2. Run installed-wheel discovery and effect smoke before classifying the route
   `CLOSED`.
3. Cross-process durable resume is intentionally not part of Forget. Adding it
   later would require a separately reviewed session schema and retention
   policy.
