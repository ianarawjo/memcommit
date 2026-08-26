# Selectable Merge Target terminal evidence

## Capture contract

- Capture command: `python agent-records/docs/screenshots/mem-merge-target-selection-20260820/capture.py`
- Command under capture: bare `mem merge`, invoked through the real Typer
  command adapter in a focused local root
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Store: a fresh isolated temporary `.mem` root per scenario
- Profile/current Context: local fixture; `target-current` is current,
  `source` is the initial readable Source, and `target-selected` is the
  alternate CREATE-authorized Target
- PTY: `180` columns by `52` rows, verified inside every child process
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, and `NO_COLOR` removed;
  raw ANSI contains foreground and background styles
- Renderer: each PNG is rendered from the actual color-preserving PTY stream;
  the matching `.typescript` and `.txt` files remain beside it
- Provider/cache: unused; Merge is deterministic and provider-free

## Ordered interaction log

| # | Image | Preceding keys or text | Visible state | Durable mutation |
| --- | --- | --- | --- | --- |
| 01 | `01-entry-current-target-default.png` | Launch bare `mem merge` | Direct mode starts with readable Source `source`; B is a selectable `TARGET · CREATE AUTHORITY` control checked at current `target-current` | None |
| 02 | `02-source-focused.png` | `Tab` | Source A owns focus; the initially checked readable Source remains `source` | None |
| 03 | `03-target-focused.png` | `Tab` | Target B owns focus and exposes both `target-current` and `target-selected` in the frozen CREATE-authorized catalog | None |
| 04 | `04-alternate-target-selected.png` | `Down`, `Enter` | `target-selected` is checked while global current remains `target-current` | None |
| 05 | `05-setup-ready.png` | `Tab` | Setup receipt shows `A · source`, `B · target-selected`, and direct reach before planning | None |
| 06 | `06-selected-target-success-receipt.png` | `Enter` | The decision-free local plan applies through the normal command boundary and reports `source` merged into `target-selected` with one added Memory and checkpoint | Only `target-selected` receives the Source-only Memory |
| 07 | `07-read-only-verification.png` | `Enter` after the receipt | Global current is still `target-current`; it is unchanged with zero checkpoints, while `target-selected` has one checkpoint | None beyond 06 |
| 08 | `08-same-endpoint-rejected.png` | Fresh launch; `Tab`, `Tab`, `Up`, `Enter`, `Tab`, `Enter` | Selecting `source` as both A and B stays editable but Continue reports that Source and Target must be distinct | None |
| 09 | `09-rejection-read-only-verification.png` | `Q` | Both possible Targets retain zero checkpoints and original content | None |

The command-local Source and Target catalogs remain frozen so namespace or
Grant changes cannot silently replace a visible row. The checked Target is not
frozen until Continue constructs the typed request and `prepare_merge()` binds
the selected identities, digests, and authority for review and Apply.
