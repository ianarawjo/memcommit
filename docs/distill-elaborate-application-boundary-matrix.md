# Distill and Elaborate application boundary matrix

Last reviewed: 2026-08-15.

| Concern | Distill | Elaborate | Evidence state |
| --- | --- | --- | --- |
| Meaning | Case/Example Context propositions → evidence-linked Rules; optional Goal focuses relevance | Goal → at least one suggested Rule, or Rules → at least one suggested Case | `VERIFIED` in domain tests |
| Typed application entry | `run_distill(DistillRequest, ...)` | `run_elaborate(ElaborateRequest, ...)` | `VERIFIED` source-level absence of command/terminal imports; fresh-process package isolation is tracked separately by `IMPORT-01` |
| Production runtime | local Store source/output ports and lazy provider factory | lazy provider factory; no Store for inline input | `VERIFIED` focused tests |
| Ground adapter | exact Goal + `WORKING_CANDIDATES` → same locked `DistillRequest` | exact Ground Goal or active Rules → same `ElaborateRequest` | `VERIFIED` pre/post revision tests; Distill locked-source PTY |
| Provider planning | complete Source frame, `WHOLE_FRAME_ONLY` | complete input tuple, `WHOLE_FRAME_ONLY`; nonempty proposal set | `VERIFIED` strict schema (`minItems: 1`), empty-response, and oversized-miss tests; provider construction remains zero before pre-call rejection |
| Prepared reuse | exact Source frame + Goal + config only | exact direction + normalized input tuple + config only | `VERIFIED` injectable port; no persisted artifact |
| Projection reuse | rejected; changing any proposition can change the complete Rule set | rejected; proposal set is defined over the complete input | intentional `N/A` |
| Configuration | one `DistillSemanticConfig` snapshot validates request, schema, live and prepared output | one `ElaborateSemanticConfig` snapshot validates request, schema, live and prepared output | `VERIFIED` nondefault-limit tests |
| Session | process-local result with opaque frozen Source token | process-local read-only result | intentional `N/A`; no durable session |
| Apply | reviewed standalone result → require-new local Context | none | Distill `VERIFIED`; Elaborate intentional `N/A` |
| Authority | local Source only; granted material rejected before provider | inline or exact local Ground record; no Context content disclosure | current boundary documented |
| Plain CLI | same typed result renderer | same typed result renderer | `VERIFIED` |
| TUI | shared Context Summary setup + semantic Viewer | semantic Viewer | `VERIFIED` in component tests and ordered actual-color PTY trace |
| Public Python | typed proposal; exact in-process Distill Apply; Ground projections | typed unverified proposal; Ground projections | `VERIFIED` focused tests |
| Agent/MCP | proposal only, `effect: NONE` | proposal only, `effect: NONE`, `verification: UNVERIFIED` | `VERIFIED` in-process invocation and installed-wheel six-tool discovery |
| Clipboard | focused `y`, whole document `Y` | focused `y`, whole document `Y` | `VERIFIED` |

## Verification evidence

The final focused regression run passed `240` tests. One source-environment
MCP stdio test skipped because the checkout interpreter does not install the
optional `mcp` dependency. The independent installed-wheel gate installed
`memcommit[mcp]` into a fresh environment, used MCP 2.0.0, and passed official
stdio discovery of Query, Add, Meld, Distill, Elaborate, and Fit plus a real
Add call. The same installed environment passed the `IMPORT-01` root/client
isolation assertions from outside the checkout.

The ordered actual-color PTY set under
`docs/screenshots/distill-elaborate-shared-app-20260815/` contains 18 states at
`180×52`: editable Distill setup, cancellation before provider construction,
review/copy, require-new Apply and read-only verification, caller-frozen Ground
Distill, and both Elaborate directions. Help has separate BY KIND, A–Z, wide,
and compact evidence under `docs/screenshots/mem-distill-help-20260815/`.

## Publication boundaries

Distill inference never mutates its Source. Standalone Apply revalidates the
exact frozen frame and publishes one new Context/checkpoint. Ground Distill
cannot Apply through its CLI, public result, agent tool, or MCP projection.

Elaborate never saves or accepts its proposals. A caller must use a separate
reviewed Ground or Context operation to promote one. This prevents generated
Case propositions from becoming fabricated evidence merely because they were
well-formed.

## Remaining gates

1. Design and install exact hidden receipts before claiming an ordinary cache
   hit for either operation.
2. Complete Help wording and responsive-render review.
3. Add granted Distill only after derivation, export, retention, and target
   acceptance authority are explicit.
4. Re-run the closed `IMPORT-01` gate whenever either operation gains another
   public adapter or optional integration.
