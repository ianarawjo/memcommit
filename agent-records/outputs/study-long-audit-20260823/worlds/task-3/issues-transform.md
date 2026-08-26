# task-3 transformation/evidence issues

## T3T-ELABORATE-HALLUCINATION — Elaboration invents healthcare circumstances and presents them as facts

- Expected: Elaborating privacy/disclosure criteria may add review examples, but it must preserve epistemic status and must not invent a confirmed visit, treatment, access condition, diagnosis, or symptom.
- Actual: Three Context-derived trials added unsupported assertions: rounds 1 and 3 asserted an explicitly confirmed/upcoming clinic purpose, and round 4 asserted current treatment, step-free access, stairs, and knee pain. Those details were absent from the scratch Source and Criteria. A round-5 inline anti-inference rule produced examples explicitly labelled suggested/unverified, showing a safer achievable form.
- Workaround: Treat Elaborate output as untrusted suggestions, inspect every output against exact Source Memories, and require explicit uncertainty labels before retaining anything. Do not use it directly as a disclosure source.
- Severity: **P1 / high** healthcare privacy and factual-integrity risk.
- Reproduction: **Yes, 3/5 materially different trials** produced unsupported factual assertions.

## T3T-DISTILL-GOAL-DRIFT — Distillation drops minimum-necessary and withholding constraints

- Expected: A goal that says minimum necessary, first-party only, or withhold until purpose/approval is confirmed must control the result's dispositions, not merely its prose style.
- Actual: Round 1 generated rules to disclose the brother's transport and medication details despite the minimum-necessary goal. Rounds 4 and 5 generated uncertainty/style rules but omitted the requested withholding-until-purpose-and-approval boundary.
- Workaround: Use Distill only to draft candidate language; independently compare every result with exact exclusion criteria and keep external publication blocked.
- Severity: **P1 / high** because omitted constraints can turn a relevant fact into an apparently approved disclosure.
- Reproduction: **Yes, 3 materially different goals**.

## T3T-RESOLVE-UNSUPPORTED — Corrective guidance can return FIT/NO CHANGE while challenged claims remain

- Expected: When an exact derived Memory is explicitly identified as unsupported and the guidance names the claims to remove, Resolve either proposes a grounded correction, reports why the selected scope cannot repair it, or fails closed.
- Actual: Round 2's whole-result instruction to remove inferred upcoming purposes returned `FIT · YES · NO CHANGE`. Round 4's exact instruction naming treatment, step-free access, stairs, and knee pain also returned `FIT · YES · NO CHANGE`; all claims remained. Round 3 correctly requested grounding, and round 5 correctly reported that related immutable items were outside the selected scope.
- Workaround: Do not accept FIT as proof that correction occurred. Re-open the exact result, check the challenged strings, broaden the mutable frame deliberately when necessary, and require a visible edit/removal proposal.
- Severity: **P1 / high** because a supposed correction path can silently preserve invented healthcare facts.
- Reproduction: **Yes, 2 unsafe no-change outcomes**, with 2 contrasting fail-closed outcomes.

## T3T-AUDIT-CURATION — Audit output does not directly produce a disclosure-safe disposition

- Expected: An audit used for healthcare sharing clearly separates include, exclude, verify, and require-approval outcomes and keeps missing purpose/currency prominent.
- Actual: The first and fifth Source-vs-Criteria audits usefully found missing purpose/currency, but did not produce an executable minimum-necessary disposition. The archive trial focused on exact duplicates, the criteria-only trial called all abstract safeguards underspecified, and the large mixed-result trial spent 27.89 seconds before failing because the provider returned a question for `NONE`.
- Workaround: Use Audit as evidence only. Apply explicit local curation criteria, inspect exact Memories, and keep transfer blocked until recipient, purpose, currency, and approval are independently confirmed.
- Severity: **P2 / medium-high** decision and reliability cost; publication remained fail-closed.
- Reproduction: **Yes, cross-scope usability limitation in 4 successful trials; 1 provider-contract failure**.

## T3T-CONFORMANCE-OVERLOAD — Pairwise conformance output is repetitive and can fail exhaustive coverage

