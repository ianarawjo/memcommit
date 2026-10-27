# Project documents and native transfer boundaries

- `common/` owns shared document values, syntax conversion, output planning, and
  native JSON/setup primitives. It has no command dispatch or provider policy.
- `mem_sync/` owns `.md` discovery, Context/file correspondence, comparison,
  conflict selection, publication, checkpoints, and whole-action restoration.
- `mem_import/` and `mem_export/` are reserved for future native `.mem` movement.
  They contain design descriptions only and have no executable CLI/API route.

One Markdown document corresponds to one Context. File-derived names remove only
the final `.md`; default output adds `.md` to the complete Context name. Thus
`notes.md.md` corresponds to `notes.md`. `SKILL.md` is ordinary Markdown;
its header is one textual Memory, without a metadata child Context or Skill-field
validation. Directory Contexts supply lexical navigation and can gain their own
corresponding Markdown document without replacing their identity or children. Every document/directory path is relative to the Profile project root.

Sharing a package does not share execution ownership: Sync uses common primitives
directly and never invokes an Import or Export operation. A future native transfer
must define its own identity/history contract instead of reusing Sync execution.
