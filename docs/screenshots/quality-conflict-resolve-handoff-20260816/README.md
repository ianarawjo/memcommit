# Conflict finding → Resolve typed handoff

These snapshots record the public, flagless `mem find-conflicts` path entering
ordinary Resolve through one typed finding receipt. The capture uses the real
prompt-toolkit applications in a color-capable `180×52` PTY with
`TERM=xterm-256color`, `COLORTERM=truecolor`, and `NO_COLOR` removed. The
provider is deterministic and process-local; the store is isolated per path.

Fixture orientation:

- current Context: `quality/capture`
- Source: two direct Memories that give incompatible daily opening times
- finder result: one `YES` conflict over the exact pair
- Resolve proposal: one verified `UPDATE` that scopes the later time to weekends
- public command: `mem find-conflicts`

## Ordered success path

1. `01-finder-setup-entry.png` — command launch; frozen readable target tree is
   focused; no provider or durable mutation.
2. `02-finder-scope.png` — `Tab`; shared target-mode/reach control is focused;
   no provider or durable mutation.
3. `03-finder-run-approval.png` — `Tab`; exact finder run action is focused; no
   provider or durable mutation.
4. `04-conflict-report.png` — `Enter`; `find_conflicts` has inspected the frozen
   two-Memory Source and the complete process-local report is focused; Source is
   unchanged.
5. `05-conflict-item.png` — `Tab`, `Down`; the exact conflict row is selected;
   no provider or durable mutation.
6. `06-conflict-detail.png` — `Enter`; the conflict classification, source-linked
   evidence, reason, and question are open; no provider or durable mutation.
7. `07-resolve-handoff.png` — `Tab`, `Tab`, `Tab`; `TO DO` offers Resolve for
   the selected conflict. This is still a process-local handoff; no provider or
   durable mutation.
8. `08-resolve-analysis.png` — `Enter`; the typed handoff has been revalidated,
   Resolve has run Fit/candidate/grounding/post-Fit analysis over the complete
   frozen Source, and ordinary Resolve review is open; no mutation yet.
9. `09-verified-repair-detail.png` — `Tab`, `Enter`; the required Resolve item
   and verified candidate detail are open; no mutation.
10. `10-repair-selected.png` — `Tab`, `Enter`; the update candidate is selected;
    no mutation.
11. `11-ready-for-exact-review.png` — `Tab`, `Tab`; `TO DO` exposes one exact
    final review action; no mutation.
12. `12-exact-apply-review.png` — `Enter`; the full command, frozen revision,
    selected candidate, exact update, Fit guarantee, checkpoint, and recovery
    boundary are displayed; the command is not run yet.
13. `13-success-receipt.png` — `Enter`; the exact update is applied and a durable
    success receipt reports one update and one checkpoint.
14. `14-read-only-store-verification.png` — `Enter`; after the TUI closes, a
    read-only store check shows the weekend-qualified Memory, exactly one
    `resolve` checkpoint, and the ordered provider operations.

## Stale-source safety branch

15. `15-stale-source-rejected.png` — fresh launch, `Tab`, `Tab`, `Enter` runs
    the finder; then `Tab`, `Tab`, `Enter` requests the conflict handoff. The
    harness inserts one concurrent Source change between those stages. Resolve
    rejects the stale finding before opening its provider: the operation list
    contains only `find_conflicts`, there is no Resolve checkpoint, and the only
    durable difference is the deliberately injected concurrent Memory.

Each PNG has a matching `.txt` terminal canvas and color-preserving
`.typescript` byte stream. Regenerate the ordered set with:

```sh
python docs/screenshots/quality-conflict-resolve-handoff-20260816/capture.py
```
