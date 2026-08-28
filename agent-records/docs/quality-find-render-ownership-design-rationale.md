# Quality-find terminal-render ownership

Last reviewed: 2026-08-28.

The Ambiguities, Conflicts, Duplicates, and Exact Duplicates commands share a
small line-oriented terminal renderer. It emits Typer output, applies the
shared console palette, and escapes untrusted terminal text, so it is a
console adapter rather than a generic `interfaces.cli` contract. No one
quality-find command owns it because all four commands use the same report
vocabulary.

The canonical implementation lives at
`memcommit.adapters.console.terminal.components.quality_find.rendering`. The `quality_find`
prefix distinguishes this quality-inspection family from ordinary `mem find`,
which retrieves relevant Memories and owns different result presentation.
The `render` suffix states that this module projects already-decided report
data; it does not discover findings, own application policy, or represent an
Apply receipt. The adjacent `quality_find_workbench` remains the interactive
presentation counterpart.

The former `memcommit.adapters.interfaces.cli.quality_findings` implementation
and inverse `memcommit.adapters.console.coordination.findings_render` facade are
removed. Production commands import the canonical owner directly. The
historical flat `memcommit.commands.findings_render` inventory entry maps to
the new owner only in the centralized command-layout record; no physical
forwarding module is retained.

This is an ownership-and-naming-only change. Function bodies, signatures,
defaults, output text, escaping, colors, exception text, and ordering remain
unchanged. Ordinary Find rendering, quality analysis, interactive workbench
behavior, and downstream Resolve or Dedun handoffs are intentional non-goals.
