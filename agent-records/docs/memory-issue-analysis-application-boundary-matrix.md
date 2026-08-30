# Memory Issue Analysis application boundary matrix

## Decision

Memory Issue Analysis is a direct application capability shared by four named
read-only operations, Audit, and validation consumers. It owns judgment over an
already frozen Memory frame; it does not decide which command was invoked:

| Shared owner | Contract |
| --- | --- |
| `capabilities.memory_issue_analysis.model` | typed Duplicate, Ambiguity, and Conflict evidence, reports, provider protocol, and ruleset identities |
| `capabilities.memory_issue_analysis.provider_contract` | shared prompt, schema, decoder, budget, calibration, and provider-call mechanics |
| `capabilities.memory_issue_analysis.reading_analysis` | Context-aware ambiguity analysis; every candidate is interpreted against the complete supplied frame |
| `capabilities.memory_issue_analysis.relation_analysis` | exact/semantic redundancy and conflict analysis over the requested frame; callers select the relation judgment they need |
| `capabilities.memory_issue_analysis.source` | exact or Profile-wide readable Source freeze, including `READ`, `DERIVE`, and applicable `COMBINE` checks before provider disclosure |
| `capabilities.memory_issue_analysis.report` | immutable issue-document projections used by read-only result browsers |
| `capabilities.memory_issue_analysis.redundancy_scope` | independent per-Context redundancy analysis across a frozen lexical scope |
| `capabilities.memory_issue_analysis.workbench` | process-local responses and Resolution-session projections over frozen issues |
| `capabilities.memory_issue_analysis.handoff` | typed, source-bound transfer from read-only issues into a named repair operation |

The former `reviewing.memory_issue` hierarchy classified the capability by a
presentation phase that not every consumer shares. It is removed without a
compatibility alias. Find, Audit, Atomize normal-form validation, and semantic
classification import the narrow analysis owner directly; they do not invoke a
peer `find-*` application merely to reuse a judgment primitive. Meld and Update
remain intentionally unchanged in this step and still require a separate
boundary review before adopting the capability.

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
- Ambiguity is Context-aware: the provider receives every direct Memory in the
  frozen frame, and ordinary antecedents or shared scope supplied by that frame
  may make a candidate clean.
- Issues and reports remain immutable read-only evidence. Resolution and
  materialization revalidate their own Source and authority boundaries.
- `capabilities.memory_issue_analysis` is the canonical physical owner. The
  former `semantic` and `reviewing` category packages are not dependencies of
  this capability and are not alternate import surfaces.
- Meld and Update module renames in the same change are mechanical only: their
  provider, session, Apply, and Compare-basis behavior does not change.
