# Exact-name dialog interface ownership

## Problem

The compact exact-name dialog is operation-neutral terminal interaction, but
its implementation lived under `memcommit.adapters.console.commands`. Its input control and
frame were already interface-owned, so the host dialog's location made the
remaining ownership boundary look command-specific and invited interface code
to depend on a command compatibility module.

## Decision

The implementation lives in
`memcommit.adapters.console.terminal.components.exact_name_dialog`. It imports the exact
name field directly from `memcommit.adapters.console.terminal.components.exact_name`.
The former `memcommit.adapters.console.coordination.exact_name_dialog` facade is removed.

The alias is intentionally stronger than copied re-exports. Legacy-first and
canonical-first imports resolve to one module object, so a legacy-path
monkeypatch changes the same globals used by canonical callers. Existing
command adapters may keep their old import until they can be cleaned up
independently without restoring command ownership of the implementation.

## Preserved contract

This is a location-only migration. It preserves the function signature, strict
view type check, TTY requirement, validation exceptions, caret placement,
Ctrl-J rejection, Escape and Ctrl-C cancellation, EOF handling, five-row
non-full-screen layout, terminal text escaping, style, and returned value.

The canonical `__module__`, source path in tracebacks, and other physical code
location metadata necessarily follow the implementation. No command result,
rendered interaction, persistence rule, or operation semantic changes. Because
the interaction itself is unchanged, this move does not require refreshed TUI
captures or operation-route evidence.
