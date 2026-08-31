"""Render the frozen relocation plan for flat memcommit root modules."""

from __future__ import annotations

import argparse
import ast
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile


REPOSITORY = Path(__file__).resolve().parents[1]
PACKAGE = REPOSITORY / "src" / "memcommit"
OUTPUT_JSON = REPOSITORY / "agent-records" / "docs" / "root-module-relocation-plan.json"
OUTPUT_MARKDOWN = (
    REPOSITORY / "agent-records" / "docs" / "root-module-relocation-plan.md"
)
BASELINE_COMMIT = "885e62c0"


ROOT_BOUNDARIES = {
    "__init__": "public package surface",
}


HISTORICAL_PACKAGE_TARGETS = {
    "memcommit.semantic_execution": "memcommit.application.capabilities.semantic_execution",
    **{
        f"memcommit.semantic_execution.{module}": (
            f"memcommit.application.capabilities.semantic_execution.{module}"
        )
        for module in (
            "budgeting",
            "coverage",
            "execution",
            "model",
            "partitioning",
            "planning",
            "relations",
        )
    },
}


# A retired prototype remains in the frozen baseline inventory, but no longer
# receives a compatibility alias once both its behavior and canonical owner
# have been deliberately removed.
RETIRED_ROOT_MODULES = {
    "atomize_grounding": (
        "retired when Atomize issues became read-only evidence instead of a "
        "second Grounding workflow"
    ),
    "atomize_grounding_application": (
        "retired with Atomize's provider-backed Grounding workflow"
    ),
    "atomize_grounding_provider": (
        "retired with Atomize's provider-backed Grounding workflow"
    ),
    "atomize_grounding_runtime": (
        "retired with Atomize's provider-backed Grounding workflow"
    ),
    "atomize_meld_adapter": (
        "retired with Atomize's compound Grounding incorporation route"
    ),
    "atomize_workflow": (
        "retired after the unused Atomize analysis-open composition facade was removed"
    ),
    "bootstrap": (
        "retired with the console presentation-mode router it existed only to compose"
    ),
    "console_invocation": (
        "retired after its isolated routing prototype proved unused by shipped "
        "console commands"
    ),
    "derived_policy": (
        "retired when ordinary Grant authority contracted to QUERY, CREATE, "
        "READ, UPDATE, and DELETE"
    ),
    "flow_placeholder": (
        "retired with the per-Memory Query catalog and its presentation assets"
    ),
    "find_answer_dialogue": (
        "retired with the uncalled conversational Search answer path"
    ),
    "find_materialization_application": (
        "retired when selected-result saving moved to the shared application capability"
    ),
    "find_materialization_runtime": (
        "retired when selected-result saving moved to the shared application capability"
    ),
    "find_scope_evidence": (
        "retired after ordinary Query retained only its one-shot evidence projection"
    ),
    "find_turn_dialogue": (
        "retired with the uncalled conversational Search follow-up interpreter"
    ),
    "interactive_command": (
        "retired after its disconnected classification registry was replaced "
        "by tests of the concrete command builders and interaction surfaces"
    ),
    "ground": ("retired when the legacy named Ground session model was removed"),
    "ground_turn_dialogue": ("retired with the legacy named Ground session interface"),
    "review_report_adapters": (
        "retired after generic application-to-console report projection was "
        "federated into each operation's console adapter"
    ),
    "translation_view": (
        "retired when the mixed translation view was split into a core catalog "
        "and explicit application and persistence owners"
    ),
    "translation_view_store": (
        "retired when translation catalog persistence moved to its explicit "
        "repository owner"
    ),
}


