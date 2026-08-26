# Ground Example USE toggle and Distill input

This ordered capture records the real named-Ground prompt-toolkit TUI and one
real exact CLI mutation in a 180-column by 52-row true-color PTY. The isolated
Store contains two reviewed ticker Examples. Both begin as `INCLUDE`; the
second row is toggled off, and a deterministic provider captures the exact
subsequent Ground Distill payload.

1. `01-selected-google-use-on` — `mem ground ticker-use`; after four Tabs and
   one Down, Google is the selected `[x]` row. No state has changed.
2. `02-exact-use-off-approval` — `Space`; the row remains `[x]` while the TUI
   displays the revision-guarded `--set-example-use ... --use EXCLUDE` command
   and its Fit/Distill effects. No state has changed yet.
3. `03-use-off-applied` — `A`; the approved command runs through
   `python -m memcommit.cli`, advances the saved Ground revision once, appends
   a Decision, and repaints Google as `[ ]`. Contexts and Context Memories are
   unchanged.
4. `04-distill-provider-verification` — `Q` closes the TUI, then the same saved
   Ground is frozen through the Ground Distill application adapter. The
   captured provider payload contains one Apple proposition and no Google
   text, proving that the unchecked Example was removed before provider
   connection.

Every step has a native-size PNG, extracted terminal canvas, and original ANSI
PTY stream. The exact command and provider call use the same temporary default
Profile Store, which is discarded after capture.
