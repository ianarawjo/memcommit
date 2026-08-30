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
    "bootstrap": "application composition root",
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
    "console_invocation": (
        "retired after its isolated routing prototype proved unused by shipped "
        "console commands"
    ),
    "flow_placeholder": (
        "retired with the per-Memory Query catalog and its presentation assets"
    ),
    "interactive_command": (
        "retired after its disconnected classification registry was replaced "
        "by tests of the concrete command builders and interaction surfaces"
    ),
}


COMPATIBILITY_TARGET_OVERRIDES = {
    # This historical forwarding implementation moves with the physical
    # facade cleanup rather than remaining executable at the package root.
    "atomize_workflow": "memcommit.application.operations.atomize.workflow",
    "context_scope": "memcommit.core.context_targeting.loading",
    "forget_resolution_adapter": (
        "memcommit.adapters.console.commands.forget.workbench.presentation"
    ),
    # The baseline facade still names the pre-staging interface package; keep
    # its historical key while advancing only the canonical implementation.
    "impact_controller": ("memcommit.adapters.console.terminal.components.impact"),
    "literal_find_application": "memcommit.application.operations.find.application",
    "literal_find_runtime": "memcommit.application.operations.find.runtime",
    "review_report": "memcommit.application.capabilities.reviewing.report",
    "dedup_runtime": "memcommit.application.operations.dedun.runtime",
    "exact_dedup": "memcommit.application.operations.dedup.application",
    "exact_dedup_application": "memcommit.application.operations.dedup.application",
}


# A relocated canonical owner may be a package rather than one module file.
MODULE_TARGET_PATH_OVERRIDES = {
    "memcommit.adapters.console.terminal.components.command_editor.command_review": (
        "memcommit/adapters/console/terminal/components/command_editor/"
        "command_review/__init__.py"
    ),
    "memcommit.persistence.store": "memcommit/persistence/store/__init__.py",
}


