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
