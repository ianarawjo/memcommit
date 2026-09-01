# Trace default Viewer capture

These captures exercise the restored default read-only Viewer for complete
Context and direct-local-Memory Trace requests. They use an isolated Store and
the repository source through `PYTHONPATH`; no provider is connected.

## Environment

- PTY: `180` columns × `52` rows, verified by `stty size`
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` removed
- Profile/Store: isolated temporary `HOME`
- Current Context: `practice/rules`
- Durable effect: none; the capture hashes the complete `.mem` tree before and
  after every Viewer and piped request

## Ordered interaction log

| Image | Exact command and preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-context-trace-viewer-entry.png` | `mem trace practice/rules --all` | Context Trace opens directly in the single `CONTEXT LINEAGE` Viewer | None |
| `02-context-trace-viewer-scrolled.png` | preceding state, then `PgDn` | Older Context operations remain inside the same bounded Viewer | None |
| `03-context-trace-viewer-closed.png` | preceding state, then `Esc` | Viewer closes and the shell reports successful read-only completion | None |
| `04-memory-trace-viewer-entry.png` | `mem trace MEMORY --context practice/rules --all` | Direct Memory Trace opens directly in the single `LINEAGE` Viewer | None |
| `05-memory-trace-viewer-scrolled.png` | preceding state, then `PgDn` | Older Memory revisions and inline diffs remain scrollable | None |
| `06-memory-trace-viewer-closed.png` | preceding state, then `Esc` | Viewer closes and the shell reports successful read-only completion | None |
| `07-piped-trace-static-read-only.png` | `mem trace MEMORY --context practice/rules --limit 3 \| sed -n 1,24p` | Non-TTY stdout retains the bounded static Trace document and names hidden older operations | None |

`MEMORY` is the exact full UID created in the isolated Store. The capture script
resolves it from `practice/rules/context.json` rather than hard-coding an
identity.
