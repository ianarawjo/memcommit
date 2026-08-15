# Ground Cases Fit receipt projection

This ordered capture records the real named-Ground prompt-toolkit TUI in a
180-column by 52-row true-color PTY. It uses an isolated Store and a delayed,
deterministic provider so the adapter's running state can be captured without
introducing provider variability. The preceding ticker Conformance capture and
the later end-to-end Ground rebuild capture exercise the real configured model.

1. `01-cases-before-fit` — `mem ground ticker-fit`; Tab was pressed four times
   to focus the saved Memories/Cases pane. No Fit receipt exists and nothing
   has mutated.
2. `02-fit-running` — `F` was pressed. The operation-owned TUI calls the Fit
   application service directly; the Ground and all Contexts remain unchanged.
3. `03-current-fit-receipt` — the immutable receipt is saved and the selected
   Case projects `FIT`, cited Rule aliases, reason, and the current receipt ID.
4. `04-stale-after-rule-change` — a separately saved Rule revision follows the
   receipt. Reopening the same Ground preserves the prior receipt but projects
   it as `STALE · FIT`; no old judgment is presented as current.

Every image has the native-size PNG, extracted terminal canvas, and original
ANSI PTY stream. The two temporary Stores are discarded after capture. This
capture performs no Context mutation, Ground approval, checkpoint creation, or
current-Context switch through the Fit action itself.
