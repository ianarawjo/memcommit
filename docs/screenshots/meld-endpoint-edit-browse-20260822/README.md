# Meld FROM/TO direct-edit and Browse verification

This ordered set focuses only on the compact Directional Meld endpoint form.
It verifies that both direct caret editing and Browse selection replace the
real FROM/TO operand fields, and that the runnable command and returned setup
receipt use those changed values. It deliberately stops before semantic Meld
analysis: endpoint setup must not mutate either Context, create a checkpoint,
save a session, or connect a provider.

## Reproduction frame

- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Adapter: `memcommit.commands.meld.setup.choose_meld_setup`
- Store: one fresh isolated temporary store per route
- Profile: none; the host Profile and host Memory store are not read
- Frozen Contexts: `route/from-a` and `route/from-b`
- Initial endpoints: `FROM route/from-a`, `TO route/from-b`
- Expected edited endpoints: `FROM route/from-b`, `TO route/from-a`
- PTY: `180` columns × `52` rows, verified by every capture
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`,
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, and `NO_COLOR` removed
- Buffer: the compact form remains in the main terminal buffer; the harness
  rejects an alternate-screen transition
- Renderer: actual ANSI PTY bytes replayed through `pyte`; every PNG retains
  matching `.typescript` and plain `.txt` evidence

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-direct-from-entry` | launch, `Right`, `Down` | Directional FROM field owns focus; initial command is `mem meld route/from-a route/from-b` | fixture Contexts only |
| `02-direct-from-caret-left` | `Left`×2, `Right`, `Delete` | both arrows move the caret inside FROM, then Delete removes its final `a`; the interior Right does not escape to Browse | none |
| `03-direct-from-replaced` | type `b` | FROM becomes `route/from-b`; duplicate endpoints immediately make the command invalid | none |
| `04-direct-to-replaced` | `Enter`, `Down`, `Left`×2, `Right`, `Delete`, type `a` | the same in-field arrow edit changes TO to `route/from-a`; the runnable command immediately uses the swapped operands | none |
| `05-direct-command-reviewed` | `Enter`, `Down` | exact `mem meld route/from-b route/from-a` start command is focused | none |
| `06-direct-setup-receipt` | `Enter` | returned directional receipt contains the two directly edited endpoint values | none |
| `07-direct-read-only-verification` | `V` | both Context byte streams/current Context/checkpoints/sessions remain unchanged; provider calls `0` | none |
| `08-browse-from-catalog` | new launch, `Right`, `Down`, `Right`, `Enter` | the first Right selects Directional; at the end of FROM, the second Right crosses from caret editing into Browse and opens the complete catalog | fixture Contexts only |
| `09-browse-from-selected-editable` | `Down`, `Enter`, `Left` | Browse writes `route/from-b` into FROM; Left returns from Browse to that same writable field | none |
| `10-browse-to-catalog` | `Down`, `Right`, `Enter`, `Up` | Right at the end of TO enters Browse, which focuses `route/from-a` while the temporary duplicate-endpoint validation remains visible | none |
| `11-browse-to-selected-editable` | `Enter`, `Left` | Browse writes `route/from-a` into TO; the selected value is again directly editable | none |
| `12-browse-command-reviewed` | `Down` | exact runnable command uses the two Browse-selected values | none |
| `13-browse-setup-receipt` | `Enter` | returned directional receipt contains the Browse-selected endpoint values | none |
| `14-browse-read-only-verification` | `V` | Context bytes/current/checkpoints/sessions remain unchanged; provider calls `0` | none |

The keyboard boundary is intentional: FROM and TO are vertically stacked, so
Up/Down moves between endpoint rows. Inside the writable name field,
Left/Right edits the caret; once Right reaches the end, another Right enters
Browse. Tab remains the exhaustive fallback. On Browse, reach, or Memory,
Left/Right moves among the same-row controls. A Browse choice writes into the
exact field rather than maintaining a parallel hidden selection, which is why
Left from Browse immediately exposes the chosen name for further direct
editing.

Reproduce from the repository root with:

```sh
python docs/screenshots/meld-endpoint-edit-browse-20260822/capture.py
```
