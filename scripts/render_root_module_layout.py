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
PACKAGE = REPOSITORY / "memcommit"
OUTPUT_JSON = REPOSITORY / "docs" / "root-module-relocation-plan.json"
OUTPUT_MARKDOWN = REPOSITORY / "docs" / "root-module-relocation-plan.md"
LEGACY_ALIAS_MODULE = (
    REPOSITORY / "memcommit" / "compatibility" / "_legacy_alias_map.py"
)
BASELINE_COMMIT = "885e62c0"


ROOT_BOUNDARIES = {
    "__init__": "public package surface",
    "bootstrap": "application composition root",
    "cli": "console entry point",
    "context": "public core Context and Memory model",
    "context_locator": "documented canonical existing-Context resolver",
    "ops": "public in-memory operation API",
    "store": "public persistence boundary",
}


COMPATIBILITY_TARGET_OVERRIDES = {
    # This historical forwarding implementation moves with the physical
    # facade cleanup rather than remaining executable at the package root.
    "atomize_workflow": "memcommit.operations.atomize.workflow",
    # These two narrow re-export surfaces remain explicit compatibility
    # modules instead of broadening to every name in their source modules.
    "context_scope": "memcommit.compatibility.context_scope",
    "forget_resolution_adapter": (
        "memcommit.compatibility.forget_resolution_adapter"
    ),
}


OPERATION_TARGETS = {
    "comparison": "memcommit.operations.compare.ledger.model",
    "comparison_evidence": "memcommit.operations.compare.ledger.evidence",
    "comparison_execution": "memcommit.operations.compare.ledger.execution",
    "comparison_present": "memcommit.interfaces.presentation.comparison",
    "comparison_provider": "memcommit.operations.compare.ledger.provider",
    "comparison_session_application": "memcommit.operations.compare.ledger.session_application",
    "comparison_store": "memcommit.operations.compare.ledger.store",
    "comparison_summary_present": "memcommit.interfaces.cli.comparison_summary",
    "conformance": "memcommit.operations.conformance.model",
    "conformance_runtime": "memcommit.operations.conformance.runtime",
    "dedun_scope": "memcommit.operations.dedun.scope",
    "dedup_planning": "memcommit.operations.dedup.planning",
    "distill": "memcommit.operations.distill.model",
    "distill_config": "memcommit.operations.distill.config",
    "distill_goal_fit": "memcommit.operations.distill.goal_fit",
    "elaborate": "memcommit.operations.elaborate.model",
    "elaborate_config": "memcommit.operations.elaborate.config",
    "elaborate_target_context": "memcommit.operations.elaborate.target_context",
    "find_answer_dialogue": "memcommit.operations.search.answer_dialogue",
    "find_answer_references": "memcommit.operations.search.answer_references",
    "find_scope_evidence": "memcommit.operations.search.scope_evidence",
    "find_turn_dialogue": "memcommit.operations.search.turn_dialogue",
    "forget_provider": "memcommit.operations.forget.provider",
    "forget_review": "memcommit.operations.forget.review",
    "granted_comparison_store": "memcommit.operations.compare.ledger.granted_store",
    "granted_source_update_application": "memcommit.operations.update.granted_source_application",
    "granted_update_application": "memcommit.operations.update.granted_application",
    "ground": "memcommit.operations.ground.model",
    "ground_context_catalog": "memcommit.operations.ground.context_catalog",
    "ground_dialogue": "memcommit.operations.ground.dialogue",
    "ground_distill": "memcommit.operations.ground.distill",
    "ground_elaborate": "memcommit.operations.ground.elaborate",
    "ground_turn_dialogue": "memcommit.operations.ground.turn_dialogue",
    "ground_workspace": "memcommit.operations.ground.workspace_model",
    "ground_workspace_application": "memcommit.operations.ground.workspace_application",
    "ground_workspace_draft": "memcommit.operations.ground.workspace_draft",
    "ground_workspace_draft_store": "memcommit.operations.ground.workspace_draft_store",
    "ground_workspace_fit": "memcommit.operations.ground.workspace_fit",
    "ground_workspace_history": "memcommit.operations.ground.workspace_history",
    "ground_workspace_projection": "memcommit.operations.ground.workspace_projection",
    "ground_workspace_runtime": "memcommit.operations.ground.workspace_runtime",
    "history_search": "memcommit.operations.log.search",
    "meld": "memcommit.operations.meld.model",
    "meld_choice_branches": "memcommit.operations.meld.choice_branches",
    "meld_provider": "memcommit.operations.meld.provider",
    "meld_resolution_adapter": "memcommit.operations.meld.resolution_adapter",
    "meld_resolution_cache": "memcommit.operations.meld.resolution_cache",
    "merge_planning": "memcommit.operations.merge.planning",
    "merge_tree": "memcommit.operations.merge.tree",
    "merge_tree_persistence": "memcommit.operations.merge.tree_persistence",
    "ordinary_query_answer": "memcommit.operations.query.answer",
    "context_rationale": "memcommit.operations.rationale.context",
    "rationale": "memcommit.operations.rationale.model",
    "rationale_cache": "memcommit.operations.rationale.cache",
    "rationale_rules": "memcommit.operations.rationale.rules",
    "rationale_scope": "memcommit.operations.rationale.scope",
    "rationale_semantic": "memcommit.operations.rationale.semantic",
    "reference_provenance": "memcommit.operations.reference.provenance",
    "resolve_rules": "memcommit.operations.resolve.rules",
    "resolve_semantic": "memcommit.operations.resolve.semantic",
    "resolve_targeting": "memcommit.operations.resolve.targeting",
    "resource_import": "memcommit.operations.resource_import.model",
    "review": "memcommit.operations.review.model",
    "review_report_adapters": "memcommit.operations.review.report_adapters",
    "search": "memcommit.operations.search.model",
    "search_artifacts": "memcommit.operations.search.artifacts",
    "semantic_add_runtime": "memcommit.operations.add.semantic_runtime",
    "share": "memcommit.operations.share.model",
    "summarize": "memcommit.operations.summarize.model",
    "update": "memcommit.operations.update.model",
    "update_application_flow": "memcommit.operations.update.application_flow",
    "update_endpoints": "memcommit.operations.update.endpoints",
    "update_receipt_store": "memcommit.operations.update.receipt_store",
    "update_resolution_adapter": "memcommit.operations.update.resolution_adapter",
}


