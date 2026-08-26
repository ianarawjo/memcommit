# `mem copy` and `mem move` Embed-shaped TUI capture log

These images render the actual color-preserving PTY stream from bare
`mem copy` and `mem move`. Copy checks two direct Memories, selects one Target
and one interleaved `POSITION` line, approves the compact editable command, and
verifies that every output has a new UID. Move follows the same source, target,
placement, and exact-command grammar without a normal link-policy frame.
Separate disposable runs verify default live-Embed retargeting, locked
link-owner rejection, Target self-link rejection, and the advanced
`--break-links` path. Snapshot References remain unchanged in every Move run.

## Reproduction frame

- Commands: bare `mem copy` and bare `mem move`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, set before launch and verified in every child
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Profile: disposable local default Store created inside each child process
- Current Context: `inbox/notes`
- Local catalog: `archive/decisions`, `inbox/notes`, `reports/snapshots`, and
  `watchers/live`
- Source Memories: `[9ef031a2]`, `[ea713f91]`, and `[ca112233]` directly owned
  by `inbox/notes`
- Move relationship: `[de450001]` is a live Memory Embed to `[9ef031a2]`;
  `[fa560001]` is an immutable snapshot Reference to the same Source
- Renderer: every cumulative ANSI stream is replayed through `pyte`, rendered
  at the full 180×52 canvas with Menlo, and retained as matching
  `.typescript`, `.txt`, and `.png` files
- Durable scope: temporary Stores are removed after capture; no real Context,
  checkpoint, protection rule, or current-Context pointer is changed

The capture command was:

```bash
env -u NO_COLOR TERM=xterm-256color COLORTERM=truecolor \
  python agent-records/docs/screenshots/mem-copy-move-transfer-20260823/capture.py
```

The driver fails unless every child reports `180x52`, the cumulative stream
contains foreground and background ANSI styles, all 24 images exist, default
Move reports one retargeted live Embed, the locked owner names the exact denied
Context, self-link rejection remains visible in the workbench, and explicit
Break verifies a dangling live Embed.

## Ordered interaction

| Image | Exact input since preceding image | Visible state | Durable mutation in disposable Store |
| --- | --- | --- | --- |
| `01-copy-entry.png` | Launch bare `mem copy` | Source Memories are visible under current `inbox/notes`; Copy has no identity-policy frame, append is staged, and the command is invalid until a Memory is checked | None |
| `02-copy-multiple-source-selected.png` | `Down`, `Enter`, `Down`, `Enter` | `[9ef031a2]` and `[ea713f91]` are both checked while the cursor remains on the second Memory; the command is now runnable | None |
| `03-copy-target-selected.png` | `Tab`, `Up`, `Enter` | `archive/decisions` is checked as Target; its two direct Memories and one checked append line appear inside the same tree row | None |
| `04-copy-position-default.png` | `Tab` | Position editing begins on the single checked append line without opening another policy surface | None |
| `05-copy-position-hover.png` | `Up` | The sole position line moves between the two Target Memories while append remains staged | None |
| `06-copy-position-staged.png` | `Enter` | The middle `POSITION · 2/3` line becomes checked; there are no duplicated BEFORE/AFTER gap rows | None |
| `07-copy-exact-command.png` | `Tab` | Compact blue `COMMAND · RUNNABLE` shows both qualified Source selectors, exact Target, and adjacent `--before` selector with no identity flag | None |
| `08-copy-success-receipt.png` | `Enter` | TUI closes; plain receipt reports two new-UID copies at the exact middle gap and one Target checkpoint | First durable mutation: Target only |
| `09-copy-read-only-verification.png` | `Enter` at capture-only pause | Direct Store inspection shows Source unchanged and both copied Memories inserted between Target markers | None after Copy |
| `10-move-entry.png` | Separate launch of bare `mem move` | Same multi-Memory Source and `INTO + POSITION` grammar; no redundant normal link-policy frame; command awaits a checked Source | None |
| `11-move-source-selected.png` | `Down`, `Enter` | `[9ef031a2]` is checked as the exact directly owned Memory to move | None |
| `12-move-target-selected.png` | `Tab`, `Up`, `Enter` | `archive/decisions` is checked as the new direct owner and its direct order is visible | None |
| `13-move-position-hover.png` | `Tab`, `Up` | The one position line hovers between Target Memories while append remains staged | None |
| `14-move-position-staged.png` | `Enter` | Middle `POSITION · 2/3` becomes the retained gap | None |
| `15-move-exact-command.png` | `Tab` | Compact runnable command contains no link flag because atomic live-Embed following is the default | None |
| `16-move-success-auto-retarget.png` | `Enter` | Receipt reports REMOVE plus ADD effects and one retargeted live Memory Embed | Source, Target, and live-link owner publish atomically with three checkpoints |
| `17-move-read-only-verification.png` | `Enter` at capture-only pause | Moved Memory is in Target; live Embed owner field is `archive/decisions` and resolves; snapshot owner field remains `inbox/notes` | None after Move |
| `18-move-locked-owner-rejected.png` | Separate locked-owner run; `Down`, `Enter`, `Tab`, `Up`, `Enter`, `Tab`, `Up`, `Enter`, `Tab`, `Enter` | Exact CLI error names locked `watchers/live`; command exits with status 1 | None |
| `19-move-locked-no-partial-verification.png` | `Enter` at capture-only pause | Every Context record is byte-semantically unchanged, live Embed still resolves to Source, and checkpoint count is zero | None |
| `20-move-self-link-rejected.png` | Separate Target-owned-link run; same selection and approval keys | Workbench remains open and explains that default retargeting would create a forbidden self-link; `--break-links` is named as the explicit alternative | None |
| `21-move-self-link-no-partial-verification.png` | `Escape`, then `Enter` at capture-only pause | Cancel receipt plus direct inspection confirms all Contexts unchanged and zero checkpoints | None |
| `22-move-break-exact-command.png` | Separate run to command; `Ctrl-U`, type `inbox/notes:9ef031a --into archive/decisions --before ab12000 --break-links` | Valid edited command synchronizes the upper Source, Target, first gap, and hidden advanced Break policy without adding a policy frame | None |
| `23-move-break-success.png` | `Enter` | Receipt explicitly reports one dangling live Memory Embed and BREAK LINKS | Source and Target publish atomically with two checkpoints; live owner is deliberately unchanged |
| `24-move-break-dangling-verification.png` | `Enter` at capture-only pause | Moved Memory is in Target; snapshot remains unchanged; live Embed retains old owner field and resolves as DANGLING | None after Move |

The Enter between each success or failure receipt and its verification is a
capture-only pause. It is not part of the product flow.
