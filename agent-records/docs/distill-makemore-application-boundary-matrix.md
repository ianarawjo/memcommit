# Distill and Makemore application boundary matrix

> **Authorization contract updated 2026-08-30.** Permission claims below that use `EMBED`, `DERIVE`, `COMBINE`, `EXPORT`, `ACCEPT_DERIVED`, or `SAVE_*` describe the retired contract preserved for design history. The current contract uses `QUERY`, `CREATE`, `READ`, `UPDATE`, and `DELETE`; `READ` covers readable semantic use and Embed traversal, while `SHARE` remains a separate endpoint capability. See `granted-derived-ownership-design-rationale.md`.

Last reviewed: 2026-08-31.

## 2026-08-31 Context auto-composition

Bare or `--from` Context Makemore now composes the existing Distill and
Makemore application contracts. The exact Target is frozen first, Distill
produces evidence-linked Rules without publishing them, and the ordinary
Rules-to-Cases Makemore path consumes those Rules. Only final Cases are added.
Checkpoint schema version 6 retains the transient Rule evidence so Review can
show the complete Source→Rules→Cases trace. Explicit `--as rules`, `--as goal`,
inline Rule/Goal, public, agent, and Ground directions retain their direct
contracts and existing provider versions.

## 2026-08-30 console route update

Standalone Distill and Makemore keep one execution/result route in every
terminal. Their former `--plain`/`--tui` presentation switches and generic
console runners are removed. Direct standalone requests still publish and
return an application receipt; physical Ground proposal routes render one
stable proposal/result before optional explicit adoption. Non-applying detail
belongs to `mem impact distill|makemore`, and applied detail belongs to
checkpoint-backed Review. The retained workbench/Viewer modules remain tested
components rather than direct-command launchers.

## Implementation ownership

Distill and Makemore now keep their executable use cases under distinct
operation owners: `memcommit.application.operations.distill` owns Distill analysis,
Source/Target freezing, provider composition, and atomic Rule publication,
while `memcommit.application.operations.makemore` owns Makemore generation plus its
Context-backed atomic Add preparation. Makemore's provider-only runtime stays
separate from `add_runtime`, so proposal-only public adapters do not acquire a
storage dependency merely because the standalone CLI can publish. The former
flat modules remain identity-preserving compatibility aliases for imported and
pickled names, but production code imports the operation owners directly.

The shared result-to-Memory transition is owned separately by
`memcommit.application.capabilities.semantic_result_memorization`. Distill and
Makemore retain their own provider, validation, Source, and receipt policies;
the shared capability only freezes the existing Target and memorizes the
complete decided result with one originating-operation checkpoint.

This relocation intentionally does not merge the operations or change their
whole-frame planning, exact prepared-result matching, authority, validation,
or publication contracts. It changes implementation ownership and dependency
direction only, so the existing behavior-focused PTY evidence does not require
a screenshot refresh.

Distill's console-specific adapters are co-located under
`memcommit.adapters.console.commands.distill`: `command.py` owns orchestration,
`proposal.py` owns the complete stable proposal text, `receipt.py` owns the
bounded automatic-result summary, and `workbench/` owns the optional read-only
proposal inspection flow. The former `interfaces/cli/distill.py` and
`interfaces/tui/operations/distill` paths are removed without compatibility
facades. Shared Viewer, clipboard, and Context-targeting mechanics retain their
existing owners. This is an ownership relocation only; output text, execution
timing, mutation boundaries, keyboard behavior, and existing PTY evidence are
unchanged.

