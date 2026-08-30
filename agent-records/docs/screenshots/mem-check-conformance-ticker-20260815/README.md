# Ticker `check-conformance` evaluation

> Historical experiment, captured 2026-08-15. The exact-output Case
> Conformance API was removed before distribution. These images,
> `actual-run.json`, and `capture.py` are preserved only as design evidence;
> the script is not a runnable contract for the current source tree.

This ordered 180x52 color-PTY capture reuses the exact twenty ticker examples
and five Rules from the preceding Distill evaluation. It constructs an isolated
typed Ground, then runs the real shared Conformance core twice with
`gpt-5.6-sol`, reasoning `none`:

1. `01-ground-rules-and-cases` — five active Rules and twenty Ground Memories
   with local expected outputs. No provider turn has occurred.
2. `02-case-provider-running` — Case Conformance receives the Rules and inputs;
   expected outputs are deliberately withheld.
3. The numbered `case-results` pages show all twenty frozen predictions and
   host-derived exact PASS/FAIL judgments.
4. `context-provider-running` — Context Conformance checks the original mapping
   Context against the five-Rule Context.
5. `context-conformance-report` — one typed judgment per Rule with evidence
   counts and reasons.
6. `read-only-verification` — complete judgment counts and unchanged Ground,
   examples, and Rules records.

Every step has a native-size PNG, extracted terminal text, and original
true-color PTY stream. `actual-run.json` contains both complete typed reports.
The temporary Store is deleted after capture; the user's active Profile is not
read or changed.

## Observed result

Case Conformance returned 16 `PASS`, three `AMBIGUOUS`, and one `FAIL`. The
three single-word examples were ambiguous because the distilled Rule required a
three-letter mnemonic but did not specify how to choose its letters. The
previously suspected `Axiom AI Technologies Inc.` case failed exactly:
the Rules predicted `AAIT` while the frozen expected output was `AAT`.

Context Conformance returned five `CONFORMS` judgments. In particular, it
interpreted `AI` as contributing the single component `A` and therefore did not
flag the executable mismatch. This contrast exposed that exact-output execution
was a different operation from Rule/Context Conformance. Because the physical
Ground model now stores proposition Examples and the prototype had not been
distributed, the Case replay branch was removed instead of retained as a
compatibility mode.