COMPATIBILITY_TARGET_OVERRIDES = {
    # This historical forwarding implementation moves with the physical
    # facade cleanup rather than remaining executable at the package root.
    "atomize_workflow": "memcommit.application.operations.semantic_updates.derive.atomize.workflow",
    "atomize_workbench": "memcommit.application.operations.semantic_updates.derive.atomize.records",
    "add_application": "memcommit.application.operations.create_copy_connect.add.application",
    "add_runtime": "memcommit.application.operations.create_copy_connect.add.runtime",
    "comparison_summary": "memcommit.application.operations.search_explain.synthesize.compare.compare_summary",
    "comparison_summary_application": "memcommit.application.operations.search_explain.synthesize.compare.application",
    "comparison_summary_provider": "memcommit.application.operations.search_explain.synthesize.compare.provider_contract",
    "comparison_summary_rules": "memcommit.application.operations.search_explain.synthesize.compare.compare_rules",
    "context_scope": "memcommit.application.capabilities.context_scope_loading",
    "context_init_application": "memcommit.application.operations.create_copy_connect.init.application",
    "context_init_runtime": "memcommit.application.operations.create_copy_connect.init.runtime",
    "current_context_application": "memcommit.application.operations.browse_navigate.pwd.application",
    "current_context_runtime": "memcommit.application.operations.browse_navigate.pwd.runtime",
    "elaborate_add_runtime": "memcommit.application.operations.semantic_updates.derive.makemore.add_runtime",
    "elaborate_application": "memcommit.application.operations.semantic_updates.derive.makemore.application",
    "elaborate_runtime": "memcommit.application.operations.semantic_updates.derive.makemore.runtime",
    "embed_application": "memcommit.application.operations.create_copy_connect.embed.application",
    "embed_runtime": "memcommit.application.operations.create_copy_connect.embed.runtime",
    "forget_resolution_adapter": (
        "memcommit.adapters.console.commands.semantic_updates.curate_integrate.forget.workbench.presentation"
    ),
    # The baseline facade still names the pre-staging interface package; keep
    # its historical key while advancing only the canonical implementation.
    "impact_controller": ("memcommit.adapters.console.terminal.components.impact"),
    "help_application": "memcommit.application.operations.system_study_tools.help.application",
    "help_lookup_application": "memcommit.application.operations.system_study_tools.help.lookup_application",
    "literal_find_application": "memcommit.application.operations.search_explain.retrieve_answer.find.application",
    "literal_find_runtime": "memcommit.application.operations.search_explain.retrieve_answer.find.runtime",
    "meld_application": "memcommit.application.operations.semantic_updates.curate_integrate.meld.apply",
    "meld_application_flow": "memcommit.application.operations.semantic_updates.curate_integrate.meld.application",
    "meld_assessment_application": "memcommit.application.operations.semantic_updates.curate_integrate.meld.planning",
    "meld_resolution_application": "memcommit.application.operations.semantic_updates.curate_integrate.meld.proposal_iteration",
    "meld_restart_application": "memcommit.application.operations.semantic_updates.curate_integrate.meld.preparation",
    "meld_session_application": "memcommit.application.operations.semantic_updates.curate_integrate.meld.proposal_iteration",
    "meld_start_application": "memcommit.application.operations.semantic_updates.curate_integrate.meld.preparation",
    # The historical combined facades were removed before Copy and Move gained
    # independent entrypoints. Their nearest shared successor is now the paired
    # contract/Store kernel; current callers enter copy or move directly.
    "memory_transfer_application": (
        "memcommit.application.capabilities.memory_transfer.application"
    ),
    "memory_transfer_runtime": "memcommit.application.capabilities.memory_transfer.runtime",
    "reference_application": "memcommit.application.operations.create_copy_connect.reference.application",
    "reference_runtime": "memcommit.application.operations.create_copy_connect.reference.runtime",
    "review_report": "memcommit.application.capabilities.reviewing.report",
    "dedup_runtime": "memcommit.application.operations.quality_resolution.repair.dedun.runtime",
    "exact_dedup": "memcommit.application.operations.quality_resolution.repair.dedup.application",
    "exact_dedup_application": "memcommit.application.operations.quality_resolution.repair.dedup.application",
    "update_application": "memcommit.application.operations.semantic_updates.foundation.update.application",
}


# A relocated canonical owner may be a package rather than one module file.
MODULE_TARGET_PATH_OVERRIDES = {
    "memcommit.adapters.console.terminal.components.command_editor": (
        "memcommit/adapters/console/terminal/components/command_editor/__init__.py"
    ),
    "memcommit.persistence.store": "memcommit/persistence/store/__init__.py",
}