OPERATION_TARGETS = {
    "quality_audit": "memcommit.application.operations.audit.model",
    "quality_audit_store": "memcommit.persistence.operations.audit.record_repository",
    "comparison": "memcommit.application.operations.compare.ledger.model",
    "comparison_evidence": "memcommit.application.operations.compare.ledger.evidence",
    "comparison_execution": "memcommit.application.operations.compare.ledger.execution",
    "comparison_present": "memcommit.adapters.console.commands.compare.presentation",
    "comparison_provider": "memcommit.application.operations.compare.ledger.provider",
    "comparison_session_application": "memcommit.application.operations.compare.ledger.session_application",
    "comparison_store": "memcommit.application.operations.compare.ledger.store",
    "comparison_summary_present": "memcommit.adapters.console.commands.compare.summary_presentation",
    "conformance": "memcommit.application.operations.conformance.model",
    "conformance_runtime": "memcommit.application.operations.conformance.runtime",
    "dedun_scope": "memcommit.application.operations.dedun.scope",
    "dedup_planning": "memcommit.application.operations.dedun.planning",
    "distill": "memcommit.application.operations.distill.model",
    "distill_config": "memcommit.application.operations.distill.config",
    "distill_goal_fit": "memcommit.application.operations.distill.goal_fit",
    "elaborate": "memcommit.application.operations.elaborate.model",
    "elaborate_config": "memcommit.application.operations.elaborate.config",
    "elaborate_target_context": "memcommit.application.operations.elaborate.target_context",
    "find_answer_dialogue": "memcommit.application.operations.search.answer_dialogue",
    "find_answer_references": "memcommit.application.operations.search.answer_references",
    "find_scope_evidence": "memcommit.application.operations.search.scope_evidence",
    "find_turn_dialogue": "memcommit.application.operations.search.turn_dialogue",
    "forget_provider": "memcommit.application.operations.forget.provider",
    "forget_review": "memcommit.application.operations.forget.review",
    "granted_comparison_store": "memcommit.application.operations.compare.ledger.granted_store",
    "granted_source_update_application": "memcommit.application.operations.update.granted_source_application",
    "granted_update_application": "memcommit.application.operations.update.granted_application",
    "ground": "memcommit.application.operations.ground.model",
    "ground_context_catalog": "memcommit.application.operations.ground.context_catalog",
    "ground_dialogue": "memcommit.application.operations.ground.dialogue",
    "ground_distill": "memcommit.application.operations.ground.distill",
    "ground_elaborate": "memcommit.application.operations.ground.elaborate",
    "ground_turn_dialogue": "memcommit.application.operations.ground.turn_dialogue",
    "ground_workspace": "memcommit.application.operations.ground.workspace_model",
    "ground_workspace_application": "memcommit.application.operations.ground.workspace_application",
    "ground_workspace_draft": "memcommit.application.operations.ground.workspace_draft",
    "ground_workspace_draft_store": "memcommit.application.operations.ground.workspace_draft_store",
    "ground_workspace_fit": "memcommit.application.operations.ground.workspace_fit",
    "ground_workspace_history": "memcommit.application.operations.ground.workspace_history",
    "ground_workspace_projection": "memcommit.application.operations.ground.workspace_projection",
    "ground_workspace_runtime": "memcommit.application.operations.ground.workspace_runtime",
    "history_search": "memcommit.application.operations.log.search",
    "meld": "memcommit.application.operations.meld.model",
    "meld_choice_branches": "memcommit.application.operations.meld.choice_branches",
    "meld_provider": "memcommit.application.operations.meld.provider",
    "meld_resolution_adapter": "memcommit.application.operations.meld.resolution_adapter",
    "meld_resolution_cache": "memcommit.application.operations.meld.resolution_cache",
    "merge_planning": "memcommit.application.operations.merge.planning",
    "merge_tree": "memcommit.application.operations.merge.tree",
    "merge_tree_persistence": "memcommit.application.operations.merge.tree_persistence",
    "ordinary_query_answer": "memcommit.application.operations.query.answer",
    "context_rationale": "memcommit.application.operations.rationale.context",
    "rationale": "memcommit.application.operations.rationale.model",
    "rationale_cache": "memcommit.application.operations.rationale.cache",
    "rationale_rules": "memcommit.application.operations.rationale.rules",
    "rationale_scope": "memcommit.application.operations.rationale.scope",
    "rationale_semantic": "memcommit.application.operations.rationale.semantic",
    "reference_provenance": "memcommit.application.operations.reference.provenance",
    "resolve_rules": "memcommit.application.operations.resolve.rules",
    "resolve_semantic": "memcommit.application.operations.resolve.semantic",
    "resolve_targeting": "memcommit.application.operations.resolve.targeting",
    "resource_import": "memcommit.application.operations.resource_import.model",
    "review": "memcommit.application.operations.review.model",
    "review_report_adapters": "memcommit.application.operations.review.report_adapters",
    "search": "memcommit.application.operations.search.model",
    "search_artifacts": "memcommit.application.operations.search.artifacts",
    "share": "memcommit.application.operations.share.model",
    "summarize": "memcommit.application.operations.summarize.model",
    "update": "memcommit.application.operations.update.model",
    "update_application_flow": "memcommit.application.operations.update.application_flow",
    "update_endpoints": "memcommit.application.operations.update.endpoints",
    "update_receipt_store": "memcommit.application.operations.update.receipt_store",
    "update_resolution_adapter": "memcommit.application.operations.update.resolution_adapter",
}


