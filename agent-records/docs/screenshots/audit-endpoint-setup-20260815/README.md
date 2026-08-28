# Audit endpoint setup PTY trace

Command under test: flagless `mem audit` source setup through
`console.tui.components.endpoint_setup`.

- PTY: `180` columns × `52` rows, verified in the child process.
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`,
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, with `NO_COLOR` removed.  The
  capture script verifies retained ANSI foreground sequences.
- Store: isolated temporary `.mem` root with `audit/current` selected and
  `audit/peer` available; one direct Memory in each Context.
- Provider: not constructed or called during any captured setup state.

## Ordered interaction

| Image | Keys before capture | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-entry-current-source.png` | none | Entry with `audit/current` selected and SOURCE focused | none |
| `02-peer-source-selected.png` | `Down`, `Enter` | `audit/peer` is the retained exact Source | none |
| `03-explicit-continue-action.png` | `Tab` | Explicit `RUN AUDIT ON FROZEN SOURCE` action focused | none |
| `04-read-only-setup-receipt.png` | `Enter` | Process-local selected-name receipt and byte/checkpoint/provider verification | none |
| `05-cancelled-without-source.png` | `Escape` from a fresh entry | `None` receipt and the same read-only verification | none |

The receipt is only the endpoint setup result.  The capture deliberately stops
before Audit's authority check, provider construction, semantic checks, or
session save so the shared component's no-effect boundary is independently
visible.
