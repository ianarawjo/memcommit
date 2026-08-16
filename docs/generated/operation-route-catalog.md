# Generated operation route catalog

This file is generated from source. `Observed shape` reports only which
layers and evidence files are statically present; it is not a safety or
architectural-closure conclusion. `Curated state` comes from the reviewed
`docs/operation-route-classification.json`; `UNREVIEWED` is not a
`LEGACY` conclusion.

| Operation | CLI entry | Application/runtime | TUI | Public Python | Agent | Boundary matrix | Observed shape | Curated state |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `add` | `memcommit.commands.add:cmd` | `memcommit.add_application`<br>`memcommit.add_runtime` | `memcommit.interfaces.tui.operations.add`<br>`memcommit.interfaces.tui.operations.add.model`<br>`memcommit.interfaces.tui.operations.add.screen` | `add_memories` | `memcommit.interfaces.agent.add` | `docs/add-callable-boundary-matrix.md` | `MULTI_ADAPTER` | `CLOSED` |
| `atomize` | `memcommit.commands.atomize:cmd` | `memcommit.atomize_analysis_application`<br>`memcommit.atomize_analysis_runtime`<br>`memcommit.atomize_application`<br>`memcommit.atomize_grounding_application`<br>`memcommit.atomize_grounding_runtime`<br>`memcommit.atomize_runtime` | `memcommit.interfaces.tui.operations.atomize`<br>`memcommit.interfaces.tui.operations.atomize.adapter`<br>`memcommit.interfaces.tui.operations.atomize.screen` | `apply_atomize_as_is`<br>`apply_atomize_grounding`<br>`apply_saved_atomize_as_is`<br>`incorporate_and_apply_atomize`<br>`keep_atomize_grounding`<br>`open_atomize_analysis`<br>`open_atomize_grounding`<br>`plan_atomize_output`<br>`reanalyze_atomize_responses`<br>`reply_atomize_grounding`<br>`save_saved_atomize_as`<br>`start_atomize_grounding`<br>`update_atomize_response` | `memcommit.interfaces.agent.atomize`<br>`memcommit.interfaces.agent.atomize_grounding` | `docs/atomize-application-boundary-matrix.md` | `MULTI_ADAPTER` | `CLOSED` |
| `audit` | `memcommit.commands.audit:cmd` | — | `memcommit.interfaces.tui.operations.audit`<br>`memcommit.interfaces.tui.operations.audit.setup` | — | — | — | `PARTIAL_SURFACE` | `UNREVIEWED` |
| `branch` | `memcommit.commands.branch:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `check-conformance` | `memcommit.commands.check_conformance:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `checkout` | `memcommit.cli:_checkout` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `checkpoint` | `memcommit.commands.checkpoint:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `chunk` | `memcommit.commands.chunk:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `clear` | `memcommit.commands.clear:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `compare` | `memcommit.commands.compare:cmd` | — | `memcommit.interfaces.tui.operations.compare`<br>`memcommit.interfaces.tui.operations.compare.model`<br>`memcommit.interfaces.tui.operations.compare.setup` | `compare_contexts`<br>`open_comparison`<br>`refresh_comparison` | `memcommit.interfaces.agent.compare` | `docs/compare-application-boundary-matrix.md` | `PARTIAL_SURFACE` | `CLOSED` |
| `config` | `memcommit.commands.config:app` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `contexts` | `memcommit.commands.contexts:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `delete` | `memcommit.commands.delete:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `diff` | `memcommit.commands.diff:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `distill` | `memcommit.commands.distill:cmd` | `memcommit.distill_application`<br>`memcommit.distill_runtime` | `memcommit.interfaces.tui.operations.distill`<br>`memcommit.interfaces.tui.operations.distill.adapter`<br>`memcommit.interfaces.tui.operations.distill.model`<br>`memcommit.interfaces.tui.operations.distill.screen` | `apply_distill`<br>`distill_context` | `memcommit.interfaces.agent.distill` | `docs/distill-elaborate-application-boundary-matrix.md` | `MULTI_ADAPTER` | `CLOSED` |
| `edit` | `memcommit.commands.edit:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `elaborate` | `memcommit.commands.elaborate:cmd` | `memcommit.elaborate_application`<br>`memcommit.elaborate_runtime` | `memcommit.interfaces.tui.operations.elaborate`<br>`memcommit.interfaces.tui.operations.elaborate.adapter`<br>`memcommit.interfaces.tui.operations.elaborate.model`<br>`memcommit.interfaces.tui.operations.elaborate.screen` | `elaborate` | `memcommit.interfaces.agent.elaborate` | `docs/distill-elaborate-application-boundary-matrix.md` | `MULTI_ADAPTER` | `CLOSED` |
| `embed` | `memcommit.interfaces.cli.embed:cmd` | `memcommit.embed_application`<br>`memcommit.embed_runtime` | `memcommit.interfaces.tui.operations.embed`<br>`memcommit.interfaces.tui.operations.embed.adapter`<br>`memcommit.interfaces.tui.operations.embed.model`<br>`memcommit.interfaces.tui.operations.embed.screen` | — | — | `docs/embed-application-boundary-matrix.md` | `BOUNDED_INTERNAL` | `CLOSED` |
| `eval` | `memcommit.commands.semantic_eval:eval_app` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `find` | `memcommit.commands.find:cmd` | `memcommit.find_application`<br>`memcommit.find_materialization_application`<br>`memcommit.find_materialization_runtime`<br>`memcommit.find_runtime` | — | — | — | `docs/find-search-application-boundary-matrix.md` | `BOUNDED_INTERNAL` | `MIXED` |
| `find-ambiguities` | `memcommit.commands.find_ambiguities:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `find-conflicts` | `memcommit.commands.find_conflicts:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `find-duplicates` | `memcommit.commands.find_duplicates:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `fit` | `memcommit.commands.fit:cmd` | `memcommit.fit_application`<br>`memcommit.fit_runtime` | `memcommit.interfaces.tui.operations.fit`<br>`memcommit.interfaces.tui.operations.fit.adapter`<br>`memcommit.interfaces.tui.operations.fit.model`<br>`memcommit.interfaces.tui.operations.fit.screen` | `fit` | `memcommit.interfaces.agent.fit` | `docs/fit-application-boundary-matrix.md` | `MULTI_ADAPTER` | `CLOSED` |
| `forget` | `memcommit.commands.forget:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `ground` | `memcommit.commands.ground:cmd` | — | — | `distill_ground`<br>`elaborate_ground` | — | — | `PARTIAL_SURFACE` | `UNREVIEWED` |
| `help` | `memcommit.commands.help_inventory:cmd` | — | `memcommit.interfaces.tui.operations.help`<br>`memcommit.interfaces.tui.operations.help.inventory` | — | — | — | `PARTIAL_SURFACE` | `UNREVIEWED` |
| `impact` | `memcommit.commands.impact:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `import` | `memcommit.commands.import_profile:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `init` | `memcommit.commands.init:cmd` | `memcommit.context_init_application`<br>`memcommit.context_init_runtime` | `memcommit.interfaces.tui.operations.context_init`<br>`memcommit.interfaces.tui.operations.context_init.model`<br>`memcommit.interfaces.tui.operations.context_init.screen` | — | — | `docs/context-init-application-boundary-matrix.md` | `BOUNDED_INTERNAL` | `CLOSED` |
| `init-study` | `memcommit.commands.init_study:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `list` | `memcommit.commands.list_memories:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `lock` | `memcommit.commands.write_protection:lock_app` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `log` | `memcommit.commands.log:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `meld` | `memcommit.commands.meld:cmd` | `memcommit.meld_application`<br>`memcommit.meld_application_flow`<br>`memcommit.meld_assessment_application`<br>`memcommit.meld_resolution_application`<br>`memcommit.meld_restart_application`<br>`memcommit.meld_runtime`<br>`memcommit.meld_session_application`<br>`memcommit.meld_start_application` | `memcommit.interfaces.tui.operations.meld`<br>`memcommit.interfaces.tui.operations.meld.model`<br>`memcommit.interfaces.tui.operations.meld.screen`<br>`memcommit.interfaces.tui.operations.meld.setup` | `apply_meld`<br>`comment_meld`<br>`defer_meld`<br>`open_meld`<br>`preserve_meld`<br>`restart_meld`<br>`start_meld` | `memcommit.interfaces.agent.meld` | `docs/meld-application-boundary-matrix.md` | `MULTI_ADAPTER` | `CLOSED` |
| `merge` | `memcommit.commands.merge:cmd` | `memcommit.merge_application`<br>`memcommit.merge_runtime` | `memcommit.interfaces.tui.operations.merge`<br>`memcommit.interfaces.tui.operations.merge.adapter`<br>`memcommit.interfaces.tui.operations.merge.model`<br>`memcommit.interfaces.tui.operations.merge.resolution`<br>`memcommit.interfaces.tui.operations.merge.screen`<br>`memcommit.interfaces.tui.operations.merge.setup` | — | — | `docs/merge-application-boundary-matrix.md` | `BOUNDED_INTERNAL` | `CLOSED` |
| `profile` | `memcommit.commands.profile:app` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `provider` | `memcommit.commands.provider:app` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `pwd` | `memcommit.commands.pwd:cmd` | `memcommit.current_context_application`<br>`memcommit.current_context_runtime` | — | — | — | — | `PARTIAL_SURFACE` | `CLOSED` |
| `query` | `memcommit.commands.query:cmd` | `memcommit.operations.query`<br>`memcommit.operations.query.granted_application`<br>`memcommit.operations.query.granted_runtime`<br>`memcommit.operations.query.ordinary_application`<br>`memcommit.operations.query.ordinary_runtime`<br>`memcommit.operations.query.reference_application`<br>`memcommit.operations.query.reference_runtime`<br>`memcommit.query_application`<br>`memcommit.query_reference_application`<br>`memcommit.query_reference_runtime`<br>`memcommit.query_runtime` | `memcommit.interfaces.tui.operations.query`<br>`memcommit.interfaces.tui.operations.query.adapter`<br>`memcommit.interfaces.tui.operations.query.model`<br>`memcommit.interfaces.tui.operations.query.screen` | `query_granted`<br>`query_ordinary`<br>`query_reference` | `memcommit.interfaces.agent.query` | `docs/query-answer-application-boundary-matrix.md`<br>`docs/query-callable-boundary-matrix.md`<br>`docs/query-reference-application-boundary-matrix.md` | `MULTI_ADAPTER` | `CLOSED` |
| `rationale` | `memcommit.commands.rationale:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `redo` | `memcommit.commands.redo:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `reference` | `memcommit.commands.reference:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `rename` | `memcommit.commands.rename:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `resolve` | `memcommit.commands.resolve:cmd` | `memcommit.resolve_application`<br>`memcommit.resolve_runtime` | `memcommit.interfaces.tui.operations.resolve`<br>`memcommit.interfaces.tui.operations.resolve.screen` | `apply_resolve`<br>`resolve_context` | `memcommit.interfaces.agent.resolve` | — | `PARTIAL_SURFACE` | `CLOSED` |
| `revert` | `memcommit.commands.revert:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `review` | `memcommit.commands.review:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `sever` | `memcommit.commands.sever:cmd` | `memcommit.sever_application`<br>`memcommit.sever_runtime` | — | — | — | `docs/sever-application-boundary-matrix.md` | `BOUNDED_INTERNAL` | `CLOSED` |
| `share` | `memcommit.commands.share:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `shell-init` | `memcommit.commands.shell_init:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `show` | `memcommit.commands.show:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `status` | `memcommit.commands.status:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `summarize` | `memcommit.commands.summarize:cmd` | `memcommit.summarize_application`<br>`memcommit.summarize_runtime` | `memcommit.interfaces.tui.operations.summarize`<br>`memcommit.interfaces.tui.operations.summarize.adapter`<br>`memcommit.interfaces.tui.operations.summarize.model`<br>`memcommit.interfaces.tui.operations.summarize.screen` | — | — | `docs/summarize-application-boundary-matrix.md` | `BOUNDED_INTERNAL` | `CLOSED` |
| `switch` | `memcommit.commands.switch:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `trace` | `memcommit.commands.trace:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `translate` | `memcommit.commands.translate:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `undo` | `memcommit.commands.undo:cmd` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `unlock` | `memcommit.commands.write_protection:unlock_app` | — | — | — | — | — | `COMMAND_ONLY` | `UNREVIEWED` |
| `update` | `memcommit.commands.update:cmd` | `memcommit.update_application`<br>`memcommit.update_application_flow` | `memcommit.interfaces.tui.operations.update`<br>`memcommit.interfaces.tui.operations.update.model`<br>`memcommit.interfaces.tui.operations.update.setup` | — | — | `docs/update-application-boundary-matrix.md` | `BOUNDED_INTERNAL` | `MIXED` |
