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

## Multilingual Memory and explanation-language research TODO

- [`multilingual-memory-and-explanation-language-design-rationale.md`](multilingual-memory-and-explanation-language-design-rationale.md)
  records why Memory authoring language, semantic analysis language,
  explanation language, interface language, and translation target are
  distinct roles. The current shared result-workbench demo deliberately
  retains English explanatory output while preserving source evidence
  verbatim; global and per-command language selection remains deferred
  research rather than partial localization.

## Clipboard result contract

- [`mem-ls-design-rationale.md`](mem-ls-design-rationale.md) defines
  `ls/list --copy` as synchronized clean-or-annotated text and typed-result
  output,
  `ls/list --paste` as frozen read-only replay, clipboard-overwrite
  invalidation, and the query-only non-disclosure boundary.
- [`mem-add-paste-design-rationale.md`](mem-add-paste-design-rationale.md)
  preserves the distinct interactive bracketed-paste intake contract for
  `mem add --paste`.

## Directional update contract notes

- [`task-1-naming-contract.md`](task-1-naming-contract.md) fixes the distinct
  names and authority roles of the query-only organizational origin, writable
  participant fork, and verified local source.
- [`mem-impact-update-design-rationale.md`](mem-impact-update-design-rationale.md)
  defines impact preview, validated local application, per-owner checkpoints,
  applied-result receipts, exception rollback, deterministic diff, and the
  still-separate future publication boundary.

## Context namespace migration

- [`context-locator-design-rationale.md`](context-locator-design-rationale.md)
  defines canonical names, explicit relative existing-Context locators, the
  one-current-snapshot rule, and the rollout boundary between lookup operands
  and newly declared names.
- [`mem-rename-design-rationale.md`](mem-rename-design-rationale.md) defines
  UID-preserving slash-subtree migration; typed reference, current-state,
  checkpoint, Ground, and translation continuity; the query-only non-access
  boundary; reviewed graph freshness; exception rollback; and the remaining
  crash-journal limitation.

## Translation contract

- [`mem-translate-design-rationale.md`](mem-translate-design-rationale.md)
  defines direct-only candidate scope, provider/curated same-UID catalogs,
  exact semantic targets, edit/import/review, explicit materialization,
  concurrency validation, checkpoint lineage, and the query-only privacy
  boundary.
- [`study-fixture-bundle-design-rationale.md`](study-fixture-bundle-design-rationale.md)
  defines English-canonical Task 1--3 stores, same-UID Korean views, concealed
  bilingual query sources, deterministic runtime identities, manifests, and
  the task-by-task `.mem` swap boundary.
- [`study-fixture-spreadsheet-design-rationale.md`](study-fixture-spreadsheet-design-rationale.md)
  defines the paired 20-tab review workbook, native review checkboxes,
  diff-only color cues, formula/read-back verification, and the boundary
  between spreadsheet annotations and runtime Memory authority.

## Atomize contract notes

- [`semantic-result-workbench-design-rationale.md`](semantic-result-workbench-design-rationale.md)
  generalizes the result-explanation hierarchy shared by bounded semantic
  operations: compact counts, what was understood, what happened, what remains
  unresolved, and traceable representative or boundary cases. It also records
  why that shared presentation must not flatten operation-specific semantics
  or mutation authority.
- [`semantic-resolution-workbench-design-rationale.md`](semantic-resolution-workbench-design-rationale.md)
  defines the shared dynamic list/detail/comment frontend used by Meld and
  Atomize and the read-only planned-change projection used by Update. It keeps
  provider, persistence, readiness, and application semantics in
  operation-owned controllers, leaves Ground separate, and reserves only the
  adapter boundary for future Reconcile.
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
  human communication. Shared turn-lineage may be reused, but named Ground's
  Goal–Rules–Memories frame remains separate from Resolution Workbench.
- [`mem-atomize-grounding-screen-captures.md`](mem-atomize-grounding-screen-captures.md)
  indexes exact tested CLI captures for the workbench, awaiting, resumed,
  corrected ready, and applied states.

## Meld contract note

- [`mem-meld-usage.md`](mem-meld-usage.md) is the canonical user-facing
  command guide. It standardizes “atomic meld” as informal shorthand for the
  implemented issue-scoped directional flow under
  `mem atomize --evaluate`; documents Context-wide directional
  `mem meld [INCOMING] --into BASELINE` and its current-baseline convenience
  `mem meld --from INCOMING`; distinguishes both from symmetric
  `mem meld LEFT_PEER RIGHT_PEER`; and reserves `--to` for a future explicit
  symmetric result destination.
- [`mem-meld-design-rationale.md`](mem-meld-design-rationale.md) distills the
  directional and symmetric authority modes; explains issue/all/remaining
  turn scope; documents both implemented Context workbenches and the atomize
  flow's lossless directional/issue projection, where a unary source candidate
  becomes an ephemeral one-Memory `INCOMING` Context frame against its bound
  `BASELINE`; and records shared turn-lineage, relation, provenance, approval,
  and mutation contracts.

## Compare contract note

- [`mem-compare-design-rationale.md`](mem-compare-design-rationale.md) defines
  targetless ordered peer comparison, durable source-bound analysis,
  exhaustive N:M relations, automatic reanalysis after source changes, and
  the boundary between a static Compare view and later grounding/Meld turns.
