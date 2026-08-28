# Retired zsh prefill integration design rationale

## Status

The public `mem shell-init` route and its hidden Help transport were retired on
2026-08-28. This note preserves the reason the former design existed and the
reason it was superseded; it is not current setup guidance.

The former zsh wrapper solved two parent-shell problems in one generated
function. It used zsh `print -z` to place a Help selection in the parent's edit
buffer, and it used `fc -p` before `init-study` to hide the previous history
list. Both mechanics required parent-shell ownership, but their product
responsibilities were unrelated.

## Replacement boundaries

Interactive `mem help` now keeps the selected operation fixed, opens a shared
exact-command editor inside the Help process, and runs the reviewed argv as a
separate child process after Help closes. It never passes the edited text to a
shell, so redirection, substitution, and shell operators are not interpreted.
The hidden selection-output option and parent-buffer prefill are gone.

Interactive `mem init-study` now schedules a disposable zsh after its own
command attempt is finalized. The child receives a private temporary
`HISTFILE` and `ZDOTDIR`, disables history saving, skips startup files, and
returns to the caller when it exits. Nested Study invocations do not open
another shell.

These responsibilities and their remaining limitations are recorded in
[`help-init-study-shell-responsibility-design-rationale.md`](help-init-study-shell-responsibility-design-rationale.md).

## Why the former wrapper was rejected

Keeping `shell-init` as a public operation made Help behavior depend on
optional shell installation and made Study isolation depend on whether the
same wrapper happened to intercept `init-study`. It also presented one command
as the owner of two capabilities whose lifecycle and safety boundaries differ.
Moving each behavior to its owning operation makes ordinary invocation the
complete path and removes shell-specific setup from Help discovery.

## Preserved limitations

- Help cannot edit the caller's parent-shell buffer; it edits and executes a
  child command inside its own terminal flow.
- Study isolation currently requires zsh to be installed.
- The Study shell protects against accidental history recall, not a hostile
  user with access to the same operating-system account.
- Non-interactive `mem help` remains stable plain text, and non-interactive
  `mem init-study` initializes Profiles without opening a shell.
- A shell startup file that still evaluates `mem shell-init zsh` must remove
  that obsolete line. A hidden no-op compatibility command is intentionally
  not retained because it would keep the retired operation installed forever.
