# memcommit

A git-like local memory store CLI.

## Interactive command picker in zsh

After installing the `mem` entry point, enable the zsh integration in the
current shell:

```zsh
eval "$(mem shell-init zsh)"
```

Run `mem help`, choose a command with the arrow keys, and press Enter. The
selected `mem <command> ` text is placed in the next zsh input line so it can
be completed or edited before execution.

Add the same `eval` line to `.zshrc` to enable it in future shells. The command
only prints shell code; it does not edit shell startup files itself.

## Whole-store profiles

`mem switch` changes Context inside one MemoryStore. Use `mem profile` when a
complete local store should change instead:

```zsh
mem profile import-study --from outputs/study-fixtures
mem profile list
mem profile task-1
mem switch
mem profile authoring
```

`mem profile use NAME` remains the equivalent explicit form for scripts.

The existing `~/.mem` is the fixed `authoring` profile. Imported profiles are
editable local copies; selecting another profile does not modify or move the
authoring store or the generated package source. Query-only sources travel
with a profile but remain absent from `mem switch`.

## Write protection

Protect the current Context, a recursive Context snapshot, one directly owned
Memory, or the active Profile from later writes:

```zsh
mem lock
mem unlock
mem lock --recursive
mem lock context CONTEXT [--recursive]
mem unlock context CONTEXT [--recursive]
mem lock memory MEMORY_UID [--context CONTEXT]
mem unlock memory MEMORY_UID [--context CONTEXT]
mem lock profile
mem unlock profile
```

Bare `lock` and `unlock` target the current Context. `--recursive` atomically
applies the Context policy to the root and its existing lexical descendants;
future descendants do not inherit it. A Profile lock blocks durable writes
inside that Profile while allowing reads and Context/Profile switching.
Unlocking a Profile preserves narrower Context and Memory locks.

## Meld quick start

The implemented meld workflows have different entry points:

- one-issue directional grounding, informally called atomic meld:
  `mem atomize --context CONTEXT --evaluate ISSUE`;
- directional Context intake into an authoritative baseline:
  `mem meld --into BASELINE` when the current Context is incoming, or
  `mem meld INCOMING --into BASELINE` when both roles are explicit. When the
  current Context is the baseline, `mem meld --from INCOMING` is equivalent
  convenience grammar;
- symmetric combination of two equal-authority Contexts:
  create an empty result Context, then run `mem meld LEFT_PEER RIGHT_PEER`.

See [`docs/mem-meld-usage.md`](docs/mem-meld-usage.md) for the canonical
commands, interactive controls, acceptance boundaries, and the deliberate
distinction between directional `--into` and the reserved future symmetric
`--to` destination.
