# Meld local choice branch interaction log

This ordered capture records the new provider-free boundary for Meld issue
choices. The fixture uses the real `MeldSession`, `MemoryStore`, and shared
Resolution Workbench against an isolated temporary store. It has one REQUIRED
binary conflict so the saved record is easy to inspect. No managed Profile or
global current Context participates.

Every interactive capture used a real color-capable PTY at `180 × 52`:

- `TERM=xterm-256color`
- `COLORTERM=truecolor`
- `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`
- `NO_COLOR` removed
- live `stty size` output verified as `52 180`

The raw streams contain true-color foreground and background ANSI sequences.
The PNGs render those actual streams; they are not synthetic screen fixtures.

| Capture | Exact command | Preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- | --- |
| `01-initial-assessment` | `python capture_meld_local_choices.py --child TEMP_STORE --mode open` | None | Frozen symmetric Compare basis, one required conflict, empty result target | Fixture Contexts and assessed Meld session created; no choice yet |
| `02-issue-detail` | same live command | `Tab`, `Down`, `Enter` | Source-linked conflict detail and its two options | None |
| `03-choice-selected` | same live command | `Tab`, `Enter` | First option marked `✓`; To Do exposes `INCORPORATE RESPONSES` | Process-local selection staged; provider not called |
| `04-choice-save-receipt` | same live command | `Q` | `1 SAVED`, `PROVIDER CALLS · 0` | One assessment-bound issue/option record atomically saved |
| `05-reopened-choice-restored` | `python capture_meld_local_choices.py --child TEMP_STORE --mode reopen` | New PTY, then `Tab`, `Down`, `Enter` | The same option is restored as `✓`; incorporation remains a separate action | None |
| `06-read-only-choice-verification` | `python capture_meld_local_choices.py --child TEMP_STORE --mode verify` | Reopened TUI closed with `Q` | Exact sidecar JSON with one issue UID, option UID, empty explanation, and no semantic output | None; read-only |

The verification record contains no completion, proposal, relation delta, or
application receipt. The existing Task 2 full-replay captures continue to
cover final review, exact acceptance, success receipt, and read-only result
verification; this focused set covers only the changed local-choice boundary.

Reproduce from the repository root with:

```sh
python agent-records/screenshots/meld-local-choice-branches-20260812/capture_meld_local_choices.py
```
