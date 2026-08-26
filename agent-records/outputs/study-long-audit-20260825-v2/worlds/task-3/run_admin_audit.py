#!/usr/bin/env python3
"""Run task-3 ADMIN by specializing the reviewed non-TUI admin harness.

The shared campaign protocol is intentionally identical across non-
representative worlds.  This adapter executes a frozen copy of that harness
logic with task-3 lane constants, then adds task-3-specific Share and
init-study postconditions.  It never invokes mem outside run_world_mem.py.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


HERE = Path(__file__).resolve().parent
REFERENCE = HERE.parent / "practice-source/run_admin_audit.py"


def main() -> None:
    source = REFERENCE.read_text(encoding="utf-8")
    # Load the reviewed common noninteractive protocol without recursively
    # entering its own main block.  __file__ points at this world so every
    # evidence artifact remains task-3-owned.
    source = source.replace(
        'if __name__ == "__main__":\n    main()\n',
        '',
    )
    source = source.replace('WORLD = "practice-source"', 'WORLD = "task-3"')
    source = source.replace('worlds/practice-source', 'worlds/task-3')
    source = source.replace(
        'admin-v2-practice-source-inactive',
        'admin-v2-task-3-inactive',
    )
    source = source.replace('admin-v2-practice-source-study', 'admin-v2-task-3-study')
    source = source.replace('admin-v2-practice-source-workers', 'admin-v2-task-3-workers')
    source = source.replace('admin/v2-practice-source', 'admin/v2-task-3')
    source = source.replace('admin-v2-practice-source-missing', 'admin-v2-task-3-missing')
    source = source.replace(
        'practice/admin-v2-missing-share-source',
        'task-3/local/admin-v2-missing-share-source',
    )
    source = source.replace(
        'practice/admin-v2-missing-branch-source',
        'task-3/local/admin-v2-missing-branch-source',
    )
    source = source.replace(
        'practice/admin-v2-missing-checkout',
        'task-3/local/admin-v2-missing-checkout',
    )
    namespace: dict[str, object] = {
        "__name__": "task3_admin_protocol",
        "__file__": str(Path(__file__).resolve()),
    }
    exec(compile(source, str(REFERENCE), "exec"), namespace)

    store = Path(namespace["STORE"])
    source_path = store / "contexts/task-3/local/personal-memory/2024/03/context.json"
    source_digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    namespace.update(
        {
            "C": "task-3/local/admin-v2-scratch",
            "R": "task-3/local/guardrails",
            "R_CHILD": "task-3/local/guardrails/approval-and-delivery",
            "O": "task-1",
            "O_CHILD": "task-1/description",
            "ENTRY": "practice",
            "SOURCE_PATH": source_path,
            "SOURCE_DIGEST": source_digest,
        }
    )

    original_run = namespace["run"]

    def guarded_run(
        operation: str,
        args: list[str],
        *,
        method: str,
        targets: tuple[str, ...] = (),
        stdin_text: str | None = None,
    ):
        before_tree = namespace["context_tree_digest"]()
        before_registry = namespace["sha"](namespace["REGISTRY"])
        completed = original_run(
            operation,
            args,
            method=method,
            targets=targets,
            stdin_text=stdin_text,
        )
        after_tree = namespace["context_tree_digest"]()
        after_registry = namespace["sha"](namespace["REGISTRY"])
        if operation == "share":
            unchanged = before_tree == after_tree and before_registry == after_registry
            namespace["record_host"](
                "share_zero_delivery_assertion",
                command_args=args,
                context_tree_unchanged=before_tree == after_tree,
                registry_unchanged=before_registry == after_registry,
                delivery_count=0,
                result="PASS" if unchanged else "FAIL",
            )
            if not unchanged:
                raise RuntimeError("Share trial changed sender/registry state")
        if operation == "init-study":
            success_blocked = completed.returncode != 0
            namespace["record_host"](
                "init_study_zero_success_assertion",
                command_args=args,
                exit=completed.returncode,
                success_count=0 if success_blocked else 1,
                result="PASS" if success_blocked else "FAIL",
            )
            if not success_blocked:
                raise RuntimeError("init-study unexpectedly succeeded")
        return completed

    namespace["run"] = guarded_run
    namespace["main"]()


if __name__ == "__main__":
    main()
