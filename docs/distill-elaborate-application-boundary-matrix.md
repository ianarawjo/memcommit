# Distill and Elaborate application boundary matrix

Last reviewed: 2026-08-20.

| Concern | Distill | Elaborate | Evidence state |
| --- | --- | --- | --- |
| Meaning | Case/Example Context propositions → evidence-linked generative Rules, including common language, tone, expression, and notation; optional Goal focuses relevance | Goal → at least one suggested Rule, or Rules → at least one suggested Case | `VERIFIED` against quoted café, lost-property, and Cloze reference families |
| Typed application entry | `run_distill(DistillRequest, ...)` | `run_elaborate(ElaborateRequest, ...)` | `VERIFIED` source-level absence of command/terminal imports; fresh-process package isolation is tracked separately by `IMPORT-01` |
| Production runtime | exact local Source port, pre-provider existing-Target freeze, atomic generated-Memory Add, and lazy provider factory | exact ordinary Context Source/Target freeze; recursive exact-Target ambient projection; atomic generated-Memory Add; lazy provider factory | `VERIFIED` focused tests |
| Directional endpoints | omitted `--from`/`--to` fill from one Current snapshot; Source may equal Target | same four-way endpoint matrix; inline input has only a Target | `VERIFIED` CLI matrix and same-Context pre-image tests |
| Ground adapter | physical Goal plus ordinary `/examples` and `/contexts` subtree Memories; legacy Goal + `WORKING_CANDIDATES` remains transitional | physical exact Goal or directly owned Rules; existing `/rules` or `/examples` destination lane is ambient; legacy Ground projects its corresponding Rule/Case lane | `VERIFIED` destination-lane and unrelated-lane tests |
| Provider planning | complete Source frame plus all three quoted reference families, `WHOLE_FRAME_ONLY`; no default Rule-count ceiling, while an injected explicit ceiling remains enforceable | complete input tuple, all three quoted reference families, and exact Target ambient frame in both modes, `WHOLE_FRAME_ONLY`; exactly three proposals by default or exactly `--n N` (`-n`/`--number`) within the directional bound | `VERIFIED` prompt quotation, default no-`maxItems` schema, explicit-limit enforcement, Target budget inclusion, strict Elaborate exact-count bounds, mismatch rejection, empty-response, and oversized-miss tests |
| Prepared reuse | exact Source frame + Goal + config only | exact direction + normalized input tuple + exact number (default three) + Target ambient frame + config only | `VERIFIED` injectable port; no persisted artifact |
| Projection reuse | rejected; changing any proposition can change the complete Rule set | rejected; proposal set is defined over the complete input | intentional `N/A` |
| Configuration | one `DistillSemanticConfig` snapshot validates request, schema, live and prepared output; `max_rules=None` by default and a positive injected ceiling is optional | one `ElaborateSemanticConfig` snapshot validates request, schema, live and prepared output | `VERIFIED` default-unbounded and nondefault-limit tests |
| Session | process-local exact proposal; Impact does not persist it | process-local exact proposal; Impact does not persist it | intentional `N/A`; no durable session |
| Publication | default standalone → existing Target, all Rules or none; legacy require-new Apply remains compatible | default standalone → existing Target, all proposals or none | `VERIFIED` endpoint, checkpoint, target/source drift, and no-partial-publication tests |
| Authority | standalone local Source; physical typed Ground inputs fail before provider until authority-aware projection exists | Source remains exact ordinary input; Target local embeds are exact; QUERY-only is name-only; granted proposal context requires `READ + EMBED + DERIVE + COMBINE`, while direct Add also requires `EXPORT + SAVE_ANALYSIS` before provider connection | `VERIFIED` local cycle/dedup, name-only query, grant proposal/Add success and denial, and ambient-drift tests |
| Plain CLI | semantic generation has no default Rule-count ceiling; the Add receipt previews up to 20 exact added Memories while storing the complete Rule set, then prints exact Review and Undo routes; explicit Impact is read-only | the Add receipt uses the same bounded preview; `--n` (`-n`/`--number`) means an exact Rule or Case count and explicit Impact is read-only | `VERIFIED` |
| TUI | Impact owns one compact proposal catalog; the hidden legacy/Ground read-only adapter retains its Viewer | Impact owns one compact Rule/Case proposal catalog, count-only Target ambient summary, and compact exhaustive-coverage detail; only the Ground read-only adapter retains its result Viewer | `VERIFIED` in component tests; refreshed Add/Impact PTY evidence is recorded separately |
| Public Python | typed proposal with no default Rule-count ceiling; exact in-process Distill Apply; Ground projections | typed unverified proposal; Ground projections; exact count defaults to three with an optional override in both directions | `VERIFIED` focused tests |
| Agent/MCP | complete proposal with no default Rule-count ceiling, `effect: NONE` | proposal only, exact count defaults to three with an optional override, typed Target ambient/use trace, `effect: NONE`, `verification: UNVERIFIED` | Distill agent contract v1 and Elaborate agent contract v3; CLI mutation does not silently broaden callable authority |
| Clipboard | focused `y`, whole document `Y` | focused `y`, whole document `Y` | `VERIFIED` |

## Verification evidence

Focused regression covers both four-way endpoint matrices, same-Context
pre-images, context-role validation, atomic multi-Memory publication,
pre-provider missing targets, concurrent Source/Target drift, and Impact's
zero-checkpoint guarantee. Installed-wheel callable verification remains a
separate gate because this CLI Add slice intentionally leaves public and MCP
routes proposal-only.

The ordered actual-color PTY set under
`docs/screenshots/distill-elaborate-shared-app-20260815/` contains 18 states at
`180×52`: editable Distill setup, cancellation before provider construction,
review/copy, require-new Apply and read-only verification, caller-frozen Ground
Distill, and both Elaborate directions. Help has separate BY KIND, A–Z, wide,
and compact evidence under `docs/screenshots/mem-distill-help-20260815/`.

## Publication boundaries

Distill inference never mutates its Source by itself. Standalone publication
revalidates the exact frozen frame and appends to an existing Target in one
checkpoint. Ground Distill cannot publish through its CLI, public result,
agent tool, or MCP projection.

Standalone Elaborate stores its proposals but never marks them verified or
accepted. Ground Elaborate remains proposal-only. Stored generated Case
propositions therefore remain hypotheses rather than fabricated evidence.

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