OPERATION_TARGETS = {
    "quality_audit": "memcommit.application.operations.quality_resolution.diagnose.audit.model",
    "quality_audit_store": "memcommit.persistence.operations.audit.record_repository",
    "comparison": "memcommit.application.capabilities.memory_issue_analysis.peer_relations.model",
    "comparison_evidence": "memcommit.application.capabilities.memory_issue_analysis.peer_relations.evidence",
    "comparison_execution": "memcommit.application.capabilities.memory_issue_analysis.peer_relations.execution",
    "comparison_present": "memcommit.adapters.console.commands.search_explain.synthesize.compare.presentation",
    "comparison_provider": "memcommit.application.capabilities.memory_issue_analysis.peer_relations.provider_contract",
    "comparison_session_application": "memcommit.application.operations.search_explain.synthesize.compare.sessions",
    "comparison_store": "memcommit.application.capabilities.memory_issue_analysis.peer_relations.repository",
    "comparison_summary_present": "memcommit.adapters.console.commands.search_explain.synthesize.compare.summary_presentation",
    "conformance": "memcommit.application.operations.quality_resolution.validate.check_conformance.model",
    "conformance_runtime": "memcommit.application.operations.quality_resolution.validate.check_conformance.runtime",
    "dedun_scope": "memcommit.application.operations.quality_resolution.repair.dedun.runtime",
    "dedup_planning": "memcommit.application.operations.quality_resolution.repair.dedun.analysis",
    "distill": "memcommit.application.operations.semantic_updates.derive.distill.model",
    "distill_config": "memcommit.application.operations.semantic_updates.derive.distill.config",
    "distill_goal_fit": "memcommit.application.operations.semantic_updates.derive.distill.goal_fit",
    "elaborate": "memcommit.application.operations.semantic_updates.derive.makemore.model",
    "elaborate_config": "memcommit.application.operations.semantic_updates.derive.makemore.config",
    "elaborate_target_context": "memcommit.application.operations.semantic_updates.derive.makemore.target_context",
    "find_answer_references": "memcommit.application.operations.search_explain.retrieve_answer.search.answer_references",
    "forget_provider": "memcommit.application.operations.semantic_updates.curate_integrate.forget.provider",
    "forget_review": "memcommit.application.operations.semantic_updates.curate_integrate.forget.review",
    "granted_comparison_store": "memcommit.application.capabilities.memory_issue_analysis.peer_relations.granted_repository",
    "granted_source_update_application": "memcommit.application.context_access.model",
    "granted_update_application": "memcommit.application.operations.semantic_updates.foundation.update.publication",
    "ground_context_catalog": "memcommit.application.operations.ground_workbench.ground.context_catalog",
    "ground_dialogue": "memcommit.application.operations.ground_workbench.ground.dialogue",
    "ground_distill": "memcommit.application.operations.ground_workbench.ground.distill",
    "ground_elaborate": "memcommit.application.operations.ground_workbench.ground.makemore",
    "ground_workspace": "memcommit.application.operations.ground_workbench.ground.workspace_model",
    "ground_workspace_application": "memcommit.application.operations.ground_workbench.ground.workspace_application",
    "ground_workspace_draft": "memcommit.application.operations.ground_workbench.ground.workspace_draft",
    "ground_workspace_draft_store": "memcommit.application.operations.ground_workbench.ground.workspace_draft_store",
    "ground_workspace_fit": "memcommit.application.operations.ground_workbench.ground.workspace_fit",
    "ground_workspace_history": "memcommit.application.operations.ground_workbench.ground.workspace_history",
    "ground_workspace_projection": "memcommit.application.operations.ground_workbench.ground.workspace_projection",
    "ground_workspace_runtime": "memcommit.application.operations.ground_workbench.ground.workspace_runtime",
    "history_search": "memcommit.application.capabilities.history.query.semantic_history_query",
    "meld": "memcommit.application.operations.semantic_updates.curate_integrate.meld.model",
    "meld_choice_branches": "memcommit.application.operations.semantic_updates.curate_integrate.meld.proposal_choices",
    "meld_provider": "memcommit.application.operations.semantic_updates.curate_integrate.meld.provider",
    "meld_resolution_adapter": "memcommit.application.operations.semantic_updates.curate_integrate.meld.proposal_projection",
    "meld_resolution_cache": "memcommit.application.operations.semantic_updates.curate_integrate.meld.proposal_cache",
    "merge_planning": "memcommit.application.operations.direct_changes.merge.planning",
    "merge_tree": "memcommit.application.operations.direct_changes.merge.tree",
    "merge_tree_persistence": "memcommit.application.operations.direct_changes.merge.tree_persistence",
    "ordinary_query_answer": "memcommit.application.operations.search_explain.retrieve_answer.query.answer",
    "context_rationale": "memcommit.application.operations.history_recovery.inspection.rationale.context",
    "rationale": "memcommit.application.operations.history_recovery.inspection.rationale.model",
    "rationale_cache": "memcommit.application.operations.history_recovery.inspection.rationale.cache",
    "rationale_rules": "memcommit.application.operations.history_recovery.inspection.rationale.rules",
    "rationale_scope": "memcommit.application.operations.history_recovery.inspection.rationale.scope",
    "rationale_semantic": "memcommit.application.operations.history_recovery.inspection.rationale.semantic",
    "reference_provenance": "memcommit.application.operations.create_copy_connect.reference.provenance",
    "resolve_rules": "memcommit.application.operations.quality_resolution.repair.resolve.rules",
    "resolve_semantic": "memcommit.application.operations.quality_resolution.repair.resolve.semantic",
    "resolve_targeting": "memcommit.application.operations.quality_resolution.repair.resolve.targeting",
    "resource_import": "memcommit.application.operations.create_copy_connect.resource_import",
    "show_application": "memcommit.application.operations.browse_navigate.show.application",
    "show_runtime": "memcommit.application.operations.browse_navigate.show.runtime",
    "status_application": "memcommit.application.operations.browse_navigate.status.application",
    "status_runtime": "memcommit.application.operations.browse_navigate.status.runtime",
    "switch_application": "memcommit.application.operations.browse_navigate.switch.application",
    "switch_runtime": "memcommit.application.operations.browse_navigate.switch.runtime",
    "review": "memcommit.application.operations.operation_lifecycle.review.model",
    "search": "memcommit.application.operations.search_explain.retrieve_answer.search.model",
    "search_artifacts": "memcommit.application.operations.search_explain.retrieve_answer.search.artifacts",
    "share": "memcommit.application.operations.sharing_protection.share.model",
    "summarize": "memcommit.application.operations.search_explain.synthesize.summarize.model",
    "update": "memcommit.application.operations.semantic_updates.foundation.update.model",
    "update_application_flow": "memcommit.adapters.console.commands.semantic_updates.foundation.update.workbench.application",
    "update_endpoints": "memcommit.adapters.console.commands.semantic_updates.foundation.update.endpoint_operands",
    "update_receipt_store": (
        "memcommit.persistence.operations.update.receipt_repository"
    ),
    "update_resolution_adapter": "memcommit.adapters.console.commands.semantic_updates.foundation.update.workbench.presentation",
}


