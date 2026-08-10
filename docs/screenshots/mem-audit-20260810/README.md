# `mem audit` real-session capture

This record verifies one real provider-backed Audit over an existing Sever
result Context. It preserves the setup screen, all three execution stages, the
combined report, an actionable finding detail, the saved receipt, an exact
saved-session reopen, and the non-interactive saved snapshot.

## Environment

- Date: 2026-08-10
- Repository: `/Users/KimMunyeong/Github/memcommit`
- Profile: `study-alt-20260810-t3-find-additive`
- Current Context at setup: `task-3/local/personal-memory`
- Frozen Audit Source: `task-3/local/results/additive-final`
- Source shape: 3 direct Memories; descendants and embedded Contexts excluded
- Provider: `codex_chatgpt:gpt-5.6-sol`
- Reasoning effort: `medium`
- PTY: 180 columns x 52 rows, verified through the spawned PTY dimensions
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` removed
- Capture provenance: the real color-preserving PTY byte stream was replayed
  with `pyte` and rendered at 1980 x 1092. The matching raw `.typescript` and
  plain `.txt` state accompany every PNG.

The capture driver invokes the repository entry point as
`python -m memcommit.cli` so it can own and record the PTY. This is the same
project CLI used by `mem`; the ordinary `mem audit` command was also exercised
before the capture run.

## Commands and interaction

1. `mem audit`
   - Captured the initial shared Context selector and `RUN AUDIT` action.
   - Sent `Escape` to cancel without executing.
2. `mem audit --context task-3/local/results/additive-final`
   - Waited through Duplicate and Ambiguity without replacing the progress
     surface.
   - Captured the one cumulative `1 → 2 → 3` surface during Conflict.
   - Sent `H` during Conflict and captured the live read-only Help inventory.
   - Sent `H` again and captured the same cumulative progress surface restored.
   - Captured the complete saved Audit report.
   - Sent `Tab`, `Down`, `Enter` to open the one Ambiguity item.
   - Sent `Escape`, `Escape` to return and close the saved workbench.
3. `mem review audit --session 571fd0b4-64b0-4720-af65-f7964261d655`
   - Reopened the exact durable Audit session.
4. `mem review audit --session 571fd0b4-64b0-4720-af65-f7964261d655 --snapshot`
   - Printed the same durable Audit as a non-interactive snapshot.

## Observed result

- Audit UID: `571fd0b4-64b0-4720-af65-f7964261d655`
- Duplicates: complete, 0 findings
- Ambiguities: complete, 1 finding
- Conflicts: complete, 0 findings
- Review obligation: 0 required, 1 optional
- Saved responses: 0/1
- Materialization: none; the Audit has no whole-set apply action
- Source mutation: none; no Context or Memory change and no checkpoint
- Saved Source digest:
  `845964d596076789b00507393b63b4e78d9c70aa1b9445af61f79567520b18c5`
- Live Source digest after Audit:
  `845964d596076789b00507393b63b4e78d9c70aa1b9445af61f79567520b18c5`

The one finding concerns the phrase `the day before`. It is classified
`SINGLE / HELPFUL`: the calendar-day reading is dominant, but the reminder
time is unspecified. The Review asks, "What time on the day before should the
reminder be scheduled?" and offers the dominant reading as an optional
response.

The saved report retains the frozen Source, all three completion/count rows,
each ruleset version, provider/model/reasoning provenance, the finding, its
review state, and the model-assisted/non-proof boundary. Reopening by UID and
printing with `--snapshot` both reproduced those fields.

## Capture index

- `01-audit-setup`: common Context selector plus `RUN AUDIT`
- `02-audit-checks-sequence`: Duplicate and Ambiguity complete, Conflict
  running on the same numbered surface
- `03-help-during-audit`: shared read-only Help while Conflict continues
- `04-audit-checks-restored`: the same numbered surface restored after `H`
- `05-complete-audit-report`: unified report and derived `COMPLETE` action
- `06-review-ambiguity-1`: classification, evidence, reason, question,
  proposed reading, and inline Response field
- `20-audit-saved-receipt`: saved-without-mutation receipt
- `21-saved-review-reopened`: exact durable session reopened by UID
- `22-saved-review-snapshot`: durable non-interactive snapshot

During visual verification, the common workbench initially projected a
phantom `RESOLVE ALL` row even though Audit deliberately has no whole-set
strategy. The Audit adapter was corrected to derive the action from its real
capabilities; the final report and reopened-session captures above were then
regenerated and show `COMPLETE` instead.
