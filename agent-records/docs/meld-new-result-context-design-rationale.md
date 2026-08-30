# Explicit Meld roles and Result Context

## Problem

The former two-operand form was symmetric but hid its Result in the current
Context:

```bash
mem meld LEFT_PEER RIGHT_PEER
```

That made the same visible `A B` shape look directional while actually meaning
`A + B → current`. A person also had to create and switch to an empty Result
before running it. The error that all three Contexts must be distinct exposed
the hidden operand only after parsing, so it explained an internal invariant
rather than the command the person thought they had entered.

## Command contract

Directional Meld is the primitive positional form:

```bash
mem meld INCOMING                         # INCOMING → current BASELINE
mem meld INCOMING BASELINE                # INCOMING → BASELINE
```

Symmetric Meld is the explicit three-frame application:

```bash
mem meld PEER_A PEER_B RESULT_C           # PEER_A + PEER_B → RESULT_C
mem meld PEER_A PEER_B --to RESULT_C      # equivalent explicit alias
```

`--into BASELINE` and `--from INCOMING` remain directional aliases. The old
hidden-current symmetric meaning of `mem meld A B` is intentionally removed;
that exact form now always means `A → B`. Parsing never inspects whether `B`
is empty to choose a mode.

Existing source operands use the shared existing-Context locator resolver.
`RESULT_C` is an exact ordinary Context name because it may not exist yet; it
is never reinterpreted relative to a later current-Context value.

## Result adoption boundary

An explicit symmetric Result has one of three valid states:

- absent: Meld creates it atomically with the initial saved session;
- present, local, empty, and session-free: Meld adopts it as the Result;
- present with the exact compatible saved Meld session: Meld resumes it.

A populated Result, a granted Result, or a Result with an unrelated or
incompatible session is rejected. Meld never overwrites existing content and
never chooses a hidden Result from the current Context. Creating or adopting a
Result does not switch the current Context.

## Invariants

- Directional INCOMING and BASELINE must resolve to different Contexts.
- Symmetric PEER A, PEER B, and RESULT C must all be distinct.
- Both symmetric peers must exist and retain equal authority.
- The command obtains an exact fresh ordered Compare analysis matching both
  peers and scope flags before publishing a new Result and session.
- A provider or Compare failure before publication leaves a new Result absent.
- The Result remains empty until an explicitly accepted proposal is applied.
- Context creation and initial session publication share one atomic boundary.
- Granted peers retain the normal combination, derivation, export, and result
  retention checks.

## Alternatives considered

Keeping `mem meld A B` symmetric and adding only a better error would still
leave `B` looking like a destination while the real Result remained hidden.
Overloading `A B` by checking whether `B` was empty would make command meaning
depend on mutable storage state. Requiring `--from` and `--to` everywhere would
be explicit but would make the common directional primitive less direct.

The selected arity makes the authority shape visible before execution:
one or two operands are directional; three operands are symmetric.

## Operation independence

Compare ends at its own analysis and report. It does not open Meld, collect a
Result name, or offer a Meld-specific continuation because comparison may be
followed by several different operations or no mutation at all. A person
starts Meld explicitly through its own CLI, TUI, Python, or agent adapter, and
that Meld invocation alone selects or creates `RESULT_C`.

Symmetric Meld may still reuse or refresh an exact ordered Compare basis inside
its operation-owned runtime. That semantic prerequisite is not a UI handoff and
does not give Compare authority over Meld setup, persistence, or execution.
