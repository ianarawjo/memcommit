# Memory Issue finding application boundary matrix

## Decision

Memory Issue finding has one shared capability family and four named operation
boundaries. The capability family does not decide which command was invoked:

| Shared owner | Contract |
| --- | --- |
| `reviewing.memory_issue.finding.model` | typed Duplicate, Ambiguity, and Conflict findings, reports, provider protocol, and ruleset identities |
| `reviewing.memory_issue.finding.detection` | provider-free and one-shot provider detection over an already assembled direct-Memory `Context`; no Store lookup, persistence, handoff, or rendering |
| `reviewing.memory_issue.finding.source` | exact or Profile-wide readable Source freeze, including `READ`, `DERIVE`, and applicable `COMBINE` checks before provider disclosure |
| `reviewing.memory_issue.finding.report` | immutable finding-document projections used by read-only result browsers |
| `reviewing.memory_issue.finding.redundancy_scope` | independent per-Context redundancy analysis across a frozen lexical scope |
| `reviewing.memory_issue.resolution.workbench` | process-local responses and Resolution-session projections over frozen findings |
| `reviewing.memory_issue.resolution.handoff` | typed, source-bound transfer from read-only findings into a named repair operation |

The former `findings.py` mixed all three contracts and is removed without a
compatibility alias. Audit, Atomize normal-form validation, and semantic
classification may consume the shared model or detector directly because they
are separate operations; they do not invoke a peer `find-*` application merely
to reuse a judgment primitive.

## Named operation routes

| Operation | Current routes | Application owner | Result/effect |
| --- | --- | --- | --- |
| Find Duplicates | CLI and public Python | `operations.find_duplicates.application.find_duplicates` | resolves readable authority and returns one provider-free direct or lexical exact-DUP scope; no mutation |
| Find Redundancies | CLI, public Python, agent, and Dedun's shared analysis phase | `operations.find_redundancies.application` | prepares an exact/lexical Source and executes combined or independent complete-DUN analysis; Find remains read-only and Dedun retains its separate Apply boundary |
| Find Ambiguities | direct, `--all`, `--select`, public Python, and agent | `operations.find_ambiguities.application` | prepares an authorized frozen Source or accepts the setup-approved Source, then returns a typed report and process-local review projection |
| Find Conflicts | direct, `--all`, `--select`, `--handoff-json`, public Python, and agent | `operations.find_conflicts.application` | returns the same typed Source/report/session boundary; Resolve conversion remains a subsequent operation-owned handoff |

Console modules now own only operand grammar, progress, rendering, and
interactive transitions. The Python adapter may assemble a deliberately
multi-Context public Source, but its semantic execution enters the same
operation `analyze_*` callable. The agent adapter delegates to that public
route. `find-duplicates` never constructs a provider; its earlier test-time
provider hook was stale and has been removed from the route contract.

## Invariants

- Context locators resolve against one command-start current-Context snapshot.
- Granted provider-backed Sources require downstream-use authority before the
  provider factory is called; provider-free exact DUP requires readable access
  only.
- A recursive redundancy scope judges each lexical Context independently and
  publishes no partial report if a later frame fails.
- Findings and reports remain immutable read-only evidence. Resolution and
  materialization revalidate their own Source and authority boundaries.
- `reviewing.memory_issue.finding` owns observation and report construction;
  `reviewing.memory_issue.resolution` owns response state and repair handoff.
  The broader operation-neutral `reviewing` capabilities remain outside this
  package and are intentionally unchanged.
