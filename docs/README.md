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
