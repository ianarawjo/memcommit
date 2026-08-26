# Historical Fit stored-source Viewer evidence

> Superseded: this set records the removed Viewer-era interface. Its overlap
> failure in state 05 is no longer current behavior; repeated or overlapping
> stored coordinates now remain explicit n-ary Fit operands and are shown in
> `agent-records/docs/screenshots/fit-compact-receipt-20260821`.

This ordered set records general Fit automatically classifying one
current-Context Memory UID and one readable Context positional operand. The command
runs in a real `180 × 52` color-capable PTY with an isolated temporary Store
and deterministic delayed provider. `TERM=xterm-256color`,
`COLORTERM=truecolor`, and prompt-toolkit 24-bit color are enabled;
`NO_COLOR` is removed. PNGs are rendered from the retained ANSI PTY stream.

Command:

```bash
python agent-records/docs/screenshots/fit-stored-sources-20260820/capture.py
```

The representative success path starts with current Context `fit/current`.
The UUID-shaped operand names the current Context's only direct Memory, while
`fit/policies` contributes that Context's only direct ordinary Memory. General
Fit remains process-local and creates no receipt or checkpoint.

| # | File | Exact command / preceding keys | Visible state | Durable mutation |
| --- | --- | --- | --- | --- |
| 01 | `01-provider-running` | `mem fit a66e8b54 fit/policies --tui`; no key | Command and verified `180×52` PTY size; one whole-frame provider turn is running | none |
| 02 | `02-judgment-entry` | provider completion; no key | Viewer enters on Judgment with `YES`; both frozen stored inputs remain visible with public Context and Memory UID provenance | none |
| 03 | `03-frozen-stored-inputs` | `Down` | Complete Frozen Input owns focus; both exact Memory bodies use the shared Memory-object style | none |
| 04 | `04-close-read-only-verification` | `q` | Actual `mem show` output proves both Contexts unchanged; provider calls `1`, Fit receipts `0` | none |
| 05 | `05-overlap-blocked-before-provider` | historical `mem fit ee1f9af8 fit/current --plain`; no key | Superseded Viewer-era behavior: overlap failed locally. Current Fit preserves both occurrences as operands and returns an operation-wide verdict | none |

UID prefixes vary when the capture is regenerated because the isolated fixture
creates fresh identities. The interaction order, source roles, Context names,
provider count, and mutation evidence remain stable.

Context operands are direct-only in this slice. The capture deliberately does
not imply lexical-descendant, embedded-Context, Memory-reference, or QUERY-only
traversal.
