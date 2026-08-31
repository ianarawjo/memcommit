# Root module relocation plan

This is the frozen path-only inventory for the 249 Python modules that
were directly under memcommit at baseline commit 885e62c0.

## Summary

| Role | Modules |
| --- | ---: |
| historical-compatibility-facade | 95 |
| operation-implementation | 69 |
| retired-prototype | 18 |
| root-boundary | 1 |
| shared-concept-implementation | 66 |

## Modules

| Baseline module | Role | Action | Canonical target | Importers |
| --- | --- | --- | --- | ---: |
| memcommit | root-boundary | retain | memcommit | 870 |
| memcommit._architecture_catalog | shared-concept-implementation | relocate-without-alias | scripts.callable_catalog.catalog | 0 |
| memcommit.add_application | historical-compatibility-facade | remove | memcommit.application.operations.add.application | 0 |
| memcommit.add_runtime | historical-compatibility-facade | remove | memcommit.application.operations.add.runtime | 0 |
| memcommit.ambiguity_pipeline | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.semantic.classification.ambiguity | 1 |
| memcommit.application_flow | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.flow | 2 |
| memcommit.application_review_policy | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.review_policy | 7 |
| memcommit.applied_checkpoint_review | shared-concept-implementation | relocate-without-alias | memcommit.application.operations.review.applied_checkpoint | 2 |
| memcommit.atomize | historical-compatibility-facade | remove | memcommit.application.operations.atomize.domain | 0 |
| memcommit.atomize_analysis_application | historical-compatibility-facade | remove | memcommit.application.operations.atomize.analysis_application | 0 |
| memcommit.atomize_analysis_runtime | historical-compatibility-facade | remove | memcommit.application.operations.atomize.analysis_runtime | 0 |
| memcommit.atomize_application | historical-compatibility-facade | remove | memcommit.application.operations.atomize.application | 0 |
| memcommit.atomize_grounding | retired-prototype | retire | none (retired) | 0 |
| memcommit.atomize_grounding_application | retired-prototype | retire | none (retired) | 0 |
| memcommit.atomize_grounding_provider | retired-prototype | retire | none (retired) | 0 |
| memcommit.atomize_grounding_runtime | retired-prototype | retire | none (retired) | 0 |
| memcommit.atomize_meld_adapter | retired-prototype | retire | none (retired) | 0 |
| memcommit.atomize_normal_form | historical-compatibility-facade | remove | memcommit.application.operations.atomize.normal_form | 0 |
| memcommit.atomize_resolution_adapter | historical-compatibility-facade | remove | memcommit.application.operations.atomize.resolution_adapter | 0 |
| memcommit.atomize_result_adapter | historical-compatibility-facade | remove | memcommit.application.operations.atomize.result_adapter | 0 |
| memcommit.atomize_runtime | historical-compatibility-facade | remove | memcommit.application.operations.atomize.runtime | 0 |
| memcommit.atomize_workbench | historical-compatibility-facade | remove | memcommit.application.operations.atomize.records | 0 |
| memcommit.atomize_workflow | retired-prototype | retire | none (retired) | 0 |
| memcommit.bootstrap | retired-prototype | retire | none (retired) | 3 |
| memcommit.checkpoint_catalog | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.checkpoint_catalog | 3 |
| memcommit.checkpoint_frames | shared-concept-implementation | relocate-without-alias | memcommit.persistence.store.context_memory.checkpoint_frame_mapping | 1 |
| memcommit.checkpoint_migration | shared-concept-implementation | relocate-without-alias | memcommit.application.operations.rename.history_repair | 0 |
| memcommit.chunking | historical-compatibility-facade | remove | memcommit.application.operations.chunk.domain | 1 |
| memcommit.cli | shared-concept-implementation | relocate-without-alias | memcommit.adapters.console.entrypoint | 14 |
| memcommit.clipboard | shared-concept-implementation | relocate-without-alias | memcommit.adapters.console.clipboard | 11 |
| memcommit.command_attempts | shared-concept-implementation | relocate-without-alias | memcommit.persistence.command_ledger.attempts | 16 |
| memcommit.command_history | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.command_recovery | 11 |
| memcommit.comparison | operation-implementation | relocate-without-alias | memcommit.application.capabilities.memory_issue_analysis.peer_relations.model | 33 |
| memcommit.comparison_evidence | operation-implementation | relocate-without-alias | memcommit.application.capabilities.memory_issue_analysis.peer_relations.evidence | 5 |
| memcommit.comparison_execution | operation-implementation | relocate-without-alias | memcommit.application.capabilities.memory_issue_analysis.peer_relations.execution | 9 |
| memcommit.comparison_present | operation-implementation | relocate-without-alias | memcommit.adapters.console.commands.compare.presentation | 5 |
| memcommit.comparison_provider | operation-implementation | relocate-without-alias | memcommit.application.capabilities.memory_issue_analysis.peer_relations.provider_contract | 11 |
| memcommit.comparison_session_application | operation-implementation | relocate-without-alias | memcommit.application.operations.compare.sessions | 2 |
| memcommit.comparison_store | operation-implementation | relocate-without-alias | memcommit.application.capabilities.memory_issue_analysis.peer_relations.repository | 10 |
| memcommit.comparison_summary | historical-compatibility-facade | remove | memcommit.application.operations.compare.compare_summary | 1 |
| memcommit.comparison_summary_application | historical-compatibility-facade | remove | memcommit.application.operations.compare.application | 0 |
| memcommit.comparison_summary_present | operation-implementation | relocate-without-alias | memcommit.adapters.console.commands.compare.summary_presentation | 1 |
| memcommit.comparison_summary_provider | historical-compatibility-facade | remove | memcommit.application.operations.compare.provider_contract | 0 |
| memcommit.comparison_summary_rules | historical-compatibility-facade | remove | memcommit.application.operations.compare.compare_rules | 0 |
| memcommit.config | shared-concept-implementation | relocate-without-alias | memcommit.configuration.config | 24 |
| memcommit.conformance | operation-implementation | relocate-without-alias | memcommit.application.operations.conformance.model | 6 |
| memcommit.conformance_runtime | operation-implementation | relocate-without-alias | memcommit.application.operations.conformance.runtime | 2 |
| memcommit.console_invocation | retired-prototype | retire | none (retired) | 0 |
| memcommit.context | shared-concept-implementation | relocate-without-alias | memcommit.core.context | 279 |
| memcommit.context_catalog | shared-concept-implementation | relocate-without-alias | memcommit.persistence.store.context_memory.catalog_model | 1 |
| memcommit.context_history | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.history.query.context_history_slicing | 4 |
| memcommit.context_init_application | historical-compatibility-facade | remove | memcommit.application.operations.init.application | 0 |
| memcommit.context_init_runtime | historical-compatibility-facade | remove | memcommit.application.operations.init.runtime | 0 |
| memcommit.context_lifecycle | shared-concept-implementation | relocate-without-alias | memcommit.persistence.store.context_memory.lifecycle_model | 1 |
| memcommit.context_locator | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.context_locator | 44 |
| memcommit.context_naming | shared-concept-implementation | relocate-without-alias | memcommit.core.context_targeting.naming | 26 |
| memcommit.context_rationale | operation-implementation | relocate-without-alias | memcommit.application.operations.rationale.context | 1 |
| memcommit.context_scope | historical-compatibility-facade | remove | memcommit.application.capabilities.context_scope_loading | 0 |
| memcommit.context_snapshot | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.context_snapshot | 12 |
| memcommit.current_context_application | historical-compatibility-facade | remove | memcommit.application.operations.pwd.application | 0 |
| memcommit.current_context_navigation | shared-concept-implementation | relocate-without-alias | memcommit.core.context_navigation | 3 |
| memcommit.current_context_runtime | historical-compatibility-facade | remove | memcommit.application.operations.pwd.runtime | 0 |
| memcommit.dedun_scope | operation-implementation | relocate-without-alias | memcommit.application.operations.dedun.runtime | 1 |
| memcommit.dedup_application | historical-compatibility-facade | remove | memcommit.application.operations.dedup.application | 0 |
| memcommit.dedup_planning | operation-implementation | relocate-without-alias | memcommit.application.operations.dedun.analysis | 2 |
| memcommit.dedup_runtime | historical-compatibility-facade | remove | memcommit.application.operations.dedun.runtime | 0 |
| memcommit.delete_application | historical-compatibility-facade | remove | memcommit.application.operations.delete.application | 0 |
| memcommit.delete_runtime | historical-compatibility-facade | remove | memcommit.application.operations.delete.runtime | 0 |
| memcommit.derived_policy | shared-concept-implementation | relocate-without-alias | memcommit.application.authorization.source_use | 26 |
| memcommit.direct_item_duplicates | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.reviewing.direct_item_duplicates | 8 |
| memcommit.distill | operation-implementation | relocate-without-alias | memcommit.application.operations.distill.model | 8 |
| memcommit.distill_application | historical-compatibility-facade | remove | memcommit.application.operations.distill.application | 0 |
| memcommit.distill_config | operation-implementation | relocate-without-alias | memcommit.application.operations.distill.config | 3 |
| memcommit.distill_elaborate_reference | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.semantic.generative_reduction_reference | 2 |
| memcommit.distill_goal_fit | operation-implementation | relocate-without-alias | memcommit.application.operations.distill.goal_fit | 1 |
| memcommit.distill_runtime | historical-compatibility-facade | remove | memcommit.application.operations.distill.runtime | 0 |
| memcommit.duplicate_pipeline | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.semantic.classification.duplicates | 1 |
| memcommit.edit_application | historical-compatibility-facade | remove | memcommit.application.operations.edit.application | 0 |
| memcommit.edit_runtime | historical-compatibility-facade | remove | memcommit.application.operations.edit.runtime | 0 |
| memcommit.elaborate | operation-implementation | relocate-without-alias | memcommit.application.operations.makemore.model | 11 |
| memcommit.elaborate_add_runtime | historical-compatibility-facade | remove | memcommit.application.operations.makemore.add_runtime | 0 |
| memcommit.elaborate_application | historical-compatibility-facade | remove | memcommit.application.operations.makemore.application | 0 |
| memcommit.elaborate_config | operation-implementation | relocate-without-alias | memcommit.application.operations.makemore.config | 3 |
| memcommit.elaborate_runtime | historical-compatibility-facade | remove | memcommit.application.operations.makemore.runtime | 0 |
| memcommit.elaborate_target_context | operation-implementation | relocate-without-alias | memcommit.application.operations.makemore.target_context | 2 |
| memcommit.embed_application | historical-compatibility-facade | remove | memcommit.application.operations.embed.application | 0 |
| memcommit.embed_runtime | historical-compatibility-facade | remove | memcommit.application.operations.embed.runtime | 0 |
| memcommit.exact_command_review | shared-concept-implementation | relocate-without-alias | memcommit.adapters.console.terminal.components.command_editor.model | 14 |
| memcommit.exact_dedup | historical-compatibility-facade | remove | memcommit.application.operations.dedup.application | 0 |
| memcommit.exact_dedup_application | historical-compatibility-facade | remove | memcommit.application.operations.dedup.application | 0 |
| memcommit.find_answer_dialogue | retired-prototype | retire | none (retired) | 3 |
| memcommit.find_answer_references | operation-implementation | relocate-without-alias | memcommit.application.operations.search.answer_references | 6 |
| memcommit.find_application | historical-compatibility-facade | remove | memcommit.application.operations.search.application | 0 |
| memcommit.find_materialization_application | historical-compatibility-facade | remove | memcommit.application.operations.search.materialization_application | 0 |
| memcommit.find_materialization_runtime | historical-compatibility-facade | remove | memcommit.application.operations.search.materialization_runtime | 0 |
| memcommit.find_runtime | historical-compatibility-facade | remove | memcommit.application.operations.search.runtime | 0 |
| memcommit.find_scope_evidence | retired-prototype | retire | none (retired) | 2 |
| memcommit.find_turn_dialogue | retired-prototype | retire | none (retired) | 1 |
| memcommit.findings | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.memory_issue_analysis.provider_contract | 15 |
| memcommit.fit | historical-compatibility-facade | remove | memcommit.application.operations.fit.ground_report | 1 |
| memcommit.fit_application | historical-compatibility-facade | remove | memcommit.application.operations.fit.application | 0 |
| memcommit.fit_coherence | historical-compatibility-facade | remove | memcommit.application.operations.fit.coherence | 0 |
| memcommit.fit_judgment | historical-compatibility-facade | remove | memcommit.application.operations.fit.judgment | 0 |
| memcommit.fit_runtime | historical-compatibility-facade | remove | memcommit.application.operations.fit.runtime | 0 |
| memcommit.fit_store | historical-compatibility-facade | remove | memcommit.application.operations.fit.store | 0 |
| memcommit.flow_placeholder | retired-prototype | retire | none (retired) | 1 |
| memcommit.forget_application | historical-compatibility-facade | remove | memcommit.application.operations.forget.application | 0 |
| memcommit.forget_provider | operation-implementation | relocate-without-alias | memcommit.application.operations.forget.provider | 2 |
| memcommit.forget_resolution_adapter | historical-compatibility-facade | remove | memcommit.adapters.console.commands.forget.workbench.presentation | 1 |
| memcommit.forget_review | operation-implementation | relocate-without-alias | memcommit.application.operations.forget.review | 4 |
| memcommit.forget_runtime | historical-compatibility-facade | remove | memcommit.application.operations.forget.runtime | 0 |
| memcommit.goal_focus | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.semantic.goal_focus | 18 |
| memcommit.goal_focus_runtime | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.semantic.goal_focus_runtime | 11 |
| memcommit.granted_comparison_store | operation-implementation | relocate-without-alias | memcommit.application.capabilities.memory_issue_analysis.peer_relations.granted_repository | 8 |
| memcommit.granted_provenance | shared-concept-implementation | relocate-without-alias | memcommit.application.operations.trace.granted_view | 2 |
| memcommit.granted_query_application | historical-compatibility-facade | remove | memcommit.application.operations.query.granted_application | 0 |
| memcommit.granted_query_runtime | historical-compatibility-facade | remove | memcommit.application.operations.query.granted_runtime | 0 |
| memcommit.granted_source_update_application | operation-implementation | relocate-without-alias | memcommit.application.operations.update.granted_source | 1 |
| memcommit.granted_update_application | operation-implementation | relocate-without-alias | memcommit.application.operations.update.granted_target | 5 |
| memcommit.ground | retired-prototype | retire | none (retired) | 26 |
| memcommit.ground_context_catalog | operation-implementation | relocate-without-alias | memcommit.application.operations.ground.context_catalog | 1 |
| memcommit.ground_dialogue | operation-implementation | relocate-without-alias | memcommit.application.operations.ground.dialogue | 1 |
| memcommit.ground_distill | operation-implementation | relocate-without-alias | memcommit.application.operations.ground.distill | 2 |
| memcommit.ground_elaborate | operation-implementation | relocate-without-alias | memcommit.application.operations.ground.makemore | 2 |
| memcommit.ground_turn_dialogue | retired-prototype | retire | none (retired) | 2 |
| memcommit.ground_workspace | operation-implementation | relocate-without-alias | memcommit.application.operations.ground.workspace_model | 13 |
| memcommit.ground_workspace_application | operation-implementation | relocate-without-alias | memcommit.application.operations.ground.workspace_application | 4 |
| memcommit.ground_workspace_draft | operation-implementation | relocate-without-alias | memcommit.application.operations.ground.workspace_draft | 3 |
| memcommit.ground_workspace_draft_store | operation-implementation | relocate-without-alias | memcommit.application.operations.ground.workspace_draft_store | 2 |
| memcommit.ground_workspace_fit | operation-implementation | relocate-without-alias | memcommit.application.operations.ground.workspace_fit | 2 |
| memcommit.ground_workspace_history | operation-implementation | relocate-without-alias | memcommit.application.operations.ground.workspace_history | 1 |
| memcommit.ground_workspace_projection | operation-implementation | relocate-without-alias | memcommit.application.operations.ground.workspace_projection | 3 |
| memcommit.ground_workspace_runtime | operation-implementation | relocate-without-alias | memcommit.application.operations.ground.workspace_runtime | 8 |
| memcommit.help_application | historical-compatibility-facade | remove | memcommit.application.operations.help.application | 0 |
| memcommit.help_lookup_application | historical-compatibility-facade | remove | memcommit.application.operations.help.lookup_application | 0 |
| memcommit.history | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.history.reconstruction.checkpoint_state_projection | 12 |
| memcommit.history_display | shared-concept-implementation | relocate-without-alias | memcommit.adapters.console.terminal.components.history.display | 3 |
| memcommit.history_search | operation-implementation | relocate-without-alias | memcommit.application.capabilities.history.query.semantic_history_query | 4 |
| memcommit.impact_controller | historical-compatibility-facade | remove | memcommit.adapters.console.terminal.components.impact | 0 |
| memcommit.interactive_command | retired-prototype | retire | none (retired) | 6 |
| memcommit.interactive_command_review | shared-concept-implementation | relocate-without-alias | memcommit.adapters.console.terminal.components.command_editor | 6 |
| memcommit.literal_find_application | historical-compatibility-facade | remove | memcommit.application.operations.find.application | 0 |
| memcommit.literal_find_runtime | historical-compatibility-facade | remove | memcommit.application.operations.find.runtime | 0 |
| memcommit.meld | operation-implementation | relocate-without-alias | memcommit.application.operations.meld.model | 24 |
| memcommit.meld_application | historical-compatibility-facade | remove | memcommit.application.operations.meld.apply | 0 |
| memcommit.meld_application_flow | historical-compatibility-facade | remove | memcommit.application.operations.meld.application | 0 |
| memcommit.meld_assessment_application | historical-compatibility-facade | remove | memcommit.application.operations.meld.planning | 0 |
| memcommit.meld_choice_branches | operation-implementation | relocate-without-alias | memcommit.application.operations.meld.proposal_choices | 1 |
| memcommit.meld_provider | operation-implementation | relocate-without-alias | memcommit.application.operations.meld.provider | 7 |
| memcommit.meld_resolution_adapter | operation-implementation | relocate-without-alias | memcommit.application.operations.meld.proposal_projection | 3 |
| memcommit.meld_resolution_application | historical-compatibility-facade | remove | memcommit.application.operations.meld.proposal_iteration | 0 |
| memcommit.meld_resolution_cache | operation-implementation | relocate-without-alias | memcommit.application.operations.meld.proposal_cache | 3 |
| memcommit.meld_restart_application | historical-compatibility-facade | remove | memcommit.application.operations.meld.preparation | 0 |
| memcommit.meld_runtime | historical-compatibility-facade | remove | memcommit.application.operations.meld.runtime | 0 |
| memcommit.meld_session_application | historical-compatibility-facade | remove | memcommit.application.operations.meld.proposal_iteration | 0 |
| memcommit.meld_start_application | historical-compatibility-facade | remove | memcommit.application.operations.meld.preparation | 0 |
| memcommit.memory_diff | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.reviewing.memory_diff | 12 |
| memcommit.memory_lineage | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.history.reconstruction.memory_lineage_relations | 4 |
| memcommit.memory_transfer_application | historical-compatibility-facade | remove | memcommit.application.operations.copy_and_move.application | 0 |
| memcommit.memory_transfer_runtime | historical-compatibility-facade | remove | memcommit.application.operations.copy_and_move.runtime | 0 |
| memcommit.merge_application | historical-compatibility-facade | remove | memcommit.application.operations.merge.application | 0 |
| memcommit.merge_planning | operation-implementation | relocate-without-alias | memcommit.application.operations.merge.planning | 1 |
| memcommit.merge_runtime | historical-compatibility-facade | remove | memcommit.application.operations.merge.runtime | 0 |
| memcommit.merge_tree | operation-implementation | relocate-without-alias | memcommit.application.operations.merge.tree | 1 |
| memcommit.merge_tree_persistence | operation-implementation | relocate-without-alias | memcommit.application.operations.merge.tree_persistence | 1 |
| memcommit.name_suggestions | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.name_suggestions | 3 |
| memcommit.operation_gate_pipeline | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.semantic.classification.gates | 1 |
| memcommit.ops | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.ops | 25 |
| memcommit.ordinary_query_answer | operation-implementation | relocate-without-alias | memcommit.application.operations.query.answer | 3 |
| memcommit.profile_config | shared-concept-implementation | relocate-without-alias | memcommit.application.operations.profile.config | 116 |
| memcommit.profiles | shared-concept-implementation | relocate-without-alias | memcommit.application.operations.profile.model | 87 |
| memcommit.provenance | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.history.query.memory_history_slicing | 13 |
| memcommit.provider_types | shared-concept-implementation | relocate-without-alias | memcommit.providers.types | 45 |
| memcommit.quality_audit | operation-implementation | relocate-without-alias | memcommit.application.operations.audit.model | 6 |
| memcommit.quality_audit_store | operation-implementation | relocate-without-alias | memcommit.persistence.operations.audit.record_repository | 4 |
| memcommit.quality_find_report | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.memory_issue_analysis.report | 6 |
| memcommit.quality_find_workbench | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.memory_issue_analysis.workbench | 11 |
| memcommit.quality_finding_handoff | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.memory_issue_analysis.handoff | 21 |
| memcommit.query_application | historical-compatibility-facade | remove | memcommit.application.operations.query.ordinary_application | 0 |
| memcommit.query_provider | shared-concept-implementation | relocate-without-alias | memcommit.providers.subscription | 63 |
| memcommit.query_reference_application | historical-compatibility-facade | remove | memcommit.application.operations.query.reference_application | 0 |
| memcommit.query_reference_runtime | historical-compatibility-facade | remove | memcommit.application.operations.query.reference_runtime | 0 |
| memcommit.query_runtime | historical-compatibility-facade | remove | memcommit.application.operations.query.ordinary_runtime | 0 |
| memcommit.rationale | operation-implementation | relocate-without-alias | memcommit.application.operations.rationale.model | 8 |
| memcommit.rationale_cache | operation-implementation | relocate-without-alias | memcommit.application.operations.rationale.cache | 3 |
| memcommit.rationale_rules | operation-implementation | relocate-without-alias | memcommit.application.operations.rationale.rules | 3 |
| memcommit.rationale_scope | operation-implementation | relocate-without-alias | memcommit.application.operations.rationale.scope | 2 |
| memcommit.rationale_semantic | operation-implementation | relocate-without-alias | memcommit.application.operations.rationale.semantic | 3 |
| memcommit.read_report | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.reviewing.read_report | 7 |
| memcommit.read_report_recents | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.reviewing.read_report_recents | 3 |
| memcommit.redundancy_scope | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.memory_issue_analysis.redundancy_scope | 3 |
| memcommit.reference_application | historical-compatibility-facade | remove | memcommit.application.operations.reference.application | 0 |
| memcommit.reference_provenance | operation-implementation | relocate-without-alias | memcommit.application.operations.reference.provenance | 3 |
| memcommit.reference_runtime | historical-compatibility-facade | remove | memcommit.application.operations.reference.runtime | 0 |
| memcommit.replace_application | historical-compatibility-facade | remove | memcommit.application.operations.replace.application | 0 |
| memcommit.replace_runtime | historical-compatibility-facade | remove | memcommit.application.operations.replace.runtime | 0 |
| memcommit.resolution_workbench | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.resolution.workbench | 25 |
| memcommit.resolve_application | historical-compatibility-facade | remove | memcommit.application.operations.resolve.application | 0 |
| memcommit.resolve_rules | operation-implementation | relocate-without-alias | memcommit.application.operations.resolve.rules | 2 |
| memcommit.resolve_runtime | historical-compatibility-facade | remove | memcommit.application.operations.resolve.runtime | 0 |
| memcommit.resolve_semantic | operation-implementation | relocate-without-alias | memcommit.application.operations.resolve.semantic | 4 |
| memcommit.resolve_targeting | operation-implementation | relocate-without-alias | memcommit.application.operations.resolve.targeting | 1 |
| memcommit.resource_import | operation-implementation | relocate-without-alias | memcommit.application.operations.resource_import.model | 2 |
| memcommit.result_workbench | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.reviewing.result_workbench | 13 |
| memcommit.review | operation-implementation | relocate-without-alias | memcommit.application.operations.review.model | 21 |
| memcommit.review_report | historical-compatibility-facade | remove | memcommit.application.capabilities.reviewing.report | 3 |
| memcommit.review_report_adapters | retired-prototype | retire | none (retired) | 3 |
| memcommit.search | operation-implementation | relocate-without-alias | memcommit.application.operations.search.model | 11 |
| memcommit.search_artifacts | operation-implementation | relocate-without-alias | memcommit.application.operations.search.artifacts | 1 |
| memcommit.selective_curation | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.semantic.selective_curation | 5 |
| memcommit.semantic_add_runtime | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.semantic_result_memorization | 8 |
| memcommit.semantic_disclosure | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.semantic.disclosure | 6 |
| memcommit.semantic_prompt_policy | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.semantic.prompt_policy | 10 |
| memcommit.semantic_provider | shared-concept-implementation | relocate-without-alias | memcommit.providers.semantic | 7 |
| memcommit.semantic_redundancy_evidence | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.semantic.redundancy_evidence | 5 |
| memcommit.session_workbench_navigation | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.reviewing.session_navigation | 11 |
| memcommit.sever | historical-compatibility-facade | remove | memcommit.application.operations.sever.model | 0 |
| memcommit.sever_application | historical-compatibility-facade | remove | memcommit.application.operations.sever.application | 0 |
| memcommit.sever_provider | historical-compatibility-facade | remove | memcommit.application.operations.sever.provider | 0 |
| memcommit.sever_resolution_adapter | historical-compatibility-facade | remove | memcommit.application.operations.sever.resolution_adapter | 0 |
| memcommit.sever_runtime | historical-compatibility-facade | remove | memcommit.application.operations.sever.runtime | 0 |
| memcommit.sever_store | historical-compatibility-facade | remove | memcommit.application.operations.sever.session_store | 0 |
| memcommit.share | operation-implementation | relocate-without-alias | memcommit.application.operations.share.model | 3 |
| memcommit.show_application | historical-compatibility-facade | remove | memcommit.application.operations.show.application | 0 |
| memcommit.show_runtime | historical-compatibility-facade | remove | memcommit.application.operations.show.runtime | 0 |
| memcommit.status_application | historical-compatibility-facade | remove | memcommit.application.operations.status.application | 0 |
| memcommit.status_runtime | historical-compatibility-facade | remove | memcommit.application.operations.status.runtime | 0 |
| memcommit.storage_permissions | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.authority.storage_permissions | 4 |
| memcommit.store | shared-concept-implementation | relocate-without-alias | memcommit.persistence.store | 217 |
| memcommit.study_action_log | shared-concept-implementation | relocate-without-alias | memcommit.persistence.command_ledger.study_actions | 11 |
| memcommit.study_operation_policy | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.authority.study_operation_policy | 2 |
| memcommit.summarize | operation-implementation | relocate-without-alias | memcommit.application.operations.summarize.model | 9 |
| memcommit.summarize_application | historical-compatibility-facade | remove | memcommit.application.operations.summarize.application | 0 |
| memcommit.summarize_runtime | historical-compatibility-facade | remove | memcommit.application.operations.summarize.runtime | 0 |
| memcommit.switch_application | historical-compatibility-facade | remove | memcommit.application.operations.switch.application | 0 |
| memcommit.switch_runtime | historical-compatibility-facade | remove | memcommit.application.operations.switch.runtime | 0 |
| memcommit.temporal_history | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.history.reconstruction.memory_state_delta | 2 |
| memcommit.translate | historical-compatibility-facade | remove | memcommit.application.operations.translate.runtime | 0 |
| memcommit.translation_view | retired-prototype | retire | none (retired) | 0 |
| memcommit.translation_view_store | retired-prototype | retire | none (retired) | 0 |
| memcommit.uid_locator | shared-concept-implementation | relocate-without-alias | memcommit.core.context_targeting.uid_locator | 6 |
| memcommit.understanding | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.semantic.understanding | 10 |
| memcommit.update | operation-implementation | relocate-without-alias | memcommit.application.operations.update.model | 33 |
| memcommit.update_application | historical-compatibility-facade | remove | memcommit.application.operations.update.materialization | 1 |
| memcommit.update_application_flow | operation-implementation | relocate-without-alias | memcommit.application.operations.update.execution | 1 |
| memcommit.update_endpoints | operation-implementation | relocate-without-alias | memcommit.application.operations.update.endpoints | 2 |
| memcommit.update_receipt_store | operation-implementation | relocate-without-alias | memcommit.application.operations.update.receipt_store | 5 |
| memcommit.update_resolution_adapter | operation-implementation | relocate-without-alias | memcommit.application.operations.update.resolution_adapter | 3 |
| memcommit.write_protection | shared-concept-implementation | relocate-without-alias | memcommit.application.capabilities.authority.write_protection | 7 |
