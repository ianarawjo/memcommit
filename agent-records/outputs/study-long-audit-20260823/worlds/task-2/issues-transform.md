# task-2 transformation/evidence issues

## T2T-ATOMIZE-HANG-01 — Whole-Context atomize can hang without progress or bounded failure

- Expected: `atomize --context result` completes, reports progress, or fails within a bounded provider timeout without publishing partial state.
- Actual: The seven-Memory attempt emitted nothing for more than 150 seconds and had to be interrupted. The empty Context and two exact single-Memory controls completed.
- Workaround: Use `impact atomize` first and then exact `--memory` atomization; preserve the Context checkpoint before retrying.
- Severity: High reliability and operator-attention cost.
- Reproduction: 1/5 attempts; four bounded controls.

## T2T-MELD-PREWARM-01 — Fresh symmetric Meld repeatedly fails before analysis

- Expected: Two explicit local peer Contexts and a fresh empty/new result enter Meld analysis or return a source/authority validation explaining the bad endpoint.
- Actual: Four accumulated-state attempts failed immediately with `Declared Compare prewarm is invalid`; the error did not identify which frozen input or prewarm invariant was invalid. A nonempty-result attempt separately produced a clear error.
- Workaround: Use Compare/Distill/Update separately and retain their receipts; no safe Meld recovery was discoverable from the error.
- Severity: High because the operation remained unusable throughout the phase.
- Reproduction: 4/4 fresh-result attempts, plus one distinct nonempty-result boundary.

## T2T-DIFF-ROUTE-01 — Noninteractive explicit Diff routes are not discoverable from errors

- Expected: A shared-current-safe invocation can name a Context and select stat/raw/verbose or a checkpoint pair directly.
- Actual: Context plus `--stat`, `--raw`, or `--verbose` was rejected; plain explicit Context required an interactive terminal; a checkpoint UID was interpreted as a Context. None of five attempts reached a diff.
- Workaround: Use checkpoint/revert receipts for recovery evidence; consult operation-specific help before a later serialized TTY audit.
- Severity: High for automated recovery audits.
- Reproduction: 5/5 attempts across flag, plain, and checkpoint-shaped routes.

## T2T-SESSION-ID-01 — Review receipts advertise short IDs that do not reopen saved sessions

- Expected: The displayed short session/receipt identifier is accepted when unambiguous, or the receipt prints the exact required identifier.
- Actual: `review audit --session 797d9148` and `review update --session a920e9d2` reported unavailable, although those exact short IDs were printed by the successful producer commands. Full/receipt-oriented Distill and Forget reviews succeeded.
- Workaround: Capture and reuse full UUIDs where the producer exposes them; prefer receipt review routes.
- Severity: Medium output-reuse and session-recovery defect.
- Reproduction: 2/2 short saved-session attempts; two receipt controls succeeded.

## T2T-AUDIT-OVERLOAD-01 — Audit becomes too large to guide the next action

- Expected: A saved audit exposes counts and prioritized next actions without forcing rereading its entire source snapshot and every finding.
- Actual: The 21-Memory audit exceeded capture limits, repeated the full snapshot, six redundancy groups, four ambiguities, and all pair counts. The actionable cleanup sequence was buried.
- Workaround: Use exact finder reports or the final smaller post-curation audit.
- Severity: Medium information-overload cost.
- Reproduction: One truncated large audit; four smaller-state controls remained readable.

## T2T-RATIONALE-LANGUAGE-01 — Rationale changes output language unexpectedly

- Expected: English Memory and English invocation produce English rationale unless a language is requested.
- Actual: The distilled rule's rationale returned in Chinese. Other rationale attempts were English.
- Workaround: Verify the source/trace directly or rerun with explicit language controls when available.
- Severity: Medium downstream reuse cost.
- Reproduction: 1/5 attempts with English controls.

## T2T-FORGET-SEMANTIC-SCOPE-01 — A duplicate-focused Forget instruction removes the general merge rule

- Expected: `remove any duplicate neutral rule` removes duplicate stored instances while retaining the general policy about merging equivalent advisor requirements.
- Actual: Forget deleted the unique general merge rule and edited the conditional rule to remove its reference to shared merging. The later review made the semantic interpretation visible, but only after mutation.
- Workaround: Use `find-duplicates`/`dedup` for stored duplicates; reserve Forget for content criteria whose semantic scope is explicitly reviewed.
- Severity: High intent-interpretation risk, contained to checkpointed scratch.
- Reproduction: One destructive semantic attempt; two no-change and one unrelated-case removal controls.

## T2T-ELABORATE-FABRICATION-01 — Rule elaboration invents domain cases not grounded in task-2

- Expected: Elaborating a generic provenance/condition rule produces clearly labeled abstract cases or cases grounded in the selected source.
- Actual: Inline rule elaboration invented minors/guardian-consent, identifiable-audio encryption, and school recruitment cases absent from the advisor corpus. They were marked unverified but later inflated audit, dedun, and Forget work.
- Workaround: Prefer goal/source-grounded elaboration and keep unverified cases isolated until reviewed.
- Severity: Medium evidence-noise and cleanup cost.
- Reproduction: One rule-to-cases attempt; later Forget removed three illustrative cases.