CONCEPT_TARGETS = {
    "_architecture_catalog": "scripts.callable_catalog.catalog",
    "ambiguity_pipeline": "memcommit.application.capabilities.semantic.classification.ambiguity",
    "application_flow": "memcommit.application.capabilities.flow",
    "application_review_policy": "memcommit.application.capabilities.review_policy",
    "applied_checkpoint_review": "memcommit.application.operations.operation_lifecycle.review.applied_checkpoint",
    "checkpoint_catalog": "memcommit.application.capabilities.checkpoint_catalog",
    "checkpoint_frames": "memcommit.persistence.store.context_memory.checkpoint_frame_mapping",
    "checkpoint_migration": "memcommit.application.operations.browse_navigate.rename.history_repair",
    "cli": "memcommit.adapters.console.entrypoint",
    "clipboard": "memcommit.adapters.console.clipboard",
    "command_attempts": "memcommit.persistence.command_ledger.attempts",
    "command_history": "memcommit.application.capabilities.command_recovery",
    "config": "memcommit.configuration.config",
    "context": "memcommit.core.context",
    "context_catalog": "memcommit.persistence.store.context_memory.catalog_model",
    "context_history": "memcommit.application.capabilities.history.query.context_history_slicing",
    "context_lifecycle": "memcommit.persistence.store.context_memory.lifecycle_model",
    "context_locator": "memcommit.application.capabilities.context_locator",
    "context_naming": "memcommit.core.context_targeting.naming",
    "context_snapshot": "memcommit.application.capabilities.context_snapshot",
    "current_context_navigation": "memcommit.core.context_navigation",
    "direct_item_duplicates": "memcommit.application.capabilities.reviewing.direct_item_duplicates",
    "distill_elaborate_reference": "memcommit.application.capabilities.semantic.generative_reduction_reference",
    "duplicate_pipeline": "memcommit.application.capabilities.semantic.classification.duplicates",
    "exact_command_review": "memcommit.adapters.console.terminal.components.command_editor.model",
    "findings": "memcommit.application.capabilities.memory_issue_analysis.provider_contract",
    "goal_focus": "memcommit.application.capabilities.semantic.goal_focus",
    "goal_focus_runtime": "memcommit.application.capabilities.semantic.goal_focus_runtime",
    "granted_provenance": "memcommit.application.operations.history_recovery.inspection.trace.granted_view",
    "history": "memcommit.application.capabilities.history.reconstruction.checkpoint_state_projection",
    "history_display": "memcommit.adapters.console.terminal.components.history.display",
    "interactive_command_review": "memcommit.adapters.console.terminal.components.command_editor",
    "memory_diff": "memcommit.application.capabilities.reviewing.memory_diff",
    "memory_lineage": "memcommit.application.capabilities.history.reconstruction.memory_lineage_relations",
    "name_suggestions": "memcommit.application.capabilities.name_suggestions",
    "ops": "memcommit.application.capabilities.ops",
    "operation_gate_pipeline": "memcommit.application.capabilities.semantic.classification.gates",
    "profile_config": "memcommit.application.operations.profiles.profile.config",
    "profiles": "memcommit.application.operations.profiles.profile.model",
    "provenance": "memcommit.application.capabilities.history.query.memory_history_slicing",
    "provider_types": "memcommit.providers.types",
    "quality_find_report": "memcommit.application.capabilities.memory_issue_analysis.report",
    "quality_find_workbench": "memcommit.application.capabilities.memory_issue_analysis.workbench",
    "quality_finding_handoff": "memcommit.application.capabilities.memory_issue_analysis.handoff",
    "query_provider": "memcommit.providers.subscription",
    "read_report": "memcommit.application.capabilities.reviewing.read_report",
    "read_report_recents": "memcommit.application.capabilities.reviewing.read_report_recents",
    "redundancy_scope": "memcommit.application.capabilities.memory_issue_analysis.redundancy_scope",
    "resolution_workbench": "memcommit.application.capabilities.resolution.workbench",
    "result_workbench": "memcommit.application.capabilities.reviewing.result_workbench",
    "selective_curation": "memcommit.application.capabilities.semantic.selective_curation",
    "semantic_disclosure": "memcommit.application.capabilities.semantic.disclosure",
    "semantic_add_runtime": (
        "memcommit.application.capabilities.semantic_result_memorization"
    ),
    "semantic_prompt_policy": "memcommit.application.capabilities.semantic.prompt_policy",
    "semantic_provider": "memcommit.providers.semantic",
    "semantic_redundancy_evidence": "memcommit.application.capabilities.semantic.redundancy_evidence",
    "session_workbench_navigation": "memcommit.application.capabilities.reviewing.session_navigation",
    "storage_permissions": "memcommit.application.capabilities.authority.storage_permissions",
    "study_action_log": "memcommit.persistence.command_ledger.study_actions",
    "study_operation_policy": "memcommit.application.capabilities.authority.study_operation_policy",
    "store": "memcommit.persistence.store",
    "temporal_history": "memcommit.application.capabilities.history.reconstruction.memory_state_delta",
    "uid_locator": "memcommit.core.context_targeting.uid_locator",
    "understanding": "memcommit.application.capabilities.semantic.understanding",
    "write_protection": "memcommit.application.capabilities.authority.write_protection",
}


