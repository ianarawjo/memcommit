# Directional Meld arrow-to-Apply verification

This ordered set verifies that the repaired two-axis Meld setup does not stop
at a process-local receipt: the selected directional request reaches the real
Meld runtime, edits the Baseline, adds the novel incoming Memory, records one
Meld checkpoint, and leaves the Incoming Context unchanged. A second isolated
store separates exact review from `--accept` so provider-free application,
idempotent replay, Undo, Redo, and a fresh read-only reload are visible rather
than inferred from the setup path.

## Reproduction frame

- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Command adapter: `memcommit.commands.meld.command.cmd`, registered as `mem meld` in
  the capture's minimal Typer command group
- Setup adapter: `memcommit.commands.meld.setup.choose_meld_setup`
- Runtime/application boundary: `prepare_meld_start`, `execute_meld_start`,
  and the command-owned persisted `--accept` route; the harness never writes a
  Context directly after fixture creation
- Stores: two fresh temporary stores, one for the setup-to-Apply path and one
  for exact review/Apply/recovery; both are deleted after capture
- Profile: none; the host Profile and host Memory store are not read
- Current Context: `test/update/from`
- Incoming A: `test/update/from`, two Memories
- Baseline/Target B: `test/update/to`, two Memories before Apply
- Provider: deterministic `DirectionalProvider` fixture, delayed only so the
  real wait surface can be captured
- PTY: `180` columns × `52` rows, verified in every child
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`,
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, and `NO_COLOR` removed
- Renderer: actual cumulative ANSI PTY bytes replayed through `pyte`; every PNG
  has matching `.typescript` and plain `.txt` evidence

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-setup-entry` | launch bare `mem meld` | symmetric default and the frozen current/eligible endpoint names | fixture Contexts only |
| `02-directional-mode` | `Right` | `DIRECTIONAL · UPDATE EXISTING`; A and B each expose Browse, reach, and Memory controls | none |
| `03-incoming-source` | `Down` | A's exact Context input owns focus | none |
| `04-horizontal-memory-stop` | `Tab`, `Right`, `Right` | focus crosses Browse and reach to A's same-row Memory control; the footer advertises row-local Left/Right | none |
| `05-baseline-target` | `Left` ×3, `Down`, `Ctrl-U`, type `test/update/to` | focus returns across the row to A input, then vertical movement reaches B and stages the exact writable target | none |
| `06-start-reviewed` | `Down` | the exact runnable `mem meld test/update/from test/update/to` command is focused | none |
| `07-provider-analysis-pending` | `Enter` | real `MELD · ANALYZING MELD TURN` wait surface | none; provider call in flight |
| `08-auto-application-receipt` | provider completes | local decision-free policy applies through the operation boundary: session `APPLIED`, checkpoint `1`, target Memories `3`, effects `EDIT, ADD` | B edited and expanded; A unchanged |
| `09-exact-ready-proposal` | start the same request in the second store without acceptance | complete `READY_TO_APPLY` proposal, exact `--accept` command, two original target UIDs, zero checkpoints | saved review session only |
| `10-exact-accept-receipt` | run `mem meld test/update/from test/update/to --accept` | provider calls `0`, checkpoint `1`, target Memories `3`; the edited and retained target UIDs match image 09 and the third UID is new | exact B edit/add |
| `11-idempotent-repeat` | run the same exact `--accept` again | prior application recovered, same receipt/checkpoint, still three Memories and one checkpoint | none |
| `12-operation-undo` | `mem undo` | session returns to `READY_TO_APPLY`, original two target Memories restored | reverses one edit and one add |
| `13-operation-redo` | `mem redo` | session returns to `APPLIED`, three target Memories restored | reapplies one edit and one add |
| `14-read-only-result-verification` | reopen the store and reload `test/update/to` | final three Memories and original `EDIT, ADD` Meld evidence remain readable with no provider call | none |

The receipt's `RESULT MEMORIES · 2` is the count of reviewed result operations
(`EDIT` and `ADD`), while `TARGET MEMORIES · 3` is the durable Baseline total
after applying those operations. The unchanged unrelated store-policy Memory
and the edited parking Memory retain their original UIDs; only the ATM addition
receives a new UID.

The setup path intentionally auto-applies a ready, decision-free local target
because the same operation has a local Undo boundary. Image 09–10 separately
proves the explicit exact-command path: the reviewed proposal remains unchanged
until `--accept`, and Apply constructs no provider.

Reproduce from the repository root with:

```sh
python docs/screenshots/meld-directional-apply-20260822/capture.py
```
