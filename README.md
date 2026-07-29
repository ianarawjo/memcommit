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
