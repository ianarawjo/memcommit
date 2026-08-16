# Named Ground Fit Resolve capture

This ordered set records the real `run_named_ground_shell` workbench and the
real Ground Resolve application boundary. The capture harness creates a
temporary isolated store, saves one current non-FIT receipt, then opens the
same named-Ground adapter used by `mem ground`. Resolve application executes
the production planner, exact review, bound-Context checks, and Ground CAS; it
does not use a fake provider or synthetic screen renderer.

- Driver command: `python docs/screenshots/mem-ground-fit-resolve-ticker-20260815/capture.py`
- Child command: `python .../capture.py --child TEMP_STORE`
- PTY: `180` columns × `52` rows, verified through the spawned PTY dimensions
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, 24-bit prompt-toolkit
  depth, and `NO_COLOR` removed
- Ground: `ticker-fit-resolve`, initially revision `2`
- Bound Contexts: `test/ground/ticker-description`,
  `test/ground/ticker-examples`, and `test/ground/ticker-output`
- Initial Fit: current `UNDERDETERMINED` receipt for Example `c1`
- Temporary store: removed after capture

## Ordered interaction log

1. `01-current-nonfit-example.png`
   - Preceding keys: `Tab` × 4 from the initial Message composer.
   - Visible state: Memories focused; `c1` shows current issue mark `!`.
   - Durable mutation: none.
2. `02-fit-resolve-menu.png`
   - Preceding key: `X`.
   - Visible state: exact Fit reason and observed result; choices are Goal,
     each cited Rule, Example, USE, and Defer. The selected Goal row is only a
     cursor; nothing is applied.
   - Durable mutation: none.
3. `03-cited-rule-inline-editor.png`
   - Preceding keys: `Down`, `Enter`.
   - Visible state: cited Rule `r1` opens in the existing Rules-pane direct
     editor. The transient choice list has closed.
   - Durable mutation: none.
4. `04-edited-rule-not-saved.png`
   - Preceding text: ` Replace the single-word boundary with its first three letters.`
   - Visible state: replacement text remains editable and unsaved.
   - Durable mutation: none.
5. `05-exact-command-review.png`
   - Preceding key: `Enter`.
   - Visible state: `PROPOSED COMMAND · NOT RUN` with the exact Ground version
     guard and one `REFINE` action.
   - Durable mutation: none.
6. `06-effects-review.png`
   - Preceding key: `Right`.
   - Visible state: one Rule will reopen as `PROPOSED`; the old Fit receipt is
     retained and becomes stale; other Ground items and Contexts are unchanged.
   - Durable mutation: none.
7. `07-applied-stale-fit.png`
   - Preceding key: `Enter` on exact approval.
   - Visible state: `APPLIED · RESOLVE_REFINE_RULE`, Ground revision `3`, and
     `c1` now shows stale mark `◷`.
   - Durable mutation: exactly one Ground revision; no Context mutation.
8. `08-stale-fit-detail.png`
   - Preceding key: `Enter` on `c1`.
   - Visible state: the selected Example detail retains `FIT · ◷`; the Apply
     receipt remains visible in Chat.
   - Durable mutation: none.
9. `09-read-only-verification.png`
   - Preceding key: `Q`.
   - Visible state: independent store verification reports revision `2 → 3`,
     exactly one revision, the same receipt UID retained, `CURRENT False`,
     `STALE True`, and no Context mutation.
   - Durable mutation: none after the approved Resolve.

Every PNG is rendered from its adjacent color-preserving `.typescript`; the
`.txt` file is the corresponding terminal-cell projection for text review.
