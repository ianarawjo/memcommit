# Meld shared TUI migration trace

This ordered set records Meld's rebuilt shared Endpoint Setup and the relocated
saved-session workbench. All captures use actual typed application/session
objects and isolated temporary stores; no provider connection is constructed.

## Reproduction frame

- Command adapters: `commands.meld_setup.choose_meld_setup` and
  `interfaces.tui.operations.meld.screen.run_meld_shell`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Store: one new isolated temporary store per flow
- Profile: none; the host Profile and host Memory store are not read
- Current Context in setup flows: `capture/incoming`
- PTY: `180` columns × `52` rows, verified by the child process
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`,
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, and `NO_COLOR` removed
- Renderer: the actual cumulative ANSI PTY stream replayed through `pyte` and
  drawn at full terminal resolution with Menlo; matching `.typescript` and
  plain `.txt` evidence is retained beside each PNG

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-symmetric-mode-entry` | launch new Meld setup | Symmetric A+B→C shape owns focus | fixture Contexts only |
| `02-symmetric-peer-a` | `Tab` | A is labelled as an equal peer | none |
| `03-symmetric-peer-b` | `Tab`, `Tab` | B is independently selected as a peer | none |
| `04-new-result-name-entry` | `Tab`, `Tab` | exact new Result field is empty and `NOT CREATED` | none |
| `05-new-result-name-unconfirmed` | type `capture/new-result` | name is editable but not yet confirmed | none |
| `06-symmetric-setup-reviewed` | `Enter` | new C is confirmed process-locally and To Do shows A/B/C | none |
| `07-symmetric-setup-receipt` | `Enter` | typed symmetric receipt says `CREATE=True · NOT CREATED` | none |
| `08-symmetric-read-only-verification` | `V` | current Context/bytes/checkpoints unchanged; C absent; zero sessions/provider calls | none |
| `09-directional-mode-selected` | new launch, `Right` | Directional A→B hides C and changes authority labels | fixture Contexts only |
| `10-directional-incoming-memory` | `Tab`×3, `Down`, `Enter` | one exact incoming Memory is checked | none |
| `11-directional-baseline` | `Tab` | B is the authoritative Baseline and Result | none |
| `12-directional-baseline-descendants` | `Tab`, `Right` | only B is broadened to descendants | none |
| `13-directional-memory-disabled` | `Tab` | B Memory focus cannot survive recursive reach | none |
| `14-directional-setup-reviewed` | `Tab` | To Do shows exact A Memory and recursive B, with no C | none |
| `15-directional-setup-receipt` | `Enter` | typed directional receipt preserves the independent scopes | none |
| `16-directional-read-only-verification` | `V` | Context bytes/current/checkpoints unchanged; zero sessions/provider calls | none |
| `17-relocated-session-entry` | launch saved-session adapter | complete saved symmetric assessment opens through the relocated screen module | fixture session only |
| `18-relocated-session-issue-detail` | `Tab`, `Down`, `Enter` | source-linked required issue and choices are visible | none |
| `19-relocated-session-choice` | `Tab`, `Enter` | first response is visibly staged | process-local only |
| `20-relocated-session-read-only-receipt` | `Q` | adapter path, unchanged session/target, and zero provider calls are verified | none |

The setup flows deliberately stop at their process-local receipt: they prove
that setup itself cannot create C, connect a provider, save a Meld session, or
apply B. Runtime/application/cache/Grant behavior is covered by the Meld test
matrix (`340` Meld/component/Resolution boundary tests, `10` Grant-focused
tests, and `35` Study-prewarm tests at this migration). The boundary suite also
parses every module under `memcommit/interfaces` and verifies that no interface
imports a legacy command adapter. Existing full-replay captures continue to
cover provider reconciliation, exact application, Undo/Redo, and durable Result
inspection because the relocated screen did not change those semantics.

Reproduce from the repository root with:

```sh
python docs/screenshots/mem-meld-shared-tui-20260815/capture.py
```
