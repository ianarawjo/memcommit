# `mem help` design rationale

## Intent

The default Typer help output proves that a command is registered, but it does
not distinguish a complete local command contract from a bounded research
slice, an older semantic path, or an alias. That distinction matters while
building the study prototype and when preparing its printed cheat sheet.

`mem help` therefore renders one concise inventory line per visible registered
command:

```text
name - implementation level - short description
```

It reports capabilities; it does not recommend a command sequence or perform
work for the participant.

## Levels

- `implemented`: the behavior advertised by that command's current short
  description is available.
- `partial`: only a deliberately bounded subset of the broader operation is
  available. For example, `merge` is a structural UID union, `diff` only
  renders the active stage, `review` currently has only an ambiguity adapter,
  and `update` stages a plan without applying it to the target.
- `legacy`: an older configured-LLM path remains callable but is outside the
  current staged research workflow.
- `alias`: an alternate spelling delegates to another command.

`implemented` is not a production-readiness claim. The repository as a whole
is a research prototype, and individual commands may still have documented
permission, provider, concurrency, or remote-persistence boundaries.

## Consistency boundary

Descriptions are read from the same Click/Typer command registrations used by
`mem --help`; the inventory does not maintain a second description catalog.
Implementation levels are explicit because they are design judgments rather
than properties that can be inferred safely from registration.

The renderer fails closed if a visible command has no level or if a level
remains for a command that is no longer registered. This makes adding,
renaming, or removing a command require an intentional maturity decision
instead of silently presenting it as implemented.

Only callable visible commands are listed. Proposed but unregistered
operations are omitted rather than shown as commands a participant could try.
Their design state remains in the focused operation rationale documents and
the external function inventory.

## Relationship to `mem --help`

`mem --help` remains Typer's syntax-oriented reference, including global
options. `mem help` is the compact implementation inventory. Per-command
syntax continues to use:

```text
mem <command> --help
```
