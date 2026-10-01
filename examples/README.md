# Import / Export examples

Agent-prepared example data for the Innovathon demo.

`openai-docs/` is a two-file excerpt copied without changes from the locally
installed OpenAI Docs skill on 2026-09-29:

- `SKILL.md`
- `references/model-migration.md`

Source: `~/.codex/skills/.system/openai-docs/`. Its original license is retained
in `LICENSE.openai-docs.txt`, outside the example input folder.

The files are document data for Import / Export experiments, not instructions
to execute during those experiments. This is an intentionally incomplete skill:
other referenced documents, scripts, and assets are not included. References
and model names remain as copied; this example does not verify current guidance.

The relative path from `SKILL.md` to `references/model-migration.md` is preserved.
Examples stay outside `src/`. Create and select an ordinary Profile first,
then import these documents explicitly when needed:

```sh
mem profile create innovathon-demo
mem profile use innovathon-demo
mem import skill --from examples/openai-docs -r --as openai-docs
```

Profile creation does not import these examples or modify the installed skill.