CONCEPT_TARGETS = {
    "_architecture_catalog": "memcommit.architecture.catalog",
    "ambiguity_pipeline": "memcommit.semantic.classification.ambiguity",
    "application_flow": "memcommit.application.flow",
    "application_review_policy": "memcommit.application.review_policy",
    "applied_checkpoint_review": "memcommit.retained_history.applied_review",
    "checkpoint_catalog": "memcommit.retained_history.checkpoint_catalog",
    "checkpoint_frames": "memcommit.retained_history.checkpoint_frames",
    "checkpoint_migration": "memcommit.retained_history.checkpoint_migration",
    "clipboard": "memcommit.infrastructure.clipboard",
    "command_attempts": "memcommit.infrastructure.command_ledger.attempts",
    "command_history": "memcommit.retained_history.command_history",
    "config": "memcommit.infrastructure.config",
    "console_invocation": "memcommit.interfaces.cli.invocation",
    "context_catalog": "memcommit.context_targeting.context_catalog",
    "context_history": "memcommit.retained_history.context_history",
    "context_lifecycle": "memcommit.retained_history.context_lifecycle",
    "context_naming": "memcommit.context_targeting.naming",
    "context_snapshot": "memcommit.retained_history.context_snapshot",
    "current_context_navigation": "memcommit.context_targeting.navigation",
    "derived_policy": "memcommit.authority.derived_policy",
    "direct_item_duplicates": "memcommit.reviewing.direct_item_duplicates",
    "distill_elaborate_reference": "memcommit.semantic.generative_reduction_reference",
    "duplicate_pipeline": "memcommit.semantic.classification.duplicates",
    "exact_command_review": "memcommit.application.exact_command_review",
    "findings": "memcommit.reviewing.quality.findings",
    "flow_placeholder": "memcommit.interfaces.presentation.flow_placeholder",
    "goal_focus": "memcommit.semantic.goal_focus",
    "goal_focus_runtime": "memcommit.semantic.goal_focus_runtime",
    "granted_provenance": "memcommit.retained_history.granted_provenance",
    "history": "memcommit.retained_history.reconstruction",
    "history_display": "memcommit.retained_history.display",
    "interactive_command": "memcommit.application.interactive_command",
    "interactive_command_review": "memcommit.application.interactive_command_review",
    "memory_diff": "memcommit.reviewing.memory_diff",
    "memory_lineage": "memcommit.retained_history.memory_lineage",
    "name_suggestions": "memcommit.context_targeting.name_suggestions",
    "operation_gate_pipeline": "memcommit.semantic.classification.gates",
    "profile_config": "memcommit.operations.profile.config",
    "profiles": "memcommit.operations.profile.model",
    "provenance": "memcommit.retained_history.provenance",
    "provider_types": "memcommit.infrastructure.providers.types",
    "quality_audit": "memcommit.reviewing.quality.audit",
    "quality_audit_store": "memcommit.reviewing.quality.audit_store",
    "quality_find_report": "memcommit.reviewing.quality.report",
    "quality_find_workbench": "memcommit.reviewing.quality.workbench",
    "quality_finding_handoff": "memcommit.reviewing.quality.handoff",
    "query_provider": "memcommit.infrastructure.providers.subscription",
    "read_report": "memcommit.reviewing.read_report",
    "read_report_recents": "memcommit.reviewing.read_report_recents",
    "redundancy_scope": "memcommit.reviewing.quality.redundancy_scope",
    "resolution_workbench": "memcommit.resolution.workbench",
    "result_workbench": "memcommit.reviewing.result_workbench",
    "selective_curation": "memcommit.semantic.selective_curation",
    "semantic_disclosure": "memcommit.semantic.disclosure",
    "semantic_prompt_policy": "memcommit.semantic.prompt_policy",
    "semantic_provider": "memcommit.infrastructure.providers.semantic",
    "semantic_redundancy_evidence": "memcommit.semantic.redundancy_evidence",
    "session_workbench_navigation": "memcommit.reviewing.session_navigation",
    "storage_permissions": "memcommit.authority.storage_permissions",
    "study_action_log": "memcommit.infrastructure.command_ledger.study_actions",
    "study_operation_policy": "memcommit.authority.study_operation_policy",
    "temporal_history": "memcommit.retained_history.temporal",
    "uid_locator": "memcommit.context_targeting.uid_locator",
    "understanding": "memcommit.semantic.understanding",
    "write_protection": "memcommit.authority.write_protection",
}


