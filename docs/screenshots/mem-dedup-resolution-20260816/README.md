# Dedun semantic redundancy Resolution Session

These snapshots record the flagless `mem dedun` path from semantic discovery
through confirmed evidence, survivor review, and exact Apply. They use real prompt-toolkit
applications in a color-capable `180×52` PTY with `TERM=xterm-256color`,
`COLORTERM=truecolor`, and `NO_COLOR` removed. The provider is deterministic
and process-local; each scenario has a fresh isolated Store.

Fixture orientation:

- current Context: `dedup/capture`;
- Source: two semantically equivalent weekday-opening Memories plus one
  unrelated closing-time Memory;
- finder result: one `SEMANTIC_EQUIVALENT` link;
- Dedun recommendation: retain the first existing Context-order UID unchanged;
- public command: `mem dedun`.

## Ordered success path

| # | State | Preceding keys or action | Visible boundary | Durable effect |
| --- | --- | --- | --- | --- |
| 01 | Finder setup entry | Launch command | Frozen readable Context target tree | None |
| 02 | Finder scope | `Tab` | Shared target-mode and reach controls | None |
| 03 | Finder run approval | `Tab` | Exact read-only finder run action | None |
| 04 | Duplicate report | `Enter` | Complete process-local finder result; Source unchanged | None |
| 05 | Duplicate item | `Tab`, `Down` | Exact duplicate finding row | None |
| 06 | Duplicate detail | `Enter` | Classification, source Memories, and reason | None |
| 07 | Finder Responses | `Tab` | `CONFIRM LINK`, `REJECT LINK`, `DEFER`, then free Response | None |
| 08 | Link confirmed | `Enter` | Confirmation is checked but remains process-local | None |
| 09 | Dedun evidence submission | `Tab`, `Tab` | To Do submits only confirmed semantic redundancy links to Dedun resolution | None |
| 10 | Dedun plan entry | `Enter` | Fresh Source/authority validation and connected-group report | None |
| 11 | Redundancy group detail | `Tab`, `Enter` | Exact members, evidence links, and unchanged-survivor rule | None |
| 12 | Survivor Responses | `Tab` | Existing member UIDs are the only legal choices | None |
| 13 | Survivor selected | `Enter` | Context-order recommendation checked; no deletion yet | None |
| 14 | Ready for review | `Tab`, `Tab` | To Do exposes a separate final review | None |
| 15 | Exact Apply review | `Enter` | Full evidence, group/Memory selection, frozen revision, effects, Undo | None |
| 16 | Success receipt | `Enter` | One survivor, one absorbed UID, and checkpoint are reported | One `dedun` checkpoint |
| 17 | Read-only verification | `Enter` | Reload shows unchanged survivor, unrelated Memory, and one checkpoint | None beyond 16 |

## Safety branches

18. `18-stale-source-rejected.png` — after the link is confirmed but before
    Dedun resolution opens, the harness adds a concurrent Source Memory. Dedun
    rejects the evidence before review; no checkpoint is published.
19. `19-inbound-reference-blocked.png` — a fresh run reaches exact Apply while
    another Context contains a `MemoryRef` to the would-be absorbed UID. The
    complete Apply fails visibly under the command lock.
20. `20-inbound-no-checkpoint-verification.png` — after closing the failed
    review, both duplicate UIDs still exist and no checkpoint was created.

Each PNG has a matching `.txt` terminal canvas and color-preserving
`.typescript` byte stream. Regenerate with:

```sh
python docs/screenshots/mem-dedup-resolution-20260816/capture.py
```