def _module_target_path(module: str) -> str:
    return MODULE_TARGET_PATH_OVERRIDES.get(
        module,
        module.replace(".", "/") + ".py",
    )


def _canonical_source_path(module: str) -> Path:
    relative = Path(_module_target_path(module))
    if module.startswith("scripts."):
        return REPOSITORY / relative
    return REPOSITORY / "src" / relative


CLASSIFIED_OPERATION_TARGETS = {
    "find": "search_explain.retrieve_answer.find",
    "search": "search_explain.retrieve_answer.search",
    "query": "search_explain.retrieve_answer.query",
    "summarize": "search_explain.synthesize.summarize",
    "compare": "search_explain.synthesize.compare",
    "edit": "direct_changes.edit",
    "move": "direct_changes.move",
    "replace": "direct_changes.replace",
    "chunk": "direct_changes.chunk",
    "delete": "direct_changes.delete",
    "clear": "direct_changes.clear",
    "merge": "direct_changes.merge",
    "update": "semantic_updates.foundation.update",
    "atomize": "semantic_updates.derive.atomize",
    "distill": "semantic_updates.derive.distill",
    "elaborate": "semantic_updates.derive.elaborate",
    "makemore": "semantic_updates.derive.makemore",
    "forget": "semantic_updates.curate_integrate.forget",
    "sever": "semantic_updates.curate_integrate.sever",
    "meld": "semantic_updates.curate_integrate.meld",
    "translate": "translation.translate",
    "find_duplicates": "quality_resolution.diagnose.find_duplicates",
    "find_redundancies": "quality_resolution.diagnose.find_redundancies",
    "find_ambiguities": "quality_resolution.diagnose.find_ambiguities",
    "find_conflicts": "quality_resolution.diagnose.find_conflicts",
    "audit": "quality_resolution.diagnose.audit",
    "dedup": "quality_resolution.repair.dedup",
    "dedun": "quality_resolution.repair.dedun",
    "resolve": "quality_resolution.repair.resolve",
    "fit": "quality_resolution.validate.fit",
    "conformance": "quality_resolution.validate.check_conformance",
    "review": "operation_lifecycle.review",
    "log": "history_recovery.inspection.log",
    "diff": "history_recovery.inspection.diff",
    "trace": "history_recovery.inspection.trace",
    "rationale": "history_recovery.inspection.rationale",
    "checkpoint": "history_recovery.recovery.checkpoint",
    "undo": "history_recovery.recovery.undo",
    "redo": "history_recovery.recovery.redo",
    "revert": "history_recovery.recovery.revert",
}


