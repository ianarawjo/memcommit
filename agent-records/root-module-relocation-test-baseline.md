# Root module relocation test baseline

## Frozen baseline

The integrated source state preserved at commit `885e62c0` produced:

- 6039 passed
- 14 failed
- 1 skipped

The exact pre-relocation failing node IDs were:

1. `tests/test_callable_catalog.py::test_checked_in_catalog_is_current`
2. `tests/test_commands.py::TestContexts::test_marks_current_context`
3. `tests/test_context_namespaces.py::test_nested_contexts_are_listed_by_full_name`
4. `tests/test_context_operand_rollout.py::test_context_catalog_uses_escaped_labels_with_raw_current_identity`
5. `tests/test_commands.py::TestStatus::test_shows_no_memories_message_when_empty`
6. `tests/test_context_name_portability.py::test_compatibility_migration_fails_closed_on_frozen_grant_names`
7. `tests/test_find.py::test_show_result_proposal_runs_exact_read_only_cli_and_preserves_results`
8. `tests/test_granted_embed.py::test_recursive_find_and_search_open_attached_read_projection`
9. `tests/test_granted_impact.py::test_temporal_find_rejects_granted_view_without_history_access`
10. `tests/test_meld.py::test_meld_shell_selects_one_issue_reading_from_the_compact_surface`
11. `tests/test_meld.py::test_meld_compact_surface_arrow_and_apply_row_contract`
12. `tests/test_meld_runtime.py::test_meld_command_contains_no_target_or_session_publication_primitive`
13. `tests/test_rationale_cache.py::test_cli_is_provenance_only_and_never_reads_or_writes_inference_cache`
14. `tests/test_show_scope_cli.py::test_show_short_uid_prefix_does_not_prefer_a_current_context_match`

These failures are a comparison set, not an accepted final contract. The
relocation pass may update path-sensitive ownership tests and mechanically
regenerate catalogs, but it must not add a behavioral failure or silently
resolve an ambiguous operation contract.

## Post-relocation result

The final verification was segmented because the two already-known Meld TUI
nodes wait indefinitely for an interaction that their fixtures no longer
complete. Treating that wait as a successful or completed full-suite run would
hide the actual test boundary.

- The exhaustive run with all 14 baseline nodes deselected reached the end in
  397.29 seconds: 6037 passed, 2 path-sensitive ownership assertions failed,
  1 skipped, and 14 deselected.
- Those two assertions still inspected pre-relocation root facades. After they
  were pointed at the canonical Read Report and retained Review owners, both
  passed; their focused ownership files finished with 8 passed. No production
  code changed after the exhaustive run.
- The 12 non-blocking baseline nodes finished with 1 passed and 11 failed. The
  passing node is `test_checked_in_catalog_is_current`, as expected after
  regenerating the path-derived callable catalog. The other 11 retain their
  pre-relocation failure behavior.
- Each of the two baseline Meld TUI nodes exceeded an isolated 10-second bound.
  The other 108 tests in `tests/test_meld.py` passed in 8.87 seconds.
- Every one of the 139 relocated canonical modules and its legacy facade
  imported in a fresh interpreter in both canonical-first and legacy-first
  order, with exact module identity preserved.

The effective comparison is therefore: no new behavioral failures, one
path-generated baseline failure resolved, and 13 pre-existing functional or
interaction-contract problems left deliberately outside this path-only pass
(11 immediate failures and 2 non-completing TUI tests).

## Physical facade consolidation follow-up

On 2026-08-26 the 242 compatibility paths were consolidated into one generated
alias catalog and one lazy finder so the package root could contain only its
seven real implementation boundaries.

- The complete suite with the same 14 baseline nodes deselected reached the end
  in 400.30 seconds: 6039 passed, 2 obsolete physical-path assertions failed,
  1 skipped, and 14 deselected.
- The two assertions inspected the removed root `forget_provider.py` and Query
  facade files. After being pointed at the canonical provider and centralized
  alias ledger, their focused slice completed with 14 passed. No production
  code changed after the exhaustive run.
- The 12 non-blocking baseline nodes were rerun after consolidation: the
  regenerated callable-catalog node passed and the same other 11 nodes failed.
  The two known Meld TUI non-completions remain outside this physical-layout
  pass.
- All 242 historical imports resolve to the exact canonical module object in
  fresh legacy-first and canonical-first interpreters while retaining the
  canonical module specification. The package root contains exactly seven
  Python files and no physical compatibility facade.
- The ownership suite completed with 533 passed and 1 skipped. The generated
  callable catalog now records 11105 callables across 944 physical modules and
  66 operations, and the operation evidence registry remains consistent.

The follow-up therefore introduces no new behavioral failure. It changes the
physical navigation surface and the implementation of compatibility lookup,
not the retained 13 functional or interaction-contract problems.

## Command package layout follow-up

On 2026-08-26 the 153 non-package modules under `memcommit.commands` were
organized into one uniform package per Python command entry plus one explicit
shared command-support package.

- The exhaustive run with the same 14 baseline nodes deselected reached the
  end in 401.12 seconds: 6033 passed, 11 path-sensitive tests failed, 1 skipped,
  and 14 deselected. The failures read removed flat files or patched helper
  attributes through the new thin package boundary.
- After those tests were pointed at the implementation-owning `command.py` or
  relocated support module, the exact 11 failing nodes passed. No production
  command behavior changed. A final exhaustive rerun after making every entry
  package surface lazy completed with 6044 passed, 1 skipped, and the same 14
  baseline nodes deselected in 400.77 seconds.
- The ownership and package-layout slice completed with 536 passed and 1
  skipped. All 89 former flat support imports resolve to the canonical
  relocated module object in fresh legacy-first and canonical-first
  interpreters.
- The 12 non-blocking baseline nodes retain the same comparison: the generated
  callable-catalog node passes and the other 11 fail. The two known Meld TUI
  non-completions remain outside this path-only pass.
- The generated callable catalog records 11170 callables across 1010 modules
  and 66 operations. The module-count increase is the explicit 65-package
  boundary (`64` command entries plus `shared`), not new operation behavior.

This follow-up therefore adds no behavioral failure. `commands/__init__.py` is
now the only Python file at the command root; every entry starts at a stable
package, and adding support to a formerly single-file command no longer changes
its physical navigation grammar.