CONCEPT_TARGETS = {
    "_architecture_catalog": "scripts.callable_catalog.catalog",
    "ambiguity_pipeline": "memcommit.application.capabilities.semantic.classification.ambiguity",
    "application_flow": "memcommit.application.capabilities.flow",
    "application_review_policy": "memcommit.application.capabilities.review_policy",
    "applied_checkpoint_review": "memcommit.application.capabilities.retained_history.applied_review",
    "checkpoint_catalog": "memcommit.application.capabilities.retained_history.checkpoint_catalog",
    "checkpoint_frames": "memcommit.application.capabilities.retained_history.checkpoint_frames",
    "checkpoint_migration": "memcommit.application.capabilities.retained_history.checkpoint_migration",
    "cli": "memcommit.adapters.console.entrypoint",
    "clipboard": "memcommit.adapters.console.clipboard",
    "command_attempts": "memcommit.persistence.command_ledger.attempts",
    "command_history": "memcommit.application.capabilities.retained_history.command_history",
    "config": "memcommit.configuration.config",
    "context": "memcommit.core.context",
    "context_catalog": "memcommit.core.context_targeting.context_catalog",
    "context_history": "memcommit.application.capabilities.retained_history.context_history",
    "context_lifecycle": "memcommit.application.capabilities.retained_history.context_lifecycle",
    "context_locator": "memcommit.application.capabilities.context_locator",
    "context_naming": "memcommit.core.context_targeting.naming",
    "context_snapshot": "memcommit.application.capabilities.retained_history.context_snapshot",
    "current_context_navigation": "memcommit.core.context_targeting.navigation",
    "derived_policy": "memcommit.application.capabilities.authority.derived_policy",
    "direct_item_duplicates": "memcommit.application.capabilities.reviewing.direct_item_duplicates",
    "distill_elaborate_reference": "memcommit.application.capabilities.semantic.generative_reduction_reference",
    "duplicate_pipeline": "memcommit.application.capabilities.semantic.classification.duplicates",
    "exact_command_review": "memcommit.adapters.console.terminal.components.command_editor.command_review.model",
    "findings": "memcommit.application.capabilities.reviewing.memory_issue_finding.findings",
    "goal_focus": "memcommit.application.capabilities.semantic.goal_focus",
    "goal_focus_runtime": "memcommit.application.capabilities.semantic.goal_focus_runtime",
    "granted_provenance": "memcommit.application.capabilities.retained_history.granted_provenance",
    "history": "memcommit.application.capabilities.retained_history.reconstruction",
    "history_display": "memcommit.application.capabilities.retained_history.display",
    "interactive_command_review": "memcommit.adapters.console.terminal.components.command_editor.command_review",
    "memory_diff": "memcommit.application.capabilities.reviewing.memory_diff",
    "memory_lineage": "memcommit.application.capabilities.retained_history.memory_lineage",
    "name_suggestions": "memcommit.core.context_targeting.name_suggestions",
    "ops": "memcommit.application.capabilities.ops",
    "operation_gate_pipeline": "memcommit.application.capabilities.semantic.classification.gates",
    "profile_config": "memcommit.application.operations.profile.config",
    "profiles": "memcommit.application.operations.profile.model",
    "provenance": "memcommit.application.capabilities.retained_history.memory_history_reconstruction",
    "provider_types": "memcommit.providers.types",
    "quality_find_report": "memcommit.application.capabilities.reviewing.memory_issue_finding.report",
    "quality_find_workbench": "memcommit.application.capabilities.reviewing.memory_issue_finding.workbench",
    "quality_finding_handoff": "memcommit.application.capabilities.reviewing.memory_issue_finding.handoff",
    "query_provider": "memcommit.providers.subscription",
    "read_report": "memcommit.application.capabilities.reviewing.read_report",
    "read_report_recents": "memcommit.application.capabilities.reviewing.read_report_recents",
    "redundancy_scope": "memcommit.application.capabilities.reviewing.memory_issue_finding.redundancy_scope",
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
    "temporal_history": "memcommit.application.capabilities.retained_history.temporal",
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


def _current_target(module: str | None) -> str | None:
    """Map frozen operation owners to their current canonical package."""

    if module == "memcommit.operations":
        return "memcommit.application.operations"
    if module is not None and module.startswith("memcommit.operations."):
        return "memcommit.application.operations." + module.removeprefix(
            "memcommit.operations."
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
