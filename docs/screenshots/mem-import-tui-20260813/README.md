# `mem import` flagless TUI capture log

These images render the actual color-preserving PTY streams produced by the
real flagless `mem import` command. The ordered set covers the common resource
and Source Profile controls, every materially different Profile/Context/Memory
branch, exact approval, success receipts, read-only result verification, and a
root cancellation before any source store is opened.

## Reproduction frame

- Command: `mem import`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, set by `pexpect` before each launch and
  verified inside every child as `CAPTURE PTY · 180x52`
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Profile/current Context: disposable `authoring` Profile; current
  `destination`
- Visible destination data: one local `destination` Context containing
  `Local destination Memory.`
- Registered source: non-active `source-profile` with `source/root`, lexical
  child `source/root/child`, two directly owned Memories, one Context embed,
  and one cross-Context Memory reference
- Source-list boundary: the active `authoring` Profile is absent by identity;
  the Profile screen contains only `source-profile` and does not inspect any
  candidate store before selection
- Renderer: every cumulative ANSI stream is replayed with `pyte`, then drawn at
  `1980×1092` using DejaVu Sans Mono; matching `.typescript` and `.txt`
  artifacts are retained beside each PNG
- Durable scope: four temporary homes are deleted after capture; the real
  Profile registry, stores, checkpoints, and current pointer are untouched

The capture command was:

```bash
python docs/screenshots/mem-import-tui-20260813/capture_import_tui.py
```

The driver fails unless the combined raw streams contain ANSI controls and
explicit foreground-color styles. The successful run produced 20 PNGs at the
full native canvas size and 20 raw PTY streams containing 256-color sequences.

## Ordered interaction

| Image | Exact input since preceding image | Visible state | Durable mutation in disposable home |
| --- | --- | --- | --- |
| `01-resource-kind-entry.png` | Launch `mem import` | Shared checked-row selector starts on `PROFILE`; external path intake is explicitly left to `--from PATH` | None |
| `02-source-profile-current-hidden.png` | `Enter` | Name-only source selector contains `source-profile`; footer states `CURRENT PROFILE HIDDEN FROM SOURCE LIST` and `authoring` is absent | None; no candidate store opened to build the list |
| `03-profile-name.png` | `Enter` | Shared exact-name field proposes `source-profile-import · NOT CREATED` | None |
| `04-profile-exact-approval.png` | `Enter` | Frozen `mem import profile source-profile-import --from-profile source-profile` and clean-baseline effects; only `A` applies | None |
| `05-profile-success-receipt.png` | `A` | Profile import receipt reports two Contexts, two Memories, baseline digest, excluded operational history, and unchanged active Profile | New clean-baseline Profile created; first mutation in this branch |
| `06-profile-read-only-verification.png` | `Enter` at capture-only pause | Actual `mem profile list` output shows `authoring` still current plus `source-profile` and the new `source-profile-import`; current Context remains `destination` | None after Apply |
| `07-context-kind-selected.png` | Separate launch, then `Down` | Common resource selector checks `CONTEXT` | None |
| `08-context-source-choice.png` | `Enter`, `Enter` | Selected source Profile opens through the shared Context/Memory tree; root, child, Memories, and resolved read-only Memory reference are visible | None |
| `09-context-subtree-range.png` | `Enter`, `Right` | Shared Context reach control checks `INCLUDE DESCENDANTS` | None |
| `10-context-destination-name.png` | `Enter` | Shared parent tree plus direct exact-name input shows `source/root · NOT CREATED`; browsing has not created or switched anything | None |
| `11-context-exact-approval.png` | `Enter` | Frozen recursive command names canonical source/destination and reports two Contexts/two Memories in destination Profile `authoring` | None |
| `12-context-success-receipt.png` | `A` | Receipt lists `source/root` and `source/root/child`, reports two direct Memories, and confirms unchanged Profile selection | Two new Contexts and their import checkpoints created atomically; first mutation in this branch |
| `13-context-read-only-verification.png` | `Enter` at capture-only pause | The direct `mem list source/root --direct` renderer shows the child embed and root Memory; current remains `destination` | None after Apply |
| `14-memory-kind-selected.png` | Separate launch, then `Down`, `Down` | Common resource selector checks `MEMORY` | None |
| `15-memory-source-choice.png` | `Enter`, `Enter`, `Down` | Shared source tree focuses directly owned root Memory `[20000000]`; the Memory reference remains visibly read-only and unselectable | None |
| `16-memory-destination-context.png` | `Enter` | Shared destination tree focuses current ordinary Context `destination` and previews its local Memory | None |
| `17-memory-exact-approval.png` | `Enter` | Frozen command names the full Memory UID, canonical Source Context, exact target Context, and destination Profile `authoring` | None |
| `18-memory-success-receipt.png` | `A` | Receipt confirms UID/content-preserving append into `destination` and unchanged Profile selection | One Memory append and automatic checkpoint; first mutation in this branch |
| `19-memory-read-only-verification.png` | `Enter` at capture-only pause | The direct `mem list destination --direct` renderer shows both the original local Memory and imported root Memory; current remains `destination` | None after Apply |
| `20-cancelled-before-source-open.png` | Separate launch, then `Escape` at resource entry | `Import cancelled`; read-only verification contains only original `destination` and unchanged current pointer | None; no source selector or source store opened |

The capture-only pause after each success receipt exists solely to preserve the
receipt and subsequent read-only verification as separate ordered states. It
does not alter the product interaction or persistence boundary.

