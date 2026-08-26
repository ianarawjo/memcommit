# Context and Memory Reference capture log

This ordered set records the shared immutable Reference flow for both Context
and Memory units, including the direct/recursive Context scope boundary and a
self-reference failure with no partial durable state.

## Reproduction frame

- Command: `python agent-records/docs/screenshots/reference-context-memory-20260820/capture.py`
- Commands under capture: bare `mem reference`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: isolated local fixtures; host Profiles and Grants
  are excluded
- PTY: `180` columns × `52` rows, verified by each child
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset,
  and command-attempt logging disabled
- Renderer: cumulative real PTY ANSI bytes replayed through `pyte` at the full
  Menlo terminal canvas; `.typescript` and `.txt` evidence accompany every PNG

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-context-entry.png` | Launch | Context is the explicit default snapshot unit | None |
| `02-context-source.png` | `Tab` | Source Context tree owns focus; `a-source` is selected independently from current Target `target` | None |
| `03-context-direct-scope.png` | `Tab` | `DIRECT · -d` is selected and its exact-frame meaning is visible | None |
| `04-context-recursive-scope.png` | `Right` | `RECURSIVE · -r` is selected; lexical descendants and local embeds are included | None |
| `05-context-target.png` | `Tab` | Target tree owns focus and identifies the only Context that may change | None |
| `06-context-exact-command.png` | `Tab` | Exact recursive Context Reference command and immutable effects are reviewed | None |
| `07-context-success.png` | `Enter` | TUI closes with one typed Context snapshot receipt | One Context Reference and one checkpoint in `target` |
| `08-context-source-deletion-verification.png` | `V`, `Enter` | Source root, descendant, and embedded Context are deleted; retained package still exposes all three facts | Source fixtures deleted only after Reference publication |
| `09-memory-mode.png` | Separate launch, `Right` | Memory is selected as the snapshot unit; Context scope control is absent | None |
| `10-memory-selected.png` | `Tab`, `Down`, `Enter` | One exact directly owned Source Memory is checked | None |
| `11-memory-target.png` | `Tab` | Target remains an independently reviewed local Context | None |
| `12-memory-exact-command.png` | `Tab` | Exact full-UID Memory Reference command is reviewed | None |
| `13-memory-success.png` | `Enter` | TUI closes with one typed Memory snapshot receipt | One Memory Reference and one checkpoint in `target` |
| `14-memory-read-only-verification.png` | `V`, `Enter` | Direct Store read confirms exact retained wording and unchanged Source | None |
| `15-self-reference-blocked.png` | Separate one-Context launch, `Tab` ×4, `Enter` | Exact Apply rejects using one Context as both Source and Target | None |
| `16-self-reference-no-partial-state.png` | `Escape` | Cancellation closes and Store verification reports zero Reference checkpoints | None |

Reference captures the current Context name once. Memory mode binds one direct
Memory and its owning Source revision. Context mode binds every local Context
record contributing retained bytes. Apply holds those Source bindings through
the Target compare-and-set and checkpoint, so drift or an invalid self-target
publishes no partial snapshot.
