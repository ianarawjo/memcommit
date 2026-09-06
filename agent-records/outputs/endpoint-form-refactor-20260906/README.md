# Endpoint form refactor verification — 2026-09-06

This is agent-produced execution evidence for the structural extraction and
internal `compact` → `form` rename. No human review or approval is implied.

`compare_rendering.py` reconstructs the four former compact-package Python files
from commit `0d7ff831860c4e0d59faa83378ed216aa0757e7d` into a temporary package,
then compares that baseline with the current `endpoint_setup.form` components.
Both use the current operation specifications, command codecs, and shared
components. The baseline constructor accepts the typed spec directly; the
renamed layout discriminator and public dispatcher are covered by the caller
tests separately.

Run from the repository root:

```sh
PYTHONPATH=src python agent-records/outputs/endpoint-form-refactor-20260906/compare_rendering.py
```

The harness feeds ordered keys through real prompt-toolkit applications using
pipe inputs and a sized dummy output. It compares every character/style cell
and cursor coordinate on a 180-column × 52-row canvas, then compares returned
typed drafts. `render-comparison.json` retains the baseline revision, keys,
per-state cell hashes, and final drafts. Raw mismatch cells are written to the
harness's temporary directory if a comparison fails.

All 85 rendered states across eight paths matched. Six paths finish with a
validated draft (stored Memory, symmetric Meld, corrected inline command,
corrected Branch command, required Memory, and read-only evidence); projection
failure and browser/completion cancellation finish without a draft. Frozen
catalogs and Memory projections are synthetic. No real Profile, Context,
provider, or durable application is involved.

This is a rendered-cell equivalence check for unchanged interaction behavior,
not a PTY screenshot capture or evidence of durable operation execution.

The 118 existing Endpoint Setup, mode, Meld, Update, Sever, Branch, Reference,
Compare, and Audit tests also passed in the primary checkout. The initial
broader collection was temporarily blocked by unrelated Profile and History
imports during concurrent edits; the final complete run passed without changing
those modules in this task.