def _current_target(module: str | None) -> str | None:
    """Map frozen operation owners to their current canonical package."""

    if module == "memcommit.operations":
        return "memcommit.application.operations"
    for prefix in (
        "memcommit.operations.",
        "memcommit.application.operations.",
    ):
        if module is not None and module.startswith(prefix):
            relative = module.removeprefix(prefix)
            owner, separator, remainder = relative.partition(".")
            physical_owner = CLASSIFIED_OPERATION_TARGETS.get(owner, owner)
            return "memcommit.application.operations." + physical_owner + (
                separator + remainder if separator else ""
            )
    return module


def _compatibility_target(source: str, *, stem: str) -> str | None:
    override = COMPATIBILITY_TARGET_OVERRIDES.get(stem)
    if override is not None:
        return _current_target(override)
    tree = ast.parse(source)
    bindings: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                bindings[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                bindings[alias.asname or alias.name] = f"{node.module}.{alias.name}"
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "import_module"
            and len(node.value.args) == 1
            and isinstance(node.value.args[0], ast.Constant)
            and isinstance(node.value.args[0].value, str)
        ):
            bindings[node.targets[0].id] = node.value.args[0].value
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Subscript)
            and isinstance(node.targets[0].value, ast.Attribute)
            and isinstance(node.targets[0].value.value, ast.Name)
            and node.targets[0].value.value.id == "sys"
            and node.targets[0].value.attr == "modules"
            and isinstance(node.value, ast.Name)
        ):
            return _current_target(bindings.get(node.value.id))
    return None


def _is_compatibility(source: str) -> bool:
    doc = ast.get_docstring(ast.parse(source)) or ""
    first_line = doc.splitlines()[0] if doc.splitlines() else ""
    return "Compatibility" in first_line or ("sys.modules[__name__]" in source)


def _baseline_sources() -> dict[str, str]:
    archive = subprocess.run(
        ["git", "archive", BASELINE_COMMIT, "memcommit"],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
    ).stdout
    sources = {}
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        for member in stream.getmembers():
            if not member.isfile() or not member.name.endswith(".py"):
                continue
            extracted = stream.extractfile(member)
            assert extracted is not None
            sources[member.name] = extracted.read().decode("utf-8")
    return sources


