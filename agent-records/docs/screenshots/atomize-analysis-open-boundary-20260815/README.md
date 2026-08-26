# Atomize analysis-open boundary capture

This ordered replay records the unchanged Atomize analysis surface after
moving saved reuse, hidden-prewarm materialization, and provider creation
behind `AtomizeAnalysisOpenRequest` and the production runtime port.

## Environment

- Capture date: 2026-08-15
- Command: `python agent-records/docs/screenshots/atomize-analysis-open-boundary-20260815/capture.py`
- PTY: real `pexpect` PTY, explicitly set and verified as `52 180`
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, and `NO_COLOR` removed
- Store: isolated temporary `MemoryStore` roots; no user Context was read or
  changed
- Provider: deterministic local Atomize provider; no network connection
- Harness: the production `impact.cmd` adapter in a minimal Typer root; the
  unrelated repository-wide Help inventory is intentionally disabled
- Prepared branch: an exact locally constructed match is injected at the
  runtime lookup seam; installed-registry validation remains covered by the
  Study prewarm tests
- Provenance: every PNG is rendered from its color-preserving `.typescript`;
  the matching `.txt` is the final visible-canvas projection

## Ordered interaction log

1. `01-provider-analysis-pending.png`
   - Command: `mem impact atomize --context atomize/open-boundary`
   - Visible state: existing provider progress surface before any analysis pair
     is published
   - Durable mutation: fixture only

2. `02-provider-analysis-workbench.png`
   - Visible state: unchanged read-only Atomize workbench from the completed
     provider result
   - Durable mutation: one analysis and matching workbench; no Context effect

3. `03-provider-analysis-receipt.png`
   - Preceding key: `q`
   - Visible state: `Analysis saved` receipt and explicit provider origin
     verification
   - Durable mutation: none after step 2

4. `04-saved-resume-workbench.png`
   - Command: the same Impact invocation against the saved pair
   - Visible state: the same workbench and analysis identity
   - Durable mutation: none; provider construction is configured to fail if
     attempted

5. `05-saved-resume-receipt.png`
   - Preceding key: `q`
   - Visible state: provider-free saved-resume receipt and same-analysis proof
   - Durable mutation: none

6. `06-exact-prewarm-workbench.png`
   - Command: the same Impact invocation with one exact hidden runtime match
   - Visible state: the prepared semantic report through the ordinary
     workbench, with no special hidden-session UI
   - Durable mutation: first visible analysis/workbench materialization only

7. `07-exact-prewarm-receipt.png`
   - Preceding key: `q`
   - Visible state: exact-prewarm first-use receipt, same analysis identity,
     and planned Output
   - Durable mutation: none after step 6; provider construction is forbidden

8. `08-explicit-refresh-pending.png`
   - Command: `mem impact atomize --context atomize/open-boundary --refresh`
   - Visible state: provider progress despite a current saved pair; refresh
     intentionally disables saved/prepared reuse
   - Durable mutation: none before completion

9. `09-explicit-refresh-receipt.png`
   - Preceding key: `q` after the refreshed workbench appears
   - Visible state: new-analysis receipt and changed analysis identity
   - Durable mutation: replacement analysis/workbench pair; no Context effect

10. `10-stale-saved-analysis-rejected.png`
    - Precondition: Source changes after a saved analysis
    - Visible state: stale error, exit 1, and original analysis retained
    - Durable mutation: Source fixture edit only; provider construction and
      derived-state replacement do not occur

11. `11-pair-publication-failure-restored.png`
    - Precondition: injected workbench publication failure after refreshed
      analysis persistence
    - Visible state: operation error and proof that both original analysis and
      original workbench were restored
    - Durable mutation: none after synchronous restoration

The script fails if the terminal is not 180×52 true-color, a saved or prepared
path constructs a provider, refresh reuses an old identity, stale state is
silently replaced, or pair publication leaves mixed revisions.
