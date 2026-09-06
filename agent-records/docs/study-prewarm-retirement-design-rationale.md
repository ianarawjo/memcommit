# Retire Study prewarm while preserving scenarios

Agent-authored implementation rationale, 2026-09-06.

## Motivation and boundary

The user requested keeping task 1, task 2, task 3, and practice while removing
prewarm functionality. Those scenario definitions, bilingual fixture files,
Context/Memory identities, and ordinary `init-study` materialization are not
precomputed semantic results and remain intact. Coffee and explicit legacy
initialization continue to create isolated participant/authority Profiles.

The retired subsystem generated, registered, installed, and consumed semantic
artifacts for fixed Study frames. Keeping that subsystem under `legacy` still
made current operations depend on its registries, shared bundles, and hidden
receipts. Deleting only the package would break runtime imports; leaving inert
lookup hooks would preserve an unsupported alternate execution contract.

## Operation contracts after removal

- Compare: use an exact ordinary saved analysis or run provider analysis.
  Remove Study-equivalent/projection callbacks and prepared installers. Keep
  ordered frames, focused Memory scope, Grant revalidation, and exact refresh CAS.
- Update and Impact Update: remove hidden plan lookup and origin receipts.
  Preserve ordinary Impact-plan reuse by Update, staged-session reuse, current
  target-use validation, approval, and publication/Apply boundaries.
- Atomize: open returns `SAVED` or `PROVIDER`. Remove `use_prepared` from the
  public Python/agent request, `allow_prepared` from the application request,
  prepared-result overrides, hidden installation, and prewarm-only presentation.
  Preserve refresh, reviewed-revision validation, saved scope/staleness checks,
  history rotation, pair rollback, Output planning, and exact Apply recovery.
  Existing callers must omit the removed option; it is not silently accepted.
- Summarize: nonempty authorized frames use the provider; empty frames remain
  provider-free. Preserve complete input scope and revalidation before return.
- Sever: new analysis uses the provider after input authorization; remove the
  prepared-result port, origins, and progress stage. Existing saved reviews and
  their decision, destination, CAS, and Apply lifecycle remain ordinary state.
- Meld: remove remaining prewarm imports and origin presentation. Ordinary
  operation-owned saved sessions remain outside this retirement's deletion scope.
- Import Profile: exclude retired semantic bundles from the clean baseline
  allowlist and digest; preserve Context data and supported content views.
- Init Study: preserve both scenarios and remove the obsolete prewarm-specific
  receipt wording. Operational history still starts empty.

## Compatibility, alternatives, and non-goals

Old prewarm directories, pinned references, and hidden receipts already on disk
are inert. This change does not scan, migrate, or delete user Profile data.
Already materialized ordinary sessions are still subject to their existing
schema, freshness, authority, and CAS rules; their historical prewarm origin
no longer triggers a special lookup or UI label. Old research outputs and
historical design accounts are retained, with retirement notices where needed.

This does not remove ordinary semantic caches, provider budgeting, fixture
scenarios, generic unrelated operation APIs, or saved execution/review history.
A first analysis that previously hit a hidden bundle now incurs provider
latency/cost and can report normal provider/budget failures. No new batching,
background generation, or fallback provider policy is introduced.

## Verification

Regression cases seed deliberately malformed retired artifacts in isolated
stores, then exercise Compare create/open/reuse/refresh, Atomize create/reuse
and stale rejection, Summarize, Sever, and Impact-to-Update cache reuse and
provider failure. The files must remain byte-identical. A clean Profile-copy
case checks that these files neither affect the baseline digest nor enter the
copy, while Context/Memory data and current selection survive unchanged.
Existing Coffee and explicit legacy initialization tests cover the real
scenario inventories. No live provider or real participant Profile is used.

Only prewarm-specific status branches are removed; the remaining interactive
selection, review, approval, and navigation topology is unchanged.

### Verification results

The final focused run passed 198 tests across Atomize application/public/agent,
Compare public lifecycle, Sever application, Summarize application, Update,
Coffee/legacy initialization, retirement regressions, operation ownership,
and clean/resource Profile imports. Ruff undefined/unused-name checks on the
retirement code, `git diff --check`, and the operation evidence verifier passed.
Scenario data and `application/operations/init_study` have no task diff.

A broader run of the affected command families and callable catalog passed
282 tests and retained four failures outside the removed execution branches:

- `test_compare.py::test_relative_peer_locator_errors_before_provider`: expected
  resolved-name diagnostic differs from the current unavailable-name message.
- `test_granted_impact.py::test_new_compare_and_update_setup_include_a_granted_target`:
  the setup catalog now returns more values than the test unpacks.
- `test_granted_impact.py::test_update_between_distinct_grants_writes_only_accepting_target`:
  fixture Profile registry drops required Grant placements before Update runs.
- `test_callable_catalog.py::test_operation_routes_keep_observed_shape_and_curated_conclusion_separate`:
  the Meld expectation differs from the authored classification registry.

The earlier whole-suite snapshot passed 4,849 tests and failed 33 while other
repository changes were in progress; it is not a claim of a clean full suite.
The retirement does not rewrite unrelated route judgments or fixtures to hide
those failures. Generated callable metadata is refreshed from current source.

### Commit isolation check

Before committing, a snapshot based on parent `0041d1d3c` was constructed with
only retirement changes, excluding the concurrent Meld refactor. That snapshot
passed 296 tests across the focused families and Meld application/runtime/API.
The legacy Meld command suite had 44 failures; the identical set of 44 failures
was independently reproduced on the unmodified parent (65 other cases passed,
and the retired prewarm-only case was excluded). No new failure was introduced
in that comparison. Legacy Meld branch-cache reuse remains implemented; only
the fallback to a Study-installed branch and its provenance display are removed.
