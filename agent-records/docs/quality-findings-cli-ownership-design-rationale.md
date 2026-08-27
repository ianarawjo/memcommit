# Quality-findings CLI ownership

The Ambiguities, Conflicts, Duplicates, and Exact Duplicates commands shared a
terminal renderer under `memcommit.adapters.console.commands`. That location made reusable CLI
presentation appear to belong to one command-adapter layer even though the
renderer contains no command dispatch or operation policy.

The implementation now lives unchanged in
`memcommit.adapters.interfaces.cli.quality_findings`. Production command adapters import
that owner directly. `memcommit.adapters.console.commands.shared.findings_render` remains a module alias,
not a copied re-export namespace, so either import order produces the same module
object and legacy-path monkeypatches still affect the implementation globals.

This is an ownership-only move. Function bodies, signatures, defaults, output,
escaping, colors, exception text, and ordering remain unchanged. The legacy path
stays importable; no public export list is introduced or narrowed. Source-location
metadata such as function `__module__` and traceback filenames follows the new
implementation owner, which is the intentional and unavoidable boundary of a
physical relocation.