def _module_target_path(module: str) -> str:
    return module.replace(".", "/") + ".py"


def _compatibility_target(source: str, *, stem: str) -> str | None:
    override = COMPATIBILITY_TARGET_OVERRIDES.get(stem)
    if override is not None:
        return override
    tree = ast.parse(source)
    bindings: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                bindings[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                bindings[alias.asname or alias.name] = (
                    f"{node.module}.{alias.name}"
                )
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
            return bindings.get(node.value.id)
    return None


def _is_compatibility(source: str) -> bool:
    doc = ast.get_docstring(ast.parse(source)) or ""
    first_line = doc.splitlines()[0] if doc.splitlines() else ""
    return "Compatibility" in first_line or (
        "sys.modules[__name__]" in source
    )


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
            action = "relocate"
            reason = "implementation is named for and consumed by one operation family"
        elif stem in CONCEPT_TARGETS:
            role = "shared-concept-implementation"
            target = CONCEPT_TARGETS[stem]
            action = "relocate"
            reason = "implementation belongs to a reusable named concept"
        elif stem in ROOT_BOUNDARIES:
            role = "root-boundary"
            target = module
            action = "retain"
            reason = ROOT_BOUNDARIES[stem]
        elif _is_compatibility(source):
            role = "compatibility-facade"
            target = _compatibility_target(source, stem=stem)
            action = "centralize-alias"
            reason = "preserve the old import through one compatibility registry"
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
        if entry["role"] == "compatibility-facade"
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
        if entry["action"] == "relocate"
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
            "facades without changing operation behavior or historical imports."
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
                target=entry["canonical_target"] or "multiple canonical modules",
                importers=entry["inbound_package_importers"],
            )
        )
    lines.append("")
    return "\n".join(lines)


