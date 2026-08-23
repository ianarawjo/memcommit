# Granted Memory Reference TUI — 2026-08-23

This ordered capture records one retained Memory Reference from the explicit
public Grant locator `shared/source` into the ordinary local Context
`workspace`. The Grant has exactly `READ + DERIVE + EXPORT + SAVE_ANALYSIS`;
the authority-private Context name never becomes a TUI operand.

- Command: bare `mem reference`, followed by the TUI's reviewed exact command
  `mem reference MEMORY_UID --from shared/source --into workspace`.
- PTY: `180` columns × `52` rows, verified inside the child before entry.
- Color environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, with
  `NO_COLOR` removed; `capture.py` rejects a stream without ANSI foreground
  color and the exact PTY-size receipt.
- Profile/current Context: active `authoring` Profile; current ordinary local
  Context `workspace`; managed authority Profile `reference-authority`.
- Catalog contract: Memory Source contains local Contexts plus only exact
  public Grant Contexts authorized for the four retained-reference
  permissions. Context Reference Source and Target remain local-only. Memory
  lookup begins only after selecting the qualified owner; no bare UID scan is
  performed across Grants.

## Ordered interaction log

1. `01-entry-context-unit` — bare command entry; `SNAPSHOT UNIT` is focused in
   its default Context mode. No durable mutation.
2. `02-memory-unit-grant-source` — key `Right`; Memory mode is staged and the
   explicit `GRANT shared/source` Source row plus its direct Memory preview are
   visible. No durable mutation.
3. `03-granted-source-memory-selected` — keys `Tab`, `Down`, `Enter`; the exact
   direct Memory below `shared/source` is checked. No durable mutation.
4. `04-local-target` — key `Tab`; Target focus shows only the local
   `workspace` catalog. No durable mutation.
5. `05-exact-command-approval` — key `Tab`; the complete command names
   `--from shared/source` and `--into workspace` before approval. No durable
   mutation.
6. `06-success-receipt` — key `Enter`; Freeze revalidates the Grant and Source
   snapshot, then one immutable Memory Reference and one checkpoint are saved
   in `workspace`. The authority Store is unchanged.
7. `07-read-only-retained-verification` — key `Enter` at the capture gate;
   `mem show REFERENCE_UID --context workspace` reads the retained bytes, then
   the child verifies the saved public Source name, Grant UID, authority
   Context binding, and read-only snapshot kind. This step performs no durable
   mutation.

Each stem has a cumulative raw `.typescript`, a final-canvas `.txt`, and a
color-preserving `.png`. Run `python
docs/screenshots/granted-memory-reference-20260823/capture.py` from the
repository root to refresh the complete set.
