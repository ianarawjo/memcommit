# task-1 core issues

105 counted commands completed against one cumulative frozen lane. The issue list distinguishes product/interaction findings from the provider-schema infrastructure failure.

## T1-V2-CONTEXTS-GLOBAL-OVERLOAD · World-focused discovery prints every world and Grant

- Severity: `medium`
- Classification: `usability/information-overload`
- Expected: A focused workflow should be able to narrow Context discovery to task-1 or the current subtree while preserving Grant annotations.
- Actual: Every bare Contexts call printed 105 catalog rows (125 raw lines), including unrelated task-2 and task-3 namespaces; no filter was available.
- Workaround: Use literal Find/List with an exact task-1 root after manually locating it in the global catalog.
- Evidence: task-1/core/seq-001, task-1/core/seq-022, task-1/core/seq-043, task-1/core/seq-064, task-1/core/seq-085

## T1-V2-RECURSIVE-LIST-OVERLOAD · Recursive List becomes an unbounded terminal dump

- Severity: `medium`
- Classification: `usability/information-overload`
- Expected: A recursive inspection should remain navigable or provide a bounded/summary handoff while retaining exact data access.
- Actual: The accumulated participant List occupied 904 raw lines and the public wiki List occupied 580 raw lines in plain output.
- Workaround: List one exact child at a time or use literal/semantic retrieval before List.
- Evidence: task-1/core/seq-044, task-1/core/seq-086

## T1-V2-COMPARE-SAME-CONTEXT-MEMORIES · Compare auto-types Memory endpoints but rejects peers in one Context

- Severity: `medium`
- Classification: `functional/operand-contract`
- Expected: Two explicit CONTEXT:UID endpoints should compare the selected Memories even when their owner Context is the same.
- Actual: The command rejected two distinct facility Memory UIDs with 'Compare requires two distinct Contexts.'
- Workaround: Compare Memories owned by distinct Contexts or compare their whole peer Contexts.
- Evidence: task-1/core/seq-016, task-1/core/seq-079

## T1-V2-QUALITY-SCOPE-ASYMMETRY · Quality finders expose incompatible scope grammars

- Severity: `low`
- Classification: `usability/command-consistency`
- Expected: Find Ambiguities and Find Conflicts should share the direct/recursive scope vocabulary already used by Find Duplicates and Find Redundancies, or clearly present an equivalent noninteractive range control.
- Actual: Both commands rejected --direct at parser level and suggested --select; positional exact Context worked on later attempts.
- Workaround: Use a positional exact Context for direct analysis, --all for Profile breadth, or --select only in a TTY.
- Evidence: task-1/core/seq-019, task-1/core/seq-020, task-1/core/seq-040, task-1/core/seq-041

## T1-V2-REFERENCE-GRANTED-CONTEXT-RESOLUTION · Reference cannot snapshot a readable granted Context

- Severity: `high`
- Classification: `functional/grant-resolution`
- Expected: Reference's Source Context route should resolve a readable granted public Context, as its exact granted-Memory route and Embed's whole granted-Context route do.
- Actual: Reference reported task-1/campus-wiki/building-access does not exist, although Contexts/List/Show resolved it and later granted Memory Reference and whole-Context Embed succeeded.
- Workaround: Reference an exact public Memory or Embed the public Context; use Copy when an owned snapshot is required.
- Evidence: task-1/core/seq-054, task-1/core/seq-075, task-1/core/seq-076, task-1/core/seq-097

## T1-V2-CHUNK-FRAGMENTED-ATOMS · Hard-bounded Chunk emits semantically incomplete fragments

- Severity: `high`
- Classification: `semantic-integrity/chunking`
- Expected: Clause chunking should preserve independently intelligible atomic Memories or visibly warn that a hard character cap forced dependent fragments.
- Actual: A valid clause/max-char split produced '...during the' and 'construction period.' as separate Memories; Find Ambiguities immediately flagged both as mutually dependent underspecified fragments.
- Workaround: Use a larger max_chars value and immediately run Find Ambiguities before consuming chunks.
- Evidence: task-1/core/seq-036, task-1/core/seq-040, task-1/core/seq-057, task-1/core/seq-061

## T1-V2-COMPARE-LEDGER-INVALID-REPAIR · Compare ledger waits 109 seconds then loses the analysis

- Severity: `high`
- Classification: `provider-schema-infrastructure/reliability`
- Expected: A ledger comparison should return a valid exhaustive relation ledger or fail promptly without consuming a long provider-repair cycle.
- Actual: After 109.62 seconds, Compare failed because provider repair assigned DISTINCT to invalid PEER sides; no usable ledger was published.
- Workaround: Use snapshot Compare for a summary and separate Find/Fit reports for relation evidence.
- Evidence: task-1/core/seq-100, task-1/core/seq-058, task-1/core/seq-105

## T1-V2-FIT-TEMPORAL-OVERRIDE · Fit treats a time-bounded exception as incompatible with usual hours

- Severity: `medium`
- Classification: `semantic/temporal-reasoning`
- Expected: A June 24–August 23 construction-specific 7 a.m.–11 p.m. schedule can coexist with a store's usual recess 9 a.m.–6 p.m. schedule as an explicit temporary override.
- Actual: Fit returned NO and treated the ordinary 'usual recess hours' statement as an unconditional conflict with the dated construction update.
- Workaround: State override precedence explicitly in the background or preserve the normal and temporary schedules in separate time-scoped Contexts.
- Evidence: task-1/core/seq-105
