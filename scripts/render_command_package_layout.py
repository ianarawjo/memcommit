"""Render and verify the flat-command to command-package relocation plan."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import subprocess
import sys


REPOSITORY = Path(__file__).resolve().parents[1]
COMMANDS = (
    REPOSITORY / "src" / "memcommit" / "adapters" / "console" / "commands"
)
FORMER_COMMANDS = REPOSITORY / "src" / "memcommit" / "commands"
LEGACY_NAMESPACE = "memcommit.commands"
CANONICAL_NAMESPACE = "memcommit.adapters.console.commands"
OUTPUT_JSON = (
    REPOSITORY / "agent-records" / "docs" / "command-package-layout-plan.json"
)
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
    "consolidate": ("cmd",),
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
    "semantic_eval": ("eval_app",),
    "sever": ("cmd",),
    "share": ("cmd",),
    "shell_init": ("cmd",),
    "show": ("cmd",),
    "status": ("cmd",),
    "summarize": ("cmd",),
    "switch": ("cmd",),
    "trace": ("cmd",),
    "translate": ("cmd",),
    "undo": ("cmd",),
    "update": ("cmd",),
    "write_protection": ("lock_app", "unlock_app"),
}


OWNED_SUPPORT_TARGETS = {
    "atomize_grounding": "atomize.grounding",
    "atomize_render": "atomize.render",
    "atomize_sessions": "atomize.sessions",
    "atomize_workbench_shell": "atomize.workbench.screen",
    "audit_sessions": "audit.sessions",
    "branch_dialog": "branch.setup",
    "compare_sessions": "compare.sessions",
    "compare_setup": "compare.setup",
    "compare_targeting": "compare.targeting",
    "comparison_execution": "compare.execution",
    "conflict_resolve_handoff": "find_conflicts.resolve_handoff",
    "duplicate_dedup_handoff": "find_duplicates.dedup_handoff",
    "find_chat_shell": "find.chat_shell",
    "find_materialization": "find.materialization",
    "find_query_provider_policy": "find.provider_policy",
    "find_search_workbench": "find.search_workbench",
    "forget_setup_workbench": "forget.setup_workbench",
    "ground_named_shell": "ground.named_shell",
    "ground_session_picker": "ground.session_picker",
    "ground_shell": "ground.shell",
    "ground_workspace_picker": "ground.workspace_picker",
    "impact_catalog": "impact.catalog",
    "impact_process_local": "impact.process_local",
    "impact_registry": "impact.registry",
    "impact_sessions": "impact.sessions",
    "import_workbench": "import_profile.workbench",
    "meld_sessions": "meld.sessions",
    "meld_setup": "meld.setup",
    "meld_shell": "meld.shell",
    "meld_target_picker": "meld.target_picker",
    "ordinary_query_provider_policy": "query.provider_policy",
    "profile_group": "profile.group",
    "profile_picker": "profile.picker",
    "query_workbench": "query.workbench",
    "review_report": "review.report",
    "review_resolution_shell": "review.resolution_shell",
    "review_sessions": "review.sessions",
    "search_result_present": "find.result_present",
    "sever_sessions": "sever.sessions",
    "sever_setup_shell": "sever.setup_shell",
    "share_flow": "share.flow",
    "share_viewer": "share.viewer",
    "study_name_dialog": "init_study.name_dialog",
    "context_trace_projection": "trace.context_projection",
    "trace_projection": "trace.projection",
    "update_checkpoint_history": "update.checkpoint_history",
    "update_render": "update.render",
    "update_setup": "update.setup",
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
    "endpoint_setup_flows",
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
    "session_endpoint_setup",
    "session_help",
    "session_picker",
    "tui_primitives",
    "tui_table",
}


def _target_path(module: str) -> Path:
    return REPOSITORY / "src" / (module.replace(".", "/") + ".py")


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
        entries.append(
            {
                "legacy_module": f"{LEGACY_NAMESPACE}.{stem}",
                "canonical_module": f"{CANONICAL_NAMESPACE}.{stem}.command",
                "owner": stem,
                "role": "command-entry",
                "public_exports": list(exports),
            }
        )
    for stem, target in sorted(OWNED_SUPPORT_TARGETS.items()):
        owner = target.split(".", 1)[0]
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
        entries.append(
            {
                "legacy_module": f"{LEGACY_NAMESPACE}.{stem}",
                "canonical_module": f"{CANONICAL_NAMESPACE}.shared.{stem}",
                "owner": "shared",
                "role": "shared-command-mechanism",
                "public_exports": [],
            }
        )
    legacy = [str(entry["legacy_module"]).rsplit(".", 1)[-1] for entry in entries]
    if len(entries) != 153 or len(set(legacy)) != 153:
        raise RuntimeError("command layout must classify 153 unique baseline modules")
    baseline = _baseline_modules()
    if set(legacy) != baseline:
        missing = sorted(baseline - set(legacy))
        extra = sorted(set(legacy) - baseline)
        raise RuntimeError(f"command layout mismatch: missing={missing}, extra={extra}")
    return {
        "schema_version": 1,
        "purpose": (
            "Give every CLI entry a predictable package and place multi-file "
            "support beside its owning entry under the explicit console adapter "
            "without changing command behavior."
        ),
        "baseline_commit": BASELINE_COMMIT,
        "baseline_module_count": len(entries),
        "entry_package_count": len(ENTRY_EXPORTS),
        "shared_module_count": len(SHARED_MODULES),
        "modules": sorted(entries, key=lambda entry: str(entry["legacy_module"])),
    }


def render_markdown(plan: dict[str, object]) -> str:
    lines = [
        "# Command package layout plan",
        "",
        "This is the exact path-only classification of the formerly flat",
        "`memcommit.commands` modules. Their canonical implementations now live under",
        "`memcommit.adapters.console.commands`; route closure remains solely in the",
        "operation evidence ledger.",
        "",
        f"- Baseline modules: {plan['baseline_module_count']}",
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
                if module in removed:
                    failures.append(
                        f"internal legacy command import: {path}:{node.lineno}:{module}"
                    )
    if failures:
        raise SystemExit("\n".join(failures))
    print(
        "command package layout is canonical: "
        f"{len(ENTRY_EXPORTS)} entry packages, {len(removed)} removed command paths, "
        f"{len(SHARED_MODULES)} shared mechanisms"
    )


def verify_removed_imports(plan: dict[str, object]) -> None:
    """Prove that runtime hooks do not restore the former command package."""

    removed = [LEGACY_NAMESPACE, *sorted(_removed_command_modules(plan))]
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
            package_init = COMMANDS / stem / "__init__.py"
            if package_init.read_text(encoding="utf-8") != render_entry_init(
                stem, exports
            ):
                raise SystemExit(f"stale command package boundary: {package_init}")
        verify_layout(plan)
        verify_removed_imports(plan)
        print("command package layout plan is current")
        return 0
    OUTPUT_JSON.write_text(rendered_json, encoding="utf-8")
    OUTPUT_MARKDOWN.write_text(rendered_markdown, encoding="utf-8")
    for stem, exports in ENTRY_EXPORTS.items():
        (COMMANDS / stem / "__init__.py").write_text(
            render_entry_init(stem, exports),
            encoding="utf-8",
        )
    print(f"wrote {len(plan['modules'])} command module records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
