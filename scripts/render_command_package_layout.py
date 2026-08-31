"""Render and verify the flat-command to command-package relocation plan."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import subprocess
import sys


REPOSITORY = Path(__file__).resolve().parents[1]
CONSOLE = REPOSITORY / "src" / "memcommit" / "adapters" / "console"
COMMANDS = CONSOLE / "commands"
FORMER_COMMANDS = REPOSITORY / "src" / "memcommit" / "commands"
LEGACY_NAMESPACE = "memcommit.commands"
CANONICAL_NAMESPACE = "memcommit.adapters.console.commands"
COORDINATION_NAMESPACE = "memcommit.adapters.console.coordination"
OUTPUT_JSON = REPOSITORY / "agent-records" / "docs" / "command-package-layout-plan.json"
OUTPUT_MARKDOWN = (
    REPOSITORY / "agent-records" / "docs" / "command-package-layout-plan.md"
)
BASELINE_COMMIT = "f8c54a56"


ENTRY_EXPORTS = {
    "add": ("cmd",),
    "atomize": ("cmd",),
    "audit": ("cmd",),
    "branch": ("cmd",),
    "check_conformance": ("cmd",),
    "checkpoint": ("cmd",),
    "chunk": ("cmd",),
    "clear": ("cmd",),
    "compare": ("cmd",),
    "config": ("app",),
    "contexts": ("cmd",),
    "dedun": ("cmd",),
    "dedup": ("cmd",),
    "delete": ("cmd",),
    "dev": ("app",),
    "diff": ("cmd",),
    "distill": ("cmd",),
    "edit": ("cmd",),
    "elaborate": ("cmd",),
    "find": ("cmd",),
    "find_ambiguities": ("cmd",),
    "find_conflicts": ("cmd",),
    "find_duplicates": ("cmd",),
    "find_exact_duplicates": ("cmd",),
    "fit": ("cmd",),
    "forget": ("cmd",),
    "ground": ("cmd",),
    "help_inventory": ("cmd",),
    "impact": ("app", "cmd"),
    "import_profile": ("cmd",),
    "init": ("cmd",),
    "init_study": ("cmd",),
    "list_memories": ("cmd",),
    "literal_find": ("cmd",),
    "log": ("cmd",),
    "meld": ("cmd",),
    "merge": ("cmd",),
    "profile": ("app",),
    "provider": ("app",),
    "pwd": ("cmd",),
    "query": ("cmd",),
    "rationale": ("cmd",),
    "redo": ("cmd",),
    "reference": ("cmd",),
    "remove": ("cmd",),
    "rename": ("cmd",),
    "replace": ("cmd",),
    "resolve": ("cmd",),
    "revert": ("cmd",),
    "review": ("cmd",),
    "semantic_eval": ("app",),
    "sever": ("cmd",),
    "share": ("cmd",),
    "show": ("cmd",),
    "status": ("cmd",),
    "summarize": ("cmd",),
    "switch": ("cmd",),
    "trace": ("cmd",),
    "translate": ("cmd",),
    "undo": ("cmd",),
    "update": ("cmd",),
}


ENTRY_TARGETS = {
    # The baseline module keeps the former operation name; only its canonical
    # destination advances to the renamed command package.
    "elaborate": "makemore",
    # The former semantic Find entry became Search, while provider-free
    # Literal Find became the canonical Find command.
    "find": "search",
    # The historical internal names were inverted relative to the public CLI:
    # find_duplicates ran semantic redundancy analysis, while
    # find_exact_duplicates backed the provider-free find-duplicates route.
    "find_duplicates": "find_redundancies",
    "find_exact_duplicates": "find_duplicates",
    "help_inventory": "help",
    "import_profile": "resource_import",
    "list_memories": "list",
    "literal_find": "find",
    "semantic_eval": "eval",
}


# Public command names and historical baseline stems are intentionally kept
# separate from physical package ownership. The catalog family is the stable
# first path component for classified operations on the console side.
COMMAND_PACKAGE_TARGETS = {
    "status": "browse_navigate.status",
    "pwd": "browse_navigate.pwd",
    "contexts": "browse_navigate.contexts",
    "list": "browse_navigate.list",
    "show": "browse_navigate.show",
    "switch": "browse_navigate.switch",
    "checkout": "browse_navigate.checkout",
    "rename": "browse_navigate.rename",
    "init": "create_copy_connect.init",
    "add": "create_copy_connect.add",
    "copy": "create_copy_connect.copy",
    "branch": "create_copy_connect.branch",
    "resource_import": "create_copy_connect.resource_import",
    "reference": "create_copy_connect.reference",
    "embed": "create_copy_connect.embed",
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
    "remove": "direct_changes.remove",
    "update": "semantic_updates.foundation.update",
    "atomize": "semantic_updates.derive.atomize",
    "distill": "semantic_updates.derive.distill",
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
    "check_conformance": "quality_resolution.validate.check_conformance",
    "impact": "operation_lifecycle.impact",
    "review": "operation_lifecycle.review",
    "ground": "ground_workbench.ground",
    "log": "history_recovery.inspection.log",
    "diff": "history_recovery.inspection.diff",
    "trace": "history_recovery.inspection.trace",
    "rationale": "history_recovery.inspection.rationale",
    "checkpoint": "history_recovery.recovery.checkpoint",
    "undo": "history_recovery.recovery.undo",
    "redo": "history_recovery.recovery.redo",
    "revert": "history_recovery.recovery.revert",
    "profile": "profiles.profile",
    "share": "sharing_protection.share",
    "lock": "sharing_protection.lock",
    "unlock": "sharing_protection.unlock",
    "help": "system_study_tools.help",
    "provider": "system_study_tools.provider",
    "config": "system_study_tools.config",
    "init_study": "system_study_tools.init_study",
    "eval": "system_study_tools.eval",
}


ENTRY_MODULE_OVERRIDES = {
    # Dev is a hidden diagnostic surface, not a catalog-classified operation.
    "dev": "memcommit.adapters.console.diagnostics.dev",
}


def _entry_package_target(stem: str) -> str:
    command = ENTRY_TARGETS.get(stem, stem)
    return COMMAND_PACKAGE_TARGETS.get(command, command)


def _entry_package_module(stem: str) -> str:
    override = ENTRY_MODULE_OVERRIDES.get(stem)
    if override is not None:
        return override
    return f"{CANONICAL_NAMESPACE}.{_entry_package_target(stem)}"


def _owned_support_target(target: str) -> str:
    owner, separator, remainder = target.partition(".")
    physical_owner = COMMAND_PACKAGE_TARGETS.get(owner, owner)
    return physical_owner + (separator + remainder if separator else "")


RETIRED_BASELINE_MODULES = {
    "consolidate": (
        "retired with Dedun's obsolete exact-review console replay"
    ),
    "duplicate_dedup_handoff": (
        "retired when Dedun adopted deterministic immediate Apply"
    ),
    "atomize_grounding": (
        "retired when Atomize findings became read-only operation evidence"
    ),
    "atomize_render": (
        "retired after Atomize analysis presentation converged on the workbench screen"
    ),
    "atomize_workbench_shell": (
        "retired when Impact and Review took ownership of Atomize presentation"
    ),
    "endpoint_setup_flows": (
        "retired after every remaining operation acquired a command-owned setup adapter"
    ),
    "find_chat_shell": (
        "retired with the uncalled conversational Search prototype"
    ),
    "find_materialization": (
        "retired when selected-result saving moved to the shared application capability"
    ),
    "ground_named_shell": (
        "retired with the unpublished named Ground session interface"
    ),
    "ground_session_picker": (
        "retired when Ground session discovery moved into its open workflow"
    ),
    "meld_target_picker": (
        "retired after Meld adopted the shared endpoint setup for Result selection"
    ),
    "shell_init": (
        "retired after Help and init-study took ownership of their distinct "
        "shell responsibilities"
    ),
    "session_endpoint_setup": (
        "retired with the obsolete multi-stage Atomize setup flow"
    ),
    "write_protection": (
        "split into the independently discoverable lock and unlock command packages"
    ),
}


OWNED_SUPPORT_TARGETS = {
    "atomize_sessions": "atomize.records",
    "audit_sessions": "audit.session_catalog",
    "branch_dialog": "branch.endpoint_setup",
    "compare_sessions": "compare.sessions",
    "compare_setup": "compare.endpoint_setup",
    "compare_targeting": "compare.targeting",
    "comparison_execution": "compare.execution",
    "conflict_resolve_handoff": "resolve.finding_handoff",
    "find_search_workbench": "search.search_workbench",
    "forget_setup_workbench": "forget.setup",
    "ground_shell": "ground.shell",
    "ground_workspace_picker": "ground.workspace.catalog",
    "impact_catalog": "impact.catalog",
    "impact_process_local": "impact.process_local",
    "impact_registry": "impact.registry",
    "impact_sessions": "impact.sessions",
    "import_workbench": "resource_import.workbench",
    "meld_sessions": "meld.sessions",
    "meld_setup": "meld.endpoint_setup",
    "meld_shell": "meld.command",
    "ordinary_query_provider_policy": "query.provider_policy",
    "profile_group": "profile.group",
    "profile_picker": "profile.picker",
    "query_workbench": "query.workbench",
    "review_report": "review.report",
    "review_resolution_shell": "review.resolution_shell",
    "review_sessions": "review.sessions",
    "search_result_present": "search.result_present",
    "sever_sessions": "sever.sessions",
    "sever_setup_shell": "sever.endpoint_setup",
    "share_flow": "share.flow",
    "share_viewer": "share.viewer",
    "study_name_dialog": "init_study.name_dialog",
    "context_trace_projection": "trace.context_projection",
    "trace_projection": "trace.projection",
    "update_render": "update.render",
    "update_setup": "update.endpoint_setup",
}


INFRASTRUCTURE_SUPPORT_TARGETS = {
    "find_query_provider_policy": "memcommit.providers.operation_connections",
}


SPECIAL_SUPPORT_TARGETS = {
    "update_checkpoint_history": (
        "memcommit.adapters.console.terminal.components.history.update_checkpoint",
        "terminal",
        "shared-terminal-component",
    ),
}


MODULE_TARGET_PATH_OVERRIDES = {
    "memcommit.adapters.console.commands.ground_workbench.ground.shell": (
        "src/memcommit/adapters/console/commands/ground_workbench/ground/shell/__init__.py"
    ),
    "memcommit.adapters.console.commands.semantic_updates.curate_integrate.meld.command": (
        "src/memcommit/adapters/console/commands/semantic_updates/curate_integrate/meld/command.py"
    ),
}


SHARED_MODULES = {
    "background_turn",
    "batch_input",
    "checkpoint_diff",
    "command_group",
    "command_progress",
    "command_wait",
    "context_operand",
    "context_picker",
    "context_reach_dialog",
    "diff_browser",
    "direct_item_placement",
    "exact_command_review",
    "exact_command_review_shell",
    "exact_name_dialog",
    "findings_render",
    "flat_selection_dialog",
    "history_location_picker",
    "history_picker",
    "history_present",
    "history_target",
    "horizontal_choice",
    "memory_history",
    "memory_picker",
    "memory_report_recents",
    "operation_launcher_location",
    "paste_input",
    "quality_find_workbench",
    "readable_context_catalog",
    "resolution_workbench_shell",
    "restoration_present",
    "root_group",
    "save_location_control",
    "save_location_review",
    "semantic_clipboard",
    "semantic_detail_renderer",
    "session_help",
    "session_picker",
    "tui_primitives",
    "tui_table",
}


SHARED_MODULE_TARGETS = {
    "batch_input": "batch_input_source",
    "findings_render": "quality_find_render",
}


RELOCATED_SHARED_TARGETS = {
    "background_turn": "memcommit.adapters.console.terminal.components.background_turn",
    "checkpoint_diff": "memcommit.adapters.console.terminal.components.history.checkpoint_diff",
    "command_progress": "memcommit.adapters.console.terminal.components.progress",
    "command_wait": "memcommit.adapters.console.terminal.components.command_wait",
    "context_picker": "memcommit.adapters.console.terminal.components.context_picker",
    "context_reach_dialog": "memcommit.adapters.console.terminal.components.context_reach_dialog",
    "diff_browser": "memcommit.adapters.console.terminal.components.history.browser",
    "direct_item_placement": "memcommit.adapters.console.terminal.components.direct_item_placement",
    "exact_command_review": "memcommit.adapters.console.terminal.components.command_editor",
    "exact_command_review_shell": "memcommit.adapters.console.terminal.components.command_editor.approval",
    "exact_name_dialog": "memcommit.adapters.console.terminal.components.exact_name_dialog",
    "findings_render": "memcommit.adapters.console.terminal.components.quality_find.rendering",
    "flat_selection_dialog": "memcommit.adapters.console.terminal.components.flat_selection_dialog",
    "history_location_picker": "memcommit.adapters.console.terminal.components.checkpoint_location",
    "history_picker": "memcommit.adapters.console.terminal.components.history.picker",
    "history_present": "memcommit.adapters.console.terminal.components.history.presentation",
    "horizontal_choice": "memcommit.adapters.console.terminal.components.horizontal_choice",
    "memory_picker": "memcommit.adapters.console.terminal.components.memory_report_picker",
    "operation_launcher_location": "memcommit.adapters.console.terminal.components.operation_launcher.location",
    "paste_input": "memcommit.adapters.console.terminal.components.paste_input",
    "quality_find_workbench": "memcommit.adapters.console.terminal.components.quality_find.workbench",
    "readable_context_catalog": "memcommit.application.capabilities.authority.readable_contexts",
    "resolution_workbench_shell": "memcommit.adapters.console.terminal.components.resolution.session_shell",
    "restoration_present": "memcommit.adapters.console.terminal.components.restoration_receipt",
    "save_location_control": "memcommit.adapters.console.terminal.components.save_location",
    "save_location_review": "memcommit.adapters.console.terminal.components.save_location_review",
    "semantic_clipboard": "memcommit.adapters.console.terminal.components.plain_text_clipboard",
    "semantic_detail_renderer": "memcommit.adapters.console.terminal.components.semantic_viewer.detail",
    "session_help": "memcommit.adapters.console.terminal.components.session_help",
    "session_picker": "memcommit.adapters.console.terminal.components.operation_launcher.session",
    "tui_primitives": "memcommit.adapters.console.terminal.components.primitives",
    "tui_table": "memcommit.adapters.console.terminal.components.table",
}


def _target_path(module: str) -> Path:
    override = MODULE_TARGET_PATH_OVERRIDES.get(module)
    if override is not None:
        return REPOSITORY / override
    module_path = REPOSITORY / "src" / module.replace(".", "/")
    module_file = module_path.with_suffix(".py")
    if module_file.is_file():
        return module_file
    return module_path / "__init__.py"


def _baseline_modules() -> set[str]:
    result = subprocess.run(
        [
            "git",
            "ls-tree",
            "-r",
            "--name-only",
            BASELINE_COMMIT,
            "--",
            "memcommit/commands",
        ],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
        text=True,
    )
    return {
        Path(line).stem
        for line in result.stdout.splitlines()
        if Path(line).parent == Path("memcommit/commands")
        and line.endswith(".py")
        and Path(line).stem != "__init__"
    }


def build_plan() -> dict[str, object]:
    entries: list[dict[str, object]] = []
    for stem, exports in sorted(ENTRY_EXPORTS.items()):
        target = _entry_package_target(stem)
        package_module = _entry_package_module(stem)
        entries.append(
            {
                "legacy_module": f"{LEGACY_NAMESPACE}.{stem}",
                "canonical_module": f"{package_module}.command",
                "owner": package_module.removeprefix("memcommit.adapters.console."),
                "role": "command-entry",
                "public_exports": list(exports),
            }
        )
    for stem, target in sorted(INFRASTRUCTURE_SUPPORT_TARGETS.items()):
        entries.append(
            {
                "legacy_module": f"{LEGACY_NAMESPACE}.{stem}",
                "canonical_module": target,
                "owner": "providers",
                "role": "infrastructure-support",
                "public_exports": [],
            }
        )
    for stem, (target, owner, role) in sorted(SPECIAL_SUPPORT_TARGETS.items()):
        entries.append(
            {
                "legacy_module": f"{LEGACY_NAMESPACE}.{stem}",
                "canonical_module": target,
                "owner": owner,
                "role": role,
                "public_exports": [],
            }
        )
    for stem, target in sorted(OWNED_SUPPORT_TARGETS.items()):
        target = _owned_support_target(target)
        owner = target.rsplit(".", 1)[0] if "." in target else target
        entries.append(
            {
                "legacy_module": f"{LEGACY_NAMESPACE}.{stem}",
                "canonical_module": f"{CANONICAL_NAMESPACE}.{target}",
                "owner": owner,
                "role": "command-owned-support",
                "public_exports": [],
            }
        )
    for stem in sorted(SHARED_MODULES):
        relocated = RELOCATED_SHARED_TARGETS.get(stem)
        target = SHARED_MODULE_TARGETS.get(stem, stem)
        entries.append(
            {
                "legacy_module": f"{LEGACY_NAMESPACE}.{stem}",
                "canonical_module": relocated or f"{COORDINATION_NAMESPACE}.{target}",
                "owner": (
                    "authority"
                    if stem == "readable_context_catalog"
                    else "terminal"
                    if relocated
                    else "coordination"
                ),
                "role": (
                    "shared-application-capability"
                    if stem == "readable_context_catalog"
                    else "shared-terminal-component"
                    if relocated
                    else "shared-command-mechanism"
                ),
                "public_exports": [],
            }
        )
    legacy = [str(entry["legacy_module"]).rsplit(".", 1)[-1] for entry in entries]
    baseline = _baseline_modules()
    expected_active = len(baseline) - len(RETIRED_BASELINE_MODULES)
    if len(entries) != expected_active or len(set(legacy)) != expected_active:
        raise RuntimeError(
            f"command layout must map {expected_active} active baseline modules"
        )
    classified = set(legacy) | set(RETIRED_BASELINE_MODULES)
    if classified != baseline:
        missing = sorted(baseline - classified)
        extra = sorted(classified - baseline)
        raise RuntimeError(f"command layout mismatch: missing={missing}, extra={extra}")
    return {
        "schema_version": 1,
        "purpose": (
            "Give every CLI entry a predictable package and place multi-file "
            "support beside its owning entry while keeping multi-command console "
            "mechanics outside the command-entry tree, without changing behavior."
        ),
        "baseline_commit": BASELINE_COMMIT,
        "baseline_module_count": len(entries) + len(RETIRED_BASELINE_MODULES),
        "active_module_count": len(entries),
        "entry_package_count": len(ENTRY_EXPORTS),
        "shared_module_count": sum(
            str(entry["role"]).startswith("shared-") for entry in entries
        ),
        "modules": sorted(entries, key=lambda entry: str(entry["legacy_module"])),
        "retired_legacy_modules": [
            f"{LEGACY_NAMESPACE}.{stem}" for stem in sorted(RETIRED_BASELINE_MODULES)
        ],
    }


def render_markdown(plan: dict[str, object]) -> str:
    lines = [
        "# Command package layout plan",
        "",
        "This is the exact path-only classification of the formerly flat",
        "`memcommit.commands` modules. Their canonical implementations now live under",
        "`memcommit.adapters.console.commands` for command-owned code and",
        "`memcommit.adapters.console.coordination` for nonvisual multi-command mechanics, and",
        "`memcommit.adapters.console.terminal.components` for terminal-bound components;",
        "route closure remains solely in the operation evidence ledger.",
        "",
        f"- Baseline modules: {plan['baseline_module_count']}",
        f"- Active canonical mappings: {plan['active_module_count']}",
        f"- Retired baseline modules: {len(plan['retired_legacy_modules'])}",
        f"- Command entry packages: {plan['entry_package_count']}",
        f"- Shared command mechanisms: {plan['shared_module_count']}",
        "",
        "| Legacy module | Canonical module | Role | Owner |",
        "| --- | --- | --- | --- |",
    ]
    modules = plan["modules"]
    assert isinstance(modules, list)
    for entry in modules:
        assert isinstance(entry, dict)
        lines.append(
            f"| `{entry['legacy_module']}` | `{entry['canonical_module']}` | "
            f"{entry['role']} | `{entry['owner']}` |"
        )
    lines.append("")
    return "\n".join(lines)


def render_entry_init(stem: str, exports: tuple[str, ...]) -> str:
    rendered_exports = ", ".join(json.dumps(name) for name in exports)
    return "\n".join(
        [
            f'"""Lazy public CLI surface for the {stem} command package."""',
            "",
            "from memcommit.adapters.console.commands import _load_entrypoint_attribute",
            "",
            "",
            f"__all__ = [{rendered_exports}]",
            "",
            "",
            "def __getattr__(name: str):",
            "    return _load_entrypoint_attribute(__name__, __all__, name)",
            "",
        ]
    )


def _removed_command_modules(plan: dict[str, object]) -> dict[str, str]:
    modules = plan["modules"]
    assert isinstance(modules, list)
    return {
        str(entry["legacy_module"]): str(entry["canonical_module"])
        for entry in modules
        if isinstance(entry, dict)
    }


def verify_layout(plan: dict[str, object]) -> None:
    failures: list[str] = []
    if FORMER_COMMANDS.exists():
        failures.append(f"former command package remains: {FORMER_COMMANDS}")
    root_files = {path.name for path in COMMANDS.glob("*.py")}
    if root_files != {"__init__.py"}:
        failures.append(
            f"flat command files remain: {sorted(root_files - {'__init__.py'})}"
        )
    if (COMMANDS / "shared").exists():
        failures.append("shared console mechanics remain inside the command tree")
    modules = plan["modules"]
    assert isinstance(modules, list)
    for entry in modules:
        assert isinstance(entry, dict)
        target = _target_path(str(entry["canonical_module"]))
        if not target.is_file():
            failures.append(f"missing canonical command module: {target}")
        if entry["role"] == "command-entry":
            package_init = target.parent / "__init__.py"
            if not package_init.is_file():
                failures.append(f"missing command package boundary: {package_init}")
    removed = _removed_command_modules(plan)
    retired = {str(module) for module in plan.get("retired_legacy_modules", ())}
    for path in (REPOSITORY / "src" / "memcommit").rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as error:
            failures.append(f"cannot parse {path}: {error}")
            continue
        for node in ast.walk(tree):
            imported: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
            elif isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            for module in imported:
                if module in removed or module in retired:
                    failures.append(
                        f"internal legacy command import: {path}:{node.lineno}:{module}"
                    )
    if failures:
        raise SystemExit("\n".join(failures))
    print(
        "command package layout is canonical: "
        f"{len(ENTRY_EXPORTS)} entry packages, "
        f"{len(removed) + len(retired)} removed command paths, "
        f"{len(SHARED_MODULES)} shared console mechanisms"
    )


def verify_removed_imports(plan: dict[str, object]) -> None:
    """Prove that runtime hooks do not restore the former command package."""

    retired = [str(module) for module in plan.get("retired_legacy_modules", ())]
    removed = [
        LEGACY_NAMESPACE,
        *sorted(_removed_command_modules(plan)),
        *sorted(retired),
    ]
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
    print(f"former command imports are unavailable: {len(removed)} modules")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    plan = build_plan()
    rendered_json = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    rendered_markdown = render_markdown(plan)
    if args.check:
        expected = (
            (OUTPUT_JSON, rendered_json),
            (OUTPUT_MARKDOWN, rendered_markdown),
        )
        for path, rendered in expected:
            if not path.is_file() or path.read_text(encoding="utf-8") != rendered:
                raise SystemExit(f"stale command package layout artifact: {path}")
        for stem, exports in ENTRY_EXPORTS.items():
            target = _entry_package_target(stem)
            package_module = _entry_package_module(stem)
            package_init = _target_path(package_module + ".__init__")
            if package_init.read_text(encoding="utf-8") != render_entry_init(
                target, exports
            ):
                raise SystemExit(f"stale command package boundary: {package_init}")
        verify_layout(plan)
        verify_removed_imports(plan)
        print("command package layout plan is current")
        return 0
    OUTPUT_JSON.write_text(rendered_json, encoding="utf-8")
    OUTPUT_MARKDOWN.write_text(rendered_markdown, encoding="utf-8")
    for stem, exports in ENTRY_EXPORTS.items():
        target = _entry_package_target(stem)
        package_module = _entry_package_module(stem)
        _target_path(package_module + ".__init__").write_text(
            render_entry_init(target, exports),
            encoding="utf-8",
        )
    print(f"wrote {len(plan['modules'])} command module records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
