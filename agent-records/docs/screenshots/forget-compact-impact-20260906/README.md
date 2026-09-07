# Compact Forget Impact and Apply — ordered PTY record

This is agent-produced execution evidence for the compact direct Forget UI. It supersedes the earlier full-report approval capture for current behavior; it does not imply independent human review.

## Reproduction

Run `python agent-records/docs/screenshots/forget-compact-impact-20260906/capture.py` from the repository root with `pexpect`, `pyte`, and Pillow available. The child uses the repository `.venv/bin/python` and the real console entrypoint in a PTY. Only the provider response is deterministic; no live provider, personal Context, or personal profile registry is used. Temporary stores are deleted after each scenario.

All images render the actual ANSI-preserving PTY byte stream with pyte/Pillow, rather than synthetic UI text. The live terminal is asserted as **180 columns × 52 rows** before launching the command. `NO_COLOR` is removed; `TERM=xterm-256color`, `COLORTERM=truecolor`, and 24-bit prompt-toolkit color are set. Both foreground and background ANSI sequences are checked for every interactive scenario. The full terminal canvas is preserved at 1832 × 1124 pixels. Matching `.typescript` and `.txt` files accompany each PNG.

## Commands and state

All ordinary scenarios use an isolated authoring profile, current Context `notes`, and the command:

```text
mem forget "Forget the obsolete desk location and access code; keep accessibility guidance." --from notes
```

The granted scenario uses current Context `participant` in isolated authoring, an isolated managed `authority` profile owning `notes`, and a READ/UPDATE/DELETE Grant. Its exact command is:

```text
mem forget "Forget the obsolete desk location and access code; keep accessibility guidance." --from granted/authority/notes
```

The no-op scenario runs `mem forget "Keep everything unchanged." --from notes` and bypasses approval. Every scenario verifies via `mem show notes --direct` (granted: `mem show granted/authority/notes --direct`). The Enter after each receipt is a capture-harness gate before that read-only command, not an additional application approval.

Fixture setup creates three Memories before the displayed command. During analysis, the provider gate holds the single complete response long enough to capture entry. Afterward the exact batch proposes one TRANSFORM, one DROP, and one KEEP. No filtering or browsing calls the provider again.

## Ordered interactions

| Image | Scenario | Preceding keys or input | Durable effect at this step |
| --- | --- | --- | --- |
| [01-analysis-entry.png](01-analysis-entry.png) | apply | explicit command; no keys | fixture setup only |
| [02-apply-impact.png](02-apply-impact.png) | apply | provider response; no keys | none; complete process-local batch only |
| [03-change-reason.png](03-change-reason.png) | apply | Down; Enter on TRANSFORM | none |
| [04-keep-expanded.png](04-keep-expanded.png) | apply | Down twice; Enter on KEEP group | none |
| [05-keep-reason.png](05-keep-reason.png) | apply | Down; Enter on retained Memory | none |
| [06-apply-focused.png](06-apply-focused.png) | apply | Up; Enter closes KEEP group; Tab to Apply | none |
| [07-apply-receipt.png](07-apply-receipt.png) | apply | Enter on Apply | owner edit/removal/checkpoint |
| [08-apply-verification.png](08-apply-verification.png) | apply | harness gate Enter; mem show notes --direct | none |
| [09-cancel-impact.png](09-cancel-impact.png) | cancel | provider response; no keys | none; complete process-local batch only |
| [10-cancel-receipt.png](10-cancel-receipt.png) | cancel | Escape | none from Forget; stale scenario preserves a concurrent write |
| [11-cancel-verification.png](11-cancel-verification.png) | cancel | harness gate Enter; mem show notes --direct | none |
| [12-granted-impact.png](12-granted-impact.png) | granted | provider response; no keys | none; complete process-local batch only |
| [13-granted-receipt.png](13-granted-receipt.png) | granted | Enter on Apply | owner edit/removal/checkpoint |
| [14-granted-verification.png](14-granted-verification.png) | granted | harness gate Enter; mem show notes --direct | none |
| [15-noop-receipt-and-verification.png](15-noop-receipt-and-verification.png) | noop | explicit all-KEEP command, then read-only Show | none |
| [16-stale-impact.png](16-stale-impact.png) | stale | provider response; no keys | none; complete process-local batch only |
| [17-stale-receipt.png](17-stale-receipt.png) | stale | Enter on Apply | none from Forget; stale scenario preserves a concurrent write |
| [18-stale-verification.png](18-stale-verification.png) | stale | harness gate Enter; mem show notes --direct | none |

## Verified boundaries

- Apply returns the same frozen batch; the command then edits/removes exactly two Memories and creates one owner checkpoint. KEEP remains unchanged.
- The Viewer starts with Source, instruction, changed Memory diffs, and a collapsed KEEP count. There is no ITEMS, ASSESSMENT, WHAT APPLIES, or repeated Apply prose. Change and retained-Memory reasons expand independently from the KEEP group; Tab goes directly to the single Apply control.
- Escape leaves Source and checkpoints unchanged. All-KEEP bypasses the screen and creates no checkpoint.
- Granted Apply displays the public path and GRANT annotation, changes the authority owner, and leaves the participant Context and checkpoint list unchanged.
- The stale scenario injects an independent Source write after the approval UI returns and before Forget applies. CAS rejects the old batch; all original Memories plus the concurrent addition remain, with no Forget checkpoint or partial mutation.
- Every scenario asserts exactly one provider call, normal command exit status, and the expected post-command store contents.

Capture base HEAD: `b61e7222a323ae8de9578070792c75777361f3a1` with the focused implementation changes present. The accompanying code commit identifies the implemented revision.
