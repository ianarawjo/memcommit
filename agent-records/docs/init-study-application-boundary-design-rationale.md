# Init-study application boundary design rationale

## Selected boundary

`operations/system_study_tools/init_study/model.py` owns the public result type and
`application.py` selects `coffee` or `legacy` and coordinates the workflow.
The Profile-building implementation is grouped under `init_study/profile/`:
`model.py` owns its internal source/package values, `package.py` reads and
validates packaged inputs, `composition.py` turns a scenario into participant
and authority stores, and `publication.py` materializes Grants and atomically
publishes the pair. The console command owns argument validation, receipts,
action-ledger presentation, and the post-command handoff into a disposable
Study shell. The shell is scheduled on root Context close so initialization
and its command attempt are finalized before the child zsh begins.

`operations/profile` remains reusable control-plane infrastructure: Profile
validation, registry locking and replacement, store inspection, Grant
resolution, and legacy split-Study administration. Its `model/study.py` keeps
grouping, migration, rename, archive, and removal, but no longer implements
init-study package parsing, scenario remapping, store composition, or batch
publication. Production callers import the `init_study` operation directly.

The former root `init_study/composition.py` and `publication.py` modules and
former private imports through `profile.model` remain thin compatibility
exports. They return the canonical objects from `init_study/profile/` and
contain no implementation, so existing imports do not force two owners for the
same behavior.

## Invariants

- One initialization publishes exactly one participant Profile, one authority
  Profile, and all scenario Grants in one registry generation.
- The participant becomes active; the authority Profile is never selected.
- A failure before registry publication leaves no partial pair. If replacement
  becomes visible but final durability confirmation fails, both stores remain
  so the registry cannot point at missing data.
- Scenario inputs are staged privately, validated, copied without operational
  history, and removed after publication.
- Neither scenario depends on a registered source Profile or installs a shared
  semantic prewarm.
- Interactive initialization enters a fresh `zsh -d -f -i` process with a
  run-private `ZDOTDIR` and `HISTFILE`. Exiting returns to the unchanged parent
  shell. Non-interactive and already nested Study invocations remain one-shot.

## Boundary retained

Init-study still reuses Profile control-plane storage, registry, Grant-scope,
and legacy Study identity primitives. Those are shared safety and compatibility
contracts rather than scenario construction. This change deliberately moves
definitions without changing function bodies, persistence formats, names, or
transaction order.

The Study shell currently requires zsh and deliberately skips personal startup
files so a user configuration cannot reconnect ordinary history. Supporting
another shell requires its own tested isolation adapter.
