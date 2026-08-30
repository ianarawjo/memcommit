# Meld target picker layer capture

This ordered 180×52 color-PTY set shows the narrow picker used after a reviewed
Compare analysis requests a symmetric Meld and before any Meld session exists.
The picker has no standalone CLI command, so the capture harness invokes its
real `choose_meld_target` adapter with an isolated `MemoryStore` and the exact
two Compare source names.

## Reproduction

- Command: `python agent-records/docs/screenshots/meld-target-picker-layer-20260829/capture.py`
- Working directory: repository root
- PTY: 180 columns × 52 rows, set on the spawned PTY
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, 24-bit prompt-toolkit depth, `NO_COLOR` removed
- Current Context: `capture/empty-result`
- Sources: `capture/compare-a`, `capture/compare-b`
- Eligible existing Result: `capture/empty-result`
- Store/Profile: isolated temporary store; no host Profile read

## Ordered interaction log

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-target-picker-entry` | launch picker after reviewed Compare | `CREATE NEW RESULT CONTEXT` is the initial target row | fixture Contexts only |
| `02-existing-empty-target-selected` | `Down` | existing empty `capture/empty-result` is selected | none |
| `03-new-target-name-entry` | `Up`, `Enter`, type `capture/new-result` | exact new Result name is editable in the picker | none |
| `04-process-local-target-receipt` | `Enter` | typed handoff receipt says pre-session setup and `MELD SESSION CREATED · False` | none |
| `05-read-only-verification` | `V` | Context bytes unchanged, new Result absent, zero sessions and provider calls | none |

The first three images are the picker itself. The final two make its layer
boundary explicit: it returns only `(context_name, create)` to the caller;
Meld orchestration creates the Context and session later.
