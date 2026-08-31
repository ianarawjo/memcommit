# Search Save Context from selection

This ordered set exercises the actual Search command workbench, its
Search-to-selection adapter, and the shared Store-backed
`save_context_from_selection` capability. Each branch runs in its own isolated
explicit Store with Current set to `task/source`; no configured Profile or
existing Context is read or changed.

All captures use a color-capable 180-column by 52-row PTY with
`TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` removed, and
`PROMPT_TOOLKIT_NO_CPR=1`. The Search ranking response is deterministic so the
record isolates Save As behavior; every save, checkpoint, relationship, and
read-only verification uses the production application and persistence code.

## Interaction log

| Capture | Command / preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-search-entry` | `python capture.py --harness COPY <isolated-store>` | Current `task/source`, compact Scope, focused empty Search | none |
| `02-query-entered` | type `accessibility` | Exact Search input before execution | none |
| `03-search-result` | `Enter`, wait | One Source-bound result; COPY, REFERENCE, and EMBED are all visible | none |
| `04-result-checked` | `Space` | Exact result set contains one checked Memory | none |
| `05-copy-mode-selected` | `Tab` | COPY selected in Save As | none |
| `06-copy-save-location` | `Tab`, replace with `task/results/copy` | Exact require-new local destination | none |
| `07-copy-exact-save` | `Tab` | Reviewed `SAVE 1 CHECKED AS COPY` action | none |
| `08-copy-success-receipt` | `Enter` | One Search receipt for the created COPY Context | creates `task/results/copy` in isolated Store |
| `09-copy-read-only-verification` | `Enter` at harness pause | Fresh directly owned Memory, Source unchanged, Current unchanged | none |
| `10-reference-mode-selected` | new isolated run; Search, check, `Tab`, `Right` | REFERENCE selected as immutable snapshot | none |
| `11-reference-save-location` | `Tab`, replace with `task/results/reference` | Exact require-new local destination | none |
| `12-reference-exact-save` | `Tab` | Reviewed `SAVE 1 CHECKED AS REFERENCE` action | none |
| `13-reference-success-receipt` | `Enter` | One Search receipt for the created snapshot Context | creates `task/results/reference` in isolated Store |
| `14-reference-read-only-verification` | `Enter` at harness pause | Immutable snapshot resolves retained content, Source and Current unchanged | none |
| `15-embed-mode-selected` | new isolated run; Search, check, `Tab`, `Right` ×2 | EMBED selected as live relationship | none |
| `16-embed-save-location` | `Tab`, replace with `task/results/embed` | Exact require-new local destination | none |
| `17-embed-exact-save` | `Tab` | Reviewed `SAVE 1 CHECKED AS EMBED` action | none |
| `18-embed-success-receipt` | `Enter` | One Search receipt for the created live-link Context | creates `task/results/embed` in isolated Store |
| `19-embed-read-only-verification` | `Enter` at harness pause | Live Embed resolves Source content, Source and Current unchanged | none |

The capture script asserts the PTY dimensions, foreground and background ANSI
styles, all three visible mode labels, exact Save Location, successful receipt,
direct relationship kind, resolved content, Source preservation, and unchanged
Current Context.
