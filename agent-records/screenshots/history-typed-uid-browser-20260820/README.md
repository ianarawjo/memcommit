# Typed History UID browser capture log

> Historical evidence for typed checkpoint identities. Bare Revert no longer
> begins with this Profile-wide Context tree; the current direct-entry and
> complete revision Viewer are recorded under
> `agent-records/screenshots/revert-revision-result-20260821/`.

This ordered evidence set records the Context-history presentation that keeps
Checkpoint, Memory, Context, restoration Receipt, and restored Source-command
identities visually distinct. It also verifies that copied Branch lineage is
shown as inherited instead of being counted as commands directly executed on
the branch.

## Reproduction frame

- Command:
  `python agent-records/screenshots/history-typed-uid-browser-20260820/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Store: isolated temporary Store; no personal Profile or Context content is
  read or changed
- Profile/current Context: temporary default Profile; current `practice/2`
- Fixture path: Init and Add in `practice/1`; exact Branch to `practice/2`;
  direct Embed, Edit, Remove, Undo, Redo, and Undo in `practice/2`
- PTY: `180` columns × `52` rows, set before launch and printed by each child
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` removed,
  prompt-toolkit 24-bit depth; raw streams are checked for foreground and
  background ANSI styles
- Renderer: the actual ANSI PTY stream is replayed through `pyte` and drawn on
  a full Menlo terminal canvas. Raw `.typescript` and plain `.txt` evidence is
  retained beside each PNG.
- Mutation boundary: fixture setup mutates only the temporary Store. The
  captured Revert path is cancelled before Apply and is read-only.

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-context-entry.png` | Launch bare `mem revert` | `practice/2` focused with `6 direct · 1 inherited · 0 descendant commands` | None |
| `02-typed-direct-and-inherited-history.png` | `Right` | Direct commands and inherited `practice/1` lineage are separate; every compact UID has a role label | None |
| `03-undo-identities-focused.png` | `Down` | Latest Undo focused; exact Checkpoint, Receipt, and Source command unit appear in `SELECTED COMMAND` | None |
| `04-inherited-add-identities-focused.png` | `Down` ×6 as one held-arrow burst, then `Up` | Inherited Add focused; exact Checkpoint and Memory UIDs plus `inherited from practice/1` are visible | None |
| `05-exact-checkpoint-review.png` | `Enter` | The inherited Add's exact Checkpoint UID is staged in the existing Revert review | None |
| `06-cancelled-without-mutation.png` | `q` | Revert cancellation receipt | None |
| `07-read-only-verification.png` | Launch verifier | Current pointer, final-Undo Memory, 6/1 command split, and checkpoint count are unchanged | None |

The creation baseline remains visible under inherited history but is not
counted as a command. Compact rows use eight-character prefixes only for
scanning; the focused detail and exact Revert receipt retain full identifiers.