- Expected: The command summarizes repeated missing-evidence findings, foregrounds distinct actionable gaps, and guarantees complete typed coverage of every target.
- Actual: Round 1 printed ten near-identical `INSUFFICIENT_EVIDENCE` entries for a five-by-four frame. A later accumulated-result trial failed because the provider did not account for every target Memory. Narrow inline/exact-criterion trials completed, but still required manual interpretation rather than a disclosure disposition.
- Workaround: Check one narrowly scoped rule at a time, preserve the full frozen input list, and manually reconcile per-Memory results before relying on the report.
- Severity: **P2 / medium** information-overload and completeness risk.
- Reproduction: **Yes, 1 repetitive complete matrix and 1 incomplete large-frame failure**.

## T3T-CHECKPOINT-SET-UID — A displayed recursive checkpoint-set identifier is not accepted by Revert

- Expected: The identifier printed by recursive Checkpoint is directly reusable by Revert, or the receipt lists the child checkpoint identifiers/required syntax.
- Actual: `checkpoint ... --recursive` printed set UID `777af68d`; `revert 777af68d --context ... --keep` could not resolve it. Direct Context checkpoints `238eb6bd`, `16d90912`, `612e09c8`, and `9fbd9e78` were all reusable successfully.
- Workaround: Before each destructive exact-Context action, create a direct checkpoint for that Context and use its UID. Do not depend on the recursive set UID for recovery.
- Severity: **P1 / high** recovery-contract defect for subtree operations.
- Reproduction: **One recursive-set failure; 4/4 direct checkpoints provide the contrasting working route**.

## T3T-DIFF-ROUTE — Diff's checkpoint and noninteractive routes are hard to discover and output is expensive

- Expected: A Checkpoint receipt can be piped into a noninteractive Diff, and an explicit Context supports a concise summary mode without requiring a TTY.
- Actual: Explicit Context plus `--stat` was rejected; non-TTY `diff CONTEXT` required an interactive terminal or an unspecified explicit checkpoint form; passing checkpoint UID `16d90912` positionally was interpreted as a Context. The two real 180×52 truecolor TUI runs succeeded, but the 25-Memory recovery case required navigation through a dense change report and 13 history items.
- Workaround: Use a real color PTY, open Diff with the exact Context, select the checkpoint interactively, and keep the direct Checkpoint receipt separately for Revert.
- Severity: **P2 / medium-high** recovery discovery and operation-cost issue.
- Reproduction: **Yes, 3 CLI route failures and 2 successful TUI trials**.

## T3T-REVIEW-ARTIFACT — Printed semantic session/receipt identifiers are inconsistently reviewable

- Expected: Any operation that prints a session or receipt plus a `mem review ...` affordance can be reviewed later with that exact identifier, with clear incomplete/applied state.
- Actual: Audit session prefix `9ae79761` and Update receipt `72ed1283` were reported unavailable to Review. Sever correctly rejected review before execution, and Atomize Context review succeeded after Apply. `impact update --session 5c0e2d19` could still locate an applied Update that Review could not locate through the tested receipt route.
- Workaround: Immediately snapshot successful reports, prefer the operation-specific exact review route when documented, and do not assume every printed identifier belongs to Review's artifact namespace.
- Severity: **P2 / medium-high** independent-review and output-reuse defect.
- Reproduction: **Yes, 2 unavailable artifacts**, plus working Atomize and state-aware Sever contrasts.

## T3T-MELD-RELIABILITY — Meld fails across valid-looking Context and stale-session paths

- Expected: Valid exact local frames produce a reviewable Meld proposal or a stable typed semantic finding; stale prior work exposes one clear restart action.
- Actual: The first Context-pair trial failed on an invalid provider relation, and a fresh two-Context target failed during Compare prewarm. An inline rule succeeded, a second inline source was blocked because the target retained another Meld's source identity, and explicit `--restart` finally produced a READY proposal.
- Workaround: Keep inputs narrow, retain the target's active session identity, and use explicit `--restart` when deliberately replacing stale analysis.
- Severity: **P2 / medium-high** reliability and re-entry cost.
- Reproduction: **Yes, 2 semantic failures and 1 stale-session failure; 2 inline success routes**.

## T3T-GROUND-STATE — A created named Ground cannot be edited through its later revision route