| Concern | Distill | Makemore | Evidence state |
| --- | --- | --- | --- |
| Meaning | Case/Example Context propositions → evidence-linked generative Rules, including common language, tone, expression, and notation; optional Goal focuses relevance and receives a non-generative whole-result Fit audit | Goal → suggested Rules; explicit Rules → suggested Cases; automatic Context Source → transient Distilled Rules → suggested Cases | `VERIFIED` against quoted café, lost-property, and Cloze reference families plus Goal Fit and composite-pipeline focused tests |
| Typed application entry | `run_distill(DistillRequest, ...)` | direct `run_makemore(MakemoreRequest, ...)`; Context composition in `prepare_distilled_makemore_add(...)` | `VERIFIED` source-level absence of command/terminal imports; fresh-process package isolation is tracked separately by `IMPORT-01` |
| Production runtime | exact local Source port, pre-provider existing-Target freeze, atomic generated-Memory Add, and lazy provider factory | exact ordinary Context Source/Target freeze; automatic process-local Distill composition or explicit direct Source role; recursive exact-Target ambient projection; one-turn best-effort Makemore generation by default; optional `--strict` ordered collection Conformance plus complete-frame Source Fit; exact Target restatement rejection; atomic final-Memory Add; lazy provider factory | `VERIFIED` focused tests |
| Directional endpoints | omitted `--from`/`--to` fill from one Current snapshot; Source may equal Target | same four-way endpoint matrix; inline input has only a Target | `VERIFIED` CLI matrix and same-Context pre-image tests |
| Ground adapter | physical Goal plus ordinary `/examples` and `/contexts` subtree Memories | physical exact Goal or directly owned Rules; existing `/rules` or `/examples` destination lane is ambient | `VERIFIED` destination-lane and unrelated-lane tests |
| Goal operand | shared frozen direct-Memory Context, direct Memory, or inline-text relevance frame; Goal is never evidence | same shared relevance frame; standalone one-item `--goal` is also the Goal Source, while `--from`/`--rule` keeps Source and focus separate | `VERIFIED` Context/Memory/text, typo fail-closed, stale binding, and motivating `--from` + `--goal` tests |
| Provider planning | complete Source frame plus all three quoted reference families, `WHOLE_FRAME_ONLY`; no default Rule-count ceiling; no Goal means exactly one generation turn, while a Goal adds one exhaustive `WHOLE_FRAME_ONLY` Fit audit over the decoded Rule set | direct modes use one complete Makemore input tuple; automatic Context mode first runs the unchanged whole-frame Distill contract, then one unchanged Makemore turn over its complete Rule result and exact Target ambient frame; best-effort stops there, while `--strict` adds complete Conformance and Fit; exactly three final proposals by default or exactly any positive `--n N`, with no ordinary count ceiling | `VERIFIED` direct and composite call order, transient Rule evidence, exact final count, strict rejection/acceptance, Target drift, and no-partial-publication tests |
| Prepared reuse | exact Source frame + Goal + config only | exact direction + normalized input tuple + exact number (default three) + quality policy + Target ambient frame + config only | `VERIFIED` injectable port; no persisted artifact |
| Projection reuse | rejected; changing any proposition can change the complete Rule set | rejected; proposal set is defined over the complete input | intentional `N/A` |
| Configuration | one `DistillSemanticConfig` snapshot validates request, schema, live and prepared output; `max_rules=None` by default and a positive injected ceiling is optional | one `MakemoreSemanticConfig` snapshot validates request, schema, live and prepared output; both directional maxima are `None` by default and positive injected ceilings are optional | `VERIFIED` default-unbounded and nondefault-limit tests |
| Session | process-local exact proposal; Impact does not persist it | process-local exact proposal; Impact does not persist it | intentional `N/A`; no durable session |
| Publication | default standalone → existing Target, all Rules or none; `NOT_FIT` Goal audit blocks both existing-Target Add and legacy require-new Apply, while `UNDETERMINED` remains non-blocking | automatic Context mode publishes final Cases only and records transient Rules in checkpoint v6; direct mode retains checkpoint v5; default best-effort → existing Target, all structurally valid proposal occurrences or none; strict validation failure or exact Target restatement publishes none | `VERIFIED` endpoint, transient-intermediate, best-effort/strict policy, validation failure, checkpoint, target/source drift, and no-partial-publication tests |
| Physical Ground adoption | proposal-only by default; explicit `--adopt` adds the complete Rule set to `/rules` as one revision and Ground-local Undo unit | proposal-only by default; explicit `--adopt` adds the complete Rule/Case set to `/rules` or `/examples` as one revision and Ground-local Undo unit | `VERIFIED` atomic adoption, stale revision/target rejection, provenance, CLI receipt, and local Undo tests |
| Authority | standalone local Source; physical typed Ground inputs fail before provider until authority-aware projection exists | Source remains exact ordinary input; Target local embeds are exact; QUERY-only is name-only; granted proposal context requires `READ + EMBED + DERIVE + COMBINE`, while direct Add also requires `EXPORT + SAVE_ANALYSIS` before provider connection | `VERIFIED` local cycle/dedup, name-only query, grant proposal/Add success and denial, and ambient-drift tests |
| Plain CLI | semantic generation has no default Rule-count ceiling; the Add receipt previews up to 20 exact added Memories while storing the complete Rule set, then prints exact Review and Undo routes; explicit Impact is read-only | bare Context mode reports `DISTILL → MAKEMORE` and the transient Rule count; the Add receipt previews final Memories only; `--n` applies to the exact final Rule or Case count and explicit Impact is read-only | `VERIFIED` |
| TUI | Impact owns one compact proposal catalog; physical Ground remains line-oriented | Impact shows transient Distilled Rules before one compact final proposal catalog, count-only Target ambient summary, and compact exhaustive-coverage detail; physical Ground remains line-oriented | `VERIFIED` in component tests; refreshed composite Impact PTY evidence is recorded separately |
| Public Python | typed proposal with no default Rule-count ceiling; exact in-process Distill Apply; Ground projections | typed unverified proposal with explicit best-effort/strict policy and nullable per-Case validation; Ground projections; exact count defaults to three and accepts any positive override in both directions | `VERIFIED` focused tests |
| Agent | complete proposal with no default Rule-count ceiling, `effect: NONE` | proposal only; exact count defaults to three; optional strict boolean; typed Target ambient/use, explicit quality policy, and nullable per-Case validation, `effect: NONE`, `verification: UNVERIFIED` | Distill agent contract v1 and Makemore agent contract v5; CLI mutation does not silently broaden callable authority |
| Clipboard | focused `y`, whole document `Y` | focused `y`, whole document `Y` | `VERIFIED` |

