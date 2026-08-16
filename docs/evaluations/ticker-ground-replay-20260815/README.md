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

The post-fix rerun and convergence assessment will be stored as
`actual-run.json`. Its round summary distinguishes improvements from genuine
FIT-to-non-FIT regressions and reports the final Fit status of the four
Examples whose outputs must remain unresolved.
