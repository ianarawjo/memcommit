# Conflict finding → Resolve typed handoff

These snapshots record the explicit `mem find-conflicts --select` path entering
ordinary Resolve through one typed finding receipt. The capture uses the real
prompt-toolkit applications in a color-capable `180×52` PTY with
`TERM=xterm-256color`, `COLORTERM=truecolor`, and `NO_COLOR` removed. The
provider is deterministic and process-local; the store is isolated per path.

Fixture orientation:

- current Context: `quality/capture`
- Source: two direct Memories that give incompatible daily opening times plus
  one exact weekend schedule that grounds the later Resolve repair
- finder result: one `YES` conflict over the exact pair
- Resolve proposal: one verified `UPDATE` that scopes the later time to weekends
- public command: `mem find-conflicts --select`

## Ordered success path

1. `01-finder-setup-entry.png` — command launch; frozen readable target tree is
   focused; no provider or durable mutation.
2. `02-finder-scope.png` — `Tab`; shared target-mode/reach control is focused;
   no provider or durable mutation.
3. `03-finder-run-approval.png` — `Tab`; exact finder run action is focused; no
   provider or durable mutation.
4. `04-conflict-report.png` — `Enter`; `find_conflicts` has inspected the frozen
   three-Memory Source. The compact browser reports `2/3` Memories involved and
   `1/3` pairs flagged, keeps the reason and question, and exposes no scope
   taxonomy; Source is unchanged.
5. `05-resolve-analysis.png` — `Enter`; the typed handoff has been revalidated,
   Resolve has run Fit/candidate/grounding/post-Fit analysis over the complete
   frozen Source, and the single verified plan is focused in the compact
   execution surface; no mutation yet.
6. `06-apply-row-ready.png` — `Down`; `APPLY VERIFIED PLAN · 1/1 READY` is the
   focused exact action; no second report or confirmation screen intervenes.
7. `07-success-receipt-and-store-verification.png` — `Enter`; the exact update
   is applied, the durable receipt reports one update and one checkpoint, and
   the same terminal canvas includes the read-only check of the
   weekend-qualified Memory and ordered provider operations.

## Stale-source safety branch

8. `08-stale-source-rejected.png` — fresh launch, `Tab`, `Tab`, `Enter` runs
    the finder; then `Enter` requests the conflict handoff. The
    harness inserts one concurrent Source change between those stages. Resolve
    rejects the stale finding before opening its provider: the operation list
    contains only `find_conflicts`, there is no Resolve checkpoint, and the only
    durable difference is the deliberately injected concurrent Memory.

Each PNG has a matching `.txt` terminal canvas and color-preserving
`.typescript` byte stream. Regenerate the ordered set with:

```sh
python agent-records/screenshots/quality-conflict-resolve-handoff-20260816/capture.py
```