- Expected: After successful named creation at revision 0, later `--snapshot` and `--add-rule --if-revision 0` commands resolve the same durable Ground and either apply or report a revision/staleness conflict.
- Actual: Round 3 created `task3-healthcare-transform` revision 0 and round 4 read it as STALE. Round 5 then said to create the Ground workspace before applying the local rule edit. The command therefore appeared to lose the durable edit target while retaining snapshot state.
- Workaround: Preserve the original creation receipt and avoid relying on local edits in this audit. Keep the safety rule as an explicit scratch criterion instead.
- Severity: **P2 / medium-high** durable workflow-state inconsistency.
- Reproduction: **One edit failure after two successful reads of the named Ground**.

## T3T-RATIONALE-LIMIT — Rationale's default narrative bound can make ordinary provenance fail

- Expected: A simple one-event copy provenance fits the default projection bound deterministically, or the command returns a bounded recorded-only projection without calling a provider.
- Actual: The first JSON call failed because the provider exceeded the default 40-unit complete-narrative limit. Explicit 80/120-word calls succeeded, and the final JSON call produced a 45-word recorded-only projection with inference `NOT_REQUESTED`.
- Workaround: Supply an explicit word limit large enough for the deterministic recorded projection and inspect `inference_status`/projection status in JSON.
- Severity: **P2 / medium** surprising failure and retry cost; no fabricated provenance was published.
- Reproduction: **One default-bound failure; 3 explicit-bound successes**.

## T3T-RATIONALE-SEMANTIC-WARNING — Provenance explains origin without warning that derived content was unsupported

- Expected: Rationale distinguishes “this text was produced by operation X” from “this claim is grounded by Source evidence,” especially when the chosen Memory was generated by Elaborate.
- Actual: Rationale for the invented treatment/access/knee-pain Memory accurately described its operation origin but did not warn that its factual content had no support in the input criteria. A reader could mistake recorded derivation provenance for evidentiary validation.
- Workaround: Pair Rationale with exact Source/criterion inspection and conformance; never treat an operation event as factual support.
- Severity: **P2 / medium-high** epistemic-clarity risk.
- Reproduction: **One exact unsupported derived Memory; the issue is independently evidenced by the preceding Elaborate input/output**.

## T3T-TRACE-LIMIT — JSON Trace ignores the requested compact limit

- Expected: `--limit 1` bounds a machine-readable trace or clearly defines the limit as affecting only a named subfield.
- Actual: The final exact-child JSON trace with `--limit 1` returned the full component set, both events, analysis, source spans, and child evidence (1,737 output tokens). Earlier JSON/plain deep traces similarly required hundreds of tokens, making direct output chaining expensive.
- Workaround: Parse only the required typed fields and carry exact UIDs forward; use plain mode for a compact human check.
- Severity: **P2 / medium** information-overload and output-reuse cost.
- Reproduction: **Yes, 2 JSON traces and 1 verbose trace were large; the final minimal-limit case is direct evidence**.

## T3T-ATOMIZE-EMPTY — Empty Atomize publishes an applied receipt and checkpoint

- Expected: Atomizing a Context with zero direct Memories is an explicit no-op and creates no semantic Apply/checkpoint artifacts.
- Actual: The empty `transform-scratch` parent reported `ATOMIZE APPLIED · 0/0` and created receipt `a765244d` plus checkpoint `7c541d30`.
- Workaround: Preflight with exact `list` and skip Atomize when the direct frame is empty.
- Severity: **P3 / low-medium** audit noise and unnecessary durable history.
- Reproduction: **One intentional empty-boundary trial**.

## T3T-SEVER-CLASSIFICATION — Safe fail-closed result is accompanied by misleading exclusion labels

- Expected: Sever keeps Source unchanged, creates a separate reviewed Result, and explains each exclusion using the exact missing-purpose/approval criterion without misclassifying first-party access facts.
- Actual: The round-2/4 analysis and Impact classified all three candidates FORGET, which was safe under missing purpose/approval. However, it described the clinic/reception access facts as unnecessary third-party logistics even though they are first-party-relevant environmental/access facts. Final Apply correctly created a separate empty local result and left Source unchanged.
- Workaround: Accept the empty result as fail-closed, but do not reuse the provider's category labels. Re-evaluate exact candidates only after recipient, purpose, currency, and approval are supplied.
- Severity: **P2 / medium** explanation-quality issue; materialization safety behavior was correct.
- Reproduction: **Yes, the classification persisted across Ready, Impact, Resume, and Apply**.

