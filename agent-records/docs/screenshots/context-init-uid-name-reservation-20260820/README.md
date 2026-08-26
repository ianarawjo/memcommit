# Context Init UID-selector name reservation

This ordered set records the ordinary `mem init` TUI rejecting a new root
Context name that would be indistinguishable from a visible Memory UID prefix.
It then accepts the slash-qualified `fit/deadbeef`, creates exactly that empty
Context, and verifies it through a separate read-only command.

The capture uses a real `180 × 52` color-capable PTY and an isolated temporary
home. `TERM=xterm-256color` and `COLORTERM=truecolor` are set, `NO_COLOR` is
removed, and cursor-position requests are answered by the recorder.

```bash
python agent-records/docs/screenshots/context-init-uid-name-reservation-20260820/capture.py
```

| # | File | Exact command / preceding keys | Visible state | Durable mutation |
| --- | --- | --- | --- | --- |
| 01 | `01-name-entry` | `mem init`; no key | Exact-name editor with its default `new-context` value at verified `180×52` | none |
| 02 | `02-uid-shaped-name-entered` | type `deadbeef` | Candidate visible before validation | none |
| 03 | `03-uid-shaped-name-rejected` | `Enter` | Shared validator explains that a Context name cannot have Memory UUID/prefix shape; editor remains open | none |
| 04 | `04-namespaced-name-entered` | replace with `fit/deadbeef` | Slash-qualified unambiguous Context name is staged | none |
| 05 | `05-init-success` | `Enter` | Exact initialization receipt for `fit/deadbeef` | creates and selects `fit/deadbeef` |
| 06 | `06-read-only-verification` | separate `mem show --context fit/deadbeef` | Context exists with zero Memories | none |

Existing legacy UUID-shaped Contexts are not deleted or made unreadable. They
remain explicit-Context operands and can be migrated separately.
