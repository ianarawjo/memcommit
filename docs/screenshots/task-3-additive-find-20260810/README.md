# Task 3 additive Find/Sever study run

This directory records a fresh Task 3 run performed from the task description,
`mem help`/command help, readable public guidance, and terminal-visible command
results only. No fixture source, answer key, or implementation solution was
opened while choosing the Memories.

## Environment

- Editable Study profile: `study-alt-20260810-t3-find-additive`
- Paired receiver profile: `study-alt-20260810-t3-find-additive-granted-memory`
- Source: `task-3/local/personal-memory`
- Receiver endpoint: `task-3/government/healthcare-agent`
- PTY: `180` columns by `52` rows
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` removed
- Final profile check: `53-pty-profile-check.typescript`

The final check reported `52 180`. The captured streams contain true-color ANSI
sequences such as `38;2;139;213;255` and focused backgrounds such as
`48;2;16;36;47`; therefore the rendered color is application output rather
than a post-hoc semantic recoloring.

## Strategy

The experiment tested an additive path rather than beginning with a 300-Memory
subtractive pass:

1. Query the recipient route for the confirmed service, recipient, purpose,
   categories, channel, retention, and downstream rules.
2. Run two narrow Finds over the original personal-memory subtree.
3. Copy only checked candidates into two new staging Contexts.
4. Add six process-specific minimum-disclosure criteria to a new local Context.
5. Sever each small candidate group independently.
6. Merge only reviewed results into a new empty accumulator.
7. Find the accumulator again from a privacy/staleness perspective.
8. Run a whole-accumulator Forget audit.
9. Sever the accumulator once more into a fresh final Context.
10. Share only that final Context and verify the receiver-owned copy.

The recipient query confirmed the government healthcare institution as the
initial recipient and the institution screen as the transmission channel. It
did not confirm an exact healthcare service, a minimum category list, precise
third parties, downstream scope, or deletion/retention details. The criteria
therefore treated necessity as unproven unless a Memory independently expressed
a stable cross-healthcare preference or verification policy.

## Interaction log

The numbered `.typescript` files are the raw PTY byte streams. Important text
and key actions were:

### Discovery and Find 1

- `mem switch task-3/description`, then `mem show`
- `mem contexts`
- `mem show --context task-3/remote/government/healthcare-agent/info-request`
- `mem query task-3/remote/government/healthcare-agent/info-request/questions-and-answers ... --context task-3/local/personal-memory`
- `mem switch task-3/local/personal-memory`
- `mem find "stable current accessibility, communication, sensory, mobility, or accommodation preferences useful across healthcare interactions, excluding private event details and third-party information"`
- Keys: type query, `Enter`; `Down` x4; check results 5 and 4 with
  `Enter`, `Up`, `Enter`; skip result 3 with `Up` x2; check results 2 and 1
  with `Enter`, `Up`, `Enter`; `Tab` to Materialize; `Tab` to Save
  Location; `Ctrl-U`; type
  `task-3/local/candidates/accessibility-communication`; `Tab`; `Enter`.
- Result: four checked Memories copied; the medication-history result was not
  checked.

### Find 2

- `mem find "stable current healthcare coordination preferences for scheduling, reminders, preparation, language, preferred contact channel, or support logistics, excluding actual phone numbers, addresses, dates, medication details, and third-party information"`
- Inspect the five results, skip the three duplicates from Find 1, check the
  availability-confirmation and checklist candidates, then move through
  Materialize and Save Location with `Tab`.
- Save name entered:
  `task-3/local/candidates/coordination-preparation`.
- Result: two checked Memories copied.

### Criteria, accumulator, and background Help

- `mem init task-3/local/criteria/additive-minimum --parents`
- Six `mem add --context task-3/local/criteria/additive-minimum ...` commands;
  `mem show` verified exactly six criteria.
- `mem init task-3/local/results/additive-allowlist --parents`
- During the first Sever wait, the shared Help inventory remained live. Keys:
  `Down` x4, then `Right` to expand the `mem show` forms; `q` returned to the
  running operation. The Sever continued from 0 to 12 seconds while Help was
  open.

### Sever 1

- Source: `task-3/local/candidates/accessibility-communication`
- Result: `task-3/local/reviewed/accessibility-communication`
- Review navigation: `Tab`, `Down`, `Enter`, `PgDn`; then repeat
  `Tab` x2, `Down`, `Enter`, `PgDn` to inspect the remaining decisions.
- `A` (uppercase) caused no visible change. `a` opened final review. A plain
  `Enter` returned rather than applying; reopening with `a`, then `End`,
  `Enter` applied the proposal.
- Outcome: two KEEP and two FORGET; Source unchanged.

### Sever 2 and additive merge

- Source: `task-3/local/candidates/coordination-preparation`
- Result: `task-3/local/reviewed/coordination-preparation`
- The same Viewer/Items navigation inspected both decisions; `a`, `End`,
  `Enter` applied.
- Outcome: one REFRAME and one FORGET; Source unchanged.
- `mem merge task-3/local/reviewed/accessibility-communication` added two.
- `mem merge task-3/local/reviewed/coordination-preparation` added one.
- `mem show` verified exactly three accumulator Memories.

### Find/Forget audit and final Sever

- `mem find "any retained detail that could be stale, unnecessary, too specific, private, third-party, medication, location, contact, credential, financial, or current functional status" --direct`
- The risk Find returned the two generic scheduling policies containing words
  such as availability and address; neither contained an actual value.
- `mem forget "Forget or minimally generalize ...; keep generic verification policies that contain no such value."`
- The audit proposed zero changes. Keys: `q` closed background Help; `a`
  opened the first required review; `Tab`, `Enter` selected the recommendation;
  `a` showed all three recommendations in final review; `End`, `Enter`
  completed the no-op apply path.
- Final Sever Source: `task-3/local/results/additive-allowlist`
- Final result: `task-3/local/results/additive-final`
- Keys followed the same required-item path: `q`; `a`; `Tab`, `Enter`; `a`;
  `End`, `Enter`.
- Outcome: three compact REFRAME results; Source unchanged.

### Share and verification

- `mem share task-3/local/results/additive-final --to task-3/government/healthcare-agent`
- Receipt: Share `50a7f929-1b4c-5766-b2de-acacc137fee5`, three Memories,
  consent digest
  `130e3272b7c82b935380913ab3676192165fab58a50966335133c211bfa388b7`.
- Read-back failed in the sender profile with both the printed
  `PROFILE:PATH` receiver locator and the suffix path alone.
- `mem profile use study-alt-20260810-t3-find-additive-granted-memory`
  followed by `mem show --context task-3/remote/government/healthcare-agent/received-shares/50a7f929-1b4c-5766-b2de-acacc137fee5`
  verified exactly the same three texts.
- The active profile was returned to
  `study-alt-20260810-t3-find-additive`.
- `mem list task-3/local/personal-memory --recursive` was counted by Memory
  rows and returned `300`, confirming that the original Source remained intact.

## Outcome

Six Find candidates became three transferred Memories:

1. A day-before appointment reminder is sufficient for rechecking preparation.
2. Confirm date, time, address, and floor before adding a follow-up visit.
3. Because availability varies weekly, confirm it separately for each
   appointment instead of relying on prior availability.

The two small Severs made different local decisions while converging on a
three-Memory accumulator. The final Sever retained the same count but rewrote
all three again. This is useful study evidence: the semantic pipeline preserved
the selection boundary while wording was not idempotent under a repeated pass.

## Observed issues and boundaries

1. A zero-change Forget apply returned directly to the shell with no success or
   explicit no-op receipt. A following `mem show` proved that all three
   Memories were unchanged.
2. The Share receipt's receiver locator is not directly readable from the
   sender profile, even though switching to the named receiver profile proves
   that the Context exists and contains the exact payload. This may be an
   authorization boundary, but the receipt does not explain the required
   verification route.
3. Final apply navigation is discoverable but easy to misread: `a` opens the
   review, while `End` is needed to reach the actual Apply block before
   `Enter`; pressing `Enter` immediately returns.
4. Repeating Sever over an already curated three-Memory result produced three
   stylistic reframes. Count and meaning remained stable, but wording did not.
5. Explicit `mem share SOURCE --to ENDPOINT` sent immediately and returned a
   receipt; it did not open a second interactive consent screen.

## Rendered captures

The PNGs are full `2568×1656` renders of the actual color-preserving PTY byte
streams, not synthetic fixtures:

1. `01-task-description.png`
2. `02-find-accessibility-selection.png`
3. `03-find-coordination-selection.png`
4. `04-help-during-sever.png`
5. `05-sever-accessibility-review.png`
6. `06-sever-accessibility-receipt.png`
7. `07-sever-coordination-review.png`
8. `08-forget-audit.png`
9. `09-final-sever-review.png`
10. `10-final-sever-receipt.png`
11. `11-final-context.png`
12. `12-share-receipt.png`
13. `13-receiver-verification.png`
14. `14-source-count.png`

