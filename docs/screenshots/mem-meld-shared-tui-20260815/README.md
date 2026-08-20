# Meld shared TUI migration trace

This ordered set records Meld's inline five-row shared Endpoint Setup and the
relocated saved-session workbench. The setup stays in the terminal's main
buffer, preserves the preceding command lines, and keeps Context trees and
Memory lists out of its persistent rows: matching Context names, an explicitly
opened Browse catalog, and direct-Memory detail appear only while the
corresponding control is active. All captures use actual typed
application/session objects and isolated temporary stores; no provider
connection is constructed.

## Reproduction frame

- Command adapters: `commands.meld_setup.choose_meld_setup` and
  `interfaces.tui.operations.meld.screen.run_meld_shell`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Store: one new isolated temporary store per flow
- Profile: none; the host Profile and host Memory store are not read
- Current Context in setup flows: `capture/incoming`; `capture/empty-result`
  is the eligible existing empty Result candidate
- PTY: `180` columns × `52` rows, verified by the child process
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`,
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, and `NO_COLOR` removed
- Main-buffer probe: `PROMPT_TOOLKIT_NO_CPR=1` because the byte-recording
  pexpect PTY cannot answer CPR; setup streams are rejected if they contain an
  alternate-screen `1049h` transition
- Renderer: the actual cumulative ANSI PTY stream replayed through `pyte` and
  drawn at full terminal resolution with Menlo; matching `.typescript` and
  plain `.txt` evidence is retained beside each PNG

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-symmetric-mode-entry` | launch new Meld setup | preceding command/PTY lines remain above the inline compact form; `MODE` owns focus | fixture Contexts only |
| `02-symmetric-peer-a` | `Tab` | compact `FROM` exact-name input owns focus near the left edge; its `› ` prompt is visibly writable | none |
| `02a-symmetric-context-matches` | `Ctrl-U`, type `capture/` | the typed draft is visible after `› ` and frozen matching readable Context names appear while the person types | none |
| `02b-symmetric-browse-trigger` | restore `capture/incoming`, `Tab` | the visible `[ BROWSE ]` control beside A owns focus before any catalog opens | none |
| `02c-symmetric-all-allowed-contexts` | `Enter` | A's complete frozen role-authorized readable catalog opens transiently through the shared Context tree | none |
| `03-symmetric-peer-b` | `Escape`, `Tab`, `Tab` | the catalog collapses to its Browse trigger; `WITH` is an independently writable exact-name input | none |
| `04-new-result-name-entry` | `Tab`×3 | `CHOOSE EMPTY OR ENTER NEW NAME` distinguishes an existing empty Result from a not-yet-created exact name | none |
| `05-new-result-name-unconfirmed` | type `capture/new-result` | the direct name is visibly `NEW · NOT CREATED` | none |
| `06-symmetric-setup-reviewed` | `Enter` | new C is confirmed process-locally and the concrete `[ START MELD ]` action owns focus | none |
| `07-symmetric-setup-receipt` | `Enter` | capture harness receives the typed symmetric receipt with `CREATE=True · NOT CREATED` | none |
| `08-symmetric-read-only-verification` | `V` | current Context/bytes/checkpoints unchanged; the newly named C is absent; zero sessions/provider calls | none |
| `09-directional-mode-selected` | new launch, `Right` | compact `MODE` selector stages `DIRECTIONAL · UPDATE EXISTING`; C is hidden and authority labels change | fixture Contexts only |
| `09a-directional-memory-choices` | `Tab`×4, `Down` | A's direct-Memory choices expand only on demand below the five-row form | none |
| `10-directional-incoming-memory` | `Enter` | one exact incoming Memory is selected and the temporary detail collapses | none |
| `11-directional-baseline` | `Tab` | B is the authoritative Baseline and Result | none |
| `12-directional-baseline-descendants` | `Tab`, `Tab`, `Right` | only B is broadened to descendants | none |
| `13-directional-memory-disabled` | `Tab` | B Memory focus cannot survive recursive reach | none |
| `14-directional-setup-reviewed` | `Tab` | `[ START MELD ]` owns focus after exact A Memory and recursive B, with no C | none |
| `15-directional-setup-receipt` | `Enter` | capture harness receives a typed directional receipt preserving the independent scopes | none |
| `16-directional-read-only-verification` | `V` | Context bytes/current/checkpoints unchanged; zero sessions/provider calls | none |
| `17-relocated-session-entry` | launch saved-session adapter | complete saved symmetric assessment opens through the relocated screen module | fixture session only |
| `18-relocated-session-issue-detail` | `Tab`, `Down`, `Enter` | source-linked required issue and choices are visible | none |
| `19-relocated-session-choice` | `Tab`, `Enter` | first response is visibly staged | process-local only |
| `20-relocated-session-read-only-receipt` | `Q` | adapter path, unchanged session/target, and zero provider calls are verified | none |

The capture harness deliberately stops at the process-local receipt: it proves
that setup itself cannot create C, connect a provider, save a Meld session, or
apply B. The real picker caller passes that receipt into `commands.meld`, where
`START MELD` begins the existing runtime. Runtime/application/cache/Grant
behavior is covered by the Meld test
matrix (`340` Meld/component/Resolution boundary tests, `10` Grant-focused
tests, and `35` Study-prewarm tests at this migration). The boundary suite also
parses every module under `memcommit/interfaces` and verifies that no interface
imports a legacy command adapter. Existing full-replay captures continue to
cover provider reconciliation, exact application, Undo/Redo, and durable Result
inspection because the relocated screen did not change those semantics.

The compact form changes presentation only. Its stable mode IDs, exact writable
Context operands, independent A/B descendant controls, directional
direct-Memory focus, existing-versus-new C intent, and typed setup receipts
remain the executable parity boundary with the CLI.

Reproduce from the repository root with:

```sh
python docs/screenshots/mem-meld-shared-tui-20260815/capture.py
```