def _inbound_importers(
    module: str,
    *,
    source_path: str,
    sources: dict[str, str],
) -> int:
    needle = module + "."
    direct = module
    count = 0
    for path, source in sources.items():
        if path == source_path:
            continue
        if direct in source or needle in source:
            count += 1
    return count


def build_plan() -> dict[str, object]:
    entries = []
    unclassified = []
    sources = _baseline_sources()
    root_paths = sorted(
        path
        for path in sources
        if path.startswith("memcommit/") and path.count("/") == 1
    )
    for relative_path in root_paths:
        path = Path(relative_path)
        stem = path.stem
        source = sources[relative_path]
        module = f"memcommit.{stem}" if stem != "__init__" else "memcommit"
        if stem in OPERATION_TARGETS:
            role = "operation-implementation"
            target = OPERATION_TARGETS[stem]
            action = "relocate-without-alias"
            reason = "implementation is named for and consumed by one operation family"
        elif stem in CONCEPT_TARGETS:
            role = "shared-concept-implementation"
            target = CONCEPT_TARGETS[stem]
            action = "relocate-without-alias"
            reason = "implementation belongs to a reusable named concept"
        elif stem in ROOT_BOUNDARIES:
            role = "root-boundary"
            target = module
            action = "retain"
            reason = ROOT_BOUNDARIES[stem]
        elif stem in RETIRED_ROOT_MODULES:
            role = "retired-prototype"
            target = None
            action = "retire"
            reason = RETIRED_ROOT_MODULES[stem]
        elif _is_compatibility(source):
            role = "historical-compatibility-facade"
            target = _compatibility_target(source, stem=stem)
            action = "remove"
            reason = "historical forwarding imports are intentionally unsupported"
        else:
            unclassified.append(path.name)
            continue
        entries.append(
            {
                "path": relative_path,
                "module": module,
                "lines": len(source.splitlines()),
                "inbound_package_importers": _inbound_importers(
                    module,
                    source_path=relative_path,
                    sources=sources,
                ),
                "role": role,
                "action": action,
                "canonical_target": target,
                "canonical_target_path": (
                    _module_target_path(target) if target is not None else None
                ),
                "reason": reason,
            }
        )
    if unclassified:
        raise RuntimeError(
            "Unclassified root modules: " + ", ".join(sorted(unclassified))
        )
    missing_compatibility_targets = [
        entry["module"]
        for entry in entries
        if entry["role"] == "historical-compatibility-facade"
        and entry["canonical_target"] is None
    ]
    if missing_compatibility_targets:
        raise RuntimeError(
            "Compatibility facades without targets: "
            + ", ".join(missing_compatibility_targets)
        )
    if len(entries) != 249:
        raise RuntimeError(f"Expected 249 root modules, found {len(entries)}")
    targets = [
        entry["canonical_target"]
        for entry in entries
        if entry["action"] == "relocate-without-alias"
    ]
    if len(targets) != len(set(targets)):
        raise RuntimeError("Relocation targets must be unique")
    summary: dict[str, int] = {}
    for entry in entries:
        role = str(entry["role"])
        summary[role] = summary.get(role, 0) + 1
    return {
        "schema_version": 1,
        "purpose": (
            "Freeze the ownership classification used to remove flat physical "
            "facades without changing operation behavior and without preserving "
            "historical imports."
        ),
        "baseline_commit": BASELINE_COMMIT,
        "root_module_count": len(entries),
        "summary": summary,
        "modules": entries,
    }


def render_markdown(plan: dict[str, object]) -> str:
    summary = plan["summary"]
    assert isinstance(summary, dict)
    modules = plan["modules"]
    assert isinstance(modules, list)
    lines = [
        "# Root module relocation plan",
        "",
        "This is the frozen path-only inventory for the 249 Python modules that",
        "were directly under memcommit at baseline commit 885e62c0.",
        "",
        "## Summary",
        "",
        "| Role | Modules |",
        "| --- | ---: |",
    ]
    for role, count in sorted(summary.items()):
        lines.append(f"| {role} | {count} |")
    lines.extend(
        [
            "",
            "## Modules",
            "",
            "| Baseline module | Role | Action | Canonical target | Importers |",
            "| --- | --- | --- | --- | ---: |",
        ]
    )
    for entry in modules:
        assert isinstance(entry, dict)
        lines.append(
            "| {module} | {role} | {action} | {target} | {importers} |".format(
                module=entry["module"],
                role=entry["role"],
                action=entry["action"],
                target=(
                    "none (retired)"
                    if entry["role"] == "retired-prototype"
                    else entry["canonical_target"] or "multiple canonical modules"
                ),
                importers=entry["inbound_package_importers"],
            )
        )
    lines.append("")
    return "\n".join(lines)


