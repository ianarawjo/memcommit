# Console invocation routing retirement

## Decision

The console has no user-selectable `AUTO`, `PLAIN`, or `TUI` presentation
mode. Remove `--plain` and `--tui` from operation commands, delete
`memcommit.adapters.console.router`, and delete the composition-root runners
whose only job was to select between line output and an operation screen.
Terminal capability may still control color, wrapping, clipboard support, and
whether an input editor can open; it must not select a different semantic flow
for the same complete argv.

This supersedes this record's earlier, narrower retirement of
`adapters.interfaces.cli.invocation`. That prototype was unused, but the later
`ConsoleRunner` abstraction proved unnecessary for the same reason: commands
had already accumulated operation-specific exceptions around it, so it was
neither a common execution contract nor the owner of one coherent UI policy.

## Command contract

A command now derives its route from input completeness and operation meaning:

- `mem find` and an incomplete `mem replace` open their operation-owned input
  editor only in an interactive terminal. A supplied Find pattern or complete
  Replace pair executes immediately and prints the same bounded result or
  receipt in every terminal.
- Resolve, Summarize, Distill, Makemore, Fit, Log, Trace, and the internal
  exact Dedun replay have one result route. Complete execution commands apply
  or return their operation receipt; read-only commands print their typed
  document. Impact and Review remain the explicit homes for non-applying
  analysis and retained post-application evidence.
- Trace prints its bounded lineage document directly. The former compact
  receipt-to-`--plain` indirection and `--tui` Viewer selection are removed.
- ANSI-free behavior comes from pipes, `NO_COLOR`, or terminal capability. A
  command flag no longer duplicates that environmental presentation concern.

Unknown retired flags fail during argument parsing before Store access,
provider construction, or mutation. They are not retained as hidden no-ops,
because accepting them would preserve the misleading public concept and make
future command forms appear to support a mode switch that no longer exists.

## Why this boundary

The complete argv is the durable, scriptable expression of intent. Letting TTY
state replace its result with a setup screen, pager, or Viewer made the same
invocation require different keys and produce different output depending on
where it ran. Conversely, missing required text genuinely needs an input
surface and cannot execute outside a TTY. Input completeness is therefore the
useful boundary; “plain versus TUI” is not.

Keeping operation-owned editors and reusable Viewer/workbench components is
intentional. Those components remain available to bare input flows, Impact,
Review, and other explicitly named operations. The retirement removes the
global route selector and direct-command presentation switches; it does not
merge operation models or move application policy into terminal code.

## Compatibility and limitations

Historical screenshots and earlier rationale sections retain the exact
commands that produced them and are not rewritten as if the old flags never
existed. Current Help, tests, and boundary matrices identify those routes as
retired. External scripts that passed `--plain` or `--tui` must remove the
flag; their replacement is the command's single current output contract, not a
new synonym.

The first slice leaves now-unreachable operation-specific Viewer/workbench
implementations in place when they are independently tested or share useful
projection code. Removing or repurposing those components is a separate
ownership decision. This change also does not resolve the still-distinct
Resolve ambiguity/conflict application responsibilities; that analysis follows
after console routing is no longer obscuring the call path.
