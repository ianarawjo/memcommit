# Documentation language and evidence convention

Memcommit's implementation notes, design rationales, command contracts, and
decision histories are written in English so they can be reviewed and reused
consistently.

Non-English text is retained only when it is evidence rather than explanatory
prose:

- verbatim user or study-task source material;
- bilingual source records whose filename explicitly says `original-and-*`;
- linguistic examples whose exact wording is part of a semantic boundary or
  regression case.

These quotations are not treated as an exception to the English documentation
contract: the surrounding explanation, labels, and conclusions remain in
English. Task-specific material is intentionally not translated or normalized
until the task fixtures and study wording are finalized, because an early
rewrite could destroy the exact ambiguity, scope, or malformed wording that a
semantic operation is meant to preserve and analyze.

When a design decision excludes a behavior, defers it, or accepts a prototype
limitation, the relevant focused `*-design-rationale.md` document must state
the reason and the remaining boundary. A conversation-only explanation is not
considered sufficient design history.

## Translation contract

- [`mem-translate-design-rationale.md`](mem-translate-design-rationale.md)
  defines direct-only candidate scope, derived-Context replacement by default,
  explicit in-place compatibility, strict provider output, concurrency
  validation, checkpoint lineage, and the query-only privacy boundary.

## Atomize contract notes

- [`mem-atomize-design-rationale.md`](mem-atomize-design-rationale.md) defines
  atomicity, source grounding, preview/application boundaries, and lineage.
- [`mem-atomize-workbench-design-rationale.md`](mem-atomize-workbench-design-rationale.md)
  defines the aggregate analysis, typed issue workbench, stable resume, and
  explicit reanalysis contract.
- [`memory-review-shell-design-rationale.md`](memory-review-shell-design-rationale.md)
  records the interaction language shared with ambiguity review while keeping
  each operation's persistence, source arity, and mutation boundaries distinct.
- [`mem-review-conversational-grounding-design-rationale.md`](mem-review-conversational-grounding-design-rationale.md)
  records the atomize grounding-session contract for multi-turn
  comment–implication–confirmation loops modeled on grounding in ordinary
  human communication, plus the explicit next TODO to generalize that turn
  model through `mem ground`.
- [`mem-atomize-grounding-screen-captures.md`](mem-atomize-grounding-screen-captures.md)
  indexes exact tested CLI captures for the workbench, awaiting, resumed,
  corrected ready, and applied states.