def _removed_modules(plan: dict[str, object]) -> dict[str, str]:
    modules = plan["modules"]
    assert isinstance(modules, list)
    removed = dict(HISTORICAL_PACKAGE_TARGETS)
    for entry in modules:
        assert isinstance(entry, dict)
        if entry["role"] in {"root-boundary", "retired-prototype"}:
            continue
        target = entry["canonical_target"]
        if not isinstance(target, str) or not target:
            raise RuntimeError(f"Relocation target is missing: {entry['module']}")
        removed[str(entry["module"])] = target
    return removed


def verify_current_layout(plan: dict[str, object]) -> None:
    removed = _removed_modules(plan)
    failures = []
    for legacy, target in sorted(removed.items()):
        stem = legacy.removeprefix("memcommit.")
        legacy_path = PACKAGE / Path(*stem.split("."))
        legacy_file = legacy_path.with_suffix(".py")
        legacy_package = legacy_path / "__init__.py"
        target_path = _canonical_source_path(target)
        target_package = target_path.with_suffix("") / "__init__.py"
        if not target_path.is_file() and not target_package.is_file():
            failures.append(f"missing canonical target: {target_path}")
        if legacy_file.exists() or legacy_package.exists():
            failures.append(f"physical compatibility facade remains: {legacy_path}")

    for path in PACKAGE.rglob("*.py"):
        if path.parent == PACKAGE:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
            elif isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            for module in modules:
                if module in removed:
                    failures.append(
                        f"internal legacy import: {path}:{node.lineno}:{module}"
                    )

    root_module_names = {path.stem for path in PACKAGE.glob("*.py")}
    if root_module_names != set(ROOT_BOUNDARIES):
        failures.append(
            "root implementation boundary differs: expected "
            f"{sorted(ROOT_BOUNDARIES)}, found {sorted(root_module_names)}"
        )
    if failures:
        raise SystemExit("\n".join(failures))
    print(
        "root module layout is canonical-only: "
        f"{len(removed)} removed historical imports, "
        f"{len(ROOT_BOUNDARIES)} root implementations"
    )


def verify_removed_imports(plan: dict[str, object]) -> None:
    """Prove that no historical root import is restored by runtime hooks."""

    removed = sorted(_removed_modules(plan))
    code = "\n".join(
        [
            "from importlib import import_module",
            f"modules = {removed!r}",
            "unexpected = []",
            "for module in modules:",
            "    try:",
            "        import_module(module)",
            "    except ModuleNotFoundError:",
            "        pass",
            "    else:",
            "        unexpected.append(module)",
            "assert not unexpected, unexpected",
        ]
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode:
        raise SystemExit(result.stderr.strip() or result.stdout.strip())
    print(f"historical root imports are unavailable: {len(removed)} modules")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    plan = build_plan()
    rendered_json = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    rendered_markdown = render_markdown(plan)
    if args.check:
        if not OUTPUT_JSON.exists() or not OUTPUT_MARKDOWN.exists():
            raise SystemExit("root module relocation plan is missing")
        if OUTPUT_JSON.read_text(encoding="utf-8") != rendered_json:
            raise SystemExit("root module relocation JSON is stale")
        if OUTPUT_MARKDOWN.read_text(encoding="utf-8") != rendered_markdown:
            raise SystemExit("root module relocation Markdown is stale")
        verify_current_layout(plan)
        verify_removed_imports(plan)
        print("root module relocation plan is current")
        return 0
    OUTPUT_JSON.write_text(rendered_json, encoding="utf-8")
    OUTPUT_MARKDOWN.write_text(rendered_markdown, encoding="utf-8")
    print(f"wrote {len(plan['modules'])} root module records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
