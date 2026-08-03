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

## Meld quick start

The implemented meld workflows have different entry points:

- one-issue directional grounding, informally called atomic meld:
  `mem atomize --context CONTEXT --evaluate ISSUE`;
- directional Context intake into an authoritative baseline:
  `mem meld --into BASELINE` when the current Context is incoming, or
  `mem meld INCOMING --into BASELINE` when it is explicit;
- symmetric combination of two equal-authority Contexts:
  create an empty result Context, then run `mem meld LEFT_PEER RIGHT_PEER`.

See [`docs/mem-meld-usage.md`](docs/mem-meld-usage.md) for the canonical
commands, interactive controls, acceptance boundaries, and the deliberate
distinction between directional `--into` and the reserved future symmetric
`--to` destination.
