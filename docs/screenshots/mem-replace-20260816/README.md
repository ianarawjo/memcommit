# `mem replace` interactive evidence

Captured on 2026-08-16 from the repository command adapter in a real
color-capable `180×52` PTY (`TERM=xterm-256color`, `COLORTERM=truecolor`, and
`NO_COLOR` removed). Every run used a fresh temporary `MemoryStore`; no Study
or user Profile data was opened or changed. The recorder preserves the raw PTY
stream (`.typescript`), terminal text (`.txt`), and rendered terminal image
(`.png`) for each step.

The initial current Context was `replace/demo`. Its direct Memory contained two
occurrences of `Campus`; `replace/demo/child` contained one. The exact command
was equivalent to:

```text
mem replace Campus University --context replace/demo --tui
```

## Successful atomic path

| Snapshot | Preceding input | Visible contract | Durable effect at this step |
| --- | --- | --- | --- |
| `01-entry` | command launch | Pattern and literal replacement are visible; current local Context is selected | None |
| `02-local-context-target` | `Tab`, `Tab` | Focus reaches the shared local Context selector; `ALL` is explicitly labelled `ALL LOCAL CONTEXTS` | None |
| `03-scope-controls` | `Tab` | Target cardinality, lexical reach, embedded reach, literal/regex mode, and case policy are independent | None |
| `04-descendant-scope-selected` | `Down`, `Right` | Lexical descendants are selected while embeds remain excluded | None |
| `05-complete-before-after-review` | `Enter` | One frozen plan shows both owner Contexts, both Memories, and all three exact occurrences | None |
| `06-exact-command-approval` | `Tab` | To Do shows the exact argv, reviewed plan digest, complete effect, and one-command recovery promise | None |
| `07-atomic-apply-receipt` | `Enter` | Apply receipt reports two changed Memories, three occurrences, and two per-Context checkpoints | Both Context changes publish as one command unit |
| `08-read-only-store-verification` | `Enter` | Post-command direct Store read shows both Memories changed and two checkpoints | None; verification is read-only |

## Stale namespace rejection

The second run repeats steps `01` through `06` in another temporary Store. Its
Apply adapter creates an unrelated local Context after review and immediately
before the normal Store Apply. This deliberately changes the frozen local
namespace without changing either target Memory.

| Snapshot | Preceding input | Visible contract | Durable effect at this step |
| --- | --- | --- | --- |
| `09-stale-namespace-rejected` | `Enter` on the reviewed exact command | Apply reports that the Context namespace changed after review and stays in the workbench | Only the injected unrelated Context exists; Replace publishes no Memory/checkpoint effect |
| `10-stale-no-partial-write-verification` | `Q` | Direct Store read shows both original `Campus` Memories and zero checkpoints | None; proves no partial Replace publication |

The capture script asserts the `180×52` terminal size, foreground and
background ANSI color sequences, successful receipt, changed post-image, stale
error, unchanged failure post-image, and zero failure checkpoints.
