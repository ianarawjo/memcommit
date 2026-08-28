# Help and init-study shell responsibility design rationale

## Problem

The retired `mem shell-init` route printed one zsh wrapper that combined two
unrelated policies. It transported a selected Help command into the parent
shell's editable input buffer, and it pushed a new parent-shell history stack
before `init-study`. The implementation was shared only because both behaviors
needed parent-shell control; Help command handoff and Study isolation do not
share a lifecycle or semantic owner.

## Selected boundaries

Help owns command discovery, form selection, and the editable handoff. After a
form is selected, a second prompt-toolkit screen composes the shared editable
exact-command control. The selected `mem OPERATION` prefix is fixed while its
arguments remain editable. Enter returns an argv and closes Help before a child
`mem` process starts. The argv is passed directly to `subprocess.run` without a
shell, so quoting is parsed once and shell metacharacters are never reinterpreted.

`init-study` owns Study environment entry. After Profile publication and
receipt output, it schedules a disposable interactive zsh on the root Click
Context's close callback. This ordering lets the outer command-attempt and
Study-action ledgers finish before commands inside the Study shell begin. The
child skips user and global startup files and receives run-private history and
configuration paths. Exiting the child returns to the unchanged parent shell.

## Invariants

- Help never changes the selected operation prefix in its editor; only that
  operation's operands and options are editable.
- Help closes before the selected command executes, and execution never uses
  `shell=True` or evaluates a rendered command string.
- Cancelling either Help screen launches nothing.
- `init-study` opens a Study shell only for a real interactive terminal and
  never nests another shell when `MEMCOMMIT_STUDY_SHELL=1` is present.
- The Study Profile pair remains published even if zsh cannot start. Shell
  startup errors are reported after the completed initialization attempt.
- Plain and non-interactive Help remain read-only inventory output;
  non-interactive `init-study` remains a one-shot initializer.

## Alternatives

Keeping `shell-init` as a public setup route retained the behavior but preserved
the accidental coupling and required every ordinary `mem` invocation to pass
through a shell function. Moving that wrapper wholesale under `init-study`
would incorrectly make Help editing a Study concern. Directly invoking an
edited command from the still-open Help application would complicate terminal
ownership and nested TUI cleanup. Closing Help and launching an argv child keeps
the command boundary explicit while preserving the edit-before-Enter contract.

## Limitations

The Study shell currently requires zsh, matching the only shell supported by
the retired integration. It deliberately skips personal rc files to keep
history isolation reliable, so personal aliases and prompt configuration do
not appear inside the Study shell. Supporting another shell requires a separate
tested isolation adapter rather than treating shell syntax as interchangeable.
