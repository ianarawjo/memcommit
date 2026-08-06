# zsh command-prefill design rationale

## Motivation

The interactive `mem help` inventory can identify a real command, but an
ordinary child process cannot modify its parent shell's editable input buffer.
Printing a selected command after the browser closes still leaves the
participant to copy or retype it.

The zsh integration provides an explicit shell-owned bridge:

```zsh
eval "$(mem shell-init zsh)"
```

After that opt-in, an exact `mem help` invocation opens the existing picker.
Enter on a command opens its invocation Forms; Enter on a focused Form places
that editable template in zsh's next edit buffer. Both navigation confirmations
are consumed before the picker closes. The user can replace placeholders or add
options and separately decides whether to execute the resulting command.

## Data and control contract

The generated zsh function intercepts only interactive `mem help` with no
additional arguments. Every other invocation delegates to the installed
executable with `command mem "$@"`.

The intercepted path calls a hidden transport boundary:

```text
command mem help --emit-selection
```

- prompt-toolkit reads from stdin and renders the selector to stderr, which
  remains attached to the terminal while zsh captures stdout;
- cancel emits no stdout;
- a successful selection emits exactly one audited editable command template;
- the wrapper rejects output outside the bounded template character set and
  uses zsh's `print -z` builtin to place that text, plus a trailing space, in
  the next edit buffer. That set includes `#` because the query-view Memory
  selector is written `[query_view]#[memory_handle]`; it does not admit
  command substitution, redirection, control operators, or newlines.

No selected command callback runs during this exchange.

## Safety and ownership boundaries

The integration deliberately requires `eval` in the current shell because
only the parent shell can own its edit buffer. `mem shell-init zsh` merely
prints a static function. It does not modify `.zshrc`, install key bindings,
inject terminal input, or change the current shell without explicit
evaluation.

The selection is prefilled, not executed. This is important because commands
have different argument requirements and some can change local state or call
a provider without additional confirmation. The editable line preserves the
normal shell and CLI parsing path and keeps execution as a separate user
action.

The wrapper uses `command mem` so its internal calls bypass the function and
reach the packaged entry point rather than recursing.

## Compatibility and limitations

- The first implementation supports zsh and its `print -z` buffer stack.
- The `mem` entry point must be installed and available on `PATH`.
- The `eval` affects only the current shell unless the user adds it to a shell
  startup file.
- Non-interactive shells delegate to the ordinary CLI, where `mem help`
  retains its stable plain-text inventory.
- Bash Readline and Fish require different parent-shell integrations and are
  intentional future extensions rather than emulations through unsafe input
  injection.
