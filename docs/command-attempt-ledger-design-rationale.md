# Command-attempt ledger design rationale

## Problem

Context checkpoints explain successful state changes, and saved semantic
sessions explain provider work that reached a valid review artifact. Neither
records an entered command that fails before those boundaries. A timed-out
`mem sever`, invalid provider response, refused mutation, or interrupted TUI
could therefore leave only transient terminal text, making its selected frame,
effective timeout, and elapsed time impossible to reconstruct.

Every top-level `mem` invocation now publishes one Profile-scoped command
attempt under:

```text
ledger/command-attempts/ATTEMPT_UID.json
```

This is an execution audit ledger, not a replacement for Context checkpoints,
semantic sessions, provider-evaluation ledgers, or Undo/Redo receipts.
Current Profiles created by `mem init-study` additionally use the narrower,
content-free detailed telemetry described in
`docs/study-action-ledger-design-rationale.md`; ordinary Profiles do not.

## Lifecycle contract

The root Click group freezes the active Profile and writes a `RUNNING` record
before it dispatches the selected command. Normal return finalizes the same
record as `COMPLETED`; a nonzero Click/Typer exit or exception becomes
`FAILED`; and keyboard interruption becomes `INTERRUPTED`. Both publication
and finalization are fsynced atomic file writes. If the whole process or
machine stops before finalization, the retained `RUNNING` record is deliberate
evidence of an incomplete attempt rather than a fabricated failure outcome.

The record includes a random UID, top-level operation name, UTC start/end,
monotonic elapsed duration, terminal-presence booleans, terminal status, and a
bounded failure class/exit code. An exit-zero help or version path is a
completed invocation. Nested command families such as `provider status` are
recorded by their top-level operation (`provider`); raw token recovery is not
used to guess whether later operands are subcommands.

The attempt is written to the Profile active when the root command starts.
Consequently, a successful `mem profile` switch remains auditable in the old
Profile rather than moving its own in-flight record to the newly selected
Profile. This preserves a single storage and identity boundary for one
attempt.

## Privacy boundary

The generic root record never stores raw argv, stdout, stderr, cwd,
environment variables, prompts, Memory text, query text, Ground comments,
composer content, provider responses, or query-only routing/content. This is
why a command such as `mem add "private text"` can be audited as an `add`
attempt without copying the private text into a second durable surface.

Operation enrichment is allowlisted and structurally validated rather than
accepting arbitrary dictionaries. The first enrichment is Sever, which may
record only Source/Criteria/Result public names, scopes, ordinary Memory
counts, excluded query-only Context count, provider identity, effective
timeout, and a coarse failure kind. It never records frame contents, aliases,
candidate decisions, rationales, or query-only names. The frozen frame details
are published before provider inference so connection or completion failure
still leaves useful evidence.

The command-attempt ledger is system audit metadata. It remains writable when
ordinary Profile content is write-protected; otherwise read-only and refused
commands could not meet the all-attempt logging contract. Its directory and
files use private permissions, reject symbolic links and unexpected entries,
and fail closed when a record is malformed.

## Inspection

`mem log` retains its Context-checkpoint meaning. `mem log --operations`
selects the Profile command-attempt ledger and prints recent attempts with
status and elapsed time. The currently executing log invocation is omitted
from its own output but becomes visible on the next inspection. Sever rows add
their bounded frame and provider diagnostics.

`mem log --actions` is a separate current-Study-only view. It uses the generic
attempt UID to correlate command lifecycle with terminal, provider, and
review-action phases without changing the all-Profile attempt schema.

## Alternatives and limitations

- Adding failed attempts to Context checkpoints was rejected because many
  attempts have no target Context and checkpoints imply recoverable state.
- Logging only semantic commands was rejected because parsing, authority,
  storage, and ordinary command failures are also operational evidence.
- Raw argv logging was rejected because many commands accept private Memory or
  dialogue text positionally.
- One append-only start event plus a separate terminal event was considered.
  Replacing one UID-addressed RUNNING record keeps inspection simple while
  still preserving process-loss evidence; it is not a cryptographically
  immutable audit system.
- A command that returns normally after the person cancels an interactive
  picker is currently `COMPLETED`: the command lifecycle completed and made no
  claim that a semantic artifact was created. A later operation-specific
  effect field can distinguish cancellation without changing generic status.
- The test-only `MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG` seam prevents embedded
  `CliRunner` suites from writing host audit records. It is not a documented
  user configuration or a command-level bypass.
