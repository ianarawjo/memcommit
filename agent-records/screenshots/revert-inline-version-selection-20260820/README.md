# Revert inline version selection and result-level duplicate rejection

> Historical pre-change evidence for Revert images 01–07. The current Revert
> entry and checkpoint Viewer are refreshed under
> `agent-records/screenshots/revert-revision-result-20260821/`; Merge images 08–11 remain
> evidence for their separate same-result validation boundary.

This ordered evidence set records two related picker boundaries. Revert exposes
every exact checkpoint below its Context and lets Enter stage that version for
the existing History/Apply review. Merge keeps the current Target selectable as
a Source candidate, then rejects the invalid same-Context result only when the
person tries to continue.

## Reproduction frame

- Command: `python agent-records/screenshots/revert-inline-version-selection-20260820/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Stores: two isolated temporary Stores; neither uses or changes the active
  Profile
- Revert fixture: `revert/versions` with Init and two exact Update checkpoints;
  both Update records deliberately share one operation identity but retain
  different snapshots
- Merge fixture: `merge/source` and current `merge/target`, each with one direct
  Memory and no checkpoints
- PTY: `180` columns × `52` rows, set and printed by every child
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` removed,
  prompt-toolkit 24-bit depth
- Renderer: the actual ANSI PTY stream is replayed through `pyte` and drawn on
  a full Menlo terminal canvas; raw `.typescript` and plain `.txt` records are
  retained beside each PNG
- Mutation boundary: only image 06 follows a durable action, confined to the
  temporary Revert Store; Merge remains read-only throughout

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-revert-context-entry.png` | Launch bare Revert | Local Context location row focused | None |
| `02-all-exact-versions-visible.png` | `Right` | Init and both repeated-identity Update checkpoints remain independently visible with explicit Checkpoint and shared Command-unit labels | None |
| `03-older-version-focused.png` | `Down` ×2 | Older exact Update checkpoint owns focus and its full typed identifiers appear in the passive detail region | None |
| `04-version-staged-history-policy.png` | `Enter` | Exact UID is checked and History policy owns focus; no redundant Items Enter is required | None |
| `05-exact-apply.png` | `Enter` | Apply repeats the exact checkpoint and discard-newer policy | None |
| `06-revert-success-receipt.png` | `Enter` | Revert success and recovery receipt | Revert only |
| `07-revert-read-only-verification.png` | Launch verifier | Version-one Memory restored, selected checkpoint retained, newer checkpoint discarded | None |
| `08-merge-entry.png` | Launch bare Merge | Valid alternate Source is the initial draft; current Target remains an available row | None |
| `09-same-target-source-selected.png` | `Tab`, `Down`, `Enter` | Current Target is explicitly selected as Source rather than disabled by the picker | None |
| `10-same-result-rejected-at-continue.png` | `Tab`, `Enter` | Continue reports that Source A and Target B must be distinct | None |
| `11-merge-read-only-verification.png` | `q`, launch verifier | Both Context contents and zero-checkpoint histories are unchanged | None |

The shared picker still rejects duplicate row identities inside one frozen
catalog because duplicate identities cannot be addressed unambiguously. That
structural integrity check is distinct from operation rules such as “A and B
must differ,” which belong to the completed draft or application boundary.
