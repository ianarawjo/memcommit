# a-is-apple transform-phase issues

Study: `study-long-audit-20260823`  
Frozen launcher: `env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/KimMunyeong/.codex/audit-snapshots/memcommit-study-long-audit-20260823-code python -m memcommit.cli`  
Scope: 120 actual attempts, 24 operations × 5 interleaved rounds. No code, test, commit, Profile, current Context, Undo, or Redo mutation was performed.

## AIA-T-ELABORATE-INVENTION-01 · provider invents alternatives to satisfy a rule

- Expected: With only `a → apple` and an abstract instruction about unresolved alternatives, Elaborate should preserve the absence of supplied alternatives or label a placeholder without creating candidate facts.
- Actual: Rounds 3 and 5 introduced `a → apricot`, `a → avocado`, and a same-initial-letter heuristic. Later Audit, Conformance, Forget, and Resolve all spent work analyzing or repairing those invented examples.
- Workaround: Treat Elaborate output as unverified, audit it before transfer, and remove invented cases with a checkpointed Forget.
- Severity: high.
- Reproduction: 2/2 materially comparable rule-to-cases attempts.

## AIA-T-ELABORATE-SCOPE-01 · abstract goal drifts outside the apple world

- Expected: “dual provenance” should either ask which two apple-world sources are meant or remain an explicitly incomplete draft.
- Actual: Elaborate created three generic policy-governance rules with no concrete apple source. Those rules later produced 8 ambiguity findings and 8 conflict pairs when combined with canonical-mapping rules.
- Workaround: Use exact source Contexts and a concrete rule instead of a free-standing goal; audit before merge.
- Severity: high.
- Reproduction: one direct attempt, with downstream confirmation by Atomize and Audit.

## AIA-T-FORGET-PROVENANCE-01 · provenance-sensitive Forget removes all atomized canonical facts

- Expected: Atomize children derived from the distilled canonical rule should retain enough visible lineage for “remove rules without preserved provenance” to keep or transform them conservatively.
- Actual: Forget removed all three canonical atomic mappings in round 2. The immediately following Impact, Meld, and Sever failed because their Source became empty.
- Workaround: checkpoint before Forget, phrase the criterion around concrete unwanted content, and review the Forget receipt before downstream use.
- Severity: high.
- Reproduction: one destructive attempt; three downstream failures confirmed the published empty state.

## AIA-T-MELD-PEER-01 · provider relation cannot satisfy the PEER-side decoder

- Expected: Meld should either produce a valid symmetric comparison or return an actionable relation-level review item.
- Actual: Round 4 failed with `Codex compare returned a cross-source relation without both PEER sides`; no useful relation was exposed for correction.
- Workaround: retain the two sources and retry as a new Meld session; do not materialize.
- Severity: high.
- Reproduction: 1/1 observed malformed-provider boundary.

## AIA-T-UPDATE-STAGE-01 · unrelated explicit routes collide with a persisted working stage

- Expected: Three explicit Source→Target routes should be independently previewable, or the error should identify the exact staged route that conflicts.
- Actual: Rounds 1–3 all failed with the same generic “applied update or local working copy has diverged” message and only suggested `--replace-stage`.
- Workaround: use `--replace-stage --direct` only after reviewing that replacement is safe; this succeeded in rounds 4–5.
- Severity: medium-high.
- Reproduction: 3/3 early routes; recovery verified 2/2 with explicit replacement.

## AIA-T-DIFF-ROUTE-01 · Diff entry grammar is hard to discover in automation

- Expected: A Context plus `--raw/--stat/--verbose`, or a plain explicit checkpoint, should lead to a usable noninteractive diff or a correction naming the required operand form.
- Actual: Four attempts split between usage rejection and “interactive history selection requires a terminal.” The fifth exact-looking checkpoint was interpreted as a Context.
- Workaround: first discover the full checkpoint contract from help/log output, then pass the exact supported history selector; this phase could not obtain a successful non-current route.
- Severity: medium-high.
- Reproduction: 5/5 failed with three different error shapes.

## AIA-T-CHECKPOINT-LOCATOR-01 · checkpoint prefix is interpreted as a Context

- Expected: After `checkpoint result` prints `017714b1`, `diff 017714b1` should recognize that prior output or explain the missing companion selector.
- Actual: Diff said Context `017714b1` was unavailable.
- Workaround: use a separately documented full diff selector rather than chaining the printed short UID directly.
- Severity: medium.
- Reproduction: 1/1 prior-output chaining attempt.