## T3T-RESULT-OVERLOAD — A single transform target mixes evidence, rules, examples, and copies

- Expected: Accumulated transform output remains independently reviewable by type/phase, and later semantic operations can identify what is evidence versus a rule or example.
- Actual: `result` grew to 25 mixed Memories. Diff showed 25 removals plus 13 history entries, Check Conformance could not cover the whole frame, Meld Impact showed only 1/24 coverage, and Revert abbreviated 38 effects. Dedun later collapsed 7 redundancies to 3 survivors before Merge re-added the three exact Source facts, but its concise receipt did not expose enough mapping for direct review.
- Workaround: Use separate Contexts for source evidence, criteria, generated examples, and reviewed disposition; checkpoint each exact target before semantic cleanup.
- Severity: **P2 / medium-high** information architecture and review-cost issue.
- Reproduction: **Yes, observed across Diff, Conformance, Meld Impact, Revert, Dedun, and Merge**.

## T3T-RESOLVE-OPAQUE — FIT/NO CHANGE exposes no per-Memory safety disposition

- Expected: A whole-Source safety instruction produces an inspectable keep/change/drop decision for each input or identifies the evidence it evaluated.
- Actual: Round 1 printed only `FIT · YES · NO CHANGE` for the three candidate Source Memories; it did not show how missing approval, purpose, currency, or recipient applied to any Memory.
- Workaround: Treat the result only as a no-mutation receipt and use exact-Memory review plus explicit criteria for the actual disclosure decision.
- Severity: **P2 / medium-high** explainability risk.
- Reproduction: **One whole-Source trial; the same terse FIT/NO CHANGE form recurred in the unsafe corrective trials recorded under T3T-RESOLVE-UNSUPPORTED**.

## T3T-IMPACT-PRESENTATION — Impact wraps decision text mid-token

- Expected: A safety preview remains scannable and copyable at ordinary terminal width, with action, Memory, and reason boundaries intact.
- Actual: The round-1 Forget Impact wrapped words mid-token across the three DROP proposals, slowing comparison of already dense decisions.
- Workaround: Use the exact source list beside the preview and widen/copy the terminal output before reviewing it.
- Severity: **P3 / low-medium** presentation and review-cost issue.
- Reproduction: **One narrow rendered preview; later saved-session Impact routes exposed different reports**.

## T3T-UPDATE-STAGE — Direct Update requires hidden prior-stage recovery knowledge

- Expected: A direct exact-frame Update either evaluates the current frozen frames or names the conflicting stage and offers a clear safe next command.
- Actual: The first direct call rejected the target as divergent from a prior working copy. Recovery required discovering and adding `--replace-stage`; subsequent calls then applied as NO CHANGE.
- Workaround: Preserve the failure receipt, inspect current target state, and use `--replace-stage` only after deliberately accepting replacement of the stale process stage.
- Severity: **P2 / medium** re-entry and state-clarity cost; no partial update occurred.
- Reproduction: **One deterministic stale-stage failure followed by 4 safe replace-stage calls**.

## T3T-DEDUN-RECEIPT — Semantic cleanup counts are not enough for direct result reuse

- Expected: When Dedun absorbs seven Memories, the receipt identifies each kept UID and every absorbed-to-kept mapping so Review, Trace, and later Merge can reuse the result without another List/Show pass.
- Actual: The late trial reported only `absorbed 7 · kept 3` plus a checkpoint. The next structural Merge re-added all three exact Source Memories, but the concise Dedun output did not let the audit determine which semantic items survived without rereading the Context.
- Workaround: Checkpoint first, then run exact List/Show or Review immediately after Dedun and record survivor UIDs before another mutation.
- Severity: **P2 / medium** output-reuse and independent-review cost.
- Reproduction: **One actual multi-absorption trial; earlier no-op trials did not exercise the receipt boundary**.

## Safe transformation outcome

No external healthcare transfer was attempted. All destructive testing stayed inside `task-3/local/transform-scratch`; the original personal-memory fixture and granted remote Contexts were not mutated. Scratch Source retained only three first-party access-related facts after third-party transport and unverified medication details were removed. Because recipient purpose, currency, and explicit approval remained unconfirmed, final Sever materialized a separate empty local result (`KEEP 0 · FORGET 3`) and preserved Source unchanged.
