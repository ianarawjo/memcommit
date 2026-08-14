# Sever application-boundary matrix

## Status

`MIGRATING`, reviewed 2026-08-14.

Sever is the second operation slice used to test the target application
architecture after Summarize. Its semantic analysis and require-new Apply now
have typed, terminal-independent entry points. Existing CLI setup, saved-session
launching, Resolution review, and session persistence remain compatibility
adapters and have not yet been presented as a stable Python API.

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
existing review/session adapters
        |
        v
SeverApplyRequest -> run_sever_apply -> SeverApplyResult
```

## Boundary matrix

| Concern | Typed/application owner | Production adapter | Existing interface adapter | Verified invariant |
| --- | --- | --- | --- | --- |
| Analysis input | `SeverAnalysisRequest` | `MemoryStoreSeverInputPort` | CLI flags and three-pane setup map Source, Criteria, Result, and the two ranges | Relative CLI locators are frozen to canonical public names before confirmation; runtime repeats authority checks before disclosure |
| Frozen evidence | `FrozenSeverInputs` | `capture_sever_binding` | No interface may append hidden Memories | Source and Criteria each retain exact Context identities, digests, ordinary Memories, Grant binding, range, and excluded query-only names |
| Cache | `SeverPreparedLookup` | installed Sever prewarm adapter | Interface receives the typed exact/equivalent/projected origin | Lookup runs only after authority and complete frame capture; a prepared review must exactly match the requested frozen bindings and output name after any adapter-owned safe projection |
| Provider | lazy `SeverProviderFactory` | configured provider supplied by the composition boundary | Progress is projected from typed stages | Cache hits never construct a provider; live work remains one whole-frame selective-curation turn |
| Review result | `SeverAnalysisResult` | strict provider decoder or fresh prepared review | Existing session store and Resolution Workbench | The review covers every Source Memory exactly once and creates no Result Context |
| Apply input | `SeverApplyRequest` | `MemoryStoreSeverOutputPort` | CLI `--accept` and TUI Accept call the same typed use case | Only the reviewed session crosses the materialization boundary |
| Apply result | `SeverApplyResult` | require-new Context creation and checkpoint | Existing command saves the returned APPLIED session under record-digest CAS | Source and Criteria bindings, candidates, output name, and grounded summary cannot change during Apply |
| Idempotence | `run_sever_apply` | output port is skipped for an already APPLIED session | Reopening an applied session remains read-only | A repeated application call does not create a second Context |
| Presentation | none | none | command wait, plain renderer, setup TUI, Resolution Workbench | `sever_application` imports no Typer, prompt-toolkit, TUI, or `commands.*` module |

## Dependency direction

`memcommit.sever_application` depends only on the Sever domain/session and
provider-decoder contracts. It does not import terminal or command modules.
`memcommit.sever_runtime` implements Store, Grant, cache, provider-attempt, and
checkpoint ports. Grant mechanics temporarily remain under
`memcommit.commands.granted_context`; that transitional dependency is confined
to the runtime adapter, as it is for the Summarize slice.

`memcommit.commands.sever` retains thin `_start` and `_apply` compatibility
facades because existing internal tests and Study setup code historically
called them. New Study frame capture imports the runtime owner directly rather
than reaching through the command. The command's visible progress screen maps
typed stages to its existing text and does not enter the application module.

## Safety and compatibility invariants

- Analysis completes locator, READ/Grant, COMBINE, derived-transfer, retained-
  analysis, require-new-name, and complete-frame checks before cache lookup or
  provider construction.
- Query-only routes never disclose hidden content. Live `MemoryRef` values fail
  rather than being copied into a retained frame.
- Prepared and provider-produced reviews cross the same validation gate;
  neither may change Source, Criteria, ranges, output name, or review state.
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
- AST-level application independence from commands, Typer, and prompt-toolkit;
- runtime independence from Typer and prompt-toolkit;
- real-Store analysis with no terminal output or premature Result creation;
- real-Store Apply, checkpoint creation, exact result content, and byte-for-byte
  Source preservation;
- missing Source failure before provider construction;
- existing CLI, TUI setup, authority, exact Study prewarm, review, Apply,
  Undo/Redo, and application-report behavior.

The focused run passed 61 tests. No visible TUI flow changed, so the existing
ordered Sever captures remain the applicable presentation evidence; this
structural extraction does not claim a new TUI design.

An expanded 353-test run across Sever, authority, command attempts/wait,
Context scope, Impact/session/restoration, Share interaction, Study
installation, and Context-operand consumers completed with 352 passed and one
failure. The single failure is the unrelated Compare help contract expecting
`--reference-memory`; its assertion and stack do not enter a Sever module.

## Remaining boundaries and non-goals

1. Saved-session creation, review decisions, destination revisions, and the
   record-digest save after Apply are still orchestrated by the command adapter.
   Moving that lifecycle requires a typed session repository port and must
   preserve Undo/Redo compatibility.
2. Result creation and the subsequent APPLIED-session save retain the existing
   crash window documented in `mem-sever-design-rationale.md`. This extraction
   does not claim transactionality or receipt recovery.
3. This boundary preserves `EXACT`, `EQUIVALENT_SCOPE`, and `PROJECTED` cache
   origins but does not decide when projection is safe. The Study prewarm
   adapter remains authoritative for that separate cache contract.
4. The setup TUI and Resolution Workbench remain command-hosted adapters. They
   now reach the same typed analysis/Apply use cases, but have not yet moved
   under a Sever-specific `interfaces.tui.operations` package.
5. `execute_sever_analysis` and `execute_sever_apply` are internal callable
   evidence, not a versioned public Python facade. Store-root ownership,
   configured-provider bootstrap, error taxonomy, and session lifecycle must be
   decided before public export.
