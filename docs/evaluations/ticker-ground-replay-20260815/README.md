# Ticker Ground 5→50 provider replay

This directory records the real-provider evaluation of the frozen ticker
Ground workflow. Run it from the repository root with:

```bash
python docs/evaluations/ticker-ground-replay-20260815/run.py
```

The script uses the stored ChatGPT login through `CodexChatGPTProvider`, model
`gpt-5.6-sol`, reasoning `none`, and a fresh temporary Memory store. It does
not retain prompts, completions, credentials, or the temporary store. The JSON
records content-free call metadata plus the decoded Ground, Resolve, and Fit
ledger that crossed application validation.

Verify the retained records without making another provider call:

```bash
python docs/evaluations/ticker-ground-replay-20260815/verify.py
```

## First-run failure retained

[`failed-overlap-run.json`](failed-overlap-run.json) is the first unmodified
run record. Calls 1–14 completed through the 35-Example Fit. Call 15 returned a
schema-valid 50-Example Distill response, but local semantic validation found
that one late Example appeared in both the support and boundary lists of the
same Rule. Distill failed closed with no resulting Rule or partial Ground
revision.

The local disjointness invariant already existed, but the provider prompt had
stated only that cited and outside evidence must be disjoint. The follow-up
change explicitly states that one Rule's support and boundary lists are also
disjoint and advances the Distill provider contract version. The complete
replay is rerun from a fresh store rather than resuming after the failed
semantic turn.

## Completed run

[`actual-run.json`](actual-run.json) is the complete post-fix rerun. All 17
provider calls completed in 385.528 provider seconds. The resulting Ground has
50 separately accepted INCLUDE Examples, six separately accepted Rules, 112
semantic revisions, and 143 recorded workflow events. Each mutating event
advanced exactly one Ground revision; explicit Fit deferrals at rounds 3, 4,
and 5 changed none.

The per-round Fit results were:

| Included Examples | FIT | UNDERDETERMINED | CONTRADICTS |
| ---: | ---: | ---: | ---: |
| 5 | 5 | 0 | 0 |
| 10 | 10 | 0 | 0 |
| 20 | 18 | 2 | 0 |
| 35 | 33 | 0 | 2 |
| 50 | 48 | 0 | 2 |

No previously FIT Example became non-FIT in a later round. The two
underdetermined Examples at 20 became FIT at 35. All four intentionally
unsupported final boundaries (`t46`–`t49`) were FIT while their propositions
still said the output remained unresolved, so the workflow did not fabricate
transliteration, slash, debt-security, or unsupported-series policies.

The run did not fully converge:

- `t24` (`Gamma 24 Seven Corp.` → `G2S`) genuinely conflicts with an accepted
  Rule that says a standalone numeric token is preserved in full. A later
  reviewed Rule refinement is required.
- `t23` (`Beta X5 Labs LLC` → `BXL`) was labelled `CONTRADICTS`, but the same
  Fit judgment's reason says that `X5` contributes `X`, the result is `BXL`,
  and the Example is coherent. This is an internally inconsistent Fit verdict,
  not evidence that the Example or Rule should be silently rewritten.

The saved Goal also remained the original vague Korean sentence. The initial
five-Example Fit judged every Example FIT, so the replay's issue-triggered Goal
Resolve branch did not execute. Elaborate still produced Rules, but selecting a
Rule does not implicitly rewrite the Goal. This is useful negative evidence:
the current loop can accumulate evidence-bound Rules without guaranteeing that
the visible Goal becomes more precise. A later conversational policy must make
Goal refinement an explicit reviewed action rather than infer it from proposal
selection or rely only on a non-FIT trigger.
