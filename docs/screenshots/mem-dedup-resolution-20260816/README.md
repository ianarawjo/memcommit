# Dedun semantic redundancy Resolution Session

These snapshots record the flagless `mem dedun` path from semantic discovery
through confirmed evidence, survivor decisions, exact Apply, compact Receipt,
and provider-free post-application Review. They use real prompt-toolkit
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
| 10 | Dedun decision entry | `Enter` | Compact Items + To Do only; the recommendation is preselected and no Viewer exists | None |
| 11 | Survivor decisions | `Enter` | Exact members and confirmed evidence remain adjacent to the legal survivor choices | None |
| 12 | Alternate survivor selected | `Down`, `Enter` | A different existing UID is staged; no deletion yet | None |
| 13 | Recommendation restored | `Up`, `Enter` | Context-order recommendation is checked again | None |
| 14 | Apply confirmation ready | `Tab`, `Tab` | To Do exposes exact Apply confirmation, not a Review operation | None |
| 15 | Exact Apply confirmation | `Enter` | Frozen command, group/Memory decision, effects, and Undo boundary | None |
| 16 | Compact success receipt | `Enter` | Survivor/absorbed counts, full checkpoint UID, Review route, and recovery | One `dedun` checkpoint |
| 17 | Post-application Review and store verification | `Enter` | `mem review dedun --receipt UID --snapshot` shows immutable applied members/evidence; reload confirms one checkpoint | None beyond 16 |

## Safety branches

18. `18-stale-source-rejected.png` — after the link is confirmed but before
    Dedun resolution opens, the harness adds a concurrent Source Memory. Dedun
    rejects the evidence before the decision workbench; no checkpoint is published.
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

The historical filenames `14-ready-for-review` and `15-exact-apply-review`
remain stable so existing links do not break; their recorded visible states
are now Apply confirmation, while Review occurs only in state 17 after the
checkpoint exists.
