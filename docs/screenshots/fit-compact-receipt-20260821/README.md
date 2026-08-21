# Fit compact receipt terminal evidence

This ordered set records the standalone Fit route after removal of its semantic
Viewer. Every capture uses a real color-capable `180 × 52` PTY with
`TERM=xterm-256color`, `COLORTERM=truecolor`, and `NO_COLOR` removed. PNGs are
rendered from the actual PTY stream; the adjacent text and typescript files
retain the plain canvas and raw terminal bytes. The compact line-oriented Fit
receipt styles only typed judgment tokens through the shared palette: `YES`
green, `MAY` yellow, and `NO` red. Everything else stays neutral, and the
adjacent plain canvas confirms that marks and labels remain the complete
information channel without ANSI.

Command:

```bash
python docs/screenshots/fit-compact-receipt-20260821/capture.py
```

| # | File | Exact command or route | Visible state | Durable mutation |
| --- | --- | --- | --- | --- |
| 01 | `01-provider-running` | `mem fit "The lobby closes at five." "Visitors may use the side entrance after five."` | One bounded whole-frame provider turn; no Viewer exists | none |
| 02 | `02-yes-receipt` | provider completion | One n-ary operator line: `FIT · YES · operand ↔ operand`; only `YES` is green | none |
| 03 | `03-issue-only-ground-receipt` | typed result of `mem fit --ground ticker` | Whole-operation header `FIT · NO · [GROUND CONTEXT ticker] · 1/3`, then one line per local `MAY` or `NO`; only those judgment tokens are colored and fitting detail is absent | none in the projection fixture |
| 04 | `04-stale-summary-only` | typed result of `mem fit --ground ticker --receipt <uid>` after revision drift | `FIT · STALE · [GROUND CONTEXT ticker] · 1/3`; neutral `STALE`, with old issue details suppressed | none |
| 05 | `05-repeated-operands-fit-yes` | `mem fit <uid-prefix> fit/current` | The same stored coordinate selected directly and through its Context remains two visible operands and returns `FIT · YES`; receipt count remains zero | none |
| 06 | `06-general-no-relation-receipt` | `mem fit "The main entrance closes from five until ten." "The main entrance stays open until ten."` | One operator line: `FIT · NO · [PROPOSITION p1] … ↔ [PROPOSITION p2] …` | none |
| 07 | `07-three-context-operands` | `mem fit context-a context-b context-c` | One n-ary line contains three typed Context-plus-Memory operands and two `↔` separators | none |

The general success, general conflict, and repeated-coordinate states cross
the production command and stored-source runtime. The Ground issue and stale states inject a fully typed
`FitResult` at the CLI receipt adapter so the presentation contract is
deterministic without creating a fake Ground receipt. Focus, scrolling,
clipboard keys, and close keys are absent because standalone Fit is no longer
an interactive surface.