def render_legacy_alias_module(plan: dict[str, object]) -> str:
    modules = plan["modules"]
    assert isinstance(modules, list)
    aliases = []
    for entry in modules:
        assert isinstance(entry, dict)
        if entry["role"] == "root-boundary":
            continue
        target = entry["canonical_target"]
        if not isinstance(target, str) or not target:
            raise RuntimeError(f"Legacy alias target is missing: {entry['module']}")
        aliases.append((str(entry["module"]), target))
    if len(aliases) != 242:
        raise RuntimeError(f"Expected 242 legacy aliases, found {len(aliases)}")
    lines = [
        '"""Generated legacy root-submodule aliases; do not edit directly."""',
        "",
        "from __future__ import annotations",
        "",
        "",
        "LEGACY_SUBMODULE_ALIASES = {",
    ]
    for legacy, canonical in sorted(aliases):
        lines.append(f"    {legacy!r}: {canonical!r},")
    lines.extend(["}", ""])
    return "\n".join(lines)


def _plan_aliases(plan: dict[str, object]) -> dict[str, str]:
    modules = plan["modules"]
    assert isinstance(modules, list)
    aliases = {}
    for entry in modules:
        assert isinstance(entry, dict)
        if entry["role"] == "root-boundary":
            continue
        target = entry["canonical_target"]
        if not isinstance(target, str) or not target:
            raise RuntimeError(f"Legacy alias target is missing: {entry['module']}")
        aliases[str(entry["module"])] = target
    return aliases


def verify_current_layout(plan: dict[str, object]) -> None:
    aliases = _plan_aliases(plan)
    failures = []
    for legacy, target in sorted(aliases.items()):
        stem = legacy.removeprefix("memcommit.")
        root_path = PACKAGE / f"{stem}.py"
        target_path = REPOSITORY / _module_target_path(target)
        target_package = target_path.with_suffix("") / "__init__.py"
        if not target_path.is_file() and not target_package.is_file():
            failures.append(f"missing canonical target: {target_path}")
        if root_path.exists():
            failures.append(f"physical compatibility facade remains: {root_path}")

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
                if module in aliases:
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
        "root module layout is physical-owner only: "
        f"{len(aliases)} centralized aliases, "
        f"{len(ROOT_BOUNDARIES)} root implementations"
    )


def verify_isolated_imports(plan: dict[str, object]) -> None:
    """Check both import orders without an earlier module masking a cycle."""

    aliases = _plan_aliases(plan)
    failures = []
    for legacy, target in sorted(aliases.items()):
        for order in ("canonical-first", "legacy-first"):
            first, second = (
                (target, legacy) if order == "canonical-first" else (legacy, target)
            )
            code = (
                "from importlib import import_module; "
                f"first=import_module({first!r}); second=import_module({second!r}); "
                "assert first is second; "
                f"assert first.__spec__.name == {target!r}"
            )
            try:
                result = subprocess.run(
                    [sys.executable, "-c", code],
                    cwd=REPOSITORY,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except subprocess.TimeoutExpired:
                failures.append(f"{order} import timed out: {legacy} -> {target}")
                continue
            if result.returncode:
                detail = result.stderr.strip() or result.stdout.strip()
                failures.append(
                    f"{order} import failed: {legacy} -> {target}\n{detail}"
                )
    if failures:
        raise SystemExit("\n".join(failures))
    print(
        "isolated compatibility imports are canonical in both orders: "
        f"{len(aliases)} modules"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    plan = build_plan()
    rendered_json = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    rendered_markdown = render_markdown(plan)
    rendered_aliases = render_legacy_alias_module(plan)
    if args.check:
        if (
            not OUTPUT_JSON.exists()
            or not OUTPUT_MARKDOWN.exists()
            or not LEGACY_ALIAS_MODULE.exists()
        ):
            raise SystemExit("root module relocation plan is missing")
        if OUTPUT_JSON.read_text(encoding="utf-8") != rendered_json:
            raise SystemExit("root module relocation JSON is stale")
        if OUTPUT_MARKDOWN.read_text(encoding="utf-8") != rendered_markdown:
            raise SystemExit("root module relocation Markdown is stale")
        if LEGACY_ALIAS_MODULE.read_text(encoding="utf-8") != rendered_aliases:
            raise SystemExit("legacy submodule alias map is stale")
        verify_current_layout(plan)
        verify_isolated_imports(plan)
        print("root module relocation plan is current")
        return 0
    OUTPUT_JSON.write_text(rendered_json, encoding="utf-8")
    OUTPUT_MARKDOWN.write_text(rendered_markdown, encoding="utf-8")
    LEGACY_ALIAS_MODULE.parent.mkdir(parents=True, exist_ok=True)
    LEGACY_ALIAS_MODULE.write_text(rendered_aliases, encoding="utf-8")
    print(f"wrote {len(plan['modules'])} root module records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
