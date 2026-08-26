# Update terminal-session rotation rationale

## Problem

After `mem update` applies and `mem diff` shows the result, a person reasonably
treats that Update as complete. A later command with different Source evidence
is a new work unit. The former singleton behavior instead kept the applied
receipt in the active work slot and rejected the next request with a divergence
error unless `--replace-stage` was supplied. That made the CLI appear to allow
only the first Update, even though the completed receipt was already durable.

## Lifecycle contract

An applied receipt is terminal evidence, not unfinished work. Update now
distinguishes these cases:

- An exact repeat of the applied invocation returns the same receipt without a
  provider call, mutation, or checkpoint.
- A distinct explicit invocation starts a new Update automatically. Before the
  new staged record is published, the previous applied receipt is retained in
  immutable UID-addressed receipt storage. Output names its short UID and the
  exact `mem review update --session UID` command.
- A staged receipt remains an unfinished proposal and still blocks different
  work unless the person explicitly chooses `--replace-stage`.
- An undone receipt remains attached to its exact Redo path. Starting unrelated
  work still requires an explicit lifecycle choice so Redo is not displaced by
  surprise.

When a distinct command omits `--goal`, it does not inherit the completed
Update's Goal focus. An explicitly supplied Goal is frozen and revalidated as
usual.

## Integrity boundary

Planning happens before active-record replacement. Provider, decoding, or
validation failure therefore leaves the previous applied receipt active. On
successful planning, `MemoryStore.save_staged_update` uses compare-and-swap
against the exact active record observed at command start, archives terminal
evidence, and publishes the new staged session. Concurrent work cannot be
silently overwritten. Review remains available by immutable session UID after
the singleton moves to the new work unit.

## Scope and alternatives

Requiring `--replace-stage` for terminal evidence was rejected because it
conflates “discard unfinished work” with “begin work after completion.” Simply
overwriting the singleton was also rejected because it would lose an obvious
review route and weaken historical evidence. The chosen rotation preserves
both the new-work mental model and exact retry idempotence.

This decision changes Update only. Atomize already identifies and reopens its
applied analysis/output pair idempotently, while Meld has a richer continuing
relation session and explicit restart contract. A later operation-by-operation
lifecycle audit may adopt the same principle where terminal evidence still
occupies a new-work slot, but this change does not assume that every semantic
operation has the same session boundary.