## AIA-T-RATIONALE-LIMIT-01 · valid rationale fails on provider verbosity

- Expected: Rationale should reconcile or retry a complete narrative to its declared 40-word output contract.
- Actual: The same stable Memory failed twice because the provider exceeded 40 words. Later scratch Memories succeeded, so the user cannot predict which ordinary Memory will render.
- Workaround: retry or use Trace; neither preserves the same explanatory narrative.
- Severity: medium.
- Reproduction: 2/2 attempts on `source:f9fbc251`.

## AIA-T-GROUND-DISCOVERY-01 · TUI reports no ordinary Context locators

- Expected: The 180×52 Ground discovery turn should list or recommend names from the existing local `audit/a-is-apple` hierarchy without opening Memory contents.
- Actual: The TUI stated “No ordinary Context locator names were found” despite the world’s source, working, archive, comparisons, and transform-scratch Contexts.
- Workaround: enter an exact new/local plan manually; no Ground was approved in this phase.
- Severity: medium-high.
- Reproduction: 1/1 actual TTY discovery attempt.

## AIA-T-GROUND-DENSITY-01 · initial TUI requires reading many mostly empty frames

- Expected: The initial discovery state should foreground the proposed Goal, Context choices, and exact approval boundary.
- Actual: One 180×52 screen rendered LOCATION, GOAL, CONTEXTS, RULES, MEMORIES, CHAT, and ACTION with large empty regions. The proposed command and “not created” boundary were visible but required scanning repeated empty-state copy.
- Workaround: use the non-TTY stable draft for quick inspection, or scan CHAT/ACTION and quit with Q.
- Severity: medium.
- Reproduction: 1/1 actual TTY attempt; cost was one key to close but multiple screen regions to inspect.

## AIA-T-AUDIT-OVERLOAD-01 · dense findings bury the next decision

- Expected: A late-state audit should preserve complete evidence while making the highest-impact required decisions immediately identifiable.
- Actual: Round 5 emitted more than 4,000 tokens for 15 Memories, 8 ambiguities, and 8 conflict pairs. Repeated full Memory text and pairwise findings dominated the output; there was no concise prioritized next-action summary.
- Workaround: consume the saved session in a viewer and review one category at a time.
- Severity: medium-high.
- Reproduction: 1 dense late-state attempt; smaller rounds showed the output grows sharply with findings.

## AIA-T-IMPACT-OVERLOAD-01 · one planned addition repeats many source blocks

- Expected: Impact should summarize a planned addition once and keep its many source references compact or expandable.
- Actual: A two-addition preview printed nine full source reference blocks for the first addition, including repeated Context identity and hashes.
- Workaround: read the summary first and use the exact detail only when provenance inspection is needed.
- Severity: medium.
- Reproduction: 1/1 populated Update Impact attempt.

## AIA-T-ZERO-JUDGMENT-NEXT-01 · “NEEDS INPUT” with no judgments

- Expected: If Meld has zero required and zero optional judgments, its receipt should say ready/no-input or name the concrete remaining action.
- Actual: Rounds 3 and 5 printed `MELD NEEDS INPUT` together with `REQUIRED 0 · OPTIONAL 0`.
- Workaround: inspect the saved Impact/session and avoid assuming that the label itself proves unresolved user work.
- Severity: medium.
- Reproduction: 2/2 successful Meld session creations.

## AIA-T-RESOLVE-AUTO-01 · Resolve applies an update without an intermediate decision receipt

- Expected: On a Context containing newly invented alternatives and an ambiguity, Resolve should expose what it will change before applying, or clearly identify why no user decision is required.
- Actual: Round 3 printed `APPLIED · UPDATE 1 · FIT YES` and only then supplied a checkpoint/review route.
- Workaround: checkpoint before Resolve and inspect the review receipt immediately after.
- Severity: medium.
- Reproduction: 1/1 non-no-op Resolve attempt.

## Safety and recovery evidence

- Destructive Clear was preceded by explicit checkpoints in rounds 4 and 5.
- Revert restored the exact pre-clear criteria and result states using `--keep`.
- Missing Delete/Revert targets failed without mutation.
- Granted or non-apple sources were never mutated.
- The shared current Context remained `practice`; every mutable operation used an explicit apple-local target.

