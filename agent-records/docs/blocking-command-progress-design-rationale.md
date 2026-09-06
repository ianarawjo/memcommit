# Blocking command progress design rationale

## Problem

Provider-backed commands can spend tens of seconds inside a synchronous
provider call before printing a result or reopening a workbench. The first
progress rollout covered Find, Compare, and the quality finders, but Update and
several other command controllers still left the terminal unchanged. The same
wait therefore looked alive in one operation and stalled in another.

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
- `CommandProgress` defaults to its captured stderr TTY status. The command
  wait wrapper preserves its existing override: interactive stdin/stdout or
  explicit `interactive=True` forces the line on, otherwise stderr decides.
  Progress is erased when the work exits; stdout remains owned by the command.
  Fully redirected execution receives no progress text by default.
- Untrusted operation or stage text is terminal-escaped and folded to one line.
- A provider factory may be wrapped lazily. The progress line starts only when
  the reusable workflow actually requests a provider, so a valid saved result
  or cache hit does not flash a false `CONNECTING PROVIDER` state.

Compare, Meld, Forget, Sever, Update, and Audit use `run_command_wait` to
execute one blocking callback behind this line. As of 2026-09-05 the unused
full-screen command-wait branch is removed; it no longer accepts prior-report,
confirmed-input, Context-browser, or Help parameters. Work still runs exactly
once on the calling thread, with the same result and exception propagation.
The retirement rationale and historical UI evidence are preserved in
[`interactive-command-wait-design-rationale.md`](interactive-command-wait-design-rationale.md).

## Coverage audit

The following command boundaries use the shared progress line. This inventory
is presentation coverage, not an operation route classification.

- Update planning and Directional Impact Update planning.
- Atomize analysis from Atomize or Impact, Atomize grounding turns, and final
  normal-form Apply. Apply progress starts only when Dedun or verification
  requests a provider, so exact checkpoint recovery remains silent.
- Meld candidate start/restart and candidate Update planning/verification.
- Search, Compare, Compare rationale, the three quality finders,
  and ambiguity Review creation; initial Compare analysis uses the transient
  line in a TTY.
- Query routing/answering, Translate, Summarize, Rationale, semantic Log and
  Revert selection, Provider Probe, and initial Forget/Sever analysis.

Find follow-up turns and Ground dialogue turns remain inside their full-screen
surfaces. They keep those surfaces responsive and animate there instead of
painting a competing stderr line. Their animation frames and cadence come from
the same shared `.`, `..`, `…` contract. Saved-session browsing, cached
Rationale or Translate views, cached Update or Atomize analysis, and other
provider-free resumes stay silent. Semantic evaluation campaigns retain their
own durable per-case event output because it is a multi-call experiment log,
not one blocking command wait.

The progress boundary belongs to command orchestration rather than provider or
domain modules. This prevents a reusable analysis function from writing to a
terminal when called by tests, another controller, or an already-visible TUI.
It also lets each command name only stages it can actually observe, such as
provider connection, frozen-frame preparation, ranking, or answer generation.

## Boundaries and alternatives

This is liveness and coarse progress, not cancellation or a completion
estimate. A stuck provider call will keep animating and its existing timeout
remains authoritative. Streaming provider events could support richer progress
later, but changing the provider protocol is intentionally outside this UI
fix. The wrapper intentionally does not intercept arbitrary provider methods;
the command that owns the wait also owns when the line closes. Rich's generic
spinner was not used because it would not establish the shared stage contract
or preserve the existing `.`, `..`, `…` visual language.
