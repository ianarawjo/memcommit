# Recursive Share bundle

This ordered color-PTY set records `mem share practice -r`: endpoint choice,
complete lexical-subtree review, in-view endpoint Browse and replacement,
exact-command Apply, receiver verification, cancellation, and fail-closed
rejection after subtree membership changes.

## Interaction log

| Capture | Exact command | PTY | Profile / current Context | Preceding keys or state | Visible state | Durable mutation |
|---|---|---|---|---|---|---|
| `01-endpoint-choice` | `mem share practice -r` | `180×52` | `share-sender` / `practice` | Launch with two valid SHARE endpoints | Exact endpoint picker; `government/healthcare-agent` focused | None |
| `02-recursive-bundle-entry` | same | `180×52` | same | `Enter` | `FROM → TO → MEMORIES → APPLY` entry; complete compact roster, selected endpoint, full Memory UIDs, and explicit recursive command are all visible | None |
| `03-descendant-context-focused` | same | `180×52` | same | `Down`, `Down` | First lexical descendant is an independent reviewed Source member | None |
| `04-endpoint-focused` | same | `180×52` | same | `Tab` | Separate `TO · SHARE ENDPOINT` Surface is focused; Enter is visibly bound to Browse | None |
| `05-endpoint-browse` | same | `180×52` | same | `Enter` | Complete authorized endpoint catalog shows current `government/healthcare-agent` and alternative `research/archive-agent` | None |
| `06-endpoint-updated` | same | `180×52` | same | `Down`, `Enter` | Viewer returns to focused `TO`; endpoint and exact Apply command both show `research/archive-agent` | None |
| `07-descendant-memory-focused` | same | `180×52` | same | `Down`, `Down` | Descendant-owned Memory is attributed by complete Memory UID and exact Source Context | None |
| `08-exact-apply` | same | `180×52` | same | `Tab` | `APPLY` is focused with the exact explicit recursive command and `[ PRESS ENTER TO APPLY ]`; still not sent | None |
| `09-success-receipt` | same | `180×52` | same | `Enter` | One recursive Share receipt names the updated endpoint, Context and Memory totals, consent digest, and receiver root | Four receiver-owned Contexts created as one exception-atomic batch |
| `10-read-only-receiver-verification` | same | `180×52` | same | `V` | Root and lexical suffixes exist under the updated receiver endpoint with bundle indices `1/4` through `4/4`; Source/current unchanged | None after Apply |
| `11-cancelled-bundle-verification` | `mem share practice -r` | `180×52` | fresh `share-sender` / `practice` | Select endpoint with `Enter`, then `Escape` from viewer | Cancellation receipt and zero received Contexts | None |
| `12-stale-membership-failure` | prepared equivalent of `mem share practice -r --to government/healthcare-agent` | `180×52` | fresh `share-sender` / `practice` | Add `practice/late` after preview, then attempt Apply | Stale bundle rejected and zero received Contexts | Source test fixture gains one child; receiver unchanged |
| `13-unavailable-entry` | `mem share practice -r` | `180×52` | fresh `share-sender` / `practice` | Launch after removing every SHARE Grant from the fixture registry | Read-only `FROM → TO → MEMORIES → APPLY` projection; endpoint and Apply are explicitly unavailable | None |
| `14-unavailable-close-verification` | same | `180×52` | same | `Escape` | Cancellation receipt, zero received Contexts, and unchanged Source/current | None |

The recursive range contains only ordinary local lexical descendants. It does
not follow embedded Context edges. Empty structural Context members are
preserved when the complete bundle contains at least one Memory.

The harness removes `NO_COLOR`, sets `TERM=xterm-256color`,
`COLORTERM=truecolor`, and prompt-toolkit 24-bit color, verifies the live
`180×52` size in every stream, and renders each PNG from its matching actual
PTY `.typescript` bytes. Regenerate from the repository root with:

```sh
python agent-records/screenshots/mem-share-recursive-20260822/capture.py
```
