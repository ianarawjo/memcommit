# Granted Copy Memory-transfer TUI capture log

This ordered set records Copy's role-separated interactive contract. The Source
catalog contains ordinary local Contexts plus the explicit public name of one
direct Grant that authorizes retained export; the Into catalog contains only
ordinary local Contexts. The selected granted Memory is therefore rendered and
frozen as the qualified locator `shared/source:UID`, while the Target and gap
remain local.

## Reproduction frame

- Capture command:
  `python agent-records/docs/screenshots/granted-copy-memory-transfer-20260823/capture.py`
- Command under capture: bare `mem copy` through the real Typer root
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, verified inside the child process
- Color environment: `TERM=xterm-256color`, `COLORTERM=truecolor`,
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, and `NO_COLOR` unset
- Profile: isolated active `authoring` Profile with one managed
  `copy-authority` Profile; no host Profile or Grant is visible
- Current Context: local `workspace`
- Local Contexts: `workspace`, `local-source`, and `target`
- Grant: authority `authority/source` published to the active Profile as
  `shared/source` with `READ`, `DERIVE`, `EXPORT`, and `SAVE_ANALYSIS`
- Renderer: cumulative real PTY ANSI bytes replayed through `pyte` and rendered
  on the full Menlo canvas; each PNG has matching `.txt` and `.typescript`
  evidence

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-entry.png` | Launch bare `mem copy` | Source is focused at current local `workspace`; `shared/source` is visibly annotated `GRANT`, `READ + EXPORT`, and `COPY + RETAIN`; Into contains only the three local Contexts; command is invalid until a Memory is checked | None |
| `02-granted-source-open.png` | `Up`, `Up`, `Right` | Public `shared/source` owns the Source cursor and its one direct authority Memory is previewed; the Memory is not yet checked and the command stays invalid | None |
| `03-granted-memory-selected.png` | `Down`, `Enter` | The exact authority Memory is checked and the runnable command immediately uses `shared/source:UID`; the initial Into remains local `workspace` | None |
| `04-local-target-selected.png` | `Tab`, `Up`, `Enter` | The independent Into control selects local `target`; its direct ordering marker and last gap are visible, while the granted Source stays checked above | None |
| `05-target-gap-selected.png` | `Tab`, `Up`, `Enter` | Position editing stages the local gap before the marker; the command adds `--before MARKER_UID` | None |
| `06-exact-approval.png` | `Tab` | The focused exact command is `mem copy shared/source:UID --into target --before MARKER_UID`; the public Source owner and local Target boundary are reviewable before Apply | None |
| `07-copy-success.png` | `Enter` | The TUI closes; the typed receipt reports one new local UID, qualified Source `shared/source`, local `target`, selected start gap, and target checkpoint | One fresh Memory and one Copy checkpoint in local `target`; authority Source unchanged |
| `08-read-only-verification.png` | `V`, `Enter` at the capture-only gate | Direct Store reads confirm exactly one retained copy, the exact content, one unchanged authority Source Memory, one Copy checkpoint, and placement before the marker | No additional mutation |

The public name is authorization-bearing identity, not a local alias. The
interactive picker and edited exact command may resolve a granted Memory only
through that explicit owner; unqualified Memory UIDs search the frozen local
Source catalog only. Move and every Into role stay local-only, so this flow does
not confer authority to mutate an authority Profile or target a Grant.
