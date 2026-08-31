# Command package layout plan

This is the exact path-only classification of the formerly flat
`memcommit.commands` modules. Their canonical implementations now live under
`memcommit.adapters.console.commands` for command-owned code and
`memcommit.adapters.console.coordination` for nonvisual multi-command mechanics, and
`memcommit.adapters.console.terminal.components` for terminal-bound components;
route closure remains solely in the operation evidence ledger.

- Baseline modules: 153
- Active canonical mappings: 139
- Retired baseline modules: 14
- Command entry packages: 61
- Shared command mechanisms: 40

| Legacy module | Canonical module | Role | Owner |
| --- | --- | --- | --- |
| `memcommit.commands.add` | `memcommit.adapters.console.commands.add.command` | command-entry | `add` |
| `memcommit.commands.atomize` | `memcommit.adapters.console.commands.semantic_updates.derive.atomize.command` | command-entry | `semantic_updates.derive.atomize` |
| `memcommit.commands.atomize_sessions` | `memcommit.adapters.console.commands.semantic_updates.derive.atomize.records` | command-owned-support | `semantic_updates.derive.atomize` |
| `memcommit.commands.audit` | `memcommit.adapters.console.commands.quality_resolution.diagnose.audit.command` | command-entry | `quality_resolution.diagnose.audit` |
| `memcommit.commands.audit_sessions` | `memcommit.adapters.console.commands.quality_resolution.diagnose.audit.session_catalog` | command-owned-support | `quality_resolution.diagnose.audit` |
| `memcommit.commands.background_turn` | `memcommit.adapters.console.terminal.components.background_turn` | shared-terminal-component | `terminal` |
| `memcommit.commands.batch_input` | `memcommit.adapters.console.coordination.batch_input_source` | shared-command-mechanism | `coordination` |
| `memcommit.commands.branch` | `memcommit.adapters.console.commands.branch.command` | command-entry | `branch` |
| `memcommit.commands.branch_dialog` | `memcommit.adapters.console.commands.branch.endpoint_setup` | command-owned-support | `branch` |
| `memcommit.commands.check_conformance` | `memcommit.adapters.console.commands.quality_resolution.validate.check_conformance.command` | command-entry | `quality_resolution.validate.check_conformance` |
| `memcommit.commands.checkpoint` | `memcommit.adapters.console.commands.history_recovery.recovery.checkpoint.command` | command-entry | `history_recovery.recovery.checkpoint` |
| `memcommit.commands.checkpoint_diff` | `memcommit.adapters.console.terminal.components.history.checkpoint_diff` | shared-terminal-component | `terminal` |
| `memcommit.commands.chunk` | `memcommit.adapters.console.commands.direct_changes.chunk.command` | command-entry | `direct_changes.chunk` |
| `memcommit.commands.clear` | `memcommit.adapters.console.commands.direct_changes.clear.command` | command-entry | `direct_changes.clear` |
| `memcommit.commands.command_group` | `memcommit.adapters.console.coordination.command_group` | shared-command-mechanism | `coordination` |
| `memcommit.commands.command_progress` | `memcommit.adapters.console.terminal.components.progress` | shared-terminal-component | `terminal` |
| `memcommit.commands.command_wait` | `memcommit.adapters.console.terminal.components.command_wait` | shared-terminal-component | `terminal` |
| `memcommit.commands.compare` | `memcommit.adapters.console.commands.search_explain.synthesize.compare.command` | command-entry | `search_explain.synthesize.compare` |
| `memcommit.commands.compare_sessions` | `memcommit.adapters.console.commands.search_explain.synthesize.compare.sessions` | command-owned-support | `search_explain.synthesize.compare` |
| `memcommit.commands.compare_setup` | `memcommit.adapters.console.commands.search_explain.synthesize.compare.endpoint_setup` | command-owned-support | `search_explain.synthesize.compare` |
| `memcommit.commands.compare_targeting` | `memcommit.adapters.console.commands.search_explain.synthesize.compare.targeting` | command-owned-support | `search_explain.synthesize.compare` |
| `memcommit.commands.comparison_execution` | `memcommit.adapters.console.commands.search_explain.synthesize.compare.execution` | command-owned-support | `search_explain.synthesize.compare` |
| `memcommit.commands.config` | `memcommit.adapters.console.commands.config.command` | command-entry | `config` |
| `memcommit.commands.conflict_resolve_handoff` | `memcommit.adapters.console.commands.quality_resolution.repair.resolve.finding_handoff` | command-owned-support | `quality_resolution.repair.resolve` |
| `memcommit.commands.context_operand` | `memcommit.adapters.console.coordination.context_operand` | shared-command-mechanism | `coordination` |
| `memcommit.commands.context_picker` | `memcommit.adapters.console.terminal.components.context_picker` | shared-terminal-component | `terminal` |
| `memcommit.commands.context_reach_dialog` | `memcommit.adapters.console.terminal.components.context_reach_dialog` | shared-terminal-component | `terminal` |
| `memcommit.commands.context_trace_projection` | `memcommit.adapters.console.commands.history_recovery.inspection.trace.context_projection` | command-owned-support | `history_recovery.inspection.trace` |
| `memcommit.commands.contexts` | `memcommit.adapters.console.commands.contexts.command` | command-entry | `contexts` |
| `memcommit.commands.dedun` | `memcommit.adapters.console.commands.quality_resolution.repair.dedun.command` | command-entry | `quality_resolution.repair.dedun` |
| `memcommit.commands.dedup` | `memcommit.adapters.console.commands.quality_resolution.repair.dedup.command` | command-entry | `quality_resolution.repair.dedup` |
| `memcommit.commands.delete` | `memcommit.adapters.console.commands.direct_changes.delete.command` | command-entry | `direct_changes.delete` |
| `memcommit.commands.dev` | `memcommit.adapters.console.commands.dev.command` | command-entry | `dev` |
| `memcommit.commands.diff` | `memcommit.adapters.console.commands.history_recovery.inspection.diff.command` | command-entry | `history_recovery.inspection.diff` |
| `memcommit.commands.diff_browser` | `memcommit.adapters.console.terminal.components.history.browser` | shared-terminal-component | `terminal` |
| `memcommit.commands.direct_item_placement` | `memcommit.adapters.console.terminal.components.direct_item_placement` | shared-terminal-component | `terminal` |
| `memcommit.commands.distill` | `memcommit.adapters.console.commands.semantic_updates.derive.distill.command` | command-entry | `semantic_updates.derive.distill` |
| `memcommit.commands.edit` | `memcommit.adapters.console.commands.direct_changes.edit.command` | command-entry | `direct_changes.edit` |
| `memcommit.commands.elaborate` | `memcommit.adapters.console.commands.semantic_updates.derive.makemore.command` | command-entry | `semantic_updates.derive.makemore` |
| `memcommit.commands.exact_command_review` | `memcommit.adapters.console.terminal.components.command_editor` | shared-terminal-component | `terminal` |
| `memcommit.commands.exact_command_review_shell` | `memcommit.adapters.console.terminal.components.command_editor.approval` | shared-terminal-component | `terminal` |
| `memcommit.commands.exact_name_dialog` | `memcommit.adapters.console.terminal.components.exact_name_dialog` | shared-terminal-component | `terminal` |
| `memcommit.commands.find` | `memcommit.adapters.console.commands.search_explain.retrieve_answer.search.command` | command-entry | `search_explain.retrieve_answer.search` |
| `memcommit.commands.find_ambiguities` | `memcommit.adapters.console.commands.quality_resolution.diagnose.find_ambiguities.command` | command-entry | `quality_resolution.diagnose.find_ambiguities` |
| `memcommit.commands.find_conflicts` | `memcommit.adapters.console.commands.quality_resolution.diagnose.find_conflicts.command` | command-entry | `quality_resolution.diagnose.find_conflicts` |
| `memcommit.commands.find_duplicates` | `memcommit.adapters.console.commands.quality_resolution.diagnose.find_redundancies.command` | command-entry | `quality_resolution.diagnose.find_redundancies` |
| `memcommit.commands.find_exact_duplicates` | `memcommit.adapters.console.commands.quality_resolution.diagnose.find_duplicates.command` | command-entry | `quality_resolution.diagnose.find_duplicates` |
| `memcommit.commands.find_query_provider_policy` | `memcommit.providers.operation_connections` | infrastructure-support | `providers` |
| `memcommit.commands.find_search_workbench` | `memcommit.adapters.console.commands.search_explain.retrieve_answer.search.search_workbench` | command-owned-support | `search_explain.retrieve_answer.search` |
| `memcommit.commands.findings_render` | `memcommit.adapters.console.terminal.components.quality_find.rendering` | shared-terminal-component | `terminal` |
| `memcommit.commands.fit` | `memcommit.adapters.console.commands.quality_resolution.validate.fit.command` | command-entry | `quality_resolution.validate.fit` |
| `memcommit.commands.flat_selection_dialog` | `memcommit.adapters.console.terminal.components.flat_selection_dialog` | shared-terminal-component | `terminal` |
| `memcommit.commands.forget` | `memcommit.adapters.console.commands.semantic_updates.curate_integrate.forget.command` | command-entry | `semantic_updates.curate_integrate.forget` |
| `memcommit.commands.forget_setup_workbench` | `memcommit.adapters.console.commands.semantic_updates.curate_integrate.forget.setup` | command-owned-support | `semantic_updates.curate_integrate.forget` |
| `memcommit.commands.ground` | `memcommit.adapters.console.commands.ground.command` | command-entry | `ground` |
| `memcommit.commands.ground_shell` | `memcommit.adapters.console.commands.ground.shell` | command-owned-support | `ground` |
| `memcommit.commands.ground_workspace_picker` | `memcommit.adapters.console.commands.ground.workspace.catalog` | command-owned-support | `ground.workspace` |
| `memcommit.commands.help_inventory` | `memcommit.adapters.console.commands.help.command` | command-entry | `help` |
| `memcommit.commands.history_location_picker` | `memcommit.adapters.console.terminal.components.checkpoint_location` | shared-terminal-component | `terminal` |
| `memcommit.commands.history_picker` | `memcommit.adapters.console.terminal.components.history.picker` | shared-terminal-component | `terminal` |
| `memcommit.commands.history_present` | `memcommit.adapters.console.terminal.components.history.presentation` | shared-terminal-component | `terminal` |
| `memcommit.commands.history_target` | `memcommit.adapters.console.coordination.history_target` | shared-command-mechanism | `coordination` |
| `memcommit.commands.horizontal_choice` | `memcommit.adapters.console.terminal.components.horizontal_choice` | shared-terminal-component | `terminal` |
| `memcommit.commands.impact` | `memcommit.adapters.console.commands.operation_lifecycle.impact.command` | command-entry | `operation_lifecycle.impact` |
| `memcommit.commands.impact_catalog` | `memcommit.adapters.console.commands.operation_lifecycle.impact.catalog` | command-owned-support | `operation_lifecycle.impact` |
| `memcommit.commands.impact_process_local` | `memcommit.adapters.console.commands.operation_lifecycle.impact.process_local` | command-owned-support | `operation_lifecycle.impact` |
| `memcommit.commands.impact_registry` | `memcommit.adapters.console.commands.operation_lifecycle.impact.registry` | command-owned-support | `operation_lifecycle.impact` |
| `memcommit.commands.impact_sessions` | `memcommit.adapters.console.commands.operation_lifecycle.impact.sessions` | command-owned-support | `operation_lifecycle.impact` |
| `memcommit.commands.import_profile` | `memcommit.adapters.console.commands.import_profile.command` | command-entry | `import_profile` |
| `memcommit.commands.import_workbench` | `memcommit.adapters.console.commands.import_profile.workbench` | command-owned-support | `import_profile` |
| `memcommit.commands.init` | `memcommit.adapters.console.commands.init.command` | command-entry | `init` |
| `memcommit.commands.init_study` | `memcommit.adapters.console.commands.init_study.command` | command-entry | `init_study` |
| `memcommit.commands.list_memories` | `memcommit.adapters.console.commands.list.command` | command-entry | `list` |
| `memcommit.commands.literal_find` | `memcommit.adapters.console.commands.search_explain.retrieve_answer.find.command` | command-entry | `search_explain.retrieve_answer.find` |
| `memcommit.commands.log` | `memcommit.adapters.console.commands.history_recovery.inspection.log.command` | command-entry | `history_recovery.inspection.log` |
| `memcommit.commands.meld` | `memcommit.adapters.console.commands.semantic_updates.curate_integrate.meld.command` | command-entry | `semantic_updates.curate_integrate.meld` |
| `memcommit.commands.meld_sessions` | `memcommit.adapters.console.commands.semantic_updates.curate_integrate.meld.sessions` | command-owned-support | `semantic_updates.curate_integrate.meld` |
| `memcommit.commands.meld_setup` | `memcommit.adapters.console.commands.semantic_updates.curate_integrate.meld.endpoint_setup` | command-owned-support | `semantic_updates.curate_integrate.meld` |
| `memcommit.commands.meld_shell` | `memcommit.adapters.console.commands.semantic_updates.curate_integrate.meld.command` | command-owned-support | `semantic_updates.curate_integrate.meld` |
| `memcommit.commands.memory_history` | `memcommit.adapters.console.coordination.memory_history` | shared-command-mechanism | `coordination` |
| `memcommit.commands.memory_picker` | `memcommit.adapters.console.terminal.components.memory_report_picker` | shared-terminal-component | `terminal` |
| `memcommit.commands.memory_report_recents` | `memcommit.adapters.console.coordination.memory_report_recents` | shared-command-mechanism | `coordination` |
| `memcommit.commands.merge` | `memcommit.adapters.console.commands.direct_changes.merge.command` | command-entry | `direct_changes.merge` |
| `memcommit.commands.operation_launcher_location` | `memcommit.adapters.console.terminal.components.operation_launcher.location` | shared-terminal-component | `terminal` |
| `memcommit.commands.ordinary_query_provider_policy` | `memcommit.adapters.console.commands.search_explain.retrieve_answer.query.provider_policy` | command-owned-support | `search_explain.retrieve_answer.query` |
| `memcommit.commands.paste_input` | `memcommit.adapters.console.terminal.components.paste_input` | shared-terminal-component | `terminal` |
| `memcommit.commands.profile` | `memcommit.adapters.console.commands.profile.command` | command-entry | `profile` |
| `memcommit.commands.profile_group` | `memcommit.adapters.console.commands.profile.group` | command-owned-support | `profile` |
| `memcommit.commands.profile_picker` | `memcommit.adapters.console.commands.profile.picker` | command-owned-support | `profile` |
| `memcommit.commands.provider` | `memcommit.adapters.console.commands.provider.command` | command-entry | `provider` |
| `memcommit.commands.pwd` | `memcommit.adapters.console.commands.pwd.command` | command-entry | `pwd` |
| `memcommit.commands.quality_find_workbench` | `memcommit.adapters.console.terminal.components.quality_find.workbench` | shared-terminal-component | `terminal` |
| `memcommit.commands.query` | `memcommit.adapters.console.commands.search_explain.retrieve_answer.query.command` | command-entry | `search_explain.retrieve_answer.query` |
| `memcommit.commands.query_workbench` | `memcommit.adapters.console.commands.search_explain.retrieve_answer.query.workbench` | command-owned-support | `search_explain.retrieve_answer.query` |
| `memcommit.commands.rationale` | `memcommit.adapters.console.commands.history_recovery.inspection.rationale.command` | command-entry | `history_recovery.inspection.rationale` |
| `memcommit.commands.readable_context_catalog` | `memcommit.application.capabilities.authority.readable_contexts` | shared-application-capability | `authority` |
| `memcommit.commands.redo` | `memcommit.adapters.console.commands.history_recovery.recovery.redo.command` | command-entry | `history_recovery.recovery.redo` |
| `memcommit.commands.reference` | `memcommit.adapters.console.commands.reference.command` | command-entry | `reference` |
| `memcommit.commands.remove` | `memcommit.adapters.console.commands.direct_changes.remove.command` | command-entry | `direct_changes.remove` |
| `memcommit.commands.rename` | `memcommit.adapters.console.commands.rename.command` | command-entry | `rename` |
| `memcommit.commands.replace` | `memcommit.adapters.console.commands.direct_changes.replace.command` | command-entry | `direct_changes.replace` |
| `memcommit.commands.resolution_workbench_shell` | `memcommit.adapters.console.terminal.components.resolution.session_shell` | shared-terminal-component | `terminal` |
| `memcommit.commands.resolve` | `memcommit.adapters.console.commands.quality_resolution.repair.resolve.command` | command-entry | `quality_resolution.repair.resolve` |
| `memcommit.commands.restoration_present` | `memcommit.adapters.console.terminal.components.restoration_receipt` | shared-terminal-component | `terminal` |
| `memcommit.commands.revert` | `memcommit.adapters.console.commands.history_recovery.recovery.revert.command` | command-entry | `history_recovery.recovery.revert` |
| `memcommit.commands.review` | `memcommit.adapters.console.commands.operation_lifecycle.review.command` | command-entry | `operation_lifecycle.review` |
| `memcommit.commands.review_report` | `memcommit.adapters.console.commands.operation_lifecycle.review.report` | command-owned-support | `operation_lifecycle.review` |
| `memcommit.commands.review_resolution_shell` | `memcommit.adapters.console.commands.operation_lifecycle.review.resolution_shell` | command-owned-support | `operation_lifecycle.review` |
| `memcommit.commands.review_sessions` | `memcommit.adapters.console.commands.operation_lifecycle.review.sessions` | command-owned-support | `operation_lifecycle.review` |
| `memcommit.commands.root_group` | `memcommit.adapters.console.coordination.root_group` | shared-command-mechanism | `coordination` |
| `memcommit.commands.save_location_control` | `memcommit.adapters.console.terminal.components.save_location` | shared-terminal-component | `terminal` |
| `memcommit.commands.save_location_review` | `memcommit.adapters.console.terminal.components.save_location_review` | shared-terminal-component | `terminal` |
| `memcommit.commands.search_result_present` | `memcommit.adapters.console.commands.search_explain.retrieve_answer.search.result_present` | command-owned-support | `search_explain.retrieve_answer.search` |
| `memcommit.commands.semantic_clipboard` | `memcommit.adapters.console.terminal.components.plain_text_clipboard` | shared-terminal-component | `terminal` |
| `memcommit.commands.semantic_detail_renderer` | `memcommit.adapters.console.terminal.components.semantic_viewer.detail` | shared-terminal-component | `terminal` |
| `memcommit.commands.semantic_eval` | `memcommit.adapters.console.commands.eval.command` | command-entry | `eval` |
| `memcommit.commands.session_help` | `memcommit.adapters.console.terminal.components.session_help` | shared-terminal-component | `terminal` |
| `memcommit.commands.session_picker` | `memcommit.adapters.console.terminal.components.operation_launcher.session` | shared-terminal-component | `terminal` |
| `memcommit.commands.sever` | `memcommit.adapters.console.commands.semantic_updates.curate_integrate.sever.command` | command-entry | `semantic_updates.curate_integrate.sever` |
| `memcommit.commands.sever_sessions` | `memcommit.adapters.console.commands.semantic_updates.curate_integrate.sever.sessions` | command-owned-support | `semantic_updates.curate_integrate.sever` |
| `memcommit.commands.sever_setup_shell` | `memcommit.adapters.console.commands.semantic_updates.curate_integrate.sever.endpoint_setup` | command-owned-support | `semantic_updates.curate_integrate.sever` |
| `memcommit.commands.share` | `memcommit.adapters.console.commands.share.command` | command-entry | `share` |
| `memcommit.commands.share_flow` | `memcommit.adapters.console.commands.share.flow` | command-owned-support | `share` |
| `memcommit.commands.share_viewer` | `memcommit.adapters.console.commands.share.viewer` | command-owned-support | `share` |
| `memcommit.commands.show` | `memcommit.adapters.console.commands.show.command` | command-entry | `show` |
| `memcommit.commands.status` | `memcommit.adapters.console.commands.status.command` | command-entry | `status` |
| `memcommit.commands.study_name_dialog` | `memcommit.adapters.console.commands.init_study.name_dialog` | command-owned-support | `init_study` |
| `memcommit.commands.summarize` | `memcommit.adapters.console.commands.search_explain.synthesize.summarize.command` | command-entry | `search_explain.synthesize.summarize` |
| `memcommit.commands.switch` | `memcommit.adapters.console.commands.switch.command` | command-entry | `switch` |
| `memcommit.commands.trace` | `memcommit.adapters.console.commands.history_recovery.inspection.trace.command` | command-entry | `history_recovery.inspection.trace` |
| `memcommit.commands.trace_projection` | `memcommit.adapters.console.commands.history_recovery.inspection.trace.projection` | command-owned-support | `history_recovery.inspection.trace` |
| `memcommit.commands.translate` | `memcommit.adapters.console.commands.translation.translate.command` | command-entry | `translation.translate` |
| `memcommit.commands.tui_primitives` | `memcommit.adapters.console.terminal.components.primitives` | shared-terminal-component | `terminal` |
| `memcommit.commands.tui_table` | `memcommit.adapters.console.terminal.components.table` | shared-terminal-component | `terminal` |
| `memcommit.commands.undo` | `memcommit.adapters.console.commands.history_recovery.recovery.undo.command` | command-entry | `history_recovery.recovery.undo` |
| `memcommit.commands.update` | `memcommit.adapters.console.commands.semantic_updates.foundation.update.command` | command-entry | `semantic_updates.foundation.update` |
| `memcommit.commands.update_checkpoint_history` | `memcommit.adapters.console.terminal.components.history.update_checkpoint` | shared-terminal-component | `terminal` |
| `memcommit.commands.update_render` | `memcommit.adapters.console.commands.semantic_updates.foundation.update.render` | command-owned-support | `semantic_updates.foundation.update` |
| `memcommit.commands.update_setup` | `memcommit.adapters.console.commands.semantic_updates.foundation.update.endpoint_setup` | command-owned-support | `semantic_updates.foundation.update` |
