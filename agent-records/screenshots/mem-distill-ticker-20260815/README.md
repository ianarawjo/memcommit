# Ticker-example Distill evaluation

This ordered snapshot set evaluates Distill against twenty synthetic
company-name-to-ticker examples. The examples are generative design cases, not
claims about official market symbols. The explicit Goal asks for deterministic,
reusable rules and for important boundaries or exceptions.

The evaluation runs the real Distill application and output adapter against an
isolated temporary `MemoryStore`. It connects to the actual subscription-backed
Codex provider with `gpt-5.6-sol` and reasoning `none`. Direct application
composition is used so the evaluation can pin that model without changing the
user's global provider configuration. It exercises the same Source freezing,
whole-frame provider contract, decoder, revalidation, renderer, Apply adapter,
CAS, and checkpoint path used by `mem distill`.

Capture environment: repository root, `180x52` PTY,
`TERM=xterm-256color`, `COLORTERM=truecolor`, and `NO_COLOR` removed. Every
numbered step has a native-size PNG, extracted terminal text, and original
color-preserving PTY byte stream. `actual-run.json` preserves the complete
typed result with readable evidence aliases.

1. `01-source-context-and-goal` — isolated Source Context containing all twenty
   cases and the exact Distill Goal; no provider turn or mutation yet.
2. `02-provider-turn-running` — one `WHOLE_FRAME_ONLY` provider turn starts
   with all twenty cases; no Result has been published.
3. `03...reviewed-rules-page-01` and following numbered Rule pages — the actual
   decoded Rule set, complete rationales, and support/boundary aliases. `N`
   advances through every page.
4. The final `...verification` capture — exact evidence accounting, unchanged
   Source, temporary require-new Result equality, and checkpoint confirmation.

The temporary Store is deleted after the run. No Context in the user's active
Profile is read or changed.

## Observed result

The actual run compressed the twenty examples into five Rules. All twenty
Source Memories were cited as support or boundary evidence, none was silently
omitted, the Source record remained unchanged, and the five temporary Result
Memories exactly matched the five reviewed Rules.

The normalization, single-word, share-class, and non-official-symbol boundary
Rules cleanly fit their cited examples. One phrase is semantically too strong:
the multiword-initial Rule says to preserve a
meaningful abbreviation such as `AI` as a component even though the example
`Axiom AI Technologies → AAT` contributes only `A` from that token. The
evidence-coverage contract detects omissions and invalid aliases, but it does
not yet prove that every natural-language Rule is exactly entailed by its cited
examples. This run therefore verifies the execution and traceability contract
while also exposing a useful semantic-reconciliation limitation.
