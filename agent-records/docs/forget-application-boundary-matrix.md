# Forget application-boundary matrix

Last reviewed: 2026-08-28.

## Status

`MIGRATING` until route classification is complete. The semantic, review,
authority, freshness, Apply, public Python, agent, MCP, installed-wheel, and
existing command routes now enter the same application owners.

## Motivation

Forget already shared a strict whole-frame selective-curation decoder with
Sever, and its immutable review model was independent of the terminal. The
complete operation nevertheless existed only in `commands/forget/command.py`: that
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
  process-local decision ledger + opaque version
      |              |
      | select       | provider feedback
      v              v
run_forget_selection / run_forget_revision
          |
          v
run_forget_apply
  explicit no-op, or authority + Source CAS + one checkpoint
```

## Package ownership

The canonical terminal-independent owners now live together under
`memcommit.application.operations.forget`: `application.py` owns the typed request,
frozen Source, process-local review lifecycle, and Apply contract, while
`runtime.py` owns Store, Grant, provider-connection, checkpoint, and mutation
adapters. API, CLI, Impact, and Forget workbench consumers import those
operation-owned modules directly, so a command or presentation module is not
an accidental route to the executable contract.

The historical `memcommit.forget_application` and
`memcommit.forget_runtime` paths remain module-identity aliases. They preserve
old import order, monkeypatch targets, and serialized Python globals without
creating a second implementation owner. Importing the package alone remains
lazy. This is an ownership-only relocation: whole-frame selective curation,
Source freshness, authority, checkpoint, review, Apply, and public adapter
behavior are unchanged.

Forget's terminal-specific adapters are now co-located under
`memcommit.adapters.console.commands.forget`. `command.py` owns orchestration,
`setup.py` collects the process-local Source and instruction,
`receipt.py` projects the applied change receipt, and
`workbench/presentation.py` plus `workbench/screen.py` adapt the typed review to
the shared Resolution Session. The former operation-specific CLI/TUI trees and
physical setup forwarding module were removed so that presentation code has
one command-owned home. Historical flat imports remain centralized aliases to
these canonical modules rather than parallel implementation files.

## Boundary matrix

| Concern | Application owner | Production adapter | Invariant |
| --- | --- | --- | --- |
| Input | `ForgetAnalysisRequest` | CLI setup or Python adapter | One canonical direct Source and one nonblank instruction |
| Source freeze | `ForgetSourcePort` | `MemoryStoreForgetSourcePort` | READ/Grant resolution and complete direct loading finish before provider construction |
| Semantic analysis | `run_forget_analysis` | `forget_provider` plus injected provider factory | The complete Source and instruction run in one bounded provider turn; no hidden partitioning |
| Decoder | `forget_provider` and shared `selective_curation` | none | Exactly one KEEP/TRANSFORM/DROP disposition per direct Source Memory |
| Decision ledger | internal `ForgetReview` inside `ForgetSessionSnapshot` | interface projection only | The legacy domain type is immutable and retains every Source Memory, including KEEP; it is not the public Review operation |
| Decision version | `forget_snapshot_version` | none | Selection and provider revision return a new opaque version under the same process-local decision UID |
| Provider revision | `run_forget_revision` | injected provider factory | The original frozen Source, instruction, and role-ordered dialogue are reused as one whole frame |
| No-op | `run_forget_apply` | none | An all-KEEP decided batch creates no checkpoint and does not enter mutation authority |
| Apply | `run_forget_apply` | `MemoryStoreForgetSourcePort.apply` | Only sparse decided edits/removals enter the exact frozen Source mutation boundary |
| Authority | runtime adapter | `authorized_context_mutation` | Local writes use Context CAS; granted writes retain required UPDATE/DELETE permissions through the authority save |
| Receipt | `ForgetApplyReceipt` | Store checkpoint | Source identity, removed/edited counts, checkpoint, Grant state, and local Undo availability must match the decided effect |
| Presentation | none | `commands.forget.setup`, `commands.forget.receipt`, and `commands.forget.workbench` | Terminal wording, focus, execution choices, and cancellation do not decide authority or mutate the Source |

## Process-local execution decision

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
  provider. Interactive setup/decisions, cancel, all-KEEP, Apply, checkpoint,
  and Undo/Redo retain their authority semantics; explicit non-TTY invocation
  advances the complete provider decision set directly to Apply.
- A provider cannot choose authority, Context names, checkpoint arguments, or
  executable operations. It returns only the strict curation decision ledger.
- A changed local Context fails Store CAS without publishing the decided
  removal. Granted authority remains frozen through the authority-store save.
- Forget has no prepared-result cache. This extraction does not introduce one
  or treat another operation's cache proof as applicable.
- The compatibility modules contain no behavior. New production code imports
  `memcommit.application.operations.forget.application` or
  `memcommit.application.operations.forget.runtime` directly.

## Verification evidence

The current application/runtime, TUI-owner, ownership, and compatibility run
passes 85 focused tests covering:

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
stage changes ownership, physical module placement, and the setup value's
internal name, not terminal topology or key behavior. The centralized
`memcommit.commands.forget_setup_workbench` and
`memcommit.forget_resolution_adapter` compatibility mappings resolve to the
new command-owned modules without physical forwarding facades; the flat
application/runtime aliases likewise preserve identity without re-owning the
implementation.

## Remaining work and non-goals

1. Classify the fully verified route and regenerate the callable/operation
   catalogs.
2. Cross-process durable resume is intentionally not part of Forget. Adding it
   later would require a separately reviewed session schema and retention
   policy.

The stable Python facade is recorded in
`forget-public-python-api-design-rationale.md`; the versioned process-local
machine route is recorded in `forget-agent-adapter-design-rationale.md`.

## 2026-08-20 execution-receipt migration

Forget's whole-frame result is an execution decision set, not a public
Proposal outcome. Decision-free local execution advances to atomic Apply and a
compact receipt; required choices remain inside the Forget invocation. The
checkpoint now stores every exact REMOVE/EDIT pre-image, post-image, and
reason, enabling provider-free `mem review forget --receipt UID` after Apply.
Granted-owner checkpoint evidence is not advertised as locally reviewable.
