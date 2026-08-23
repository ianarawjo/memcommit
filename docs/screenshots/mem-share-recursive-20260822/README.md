# Recursive Share bundle

This ordered color-PTY set records `mem share practice -r`: endpoint choice,
complete lexical-subtree review, explicit Send, receiver verification,
cancellation, and fail-closed rejection after subtree membership changes.

## Interaction log

| Capture | Exact command | PTY | Profile / current Context | Preceding keys or state | Visible state | Durable mutation |
|---|---|---|---|---|---|---|
| `01-endpoint-choice` | `mem share practice -r` | `180×52` | `share-sender` / `practice` | Launch with two valid SHARE endpoints | Exact endpoint picker; `government/healthcare-agent` focused | None |
| `02-recursive-bundle-entry` | same | `180×52` | same | `Enter` | Compact one-line roster shows the root, all four Context names/counts, three-Memory total, endpoint, and not-sent state without member cards | None |
| `03-descendant-context-focused` | same | `180×52` | same | `Down`, `Down` | First lexical descendant is an independent reviewed Context member | None |
| `04-descendant-memory-focused` | same | `180×52` | same | `Tab`, `Down` | Descendant-owned Memory is visibly attributed to its exact Source Context | None |
| `05-send-bundle-approval` | same | `180×52` | same | `Tab` | Sole `SEND CONTEXT BUNDLE` action focused; still not sent | None |
| `06-success-receipt` | same | `180×52` | same | `Enter` | One recursive Share receipt with Context and Memory totals, consent digest, and receiver root | Four receiver-owned Contexts created as one exception-atomic batch |
| `07-read-only-receiver-verification` | same | `180×52` | same | `V` | Root and lexical suffixes exist with bundle indices `1/4` through `4/4`; Source/current unchanged | None after Send |
| `08-cancelled-bundle-verification` | `mem share practice -r` | `180×52` | fresh `share-sender` / `practice` | Select endpoint with `Enter`, then `Escape` from viewer | Cancellation receipt and zero received Contexts | None |
| `09-stale-membership-failure` | prepared equivalent of `mem share practice -r --to government/healthcare-agent` | `180×52` | fresh `share-sender` / `practice` | Add `practice/late` after preview, then attempt Send | Stale bundle rejected and zero received Contexts | Source test fixture gains one child; receiver unchanged |

The recursive range contains only ordinary local lexical descendants. It does
not follow embedded Context edges. Empty structural Context members are
preserved when the complete bundle contains at least one Memory.

The harness removes `NO_COLOR`, sets `TERM=xterm-256color`,
`COLORTERM=truecolor`, and prompt-toolkit 24-bit color, verifies the live
`180×52` size in every stream, and renders each PNG from its matching actual
PTY `.typescript` bytes. Regenerate from the repository root with:

```sh
python docs/screenshots/mem-share-recursive-20260822/capture.py
```
