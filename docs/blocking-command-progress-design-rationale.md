# Blocking command progress design rationale

## Problem

Provider-backed commands can spend tens of seconds inside their first
synchronous provider call before printing a result or opening a workbench.
`mem find` previously animated later interactive turns, but its initial search,
`mem compare`, and the three quality finders left the existing terminal screen
unchanged. That looked indistinguishable from a stalled process.

## Contract

Blocking command progress uses one operation-neutral transient line:

```text
MEM COMPARE · 2/2 · ANALYZING RELATIONS … · 18s
```

- `.`, `..`, and `…` cycle to prove that the local process remains alive.
- `step/total` and the stage label change only at host-observable orchestration
  boundaries. Elapsed time continues within a provider call.
- No percentage or provider-internal stage is shown because the one-shot
  provider API exposes neither.
- The line is emitted only to an interactive stderr TTY and is erased before
  normal output or an error is printed. Redirected output, snapshot contracts,
  and stdout parsing therefore remain stable.
- Untrusted operation or stage text is terminal-escaped and folded to one line.

The first rollout covers the initial provider wait in `find`, `compare`,
`find-ambiguities`, `find-conflicts`, and `find-duplicates`. The existing Find
chat busy indicator shares the same animation frames and interval. Other
blocking commands can adopt `CommandProgress` without duplicating terminal
threading or inventing a different liveness vocabulary.

## Boundaries and alternatives

This is liveness and coarse progress, not cancellation or a completion
estimate. A stuck provider call will keep animating and its existing timeout
remains authoritative. Streaming provider events could support richer progress
later, but changing the provider protocol is intentionally outside this UI
fix. Rich's generic spinner was not used because it would not establish the
shared stage contract or preserve the existing `.`, `..`, `…` visual language.
