# Ground ticker 1-to-50 live-flow result

## Outcome

The current implementation can mechanically complete a live
Elaborate–Distill–Fit Ground loop with 50 reviewed synthetic Examples, but the
run exposed correctness and consistency gaps that prevent calling the flow
reliable yet.

The exact 50-Example Distill request failed on its first provider turn because
one Example appeared as both support and boundary for the same Rule. The local
decoder rejected the result and published no proposal or Ground revision. A
second invocation with the same Ground revision, Source, Goal, model, and
reasoning setting returned a different valid result and the flow then
completed. This demonstrates safe fail-closed validation, but not consistent
semantic output.

The final Fit receipt reported all 50 Examples as `FIT`. That result contains
clear false positives. In the 20-Example receipt, the judgment reason for
`Quantum-X Labs Corp. -> QXL` says the written Rule yields `QL, not QXL`, but
the status is still `FIT`. Later Rules also use nondeterministic wording such
as “typically its first digit” while Fit accepts exact numeric outputs. At 50
Examples, the Rule says embedded uppercase initialisms preserve their
constituent letters while accepting `Axiom AI Technologies -> AAT` and
`Deep Space XR Studios -> DSXS`, where only the first initialism character is
used. The typed decoder proves exhaustive rows and valid status tokens; it
does not prove that a free-text reason logically entails its status.

## Method

- isolated Store: `store/` under this directory;
- separate stale-Context branch: `stale-branch-store/`;
- provider: subscription-backed Codex;
- model: `gpt-5.6-sol`;
- reasoning: `none`;
- synthetic Example thresholds: `1, 4, 8, 12, 20, 35, 50`;
- one vague initial Goal: `Invent compact, consistent symbols for organization names.`;
- per round: add and ACCEPT Examples, Distill the complete INCLUDE set, REFINE
  and ACCEPT one reviewed composite Rule, run and save Fit, then Elaborate the
  Rule into unverified next-case suggestions; and
- no synthetic symbol is asserted to be an official exchange ticker.

The single composite Rule is a diagnostic workaround for a current Ground
limitation: there is no reviewed operation that replaces an active set of
independent Rules as one revision. The workaround uses only existing Ground
proposal, REFINE, ACCEPT, CAS, Distill, Fit, and Elaborate paths, but it should
not become the target product interaction.

## Round results

| Examples | Distilled Rules | Reviewed Rule chars | Fit status counts |
| ---: | ---: | ---: | --- |
| 1 | 1 | 121 | `FIT 1` |
| 4 | 1 | 200 | `FIT 3`, `NOT_APPLICABLE 1` |
| 8 | 3 | 424 | `FIT 8` |
| 12 | 3 | 611 | `FIT 10`, `UNDERDETERMINED 2` |
| 20 | 4 | 847 | `FIT 20` |
| 35 | 6 | 1,150 | `FIT 35` |
| 50 | 6 | 1,264 | `FIT 50` after one rejected exact Distill attempt |

There were 22 successful semantic turns, plus the rejected first 50-Example
Distill turn. Successful turns consumed approximately 271 seconds of provider
time. Seven immutable Fit receipts remain in the isolated Store. The final
Ground is revision 114 with 50 ACCEPTED Examples, one ACCEPTED composite Rule,
and status `OPEN`; counts never imply whole-Ground approval.

## Context-change branch

After the 20-Example round, the exact Store was copied and one Memory was added
to the bound `ticker/examples` Context. Provider-spy checks produced:

| Operation | Provider-free stale rejection |
| --- | --- |
| Ground Example edit | yes |
| Ground Distill | yes |
| Fit | **no**; provider factory was reached |
| Elaborate | **no**; provider factory was reached |

This confirms both the expected missing non-destructive binding refresh and an
additional cross-operation inconsistency. Fit and Elaborate do not currently
enforce the same bound-Context freshness gate as Ground mutation and Ground
Distill.

## Evidence

- `report.json` contains all 50 propositions, every round's Distill Rules,
  Elaborate suggestions, Fit judgments and reasons, timings, the first failure,
  retry provenance, and stale-branch results.
- `store/` retains the final Ground and all seven immutable Fit receipts.
- `stale-branch-store/` retains the exact post-mutation stale probe.
- `run_live_flow.py` and `resume_final_once.py` are the executable diagnostic
  harnesses. Both use explicit Store roots and suppress Study action recording
  so the active user Profile is not contaminated.
- The focused repository regression suite for Distill, Elaborate, Fit, Ground
  Example USE, TUI, public Python, and agent adapters passed: `74 passed`.

## Required follow-up before claiming the flow works

1. Add one reviewed Ground action for replacing/reconciling a complete Rule set
   instead of retaining a composite-Rule workaround.
2. Add the non-destructive Context-binding refresh described in
   `docs/ground-ticker-iterative-flow-todo.md`.
3. Apply bound-Context freshness before provider construction consistently in
   Fit and Ground Elaborate.
4. Strengthen Fit beyond schema/exhaustiveness so a judgment reason that
   contradicts its status cannot be accepted. A deterministic exact-output
   evaluator or a separately validated entailment step is needed; a second
   unconstrained semantic opinion alone would preserve the same failure mode.
5. Decide whether a schema-valid but semantically inconsistent Distill result
   should expose an explicit retry action. Do not silently retry and present the
   second answer as if the first contract violation did not occur.

