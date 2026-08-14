# Sever application-boundary matrix

## Status

`VERIFIED` for the internal application boundary, reviewed 2026-08-14.

Sever is the second operation slice used to test the target application
architecture after Summarize. Its semantic analysis, private saved-session
lifecycle, review revisions, and require-new Apply now have typed,
terminal-independent entry points. Existing CLI setup, saved-session launching,
and Resolution presentation remain interface adapters and have not yet been
presented as a stable Python API.

## Motivation

Before this extraction, `memcommit.commands.sever` was the only complete
execution junction. Domain records, provider decoding, session persistence,
and review projection already had separate modules, but the command still
resolved authority, froze frames, consulted the Study cache, constructed the
provider, materialized the Result, and rendered terminal progress. A Python or
agent caller therefore had to invoke a CLI-shaped function or reproduce part of
the operation policy.

The extraction relocates that junction without changing the Sever meaning:

```text
CLI flags or TUI setup
        |
        v
SeverAnalysisRequest
        |
        v
run_sever_analysis
  | authority-frozen Source × Criteria
  | hidden prepared-analysis lookup
  | otherwise one whole-frame provider turn
        |
        v
SeverAnalysisResult(session, origin)
        |
        v
run_sever_session_start
        |
        v
SeverSessionSnapshot(session, opaque CAS token)
  | decision revision
  | destination revision
        |
        v
run_sever_session_apply
  | require-new output + checkpoint
  | APPLIED-session CAS save
        |
        v
SeverPersistedApplyResult
```

## Boundary matrix

| Concern | Typed/application owner | Production adapter | Existing interface adapter | Verified invariant |
| --- | --- | --- | --- | --- |
| Analysis input | `SeverAnalysisRequest` | `MemoryStoreSeverInputPort` | CLI flags and three-pane setup map Source, Criteria, Result, and the two ranges | Relative CLI locators are frozen to canonical public names before confirmation; runtime repeats authority checks before disclosure |
| Frozen evidence | `FrozenSeverInputs` | `capture_sever_binding` | No interface may append hidden Memories | Source and Criteria each retain exact Context identities, digests, ordinary Memories, Grant binding, range, and excluded query-only names |
| Cache | `SeverPreparedLookup` | installed Sever prewarm adapter | Interface receives the typed exact/equivalent/projected origin | Lookup runs only after authority and complete frame capture; a prepared review must exactly match the requested frozen bindings and output name after any adapter-owned safe projection |
| Provider | lazy `SeverProviderFactory` | configured provider supplied by the composition boundary | Progress is projected from typed stages | Cache hits never construct a provider; live work remains one whole-frame selective-curation turn |
| Review result | `SeverAnalysisResult` | strict provider decoder or fresh prepared review | Resolution Workbench renders the typed review | The review covers every Source Memory exactly once and creates no Result Context |
| Session lifecycle | `SeverSessionRepository`, `SeverSessionSnapshot` | `MemoryStoreSeverSessionRepository` | launchers and `--resume` open a snapshot; interfaces never calculate a record digest | Create, load, and replace share one opaque optimistic-CAS contract |
| Review revision | `SeverDecisionRequest` | repository replace under the snapshot token | scripted choices and TUI responses submit the same exact candidate UID and selection | stale revisions fail before they can overwrite a newer review; custom content is valid only for `CUSTOM` |
| Destination revision | `SeverDestinationRequest`, `SeverDestinationPort` | live Store name validation plus repository CAS | the Save Location editor supplies only the proposed exact name | an existing or invalid output cannot alter the review, and changing a name does not rerun analysis |
| Apply input | `SeverPersistedApplyRequest` | `MemoryStoreSeverOutputPort` plus the session repository | CLI `--accept` and TUI Accept call the same persisted use case | the current token is reloaded before any output effect; only that exact snapshot crosses materialization, then its APPLIED revision is CAS-saved |
| Apply result | `SeverPersistedApplyResult` | require-new Context, checkpoint, and APPLIED-session replacement | interfaces receive the resulting snapshot | Source and Criteria bindings, candidates, output name, and grounded summary cannot change during Apply |
| Idempotence | `run_sever_session_apply` | output and repository ports are skipped for an already APPLIED snapshot | reopening an applied session remains read-only | a repeated application call creates neither a second Context nor a second session revision |
| Presentation | none | none | command wait, plain renderer, setup TUI, Resolution Workbench | `sever_application` imports no Typer, prompt-toolkit, TUI, or `commands.*` module |

