# `mem forget` flagless setup capture log

These images render the actual color-preserving PTY byte streams produced by
the real `mem forget` Typer command boundary. The run uses a delayed,
deterministic provider so the setup, whole-frame wait, shared Resolution
Workbench, exact Apply confirmation, checkpoint receipt, and read-only result
can be reproduced without an external semantic request. The provider still
receives Forget's production prompt and complete-coverage schema, and its
response passes through the production curation decoder, review adapter,
permission calculation, Context save, and checkpoint path. An eight-second
delay keeps the report, Context browser, and input destinations visible long
enough to capture independently.

## Reproduction frame

- Command: `mem forget`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, set before launch and verified inside each
  child process
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Profile/current Context: disposable local store; current `alpha`
- Readable Contexts: `alpha` and `beta`; the setup selects `beta` without
  changing the global current Context
- Instruction: `Forget the previous west-entrance desk location and obsolete
  access code; keep general accessibility guidance.`
- Source: three direct Memories producing one EDIT, one DELETE, and one KEEP
- Provider: deterministic complete-coverage Forget response with an eight-second
  delay
- Renderer: each cumulative ANSI stream is replayed with `pyte`, then drawn at
  `1980×1092` with DejaVu Sans Mono; matching `.typescript` and `.txt` artifacts
  are retained beside every PNG
- Durable scope: temporary stores removed after capture; no real Profile,
  Context, checkpoint, or current-Context pointer was changed

The capture command was:

```bash
python agent-records/screenshots/mem-forget-flagless-setup-20260810/capture_forget_setup.py
```

The driver fails unless the combined raw PTY streams contain ANSI control
sequences and explicit foreground-color styles. The successful capture used
256-color foreground sequences and recorded `CAPTURE PTY · 180x52` inside both
child streams.

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation in disposable store |
| --- | --- | --- | --- |
| `01-setup-entry.png` | Launch `mem forget` | Blank Instruction initially focused; current `alpha` checked in one `ALL READABLE CONTEXTS` Source tree; To Do reports `INSTRUCTION REQUIRED` | None; no provider connection |
| `02-instruction-entered.png` | Type the exact instruction above | Instruction retained in its shared focused frame; To Do changes to `READY` | None; no provider connection |
| `03-source-selected.png` | `Tab`, `Down`, `Enter` | `beta` is the sole checked Source while `alpha` remains visibly marked current | None; global current remains `alpha`; no provider connection |
| `04-todo-ready.png` | `Tab` | Exact `ANALYZE AND REVIEW` action focused; Source confirms `beta · THIS CONTEXT ONLY` | None; no provider connection |
| `05-analysis-pending.png` | `Enter` | Shared command-wait report shows `CONTENT PENDING · THIS IS NOT A RESULT` for one complete three-Memory Source × instruction turn | None; Source unchanged; one provider connection active |
| `06-context-browser.png` | `c` | The switch-shaped frozen readable Context namespace opens on current `alpha`; it is explicitly read-only and cannot emit a switch receipt | None; current remains `alpha`; Source unchanged |
| `07-confirmed-inputs.png` | `i` | Frozen canonical Source, direct Memory count, unchanged boundary, and exact instruction | None; Source unchanged |
| `08-review-report.png` | `r`, then provider completes | Shared Resolution report shows the EDIT, DELETE, and KEEP result plus `REVIEW AND APPLY` | None; proposal remains process-local |
| `09-decision-detail.png` | `Tab`, `Down`, `Enter` | First required decision opens with classification, exact Forget instruction, Source Memory, reason, and proposed result | None |
| `10-approval-summary.png` | `A` | Final review lists all three checked recommendations and states that nothing changes until the action below is confirmed | None |
| `11-exact-apply-action.png` | `End` | The exact `APPLY` card, effect description, recovery hint, and no-apply Escape boundary are focused | None |
| `12-success-receipt.png` | `Enter` | Post-save receipt names canonical Source `beta`, reports one removal and one edit, and includes the created checkpoint prefix | One Context save and one Forget checkpoint; this is the first durable mutation |
| `13-read-only-verification.png` | `Enter` at the capture-only pause | Actual `mem show --context beta` output contains the edited step-free guidance and retained general guidance; the obsolete code is absent; current remains `alpha`; provider count is exactly one | None after Apply; read-only verification |
| `14-cancelled-before-provider.png` | Separate disposable launch, then `Escape` from the initial Instruction surface | `Forget cancelled`, zero provider connections, byte-semantic Source equality, and unchanged current Context | None |

The capture-only pause after the product success receipt exists solely so the
receipt and the subsequent read-only `mem show --context beta` verification can
be recorded as separate ordered states. It does not alter the application flow
or store.
