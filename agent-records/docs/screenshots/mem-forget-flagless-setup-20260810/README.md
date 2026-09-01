# `mem forget` compact bidirectional setup capture log

These images render the actual color-preserving PTY byte streams produced by
the real `mem forget` Typer command boundary. The setup intentionally contains
only `FROM`, `INSTRUCTION`, and one editable `COMMAND`; it has no separate
`READY`, metrics, `TO DO`, or action-button surface. The upper fields project
into the command, and a valid command edit atomically moves both upper fields.

The run uses a delayed deterministic provider so setup, whole-frame analysis,
the applied receipt, and read-only verification can be reproduced without an
external semantic request. The provider receives Forget's production prompt
and complete-coverage schema, and its response passes through the production
curation decoder, permission calculation, Context save, and checkpoint path.

## Reproduction frame

- Command: `mem forget`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, set before launch and verified inside each
  child process
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset,
  and `PROMPT_TOOLKIT_NO_CPR=1`
- Profile/current Context: disposable local store; current `alpha`
- Readable Contexts: `alpha` and `beta`; setup selects `beta` without changing
  the global current Context
- Initial upper-field instruction: `Forget the obsolete access code.`
- Exact command edit: `mem forget 'Forget the previous west-entrance desk
  location and obsolete access code; keep general accessibility guidance.'
  --from beta`
- Source: three direct Memories producing one EDIT, one DELETE, and one KEEP
- Provider: deterministic complete-coverage Forget response with an
  eight-second delay
- Renderer: each cumulative ANSI stream is replayed with `pyte`, then drawn at
  `1980×1092` with DejaVu Sans Mono; matching `.typescript` and `.txt` artifacts
  are retained beside every PNG
- Durable scope: temporary stores removed after capture; no real Profile,
  Context, checkpoint, or current-Context pointer was changed

The capture command was:

```bash
python agent-records/docs/screenshots/mem-forget-flagless-setup-20260810/capture_forget_setup.py
```

The driver fails unless the combined raw PTY streams contain ANSI control
sequences and explicit foreground-color styles. It also records
`CAPTURE PTY · 180x52` inside both child streams.

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation in disposable store |
| --- | --- | --- | --- |
| `01-setup-entry.png` | Launch `mem forget` | `INSTRUCTION` is initially focused; `FROM alpha` and the sole editable `mem forget` command box are visible | None; no provider connection |
| `02-instruction-entered.png` | Type `Forget the obsolete access code.` | The upper instruction immediately projects into `mem forget 'Forget the obsolete access code.' --from alpha` | None; no provider connection |
| `03-source-browser.png` | `Up`, `Right`, `Enter` | The transient `ALL READABLE CONTEXTS` browser opens with current `alpha` checked and peer `beta` visible | None; no provider connection |
| `04-source-selected-command-synced.png` | `Down`, `Enter` | `FROM` changes to `beta`, and the command immediately changes to `--from beta` | None; global current remains `alpha`; no provider connection |
| `05-command-focused.png` | `Down`, `Enter` | The single exact command action is focused; there is no separate Ready or To Do control | None; no provider connection |
| `06-command-edit-updates-fields.png` | `Ctrl-U`, then replace all command arguments with the exact command edit above | The valid command edit atomically updates both upper values: the full instruction and `FROM beta` | None; no provider connection |
| `07-analysis-pending.png` | `Enter` | Whole-frame progress shows three Source Memories analyzed against one process-local instruction | None; Source unchanged; one provider connection active |
| `08-success-receipt.png` | Provider completes | The local decision-complete result applies and reports one edit, one removal, receipt, checkpoint, review command, and recovery command | One Context save and one Forget checkpoint; this is the first durable mutation |
| `09-read-only-verification.png` | `Enter` at the capture-only pause | Actual `mem show --context beta` contains the edited and retained accessibility guidance; the obsolete code is absent; current remains `alpha`; provider count is exactly one | None after Apply; read-only verification |
| `10-cancelled-before-provider.png` | Separate disposable launch, then `Escape` from the initial Instruction field | `Forget cancelled`, zero provider connections, byte-semantic Source equality, and unchanged current Context | None |

The command box is the exact approval boundary for this local,
decision-complete path. A granted Source or a result that still requires human
resolution retains the operation's later authority/review boundary; compact
setup does not bypass it. The capture-only pause after the success receipt
exists solely to record the receipt and subsequent read-only verification as
separate ordered states.
