# Terminal status copy design rationale

## Motivation

Several terminal surfaces described the implementation state instead of the
person's task. Labels such as `layout only; no authority`, `NOT BOUND`,
`NOT SAVED`, and repeated `READ-ONLY` or `UNCHANGED` clauses appeared in setup,
progress, result, and review views. The repetition made ordinary previews look
like errors, and one Search receipt even combined `READ-ONLY ACTION` with
`APPLIED`.

The operation inventory showed the same pattern across deterministic,
semantic, and mixed commands. The fix therefore uses one presentation rule
instead of operation-specific synonyms: a status names the current result or
the next available action.

## Copy contract

- Prefer task language such as `BUILDING PLAN`, `NEEDS REVIEW`,
  `CREATE ON APPLY`, and `SUMMARY COMPLETE` over storage-lifecycle language.
- State a non-mutation boundary once where it changes the person's decision.
  Do not repeat it in the title, status, endpoint row, summary, and footer.
- Reserve `APPLIED` for an action that has crossed the operation's durable
  application boundary. A display-only action may be `SHOW COMPLETE`, but is
  never `APPLIED`.
- Describe a selected existing endpoint by its role. Do not add `NOT BOUND` or
  `UNCHANGED` when selection itself has no binding or mutation step.
- Describe a future result by the action that creates it: `CREATE ON START`,
  `CREATE ON APPLY`, or `READY TO CREATE`.

These rules affect presentation only. Provider calls, authority checks,
receipts, persistence, checkpoints, and Apply validation keep their existing
operation-owned contracts.

## Safety boundaries retained

This is not a blanket ban on negative or permission language.

- Ground must keep a proposed new Context visibly `NOT CREATED` until the
  exact Ground command is approved. The label is an explicit creation safety
  boundary, not a generic draft status.
- `READ ONLY` remains on rows or sessions whose actual access capability is
  read-only, including Grant-derived source state and saved inspection-only
  sessions.
- Cancellation, no-op, and failure receipts may say that nothing changed when
  that fact is the outcome the person needs to verify.
- Exact Apply review and recovery instructions remain visible even when nearby
  lifecycle disclaimers are removed.

## Alternatives considered

Removing every negative label would erase real authority and creation
boundaries. Keeping all labels but changing their color would leave the same
contradictory text channel in plain and piped output. A global renderer that
rewrites strings was also rejected because it could not distinguish a real
permission state from an operation's redundant lifecycle prose.

The selected approach changes the operation-owned typed projections and
renderers, backed by focused assertions for retired phrases. This keeps plain
text complete while allowing each operation to retain its actual safety
semantics.

## Limitation

This change does not rename internal model states such as `APPLIED`,
`process-local`, or frozen snapshots. Those names remain useful implementation
invariants and are changed only when they leak into user-facing copy.
