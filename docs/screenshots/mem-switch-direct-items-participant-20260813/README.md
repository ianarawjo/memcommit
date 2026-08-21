# `mem switch` direct-item source-marker capture log

This ordered color-PTY record verifies that the shared Context picker exposes
every direct item form under its owning Context instead of treating the
namespace tree as evidence of Embed reach. It uses the active Study Participant
Profile and the real `task-1/participant/construction-updates` Context, whose
persisted direct order contains six local embedded Contexts.

The lexical child rows remain ordinary `▸` Context-tree rows. Pressing `m`
opens a separate direct-item layer under the selected parent, where each
persisted occurrence is rendered as `[context UID] · VIA EMBED`. The existing
granted `task-1/campus-wiki` row retains `READ GRANT`; Grant attachment is not
reinterpreted as a namespace or Embed edge.

## Reproduction frame

- Command: `mem switch`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, set and verified before launch
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Profile: `study-20260813T135528Z-d61e7a16 · Participant`
- Current Context: `task-1/description-atomized`
- Inspected Context: `task-1/participant/construction-updates`
- Durable scope: cancellation only; no switch, checkpoint, Context write, or
  Profile-store byte change

The capture command was:

```bash
env -u NO_COLOR TERM=xterm-256color COLORTERM=truecolor \
  python docs/screenshots/mem-switch-direct-items-participant-20260813/capture.py
```

The driver disables command-attempt logging, hashes every active Profile-store
file before launch and after cancellation, and fails unless the complete byte
digest and current Context remain unchanged.

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-switch-entry.png` | Launch `mem switch` | The real shared picker opens on current `task-1/description-atomized` with only its ancestor chain expanded | None |
| `02-all-contexts-expanded.png` | `A` | All lexical Context branches expand; Grant rows retain their access annotations | None |
| `03-embed-parent-selected.png` | `Down`, `Down` | `task-1/participant/construction-updates` owns the Context cursor; its lexical children are visible but do not claim Embed reach | None |
| `04-all-direct-items-visible.png` | `m` | Six separate direct-item rows appear in persisted order as `[context UID] · VIA EMBED`, while the lexical child rows remain below them | None |
| `05-embedded-context-focused.png` | `Down` | The first embedded Context occurrence becomes a read-only viewport stop; the parent remains the semantic Switch selection and Enter is preview-only | None |
| `06-cancelled-and-show-verified.png` | `Escape` | Cancellation receipt, unchanged complete-store byte digest/current Context, and actual `mem show` direct-order verification | None |

The same shared projection also labels directly owned Memories, MemoryRefs, and
QueryContextRefs as `memory`, `memory ref`, and `query view`. Only the embedded
Context occurrence receives `VIA EMBED`; the global lexical Context row does
not.

This set remains tied to the named 2026-08-13 Participant Profile and preserves
the footer wording recorded in that frozen study environment. The current
shared controller now spells the same unchanged behavior as `m THIS Context`
and `M EVERY Context`; the reproducible disposable-Store evidence is in
[`../distill-memory-preview-20260817/`](../distill-memory-preview-20260817/README.md).