## Verification evidence

Focused regression covers both four-way endpoint matrices, same-Context
pre-images, context-role validation, atomic multi-Memory publication,
pre-provider missing targets, concurrent Source/Target drift, and Impact's
zero-checkpoint guarantee. Installed-wheel callable verification remains a
separate gate because this CLI Add slice intentionally leaves public and MCP
routes proposal-only.

The ordered actual-color PTY set under
`agent-records/docs/screenshots/distill-elaborate-shared-app-20260815/` contains 18 states at
`180×52`: editable Distill setup, cancellation before provider construction,
review/copy, require-new Apply and read-only verification, caller-frozen Ground
Distill, and both Makemore directions. Help has separate BY KIND, A–Z, wide,
and compact evidence under `agent-records/docs/screenshots/mem-distill-help-20260815/`.
The automatic Context pipeline is recorded under
`agent-records/docs/screenshots/makemore-auto-distill-20260831/`: the ordered
`180×52` set shows both provider stages, transient evidence-linked Rules, final
Case detail, and a zero-write Impact verification.

## Publication boundaries

Distill inference never mutates its Source by itself. Standalone publication
revalidates the exact frozen frame and appends to an existing Target in one
checkpoint. Ground Distill cannot publish through its CLI, public result,
agent tool, or MCP projection.

Standalone Makemore stores structurally valid exact-count best-effort Cases by
default and records that independent Source validation was not run. With
`--strict`, it stores only collections that conform to every Source Rule and
Fit the complete frame. Neither policy marks generated Cases verified as truth
or accepted as evidence. Ground Makemore remains proposal-only.

## Remaining gates

1. Design and install exact hidden receipts before claiming an ordinary cache
   hit for either operation.
2. Complete Help wording and responsive-render review.
3. Add granted Distill only after derivation, export, retention, and target
   acceptance authority are explicit.
4. Re-run the closed `IMPORT-01` gate whenever either operation gains another
   public adapter or optional integration.
5. Resolve physical `/contexts` MemoryRefs, embeds, query routes, and granted
   links only through an authority-aware projection; durable membership alone
   does not authorize provider disclosure.

## 2026-08-20 execution-receipt migration

Standalone Distill and Makemore memorize their semantic results directly.
They freeze, decode, decide the complete generated set, record it atomically as
ordinary Memories, and return a
human-first completion summary; they do not render the proposal Viewer before
reporting success. The summary pairs each result Memory's short UID with its
complete single-line content for sets of up to 20, then reports the remaining
count instead of flooding the terminal. Separate `RECEIPT` and `CHECKPOINT`
rows are omitted because the exact checkpoint UID already remains in the
copyable `mem review distill|makemore --receipt UID` command; `mem undo`
remains adjacent as the recovery route. Full overview, rationale,
support/provenance, verification state, and every result identity remain in
that checkpoint. Explicit Impact and the Ground-owned proposal variants remain
read-only exceptions.
