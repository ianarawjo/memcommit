# Meld Usage

This is the canonical user-facing command guide for the meld behavior that is
currently implemented. Update this file, the relevant CLI help, and the
associated tests together whenever hands-on testing changes the workflow.

## Canonical terms

| User-facing term | Technical contract | Command | Status |
|---|---|---|---|
| **Atomic meld** *(informal shorthand)* | An issue-scoped directional meld embedded in atomize grounding | `mem atomize --evaluate ISSUE` | Implemented |
| **Context meld** | A symmetric meld between two equal-authority Contexts | `mem meld LEFT_PEER RIGHT_PEER` | Implemented |
| **Directional Context meld** | An incoming Context melded into an authoritative baseline Context | No public command | Future |

“Atomic” identifies the issue where review begins. It does **not** promise
that only one Memory can change. A clarification may require several
traceable edits or additions when other local Memories depend on the same
interpretation.

There is no `mem meld --atomic` command and no public command that accepts two
arbitrary strings or two individual Memory UIDs. The implemented atomic entry
point remains under `mem atomize` because atomize owns the saved analysis,
issue identity, and source evidence.

## Atomic meld (informal shorthand): resolve one atomize issue

### 1. Create or resume the atomize analysis

```bash
mem atomize --context CONTEXT
```

This displays the saved workbench and its visible issue numbers. Repeating the
command resumes a compatible saved analysis without another provider call.

### 2. Start from one issue

In an interactive terminal, omit `--comment` and enter the clarification when
prompted:

```bash
mem atomize --context CONTEXT --evaluate ISSUE
```

For an explicit one-shot submission:

```bash
mem atomize --context CONTEXT \
  --evaluate ISSUE \
  --comment "The Main Building entrance accepts only a physical NFC card."
```

`ISSUE` may be a visible issue number or a unique issue/source UID prefix.
Starting the dialogue may call the semantic provider once. It does not change
Memories.

### 3. Inspect or continue the grounded interpretation

Resume the open dialogue without a provider call:

```bash
mem atomize --context CONTEXT
```

Answer a follow-up, qualify the interpretation, or repair an earlier turn:

```bash
mem atomize --context CONTEXT \
  --reply "Do not recommend the app. The staff entrance uses the same physical-card-only method." \
  --revision correct
```

The supported revision labels are:

```text
confirm
extend
correct
retract
```

Each reply is a new grounded turn and may call the provider once. The result
must show what Mem understood, which issue is resolved or remains open, and
the exact proposed `EDIT` or `ADD` consequences.

### 4. Apply or retain review evidence

Only a `READY_TO_APPLY` dialogue can be applied:

```bash
mem atomize --context CONTEXT --accept-grounding
```

Acceptance is provider-free. It applies the exact ready proposal to that
Context and creates one checkpoint. The saved atomize analysis is then stale
and must be refreshed explicitly before another review cycle.

To close the dialogue without changing Memories:

```bash
mem atomize --context CONTEXT --keep-review-only
```

One invocation may contain only one grounding action. Do not combine
`--evaluate`, `--reply`, `--accept-grounding`, or `--keep-review-only` with
`--save` or `--save-as`.

## Context meld: combine two equal-authority Contexts

### 1. Create and enter an empty result Context

```bash
mem init RESULT_CONTEXT
```

The current Context is the target. It must be empty. Neither peer source is
mutated.

### 2. Start or resume the symmetric meld

```bash
mem meld LEFT_PEER RIGHT_PEER
```

In a terminal this opens the interactive workbench. Repeating the same command
resumes the saved session. Outside a terminal it prints the saved snapshot.

The primary controls are:

```text
Up / Down               move between issues
Enter                   expand the selected issue
1–5                     select a proposed reading
Tab                     comment on the selected issue
G                       comment on the whole set
Enter in MESSAGE        send
Ctrl-J / Alt-Enter      insert a newline
P                       preserve all remaining supported distinctions
D                       keep the result as review-only
A                       accept a ready proposal
Q                       close
```

The same operations are available explicitly:

```bash
mem meld LEFT_PEER RIGHT_PEER \
  --issue 1 \
  --choice 2 \
  --comment "Keep both rules, but state their separate scopes."

mem meld LEFT_PEER RIGHT_PEER \
  --comment "Preserve every source-supported exception."

mem meld LEFT_PEER RIGHT_PEER --expand 1
mem meld LEFT_PEER RIGHT_PEER --preserve-all
mem meld LEFT_PEER RIGHT_PEER --defer-all
mem meld LEFT_PEER RIGHT_PEER --accept
```

`--expand`, resume, defer, and acceptance are provider-free. Issue comments,
whole-set comments, and preserve-all create semantic turns. `--accept` applies
the ready result to the current empty target without mutating either peer.

Use `--restart` only when intentionally replacing the saved review session
after rechecking that the target is still empty:

```bash
mem meld LEFT_PEER RIGHT_PEER --restart
```

## Deliberate boundary

The two implemented entry points share a meld reasoning contract but not one
CLI shape:

```text
one saved atomize issue + clarification
→ mem atomize --evaluate
→ issue-scoped directional meld ("atomic meld" shorthand)

two equal-authority Contexts + empty result Context
→ mem meld
→ Context-wide symmetric meld
```

A future directional Context command must make incoming and baseline authority
explicit. Until that contract is implemented, this guide must not advertise
`mem meld INCOMING --into BASELINE` as an available command.