## Dependency direction

`memcommit.sever_application` depends only on the Sever domain/session and
provider-decoder contracts. It does not import terminal or command modules.
`memcommit.sever_runtime` implements Store, Grant, cache, provider-attempt,
destination-validation, private-session, and checkpoint ports. Grant mechanics temporarily remain under
`memcommit.authority.access`; that transitional dependency is confined
to the runtime adapter, as it is for the Summarize slice.

`memcommit.commands.sever` retains thin `_start` and `_apply` compatibility
facades because existing internal tests historically called the analysis-only
and materialization-only paths. The executable command no longer calls the
session Store's `load` or `save`, calculates record digests, selects a candidate,
or changes an output name. Its CLI and TUI routes pass application-owned
snapshots and opaque version tokens to the runtime. New Study frame capture
imports the runtime owner directly rather than reaching through the command.

## Safety and compatibility invariants

- Analysis completes locator, READ/Grant, COMBINE, derived-transfer, retained-
  analysis, require-new-name, and complete-frame checks before cache lookup or
  provider construction.
- Query-only routes never disclose hidden content. Live `MemoryRef` values fail
  rather than being copied into a retained frame.
- Prepared and provider-produced reviews cross the same validation gate;
  neither may change Source, Criteria, ranges, output name, or review state.
- Every durable review mutation consumes the exact version token returned by
  create or open. The repository is the only layer that interprets that token
  as the current record digest.
- Apply reloads the durable snapshot before output creation. A stale REVIEWING
  or stale APPLIED snapshot fails before materialization; the final CAS still
  catches a race that occurs during the existing Context-creation crash window.
- Apply creates a new local ordinary Context and checkpoint. It never updates,
  deletes, or checkpoints the Source.
- Local contributing Context digests remain the Store materializer's CAS set.
  Fully granted retained inputs have no local source path to lock and preserve
  the pre-existing granted-input behavior.
- Existing Sever session schema, candidate UIDs, deterministic Result Memory
  UIDs, checkpoint payload, Undo/Redo contract, CLI text, TUI topology, and
  saved-session compatibility are unchanged.

## Verification evidence

The focused boundary and compatibility run currently covers:

- pure typed provider analysis and typed progress stages;
- prepared reuse with provider construction prohibited and its projection origin retained;
- rejection of a prepared review that changes the frozen Source or output;
- typed Apply receipt validation and idempotence;
- typed session create/open, decision, destination, persisted Apply, and stale-
  snapshot rejection;
- AST-level application independence from commands, Typer, and prompt-toolkit;
- runtime independence from Typer and prompt-toolkit;
- real-Store analysis with no terminal output or premature Result creation;
- real-Store Apply, checkpoint creation, exact result content, and byte-for-byte
  Source preservation;
- missing Source failure before provider construction;
- real-Store session CAS, destination validation, persisted Apply, and repeat-
  Apply idempotence without terminal output;
- existing CLI, TUI setup, authority, exact Study prewarm, review, Apply,
  Undo/Redo, and application-report behavior.

The focused lifecycle and compatibility run passed 53 tests. No visible TUI flow changed, so the existing
ordered Sever captures remain the applicable presentation evidence; this
structural extraction does not claim a new TUI design.

An expanded 368-test run across Sever, authority, command attempts/wait,
Context scope, Impact/session/restoration, Study installation, write
protection, and Context-operand consumers passed in full.

## Remaining boundaries and non-goals

1. Result creation and the subsequent APPLIED-session save retain the existing
   crash window documented in `mem-sever-design-rationale.md`. This extraction
   does not claim transactionality or receipt recovery.
2. This boundary preserves `EXACT`, `EQUIVALENT_SCOPE`, and `PROJECTED` cache
   origins but does not decide when projection is safe. The Study prewarm
   adapter remains authoritative for that separate cache contract.
3. The setup TUI and Resolution Workbench remain command-hosted adapters. They
   now reach the complete typed lifecycle, but have not yet moved
   under a Sever-specific `interfaces.tui.operations` package.
4. The production private-session adapter still uses the existing POSIX
   `fcntl` lock. The repository contract is platform-neutral, but a Windows
   lock implementation remains part of the cross-platform infrastructure work.
5. The `execute_sever_*` functions are internal callable
   evidence, not a versioned public Python facade. Store-root ownership,
   configured-provider bootstrap, error taxonomy, and compatibility policy must
   be decided before public export.
