# Distill and Elaborate application boundary matrix

Last reviewed: 2026-08-25.

## Implementation ownership

Distill and Elaborate now keep their executable use cases under distinct
operation owners: `memcommit.application.operations.distill` owns Distill analysis,
Source/Target freezing, provider composition, and atomic Rule publication,
while `memcommit.application.operations.elaborate` owns Elaborate generation plus its
Context-backed atomic Add preparation. Elaborate's provider-only runtime stays
separate from `add_runtime`, so proposal-only public adapters do not acquire a
storage dependency merely because the standalone CLI can publish. The former
flat modules remain identity-preserving compatibility aliases for imported and
pickled names, but production code imports the operation owners directly.

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

| Concern | Distill | Elaborate | Evidence state |
| --- | --- | --- | --- |
| Meaning | Case/Example Context propositions → evidence-linked generative Rules, including common language, tone, expression, and notation; optional Goal focuses relevance and receives a non-generative whole-result Fit audit | Goal → at least one suggested Rule, or Rules → at least one suggested Case | `VERIFIED` against quoted café, lost-property, and Cloze reference families plus Goal Fit focused tests |
| Typed application entry | `run_distill(DistillRequest, ...)` | `run_elaborate(ElaborateRequest, ...)` | `VERIFIED` source-level absence of command/terminal imports; fresh-process package isolation is tracked separately by `IMPORT-01` |
| Production runtime | exact local Source port, pre-provider existing-Target freeze, atomic generated-Memory Add, and lazy provider factory | exact ordinary Context Source/Target freeze; recursive exact-Target ambient projection; one-turn best-effort generation by default; optional `--strict` ordered collection Conformance plus complete-frame Source Fit; exact Target restatement rejection; atomic generated-Memory Add; lazy provider factory | `VERIFIED` focused tests |
| Directional endpoints | omitted `--from`/`--to` fill from one Current snapshot; Source may equal Target | same four-way endpoint matrix; inline input has only a Target | `VERIFIED` CLI matrix and same-Context pre-image tests |
| Ground adapter | physical Goal plus ordinary `/examples` and `/contexts` subtree Memories; legacy Goal + `WORKING_CANDIDATES` remains transitional | physical exact Goal or directly owned Rules; existing `/rules` or `/examples` destination lane is ambient; legacy Ground projects its corresponding Rule/Case lane | `VERIFIED` destination-lane and unrelated-lane tests |
| Goal operand | shared frozen direct-Memory Context, direct Memory, or inline-text relevance frame; Goal is never evidence | same shared relevance frame; standalone one-item `--goal` is also the Goal Source, while `--from`/`--rule` keeps Source and focus separate | `VERIFIED` Context/Memory/text, typo fail-closed, stale binding, and motivating `--from` + `--goal` tests |
| Provider planning | complete Source frame plus all three quoted reference families, `WHOLE_FRAME_ONLY`; no default Rule-count ceiling; no Goal means exactly one generation turn, while a Goal adds one exhaustive `WHOLE_FRAME_ONLY` Fit audit over the decoded Rule set | complete input tuple, all three quoted reference families, and exact Target ambient frame in one `WHOLE_FRAME_ONLY` generation turn; best-effort stops there, while `--strict` adds one complete ordered collection Conformance frame and one exhaustive collection Fit question; exactly three proposals by default or exactly any positive `--n N` (`-n`/`--number`), with no ordinary count ceiling | `VERIFIED` one-turn default, strict rejection/acceptance, collection-level Rule applicability, Target-prefix continuation/restatement rejection, repeated-content exact counts, optional injected-limit enforcement, Target budget inclusion, exact-count mismatch rejection, empty-response, and oversized-input miss tests |
| Prepared reuse | exact Source frame + Goal + config only | exact direction + normalized input tuple + exact number (default three) + quality policy + Target ambient frame + config only | `VERIFIED` injectable port; no persisted artifact |
| Projection reuse | rejected; changing any proposition can change the complete Rule set | rejected; proposal set is defined over the complete input | intentional `N/A` |
| Configuration | one `DistillSemanticConfig` snapshot validates request, schema, live and prepared output; `max_rules=None` by default and a positive injected ceiling is optional | one `ElaborateSemanticConfig` snapshot validates request, schema, live and prepared output; both directional maxima are `None` by default and positive injected ceilings are optional | `VERIFIED` default-unbounded and nondefault-limit tests |
| Session | process-local exact proposal; Impact does not persist it | process-local exact proposal; Impact does not persist it | intentional `N/A`; no durable session |
| Publication | default standalone → existing Target, all Rules or none; `NOT_FIT` Goal audit blocks both existing-Target Add and legacy require-new Apply, while `UNDETERMINED` remains non-blocking | default best-effort → existing Target, all structurally valid proposal occurrences or none; strict validation failure or exact Target restatement publishes none; equal new content remains separately identified and materialized | `VERIFIED` endpoint, best-effort/strict policy, validation failure, repeated-content UID/materialization, sequence continuation, checkpoint, target/source drift, and no-partial-publication tests |
| Physical Ground adoption | proposal-only by default; explicit `--adopt` adds the complete Rule set to `/rules` as one revision and Ground-local Undo unit | proposal-only by default; explicit `--adopt` adds the complete Rule/Case set to `/rules` or `/examples` as one revision and Ground-local Undo unit | `VERIFIED` atomic adoption, stale revision/target rejection, provenance, CLI receipt, and local Undo tests; legacy JSON Ground remains read-only |
| Authority | standalone local Source; physical typed Ground inputs fail before provider until authority-aware projection exists | Source remains exact ordinary input; Target local embeds are exact; QUERY-only is name-only; granted proposal context requires `READ + EMBED + DERIVE + COMBINE`, while direct Add also requires `EXPORT + SAVE_ANALYSIS` before provider connection | `VERIFIED` local cycle/dedup, name-only query, grant proposal/Add success and denial, and ambient-drift tests |
| Plain CLI | semantic generation has no default Rule-count ceiling; the Add receipt previews up to 20 exact added Memories while storing the complete Rule set, then prints exact Review and Undo routes; explicit Impact is read-only | the Add receipt uses the same bounded preview; `--n` (`-n`/`--number`) accepts any positive integer as the exact Rule or Case count and explicit Impact is read-only | `VERIFIED` |
| TUI | Impact owns one compact proposal catalog; the hidden legacy/Ground read-only adapter retains its Viewer | Impact owns one compact Rule/Case proposal catalog, count-only Target ambient summary, and compact exhaustive-coverage detail; only the Ground read-only adapter retains its result Viewer | `VERIFIED` in component tests; refreshed Add/Impact PTY evidence is recorded separately |
| Public Python | typed proposal with no default Rule-count ceiling; exact in-process Distill Apply; Ground projections | typed unverified proposal with explicit best-effort/strict policy and nullable per-Case validation; Ground projections; exact count defaults to three and accepts any positive override in both directions | `VERIFIED` focused tests |
| Agent | complete proposal with no default Rule-count ceiling, `effect: NONE` | proposal only; exact count defaults to three; optional strict boolean; typed Target ambient/use, explicit quality policy, and nullable per-Case validation, `effect: NONE`, `verification: UNVERIFIED` | Distill agent contract v1 and Elaborate agent contract v5; CLI mutation does not silently broaden callable authority |
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
Distill, and both Elaborate directions. Help has separate BY KIND, A–Z, wide,
and compact evidence under `agent-records/docs/screenshots/mem-distill-help-20260815/`.

## Publication boundaries

Distill inference never mutates its Source by itself. Standalone publication
revalidates the exact frozen frame and appends to an existing Target in one
checkpoint. Ground Distill cannot publish through its CLI, public result,
agent tool, or MCP projection.

Standalone Elaborate stores structurally valid exact-count best-effort Cases by
default and records that independent Source validation was not run. With
`--strict`, it stores only collections that conform to every Source Rule and
Fit the complete frame. Neither policy marks generated Cases verified as truth
or accepted as evidence. Ground Elaborate remains proposal-only.

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

Standalone Distill and Elaborate are direct semantic Adds. They freeze,
decode, decide the complete generated set, append atomically, and return a
human-first completion summary; they do not render the proposal Viewer before
reporting success. The summary pairs each result Memory's short UID with its
complete single-line content for sets of up to 20, then reports the remaining
count instead of flooding the terminal. Separate `RECEIPT` and `CHECKPOINT`
rows are omitted because the exact checkpoint UID already remains in the
copyable `mem review distill|elaborate --receipt UID` command; `mem undo`
remains adjacent as the recovery route. Full overview, rationale,
support/provenance, verification state, and every result identity remain in
that checkpoint. Explicit Impact and the Ground-owned proposal variants remain
read-only exceptions.
