# Saved Impact launcher captures

These images record the new aggregate and Atomize-filtered saved-Impact routes
in actual color-capable PTYs. The capture uses isolated temporary stores with
one current Atomize analysis and one singleton directional Update Impact plan.
The seed providers run before each command; every launcher/open verification
records zero provider calls while the captured command is active.

## Environment

- PTY: `180` columns × `52` rows, verified by the child process
- Terminal: `TERM=xterm-256color`, `COLORTERM=truecolor`
- Renderer: actual prompt-toolkit PTY byte stream rendered with `pyte`; PNGs
  preserve the complete 180×52 canvas
- Profile: `(unregistered)` isolated capture store
- Current Context: `capture/impact/atomize`
- Commands: `mem impact --sessions` and
  `mem impact atomize --sessions`

## Ordered interaction log

| # | Image | Command / preceding input | Visible state | Durable mutation |
|---|---|---|---|---|
| 1 | `01-aggregate-launcher-entry.png` | `mem impact --sessions` | Aggregate catalog opens recent-first with Update and Atomize rows; Update is focused and its exact Impact metadata is shown | None |
| 2 | `02-atomize-analysis-selected.png` | `Down` | Atomize row is focused; detail exposes the full saved analysis UID and Source/Output binding | None |
| 3 | `03-exact-atomize-impact-opened.png` | `Enter` | The selected exact Atomize analysis opens provider-free in its existing Impact workbench | None; no Context or checkpoint change |
| 4 | `04-aggregate-close-no-write-verification.png` | `q` | Aggregate route exits `0`; Context, checkpoints, workbench bytes, Update Impact-plan bytes, and UIDs remain unchanged; provider calls while open are `0` | None |
| 5 | `05-atomize-filtered-launcher.png` | `mem impact atomize --sessions` | The same launcher is filtered to the saved Atomize analysis only | None |
| 6 | `06-filtered-close-no-write-verification.png` | `Enter`, then `q` | Exact filtered selection exits `0` with the same byte, checkpoint, UID, and provider-free verification | None |

## Reproduction

```bash
python agent-records/docs/screenshots/impact-session-launcher-20260823/capture.py
```

The script fails if the raw stream lacks true-color foreground/background ANSI
or if either close receipt fails its no-write/provider-free assertions.
